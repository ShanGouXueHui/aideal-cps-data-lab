#!/usr/bin/env bash
# CPS/MySQL contract dry-run for commercial candidate feed.
# Generates DDL and upsert preview locally, embeds them in JSON report, validates all candidate rows, but never connects to MySQL.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"
mkdir -p logs reports run data/export

CANDIDATE="data/export/aideal_cps_products_commercial_candidate_latest.jsonl"
MANIFEST="data/export/aideal_cps_products_commercial_candidate_manifest.json"
REPORT="reports/cps_mysql_contract_dry_run_latest.json"
DDL="reports/aideal_cps_commission_products_ddl_latest.sql"
UPSERT_PREVIEW="reports/aideal_cps_commission_products_upsert_preview_latest.sql"
MIN_ROWS="${CPS_MYSQL_DRY_RUN_MIN_ROWS:-100}"

bash scripts/ops/hz23_candidate_feed_gate.sh > logs/cps_mysql_contract_candidate_gate.log 2>&1
CANDIDATE_GATE_RC=$?

python3 - "$CANDIDATE" "$MANIFEST" "$REPORT" "$DDL" "$UPSERT_PREVIEW" "$MIN_ROWS" "$CANDIDATE_GATE_RC" <<'PY'
import json
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from aideal_cps_data_lab.domain.commission_product import CommissionProduct, ProductValidationError
from aideal_cps_data_lab.hz24.repository import read_jsonl

candidate_path=Path(sys.argv[1])
manifest_path=Path(sys.argv[2])
report_path=Path(sys.argv[3])
ddl_path=Path(sys.argv[4])
preview_path=Path(sys.argv[5])
min_rows=int(sys.argv[6])
candidate_gate_rc=int(sys.argv[7])

def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}

def sql_quote(value):
    if value is None:
        return 'NULL'
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, int):
        return str(value)
    text=str(value)
    return "'" + text.replace('\\', '\\\\').replace("'", "''") + "'"

def serializable(payload):
    out={}
    for k,v in payload.items():
        if isinstance(v, Decimal):
            out[k]=str(v)
        else:
            out[k]=v
    return out

