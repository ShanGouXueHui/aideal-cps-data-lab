#!/usr/bin/env bash
# Read-only HZ21 runtime collector inspection.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1

git fetch origin main >/dev/null 2>&1 || true
git reset --hard origin/main >/dev/null 2>&1 || true

python3 scripts/ops/inspect_hz21_runtime.py
INSPECT_RC=$?

PUBLISH_RC=99
if [ "$INSPECT_RC" = "0" ] && [ -f reports/hz21_runtime_inspection_latest.json ]; then
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ21 runtime inspection" \
    reports/hz21_runtime_inspection_latest.json
  PUBLISH_RC=$?
fi

echo "===== SUMMARY ====="
echo "INSPECT_RC=$INSPECT_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "REPORT=reports/hz21_runtime_inspection_latest.json"
exit "$INSPECT_RC"
