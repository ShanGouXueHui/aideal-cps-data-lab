#!/usr/bin/env bash
# Schedule the read-only HZ24 tab pool analysis for the next daytime window.
# Returns immediately. No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab"
CD_RC=$?
if [ "$CD_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=project_directory_missing"
  echo "CD_RC=$CD_RC"
  exit 1
fi
mkdir -p logs run

PID_FILE="run/hz24_tab_pool_schedule.pid"
STATE_FILE="run/hz24_tab_pool_schedule.state"
LOG_FILE="logs/hz24_tab_pool_schedule.log"

if [ -f "$PID_FILE" ]; then
  EXISTING_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" 2>/dev/null; then
    TARGET_AT="$(awk -F= '$1=="TARGET_AT"{print substr($0,index($0,"=")+1)}' "$STATE_FILE" 2>/dev/null | tail -n 1)"
    echo "===== SUMMARY ====="
    echo "STATUS=ALREADY_SCHEDULED"
    echo "SCHEDULER_PID=$EXISTING_PID"
    echo "TARGET_AT=$TARGET_AT"
    echo "LOG=$LOG_FILE"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

read -r DELAY_SECONDS TARGET_AT <<< "$(python3 - <<'PY'
from datetime import datetime, timedelta
now = datetime.now()
start = now.replace(hour=9, minute=35, second=0, microsecond=0)
end = now.replace(hour=20, minute=45, second=0, microsecond=0)
if start <= now < end:
    target = now + timedelta(seconds=5)
elif now < start:
    target = start
else:
    target = start + timedelta(days=1)
print(max(1, int((target - now).total_seconds())), target.isoformat(timespec='seconds'))
PY
)"

nohup bash -c '
  sleep "$1"
  cd "$2" || exit 1
  bash scripts/hz24_run_tab_pool_analysis.sh
  rc=$?
  {
    echo "STATE=finished"
    echo "TARGET_AT=$3"
    echo "FINISHED_AT=$(date --iso-8601=seconds)"
    echo "RUN_RC=$rc"
  } > run/hz24_tab_pool_schedule.state
  rm -f run/hz24_tab_pool_schedule.pid
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
