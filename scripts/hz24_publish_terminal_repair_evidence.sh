#!/usr/bin/env bash
# Publish sanitized HZ24 repair reports only. No JSONL or secrets are included.
# No set -e is used.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="${AIDEAL_PROJECT_DIR:-$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)}"
if ! cd "$PROJECT_DIR"; then
  echo "STATUS=FAIL"
  echo "REASON=project_directory_unavailable"
  exit 1
fi

FILES=(
  reports/project_engineering_audit_latest.json
  reports/offline_quality_latest.json
  reports/hz24_sold_out_migration_latest.json
  reports/hz24_terminal_repair_latest.json
  reports/hz24_resume_gate_latest.json
)
if [ -f data/export/hz24_special_tab_outcomes_manifest.json ]; then
  FILES+=(data/export/hz24_special_tab_outcomes_manifest.json)
fi

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish HZ24 terminal repair evidence" \
  "${FILES[@]}"
PUBLISH_RC=$?

echo "===== SUMMARY ====="
if [ "$PUBLISH_RC" = "0" ]; then
  echo "STATUS=PASS"
else
  echo "STATUS=FAIL"
fi
echo "PUBLISH_RC=$PUBLISH_RC"
echo "JSONL_PUBLISHED=false"
echo "SECRETS_PUBLISHED=false"
exit "$PUBLISH_RC"
