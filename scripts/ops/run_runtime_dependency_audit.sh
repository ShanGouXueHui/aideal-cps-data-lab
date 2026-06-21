#!/usr/bin/env bash
# Read-only runtime dependency audit and evidence publisher.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1

git fetch origin main >/dev/null 2>&1 || true
git reset --hard origin/main >/dev/null 2>&1 || true

python3 scripts/ops/audit_runtime_dependencies.py
AUDIT_RC=$?

PUBLISH_RC=99
if [ -f reports/runtime_dependency_audit_latest.json ]; then
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish runtime dependency audit" \
    reports/runtime_dependency_audit_latest.json
  PUBLISH_RC=$?
fi

echo "===== SUMMARY ====="
echo "AUDIT_RC=$AUDIT_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "REPORT=reports/runtime_dependency_audit_latest.json"
exit 0
