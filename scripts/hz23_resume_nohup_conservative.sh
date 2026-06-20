#!/usr/bin/env bash
# Resume the current HZ23 checkpoint with a more conservative interaction cadence.
# The normal nohup PID and duplicate-run protection remain in effect. No set -e.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
. config/hz23-service.env

export HZ23_ITEM_SLEEP_MIN="$HZ23_CONSERVATIVE_ITEM_SLEEP_MIN"
export HZ23_ITEM_SLEEP_MAX="$HZ23_CONSERVATIVE_ITEM_SLEEP_MAX"
export HZ23_PAGE_SLEEP_MIN="$HZ23_CONSERVATIVE_PAGE_SLEEP_MIN"
export HZ23_PAGE_SLEEP_MAX="$HZ23_CONSERVATIVE_PAGE_SLEEP_MAX"
export HZ23_LIMIT="$HZ23_CONSERVATIVE_LIMIT"

bash scripts/hz23_resume_nohup_start.sh
