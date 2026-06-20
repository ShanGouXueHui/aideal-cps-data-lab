#!/usr/bin/env bash
# Reload the observer only outside the JD operation window.
# This script does not open or operate the JD browser page.
# No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
. config/hz23-service.env
mkdir -p logs reports backups

DAY_START="$HZ23_DAY_START"
DAY_END="$HZ23_DAY_END"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT="reports/hz23_observer_reload_latest.json"

INSIDE_DAYTIME="$(python3 - "$DAY_START" "$DAY_END" <<'PY'
from datetime import datetime
import sys
start,end=sys.argv[1],sys.argv[2]
now=datetime.now(); cur=now.hour*60+now.minute
sh,sm=map(int,start.split(':')); eh,em=map(int,end.split(':'))
print('true' if sh*60+sm <= cur < eh*60+em else 'false')
PY
)"

if [ "$INSIDE_DAYTIME" = "true" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAILED"
  echo "STEP=daytime_guard"
  echo "DAY_WINDOW=$DAY_START-$DAY_END"
  exit 1
fi

if [ -f run/hz23_observer_state.json ]; then
  cp -a run/hz23_observer_state.json "backups/hz23_observer_state.reload.${STAMP}.json"
  BACKUP_RC=$?
else
  BACKUP_RC=2
fi

bash -n scripts/hz23_observation_daemon.sh scripts/hz23_mainline_refresh.sh \
  > logs/hz23_reload_shell_check.log 2>&1
SHELL_RC=$?

python3 -m py_compile \
  run/hz23_finalize_round.py \
  scripts/hz23_migrate_observer_state_v2.py \
  > logs/hz23_reload_python_check.log 2>&1
PYTHON_RC=$?

if [ "$BACKUP_RC" != "0" ] || [ "$SHELL_RC" != "0" ] || [ "$PYTHON_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAILED"
  echo "STEP=pre_reload_checks"
  echo "BACKUP_RC=$BACKUP_RC"
  echo "SHELL_RC=$SHELL_RC"
  echo "PYTHON_RC=$PYTHON_RC"
  exit 1
fi

OLD_PID="$(systemctl show aideal-hz23-observer.service -p MainPID --value 2>/dev/null || true)"
OLD_ACTIVE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"

sudo systemctl restart aideal-hz23-observer.service
RESTART_RC=$?

NEW_PID=""
NEW_ACTIVE=""
for _ in $(seq 1 15); do
  NEW_PID="$(systemctl show aideal-hz23-observer.service -p MainPID --value 2>/dev/null || true)"
  NEW_ACTIVE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"
  if [ "$NEW_ACTIVE" = "active" ] && [ -n "$NEW_PID" ] && [ "$NEW_PID" != "0" ] && [ "$NEW_PID" != "$OLD_PID" ]; then
    break
  fi
  sleep 1
done

sleep 2
MODE="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/hz23_observer_status_latest.json')
try:
    print(json.loads(p.read_text(encoding='utf-8')).get('mode') or '')
except Exception:
    print('')
PY
)"

HEAD="$(git rev-parse HEAD 2>/dev/null || true)"
python3 - "$REPORT" "$STAMP" "$HEAD" "$OLD_PID" "$NEW_PID" "$OLD_ACTIVE" "$NEW_ACTIVE" "$MODE" "$RESTART_RC" <<'PY'
import json,sys
from datetime import datetime
from pathlib import Path
out=Path(sys.argv[1])
payload={
  'schema_version':'aideal-hz23-observer-reload/v1',
  'generated_at':datetime.now().isoformat(timespec='seconds'),
  'reload_stamp':sys.argv[2],
  'git_head':sys.argv[3] or None,
  'old_pid':sys.argv[4] or None,
  'new_pid':sys.argv[5] or None,
  'old_service_state':sys.argv[6] or None,
  'new_service_state':sys.argv[7] or None,
  'observer_mode':sys.argv[8] or None,
  'restart_rc':int(sys.argv[9]),
  'nighttime_guard_passed':True,
  'jd_browser_operated':False,
  'ok':int(sys.argv[9])==0 and sys.argv[7]=='active' and sys.argv[5] not in ('','0',sys.argv[4]),
}
tmp=out.with_suffix(out.suffix+'.tmp')
tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
tmp.replace(out)
PY
REPORT_RC=$?

git add "$REPORT"
if git diff --cached --quiet; then
  COMMIT_STATUS="no_change"
else
  git commit -m "reports: publish HZ23 observer reload evidence"
  COMMIT_RC=$?
  if [ "$COMMIT_RC" != "0" ]; then
    echo "===== SUMMARY ====="
    echo "STATUS=FAILED"
    echo "STEP=commit_reload_report"
    echo "COMMIT_RC=$COMMIT_RC"
    exit "$COMMIT_RC"
  fi
  COMMIT_STATUS="committed"
fi

GIT_TERMINAL_PROMPT=0 git fetch origin main
FETCH_RC=$?
if [ "$FETCH_RC" = "0" ]; then
  GIT_TERMINAL_PROMPT=0 git rebase origin/main
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

if [ "$PUSH_RC" = "0" ]; then
  bash scripts/hz23_publish_commercial_status_v2.sh
  STATUS_PUBLISH_RC=$?
else
  STATUS_PUBLISH_RC=99
fi

LOCAL_HEAD="$(git rev-parse HEAD 2>/dev/null || true)"
REMOTE_HEAD="$(git ls-remote origin refs/heads/main 2>/dev/null | awk '{print $1}')"
STATUS="PASS"
if [ "$RESTART_RC" != "0" ] || [ "$REPORT_RC" != "0" ] || [ "$NEW_ACTIVE" != "active" ] || [ -z "$NEW_PID" ] || [ "$NEW_PID" = "0" ] || [ "$NEW_PID" = "$OLD_PID" ] || [ "$FETCH_RC" != "0" ] || [ "$REBASE_RC" != "0" ] || [ "$PUSH_RC" != "0" ] || [ "$STATUS_PUBLISH_RC" != "0" ] || [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  STATUS="FAIL"
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "BACKUP_RC=$BACKUP_RC"
echo "SHELL_RC=$SHELL_RC"
echo "PYTHON_RC=$PYTHON_RC"
echo "RESTART_RC=$RESTART_RC"
echo "OLD_PID=$OLD_PID"
echo "NEW_PID=$NEW_PID"
echo "SERVICE_STATE=$NEW_ACTIVE"
echo "OBSERVER_MODE=$MODE"
echo "COMMIT_STATUS=$COMMIT_STATUS"
echo "FETCH_RC=$FETCH_RC"
echo "REBASE_RC=$REBASE_RC"
echo "PUSH_RC=$PUSH_RC"
echo "STATUS_PUBLISH_RC=$STATUS_PUBLISH_RC"
echo "LOCAL_HEAD=$LOCAL_HEAD"
echo "REMOTE_HEAD=$REMOTE_HEAD"

[ "$STATUS" = "PASS" ]
