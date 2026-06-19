#!/usr/bin/env bash
# Repository-wide static engineering audit. No JD or MySQL access. No set -e.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT_DIR="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"

cd "$ROOT_DIR"
CD_RC=$?
if [ "$CD_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=repository_root_resolution"
  exit 1
fi

mkdir -p logs reports

PYTHONPATH=src python3 -m py_compile \
  scripts/engineering_scan_full.py \
  src/aideal_cps_data_lab/engineering_audit/*.py \
  > logs/project_engineering_audit_compile.log 2>&1
COMPILE_RC=$?

if [ "$COMPILE_RC" = "0" ]; then
  PYTHONPATH=src python3 scripts/engineering_scan_full.py \
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

path = Path("reports/project_engineering_audit_latest.json")
data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
counts = {}
for item in data.get("findings") or []:
    category = str(item.get("category") or "")
    counts[category] = counts.get(category, 0) + 1
print(
    data.get("status") or "MISSING",
    int(data.get("files_scanned") or 0),
    int(data.get("blocker_count") or 0),
    int(data.get("warning_count") or 0),
    counts.get("duplicate_definition", 0) + counts.get("duplicate_implementation", 0),
    sum(value for key, value in counts.items() if key.startswith("hardcoded_")),
    counts.get("large_file", 0),
    counts.get("long_function", 0),
)
PY
)"

STATUS=PASS
if [ "$COMPILE_RC" != "0" ] || [ "$AUDIT_RC" = "99" ] || [ "$PUBLISH_RC" != "0" ]; then
  STATUS=FAIL
fi

printf '%s\n' \
  "===== SUMMARY =====" \
  "STATUS=$STATUS" \
  "COMPILE_RC=$COMPILE_RC" \
  "AUDIT_RC=$AUDIT_RC" \
  "AUDIT_STATUS=$AUDIT_STATUS" \
  "FILES_SCANNED=$FILES" \
  "BLOCKER_COUNT=$BLOCKERS" \
  "WARNING_COUNT=$WARNINGS" \
  "DUPLICATE_FINDING_COUNT=$DUPLICATES" \
  "HARDCODE_FINDING_COUNT=$HARDCODE" \
  "LARGE_FILE_COUNT=$LARGE" \
  "LONG_FUNCTION_COUNT=$LONG_FUNCTIONS" \
  "PUBLISH_RC=$PUBLISH_RC" \
  "REPORT=reports/project_engineering_audit_latest.json" \
  "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = PASS ]