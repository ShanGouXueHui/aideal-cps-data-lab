#!/usr/bin/env bash
# Run report-authority recovery from the Hangzhou Data Lab login shell.
# Uses the verified sg-aideal-datalab SSH alias. No set -e is used.

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

REMOTE_ALIAS="sg-aideal-datalab"
REMOTE_COMMAND="cd '$CI_BRIDGE_PROJECT_DIR'; git fetch origin main; FETCH_RC=\$?; if [ \"\$FETCH_RC\" != \"0\" ]; then exit \"\$FETCH_RC\"; fi; git checkout main; CHECKOUT_RC=\$?; if [ \"\$CHECKOUT_RC\" != \"0\" ]; then exit \"\$CHECKOUT_RC\"; fi; git reset --hard origin/main; RESET_RC=\$?; if [ \"\$RESET_RC\" != \"0\" ]; then exit \"\$RESET_RC\"; fi; bash scripts/ops/recover_report_authority_on_sg.sh"

ssh \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout="$CI_BRIDGE_SSH_CONNECT_TIMEOUT" \
  "$REMOTE_ALIAS" \
  "$REMOTE_COMMAND"
REMOTE_RC=$?

echo "===== REPORT AUTHORITY CONTROL SUMMARY ====="
echo "REMOTE_ALIAS=$REMOTE_ALIAS"
echo "REMOTE_RC=$REMOTE_RC"
if [ "$REMOTE_RC" = "0" ]; then
  echo "STATUS=PASS"
else
  echo "STATUS=FAIL"
fi
exit "$REMOTE_RC"
