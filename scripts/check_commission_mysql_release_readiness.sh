#!/usr/bin/env bash
# Offline only. No JD traffic, no MySQL connection, no service restart.
# No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs reports

PYTHONPATH=src python3 -m py_compile \
  scripts/backfill_commission_products_mysql.py \
  scripts/plan_commission_mysql_initialization.py \
  scripts/verify_commission_mysql_post_migration.py \
  src/aideal_cps_data_lab/persistence/mysql_batch_repository_v2.py \
  > logs/commission_mysql_release_compile.log 2>&1
COMPILE_RC=$?

PYTHONPATH=src python3 -m unittest discover \
  -s tests \
  -p 'test_*.py' \
  > reports/commission_mysql_release_unittest_latest.log 2>&1
TEST_RC=$?

PYTHONPATH=src python3 scripts/plan_commission_mysql_initialization.py \
  > logs/commission_mysql_initialization_plan.log 2>&1
PLAN_RC=$?

STATUS=PASS
if [ "$COMPILE_RC" != "0" ] || [ "$TEST_RC" != "0" ] || [ "$PLAN_RC" != "0" ]; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "COMPILE_RC=$COMPILE_RC"
echo "TEST_RC=$TEST_RC"
echo "PLAN_RC=$PLAN_RC"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

if [ "$STATUS" = "PASS" ]; then
  exit 0
fi

echo "===== COMPILE LOG ====="
tail -n 80 logs/commission_mysql_release_compile.log 2>/dev/null || true
echo "===== TEST LOG ====="
tail -n 120 reports/commission_mysql_release_unittest_latest.log 2>/dev/null || true
echo "===== PLAN LOG ====="
tail -n 80 logs/commission_mysql_initialization_plan.log 2>/dev/null || true
exit 1
