#!/usr/bin/env bash
# Offline candidate revalidation after lineage-round semantics fix.
# No JD operation, MySQL access, or observer restart. No set -e.

cd "${HOME}/projects/aideal-cps-data-lab"
CD_RC=$?
if [ "$CD_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=project_directory_missing"
  exit 1
fi
mkdir -p logs reports

PYTHONPATH=src python3 -m py_compile \
  src/aideal_cps_data_lab/application/candidate_validation.py \
  scripts/hz23_refresh_manifest_gates.py \
  scripts/validate_commercial_candidate.py \
  > logs/hz23_candidate_revalidate_compile.log 2>&1
COMPILE_RC=$?

PYTHONPATH=src python3 -m unittest tests.test_candidate_validation \
  > logs/hz23_candidate_revalidate_test.log 2>&1
TEST_RC=$?

if [ "$COMPILE_RC" = "0" ] && [ "$TEST_RC" = "0" ]; then
  PYTHONPATH=src python3 scripts/hz23_refresh_manifest_gates.py \
    > logs/hz23_candidate_gate_refresh.log 2>&1
  REFRESH_RC=$?
else
  REFRESH_RC=99
fi

if [ "$REFRESH_RC" = "0" ]; then
  PYTHONPATH=src python3 scripts/validate_commercial_candidate.py \
    > logs/hz23_candidate_validation_final.log 2>&1
  VALIDATION_RC=$?
else
  VALIDATION_RC=99
fi

PUBLISH_RC=99
if [ -f reports/hz23_manifest_gate_refresh_latest.json ] && [ -f reports/commercial_candidate_validation_latest.json ]; then
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: revalidate HZ23 commercial candidate" \
    reports/hz23_manifest_gate_refresh_latest.json \
    reports/commercial_candidate_validation_latest.json \
    data/export/aideal_cps_products_commercial_candidate_manifest.json \
    > logs/hz23_candidate_revalidate_publish.log 2>&1
  PUBLISH_RC=$?
fi

read -r ROWS DUPLICATES INVALID HASH_MISMATCH INTEGRITY READY FAILURES ERRORS <<< "$(python3 - <<'PY'
import json
from pathlib import Path
v={}; m={}
vp=Path('reports/commercial_candidate_validation_latest.json')
mp=Path('data/export/aideal_cps_products_commercial_candidate_manifest.json')
if vp.exists():
    try: v=json.loads(vp.read_text(encoding='utf-8'))
    except Exception: pass
if mp.exists():
    try: m=json.loads(mp.read_text(encoding='utf-8'))
    except Exception: pass
print(
 int(v.get('row_count') or 0),
 int(v.get('duplicate_sku_count') or 0),
 int(v.get('invalid_row_count') or 0),
 int(v.get('payload_hash_mismatch_count') or 0),
 'true' if m.get('candidate_integrity_ready') else 'false',
 'true' if m.get('observation_ready') else 'false',
 ','.join(m.get('gate_failures') or []) or '-',
 ','.join(f'{k}:{n}' for k,n in sorted((v.get('errors') or {}).items())) or '-',
)
PY
)"

STATUS=PASS
if [ "$COMPILE_RC" != "0" ] || [ "$TEST_RC" != "0" ] || [ "$REFRESH_RC" != "0" ] || [ "$VALIDATION_RC" != "0" ] || [ "$PUBLISH_RC" != "0" ]; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "COMPILE_RC=$COMPILE_RC"
echo "TEST_RC=$TEST_RC"
echo "REFRESH_RC=$REFRESH_RC"
echo "VALIDATION_RC=$VALIDATION_RC"
echo "CANDIDATE_ROWS=$ROWS"
echo "DUPLICATE_SKU_COUNT=$DUPLICATES"
echo "INVALID_ROW_COUNT=$INVALID"
echo "PAYLOAD_HASH_MISMATCH_COUNT=$HASH_MISMATCH"
echo "CANDIDATE_INTEGRITY_READY=$INTEGRITY"
echo "OBSERVATION_READY=$READY"
echo "GATE_FAILURES=$FAILURES"
echo "VALIDATION_ERRORS=$ERRORS"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = PASS ]
