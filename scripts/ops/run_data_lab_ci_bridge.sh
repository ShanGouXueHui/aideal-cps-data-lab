#!/usr/bin/env bash
# Run Data Lab offline validation on the isolated Singapore datalab account.
# No JD live access, collection, MySQL initialization, publish, or sync.
# No set -e is used.

ACTION="${1:-validate-publish}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$PROJECT_DIR/config/ci-bridge.env"
TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$PROJECT_DIR/logs/ci_bridge_${TS}.log"
SUMMARY_FILE="$PROJECT_DIR/run/ci_bridge_latest.env"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "STATUS=FAIL"
  echo "REASON=ci_bridge_config_missing"
  exit 1
fi
. "$CONFIG_FILE"

record() {
  printf '%s=%s\n' "$1" "$2" | tee -a "$SUMMARY_FILE"
}

mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/run" "$PROJECT_DIR/reports"
: > "$SUMMARY_FILE"

if [ "$(id -un)" != "$CI_BRIDGE_EXECUTION_USER" ]; then
  record STATUS FAIL
  record REASON unexpected_runtime_user
  record CURRENT_USER "$(id -un)"
  record EXPECTED_USER "$CI_BRIDGE_EXECUTION_USER"
  exit 1
fi

cd "$PROJECT_DIR"
CD_RC=$?
if [ "$CD_RC" != "0" ] || [ ! -d .git ]; then
  record STATUS FAIL
  record REASON repository_unavailable
  exit 1
fi

record ACTION "$ACTION"
record GIT_HEAD "$(git rev-parse HEAD)"
record STARTED_AT "$(date -Iseconds)"

PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  python3 -m venv "$PROJECT_DIR/.venv" >> "$LOG_FILE" 2>&1
  VENV_RC=$?
else
  VENV_RC=0
fi
record VENV_RC "$VENV_RC"

INSTALL_RC=1
if [ "$VENV_RC" = "0" ]; then
  "$PYTHON_BIN" -m pip install -e ".[browser,mysql]" >> "$LOG_FILE" 2>&1
  INSTALL_RC=$?
fi
record INSTALL_RC "$INSTALL_RC"

COMPILE_RC=1
OFFLINE_RC=1
AUDIT_RC=1
if [ "$INSTALL_RC" = "0" ]; then
  AIDEAL_OFFLINE_TEST=1 PYTHONPATH=src \
    "$PYTHON_BIN" -m compileall -q src scripts tests >> "$LOG_FILE" 2>&1
  COMPILE_RC=$?
  record COMPILE_RC "$COMPILE_RC"

  AIDEAL_DEPENDENCY_INSTALL_OUTCOME=success AIDEAL_OFFLINE_TEST=1 PYTHONPATH=src \
    "$PYTHON_BIN" scripts/run_offline_quality.py >> "$LOG_FILE" 2>&1
  OFFLINE_RC=$?
  record OFFLINE_RC "$OFFLINE_RC"

  AIDEAL_OFFLINE_TEST=1 PYTHONPATH=src \
    "$PYTHON_BIN" scripts/engineering_scan_full.py >> "$LOG_FILE" 2>&1
  AUDIT_RC=$?
  record AUDIT_RC "$AUDIT_RC"
fi

if [ -x "$PYTHON_BIN" ]; then
  "$PYTHON_BIN" scripts/ops/ci_bridge_summary.py | tee -a "$SUMMARY_FILE"
fi

PUBLISH_RC=0
if [ "$ACTION" = "validate-publish" ]; then
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: refresh Singapore CI bridge validation" \
    reports/offline_quality_latest.json \
    reports/project_engineering_audit_latest.json \
    >> "$LOG_FILE" 2>&1
  PUBLISH_RC=$?
fi
record PUBLISH_RC "$PUBLISH_RC"

FINAL_RC=0
if [ "$VENV_RC" != "0" ]; then FINAL_RC=1; fi
if [ "$INSTALL_RC" != "0" ]; then FINAL_RC=1; fi
if [ "$COMPILE_RC" != "0" ]; then FINAL_RC=1; fi
if [ "$OFFLINE_RC" != "0" ]; then FINAL_RC=1; fi
if [ "$AUDIT_RC" != "0" ]; then FINAL_RC=1; fi
if [ "$PUBLISH_RC" != "0" ]; then FINAL_RC=1; fi

record FINISHED_AT "$(date -Iseconds)"
record LOG_FILE "$LOG_FILE"
if [ "$FINAL_RC" = "0" ]; then
  record STATUS PASS
else
  record STATUS FAIL
fi

cat "$SUMMARY_FILE"
echo "===== LOG TAIL ====="
tail -n 120 "$LOG_FILE" 2>/dev/null
exit "$FINAL_RC"
