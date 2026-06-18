#!/usr/bin/env bash
# Loop safe HZ24 batches; observer is restored between batches. No set -e.
cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs reports run

exec 9>run/hz24_increment_loop.lock
if ! flock -n 9; then
  echo "===== SUMMARY ====="
  echo "STATUS=ALREADY_RUNNING"
  exit 75
fi

BATCH_NO=0
FINAL_RC=0
while true; do
  SAFE_WINDOW="$(python3 - <<'PY'
from datetime import datetime
n=datetime.now(); m=n.hour*60+n.minute
print('true' if 570 <= m < 1230 else 'false')
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

  FILES=(reports/hz24_increment_queue_build_latest.json reports/hz24_increment_collection_latest.json data/export/hz24_special_tab_increment_manifest.json)
  [ -f reports/hz24_increment_validation_latest.json ] && FILES+=(reports/hz24_increment_validation_latest.json)
  [ -f data/export/hz24_special_tab_links_manifest.json ] && FILES+=(data/export/hz24_special_tab_links_manifest.json)
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ24 increment batch ${BATCH_NO}" \
    "${FILES[@]}" \
    > "logs/hz24_increment_publish_${BATCH_NO}.log" 2>&1
  PUBLISH_RC=$?

  read -r COMPLETE SUCCESS PENDING REASON <<< "$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/hz24_increment_collection_latest.json')
x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
print('true' if x.get('complete') else 'false',int(x.get('success_count') or 0),int(x.get('pending_count') or 0),x.get('stop_reason') or '-')
PY
)"

  echo "BATCH=$BATCH_NO RC=$BATCH_RC PUBLISH_RC=$PUBLISH_RC COMPLETE=$COMPLETE SUCCESS=$SUCCESS PENDING=$PENDING REASON=$REASON" \
    >> logs/hz24_increment_loop.log

  if [ "$PUBLISH_RC" != "0" ]; then FINAL_RC=1; break; fi
  if [ "$COMPLETE" = "true" ]; then FINAL_RC=0; break; fi
  if [ "$BATCH_RC" != "0" ]; then FINAL_RC="$BATCH_RC"; break; fi

  SLEEP_SECONDS="$(python3 - <<'PY'
import random
print(random.randint(900,1500))
PY
)"
  echo "WAIT_SECONDS=$SLEEP_SECONDS" >> logs/hz24_increment_loop.log
  sleep "$SLEEP_SECONDS"
done

SERVICE_STATE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"
SERVICE_PID="$(systemctl show aideal-hz23-observer.service -p MainPID --value 2>/dev/null || true)"
STATUS=PASS
[ "$FINAL_RC" = "88" ] && STATUS=PAUSED
[ "$FINAL_RC" != "0" ] && [ "$FINAL_RC" != "88" ] && STATUS=FAIL

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "BATCH_COUNT=$BATCH_NO"
echo "FINAL_RC=$FINAL_RC"
echo "COMPLETE=${COMPLETE:-false}"
echo "SUCCESS_COUNT=${SUCCESS:-0}"
echo "PENDING_COUNT=${PENDING:-0}"
echo "STOP_REASON=${REASON:-outside_safe_window}"
echo "SERVICE_STATE=$SERVICE_STATE"
echo "SERVICE_PID=$SERVICE_PID"

exit "$FINAL_RC"
