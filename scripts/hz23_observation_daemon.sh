#!/usr/bin/env bash
# Persistent HZ23 observer.
# - No browser automation at night.
# - One lightweight read-only catalog probe each day.
# - One complete refresh cycle every random 3-5 days.
# - Writes heartbeats and checkpoints for 2-3 day observation.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
. config/hz23-service.env
mkdir -p logs reports run data/state docs/ops

STATE="run/hz23_observer_state.json"
STATUS="reports/hz23_observer_status_latest.json"
LOG="logs/hz23_observer.log"
DAY_START="$HZ23_DAY_START"
DAY_END="$HZ23_DAY_END"
LOOP_MIN="$HZ23_LOOP_SLEEP_MIN"
LOOP_MAX="$HZ23_LOOP_SLEEP_MAX"

init_state() {
  if [ -f "$STATE" ]; then
    python3 - "$STATE" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]); s=json.loads(p.read_text(encoding='utf-8'))
s.setdefault('observation_started_at',s.get('created_at'))
s.setdefault('successful_probes',0)
s.setdefault('failed_probes',0)
s.setdefault('first_successful_probe_at',None)
s.setdefault('last_probe_ok',None)
s.setdefault('last_probe_reason',None)
p.write_text(json.dumps(s,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
PY
    return
  fi
  python3 - "$STATE" <<'PY'
import json,random,sys
from datetime import datetime,timedelta
from pathlib import Path
now=datetime.now()
days=random.randint(3,5)
full=(now+timedelta(days=days)).replace(hour=9,minute=30,second=0,microsecond=0)+timedelta(minutes=random.randint(10,45))
probe=now.replace(hour=10,minute=0,second=0,microsecond=0)+timedelta(minutes=random.randint(0,60))
if probe<=now: probe+=timedelta(days=1)
state={
  'version':2,
  'created_at':now.isoformat(timespec='seconds'),
  'observation_started_at':now.isoformat(timespec='seconds'),
  'next_full_due_at':full.isoformat(timespec='seconds'),
  'next_probe_due_at':probe.isoformat(timespec='seconds'),
  'last_probe_at':None,
  'first_successful_probe_at':None,
  'successful_probes':0,
  'failed_probes':0,
  'last_probe_ok':None,
  'last_probe_reason':None,
  'last_full_started_at':None,
  'last_full_finished_at':None,
  'last_full_round_id':None,
  'last_full_complete':None,
  'last_stop_reason':None,
  'requires_manual':False,
  'successful_full_rounds':0,
}
Path(sys.argv[1]).write_text(json.dumps(state,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
PY
}

inside_daytime() {
  python3 - "$DAY_START" "$DAY_END" <<'PY'
from datetime import datetime
import sys
start,end=sys.argv[1],sys.argv[2]
now=datetime.now(); cur=now.hour*60+now.minute
sh,sm=map(int,start.split(':')); eh,em=map(int,end.split(':'))
print('true' if sh*60+sm <= cur < eh*60+em else 'false')
PY
}

due_field() {
  python3 - "$STATE" "$1" <<'PY'
import json,sys
from datetime import datetime
from pathlib import Path
try:
    v=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')).get(sys.argv[2])
    print('true' if v and datetime.now()>=datetime.fromisoformat(v) else 'false')
except Exception:
    print('false')
PY
}

write_status() {
  python3 - "$STATE" "$STATUS" "$1" <<'PY'
import json,sys,os
from datetime import datetime
from pathlib import Path
state={}
try: state=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
except Exception: pass
status={'ts':datetime.now().isoformat(timespec='seconds'),'pid':os.getppid(),'mode':sys.argv[3],'state':state}
latest=Path('reports/hz23_round_latest.json')
if latest.exists():
    try: status['latest_round']=json.loads(latest.read_text(encoding='utf-8'))
    except Exception: pass
manifest=Path('data/export/aideal_cps_products_commercial_candidate_manifest.json')
if manifest.exists():
    try: status['candidate_manifest']=json.loads(manifest.read_text(encoding='utf-8'))
    except Exception: pass
Path(sys.argv[2]).write_text(json.dumps(status,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
PY
}

schedule_next_probe() {
  python3 - "$STATE" "$1" "$2" <<'PY'
import json,random,sys
from datetime import datetime,timedelta
from pathlib import Path
p=Path(sys.argv[1]); success=sys.argv[2]=='true'; reason=sys.argv[3] or None
s=json.loads(p.read_text(encoding='utf-8')); now=datetime.now()
nxt=(now+timedelta(days=1)).replace(hour=10,minute=0,second=0,microsecond=0)+timedelta(minutes=random.randint(0,60))
s['next_probe_due_at']=nxt.isoformat(timespec='seconds')
s['last_probe_at']=now.isoformat(timespec='seconds')
s['last_probe_ok']=success
s['last_probe_reason']=reason
if success:
    s['successful_probes']=int(s.get('successful_probes') or 0)+1
    s['first_successful_probe_at']=s.get('first_successful_probe_at') or now.isoformat(timespec='seconds')
else:
    s['failed_probes']=int(s.get('failed_probes') or 0)+1
p.write_text(json.dumps(s,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
PY
}

refresh_manifest_after_successful_probe() {
  if [ "$1" = "true" ]; then
    echo "$(date '+%F %T') HZ23_GATE_STATUS_REFRESH_ONLY reason=avoid_duplicate_round_finalize" | tee -a "$LOG"
  fi
  return 0
}

schedule_after_full() {
  python3 - "$STATE" "$1" "$2" "$3" <<'PY'
import json,random,sys
from datetime import datetime,timedelta
from pathlib import Path
p=Path(sys.argv[1]); complete=sys.argv[2]=='true'; reason=sys.argv[3] or None; round_id=sys.argv[4]
s=json.loads(p.read_text(encoding='utf-8')); now=datetime.now()
s['last_full_finished_at']=now.isoformat(timespec='seconds'); s['last_full_round_id']=round_id; s['last_full_complete']=complete; s['last_stop_reason']=reason
s['requires_manual']=bool(reason and str(reason).startswith('risk_'))
if complete:
    s['successful_full_rounds']=int(s.get('successful_full_rounds') or 0)+1
    nxt=(now+timedelta(days=random.randint(3,5))).replace(hour=9,minute=30,second=0,microsecond=0)+timedelta(minutes=random.randint(10,45))
else:
    nxt=(now+timedelta(days=1)).replace(hour=9,minute=30,second=0,microsecond=0)+timedelta(minutes=random.randint(10,30))
s['next_full_due_at']=nxt.isoformat(timespec='seconds')
p.write_text(json.dumps(s,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
PY
}

run_probe() {
  PAGE="$(python3 - <<'PY'
import random
print(random.choice([1,17,34,50,67]))
PY
)"
  TS="$(date +%Y%m%d_%H%M%S)"
  ROUND="probe_${TS}"
  PREP="reports/hz23_probe_prepare_latest.json"
  SCAN="reports/hz23_probe_scan_latest.json"
  echo "$(date '+%F %T') HZ23_PROBE_START page=$PAGE" | tee -a "$LOG"
  .venv-browser/bin/python run/hz22_prepare_all_product_page.py "$PAGE" "$PREP" >> "$LOG" 2>&1
  PREP_RC=$?
  if [ "$PREP_RC" = "0" ]; then
    .venv-browser/bin/python run/hz23_scan_current_page.py "$PAGE" "$ROUND" "$SCAN" >> "$LOG" 2>&1
    SCAN_RC=$?
  else
    SCAN_RC=99
  fi
  read -r PROBE_OK PROBE_REASON <<< "$(python3 - "$PREP_RC" "$SCAN_RC" "$SCAN" <<'PY'
import json,sys
from pathlib import Path
prep_rc=int(sys.argv[1]); scan_rc=int(sys.argv[2]); p=Path(sys.argv[3])
if prep_rc!=0:
    print('false prepare_failed')
elif scan_rc!=0:
    print('false scan_failed')
elif not p.exists():
    print('false scan_report_missing')
else:
    try:
        x=json.loads(p.read_text(encoding='utf-8'))
        ok=bool(x.get('ok')) and not (x.get('risk') or []) and int(x.get('scanned') or 0)>=55
        print('true' if ok else 'false', '' if ok else (x.get('reason') or 'semantic_failure'))
    except Exception:
        print('false scan_report_invalid')
PY
)"
  echo "$(date '+%F %T') HZ23_PROBE_DONE page=$PAGE prep_rc=$PREP_RC scan_rc=$SCAN_RC probe_ok=$PROBE_OK reason=$PROBE_REASON" | tee -a "$LOG"
  schedule_next_probe "$PROBE_OK" "$PROBE_REASON"
  refresh_manifest_after_successful_probe "$PROBE_OK"
  write_status "probe_done"
  git add "$PREP" "$SCAN" "$STATE" "$STATUS" 2>/dev/null || true
  git commit -m "docs: publish HZ23 daily observation probe" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true
}

run_full() {
  ROUND="$(date +%Y%m%d_%H%M%S)"
  python3 - "$STATE" "$ROUND" <<'PY'
import json,sys
from datetime import datetime
from pathlib import Path
p=Path(sys.argv[1]); s=json.loads(p.read_text(encoding='utf-8'))
s['last_full_started_at']=datetime.now().isoformat(timespec='seconds'); s['last_full_round_id']=sys.argv[2]; s['requires_manual']=False
p.write_text(json.dumps(s,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
PY
  write_status "full_running"
  echo "$(date '+%F %T') HZ23_FULL_START round=$ROUND" | tee -a "$LOG"
  HZ23_ROUND_ID="$ROUND" HZ23_PAGE_START=1 HZ23_PAGE_END=67 HZ23_DAY_START="$DAY_START" HZ23_DAY_END="$DAY_END" bash scripts/hz23_mainline_refresh.sh >> "$LOG" 2>&1
  RC=$?
  SUMMARY="reports/hz23_round_${ROUND}_latest.json"
  read -r COMPLETE REASON <<< "$(python3 - "$SUMMARY" <<'PY'
import json,sys
from pathlib import Path
try:
    x=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    print('true' if x.get('commercial_segment_complete') else 'false', x.get('stop_reason') or '')
except Exception:
    print('false summary_missing')
PY
)"
  schedule_after_full "$COMPLETE" "$REASON" "$ROUND"
  write_status "full_done"
  echo "$(date '+%F %T') HZ23_FULL_DONE round=$ROUND rc=$RC complete=$COMPLETE reason=$REASON" | tee -a "$LOG"
}

init_state
echo "$(date '+%F %T') HZ23_OBSERVER_START pid=$$ day_window=$DAY_START-$DAY_END" | tee -a "$LOG"

while true; do
  if [ "$(inside_daytime)" = "true" ]; then
    if [ "$(due_field next_full_due_at)" = "true" ]; then
      run_full
    elif [ "$(due_field next_probe_due_at)" = "true" ]; then
      run_probe
    else
      write_status "daytime_idle"
    fi
  else
    write_status "night_rest"
  fi
  SLEEP_S="$(python3 - "$LOOP_MIN" "$LOOP_MAX" <<'PY'
import random,sys
print(round(random.uniform(float(sys.argv[1]),float(sys.argv[2])),2))
PY
)"
  sleep "$SLEEP_S"
done
