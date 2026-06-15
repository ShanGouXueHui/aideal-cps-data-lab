#!/usr/bin/env bash
# Schedule conservative HZ23 checkpoint resume for the next daytime window.
# Returns immediately. No set -e.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs run

PID_FILE="run/hz23_resume_schedule.pid"
STATE_FILE="run/hz23_resume_schedule.state"
LOG_FILE="logs/hz23_resume_schedule.log"
RUNNER_PID_FILE="run/hz23_resume_nohup.pid"

if [ -f "$RUNNER_PID_FILE" ]; then
  RUNNER_PID="$(cat "$RUNNER_PID_FILE" 2>/dev/null || true)"
  if [ -n "$RUNNER_PID" ] && kill -0 "$RUNNER_PID" 2>/dev/null; then
    echo "===== SUMMARY ====="
    echo "STATUS=RUNNER_ALREADY_ACTIVE"
    echo "RUNNER_PID=$RUNNER_PID"
    exit 0
  fi
fi

if [ -f "$PID_FILE" ]; then
  EXISTING_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" 2>/dev/null; then
    TARGET_AT="$(awk -F= '$1=="TARGET_AT"{print substr($0,index($0,"=")+1)}' "$STATE_FILE" 2>/dev/null | tail -n 1)"
    echo "===== SUMMARY ====="
    echo "STATUS=ALREADY_SCHEDULED"
    echo "SCHEDULER_PID=$EXISTING_PID"
    echo "TARGET_AT=$TARGET_AT"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

read -r DELAY_SECONDS TARGET_AT <<< "$(python3 - <<'PY'
from datetime import datetime,timedelta
now=datetime.now()
start=now.replace(hour=9,minute=31,second=0,microsecond=0)
end=now.replace(hour=21,minute=0,second=0,microsecond=0)
if start <= now < end:
    target=now+timedelta(seconds=5)
elif now < start:
    target=start
else:
    target=start+timedelta(days=1)
print(max(1,int((target-now).total_seconds())),target.isoformat(timespec='seconds'))
PY
)"

nohup bash -c '
  sleep "$1"
  cd "$2" || exit 1
  bash scripts/hz23_resume_nohup_conservative.sh
  rc=$?
  {
    echo "STATE=finished"
    echo "TARGET_AT=$3"
    echo "FINISHED_AT=$(date --iso-8601=seconds)"
    echo "LAUNCH_RC=$rc"
  } > run/hz23_resume_schedule.state
  rm -f run/hz23_resume_schedule.pid
  exit "$rc"
' _ "$DELAY_SECONDS" "${HOME}/projects/aideal-cps-data-lab" "$TARGET_AT" \
  </dev/null >> "$LOG_FILE" 2>&1 &
SCHEDULER_PID=$!

printf '%s\n' "$SCHEDULER_PID" > "$PID_FILE"
{
  echo "STATE=scheduled"
  echo "SCHEDULER_PID=$SCHEDULER_PID"
  echo "CREATED_AT=$(date --iso-8601=seconds)"
  echo "TARGET_AT=$TARGET_AT"
  echo "DELAY_SECONDS=$DELAY_SECONDS"
} > "$STATE_FILE"

sleep 1
STATUS=PASS
if ! kill -0 "$SCHEDULER_PID" 2>/dev/null; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "SCHEDULER_PID=$SCHEDULER_PID"
echo "TARGET_AT=$TARGET_AT"
echo "DELAY_SECONDS=$DELAY_SECONDS"
echo "LOG=$LOG_FILE"

[ "$STATUS" = PASS ]
