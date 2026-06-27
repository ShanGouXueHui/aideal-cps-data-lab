#!/usr/bin/env bash
# Deprecated legacy HZ23 observer.
#
# This script is intentionally fail-closed because the previous implementation
# could run browser probes/full refreshes on its own and publish runtime reports
# into main. Use scripts/ops/hz23_formal_supervisor.sh through
# scripts/ops/start_hz23_formal_supervisor.sh instead.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" 2>/dev/null || true
mkdir -p logs reports run 2>/dev/null || true

echo "$(date '+%F %T') HZ23_LEGACY_DAEMON_RETIRED use=scripts/ops/start_hz23_formal_supervisor.sh" | tee -a logs/hz23_legacy_daemon_retired.log
cat > reports/hz23_legacy_daemon_retired_latest.json <<EOF
{
  "schema_version": "hz23-legacy-daemon-retired/v1",
  "generated_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "ok": false,
  "reason": "legacy_hz23_observation_daemon_retired",
  "replacement": "scripts/ops/start_hz23_formal_supervisor.sh"
}
EOF
exit 90
