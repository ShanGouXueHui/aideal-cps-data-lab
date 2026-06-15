#!/usr/bin/env bash
# Show compact status for the background HZ23 resume. No set -e.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1

PID_FILE="run/hz23_resume_nohup.pid"
STATE_FILE="run/hz23_resume_nohup.state"
SUMMARY_FILE="reports/hz23_round_latest.json"
LOG_FILE="logs/hz23_resume_nohup.log"

RUNNER_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
PROCESS_STATE="stopped"
if [ -n "$RUNNER_PID" ] && kill -0 "$RUNNER_PID" 2>/dev/null; then
  PROCESS_STATE="running"
fi

STATE=""
RESUME_RC=""
STARTED_AT=""
FINISHED_AT=""
if [ -f "$STATE_FILE" ]; then
  STATE="$(awk -F= '$1=="STATE"{print substr($0,index($0,"=")+1)}' "$STATE_FILE" | tail -n 1)"
  RESUME_RC="$(awk -F= '$1=="RESUME_RC"{print substr($0,index($0,"=")+1)}' "$STATE_FILE" | tail -n 1)"
  STARTED_AT="$(awk -F= '$1=="STARTED_AT"{print substr($0,index($0,"=")+1)}' "$STATE_FILE" | tail -n 1)"
  FINISHED_AT="$(awk -F= '$1=="FINISHED_AT"{print substr($0,index($0,"=")+1)}' "$STATE_FILE" | tail -n 1)"
fi

ROUND_STATUS="$(python3 - "$SUMMARY_FILE" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
if not p.exists():
    print('ROUND_ID=')
    print('FULL_ROUND_COMPLETE=false')
    print('STOP_PAGE=')
    print('STOP_REASON=')
    print('COMPLETED_PAGE_COUNT=0')
    print('UNFINISHED_PAGE_COUNT=67')
    print('SCANNED_TOTAL=0')
else:
    x=json.loads(p.read_text(encoding='utf-8'))
    print(f"ROUND_ID={x.get('round_id') or ''}")
    print(f"FULL_ROUND_COMPLETE={str(bool(x.get('commercial_segment_complete'))).lower()}")
    print(f"STOP_PAGE={x.get('stop_page') or ''}")
    print(f"STOP_REASON={x.get('stop_reason') or ''}")
    print(f"COMPLETED_PAGE_COUNT={len(x.get('completed_pages') or [])}")
    print(f"UNFINISHED_PAGE_COUNT={len(x.get('unfinished_pages') or [])}")
    print(f"SCANNED_TOTAL={int(x.get('scanned_total') or 0)}")
PY
)"

SERVICE_STATE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"
SERVICE_PID="$(systemctl show aideal-hz23-observer.service -p MainPID --value 2>/dev/null || true)"

echo "===== SUMMARY ====="
echo "PROCESS_STATE=$PROCESS_STATE"
echo "RUNNER_STATE=${STATE:-unknown}"
echo "RUNNER_PID=$RUNNER_PID"
echo "STARTED_AT=$STARTED_AT"
echo "FINISHED_AT=$FINISHED_AT"
echo "RESUME_RC=$RESUME_RC"
echo "SERVICE_STATE=$SERVICE_STATE"
echo "SERVICE_PID=$SERVICE_PID"
printf '%s\n' "$ROUND_STATUS"
echo "LOG=$LOG_FILE"
