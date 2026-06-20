#!/usr/bin/env bash
# Run the complete offline code-governance gate in an isolated Git worktree.
# This entry does not run JD live collection, HZ24 recovery, MySQL initialization, or product publishing.

PROJECT_DIR="${AIDEAL_PROJECT_DIR:-${HOME}/projects/aideal-cps-data-lab}"
TARGET_REF="${1:-codex/complete-duplicate-audit}"
ACTION="${2:-validate}"
WORKTREE="${PROJECT_DIR}/run/code_governance_ci_bridge_worktree"
SUMMARY_SOURCE="${WORKTREE}/run/ci_bridge_latest.env"
SUMMARY_TARGET="${PROJECT_DIR}/run/code_governance_ci_bridge_latest.env"

mkdir -p "${PROJECT_DIR}/logs" "${PROJECT_DIR}/run" "${PROJECT_DIR}/reports"

if ! cd "${PROJECT_DIR}"; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
elif [ "${ACTION}" != "validate" ] && [ "${ACTION}" != "validate-publish" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "ERROR=INVALID_ACTION"
elif [ "${ACTION}" = "validate-publish" ] && [ "${TARGET_REF}" != "main" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "ERROR=PUBLISH_REQUIRES_MAIN"
elif [ -n "$(git status --short)" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "ERROR=DIRTY_WORKTREE"
else
  git fetch origin "${TARGET_REF}"
  FETCH_RC=$?

  if [ -d "${WORKTREE}" ]; then
    git worktree remove --force "${WORKTREE}" >/dev/null 2>&1
  fi
  rm -rf "${WORKTREE}"

  if [ "${FETCH_RC}" -eq 0 ]; then
    git worktree add --detach "${WORKTREE}" "origin/${TARGET_REF}"
    WORKTREE_RC=$?
  else
    WORKTREE_RC=1
  fi

  if [ -x "${PROJECT_DIR}/.venv/bin/python" ]; then
    PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi

  if [ "${WORKTREE_RC}" -eq 0 ]; then
    PYTHONPATH="${WORKTREE}/src" AIDEAL_OFFLINE_TEST=1 \
      "${PYTHON_BIN}" "${WORKTREE}/scripts/ops/ci_bridge_runner.py" \
      "${ACTION}" --root "${WORKTREE}"
    BRIDGE_RC=$?
  else
    BRIDGE_RC=1
  fi

  if [ -f "${SUMMARY_SOURCE}" ]; then
    cp "${SUMMARY_SOURCE}" "${SUMMARY_TARGET}"
  else
    {
      echo "STATUS=FAIL"
      echo "ERROR=SUMMARY_MISSING"
      echo "TARGET_REF=${TARGET_REF}"
      echo "ACTION=${ACTION}"
      echo "FETCH_RC=${FETCH_RC}"
      echo "WORKTREE_RC=${WORKTREE_RC}"
      echo "BRIDGE_RC=${BRIDGE_RC}"
    } > "${SUMMARY_TARGET}"
  fi

  echo "===== SUMMARY ====="
  cat "${SUMMARY_TARGET}"
  echo "TARGET_REF=${TARGET_REF}"
  echo "ACTION=${ACTION}"
  echo "WORKTREE_HEAD=$(git -C "${WORKTREE}" rev-parse HEAD 2>/dev/null)"
fi
