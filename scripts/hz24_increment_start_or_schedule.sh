#!/usr/bin/env bash
cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs run
PID_FILE=run/hz24_increment_nohup.pid
STATE_FILE=run/hz24_increment_nohup.state
LOG_FILE=logs/hz24_increment_launcher.log

if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    echo "===== SUMMARY ====="
    echo "STATUS=ALREADY_RUNNING"
    echo "RUNNER_PID=$PID"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

read -r DELAY TARGET <<< "$(python3 - <<'PY'
from datetime import datetime,timedelta
now=datetime.now(); start=now.replace(hour=9,minute=35,second=0,microsecond=0); end=now.replace(hour=17,minute=30,second=0,microsecond=0)
if start <= now < end: target=now+timedelta(seconds=5)
elif now < start: target=start
else: target=start+timedelta(days=1)
print(max(1,int((target-now).total_seconds())),target.isoformat(timespec='seconds'))
PY
)"

nohup bash -c 'sleep "$1"; cd "$2" || exit 1; exec bash scripts/hz24_increment_nohup_runner.sh' \
  _ "$DELAY" "${HOME}/projects/aideal-cps-data-lab" </dev/null >> "$LOG_FILE" 2>&1 &
PID=$!
printf '%s\n' "$PID" > "$PID_FILE"
printf 'STATE=scheduled\nRUNNER_PID=%s\nCREATED_AT=%s\nTARGET_AT=%s\nDELAY_SECONDS=%s\n' \
  "$PID" "$(date --iso-8601=seconds)" "$TARGET" "$DELAY" > "$STATE_FILE"
sleep 1
STATUS=PASS
kill -0 "$PID" 2>/dev/null || STATUS=FAIL

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "RUNNER_PID=$PID"
echo "TARGET_AT=$TARGET"
echo "DELAY_SECONDS=$DELAY"
echo "LOG=logs/hz24_increment_nohup.log"
echo "STATUS_COMMAND=bash scripts/hz24_increment_status.sh"
[ "$STATUS" = PASS ]
