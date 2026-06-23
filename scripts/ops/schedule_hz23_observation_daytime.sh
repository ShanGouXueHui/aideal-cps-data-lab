#!/usr/bin/env bash
# Schedule one HZ23 1-67 observation run for the next daytime window and publish JSON evidence.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"

SCHEDULER_LOG="logs/hz23_observation_daytime_scheduler.log"
PID_FILE="run/hz23_observation_daytime_scheduler.pid"
REPORT="reports/hz23_observation_auto_latest.json"
PAGE_START="${HZ23_PAGE_START:-1}"
PAGE_END="${HZ23_PAGE_END:-67}"

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "===== SUMMARY ====="
    echo "SCHEDULE_RC=75"
    echo "REASON=already_scheduled"
    echo "PID=$OLD_PID"
    echo "REPORT=$REPORT"
    exit 0
  fi
fi

# Cancel any old smoke scheduler to avoid concurrent browser use.
if [ -f run/hz23_smoke_daytime_scheduler.pid ]; then
  SMOKE_PID="$(cat run/hz23_smoke_daytime_scheduler.pid 2>/dev/null || true)"
  if [ -n "$SMOKE_PID" ] && kill -0 "$SMOKE_PID" 2>/dev/null; then
    kill "$SMOKE_PID" 2>/dev/null || true
  fi
  rm -f run/hz23_smoke_daytime_scheduler.pid
fi

python3 - <<'PY' > run/hz23_observation_delay.env
from datetime import datetime, timedelta
now = datetime.now()
start = now.replace(hour=9, minute=35, second=0, microsecond=0)
end = now.replace(hour=21, minute=0, second=0, microsecond=0)
if now < start:
    target = start
elif now <= end:
    target = now + timedelta(minutes=1)
else:
    target = start + timedelta(days=1)
seconds = max(0, int((target - now).total_seconds()))
print(f"DELAY_SECONDS={seconds}")
print(f"TARGET_TIME={target.strftime('%Y-%m-%dT%H:%M:%S')}")
PY
. run/hz23_observation_delay.env

(
  echo "SCHEDULED_AT=$(date '+%Y-%m-%dT%H:%M:%S') TARGET_TIME=$TARGET_TIME DELAY_SECONDS=$DELAY_SECONDS PAGE_START=$PAGE_START PAGE_END=$PAGE_END"
  sleep "$DELAY_SECONDS"
  cd "$PROJECT_DIR" || exit 1
  export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"
  git fetch origin main >/dev/null 2>&1 || true
  git reset --hard origin/main >/dev/null 2>&1 || true
  git clean -fd reports docs/ops >/dev/null 2>&1 || true

  .venv-browser/bin/python - <<'PY' >/dev/null 2>&1
import tomli
PY
  TOMLI_RC=$?
  if [ "$TOMLI_RC" != "0" ]; then
    .venv-browser/bin/python -m pip install 'tomli>=2.0.1,<3' > logs/hz23_observation_deps_install.log 2>&1 || true
  fi

  ROUND_ID="hz23_obs_$(date +%Y%m%d_%H%M%S)"
  RUN_LOG="logs/hz23_${ROUND_ID}.log"
  echo "RUN_START=$(date '+%Y-%m-%dT%H:%M:%S') ROUND_ID=$ROUND_ID PAGE_START=$PAGE_START PAGE_END=$PAGE_END" | tee -a "$SCHEDULER_LOG"
  HZ23_ROUND_ID="$ROUND_ID" HZ23_PAGE_START="$PAGE_START" HZ23_PAGE_END="$PAGE_END" HZ23_RESUME=0 bash scripts/hz23_mainline_refresh.sh > "$RUN_LOG" 2>&1
  RUN_RC=$?
  python3 - "$ROUND_ID" "$RUN_RC" "$RUN_LOG" "$REPORT" <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path
round_id=sys.argv[1]
run_rc=int(sys.argv[2])
log_path=Path(sys.argv[3])
report_path=Path(sys.argv[4])
summary_path=Path(f"reports/hz23_round_{round_id}_latest.json")
summary={}
if summary_path.exists():
    try:
        summary=json.loads(summary_path.read_text(encoding='utf-8'))
    except Exception as exc:
        summary={"summary_parse_error": repr(exc)}
log_tail=[]
if log_path.exists():
    lines=log_path.read_text(encoding='utf-8', errors='replace').splitlines()
    log_tail=lines[-220:]
payload={
    "schema_version":"hz23-observation-auto/v1",
    "generated_at":datetime.utcnow().isoformat(timespec='seconds')+'Z',
    "round_id":round_id,
    "run_rc":run_rc,
    "summary_path":str(summary_path),
    "log_path":str(log_path),
    "summary":summary,
    "log_tail":log_tail,
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
print(json.dumps({"event":"HZ23_OBSERVATION_AUTO_REPORT", "round_id":round_id, "run_rc":run_rc, "report":str(report_path)}, ensure_ascii=False, sort_keys=True))
PY
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ23 observation auto result" \
    "$REPORT" \
    "reports/hz23_round_${ROUND_ID}_latest.json" \
    reports/hz23_round_latest.json \
    > logs/hz23_observation_auto_publish.log 2>&1
  PUBLISH_RC=$?
  echo "RUN_DONE=$(date '+%Y-%m-%dT%H:%M:%S') ROUND_ID=$ROUND_ID RUN_RC=$RUN_RC PUBLISH_RC=$PUBLISH_RC REPORT=$REPORT" | tee -a "$SCHEDULER_LOG"
  rm -f "$PID_FILE"
) >> "$SCHEDULER_LOG" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"

python3 - "$REPORT" "$PID" "$TARGET_TIME" "$DELAY_SECONDS" "$PAGE_START" "$PAGE_END" <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path
report=Path(sys.argv[1])
payload={
    "schema_version":"hz23-observation-auto/v1",
    "generated_at":datetime.utcnow().isoformat(timespec='seconds')+'Z',
    "status":"SCHEDULED",
    "pid":int(sys.argv[2]),
    "target_time":sys.argv[3],
    "delay_seconds":int(sys.argv[4]),
    "page_start":int(sys.argv[5]),
    "page_end":int(sys.argv[6]),
}
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
PY
bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish HZ23 observation auto schedule" \
  "$REPORT" \
  >/dev/null 2>&1
PUBLISH_RC=$?

echo "===== SUMMARY ====="
echo "SCHEDULE_RC=0"
echo "PID=$PID"
echo "TARGET_TIME=$TARGET_TIME"
echo "DELAY_SECONDS=$DELAY_SECONDS"
echo "PAGE_START=$PAGE_START"
echo "PAGE_END=$PAGE_END"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "REPORT=$REPORT"
