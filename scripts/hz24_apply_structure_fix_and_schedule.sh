#!/usr/bin/env bash
# Update to the latest HZ24 structure logic and schedule a read-only rerun.
# Returns immediately after scheduling. No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR"
CD_RC=$?
if [ "$CD_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=project_directory_missing"
  echo "CD_RC=$CD_RC"
  exit 1
fi
mkdir -p logs run reports

GIT_TERMINAL_PROMPT=0 git fetch origin main \
  > logs/hz24_fix_fetch.log 2>&1
FETCH_RC=$?

if [ "$FETCH_RC" = "0" ]; then
  bash <(git show origin/main:scripts/hz23_reconcile_runtime_git_state.sh) \
    > logs/hz24_fix_reconcile.log 2>&1
  RECONCILE_RC=$?
else
  RECONCILE_RC=99
fi

if [ "$FETCH_RC" = "0" ] && [ "$RECONCILE_RC" = "0" ]; then
  python3 -m py_compile \
    run/hz24_inspect_tab_pool_structure.py \
    scripts/hz24_analyze_tab_overlap.py \
    > logs/hz24_fix_compile.log 2>&1
  COMPILE_RC=$?
else
  COMPILE_RC=99
fi

if [ "$COMPILE_RC" = "0" ]; then
  bash scripts/hz24_schedule_tab_pool_analysis_next_daytime.sh \
    > logs/hz24_fix_schedule.log 2>&1
  SCHEDULE_RC=$?
else
  SCHEDULE_RC=99
fi

SCHEDULER_PID="$(cat run/hz24_tab_pool_schedule.pid 2>/dev/null || true)"
TARGET_AT="$(awk -F= '$1=="TARGET_AT"{print substr($0,index($0,"=")+1)}' run/hz24_tab_pool_schedule.state 2>/dev/null | tail -n 1)"
SCHEDULE_STATE="$(awk -F= '$1=="STATE"{print substr($0,index($0,"=")+1)}' run/hz24_tab_pool_schedule.state 2>/dev/null | tail -n 1)"

STATUS=PASS
if [ "$FETCH_RC" != "0" ] || [ "$RECONCILE_RC" != "0" ] || [ "$COMPILE_RC" != "0" ] || [ "$SCHEDULE_RC" != "0" ]; then
  STATUS=FAIL
fi
if [ "$STATUS" = "PASS" ] && { [ -z "$SCHEDULER_PID" ] || ! kill -0 "$SCHEDULER_PID" 2>/dev/null; }; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "FETCH_RC=$FETCH_RC"
echo "RECONCILE_RC=$RECONCILE_RC"
echo "COMPILE_RC=$COMPILE_RC"
echo "SCHEDULE_RC=$SCHEDULE_RC"
echo "SCHEDULE_STATE=$SCHEDULE_STATE"
echo "SCHEDULER_PID=$SCHEDULER_PID"
echo "TARGET_AT=$TARGET_AT"
echo "LOG=logs/hz24_tab_pool_schedule.log"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = PASS ]
