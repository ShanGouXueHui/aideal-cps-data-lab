#!/usr/bin/env bash
# Formal single-instance HZ23 observation supervisor.
#
# Contract:
# - Exactly one supervisor instance by flock.
# - No legacy daemon/scheduler concurrent browser use.
# - Resume the existing HZ23 observation round from the first unfinished page.
# - If JD verification/risk is detected, pause collection and wait for manual verification.
# - During pause, run only a lightweight daytime probe every N seconds to detect whether
#   manual verification has restored access; no automatic verification bypass is attempted.
# - Runtime reports are JSON-only and published to runtime-evidence via git_publish_files_via_worktree.sh.
# - Rolling progress is latest-only: reports/hz23_formal_progress_latest.json.
# - No HZ24/MySQL/publish/AIdeal CPS sync is started here.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"
. config/hz23-service.env
mkdir -p logs reports run data/state data/export

ROUND_ID="${HZ23_ROUND_ID:-hz23_obs_20260624_093503}"
PAGE_END="${HZ23_PAGE_END:-67}"
ROUND_PAGE_START="${HZ23_ROUND_PAGE_START:-1}"
DAY_START="${HZ23_DAY_START:-09:30}"
DAY_END="${HZ23_DAY_END:-21:30}"
DAY_PROBE_INTERVAL_SECONDS="${HZ23_VERIFY_DAY_PROBE_INTERVAL_SECONDS:-3600}"
NIGHT_HEARTBEAT_INTERVAL_SECONDS="${HZ23_VERIFY_NIGHT_HEARTBEAT_INTERVAL_SECONDS:-10800}"
IDLE_INTERVAL_SECONDS="${HZ23_SUPERVISOR_IDLE_INTERVAL_SECONDS:-600}"
PROGRESS_PUBLISH_INTERVAL_SECONDS="${HZ23_PROGRESS_PUBLISH_INTERVAL_SECONDS:-300}"
MAX_RUNS="${HZ23_SUPERVISOR_MAX_RUNS:-0}"

LOCK_FILE="run/hz23_formal_supervisor.lock"
PID_FILE="run/hz23_formal_supervisor.pid"
STATE="run/hz23_formal_supervisor_state.json"
STATUS="reports/hz23_formal_supervisor_status_latest.json"
REPORT="reports/hz23_formal_supervisor_latest.json"
LOG="logs/hz23_formal_supervisor.log"
RESUME_REPORT="reports/hz23_observation_resume_auto_latest.json"
RESUME_SUMMARY="reports/hz23_round_${ROUND_ID}_latest.json"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "===== SUMMARY ====="
  echo "SUPERVISOR_RC=75"
  echo "REASON=hz23_formal_supervisor_lock_busy"
  echo "PID_FILE=$PID_FILE"
  [ -f "$PID_FILE" ] && cat "$PID_FILE" || true
  exit 75
fi

echo $$ > "$PID_FILE"

log_msg() {
  echo "$(date '+%F %T') $*" | tee -a "$LOG"
}

inside_daytime() {
  python3 - "$DAY_START" "$DAY_END" <<'PY'
from datetime import datetime
import sys
start,end=sys.argv[1],sys.argv[2]
now=datetime.now()
cur=now.hour*60+now.minute
sh,sm=map(int,start.split(':'))
eh,em=map(int(end.split(':')[0]), int(end.split(':')[1])) if False else map(int,end.split(':'))
print('true' if sh*60+sm <= cur < eh*60+em else 'false')
PY
}

safe_sleep() {
  seconds="$1"
  [ -z "$seconds" ] && seconds=60
  sleep "$seconds"
}