DDL_SQL="""-- AIdeal CPS commercial commission product table contract.
-- Generated as a dry-run artifact. Review before applying to production MySQL.

CREATE TABLE IF NOT EXISTS aideal_cps_commission_products (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  jd_sku_id VARCHAR(64) NOT NULL,
  title TEXT NOT NULL,
  description TEXT NULL,
  item_url TEXT NOT NULL,
  promotion_url TEXT NOT NULL,
  short_url TEXT NULL,
  long_url TEXT NULL,
  qr_url TEXT NULL,
  jd_command TEXT NULL,
  image_url TEXT NOT NULL,
  category_name VARCHAR(255) NULL,
  shop_name VARCHAR(255) NULL,
  price DECIMAL(12,2) NOT NULL,
  coupon_price DECIMAL(12,2) NULL,
  commission_rate DECIMAL(10,4) NULL,
  estimated_commission DECIMAL(12,2) NULL,
  sales_volume BIGINT NULL,
  coupon_info TEXT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  link_created_at VARCHAR(64) NULL,
  link_expire_at VARCHAR(64) NULL,
  refresh_due_at VARCHAR(64) NULL,
  source_page_no INT NULL,
  source_round_id VARCHAR(128) NULL,
  source_run_id VARCHAR(128) NULL,
  source_payload_hash CHAR(64) NOT NULL,
  catalog_change_count INT NOT NULL DEFAULT 0,
  first_seen_at VARCHAR(64) NULL,
  last_checked_at VARCHAR(64) NULL,
  last_seen_at VARCHAR(64) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_jd_sku_id (jd_sku_id),
  KEY idx_status (status),
  KEY idx_refresh_due_at (refresh_due_at),
  KEY idx_link_expire_at (link_expire_at),
  KEY idx_source_round_id (source_round_id),
  KEY idx_source_payload_hash (source_payload_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

ddl_path.write_text(DDL_SQL, encoding='utf-8')
rows=read_jsonl(candidate_path)
manifest=read_json(manifest_path)
products=[]
errors=Counter()
skus=[]
status_counts=Counter()
page_counts=Counter()
for idx,row in enumerate(rows, start=1):
    try:
        product=CommissionProduct.from_candidate_row(row)
        payload=product.persistence_payload()
        products.append(payload)
        skus.append(product.jd_sku_id)
        status_counts[payload.get('status')] += 1
        page_counts[payload.get('source_page_no')] += 1
    except ProductValidationError as exc:
        errors[str(exc)] += 1
    except Exception as exc:
        errors[type(exc).__name__] += 1

duplicate_skus=len(skus)-len(set(skus))
columns=[
  'jd_sku_id','title','description','item_url','promotion_url','short_url','long_url','qr_url','jd_command','image_url',
  'category_name','shop_name','price','coupon_price','commission_rate','estimated_commission','sales_volume','coupon_info','status',
  'link_created_at','link_expire_at','refresh_due_at','source_page_no','source_round_id','source_run_id','source_payload_hash',
  'catalog_change_count','first_seen_at','last_checked_at','last_seen_at'
]
preview=[]
for payload in products[:5]:
    values=', '.join(sql_quote(payload.get(col)) for col in columns)
    updates=', '.join(f'{col}=VALUES({col})' for col in columns if col != 'jd_sku_id')
    preview.append(
        f"INSERT INTO aideal_cps_commission_products ({', '.join(columns)}) VALUES ({values})\n"
        f"ON DUPLICATE KEY UPDATE {updates};"
    )
preview_sql='\n\n'.join(preview)+'\n'
preview_path.write_text(preview_sql, encoding='utf-8')

failures=[]
warnings=[]
if candidate_gate_rc != 0:
    failures.append(f'candidate_gate_rc:{candidate_gate_rc}')
if len(rows) < min_rows:
    failures.append('candidate_rows_below_minimum')
if errors:
    failures.append('candidate_row_validation_errors')
if duplicate_skus:
    failures.append('duplicate_skus')
if manifest.get('commercial_enabled') is not False:
    failures.append('commercial_enabled_not_false')
if manifest.get('feed_status') != 'candidate':
    failures.append('feed_status_not_candidate')
if manifest.get('row_count') != len(rows):
    warnings.append('manifest_row_count_differs')

payload={
  'schema_version':'cps-mysql-contract-dry-run/v2',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'ok':not failures,
  'failures':failures,
  'warnings':warnings,
  'candidate_path':str(candidate_path),
  'manifest_path':str(manifest_path),
  'ddl_path':str(ddl_path),
  'upsert_preview_path':str(preview_path),
  'ddl_sql':DDL_SQL,
  'upsert_preview_sql':preview_sql,
  'thresholds':{'min_rows':min_rows},
  'counts':{
    'candidate_rows':len(rows),
    'valid_products':len(products),
    'invalid_rows':sum(errors.values()),
    'duplicate_skus':duplicate_skus,
    'preview_rows':len(preview),
  },
  'candidate_gate_rc':candidate_gate_rc,
  'validation_errors':dict(errors),
  'status_counts':dict(status_counts),
  'source_page_top10':dict(page_counts.most_common(10)),
  'manifest':{
    'row_count':manifest.get('row_count'),
    'eligible_sku_count':manifest.get('eligible_sku_count'),
    'data_sha256':manifest.get('data_sha256'),
    'candidate_integrity_ready':manifest.get('candidate_integrity_ready'),
    'commercial_enabled':manifest.get('commercial_enabled'),
    'feed_status':manifest.get('feed_status'),
  },
  'sample_payloads':[serializable(p) for p in products[:3]],
}
report_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n', encoding='utf-8')
print(f'CPS_MYSQL_DRY_RUN_REPORT={report_path}')
print(f'DDL_PATH={ddl_path}')
print(f'UPSERT_PREVIEW_PATH={preview_path}')
print(f'DRY_RUN_OK={payload["ok"]}')
print(f'FAILURES={",".join(failures) if failures else "none"}')
print(f'WARNINGS={",".join(warnings) if warnings else "none"}')
print(f'CANDIDATE_ROWS={len(rows)}')
print(f'VALID_PRODUCTS={len(products)}')
print(f'INVALID_ROWS={sum(errors.values())}')
print(f'DUPLICATE_SKUS={duplicate_skus}')
print(f'PREVIEW_ROWS={len(preview)}')
print(f'CANDIDATE_GATE_RC={candidate_gate_rc}')
PY
DRY_RUN_RC=$?

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish CPS MySQL contract dry run" \
  "$REPORT" \
  > logs/cps_mysql_contract_dry_run_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "DRY_RUN_RC=$DRY_RUN_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
