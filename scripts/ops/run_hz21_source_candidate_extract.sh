#!/usr/bin/env bash
# Extract redacted HZ21 source candidate snippets from local production backups.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1

git fetch origin main >/dev/null 2>&1 || true
git reset --hard origin/main >/dev/null 2>&1 || true

if [ ! -f reports/hz21_collector_source_locator_latest.json ]; then
  python3 scripts/ops/locate_hz21_collector_sources.py >/dev/null 2>&1 || true
fi

python3 scripts/ops/extract_hz21_source_candidate.py
EXTRACT_RC=$?

PUBLISH_RC=99
if [ -f reports/hz21_source_candidate_extract_latest.json ]; then
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ21 source candidate extract" \
    reports/hz21_source_candidate_extract_latest.json
  PUBLISH_RC=$?
fi

echo "===== SUMMARY ====="
echo "EXTRACT_RC=$EXTRACT_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "REPORT=reports/hz21_source_candidate_extract_latest.json"
exit 0
