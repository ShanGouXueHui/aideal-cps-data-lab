#!/usr/bin/env bash
# Offline only: no JD live traffic and no MySQL connection.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports

PYTHONPATH=src python3 -m py_compile \
  src/aideal_cps_data_lab/config.py \
  src/aideal_cps_data_lab/domain/commission_product.py \
  src/aideal_cps_data_lab/application/backfill.py \
  src/aideal_cps_data_lab/persistence/repository.py \
  src/aideal_cps_data_lab/persistence/mysql_repository.py \
  src/aideal_cps_data_lab/persistence/mysql_factory.py \
  scripts/plan_commission_mysql_backfill.py \
  scripts/backfill_commission_products_mysql.py \
  scripts/validate_commission_mysql_ddl.py \
  scripts/validate_commission_mysql_migrations.py \
  > logs/commission_mysql_compile.log 2>&1
COMPILE_RC=$?

PYTHONPATH=src python3 -m unittest discover \
  -s tests \
  -p 'test_*.py' \
  > reports/commission_mysql_unittest_latest.log 2>&1
TEST_RC=$?

python3 scripts/validate_commission_mysql_ddl.py \
  > reports/commission_mysql_ddl_validation_latest.json
DDL_RC=$?

python3 scripts/validate_commission_mysql_migrations.py \
  > reports/commission_mysql_migration_validation_latest.json
MIGRATION_RC=$?

RISK_RC=0
python3 scripts/hz23_risk_policy_guard.py \
  > reports/hz23_risk_policy_guard_latest.json
RISK_RC=$?

STATUS="PASS"
if [ "$COMPILE_RC" != "0" ] || [ "$TEST_RC" != "0" ] || [ "$DDL_RC" != "0" ] || [ "$MIGRATION_RC" != "0" ] || [ "$RISK_RC" != "0" ]; then
  STATUS="FAIL"
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "COMPILE_RC=$COMPILE_RC"
echo "TEST_RC=$TEST_RC"
echo "DDL_RC=$DDL_RC"
echo "MIGRATION_RC=$MIGRATION_RC"
echo "RISK_RC=$RISK_RC"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
echo "REPORTS=reports/commission_mysql_*_latest.* reports/hz23_risk_policy_guard_latest.json"

if [ "$STATUS" = "PASS" ]; then
  exit 0
fi
exit 1
