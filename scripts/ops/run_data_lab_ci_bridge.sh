#!/usr/bin/env bash
# Thin Singapore Data Lab CI bridge entrypoint.
# Offline validation only. No JD live, collection, MySQL, publish version, or sync.
# No set -e is used.

ACTION="${1:-validate-publish}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$PROJECT_DIR/config/ci-bridge.env"
LOG_FILE="$PROJECT_DIR/logs/ci_bridge_bootstrap.log"

case "$ACTION" in
  validate|validate-publish) ;;
  *) echo "STATUS=FAIL"; echo "REASON=unsupported_action"; exit 2 ;;
esac

if [ ! -f "$CONFIG_FILE" ]; then
  echo "STATUS=FAIL"
  echo "REASON=ci_bridge_config_missing"
  exit 1
fi
. "$CONFIG_FILE"

if [ "$(id -un)" != "$CI_BRIDGE_EXECUTION_USER" ]; then
  echo "STATUS=FAIL"
  echo "REASON=unexpected_runtime_user"
  exit 1
fi

cd "$PROJECT_DIR"
CD_RC=$?
if [ "$CD_RC" != "0" ] || [ ! -d .git ]; then
  echo "STATUS=FAIL"
  echo "REASON=repository_unavailable"
  exit 1
fi

mkdir -p logs run reports
git fetch origin main >> "$LOG_FILE" 2>&1
FETCH_RC=$?
LOCAL_HEAD="$(git rev-parse HEAD)"
REMOTE_HEAD="$(git rev-parse origin/main 2>/dev/null)"
if [ "$FETCH_RC" != "0" ] || [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  echo "STATUS=FAIL"
  echo "REASON=checkout_not_current_main"
  exit 1
fi

PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  python3 -m venv "$PROJECT_DIR/.venv" >> "$LOG_FILE" 2>&1
  VENV_RC=$?
  if [ "$VENV_RC" != "0" ]; then
    echo "STATUS=FAIL"
    echo "REASON=venv_creation_failed"
    exit "$VENV_RC"
  fi
fi

"$PYTHON_BIN" -m pip install -e ".[browser,mysql]" >> "$LOG_FILE" 2>&1
INSTALL_RC=$?
if [ "$INSTALL_RC" != "0" ]; then
  echo "STATUS=FAIL"
  echo "REASON=dependency_install_failed"
  tail -n 80 "$LOG_FILE"
  exit "$INSTALL_RC"
fi

AIDEAL_OFFLINE_TEST=1 PYTHONPATH=src \
  "$PYTHON_BIN" scripts/ops/ci_bridge_runner.py \
  "$ACTION" --root "$PROJECT_DIR"
exit $?
