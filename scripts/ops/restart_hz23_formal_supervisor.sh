#!/usr/bin/env bash
# Restart the formal HZ23 supervisor and load the latest production code.
# This is the short operational entrypoint to replace an already-running supervisor.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run

PID_FILE="run/hz23_formal_supervisor.pid"
ROUND_ID="${HZ23_ROUND_ID:-hz23_obs_20260624_093503}"
PAGE_END="${HZ23_PAGE_END:-67}"

if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    echo "===== STOP OLD FORMAL SUPERVISOR ====="
    echo "TERM $PID"
    kill -TERM "$PID" 2>/dev/null || true
    for c in $(pgrep -P "$PID" 2>/dev/null); do
      echo "TERM child $c parent=$PID"
      kill -TERM "$c" 2>/dev/null || true
    done
    sleep 3
    if kill -0 "$PID" 2>/dev/null; then
      echo "KILL $PID"
      kill -KILL "$PID" 2>/dev/null || true
    fi
    for c in $(pgrep -P "$PID" 2>/dev/null); do
      echo "KILL child $c parent=$PID"
      kill -KILL "$c" 2>/dev/null || true
    done
  fi
fi

rm -f run/hz23_formal_supervisor.pid run/hz23_formal_supervisor.lock 2>/dev/null || true

echo "===== START LATEST FORMAL SUPERVISOR ====="
HZ23_ROUND_ID="$ROUND_ID" HZ23_PAGE_END="$PAGE_END" bash scripts/ops/start_hz23_formal_supervisor.sh
