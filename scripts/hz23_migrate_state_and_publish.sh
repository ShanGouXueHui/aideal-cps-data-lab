#!/usr/bin/env bash
# State-only migration and status publication. Does not restart the service or touch JD.
# No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs reports backups

STAMP="$(date +%Y%m%d_%H%M%S)"
if [ -f run/hz23_observer_state.json ]; then
  cp -a run/hz23_observer_state.json "backups/hz23_observer_state.${STAMP}.json"
  BACKUP_RC=$?
else
  BACKUP_RC=2
fi

python3 scripts/hz23_migrate_observer_state_v2.py \
  > reports/hz23_state_migration_v2_latest.json \
  2> logs/hz23_state_migration_v2.log
MIGRATE_RC=$?

if [ "$MIGRATE_RC" = "0" ]; then
  bash scripts/hz23_publish_commercial_status_v2.sh
  PUBLISH_RC=$?
else
  PUBLISH_RC=99
fi

STATUS="PASS"
if [ "$BACKUP_RC" != "0" ] || [ "$MIGRATE_RC" != "0" ] || [ "$PUBLISH_RC" != "0" ]; then
  STATUS="FAIL"
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "BACKUP_RC=$BACKUP_RC"
echo "MIGRATE_RC=$MIGRATE_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = "PASS" ]
