#!/usr/bin/env bash
# Start the formal HZ23 supervisor as the only background controller.
# It cleans legacy HZ23 daemon/scheduler processes before launching.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run

ROUND_ID="${HZ23_ROUND_ID:-hz23_obs_20260624_093503}"
PAGE_END="${HZ23_PAGE_END:-67}"
PID_FILE="run/hz23_formal_supervisor.pid"
LOG="logs/hz23_formal_supervisor.nohup.log"

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "===== SUMMARY ====="
    echo "START_RC=75"
    echo "REASON=formal_supervisor_already_running"
    echo "PID=$OLD_PID"
    echo "ROUND_ID=$ROUND_ID"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

echo "===== CLEAN LEGACY HZ23 BACKGROUNDS ====="
ps -eo pid=,ppid=,cmd= | grep -E 'scripts/hz23_observation_daemon.sh|schedule_hz23_observation_daytime.sh|schedule_hz23_observation_resume_daytime.sh|run_hz23_smoke_now' | grep -v grep | while read -r pid ppid cmd; do
  [ -z "$pid" ] && continue
  echo "TERM $pid $cmd"
  kill -TERM "$pid" 2>/dev/null || true
  for c in $(pgrep -P "$pid" 2>/dev/null); do
    echo "TERM child $c parent=$pid"
    kill -TERM "$c" 2>/dev/null || true
  done
done
sleep 2
ps -eo pid=,ppid=,cmd= | grep -E 'scripts/hz23_observation_daemon.sh|schedule_hz23_observation_daytime.sh|schedule_hz23_observation_resume_daytime.sh|run_hz23_smoke_now' | grep -v grep | while read -r pid ppid cmd; do
  [ -z "$pid" ] && continue
  echo "KILL $pid $cmd"
  kill -KILL "$pid" 2>/dev/null || true
  for c in $(pgrep -P "$pid" 2>/dev/null); do
    echo "KILL child $c parent=$pid"
    kill -KILL "$c" 2>/dev/null || true
  done
done
rm -f run/hz23_observation_daytime_scheduler.pid run/hz23_observation_resume_daytime_scheduler.pid run/hz23_smoke_daytime_scheduler.pid 2>/dev/null || true

echo "===== START FORMAL SUPERVISOR ====="
nohup bash scripts/ops/hz23_formal_supervisor.sh > "$LOG" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"
sleep 2

ALIVE=false
if kill -0 "$PID" 2>/dev/null; then
  ALIVE=true
fi

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish HZ23 formal supervisor launch" \
  reports/hz23_formal_supervisor_status_latest.json \
  reports/hz23_formal_supervisor_latest.json \
  run/hz23_formal_supervisor_state.json \
  >/dev/null 2>&1 || true

PUBLISH_HEAD="$(git rev-parse --short origin/runtime-evidence 2>/dev/null || true)"

echo "===== SUMMARY ====="
echo "START_RC=0"
echo "PID=$PID"
echo "ALIVE=$ALIVE"
echo "ROUND_ID=$ROUND_ID"
echo "PAGE_END=$PAGE_END"
echo "PID_FILE=$PID_FILE"
echo "LOG=$LOG"
echo "RUNTIME_EVIDENCE_HEAD=$PUBLISH_HEAD"
echo "===== HZ23 PROCESSES ====="
ps -eo pid,ppid,stat,lstart,cmd | grep -E 'hz23_formal_supervisor|hz23_observation_daemon|schedule_hz23|sleep [0-9]+' | grep -v grep || true
