#!/usr/bin/env bash
# Run only offline code validation and sanitized report publication.
# This script must run as the isolated datalab user on Singapore.
# No set -e is used.

ACTION="${1:-validate-publish}"
PROJECT_DIR="${AIDEAL_PROJECT_DIR:-/home/datalab/projects/aideal-cps-data-lab}"
EXPECTED_USER="${AIDEAL_EXPECTED_USER:-datalab}"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
TS="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$PROJECT_DIR/logs"
RUN_LOG="$LOG_DIR/remote_validation_${TS}.log"
SUMMARY_FILE="$PROJECT_DIR/run/remote_validation_latest.env"

summary_value() {
  KEY="$1"
  VALUE="$2"
  printf '%s=%s\n' "$KEY" "$VALUE" | tee -a "$SUMMARY_FILE"
}

prepare_repository() {
  CURRENT_USER="$(id -un)"
  if [ "$CURRENT_USER" != "$EXPECTED_USER" ]; then
    echo "STATUS=FAIL"
    echo "REASON=unexpected_runtime_user"
    echo "CURRENT_USER=$CURRENT_USER"
    echo "EXPECTED_USER=$EXPECTED_USER"
    return 1
  fi

  if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo "STATUS=FAIL"
    echo "REASON=repository_missing"
    echo "PROJECT_DIR=$PROJECT_DIR"
    return 1
  fi

  cd "$PROJECT_DIR"
  CD_RC=$?
  if [ "$CD_RC" != "0" ]; then
    echo "STATUS=FAIL"
    echo "REASON=repository_unavailable"
    return 1
  fi

  mkdir -p logs run reports
  : > "$SUMMARY_FILE"

  git fetch origin main >> "$RUN_LOG" 2>&1
  FETCH_RC=$?
  if [ "$FETCH_RC" != "0" ]; then
    summary_value PREPARE_RC 1
    summary_value PREPARE_REASON git_fetch_failed
    return 1
  fi

  git checkout main >> "$RUN_LOG" 2>&1
  CHECKOUT_RC=$?
  if [ "$CHECKOUT_RC" != "0" ]; then
    summary_value PREPARE_RC 1
    summary_value PREPARE_REASON git_checkout_failed
    return 1
  fi

  git reset --hard origin/main >> "$RUN_LOG" 2>&1
  RESET_RC=$?
  if [ "$RESET_RC" != "0" ]; then
    summary_value PREPARE_RC 1
    summary_value PREPARE_REASON git_reset_failed
    return 1
  fi

  summary_value PREPARE_RC 0
  summary_value GIT_HEAD "$(git rev-parse HEAD)"
  summary_value GIT_STATUS "$(git status --porcelain | wc -l | tr -d ' ')"
  return 0
}

prepare_python() {
  if [ ! -x "$PYTHON_BIN" ]; then
    python3 -m venv "$PROJECT_DIR/.venv" >> "$RUN_LOG" 2>&1
    VENV_RC=$?
    if [ "$VENV_RC" != "0" ]; then
      summary_value VENV_RC "$VENV_RC"
      return 1
    fi
  fi

  "$PYTHON_BIN" -m pip install --upgrade pip >> "$RUN_LOG" 2>&1
  PIP_RC=$?
  summary_value PIP_RC "$PIP_RC"
  if [ "$PIP_RC" != "0" ]; then
    return 1
  fi

  "$PYTHON_BIN" -m pip install -e ".[browser,mysql]" >> "$RUN_LOG" 2>&1
  INSTALL_RC=$?
  summary_value INSTALL_RC "$INSTALL_RC"
  return "$INSTALL_RC"
}

run_validation() {
  cd "$PROJECT_DIR"
  : > "$SUMMARY_FILE"
  summary_value STARTED_AT "$(date -Iseconds)"
  summary_value ACTION "$ACTION"

  prepare_repository
  PREPARE_RC=$?
  if [ "$PREPARE_RC" != "0" ]; then
    summary_value STATUS FAIL
    summary_value FINISHED_AT "$(date -Iseconds)"
    return 1
  fi

  prepare_python
  PYTHON_RC=$?
  if [ "$PYTHON_RC" != "0" ]; then
    summary_value STATUS FAIL
    summary_value FINISHED_AT "$(date -Iseconds)"
    return 1
  fi

  AIDEAL_OFFLINE_TEST=1 PYTHONPATH=src \
    "$PYTHON_BIN" -m compileall -q src scripts tests \
    >> "$RUN_LOG" 2>&1
  COMPILE_RC=$?
  summary_value COMPILE_RC "$COMPILE_RC"

  AIDEAL_OFFLINE_TEST=1 PYTHONPATH=src \
    "$PYTHON_BIN" scripts/run_offline_quality.py \
    >> "$RUN_LOG" 2>&1
  OFFLINE_RC=$?
  summary_value OFFLINE_RC "$OFFLINE_RC"

  AIDEAL_OFFLINE_TEST=1 PYTHONPATH=src \
    "$PYTHON_BIN" scripts/engineering_scan_full.py \
    >> "$RUN_LOG" 2>&1
  AUDIT_RC=$?
  summary_value AUDIT_RC "$AUDIT_RC"

  "$PYTHON_BIN" - <<'PY' >> "$SUMMARY_FILE"
import json
from pathlib import Path

def load(path: str) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))

