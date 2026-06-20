#!/usr/bin/env bash
# Run the Singapore offline CI bridge from the Hangzhou Data Lab login shell.
# This script does not run validation or production data operations in Hangzhou.
# No set -e is used.

ACTION="${1:-validate-publish}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$PROJECT_DIR/config/ci-bridge.env"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "STATUS=FAIL"
  echo "REASON=ci_bridge_config_missing"
  exit 1
fi
. "$CONFIG_FILE"

if [ "$(id -un)" != "$CI_BRIDGE_CONTROL_USER" ]; then
  echo "STATUS=FAIL"
  echo "REASON=unexpected_control_user"
  echo "CURRENT_USER=$(id -un)"
  echo "EXPECTED_USER=$CI_BRIDGE_CONTROL_USER"
  exit 1
fi

case "$ACTION" in
  validate|validate-publish)
    ;;
  *)
    echo "STATUS=FAIL"
    echo "REASON=unsupported_action"
    echo "SUPPORTED_ACTIONS=validate validate-publish"
    exit 2
    ;;
esac

REMOTE_TARGET="${CI_BRIDGE_USER}@${CI_BRIDGE_HOST}"
REMOTE_COMMAND="cd '$CI_BRIDGE_PROJECT_DIR'; git fetch origin main; FETCH_RC=\$?; if [ \"\$FETCH_RC\" != \"0\" ]; then exit \"\$FETCH_RC\"; fi; git checkout main; CHECKOUT_RC=\$?; if [ \"\$CHECKOUT_RC\" != \"0\" ]; then exit \"\$CHECKOUT_RC\"; fi; git reset --hard origin/main; RESET_RC=\$?; if [ \"\$RESET_RC\" != \"0\" ]; then exit \"\$RESET_RC\"; fi; bash scripts/ops/run_data_lab_ci_bridge.sh '$ACTION'"

ssh \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout="$CI_BRIDGE_SSH_CONNECT_TIMEOUT" \
  "$REMOTE_TARGET" \
  "$REMOTE_COMMAND"
REMOTE_RC=$?

echo "===== CI BRIDGE CONTROL SUMMARY ====="
echo "ACTION=$ACTION"
echo "REMOTE_TARGET=$REMOTE_TARGET"
echo "REMOTE_RC=$REMOTE_RC"
if [ "$REMOTE_RC" = "0" ]; then
  echo "STATUS=PASS"
else
  echo "STATUS=FAIL"
fi
exit "$REMOTE_RC"
