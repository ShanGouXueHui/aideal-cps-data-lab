#!/usr/bin/env bash
# Build the existing V2 status locally, then publish the report from an isolated worktree.
# The production worktree may contain runtime changes. No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs reports

bash scripts/hz23_publish_commercial_status_v2.sh \
  > logs/hz23_status_v2_build.log 2>&1
BUILD_AND_LEGACY_PUBLISH_RC=$?

REPORT="reports/hz23_commercial_status_v2_latest.json"
if [ ! -f "$REPORT" ]; then
  echo "STATUS_BUILD_RC=$BUILD_AND_LEGACY_PUBLISH_RC"
  echo "DIRTY_SAFE_PUBLISH_ERROR=status_report_missing"
  exit 1
fi

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish HZ23 commercial status" \
  "$REPORT" \
  > logs/hz23_status_dirty_safe_publish.log 2>&1
PUBLISH_RC=$?

echo "STATUS_BUILD_RC=$BUILD_AND_LEGACY_PUBLISH_RC"
echo "DIRTY_SAFE_PUBLISH_RC=$PUBLISH_RC"
exit "$PUBLISH_RC"
