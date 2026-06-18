#!/usr/bin/env bash
cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs run
PID_FILE=run/hz24_increment_nohup.pid
STATE_FILE=run/hz24_increment_nohup.state
PID="$$"
STARTED="$(date --iso-8601=seconds)"
printf '%s\n' "$PID" > "$PID_FILE"
printf 'STATE=running\nRUNNER_PID=%s\nSTARTED_AT=%s\n' "$PID" "$STARTED" > "$STATE_FILE"

bash scripts/hz24_increment_loop.sh >> logs/hz24_increment_nohup.log 2>&1
RC=$?
FINISHED="$(date --iso-8601=seconds)"
STATE=failed
[ "$RC" = "0" ] && STATE=completed
[ "$RC" = "88" ] && STATE=paused
printf 'STATE=%s\nRUNNER_PID=%s\nSTARTED_AT=%s\nFINISHED_AT=%s\nRUN_RC=%s\n' \
  "$STATE" "$PID" "$STARTED" "$FINISHED" "$RC" > "$STATE_FILE"
[ "$(cat "$PID_FILE" 2>/dev/null)" = "$PID" ] && rm -f "$PID_FILE"
exit "$RC"