cleanup_legacy_backgrounds() {
  CURRENT="$$"
  CLEAN_RE='scripts/hz23_observation_daemon.sh|schedule_hz23_observation_daytime.sh|schedule_hz23_observation_resume_daytime.sh|run_hz23_smoke_now|hz23_mainline_refresh.sh|run/hz22_prepare_all_product_page.py|run/hz23_scan_current_page.py|scripts/hz21_run_strong_risk_collector.sh'
  ps -eo pid=,ppid=,cmd= | grep -E "$CLEAN_RE" | grep -v grep | while read -r pid ppid cmd; do
    [ -z "$pid" ] && continue
    [ "$pid" = "$CURRENT" ] && continue
    case "$cmd" in
      *hz23_formal_supervisor.sh*) continue ;;
      *start_hz23_formal_supervisor.sh*) continue ;;
      *hz23_formal_progress_publisher.sh*) continue ;;
    esac
    log_msg "HZ23_CLEANUP_LEGACY pid=$pid ppid=$ppid cmd=$cmd"
    kill -TERM "$pid" 2>/dev/null || true
    for c in $(pgrep -P "$pid" 2>/dev/null); do
      log_msg "HZ23_CLEANUP_LEGACY_CHILD pid=$c parent=$pid"
      kill -TERM "$c" 2>/dev/null || true
    done
  done
  sleep 2
  ps -eo pid=,ppid=,cmd= | grep -E "$CLEAN_RE" | grep -v grep | while read -r pid ppid cmd; do
    [ -z "$pid" ] && continue
    [ "$pid" = "$CURRENT" ] && continue
    case "$cmd" in
      *hz23_formal_supervisor.sh*) continue ;;
      *start_hz23_formal_supervisor.sh*) continue ;;
      *hz23_formal_progress_publisher.sh*) continue ;;
    esac
    kill -KILL "$pid" 2>/dev/null || true
    for c in $(pgrep -P "$pid" 2>/dev/null); do
      kill -KILL "$c" 2>/dev/null || true
    done
  done
  rm -f run/hz23_observation_daytime_scheduler.pid run/hz23_observation_resume_daytime_scheduler.pid run/hz23_smoke_daytime_scheduler.pid 2>/dev/null || true
}

ensure_summary_from_runtime_evidence() {
  git fetch origin main runtime-evidence >/dev/null 2>&1 || true
  git checkout origin/runtime-evidence -- "$RESUME_SUMMARY" >/dev/null 2>&1
  rc=$?
  if [ "$rc" != "0" ] || [ ! -f "$RESUME_SUMMARY" ]; then
    log_msg "HZ23_RESUME_SUMMARY_CHECKOUT_FAILED round=$ROUND_ID rc=$rc summary=$RESUME_SUMMARY"
    return 2
  fi
  return 0
}

next_unfinished_page() {
  python3 - "$RESUME_SUMMARY" "$ROUND_PAGE_START" "$PAGE_END" <<'PY'
import json, sys
from pathlib import Path
p=Path(sys.argv[1])
start=int(sys.argv[2])
end=int(sys.argv[3])
try:
    x=json.loads(p.read_text(encoding='utf-8'))
    completed=set(int(v) for v in (x.get('completed_pages') or []) if isinstance(v, int))
    for page in range(start, end+1):
        if page not in completed:
            print(page)
            raise SystemExit(0)
    print(0)
except Exception:
    print(-1)
PY
}

write_state() {
  mode="$1"
  extra="$2"
  python3 - "$STATE" "$STATUS" "$REPORT" "$ROUND_ID" "$mode" "$extra" "$RESUME_SUMMARY" "$RESUME_REPORT" <<'PY'
import json, os, sys
from datetime import datetime
from pathlib import Path
state_path, status_path, report_path = map(Path, sys.argv[1:4])
round_id, mode, extra = sys.argv[4:7]
summary_path=Path(sys.argv[7])
resume_report_path=Path(sys.argv[8])
state={}
if state_path.exists():
    try: state=json.loads(state_path.read_text(encoding='utf-8'))
    except Exception: state={}
state.update({
  'schema_version':'hz23-formal-supervisor-state/v1',
  'updated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'pid':os.getppid(),
  'round_id':round_id,
  'mode':mode,
  'extra':extra,
})
summary={}
if summary_path.exists():
    try: summary=json.loads(summary_path.read_text(encoding='utf-8'))
    except Exception as exc: summary={'parse_error':repr(exc)}
resume_report={}
if resume_report_path.exists():
    try: resume_report=json.loads(resume_report_path.read_text(encoding='utf-8'))
    except Exception as exc: resume_report={'parse_error':repr(exc)}
payload={
  'schema_version':'hz23-formal-supervisor-status/v1',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'state':state,
  'summary':summary,
  'resume_report_digest':{
    'generated_at':resume_report.get('generated_at'),
    'run_rc':resume_report.get('run_rc'),
    'log_path':resume_report.get('log_path'),
    'status':resume_report.get('status'),
  }
}
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
status_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
report_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
PY
}

publish_status() {
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ23 formal supervisor status" \
    "$STATUS" "$REPORT" "$STATE" \
    > logs/hz23_formal_supervisor_publish.log 2>&1
}

