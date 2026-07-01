#!/usr/bin/env bash
# Auto-discover local MySQL connection configuration and run read-only schema check if possible.
# Secrets are used only locally and are never printed or published.
# It never creates tables, inserts rows, updates rows, deletes rows, or applies DDL.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run

REPORT="reports/mysql_connection_autodiscover_latest.json"
TABLE_NAME="${MYSQL_TABLE:-aideal_cps_commission_products}"
MYSQL_PORT_DEFAULT="${MYSQL_PORT:-3306}"
MYSQL_BIN="${MYSQL_BIN:-mysql}"

python3 - "$REPORT" "$TABLE_NAME" "$MYSQL_BIN" "$MYSQL_PORT_DEFAULT" <<'PY'
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

report=Path(sys.argv[1])
table=sys.argv[2]
mysql_bin=sys.argv[3]
default_port=sys.argv[4]

candidate_files=[
    '.env', '.env.local', '.env.production', '.env.prod',
    'config/.env', 'config/app.env', 'config/prod.env', 'config/production.env',
    'run/.env', 'run/app.env',
]
for p in Path('config').glob('*.env'):
    candidate_files.append(str(p))
for p in Path('run').glob('*.env'):
    candidate_files.append(str(p))

secret_keys={'MYSQL_PASSWORD','DB_PASSWORD','DATABASE_PASSWORD','SQL_PASSWORD','PASSWORD'}
profiles=[]
masked_lines=[]

def mask_line(line):
    if re.search(r'(PASSWORD|PASS|SECRET|TOKEN)', line, re.I):
        key=line.split('=',1)[0] if '=' in line else line[:40]
        return f'{key}=***MASKED***'
    return line.strip()[:300]

def parse_kv_file(path):
    env={}
    if not path.exists() or not path.is_file():
        return env
    try:
        text=path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return env
    for raw in text.splitlines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key,value=line.split('=',1)
        key=key.strip().replace('export ','').strip()
        value=value.strip().strip('"').strip("'")
        if re.search(r'(MYSQL|DATABASE|DB_|SQLALCHEMY)', key, re.I):
            masked_lines.append({'file':str(path),'line':mask_line(line)})
        env[key]=value
    return env

def profile_from_env(env, source):
    prof={
        'source':source,
        'host':env.get('MYSQL_HOST') or env.get('DB_HOST') or env.get('DATABASE_HOST') or '127.0.0.1',
        'port':env.get('MYSQL_PORT') or env.get('DB_PORT') or env.get('DATABASE_PORT') or default_port,
        'database':env.get('MYSQL_DATABASE') or env.get('MYSQL_DB') or env.get('DB_NAME') or env.get('DATABASE_NAME') or env.get('DB_DATABASE'),
        'user':env.get('MYSQL_USER') or env.get('DB_USER') or env.get('DATABASE_USER') or env.get('DB_USERNAME'),
        'password':env.get('MYSQL_PASSWORD') or env.get('DB_PASSWORD') or env.get('DATABASE_PASSWORD'),
        'socket':env.get('MYSQL_SOCKET'),
    }
    url=env.get('DATABASE_URL') or env.get('SQLALCHEMY_DATABASE_URI') or env.get('DB_URL')
    if url and ('mysql' in url.lower()):
        parsed=urlparse(url)
        prof.update({
            'host':parsed.hostname or prof['host'],
            'port':str(parsed.port or prof['port']),
            'database':(parsed.path or '').lstrip('/') or prof['database'],
            'user':unquote(parsed.username or '') or prof['user'],
            'password':unquote(parsed.password or '') or prof['password'],
        })
    return prof

current_env=dict(os.environ)
profiles.append(profile_from_env(current_env,'process_env'))
for file_name in dict.fromkeys(candidate_files):
    p=Path(file_name)
    env=parse_kv_file(p)
    if env:
        profiles.append(profile_from_env(env,str(p)))

# common socket/root/no-password fallbacks
profiles.extend([
    {'source':'local_root_socket','host':'localhost','port':default_port,'database':'mysql','user':'root','password':'','socket':'/var/run/mysqld/mysqld.sock'},
    {'source':'local_root_tcp_no_password','host':'127.0.0.1','port':default_port,'database':'mysql','user':'root','password':'','socket':None},
])

# de-duplicate without exposing passwords
seen=set()
unique=[]
for p in profiles:
    key=(p.get('source'),p.get('host'),p.get('port'),p.get('database'),p.get('user'),bool(p.get('password')),p.get('socket'))
    if key in seen:
        continue
    seen.add(key)
    unique.append(p)

def masked_profile(p):
    return {
        'source':p.get('source'),
        'host':p.get('host'),
        'port':p.get('port'),
        'database_present':bool(p.get('database')),
        'database':p.get('database') if p.get('database') not in {None,''} else None,
        'user_present':bool(p.get('user')),
        'user':p.get('user') if p.get('user') not in {None,''} else None,
        'password_present':bool(p.get('password')),
        'socket':p.get('socket'),
    }

