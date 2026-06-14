#!/usr/bin/env bash
# Apply the collection/data-integrity update outside the JD operation window.
# Runs offline tests first, then safely reloads the observer. No JD page operations.
# No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs reports

bash scripts/run_commission_data_checks_v2.sh \
  > logs/hz23_data_integrity_checks.log 2>&1
CHECK_RC=$?

if [ "$CHECK_RC" = "0" ]; then
  bash scripts/hz23_safe_reload_observer.sh \
    > logs/hz23_data_integrity_reload.log 2>&1
  RELOAD_RC=$?
else
  RELOAD_RC=99
fi

STATUS=PASS
if [ "$CHECK_RC" != "0" ] || [ "$RELOAD_RC" != "0" ]; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "CHECK_RC=$CHECK_RC"
echo "RELOAD_RC=$RELOAD_RC"
echo "SERVICE_STATE=$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"
echo "SERVICE_PID=$(systemctl show aideal-hz23-observer.service -p MainPID --value 2>/dev/null || true)"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

if [ "$STATUS" != "PASS" ]; then
  echo "===== CHECK LOG TAIL ====="
  tail -n 80 logs/hz23_data_integrity_checks.log 2>/dev/null || true
  echo "===== RELOAD LOG TAIL ====="
  tail -n 80 logs/hz23_data_integrity_reload.log 2>/dev/null || true
  exit 1
fi
exit 0
