#!/usr/bin/env bash
# Commit only known runtime evidence, then rebase onto origin/main.
# Unknown source-code changes are never discarded. No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab"
CD_RC=$?
if [ "$CD_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=project_directory_missing"
  echo "CD_RC=$CD_RC"
  exit 1
fi
mkdir -p logs reports backups

STAMP="$(date +%Y%m%d_%H%M%S)"
STATUS_CMD=(git status --porcelain=v1 --untracked-files=all)
"${STATUS_CMD[@]}" > "backups/hz23_git_status_${STAMP}.txt"

UNKNOWN="$("${STATUS_CMD[@]}" | awk '
{
  path=substr($0,4)
  if (path ~ /^reports\//) next
  if (path ~ /^docs\/ops\//) next
  if (path ~ /^data\/export\/.*manifest\.json$/) next
  if (path ~ /^data\/export\/.*\.jsonl$/) next
  if (path ~ /^data\/import\//) next
  if (path ~ /^data\/state\//) next
  if (path ~ /^data\/history\//) next
  if (path ~ /^data\/raw\//) next
  if (path ~ /^data\/clean\//) next
  if (path ~ /^backups\//) next
  if (path ~ /^logs\//) next
  if (path ~ /^run\//) next
  print $0
}')"

if [ -n "$UNKNOWN" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=unknown_worktree_changes"
  echo "UNKNOWN_CHANGE_COUNT=$(printf '%s\n' "$UNKNOWN" | sed '/^$/d' | wc -l)"
  printf '%s\n' "$UNKNOWN" | head -n 30
  exit 1
fi

git add reports docs/ops 2>/dev/null || true
for path in data/export/*manifest.json; do
  [ -f "$path" ] && git add "$path" 2>/dev/null || true
done

if git diff --cached --quiet; then
  COMMIT_STATUS=no_change
else
  git commit -m "reports: checkpoint HZ23 runtime evidence"
  COMMIT_RC=$?
  if [ "$COMMIT_RC" != "0" ]; then
    echo "===== SUMMARY ====="
    echo "STATUS=FAIL"
    echo "STEP=commit_runtime_evidence"
    echo "COMMIT_RC=$COMMIT_RC"
    exit 1
  fi
  COMMIT_STATUS=committed
fi

GIT_TERMINAL_PROMPT=0 git fetch origin main
FETCH_RC=$?
if [ "$FETCH_RC" = "0" ]; then
  git rebase origin/main
  REBASE_RC=$?
else
  REBASE_RC=99
fi

if [ "$FETCH_RC" = "0" ] && [ "$REBASE_RC" = "0" ]; then
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main
  PUSH_RC=$?
else
  PUSH_RC=99
fi

LOCAL_HEAD="$(git rev-parse HEAD 2>/dev/null || true)"
REMOTE_HEAD="$(git ls-remote origin refs/heads/main 2>/dev/null | awk '{print $1}')"
DIRTY_COUNT="$("${STATUS_CMD[@]}" | wc -l)"
STATUS=PASS
if [ "$FETCH_RC" != "0" ] || [ "$REBASE_RC" != "0" ] || [ "$PUSH_RC" != "0" ] || [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "COMMIT_STATUS=$COMMIT_STATUS"
echo "FETCH_RC=$FETCH_RC"
echo "REBASE_RC=$REBASE_RC"
echo "PUSH_RC=$PUSH_RC"
echo "DIRTY_COUNT=$DIRTY_COUNT"
echo "LOCAL_HEAD=$LOCAL_HEAD"
echo "REMOTE_HEAD=$REMOTE_HEAD"

[ "$STATUS" = PASS ]
