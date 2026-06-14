#!/usr/bin/env bash
# Offline only. No JD live traffic and no MySQL connection.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs reports

PYTHONPATH=src python3 -m py_compile \
  src/aideal_cps_data_lab/config.py \
  src/aideal_cps_data_lab/contracts/commission_payload.py \
  src/aideal_cps_data_lab/domain/commission_product.py \
  src/aideal_cps_data_lab/application/backfill.py \
  src/aideal_cps_data_lab/application/candidate_validation.py \
  src/aideal_cps_data_lab/persistence/repository.py \
  src/aideal_cps_data_lab/persistence/mysql_repository.py \
  src/aideal_cps_data_lab/persistence/mysql_batch_repository.py \
  src/aideal_cps_data_lab/persistence/mysql_batch_repository_v2.py \
  src/aideal_cps_data_lab/persistence/mysql_factory.py \
  run/hz23_finalize_round.py \
  scripts/validate_commercial_candidate.py \
  scripts/validate_commission_mysql_ddl.py \
  scripts/validate_commission_mysql_migrations.py \
  > logs/commission_data_compile_v2.log 2>&1
COMPILE_RC=$?

bash -n scripts/hz23_observation_daemon.sh scripts/hz23_mainline_refresh.sh \
  > logs/commission_data_shell_v2.log 2>&1
SHELL_RC=$?

PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' \
  > reports/commission_data_unittest_v2_latest.log 2>&1
TEST_RC=$?

python3 scripts/validate_commission_mysql_ddl.py \
  > reports/commission_data_ddl_v2_latest.json
DDL_RC=$?

python3 scripts/validate_commission_mysql_migrations.py \
  > reports/commission_data_migration_v2_latest.json
MIGRATION_RC=$?

python3 scripts/hz23_risk_policy_guard.py \
  > reports/commission_data_risk_v2_latest.json
RISK_RC=$?

CANDIDATE_RC=SKIP
if [ -f data/export/aideal_cps_products_commercial_candidate_latest.jsonl ] && [ -f data/export/aideal_cps_products_commercial_candidate_manifest.json ]; then
  PYTHONPATH=src python3 scripts/validate_commercial_candidate.py \
    > logs/commercial_candidate_validation.log 2>&1
  CANDIDATE_RC=$?
fi

STATUS=PASS
if [ "$COMPILE_RC" != 0 ] || [ "$SHELL_RC" != 0 ] || [ "$TEST_RC" != 0 ] || [ "$DDL_RC" != 0 ] || [ "$MIGRATION_RC" != 0 ] || [ "$RISK_RC" != 0 ]; then
  STATUS=FAIL
fi
if [ "$CANDIDATE_RC" != "SKIP" ] && [ "$CANDIDATE_RC" != "0" ]; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "COMPILE_RC=$COMPILE_RC"
echo "SHELL_RC=$SHELL_RC"
echo "TEST_RC=$TEST_RC"
echo "DDL_RC=$DDL_RC"
echo "MIGRATION_RC=$MIGRATION_RC"
echo "RISK_RC=$RISK_RC"
echo "CANDIDATE_RC=$CANDIDATE_RC"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = PASS ]
