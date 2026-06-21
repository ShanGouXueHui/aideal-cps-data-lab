#!/usr/bin/env bash
# Stop stale Singapore audit publishers and run offline validation. No set -e.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
TS="$(date -u +%Y%m%d_%H%M%S)"
LOG_DIR="$PROJECT_DIR/logs"
REPORT="$PROJECT_DIR/reports/report_authority_recovery_latest.json"
PATTERN='run_engineering_scan_and_publish|engineering_scan_and_publish|git_publish_files_via_worktree|project_engineering_audit_latest|offline_quality_latest|reports: update engineering audit baseline'
UNIT_PATTERN='audit|engineering|quality|ci-bridge|ci_bridge|git-publish|publisher'

if [ "$(id -un)" != "datalab" ]; then
  echo "STATUS=FAIL"
  echo "REASON=unexpected_user"
  echo "CURRENT_USER=$(id -un)"
  exit 1
fi
if ! cd "$PROJECT_DIR"; then
  echo "STATUS=FAIL"
  echo "REASON=repo_missing"
  exit 1
fi

mkdir -p "$LOG_DIR" "$PROJECT_DIR/reports" "$PROJECT_DIR/run"
GIT_HEAD_BEFORE="$(git rev-parse HEAD 2>/dev/null)"
CRON_CHANGED=0
SYSTEMD_STOPPED=0
PROCESS_KILLED=0

crontab -l > "$LOG_DIR/stale_audit_crontab_before_$TS.log" 2>/dev/null
CRON_RC=$?
if [ "$CRON_RC" = "0" ]; then
  grep -Ev "$PATTERN" "$LOG_DIR/stale_audit_crontab_before_$TS.log" \
    > "$LOG_DIR/stale_audit_crontab_after_$TS.log"
  if ! cmp -s "$LOG_DIR/stale_audit_crontab_before_$TS.log" \
      "$LOG_DIR/stale_audit_crontab_after_$TS.log"; then
    crontab "$LOG_DIR/stale_audit_crontab_after_$TS.log" \
      > "$LOG_DIR/stale_audit_crontab_apply_$TS.log" 2>&1
    if [ "$?" = "0" ]; then
      CRON_CHANGED=1
    fi
  fi
fi

systemctl --user list-unit-files --no-legend \
  > "$LOG_DIR/stale_audit_systemd_units_$TS.log" 2>&1
awk '{print $1}' "$LOG_DIR/stale_audit_systemd_units_$TS.log" \
  | grep -Ei "$UNIT_PATTERN" \
  > "$LOG_DIR/stale_audit_systemd_candidates_$TS.log" 2>/dev/null
while IFS= read -r unit; do
  if [ -n "$unit" ]; then
    systemctl --user stop "$unit" >> "$LOG_DIR/stale_audit_systemd_stop_$TS.log" 2>&1
    systemctl --user disable "$unit" >> "$LOG_DIR/stale_audit_systemd_stop_$TS.log" 2>&1
    SYSTEMD_STOPPED=$((SYSTEMD_STOPPED + 1))
  fi
done < "$LOG_DIR/stale_audit_systemd_candidates_$TS.log"

pgrep -afu "$(id -un)" "$PATTERN" \
  > "$LOG_DIR/stale_audit_processes_before_$TS.log" 2>/dev/null
while IFS= read -r line; do
  pid="$(printf '%s\n' "$line" | awk '{print $1}')"
  case "$pid" in ""|"$BASHPID"|"$PPID") continue ;; esac
  case "$line" in *recover_report_authority_on_sg.sh*) continue ;; esac
  kill "$pid" >> "$LOG_DIR/stale_audit_process_kill_$TS.log" 2>&1
  if [ "$?" = "0" ]; then
    PROCESS_KILLED=$((PROCESS_KILLED + 1))
  fi
done < "$LOG_DIR/stale_audit_processes_before_$TS.log"

GIT_HEAD_AFTER_STOP="$(git rev-parse HEAD 2>/dev/null)"
python3 - <<PY
import json
from pathlib import Path
payload = {
  "schema_version": "report-authority-recovery/v1",
  "generated_at": "$TS",
  "runtime_user": "datalab",
  "git_head_before": "$GIT_HEAD_BEFORE",
  "git_head_after_stop": "$GIT_HEAD_AFTER_STOP",
  "cron_changed": bool(int("$CRON_CHANGED")),
  "systemd_units_stopped": int("$SYSTEMD_STOPPED"),
  "processes_killed": int("$PROCESS_KILLED"),
  "main_publish_forbidden": True,
  "runtime_evidence_target": "runtime-evidence",
}
Path("$REPORT").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

bash scripts/git_publish_files_via_worktree.sh \
  "reports: update runtime evidence authority recovery" \
  reports/report_authority_recovery_latest.json
PUBLISH_RC=$?

bash scripts/ops/run_data_lab_ci_bridge.sh validate-publish
CI_RC=$?

REMOTE_HEAD="$(git rev-parse HEAD 2>/dev/null)"
echo "===== REPORT AUTHORITY RECOVERY SUMMARY ====="
echo "GIT_HEAD_BEFORE=$GIT_HEAD_BEFORE"
echo "GIT_HEAD_AFTER_STOP=$GIT_HEAD_AFTER_STOP"
echo "REMOTE_HEAD=$REMOTE_HEAD"
echo "CRON_CHANGED=$CRON_CHANGED"
echo "SYSTEMD_STOPPED=$SYSTEMD_STOPPED"
echo "PROCESS_KILLED=$PROCESS_KILLED"
echo "RUNTIME_EVIDENCE_PUBLISH_RC=$PUBLISH_RC"
echo "CI_BRIDGE_RC=$CI_RC"
if [ "$PUBLISH_RC" = "0" ] && [ "$CI_RC" = "0" ]; then
  echo "STATUS=PASS"
  exit 0
fi
echo "STATUS=FAIL"
exit 1