classify_run_outcome() {
  python3 - "$RESUME_SUMMARY" "$RUN_LOG" <<'PY'
import json, sys
from pathlib import Path
summary_path=Path(sys.argv[1]); log_path=Path(sys.argv[2])
summary={}
try: summary=json.loads(summary_path.read_text(encoding='utf-8'))
except Exception: pass
log=''
if log_path.exists():
    log=log_path.read_text(encoding='utf-8', errors='replace')[-20000:]
complete=bool(summary.get('commercial_segment_complete'))
stop_reason=str(summary.get('stop_reason') or '')
stop_page=summary.get('stop_page')
risk=('risk_after_jump' in log or 'risk_handler' in log or '京东验证' in log or '快速验证' in log or stop_reason.startswith('risk_'))
if complete:
    print('complete', stop_page or '', stop_reason)
elif risk:
    print('paused_for_manual_verification', stop_page or '', stop_reason or 'risk_detected')
else:
    print('stopped_non_risk', stop_page or '', stop_reason or 'unknown')
PY
}

write_resume_auto_report() {
  run_rc="$1"
  run_log="$2"
  status="$3"
  stop_page="$4"
  stop_reason="$5"
  python3 - "$ROUND_ID" "$run_rc" "$run_log" "$RESUME_REPORT" "$status" "$stop_page" "$stop_reason" <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path
round_id=sys.argv[1]
run_rc=int(sys.argv[2])
log_path=Path(sys.argv[3])
report_path=Path(sys.argv[4])
status=sys.argv[5]
stop_page=sys.argv[6] or None
stop_reason=sys.argv[7] or None
summary_path=Path(f'reports/hz23_round_{round_id}_latest.json')
summary={}
if summary_path.exists():
    try: summary=json.loads(summary_path.read_text(encoding='utf-8'))
    except Exception as exc: summary={'summary_parse_error':repr(exc)}
log_tail=[]
if log_path.exists():
    log_tail=log_path.read_text(encoding='utf-8', errors='replace').splitlines()[-220:]
payload={
  'schema_version':'hz23-observation-resume-auto/v1',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'round_id':round_id,
  'run_rc':run_rc,
  'status':status,
  'stop_page':int(stop_page) if str(stop_page or '').isdigit() else stop_page,
  'stop_reason':stop_reason,
  'summary_path':str(summary_path),
  'log_path':str(log_path),
  'summary':summary,
  'log_tail':log_tail,
}
report_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
PY
}

publish_run_result() {
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ23 formal supervisor resume result" \
    "$RESUME_REPORT" "$RESUME_SUMMARY" reports/hz23_round_latest.json "$STATUS" "$REPORT" "$STATE" \
    > logs/hz23_formal_supervisor_run_publish.log 2>&1
}

probe_manual_verified() {
  page="$1"
  prep="reports/hz23_formal_probe_prepare_latest.json"
  rm -f "$prep"
  log_msg "HZ23_VERIFY_PROBE_START page=$page"
  .venv-browser/bin/python run/hz22_prepare_all_product_page.py "$page" "$prep" >> "$LOG" 2>&1
  rc=$?
  python3 - "$prep" "$rc" <<'PY'
import json, sys
from pathlib import Path
p=Path(sys.argv[1]); rc=int(sys.argv[2])
if rc != 0 or not p.exists():
    print('false')
    raise SystemExit(0)
try:
    x=json.loads(p.read_text(encoding='utf-8'))
    risk=(x.get('after') or {}).get('risk') or []
    ok=bool(x.get('ok')) and not risk and (x.get('after') or {}).get('has4000') is True
    print('true' if ok else 'false')
except Exception:
    print('false')
PY
}

