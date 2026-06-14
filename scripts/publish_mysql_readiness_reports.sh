#!/usr/bin/env bash
# Offline only. No JD traffic, MySQL connection, or service restart.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p reports logs

bash scripts/check_commission_mysql_release_readiness.sh \
  > logs/mysql_readiness_publish.log 2>&1
CHECK_RC=$?

python3 - "$CHECK_RC" <<'PY'
import json,sys
from datetime import datetime
from pathlib import Path
p=Path('reports/commission_mysql_initialization_plan_latest.json')
plan={}
if p.exists():
    try: plan=json.loads(p.read_text(encoding='utf-8'))
    except Exception: plan={}
out=Path('reports/commission_mysql_release_readiness_latest.json')
data={
 'schema_version':'aideal-commission-mysql-release-readiness/v1',
 'generated_at':datetime.now().isoformat(timespec='seconds'),
 'offline_checks_passed':int(sys.argv[1])==0,
 'ready_for_database_initialization':bool(plan.get('ready_for_database_initialization')),
 'plan_failures':plan.get('failures') or [],
 'execution_performed':False,
}
out.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
PY
BUILD_RC=$?

git add reports/commission_mysql_initialization_plan_latest.json \
  reports/commission_mysql_release_readiness_latest.json 2>/dev/null || true

git commit -m "reports: publish commission MySQL readiness" >/dev/null 2>&1 || true
GIT_TERMINAL_PROMPT=0 git pull --rebase origin main >/dev/null 2>&1
PULL_RC=$?
GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1
PUSH_RC=$?

READY="$(python3 - <<'PY'
import json
from pathlib import Path
x=json.loads(Path('reports/commission_mysql_release_readiness_latest.json').read_text())
print(str(bool(x.get('ready_for_database_initialization'))).lower())
print(','.join(x.get('plan_failures') or []))
PY
)"

echo "===== SUMMARY ====="
echo "STATUS=$([ "$CHECK_RC" = 0 ] && [ "$BUILD_RC" = 0 ] && [ "$PULL_RC" = 0 ] && [ "$PUSH_RC" = 0 ] && echo PASS || echo FAIL)"
echo "CHECK_RC=$CHECK_RC"
echo "BUILD_RC=$BUILD_RC"
echo "PULL_RC=$PULL_RC"
echo "PUSH_RC=$PUSH_RC"
echo "READY_FOR_DATABASE_INITIALIZATION=$(printf '%s\n' "$READY" | sed -n '1p')"
echo "PLAN_FAILURES=$(printf '%s\n' "$READY" | sed -n '2p')"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
