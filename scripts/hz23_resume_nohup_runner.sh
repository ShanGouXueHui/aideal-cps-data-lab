#!/usr/bin/env bash
# Background runner for HZ23 checkpoint resume. No set -e.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs run

PID_FILE="run/hz23_resume_nohup.pid"
STATE_FILE="run/hz23_resume_nohup.state"
LOG_FILE="logs/hz23_resume_nohup.log"

RUNNER_PID="$$"
STARTED_AT="$(date --iso-8601=seconds)"
printf '%s\n' "$RUNNER_PID" > "$PID_FILE"
{
  echo "STATE=running"
  echo "RUNNER_PID=$RUNNER_PID"
  echo "STARTED_AT=$STARTED_AT"
  echo "FINISHED_AT="
  echo "RESUME_RC="
} > "$STATE_FILE"

{
  echo "===== HZ23 NOHUP RESUME START ====="
  echo "STARTED_AT=$STARTED_AT"
  echo "RUNNER_PID=$RUNNER_PID"
  bash scripts/hz23_resume_after_manual_verification.sh
  RESUME_RC=$?
  echo "===== HZ23 NOHUP RESUME END ====="
  echo "FINISHED_AT=$(date --iso-8601=seconds)"
  echo "RESUME_RC=$RESUME_RC"
} >> "$LOG_FILE" 2>&1

FINISHED_AT="$(date --iso-8601=seconds)"
{
  if [ "$RESUME_RC" = "0" ]; then echo "STATE=completed"; else echo "STATE=failed"; fi
  echo "RUNNER_PID=$RUNNER_PID"
  echo "STARTED_AT=$STARTED_AT"
  echo "FINISHED_AT=$FINISHED_AT"
  echo "RESUME_RC=$RESUME_RC"
} > "$STATE_FILE"

if [ -f "$PID_FILE" ] && [ "$(cat "$PID_FILE" 2>/dev/null)" = "$RUNNER_PID" ]; then
  rm -f "$PID_FILE"
fi

exit "$RESUME_RC"
