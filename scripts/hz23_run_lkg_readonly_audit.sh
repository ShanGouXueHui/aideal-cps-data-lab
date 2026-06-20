#!/usr/bin/env bash
# Read-only HZ23 last-known-good evidence audit. No JD, MySQL, restore, or finalize.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "${SCRIPT_DIR}/lib/project_paths.sh"
PROJECT_DIR="$(aideal_project_dir)"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=project_directory"
  exit 1
fi

mkdir -p logs reports

PYTHONPATH=src python3 -m py_compile \
  src/aideal_cps_data_lab/hz23/lkg_settings.py \
  src/aideal_cps_data_lab/hz23/lkg_candidate_audit.py \
  src/aideal_cps_data_lab/hz23/lkg_runtime_audit.py \
  scripts/hz23_readonly_lkg_audit.py \
  > logs/hz23_lkg_readonly_compile.log 2>&1
COMPILE_RC=$?

if [ "$COMPILE_RC" = "0" ]; then
  PYTHONPATH=src python3 -m unittest tests.test_hz23_lkg_readonly_audit \
    > logs/hz23_lkg_readonly_test.log 2>&1
  TEST_RC=$?
else
  TEST_RC=99
fi

if [ "$COMPILE_RC" = "0" ] && [ "$TEST_RC" = "0" ]; then
  PYTHONPATH=src python3 scripts/hz23_readonly_lkg_audit.py \
    > logs/hz23_lkg_readonly_audit.log 2>&1
  AUDIT_RC=$?
else
  AUDIT_RC=99
fi

PUBLISH_RC=99
if [ "$AUDIT_RC" = "0" ] && [ -f reports/hz23_lkg_readonly_audit_latest.json ]; then
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ23 last-known-good readonly audit" \
    reports/hz23_lkg_readonly_audit_latest.json \
    > logs/hz23_lkg_readonly_publish.log 2>&1
  PUBLISH_RC=$?
fi

read -r AUDIT_STATUS CANDIDATE_COUNT EXACT_COUNT <<< "$(python3 - <<'PY'
import json
from pathlib import Path
path = Path('reports/hz23_lkg_readonly_audit_latest.json')
data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
print(
    data.get('status') or 'REPORT_MISSING',
    int(data.get('candidate_count') or 0),
    int(data.get('exact_match_count') or 0),
)
PY
)"

STATUS=PASS
if [ "$COMPILE_RC" != "0" ] || [ "$TEST_RC" != "0" ] || [ "$AUDIT_RC" != "0" ] || [ "$PUBLISH_RC" != "0" ]; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "COMPILE_RC=$COMPILE_RC"
echo "TEST_RC=$TEST_RC"
echo "AUDIT_RC=$AUDIT_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "AUDIT_STATUS=$AUDIT_STATUS"
echo "CANDIDATE_COUNT=$CANDIDATE_COUNT"
echo "EXACT_MATCH_COUNT=$EXACT_COUNT"
echo "REPORT=reports/hz23_lkg_readonly_audit_latest.json"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = PASS ]
