#!/usr/bin/env bash
# Check that retired HZ23 production entrypoints are absent and only formal entrypoints remain.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1

BAD=0
RETIREDS="
scripts/hz23_observation_daemon.sh
scripts/ops/schedule_hz23_observation_daytime.sh
scripts/ops/schedule_hz23_observation_resume_daytime.sh
scripts/ops/run_hz23_smoke_now.sh
scripts/ops/run_hz23_smoke_now_with_deps.sh
"
FORMALS="
scripts/ops/hz23_formal_supervisor.sh
scripts/ops/hz23_formal_progress_publisher.sh
scripts/ops/start_hz23_formal_supervisor.sh
scripts/ops/restart_hz23_formal_supervisor.sh
"

echo "===== RETIRED ENTRYPOINTS MUST BE ABSENT ====="
for p in $RETIREDS; do
  if [ -e "$p" ]; then
    echo "FAIL_PRESENT $p"
    BAD=1
  else
    echo "OK_ABSENT $p"
  fi
done

echo "===== FORMAL ENTRYPOINTS MUST EXIST ====="
for p in $FORMALS; do
  if [ -f "$p" ]; then
    echo "OK_PRESENT $p"
  else
    echo "FAIL_MISSING $p"
    BAD=1
  fi
done

echo "===== LIVE HZ23 PROCESSES ====="
ps -eo pid,ppid,stat,lstart,cmd | grep -E 'hz23_observation_daemon|schedule_hz23_observation|run_hz23_smoke_now|hz23_formal_supervisor|hz23_formal_progress_publisher|hz23_mainline_refresh|hz22_prepare|hz23_scan|sleep [0-9]+' | grep -v grep || true

echo "===== SUMMARY ====="
echo "CHECK_RC=$BAD"
exit "$BAD"
