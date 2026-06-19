#!/usr/bin/env bash
# Repository-wide static engineering audit. No JD or MySQL access. No set -e.

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
  scripts/engineering_scan.py \
  src/aideal_cps_data_lab/engineering_audit/models.py \
  src/aideal_cps_data_lab/engineering_audit/limits.py \
  src/aideal_cps_data_lab/engineering_audit/common.py \
  src/aideal_cps_data_lab/engineering_audit/python_scan.py \
  src/aideal_cps_data_lab/engineering_audit/shell_scan.py \
  src/aideal_cps_data_lab/engineering_audit/service.py \
  > logs/project_engineering_audit_compile.log 2>&1
COMPILE_RC=$?

if [ "$COMPILE_RC" = "0" ]; then
  PYTHONPATH=src python3 scripts/engineering_scan.py \
    > logs/project_engineering_audit_run.log 2>&1
  AUDIT_RC=$?
else
  AUDIT_RC=99
fi

PUBLISH_RC=99
if [ -f reports/project_engineering_audit_latest.json ]; then
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish repository engineering audit" \
    reports/project_engineering_audit_latest.json \
    > logs/project_engineering_audit_publish.log 2>&1
  PUBLISH_RC=$?
fi

read -r AUDIT_STATUS FILES BLOCKERS WARNINGS DUPLICATES HARDCODE LARGE LONG_FUNCTIONS <<< "$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/project_engineering_audit_latest.json')
x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
counts={}
for item in x.get('findings') or []:
    key=str(item.get('category') or '')
    counts[key]=counts.get(key,0)+1
print(
 x.get('status') or 'MISSING',
 int(x.get('files_scanned') or 0),
 int(x.get('blocker_count') or 0),
 int(x.get('warning_count') or 0),
 counts.get('duplicate_definition',0)+counts.get('duplicate_implementation',0),
 sum(value for key,value in counts.items() if key.startswith('hardcoded_')),
 counts.get('large_file',0),
 counts.get('long_function',0),
)
PY
)"

STATUS=PASS
if [ "$COMPILE_RC" != "0" ] || [ "$AUDIT_RC" = "99" ] || [ "$PUBLISH_RC" != "0" ]; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "COMPILE_RC=$COMPILE_RC"
echo "AUDIT_RC=$AUDIT_RC"
echo "AUDIT_STATUS=$AUDIT_STATUS"
echo "FILES_SCANNED=$FILES"
echo "BLOCKER_COUNT=$BLOCKERS"
echo "WARNING_COUNT=$WARNINGS"
echo "DUPLICATE_FINDING_COUNT=$DUPLICATES"
echo "HARDCODE_FINDING_COUNT=$HARDCODE"
echo "LARGE_FILE_COUNT=$LARGE"
echo "LONG_FUNCTION_COUNT=$LONG_FUNCTIONS"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "REPORT=reports/project_engineering_audit_latest.json"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = PASS ]
