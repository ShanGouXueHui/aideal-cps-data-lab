#!/usr/bin/env bash
# Auto-discover MySQL connection using Python drivers only.
# It does not require mysql CLI. It never creates/updates/deletes data or applies DDL.
# Secrets are used only locally and are never printed or published.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run

REPORT="reports/mysql_python_autodiscover_latest.json"
TABLE_NAME="${MYSQL_TABLE:-aideal_cps_commission_products}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [ -x ".venv-browser/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv-browser/bin/python}"
fi

"$PYTHON_BIN" - "$REPORT" "$TABLE_NAME" <<'PY'
import importlib.util
import json
import os
import re
import socket
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

report=Path(sys.argv[1])
table=sys.argv[2]

candidate_files=[
    '.env', '.env.local', '.env.production', '.env.prod',
    'config/.env', 'config/app.env', 'config/prod.env', 'config/production.env',
    'run/.env', 'run/app.env',
]
for folder in ('config','run'):
    base=Path(folder)
    if base.exists():
        for p in base.glob('*.env'):
            candidate_files.append(str(p))

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
        'port':int(env.get('MYSQL_PORT') or env.get('DB_PORT') or env.get('DATABASE_PORT') or 3306),
        'database':env.get('MYSQL_DATABASE') or env.get('MYSQL_DB') or env.get('DB_NAME') or env.get('DATABASE_NAME') or env.get('DB_DATABASE'),
        'user':env.get('MYSQL_USER') or env.get('DB_USER') or env.get('DATABASE_USER') or env.get('DB_USERNAME'),
        'password':env.get('MYSQL_PASSWORD') or env.get('DB_PASSWORD') or env.get('DATABASE_PASSWORD'),
    }
    url=env.get('DATABASE_URL') or env.get('SQLALCHEMY_DATABASE_URI') or env.get('DB_URL')
    if url and ('mysql' in url.lower()):
        parsed=urlparse(url)
        prof.update({
            'host':parsed.hostname or prof['host'],
            'port':int(parsed.port or prof['port']),
            'database':(parsed.path or '').lstrip('/') or prof['database'],
            'user':unquote(parsed.username or '') or prof['user'],
            'password':unquote(parsed.password or '') or prof['password'],
        })
    return prof

def masked_profile(p):
    return {
        'source':p.get('source'),
        'host':p.get('host'),
        'port':p.get('port'),
        'database':p.get('database'),
        'database_present':bool(p.get('database')),
        'user':p.get('user'),
        'user_present':bool(p.get('user')),
        'password_present':bool(p.get('password')),
    }

profiles=[]
profiles.append(profile_from_env(dict(os.environ),'process_env'))
for file_name in dict.fromkeys(candidate_files):
    env=parse_kv_file(Path(file_name))
    if env:
        profiles.append(profile_from_env(env,file_name))
profiles.extend([
    {'source':'local_root_tcp_no_password','host':'127.0.0.1','port':3306,'database':'mysql','user':'root','password':''},
    {'source':'local_mysql_tcp_no_password','host':'127.0.0.1','port':3306,'database':'mysql','user':'mysql','password':''},
])
seen=set()
unique=[]
for p in profiles:
    key=(p.get('source'),p.get('host'),p.get('port'),p.get('database'),p.get('user'),bool(p.get('password')))
    if key in seen:
        continue
    seen.add(key)
    unique.append(p)

pymysql_available=importlib.util.find_spec('pymysql') is not None
mysql_connector_available=importlib.util.find_spec('mysql.connector') is not None
selected_driver=None
if pymysql_available:
    import pymysql
    selected_driver='pymysql'
elif mysql_connector_available:
    import mysql.connector
    selected_driver='mysql.connector'

def connect_with_profile(p, database_override=None):
    if not selected_driver:
        raise RuntimeError('python_mysql_driver_missing')
    user=p.get('user') or ''
    if not user:
        raise RuntimeError('missing_user')
    db=database_override if database_override is not None else (p.get('database') or None)
    if selected_driver == 'pymysql':
        return pymysql.connect(
            host=p.get('host') or '127.0.0.1',
            port=int(p.get('port') or 3306),
            user=user,
            password=p.get('password') or '',
            database=db,
            charset='utf8mb4',
            connect_timeout=10,
            read_timeout=20,
            write_timeout=20,
            autocommit=True,
        )
    return mysql.connector.connect(
        host=p.get('host') or '127.0.0.1',
        port=int(p.get('port') or 3306),
        user=user,
        password=p.get('password') or '',
        database=db,
        connection_timeout=10,
        autocommit=True,
    )

