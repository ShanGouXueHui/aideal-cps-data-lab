#!/usr/bin/env bash
# Run Data Lab offline validation on the isolated Singapore datalab account.
# No JD live access, collection, MySQL initialization, publish, or sync.
# No set -e is used.

ACTION="${1:-validate-publish}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$PROJECT_DIR/config/ci-bridge.env"
TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$PROJECT_DIR/logs/ci_bridge_${TS}.log"
SUMMARY_FILE="$PROJECT_DIR/run/ci_bridge_latest.env"

record() {
  printf '%s=%s\n' "$1" "$2" | tee -a "$SUMMARY_FILE"
}

case "$ACTION" in
  validate|validate-publish) ;;
  *) echo "STATUS=FAIL"; echo "REASON=unsupported_action"; exit 2 ;;
esac

if [ ! -f "$CONFIG_FILE" ]; then
  echo "STATUS=FAIL"
  echo "REASON=ci_bridge_config_missing"
  exit 1
fi
. "$CONFIG_FILE"

mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/run" "$PROJECT_DIR/reports"
: > "$SUMMARY_FILE"

if [ "$(id -un)" != "$CI_BRIDGE_EXECUTION_USER" ]; then
  record STATUS FAIL
  record REASON unexpected_runtime_user
  exit 1
fi

cd "$PROJECT_DIR"
CD_RC=$?
if [ "$CD_RC" != "0" ] || [ ! -d .git ]; then
  record STATUS FAIL
  record REASON repository_unavailable
  exit 1
fi

git fetch origin main >> "$LOG_FILE" 2>&1
FETCH_RC=$?
LOCAL_HEAD="$(git rev-parse HEAD)"
REMOTE_HEAD="$(git rev-parse origin/main 2>/dev/null)"
record ACTION "$ACTION"
record GIT_HEAD "$LOCAL_HEAD"
record STARTED_AT "$(date -Iseconds)"
if [ "$FETCH_RC" != "0" ] || [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  record STATUS FAIL
  record REASON checkout_not_current_main
  exit 1
fi

PYTHONPATH=src python3 scripts/ops/ci_bridge_report_gate.py prepare \
  --root "$PROJECT_DIR" --stamp "$TS" >> "$LOG_FILE" 2>&1
PREPARE_RC=$?
record REPORT_PREPARE_RC "$PREPARE_RC"

PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
VENV_RC=0
if [ "$PREPARE_RC" = "0" ] && [ ! -x "$PYTHON_BIN" ]; then
  python3 -m venv "$PROJECT_DIR/.venv" >> "$LOG_FILE" 2>&1
  VENV_RC=$?
fi
record VENV_RC "$VENV_RC"

INSTALL_RC=1
if [ "$PREPARE_RC" = "0" ] && [ "$VENV_RC" = "0" ]; then
  "$PYTHON_BIN" -m pip install -e ".[browser,mysql]" >> "$LOG_FILE" 2>&1
  INSTALL_RC=$?
fi
record INSTALL_RC "$INSTALL_RC"

COMPILE_RC=1
OFFLINE_RC=1
AUDIT_RC=1
if [ "$INSTALL_RC" = "0" ]; then
  AIDEAL_OFFLINE_TEST=1 PYTHONPATH=src \
    "$PYTHON_BIN" -m compileall -q src scripts tests >> "$LOG_FILE" 2>&1
  COMPILE_RC=$?
  AIDEAL_DEPENDENCY_INSTALL_OUTCOME=success AIDEAL_OFFLINE_TEST=1 PYTHONPATH=src \
    "$PYTHON_BIN" scripts/run_offline_quality.py >> "$LOG_FILE" 2>&1
  OFFLINE_RC=$?
  AIDEAL_OFFLINE_TEST=1 PYTHONPATH=src \
    "$PYTHON_BIN" scripts/engineering_scan_full.py >> "$LOG_FILE" 2>&1
  AUDIT_RC=$?
fi
record COMPILE_RC "$COMPILE_RC"
record OFFLINE_RC "$OFFLINE_RC"
record AUDIT_RC "$AUDIT_RC"

REPORT_GATE_RC=1
if [ "$INSTALL_RC" = "0" ]; then
  PYTHONPATH=src "$PYTHON_BIN" scripts/ops/ci_bridge_report_gate.py verify \
    --root "$PROJECT_DIR" --expected-head "$LOCAL_HEAD" >> "$LOG_FILE" 2>&1
  REPORT_GATE_RC=$?
  "$PYTHON_BIN" scripts/ops/ci_bridge_summary.py | tee -a "$SUMMARY_FILE"
fi
record REPORT_GATE_RC "$REPORT_GATE_RC"

PUBLISH_RC=0
if [ "$ACTION" = "validate-publish" ]; then
  git fetch origin main >> "$LOG_FILE" 2>&1
  CURRENT_REMOTE_HEAD="$(git rev-parse origin/main 2>/dev/null)"
  if [ "$REPORT_GATE_RC" = "0" ] && [ "$CURRENT_REMOTE_HEAD" = "$LOCAL_HEAD" ]; then
    bash scripts/git_publish_files_via_worktree.sh \
      "reports: refresh Singapore CI bridge validation" \
      reports/offline_quality_latest.json \
      reports/project_engineering_audit_latest.json >> "$LOG_FILE" 2>&1
    PUBLISH_RC=$?
  else
    PUBLISH_RC=1
    record PUBLISH_REASON stale_or_invalid_reports
  fi
fi
record PUBLISH_RC "$PUBLISH_RC"

FINAL_RC=0
for RC in "$PREPARE_RC" "$VENV_RC" "$INSTALL_RC" "$COMPILE_RC" "$OFFLINE_RC" "$AUDIT_RC" "$REPORT_GATE_RC" "$PUBLISH_RC"; do
  if [ "$RC" != "0" ]; then FINAL_RC=1; fi
done
record FINISHED_AT "$(date -Iseconds)"
record LOG_FILE "$LOG_FILE"
if [ "$FINAL_RC" = "0" ]; then record STATUS PASS; else record STATUS FAIL; fi

cat "$SUMMARY_FILE"
echo "===== LOG TAIL ====="
tail -n 120 "$LOG_FILE" 2>/dev/null
exit "$FINAL_RC"