run_resume_once() {
  ensure_summary_from_runtime_evidence
  summary_rc=$?
  if [ "$summary_rc" != "0" ]; then
    write_state "blocked" "resume_summary_checkout_failed"
    publish_status
    return 2
  fi
  page_start="$(next_unfinished_page)"
  if [ "$page_start" = "0" ]; then
    log_msg "HZ23_ALREADY_COMPLETE round=$ROUND_ID"
    write_state "complete" "already_complete"
    publish_status
    return 0
  fi
  if [ "$page_start" = "-1" ]; then
    log_msg "HZ23_NEXT_PAGE_FAILED round=$ROUND_ID"
    write_state "blocked" "next_page_failed"
    publish_status
    return 2
  fi

  cleanup_legacy_backgrounds
  RUN_LOG="logs/hz23_${ROUND_ID}_formal_resume_$(date +%Y%m%d_%H%M%S).log"
  log_msg "HZ23_FORMAL_RUN_START round=$ROUND_ID page_start=$page_start page_end=$PAGE_END log=$RUN_LOG"
  write_state "running" "page_start=$page_start"
  publish_status

  HZ23_ROUND_ID="$ROUND_ID" \
  HZ23_RESUME=1 \
  HZ23_RESUME_SUMMARY="$RESUME_SUMMARY" \
  HZ23_ROUND_PAGE_START="$ROUND_PAGE_START" \
  HZ23_PAGE_START="$page_start" \
  HZ23_PAGE_END="$PAGE_END" \
  bash scripts/hz23_mainline_refresh.sh > "$RUN_LOG" 2>&1 &
  RUN_PID=$!

  HZ23_ROUND_ID="$ROUND_ID" \
  HZ23_PROGRESS_RUN_LOG="$RUN_LOG" \
  HZ23_PROGRESS_TARGET_PID="$RUN_PID" \
  HZ23_PROGRESS_PUBLISH_INTERVAL_SECONDS="$PROGRESS_PUBLISH_INTERVAL_SECONDS" \
  bash scripts/ops/hz23_formal_progress_publisher.sh >/dev/null 2>&1 &
  PROGRESS_PID=$!

  wait "$RUN_PID"
  rc=$?
  kill -TERM "$PROGRESS_PID" 2>/dev/null || true
  wait "$PROGRESS_PID" 2>/dev/null || true

  read -r outcome stop_page stop_reason <<< "$(classify_run_outcome)"
  log_msg "HZ23_FORMAL_RUN_DONE round=$ROUND_ID rc=$rc outcome=$outcome stop_page=$stop_page stop_reason=$stop_reason"
  write_resume_auto_report "$rc" "$RUN_LOG" "$outcome" "$stop_page" "$stop_reason"
  write_state "$outcome" "stop_page=$stop_page stop_reason=$stop_reason rc=$rc"
  publish_run_result
  return "$rc"
}

trap 'log_msg "HZ23_FORMAL_SUPERVISOR_STOP signal"; rm -f "$PID_FILE"; exit 0' INT TERM

cleanup_legacy_backgrounds
write_state "starting" "round=$ROUND_ID"
publish_status
log_msg "HZ23_FORMAL_SUPERVISOR_START pid=$$ round=$ROUND_ID page_end=$PAGE_END day_window=$DAY_START-$DAY_END progress_interval=$PROGRESS_PUBLISH_INTERVAL_SECONDS"

RUN_COUNT=0
while true; do
  ensure_summary_from_runtime_evidence
  if [ "$?" != "0" ]; then
    write_state "blocked" "resume_summary_checkout_failed"
    publish_status
    safe_sleep "$IDLE_INTERVAL_SECONDS"
    continue
  fi

  next_page="$(next_unfinished_page)"
  if [ "$next_page" = "0" ]; then
    write_state "complete" "unfinished_pages_empty"
    publish_status
    log_msg "HZ23_FORMAL_SUPERVISOR_COMPLETE round=$ROUND_ID"
    rm -f "$PID_FILE"
    exit 0
  fi

  if [ "$(inside_daytime)" = "true" ]; then
    probe_ok="$(probe_manual_verified "$next_page")"
    if [ "$probe_ok" = "true" ]; then
      RUN_COUNT=$((RUN_COUNT + 1))
      run_resume_once
      if [ "$MAX_RUNS" != "0" ] && [ "$RUN_COUNT" -ge "$MAX_RUNS" ]; then
        write_state "stopped" "max_runs_reached=$MAX_RUNS"
        publish_status
        rm -f "$PID_FILE"
        exit 0
      fi
      safe_sleep "$IDLE_INTERVAL_SECONDS"
    else
      log_msg "HZ23_WAITING_MANUAL_VERIFICATION page=$next_page next_probe_seconds=$DAY_PROBE_INTERVAL_SECONDS"
      write_state "paused_for_manual_verification" "next_page=$next_page probe=failed"
      publish_status
      safe_sleep "$DAY_PROBE_INTERVAL_SECONDS"
    fi
  else
    log_msg "HZ23_NIGHT_HEARTBEAT no_jd_probe next_page=$next_page next_check_seconds=$NIGHT_HEARTBEAT_INTERVAL_SECONDS"
    write_state "night_wait" "next_page=$next_page no_jd_probe=true"
    publish_status
    safe_sleep "$NIGHT_HEARTBEAT_INTERVAL_SECONDS"
  fi
done