def run_mysql(profile, sql, database_override=None):
    if not shutil.which(mysql_bin):
        return 127,'','mysql_client_missing'
    user=profile.get('user') or ''
    if not user:
        return 3,'','missing_user'
    database=database_override if database_override is not None else (profile.get('database') or '')
    cmd=[mysql_bin,'--batch','--raw','--skip-column-names','--connect-timeout=10']
    if profile.get('socket') and Path(str(profile.get('socket'))).exists():
        cmd += ['--socket',str(profile.get('socket'))]
    else:
        cmd += ['--protocol=TCP','-h',str(profile.get('host') or '127.0.0.1'),'-P',str(profile.get('port') or default_port)]
    cmd += ['-u',user]
    if database:
        cmd.append(database)
    env=os.environ.copy()
    if profile.get('password'):
        env['MYSQL_PWD']=str(profile.get('password'))
    result=subprocess.run(cmd+['-e',sql],text=True,capture_output=True,env=env,timeout=30)
    return result.returncode,result.stdout,result.stderr

attempts=[]
selected=None
for p in unique:
    rc,out,err=run_mysql(p,'SELECT VERSION();', database_override=None)
    ok=(rc==0)
    attempts.append({'profile':masked_profile(p),'connect_ok':ok,'rc':rc,'error_tail':err[-300:] if not ok else ''})
    if ok and selected is None:
        selected=p

schema_result={'attempted':False,'connection_ok':False,'schema_ready':False,'failures':[]}
if selected:
    schema_result['attempted']=True
    db=selected.get('database') or os.environ.get('MYSQL_DATABASE') or os.environ.get('DB_NAME') or os.environ.get('DATABASE_NAME')
    if not db or db == 'mysql':
        # discover non-system databases for operator selection, no secrets
        rc,out,err=run_mysql(selected,"SHOW DATABASES;", database_override=None)
        dbs=[x.strip() for x in out.splitlines() if x.strip() and x.strip() not in {'information_schema','mysql','performance_schema','sys'}]
        schema_result['database_candidates']=dbs[:20]
        schema_result['failures'].append('target_database_not_identified')
    else:
        selected['database']=db
        rc,out,err=run_mysql(selected,'SELECT VERSION(), DATABASE(), @@read_only, @@super_read_only;')
        if rc != 0:
            schema_result['failures'].append('selected_profile_database_connection_failed')
            schema_result['error_tail']=err[-500:]
        else:
            schema_result['connection_ok']=True
            table_escaped=table.replace("'","''")
            rc,out,err=run_mysql(selected,f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='{table_escaped}';")
            table_exists=(rc==0 and out.strip()=='1')
            schema_result['table_exists']=table_exists
            if not table_exists:
                schema_result['failures'].append('table_missing')
                schema_result['schema_ready']=False
            else:
                schema_result['schema_ready']=True

payload={
    'schema_version':'mysql-connection-autodiscover-readonly/v1',
    'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
    'mysql_bin':mysql_bin,
    'mysql_bin_found':bool(shutil.which(mysql_bin)),
    'table_name':table,
    'masked_config_lines':masked_lines[:80],
    'profiles': [masked_profile(p) for p in unique],
    'attempts': attempts,
    'selected_profile': masked_profile(selected) if selected else None,
    'schema_result': schema_result,
    'ok': bool(selected) and schema_result.get('connection_ok') and schema_result.get('schema_ready'),
}
report.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(f'MYSQL_AUTODISCOVER_REPORT={report}')
print(f'MYSQL_BIN_FOUND={payload["mysql_bin_found"]}')
print(f'PROFILE_COUNT={len(unique)}')
print(f'CONNECT_OK={bool(selected)}')
print(f'SELECTED_SOURCE={(selected or {}).get("source") if selected else None}')
print(f'SELECTED_DATABASE={(selected or {}).get("database") if selected else None}')
print(f'SCHEMA_ATTEMPTED={schema_result.get("attempted")}')
print(f'SCHEMA_CONNECTION_OK={schema_result.get("connection_ok")}')
print(f'SCHEMA_READY={schema_result.get("schema_ready")}')
print(f'TABLE_EXISTS={schema_result.get("table_exists") if "table_exists" in schema_result else None}')
print(f'FAILURES={",".join(schema_result.get("failures") or []) if schema_result.get("failures") else "none"}')
if schema_result.get('database_candidates'):
    print('DATABASE_CANDIDATES=' + ','.join(schema_result.get('database_candidates')[:20]))
PY
DISCOVER_RC=$?

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish MySQL connection autodiscover" \
  "$REPORT" \
  > logs/mysql_connection_autodiscover_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "DISCOVER_RC=$DISCOVER_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
