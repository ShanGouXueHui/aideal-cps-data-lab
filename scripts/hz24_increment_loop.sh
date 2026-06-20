#!/usr/bin/env bash
# Loop safe HZ24 v2 batches after resume authorization. No set -e.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "${SCRIPT_DIR}/lib/project_paths.sh"
PROJECT_DIR="$(aideal_project_dir)"
if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=project_directory"
  exit 1
fi
mkdir -p logs reports run

read -r OBSERVER_SERVICE SAFE_START SAFE_END SLEEP_MIN SLEEP_MAX <<< "$(python3 - <<'PY'
import tomllib
from pathlib import Path
with Path('config/hz24-contracts.toml').open('rb') as stream:
    service = tomllib.load(stream)['observer_service']
with Path('config/hz24-loop.toml').open('rb') as stream:
    loop = tomllib.load(stream)
print(service, loop['safe_start_minute'], loop['safe_end_minute'], loop['batch_sleep_min_seconds'], loop['batch_sleep_max_seconds'])
PY
)"

exec 9>run/hz24_increment_loop.lock
if ! flock -n 9; then
  echo "===== SUMMARY ====="
  echo "STATUS=ALREADY_RUNNING"
  exit 75
fi

BATCH_NO=0
FINAL_RC=0
while true; do
  SAFE_WINDOW="$(SAFE_START="$SAFE_START" SAFE_END="$SAFE_END" python3 - <<'PY'
import os
from datetime import datetime
now = datetime.now()
minute = now.hour * 60 + now.minute
start = int(os.environ['SAFE_START'])
end = int(os.environ['SAFE_END'])
print('true' if start <= minute < end else 'false')
PY
)"
  if [ "$SAFE_WINDOW" != "true" ]; then
    FINAL_RC=88
    break
  fi

  BATCH_NO=$((BATCH_NO + 1))
  bash scripts/hz24_run_one_increment_batch.sh \
    > "logs/hz24_increment_batch_${BATCH_NO}_summary.log" 2>&1
  BATCH_RC=$?

  FILES=(
    reports/hz24_increment_queue_build_latest.json
    reports/hz24_increment_collection_latest.json
    data/export/hz24_special_tab_increment_manifest.json
  )
  OPTIONAL_FILES=(
    reports/hz24_collection_authorization_latest.json
    reports/hz24_collection_guard_latest.json
    reports/hz24_increment_validation_latest.json
    data/export/hz24_special_tab_links_manifest.json
    data/export/hz24_special_tab_outcomes_manifest.json
  )
  for path in "${OPTIONAL_FILES[@]}"; do
    if [ -f "$path" ]; then
      FILES+=("$path")
    fi
  done
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish guarded HZ24 increment batch ${BATCH_NO}" \
    "${FILES[@]}" \
    > "logs/hz24_increment_publish_${BATCH_NO}.log" 2>&1
  PUBLISH_RC=$?

  read -r COMPLETE SUCCESS UNAVAILABLE PENDING REASON <<< "$(python3 - <<'PY'
import json
from pathlib import Path
path = Path('reports/hz24_increment_collection_latest.json')
data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
print(
    'true' if data.get('complete') else 'false',
    int(data.get('success_count') or 0),
    int(data.get('unavailable_count') or 0),
    int(data.get('pending_count') or 0),
    data.get('stop_reason') or '-',
)
PY
)"

  echo "BATCH=$BATCH_NO RC=$BATCH_RC PUBLISH_RC=$PUBLISH_RC COMPLETE=$COMPLETE SUCCESS=$SUCCESS UNAVAILABLE=$UNAVAILABLE PENDING=$PENDING REASON=$REASON" \
    >> logs/hz24_increment_loop.log

  if [ "$PUBLISH_RC" != "0" ]; then FINAL_RC=1; break; fi
  if [ "$COMPLETE" = "true" ]; then FINAL_RC=0; break; fi
  if [ "$BATCH_RC" != "0" ]; then FINAL_RC="$BATCH_RC"; break; fi

  SLEEP_SECONDS="$(SLEEP_MIN="$SLEEP_MIN" SLEEP_MAX="$SLEEP_MAX" python3 - <<'PY'
import os
import random
print(random.randint(int(os.environ['SLEEP_MIN']), int(os.environ['SLEEP_MAX'])))
PY
)"
  echo "WAIT_SECONDS=$SLEEP_SECONDS" >> logs/hz24_increment_loop.log
  sleep "$SLEEP_SECONDS"
done

SERVICE_STATE="$(systemctl is-active "$OBSERVER_SERVICE" 2>/dev/null)"
SERVICE_PID="$(systemctl show "$OBSERVER_SERVICE" -p MainPID --value 2>/dev/null)"
STATUS=PASS
[ "$FINAL_RC" = "88" ] && STATUS=PAUSED
[ "$FINAL_RC" != "0" ] && [ "$FINAL_RC" != "88" ] && STATUS=FAIL

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "BATCH_COUNT=$BATCH_NO"
echo "FINAL_RC=$FINAL_RC"
echo "COMPLETE=${COMPLETE:-false}"
echo "SUCCESS_COUNT=${SUCCESS:-0}"
echo "UNAVAILABLE_COUNT=${UNAVAILABLE:-0}"
echo "PENDING_COUNT=${PENDING:-0}"
echo "STOP_REASON=${REASON:-outside_safe_window}"
echo "SERVICE_STATE=$SERVICE_STATE"
echo "SERVICE_PID=$SERVICE_PID"

exit "$FINAL_RC"
