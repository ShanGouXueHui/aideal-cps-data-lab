#!/usr/bin/env bash
# Publish selected non-secret runtime evidence from an isolated worktree.
# Default target branch is runtime-evidence. This script must never push main.
# No set -e is used.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="${AIDEAL_PROJECT_DIR:-$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)}"
TARGET_BRANCH="${AIDEAL_RUNTIME_EVIDENCE_BRANCH:-runtime-evidence}"

if ! cd "$PROJECT_DIR"; then
  echo "PUBLISH_ERROR=project_directory_unavailable"
  exit 1
fi

case "$TARGET_BRANCH" in
  ""|main|master|*/main|*/master)
    echo "PUBLISH_ERROR=main_publish_forbidden:$TARGET_BRANCH"
    exit 2
    ;;
esac

MESSAGE="${1:-}"
if [ "$#" -gt 0 ]; then
  shift
fi
if [ -z "$MESSAGE" ] || [ "$#" -lt 1 ]; then
  echo "PUBLISH_ERROR=invalid_arguments"
  exit 2
fi

FILES=()
for path in "$@"; do
  case "$path" in
    /*|*".."*|*.jsonl|.secrets/*|run/*|logs/*|*.env|*.pem|*.key)
      echo "PUBLISH_ERROR=unsafe_path:$path"; exit 2 ;;
  esac
  case "$path" in
    reports/project_engineering_audit_latest.json|reports/offline_quality_latest.json)
      echo "PUBLISH_ERROR=quality_report_forbidden:$path"; exit 2 ;;
    reports/*.json|data/export/*.json) ;;
    *) echo "PUBLISH_ERROR=path_not_allowlisted:$path"; exit 2 ;;
  esac
  if [ -f "$path" ]; then
    FILES+=("$path")
  fi
done

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "PUBLISH_ERROR=no_existing_files"
  exit 2
fi

mkdir -p run logs
WORKTREE="$(mktemp -d "${TMPDIR:-/tmp}/aideal-runtime-evidence.XXXXXX")"
aideal_runtime_evidence_cleanup() {
  git worktree remove --force "$WORKTREE" >/dev/null 2>&1
  rmdir "$WORKTREE" >/dev/null 2>&1
  git worktree prune >/dev/null 2>&1
  return 0
}
trap aideal_runtime_evidence_cleanup EXIT

GIT_TERMINAL_PROMPT=0 git fetch origin main "$TARGET_BRANCH" \
  > logs/git_publish_fetch.log 2>&1
FETCH_RC=$?
if [ "$FETCH_RC" = "0" ]; then
  WORKTREE_BASE="origin/$TARGET_BRANCH"
else
  GIT_TERMINAL_PROMPT=0 git fetch origin main \
    > logs/git_publish_fetch.log 2>&1
  FETCH_MAIN_RC=$?
  if [ "$FETCH_MAIN_RC" != "0" ]; then
    echo "PUBLISH_ERROR=fetch_failed"
    exit 1
  fi
  WORKTREE_BASE="origin/main"
fi

git worktree add --detach "$WORKTREE" "$WORKTREE_BASE" \
  > logs/git_publish_worktree.log 2>&1
WORKTREE_RC=$?
if [ "$WORKTREE_RC" != "0" ]; then
  echo "PUBLISH_ERROR=worktree_add_failed"
  exit 1
fi

for path in "${FILES[@]}"; do
  mkdir -p "$WORKTREE/$(dirname "$path")"
  cp -a "$PROJECT_DIR/$path" "$WORKTREE/$path"
done

if ! cd "$WORKTREE"; then
  echo "PUBLISH_ERROR=worktree_directory_unavailable"
  exit 1
fi
git add -f -- "${FILES[@]}"
if git diff --cached --quiet; then
  echo "PUBLISH_STATUS=no_change"
  exit 0
fi

git commit -m "$MESSAGE" > /dev/null 2>&1
COMMIT_RC=$?
if [ "$COMMIT_RC" != "0" ]; then
  echo "PUBLISH_ERROR=commit_failed"
  exit 1
fi

GIT_TERMINAL_PROMPT=0 git push origin HEAD:"$TARGET_BRANCH" \
  > "$PROJECT_DIR/logs/git_publish_push.log" 2>&1
PUSH_RC=$?
if [ "$PUSH_RC" != "0" ]; then
  echo "PUBLISH_ERROR=push_failed"
  exit 1
fi

echo "PUBLISH_STATUS=committed"
echo "PUBLISHED_BRANCH=$TARGET_BRANCH"
echo "PUBLISHED_HEAD=$(git rev-parse HEAD)"
exit 0
