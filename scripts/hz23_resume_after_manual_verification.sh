#!/usr/bin/env bash
# Resume the latest incomplete HZ23 round after manual JD verification or a daytime cutoff.
# Stops the observer to avoid concurrency and restarts it afterwards. No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs reports backups run

SUMMARY="reports/hz23_round_latest.json"
if [ ! -f "$SUMMARY" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=round_summary_missing"
  exit 1
fi

read -r ROUND_ID STOP_PAGE STOP_REASON COMPLETE <<< "$(python3 - "$SUMMARY" <<'PY'
import json,sys
from pathlib import Path
x=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
print(x.get('round_id') or '',x.get('stop_page') or '',x.get('stop_reason') or '','true' if x.get('commercial_segment_complete') else 'false')
PY
)"

if [ -z "$ROUND_ID" ] || [ -z "$STOP_PAGE" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=invalid_round_checkpoint"
  exit 1
fi
if [ "$COMPLETE" = "true" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=round_already_complete"
  exit 1
fi
case "$STOP_REASON" in
  risk_*|outside_daytime) ;;
  *)
    echo "===== SUMMARY ====="
    echo "STATUS=FAIL"
    echo "STEP=stop_reason_not_resumable"
    echo "STOP_REASON=$STOP_REASON"
    exit 1
    ;;
esac

INSIDE_DAYTIME="$(python3 - <<'PY'
from datetime import datetime
now=datetime.now(); cur=now.hour*60+now.minute
print('true' if 9*60+30 <= cur < 21*60+30 else 'false')
PY
)"
if [ "$INSIDE_DAYTIME" != "true" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=outside_daytime"
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
cp -a "$SUMMARY" "backups/hz23_round_${ROUND_ID}_before_resume_${STAMP}.json"
SUMMARY_BACKUP_RC=$?
if [ -f run/hz23_observer_state.json ]; then
  cp -a run/hz23_observer_state.json "backups/hz23_observer_state_before_resume_${STAMP}.json"
  STATE_BACKUP_RC=$?
else
  STATE_BACKUP_RC=2
fi

bash -n scripts/hz23_mainline_refresh.sh > logs/hz23_resume_shell_check.log 2>&1
SHELL_RC=$?
python3 -m py_compile run/hz22_prepare_all_product_page.py run/hz23_scan_current_page.py run/hz23_finalize_round.py > logs/hz23_resume_python_check.log 2>&1
PYTHON_RC=$?

if [ "$SUMMARY_BACKUP_RC" != "0" ] || [ "$STATE_BACKUP_RC" != "0" ] || [ "$SHELL_RC" != "0" ] || [ "$PYTHON_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=resume_preflight"
  echo "SUMMARY_BACKUP_RC=$SUMMARY_BACKUP_RC"
  echo "STATE_BACKUP_RC=$STATE_BACKUP_RC"
  echo "SHELL_RC=$SHELL_RC"
  echo "PYTHON_RC=$PYTHON_RC"
  exit 1
fi

sudo systemctl stop aideal-hz23-observer.service
STOP_SERVICE_RC=$?
if [ "$STOP_SERVICE_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=observer_stop_failed"
  echo "STOP_SERVICE_RC=$STOP_SERVICE_RC"
  exit 1
fi

HZ23_RESUME=1 HZ23_ROUND_ID="$ROUND_ID" HZ23_PAGE_START="$STOP_PAGE" HZ23_PAGE_END=67 HZ23_ROUND_PAGE_START=1 HZ23_RESUME_SUMMARY="$SUMMARY" bash scripts/hz23_mainline_refresh.sh > logs/hz23_resume_round.log 2>&1
RESUME_RC=$?

python3 - "$SUMMARY" "$RESUME_RC" <<'PY'
import json,random,sys
from datetime import datetime,timedelta
from pathlib import Path
summary=Path(sys.argv[1]); resume_rc=int(sys.argv[2])
x=json.loads(summary.read_text(encoding='utf-8')) if summary.exists() else {}
p=Path('run/hz23_observer_state.json')
s=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
now=datetime.now(); complete=bool(x.get('commercial_segment_complete'))
was_complete=bool(s.get('last_full_complete')) and s.get('last_full_round_id')==x.get('round_id')
s['last_full_finished_at']=now.isoformat(timespec='seconds')
s['last_full_round_id']=x.get('round_id')
s['last_full_complete']=complete
s['last_stop_reason']=x.get('stop_reason')
s['requires_manual']=bool(x.get('stop_reason') and str(x.get('stop_reason')).startswith('risk_'))
if complete and not was_complete:
    s['successful_full_rounds']=int(s.get('successful_full_rounds') or 0)+1
    nxt=(now+timedelta(days=random.randint(3,5))).replace(hour=9,minute=30,second=0,microsecond=0)+timedelta(minutes=random.randint(10,45))
else:
    nxt=(now+timedelta(days=1)).replace(hour=9,minute=30,second=0,microsecond=0)+timedelta(minutes=random.randint(10,30))
s['next_full_due_at']=nxt.isoformat(timespec='seconds')
if complete:
    probe=now+timedelta(minutes=random.randint(60,120))
    if probe.hour*60+probe.minute >= 20*60:
        probe=(now+timedelta(days=1)).replace(hour=10,minute=0,second=0,microsecond=0)+timedelta(minutes=random.randint(0,60))
    s['next_probe_due_at']=probe.isoformat(timespec='seconds')
s['last_resume_rc']=resume_rc
p.write_text(json.dumps(s,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
PY
STATE_UPDATE_RC=$?

sudo systemctl start aideal-hz23-observer.service
START_SERVICE_RC=$?
sleep 3
SERVICE_STATE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"
SERVICE_PID="$(systemctl show aideal-hz23-observer.service -p MainPID --value 2>/dev/null || true)"

read -r FINAL_COMPLETE FINAL_STOP FINAL_COMPLETED FINAL_UNFINISHED FINAL_SCANNED <<< "$(python3 - "$SUMMARY" <<'PY'
import json,sys
from pathlib import Path
x=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
print('true' if x.get('commercial_segment_complete') else 'false',x.get('stop_reason') or '',len(x.get('completed_pages') or []),len(x.get('unfinished_pages') or []),int(x.get('scanned_total') or 0))
PY
)"

STATUS=PASS
if [ "$STATE_UPDATE_RC" != "0" ] || [ "$START_SERVICE_RC" != "0" ] || [ "$SERVICE_STATE" != "active" ] || [ "$RESUME_RC" != "0" ]; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "ROUND_ID=$ROUND_ID"
echo "RESUME_FROM_PAGE=$STOP_PAGE"
echo "RESUME_RC=$RESUME_RC"
echo "STATE_UPDATE_RC=$STATE_UPDATE_RC"
echo "SERVICE_STATE=$SERVICE_STATE"
echo "SERVICE_PID=$SERVICE_PID"
echo "FULL_ROUND_COMPLETE=$FINAL_COMPLETE"
echo "STOP_REASON=$FINAL_STOP"
echo "COMPLETED_PAGE_COUNT=$FINAL_COMPLETED"
echo "UNFINISHED_PAGE_COUNT=$FINAL_UNFINISHED"
echo "SCANNED_TOTAL=$FINAL_SCANNED"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = PASS ]
