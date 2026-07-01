#!/usr/bin/env bash
# Read-only MySQL schema check for AIdeal CPS commission product table.
# It never creates tables, inserts rows, updates rows, deletes rows, or applies DDL.
# Required env: MYSQL_HOST, MYSQL_DATABASE, MYSQL_USER. Optional: MYSQL_PORT, MYSQL_PASSWORD, MYSQL_TABLE.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run

REPORT="reports/mysql_schema_readonly_check_latest.json"
TABLE_NAME="${MYSQL_TABLE:-aideal_cps_commission_products}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_BIN="${MYSQL_BIN:-mysql}"

python3 - "$REPORT" "$TABLE_NAME" "$MYSQL_BIN" "$MYSQL_HOST" "$MYSQL_PORT" "$MYSQL_DATABASE" "$MYSQL_USER" <<'PY'
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

report=Path(sys.argv[1])
table=sys.argv[2]
mysql_bin=sys.argv[3]
host=sys.argv[4] if len(sys.argv) > 4 else ''
port=sys.argv[5] if len(sys.argv) > 5 else '3306'
database=sys.argv[6] if len(sys.argv) > 6 else ''
user=sys.argv[7] if len(sys.argv) > 7 else ''
password=os.environ.get('MYSQL_PASSWORD') or ''

expected_columns={
  'jd_sku_id','title','description','item_url','promotion_url','short_url','long_url','qr_url','jd_command','image_url',
  'category_name','shop_name','price','coupon_price','commission_rate','estimated_commission','sales_volume','coupon_info','status',
  'link_created_at','link_expire_at','refresh_due_at','source_page_no','source_round_id','source_run_id','source_payload_hash',
  'catalog_change_count','first_seen_at','last_checked_at','last_seen_at','created_at','updated_at'
}
required_indexes={'uk_jd_sku_id','idx_status','idx_refresh_due_at','idx_link_expire_at','idx_source_round_id','idx_source_payload_hash'}

payload={
  'schema_version':'mysql-schema-readonly-check/v1',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'ok':False,
  'connection_ok':False,
  'schema_ready':False,
  'table_name':table,
  'config':{
    'host_present':bool(host),
    'port':port,
    'database_present':bool(database),
    'user_present':bool(user),
    'password_present':bool(password),
    'mysql_bin':mysql_bin,
    'mysql_bin_found':bool(shutil.which(mysql_bin)),
  },
  'failures':[],
  'warnings':[],
  'server':{},
  'table':{},
  'columns':[],
  'indexes':[],
  'missing_columns':[],
  'extra_columns':[],
  'missing_indexes':[],
}

if not shutil.which(mysql_bin):
    payload['failures'].append('mysql_client_missing')
for name,value in [('MYSQL_HOST',host),('MYSQL_DATABASE',database),('MYSQL_USER',user)]:
    if not value:
        payload['failures'].append(f'missing_{name.lower()}')

base_cmd=[mysql_bin,'--batch','--raw','--skip-column-names','--connect-timeout=10','--protocol=TCP','-h',host,'-P',str(port),'-u',user,database]
env=os.environ.copy()
if password:
    env['MYSQL_PWD']=password

def run_sql(sql):
    result=subprocess.run(base_cmd+['-e',sql], text=True, capture_output=True, env=env, timeout=30)
    return result.returncode, result.stdout, result.stderr

if not payload['failures']:
    rc,out,err=run_sql('SELECT VERSION(), DATABASE(), @@read_only, @@super_read_only;')
    if rc != 0:
        payload['failures'].append('mysql_connection_failed')
        payload['mysql_error_tail']=err[-1000:]
    else:
        payload['connection_ok']=True
        fields=out.strip().split('\t')
        if len(fields) >= 4:
            payload['server']={'version':fields[0],'database':fields[1],'read_only':fields[2],'super_read_only':fields[3]}
        rc,out,err=run_sql(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='{table.replace(chr(39), chr(39)+chr(39))}';")
        table_exists=(rc == 0 and out.strip() == '1')
        payload['table']['exists']=table_exists
        if not table_exists:
            payload['failures'].append('table_missing')
            payload['ddl_apply_required']=True
        else:
            col_sql=f"""
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COALESCE(COLUMN_DEFAULT,''), EXTRA
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{table.replace(chr(39), chr(39)+chr(39))}'
ORDER BY ORDINAL_POSITION;
"""
            rc,out,err=run_sql(col_sql)
            if rc != 0:
                payload['failures'].append('columns_query_failed')
                payload['columns_error_tail']=err[-1000:]
            else:
                cols=[]
                for line in out.splitlines():
                    parts=line.split('\t')
                    if len(parts) >= 6:
                        cols.append({'name':parts[0],'column_type':parts[1],'nullable':parts[2],'key':parts[3],'default':parts[4],'extra':parts[5]})
                payload['columns']=cols
                names={c['name'] for c in cols}
                payload['missing_columns']=sorted(expected_columns-names)
                payload['extra_columns']=sorted(names-expected_columns)
                if payload['missing_columns']:
                    payload['failures'].append('missing_columns')
                if payload['extra_columns']:
                    payload['warnings'].append('extra_columns_present')
            idx_sql=f"""
SELECT INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{table.replace(chr(39), chr(39)+chr(39))}'
ORDER BY INDEX_NAME, SEQ_IN_INDEX;
"""
            rc,out,err=run_sql(idx_sql)
            if rc != 0:
                payload['failures'].append('indexes_query_failed')
                payload['indexes_error_tail']=err[-1000:]
            else:
                indexes=[]
                idx_names=set()
                for line in out.splitlines():
                    parts=line.split('\t')
                    if len(parts) >= 4:
                        indexes.append({'name':parts[0],'non_unique':parts[1],'seq':parts[2],'column':parts[3]})
                        idx_names.add(parts[0])
                payload['indexes']=indexes
                payload['missing_indexes']=sorted(required_indexes-idx_names)
                if payload['missing_indexes']:
                    payload['failures'].append('missing_indexes')
            payload['schema_ready']=not any(f in payload['failures'] for f in ['table_missing','missing_columns','missing_indexes','columns_query_failed','indexes_query_failed'])

payload['ok']=payload['connection_ok'] and payload['schema_ready'] and not payload['failures']
report.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n', encoding='utf-8')
print(f'MYSQL_SCHEMA_REPORT={report}')
print(f'CONNECTION_OK={payload["connection_ok"]}')
print(f'SCHEMA_READY={payload["schema_ready"]}')
print(f'TABLE_EXISTS={payload.get("table",{}).get("exists")}')
print(f'FAILURES={",".join(payload["failures"]) if payload["failures"] else "none"}')
print(f'WARNINGS={",".join(payload["warnings"]) if payload["warnings"] else "none"}')
print(f'MISSING_COLUMNS={",".join(payload["missing_columns"]) if payload["missing_columns"] else "none"}')
print(f'MISSING_INDEXES={",".join(payload["missing_indexes"]) if payload["missing_indexes"] else "none"}')
print(f'MYSQL_BIN_FOUND={payload["config"]["mysql_bin_found"]}')
PY
CHECK_RC=$?

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish MySQL schema readonly check" \
  "$REPORT" \
  > logs/mysql_schema_readonly_check_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "CHECK_RC=$CHECK_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
