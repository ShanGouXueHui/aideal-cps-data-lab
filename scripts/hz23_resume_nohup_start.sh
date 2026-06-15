#!/usr/bin/env bash
# Start HZ23 resume in background and return immediately. No set -e.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs run

PID_FILE="run/hz23_resume_nohup.pid"
LAUNCH_LOG="logs/hz23_resume_nohup_launcher.log"

if [ -f "$PID_FILE" ]; then
  EXISTING_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" 2>/dev/null; then
    echo "===== SUMMARY ====="
    echo "STATUS=ALREADY_RUNNING"
    echo "RUNNER_PID=$EXISTING_PID"
    echo "LOG=logs/hz23_resume_nohup.log"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

bash -n scripts/hz23_resume_nohup_runner.sh scripts/hz23_resume_after_manual_verification.sh
SYNTAX_RC=$?
if [ "$SYNTAX_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=syntax_check"
  echo "SYNTAX_RC=$SYNTAX_RC"
  exit 1
fi

nohup bash scripts/hz23_resume_nohup_runner.sh \
  </dev/null >> "$LAUNCH_LOG" 2>&1 &
LAUNCH_PID=$!

sleep 2
RUNNER_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
STATUS=PASS
if [ -z "$RUNNER_PID" ] || ! kill -0 "$RUNNER_PID" 2>/dev/null; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "LAUNCH_PID=$LAUNCH_PID"
echo "RUNNER_PID=$RUNNER_PID"
echo "LOG=logs/hz23_resume_nohup.log"
echo "STATUS_COMMAND=bash scripts/hz23_resume_nohup_status.sh"

[ "$STATUS" = PASS ]