def query(conn, sql):
    cur=conn.cursor()
    cur.execute(sql)
    rows=cur.fetchall()
    cur.close()
    return rows

attempts=[]
selected=None
if selected_driver:
    for p in unique:
        try:
            conn=connect_with_profile(p, database_override=None)
            rows=query(conn,'SELECT VERSION()')
            conn.close()
            attempts.append({'profile':masked_profile(p),'connect_ok':True,'driver':selected_driver})
            if selected is None:
                selected=p
        except Exception as exc:
            attempts.append({'profile':masked_profile(p),'connect_ok':False,'driver':selected_driver,'error_tail':repr(exc)[-300:]})
else:
    attempts.append({'connect_ok':False,'error_tail':'python_mysql_driver_missing'})

schema={'attempted':False,'connection_ok':False,'schema_ready':False,'failures':[]}
if selected:
    schema['attempted']=True
    db=selected.get('database')
    if not db or db == 'mysql':
        try:
            conn=connect_with_profile(selected, database_override=None)
            db_rows=query(conn,'SHOW DATABASES')
            conn.close()
            dbs=[str(r[0]) for r in db_rows if str(r[0]) not in {'information_schema','mysql','performance_schema','sys'}]
            schema['database_candidates']=dbs[:20]
            schema['failures'].append('target_database_not_identified')
        except Exception as exc:
            schema['failures'].append('database_discovery_failed')
            schema['error_tail']=repr(exc)[-500:]
    else:
        try:
            conn=connect_with_profile(selected, database_override=db)
            schema['connection_ok']=True
            rows=query(conn,"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=%s" if selected_driver == 'pymysql' else "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=%s")
            conn.close()
        except Exception:
            # Parameter style differs across drivers; retry with escaped constant because table name is local constant.
            try:
                conn=connect_with_profile(selected, database_override=db)
                table_escaped=table.replace("'","''")
                rows=query(conn,f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='{table_escaped}'")
                table_exists=bool(rows and int(rows[0][0]) == 1)
                schema['table_exists']=table_exists
                if not table_exists:
                    schema['failures'].append('table_missing')
                else:
                    schema['schema_ready']=True
                conn.close()
            except Exception as exc:
                schema['failures'].append('schema_query_failed')
                schema['error_tail']=repr(exc)[-500:]

payload={
    'schema_version':'mysql-python-autodiscover-readonly/v1',
    'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
    'python_executable':sys.executable,
    'pymysql_available':pymysql_available,
    'mysql_connector_available':mysql_connector_available,
    'selected_driver':selected_driver,
    'table_name':table,
    'masked_config_lines':masked_lines[:80],
    'profiles':[masked_profile(p) for p in unique],
    'attempts':attempts,
    'selected_profile':masked_profile(selected) if selected else None,
    'schema_result':schema,
    'ok':bool(selected) and schema.get('connection_ok') and schema.get('schema_ready'),
}
report.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n', encoding='utf-8')
print(f'MYSQL_PYTHON_AUTODISCOVER_REPORT={report}')
print(f'PYTHON_EXECUTABLE={sys.executable}')
print(f'PYMYSQL_AVAILABLE={pymysql_available}')
print(f'MYSQL_CONNECTOR_AVAILABLE={mysql_connector_available}')
print(f'SELECTED_DRIVER={selected_driver}')
print(f'PROFILE_COUNT={len(unique)}')
print(f'CONNECT_OK={bool(selected)}')
print(f'SELECTED_SOURCE={(selected or {}).get("source") if selected else None}')
print(f'SELECTED_DATABASE={(selected or {}).get("database") if selected else None}')
print(f'SCHEMA_ATTEMPTED={schema.get("attempted")}')
print(f'SCHEMA_CONNECTION_OK={schema.get("connection_ok")}')
print(f'SCHEMA_READY={schema.get("schema_ready")}')
print(f'TABLE_EXISTS={schema.get("table_exists") if "table_exists" in schema else None}')
print(f'FAILURES={",".join(schema.get("failures") or []) if schema.get("failures") else "none"}')
if schema.get('database_candidates'):
    print('DATABASE_CANDIDATES=' + ','.join(schema.get('database_candidates')[:20]))
PY
PY_RC=$?

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish MySQL Python autodiscover" \
  "$REPORT" \
  > logs/mysql_python_autodiscover_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "PY_RC=$PY_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
