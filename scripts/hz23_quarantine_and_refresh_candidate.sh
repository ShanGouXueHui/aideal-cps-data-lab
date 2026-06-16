#!/usr/bin/env bash
# Quarantine unsafe HZ20 source rows, refresh manifest gates, and publish evidence.
# No JD operation and no MySQL access. No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs reports backups

if pgrep -af 'scripts/[h]z23_mainline_refresh.sh|scripts/[h]z23_resume_after_manual_verification.sh' >/dev/null 2>&1; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=collection_process_running"
  exit 1
fi

PYTHONPATH=src python3 -m py_compile \
  scripts/hz23_quarantine_unsafe_source_rows.py \
  scripts/hz23_refresh_manifest_gates.py \
  > logs/hz23_quarantine_compile.log 2>&1
COMPILE_RC=$?
if [ "$COMPILE_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=compile"
  echo "COMPILE_RC=$COMPILE_RC"
  exit 1
fi

PYTHONPATH=src python3 scripts/hz23_quarantine_unsafe_source_rows.py \
  > logs/hz23_quarantine_dry_run.log 2>&1
DRY_RUN_RC=$?
UNSAFE_BEFORE="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/hz23_hz20_quarantine_latest.json')
try: print(int(json.loads(p.read_text(encoding='utf-8')).get('unsafe_row_count') or 0))
except Exception: print(-1)
PY
)"

if [ "$DRY_RUN_RC" != "0" ] || [ "$UNSAFE_BEFORE" -lt 0 ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=quarantine_dry_run"
  echo "DRY_RUN_RC=$DRY_RUN_RC"
  echo "UNSAFE_BEFORE=$UNSAFE_BEFORE"
  exit 1
fi

OLD_SERVICE_STATE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"
if [ "$OLD_SERVICE_STATE" = "active" ]; then
  sudo systemctl stop aideal-hz23-observer.service
  STOP_RC=$?
else
  STOP_RC=0
fi
if [ "$STOP_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=observer_stop"
  echo "STOP_RC=$STOP_RC"
  exit 1
fi

PYTHONPATH=src python3 scripts/hz23_quarantine_unsafe_source_rows.py --execute \
  > logs/hz23_quarantine_execute.log 2>&1
QUARANTINE_RC=$?

if [ "$QUARANTINE_RC" = "0" ]; then
  PYTHONPATH=src python3 scripts/hz23_refresh_manifest_gates.py \
    > logs/hz23_manifest_gate_refresh.log 2>&1
  REFRESH_RC=$?
else
  REFRESH_RC=99
fi

if [ "$OLD_SERVICE_STATE" = "active" ]; then
  sudo systemctl start aideal-hz23-observer.service
  START_RC=$?
else
  START_RC=0
fi
sleep 2
SERVICE_STATE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"
SERVICE_PID="$(systemctl show aideal-hz23-observer.service -p MainPID --value 2>/dev/null || true)"

PUBLISH_FILES=(
  reports/hz23_hz20_quarantine_latest.json
  reports/hz23_manifest_gate_refresh_latest.json
  data/export/aideal_cps_products_commercial_candidate_manifest.json
)
bash scripts/git_publish_files_via_worktree.sh \
  "reports: quarantine HZ20 source rows and refresh candidate gates" \
  "${PUBLISH_FILES[@]}" \
  > logs/hz23_quarantine_publish.log 2>&1
PUBLISH_RC=$?

read -r UNSAFE_AFTER CANDIDATE_ROWS INTEGRITY_READY SUCCESSFUL_PROBES OBSERVATION_READY FAILURES <<< "$(python3 - <<'PY'
import json
from pathlib import Path
q=json.loads(Path('reports/hz23_manifest_gate_refresh_latest.json').read_text(encoding='utf-8'))
print(
 int((q.get('source_audit') or {}).get('unsafe') or 0),
 int(q.get('candidate_row_count') or 0),
 'true' if q.get('candidate_integrity_ready') else 'false',
 int(q.get('successful_probes') or 0),
 'true' if q.get('observation_ready') else 'false',
 ','.join(q.get('gate_failures') or []) or '-',
)
PY
)"

STATUS=PASS
if [ "$QUARANTINE_RC" != "0" ] || [ "$REFRESH_RC" != "0" ] || [ "$START_RC" != "0" ] || [ "$PUBLISH_RC" != "0" ]; then STATUS=FAIL; fi
if [ "$OLD_SERVICE_STATE" = "active" ] && [ "$SERVICE_STATE" != "active" ]; then STATUS=FAIL; fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "COMPILE_RC=$COMPILE_RC"
echo "DRY_RUN_RC=$DRY_RUN_RC"
echo "UNSAFE_BEFORE=$UNSAFE_BEFORE"
echo "QUARANTINE_RC=$QUARANTINE_RC"
echo "REFRESH_RC=$REFRESH_RC"
echo "UNSAFE_AFTER=$UNSAFE_AFTER"
echo "CANDIDATE_ROWS=$CANDIDATE_ROWS"
echo "CANDIDATE_INTEGRITY_READY=$INTEGRITY_READY"
echo "SUCCESSFUL_PROBES=$SUCCESSFUL_PROBES"
echo "OBSERVATION_READY=$OBSERVATION_READY"
echo "GATE_FAILURES=$FAILURES"
echo "SERVICE_STATE=$SERVICE_STATE"
echo "SERVICE_PID=$SERVICE_PID"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = PASS ]
