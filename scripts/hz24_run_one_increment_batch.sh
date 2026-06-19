#!/usr/bin/env bash
# One HZ24 increment batch. No set -e.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1
mkdir -p logs reports run data/import data/export
export PYTHONPATH="$PROJECT_ROOT/src"

OBSERVER_SERVICE="$(python3 - <<'PY'
import tomllib
from pathlib import Path
with Path('config/hz24-contracts.toml').open('rb') as stream:
    print(tomllib.load(stream)['observer_service'])
PY
)"

python3 scripts/hz24_build_increment_queue.py > logs/hz24_queue.log 2>&1
QUEUE_RC=$?
if [ "$QUEUE_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=queue"
  echo "QUEUE_RC=$QUEUE_RC"
  exit 1
fi

OLD_STATE="$(systemctl is-active "$OBSERVER_SERVICE" 2>/dev/null || true)"
if [ "$OLD_STATE" = "active" ]; then
  sudo systemctl stop "$OBSERVER_SERVICE"
  STOP_RC=$?
else
  STOP_RC=0
fi
if [ "$STOP_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=observer_stop"
  echo "STOP_RC=$STOP_RC"
  exit 1
fi

.venv-browser/bin/python run/hz24_collect_increment_links.py > logs/hz24_batch.log 2>&1
COLLECT_RC=$?

if [ "$OLD_STATE" = "active" ]; then
  sudo systemctl start "$OBSERVER_SERVICE"
  START_RC=$?
else
  START_RC=0
fi
sleep 2
SERVICE_STATE="$(systemctl is-active "$OBSERVER_SERVICE" 2>/dev/null || true)"

read -r COMPLETE LINKED UNAVAILABLE PENDING REASON <<< "$(python3 - <<'PY'
import json
from pathlib import Path
path=Path('reports/hz24_increment_collection_latest.json')
x=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
print('true' if x.get('complete') else 'false',int(x.get('success_count') or 0),int(x.get('unavailable_count') or 0),int(x.get('pending_count') or 0),x.get('stop_reason') or '-')
PY
)"

if [ "$COMPLETE" = "true" ]; then
  python3 scripts/hz24_validate_increment_outcomes.py > logs/hz24_validate.log 2>&1
  VALIDATE_RC=$?
else
  VALIDATE_RC=SKIP
fi

STATUS=PASS
EXIT_RC="$COLLECT_RC"
if [ "$COLLECT_RC" != "0" ]; then STATUS=PAUSED; fi
if [ "$START_RC" != "0" ]; then STATUS=FAIL; EXIT_RC=1; fi
if [ "$OLD_STATE" = "active" ] && [ "$SERVICE_STATE" != "active" ]; then STATUS=FAIL; EXIT_RC=1; fi
if [ "$COMPLETE" = "true" ] && [ "$VALIDATE_RC" != "0" ]; then STATUS=FAIL; EXIT_RC=1; fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "QUEUE_RC=$QUEUE_RC"
echo "STOP_RC=$STOP_RC"
echo "COLLECT_RC=$COLLECT_RC"
echo "COMPLETE=$COMPLETE"
echo "LINKED_COUNT=$LINKED"
echo "UNAVAILABLE_COUNT=$UNAVAILABLE"
echo "PENDING_COUNT=$PENDING"
echo "STOP_REASON=$REASON"
echo "VALIDATE_RC=$VALIDATE_RC"
echo "START_RC=$START_RC"
echo "SERVICE_STATE=$SERVICE_STATE"

exit "$EXIT_RC"
