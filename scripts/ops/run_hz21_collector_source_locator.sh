#!/usr/bin/env bash
# Locate old HZ21 collector sources on production disk and publish redacted metadata.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1

git fetch origin main >/dev/null 2>&1 || true
git reset --hard origin/main >/dev/null 2>&1 || true

python3 scripts/ops/locate_hz21_collector_sources.py
LOCATE_RC=$?

PUBLISH_RC=99
if [ -f reports/hz21_collector_source_locator_latest.json ]; then
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ21 collector source locator" \
    reports/hz21_collector_source_locator_latest.json
  PUBLISH_RC=$?
fi

echo "===== SUMMARY ====="
echo "LOCATE_RC=$LOCATE_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "REPORT=reports/hz21_collector_source_locator_latest.json"
exit 0
