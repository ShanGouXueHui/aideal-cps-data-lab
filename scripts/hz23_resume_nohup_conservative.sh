#!/usr/bin/env bash
# Resume the current HZ23 checkpoint with a more conservative interaction cadence.
# The normal nohup PID and duplicate-run protection remain in effect. No set -e.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1

export HZ23_ITEM_SLEEP_MIN="${HZ23_ITEM_SLEEP_MIN:-4}"
export HZ23_ITEM_SLEEP_MAX="${HZ23_ITEM_SLEEP_MAX:-8}"
export HZ23_PAGE_SLEEP_MIN="${HZ23_PAGE_SLEEP_MIN:-180}"
export HZ23_PAGE_SLEEP_MAX="${HZ23_PAGE_SLEEP_MAX:-300}"
export HZ23_LIMIT="${HZ23_LIMIT:-25}"

bash scripts/hz23_resume_nohup_start.sh