offline = load("reports/offline_quality_latest.json")
audit = load("reports/project_engineering_audit_latest.json")
summary = audit.get("summary") or {}
categories = summary.get("category_counts") or {}
values = {
    "OFFLINE_STATUS": offline.get("status", "MISSING"),
    "TESTS_RUN": offline.get("tests_run", -1),
    "TEST_FAILURES": offline.get("test_failure_count", -1),
    "TEST_ERRORS": offline.get("test_error_count", -1),
    "JD_LIVE_CALLED": str(offline.get("jd_live_called")).lower(),
    "AUDIT_STATUS": audit.get("status", "MISSING"),
    "GLOBAL_BLOCKERS": audit.get("blocker_count", -1),
    "FULL_GATE_BLOCKERS": audit.get("full_gate_blocker_count", -1),
    "ACTIVE_BLOCKERS": audit.get("active_blocker_count", -1),
    "COMPATIBILITY_BLOCKERS": audit.get("compatibility_blocker_count", -1),
    "HISTORICAL_BLOCKERS": audit.get("historical_blocker_count", -1),
    "SUPPORT_BLOCKERS": audit.get("support_blocker_count", -1),
    "DUPLICATE_DEFINITION": categories.get("duplicate_definition", 0),
    "DUPLICATE_IMPLEMENTATION": categories.get("duplicate_implementation", 0),
    "LARGE_FILE": categories.get("large_file", 0),
    "LONG_FUNCTION": categories.get("long_function", 0),
}
for key, value in values.items():
    print(f"{key}={value}")
PY

  VALIDATION_RC=0
  if [ "$COMPILE_RC" != "0" ]; then VALIDATION_RC=1; fi
  if [ "$OFFLINE_RC" != "0" ]; then VALIDATION_RC=1; fi
  if [ "$AUDIT_RC" != "0" ]; then VALIDATION_RC=1; fi

  summary_value VALIDATION_RC "$VALIDATION_RC"
  if [ "$VALIDATION_RC" = "0" ]; then
    summary_value STATUS PASS
  else
    summary_value STATUS FAIL
  fi
  summary_value FINISHED_AT "$(date -Iseconds)"
  return "$VALIDATION_RC"
}

publish_reports() {
  cd "$PROJECT_DIR"
  FILES=(
    reports/offline_quality_latest.json
    reports/project_engineering_audit_latest.json
  )

  for path in "${FILES[@]}"; do
    if [ ! -f "$path" ]; then
      echo "STATUS=FAIL"
      echo "REASON=required_report_missing"
      echo "MISSING_FILE=$path"
      return 1
    fi
  done

  bash scripts/git_publish_files_via_worktree.sh \
    "reports: refresh isolated Data Lab validation" \
    "${FILES[@]}" \
    >> "$RUN_LOG" 2>&1
  PUBLISH_RC=$?
  summary_value PUBLISH_RC "$PUBLISH_RC"
  return "$PUBLISH_RC"
}

print_result() {
  echo "===== DATA LAB REMOTE VALIDATION ====="
  if [ -f "$SUMMARY_FILE" ]; then
    cat "$SUMMARY_FILE"
  else
    echo "STATUS=FAIL"
    echo "REASON=summary_missing"
  fi
  echo "LOG_FILE=$RUN_LOG"
  echo "===== LOG TAIL ====="
  tail -n 120 "$RUN_LOG" 2>/dev/null
}

case "$ACTION" in
  validate)
    run_validation
    FINAL_RC=$?
    print_result
    exit "$FINAL_RC"
    ;;
  validate-publish)
    run_validation
    VALIDATION_RC=$?
    publish_reports
    PUBLISH_RC=$?
    print_result
    if [ "$PUBLISH_RC" != "0" ]; then
      exit "$PUBLISH_RC"
    fi
    exit "$VALIDATION_RC"
    ;;
  publish-reports)
    prepare_repository
    PREPARE_RC=$?
    if [ "$PREPARE_RC" != "0" ]; then
      print_result
      exit "$PREPARE_RC"
    fi
    publish_reports
    FINAL_RC=$?
    print_result
    exit "$FINAL_RC"
    ;;
  *)
    echo "STATUS=FAIL"
    echo "REASON=unknown_action"
    echo "SUPPORTED_ACTIONS=validate validate-publish publish-reports"
    exit 2
    ;;
esac
