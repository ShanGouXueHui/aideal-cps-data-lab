#!/usr/bin/env bash
# Export the canonical AIdeal CPS product feed v1 for CPS read-only consumption.
# It does not connect to MySQL, does not write CPS DB, and does not start collectors.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"
mkdir -p logs reports exports/aideal-cps-product-feed/v1

CANDIDATE="data/export/aideal_cps_products_commercial_candidate_latest.jsonl"
SOURCE_A="data/import/hz_jd_union_all_product_full_links_latest.jsonl"
OUT_DIR="exports/aideal-cps-product-feed/v1"
LATEST="$OUT_DIR/latest.jsonl"
SCHEMA="$OUT_DIR/schema.json"
MANIFEST="$OUT_DIR/manifest_latest.json"
QUALITY="$OUT_DIR/quality_latest.json"
SAMPLES="$OUT_DIR/samples_10_latest.json"
REPORT="reports/cps_product_feed_v1_contract_latest.json"

python3 - "$CANDIDATE" "$SOURCE_A" "$LATEST" "$SCHEMA" "$MANIFEST" "$QUALITY" "$SAMPLES" "$REPORT" <<'PY'
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from aideal_cps_data_lab.domain.commission_product import CommissionProduct, ProductValidationError
from aideal_cps_data_lab.hz24.repository import read_jsonl

candidate_path=Path(sys.argv[1])
source_path=Path(sys.argv[2])
latest_path=Path(sys.argv[3])
schema_path=Path(sys.argv[4])
manifest_path=Path(sys.argv[5])
quality_path=Path(sys.argv[6])
samples_path=Path(sys.argv[7])
report_path=Path(sys.argv[8])

generated_at=datetime.utcnow().isoformat(timespec='seconds')+'Z'
contract_version='aideal-cps-product-feed/v1'
fields=[
 'schema_version','source','jd_sku_id','sku','title','description','image_url','item_url','price','original_price','final_price','coupon_price','coupon_after_price','currency',
 'commission_rate','plus_commission_rate','estimated_commission','sales_volume','thirty_day_order_count','thirty_day_paid_commission',
 'category_name','category_id','category_path','brand_name','shop_name','shop_id','is_jd_self_operated','shop_avg_commission_rate','shop_category_name',
 'promotion_url','short_url','long_url','qr_url','jd_command','link_created_at','link_expire_at','link_valid_days','link_validated_at','refresh_due_at',
 'promotion_host_verified','stock_state','availability_status','source_round_id','source_run_id','source_page_no','source_rank','source_position','source_updated_at',
 'source_payload_hash','status','data_quality_flags','quarantine_reason'
]

requested_sample_fields=[
 'jd_sku_id','title','image_url','item_url','price','final_price','coupon_price','commission_rate','plus_commission_rate','estimated_commission','sales_volume',
 'thirty_day_order_count','thirty_day_paid_commission','category_name','category_id','category_path','brand_name','shop_name','shop_id','is_jd_self_operated',
 'promotion_url','short_url','long_url','qr_url','jd_command','link_created_at','link_expire_at','refresh_due_at','source_round_id','source_run_id','source_page_no',
 'source_updated_at','source_payload_hash','status','data_quality_flags'
]

def first_value(*values):
    for value in values:
        if value not in (None, ''):
            return value
    return None

def parse_dt(value):
    if not value:
        return None
    text=str(value).strip().replace('Z','+00:00')
    for fmt in (None,):
        try:
            return datetime.fromisoformat(text)
        except Exception:
            pass
    for pattern in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d'):
        try:
            return datetime.strptime(str(value).strip(), pattern)
        except Exception:
            pass
    return None

def link_days(created, expires, raw_days=None):
    if raw_days not in (None, ''):
        try:
            return int(float(str(raw_days).strip()))
        except Exception:
            pass
    c=parse_dt(created)
    e=parse_dt(expires)
    if c and e:
        return max(0, int(round((e-c).total_seconds()/86400)))
    return None

def is_u_jd(url):
    try:
        p=urlparse(str(url or '').strip())
        return p.scheme == 'https' and p.hostname == 'u.jd.com'
    except Exception:
        return False

def non_empty(row, key):
    return row.get(key) not in (None, '')

source_rows=read_jsonl(source_path)
source_by_sku={}
for row in source_rows:
    sku=str(row.get('sku') or row.get('jd_sku_id') or '').strip()
    if sku:
        source_by_sku[sku]=row

candidate_rows=read_jsonl(candidate_path)
export_rows=[]
valid_products=0
invalid_rows=0
for rank,row in enumerate(candidate_rows, start=1):
    sku=str(row.get('jd_sku_id') or row.get('sku') or '').strip()
    src=source_by_sku.get(sku) or {}
    try:
        CommissionProduct.from_candidate_row(row)
        valid_products += 1
    except ProductValidationError:
        invalid_rows += 1
    promotion_url=first_value(row.get('promotion_url'), row.get('short_url'))
    flags=[]
    unsupported=[
        'brand_name','shop_id','category_id','category_path','is_jd_self_operated','plus_commission_rate','original_price','final_price','coupon_after_price',
        'thirty_day_order_count','thirty_day_paid_commission','shop_avg_commission_rate','shop_category_name','stock_state'
    ]
    for key in unsupported:
        if first_value(row.get(key), src.get(key)) is None:
            flags.append(f'{key}_not_available')
    if not is_u_jd(promotion_url):
        flags.append('promotion_url_host_not_verified')
    if not row.get('link_expire_at'):
        flags.append('link_expire_at_missing')
    if not row.get('price'):
        flags.append('price_missing')
    out={
        'schema_version':contract_version,
        'source':'jd_union_datalab',
        'jd_sku_id':sku,
        'sku':sku,
        'title':row.get('title'),
        'description':row.get('description'),
        'image_url':row.get('image_url'),
        'item_url':row.get('item_url'),
        'price':row.get('price'),
        'original_price':first_value(row.get('original_price'), src.get('original_price')),
        'final_price':first_value(row.get('final_price'), src.get('final_price')),
        'coupon_price':row.get('coupon_price'),
        'coupon_after_price':first_value(row.get('coupon_after_price'), src.get('coupon_after_price')),
        'currency':'CNY',
        'commission_rate':row.get('commission_rate'),
        'plus_commission_rate':first_value(row.get('plus_commission_rate'), src.get('plus_commission_rate')),
        'estimated_commission':row.get('estimated_commission') or row.get('estimated_income'),
        'sales_volume':row.get('sales_volume'),
        'thirty_day_order_count':first_value(row.get('thirty_day_order_count'), src.get('thirty_day_order_count'), src.get('thirty_day_orders')),
        'thirty_day_paid_commission':first_value(row.get('thirty_day_paid_commission'), src.get('thirty_day_paid_commission')),
        'category_name':row.get('category_name'),
        'category_id':first_value(row.get('category_id'), src.get('category_id')),
        'category_path':first_value(row.get('category_path'), src.get('category_path')),
        'brand_name':first_value(row.get('brand_name'), src.get('brand_name'), src.get('brand')),
        'shop_name':row.get('shop_name'),
        'shop_id':first_value(row.get('shop_id'), src.get('shop_id')),
        'is_jd_self_operated':first_value(row.get('is_jd_self_operated'), src.get('is_jd_self_operated')),
        'shop_avg_commission_rate':first_value(row.get('shop_avg_commission_rate'), src.get('shop_avg_commission_rate')),
        'shop_category_name':first_value(row.get('shop_category_name'), src.get('shop_category_name')),
        'promotion_url':promotion_url,
        'short_url':row.get('short_url'),
        'long_url':row.get('long_url'),
        'qr_url':row.get('qr_url'),
        'jd_command':row.get('jd_command'),
        'link_created_at':row.get('link_created_at'),
        'link_expire_at':row.get('link_expire_at'),
        'link_valid_days':link_days(row.get('link_created_at'), row.get('link_expire_at'), src.get('link_expire_days')),
        'link_validated_at':row.get('source_updated_at') or row.get('last_checked_at') or src.get('ts'),
        'refresh_due_at':row.get('refresh_due_at'),
        'promotion_host_verified':is_u_jd(promotion_url),
        'stock_state':first_value(row.get('stock_state'), src.get('stock_state')),
        'availability_status':row.get('status') or 'active',
        'source_round_id':row.get('source_round_id'),
        'source_run_id':row.get('source_run_id'),
        'source_page_no':row.get('source_page_no'),
        'source_rank':rank,
        'source_position':first_value(row.get('source_position'), src.get('page_order')),
        'source_updated_at':row.get('source_updated_at') or src.get('ts'),
        'source_payload_hash':row.get('source_payload_hash'),
        'status':row.get('status'),
        'data_quality_flags':flags,
        'quarantine_reason':row.get('quarantine_reason'),
    }
    export_rows.append({k:out.get(k) for k in fields})

latest_path.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in export_rows), encoding='utf-8')
raw=latest_path.read_bytes()
sha=hashlib.sha256(raw).hexdigest()

total=len(export_rows)
skus=[r.get('jd_sku_id') for r in export_rows if r.get('jd_sku_id')]
distinct=len(set(skus))

def count_non_empty(key):
    return sum(1 for r in export_rows if non_empty(r,key))

def rate(key):
    return round(count_non_empty(key)/total, 6) if total else 0

quality={
    'schema_version':'aideal-cps-product-feed-quality/v1',
    'generated_at':generated_at,
    'total_rows':total,
    'distinct_sku_count':distinct,
    'duplicate_sku_rows':total-distinct,
    'valid_products':valid_products,
    'invalid_rows':invalid_rows,
    'promotion_url_non_empty_count':count_non_empty('promotion_url'),
    'promotion_url_u_jd_host_count':sum(1 for r in export_rows if is_u_jd(r.get('promotion_url'))),
    'short_url_non_empty_count':count_non_empty('short_url'),
    'price_non_empty_rate':rate('price'),
    'commission_rate_non_empty_rate':rate('commission_rate'),
    'estimated_commission_non_empty_rate':rate('estimated_commission'),
    'image_url_non_empty_rate':rate('image_url'),
    'link_expire_at_non_empty_rate':rate('link_expire_at'),
    'source_payload_hash_non_empty_rate':rate('source_payload_hash'),
}

field_status={
 'stable_now':['jd_sku_id','sku','title','image_url','item_url','price','currency','commission_rate','estimated_commission','category_name','shop_name','promotion_url','short_url','long_url','qr_url','jd_command','link_created_at','link_expire_at','link_valid_days','link_validated_at','refresh_due_at','promotion_host_verified','availability_status','source_round_id','source_run_id','source_page_no','source_rank','source_position','source_updated_at','source_payload_hash','status','data_quality_flags'],
 'optional_may_be_empty':['description','coupon_price','sales_volume','coupon_info','quarantine_reason'],
 'not_stably_available_now':['brand_name','shop_id','category_id','category_path','is_jd_self_operated','plus_commission_rate','original_price','final_price','coupon_after_price','thirty_day_order_count','thirty_day_paid_commission','shop_avg_commission_rate','shop_category_name','stock_state'],
}

schema={
    'schema_version':'aideal-cps-product-feed-schema/v1',
    'contract_version':contract_version,
    'full_file_paths':{
        'latest_jsonl':'/home/cpsdata/projects/aideal-cps-data-lab/exports/aideal-cps-product-feed/v1/latest.jsonl',
        'schema_json':'/home/cpsdata/projects/aideal-cps-data-lab/exports/aideal-cps-product-feed/v1/schema.json',
        'manifest_json':'/home/cpsdata/projects/aideal-cps-data-lab/exports/aideal-cps-product-feed/v1/manifest_latest.json',
    },
    'db_contract_target':{
        'database':'aideal_cps_data_lab',
        'table_or_view':'cps_jd_union_products',
        'full_path':'aideal_cps_data_lab.cps_jd_union_products',
        'status':'not_materialized_by_data_lab_export_script; use file feed unless CPS creates/validates this view',
    },
    'fields':fields,
    'field_status':field_status,
    'field_semantics':{
        'price':'JD Union/catalog captured display price. It is not guaranteed to be final price or coupon-after price.',
        'coupon_price':'Optional source coupon price field when present. Do not assume price - coupon_price relationship unless source explicitly confirms.',
        'commission_rate':'Percentage number. 20.00 means 20%.',
        'estimated_commission':'Platform total estimated commission for the product/link, not user cashback amount.',
        'plus_commission_rate':'Not stably provided in current feed; remains null unless source provides it.',
        'promotion_url':'Validated promotion short link. Candidate gate requires https://u.jd.com/ host.',
        'link_expire_at':'Promotion link expiry timestamp if collected from JD Union. Link validity days derive from link_created_at/link_expire_at or source link_expire_days.',
        'availability_status':'Feed eligibility/status, not real-time stock.',
        'stock_state':'Not stably provided by current page/network source.',
    },
}

manifest={
    'schema_version':'aideal-cps-product-feed-manifest/v1',
    'contract_version':contract_version,
    'generated_at':generated_at,
    'latest_jsonl':'/home/cpsdata/projects/aideal-cps-data-lab/exports/aideal-cps-product-feed/v1/latest.jsonl',
    'schema_json':'/home/cpsdata/projects/aideal-cps-data-lab/exports/aideal-cps-product-feed/v1/schema.json',
    'quality_json':'/home/cpsdata/projects/aideal-cps-data-lab/exports/aideal-cps-product-feed/v1/quality_latest.json',
    'samples_json':'/home/cpsdata/projects/aideal-cps-data-lab/exports/aideal-cps-product-feed/v1/samples_10_latest.json',
    'row_count':total,
    'distinct_sku_count':distinct,
    'duplicate_sku_rows':total-distinct,
    'data_sha256':sha,
    'commercial_ready':True,
    'commercial_enabled':False,
    'feed_status':'candidate',
    'idempotency_key':'jd_sku_id + source_payload_hash',
}

samples=[{k:r.get(k) for k in requested_sample_fields} for r in export_rows[:10]]
quality_path.write_text(json.dumps(quality,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
schema_path.write_text(json.dumps(schema,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
samples_path.write_text(json.dumps(samples,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
report={
    'schema_version':'cps-product-feed-v1-contract-report/v1',
    'generated_at':generated_at,
    'db_full_path':'aideal_cps_data_lab.cps_jd_union_products',
    'db_status':'not currently materialized/verified by Data Lab; file feed is canonical fallback',
    'file_feed_full_path':manifest['latest_jsonl'],
    'schema_full_path':manifest['schema_json'],
    'manifest_full_path':manifest['latest_jsonl'].replace('latest.jsonl','manifest_latest.json'),
    'quality':quality,
    'samples':samples,
    'field_status':field_status,
    'field_semantics':schema['field_semantics'],
    'final_conclusion':{
        'cps_v1_readonly_consumption':'yes_via_file_feed',
        'cps_recommendation_ranking':'basic_only; missing brand/category_id/shop_id/plus/order/stock fields for advanced ranking',
        'must_add_fields':['none for v1 read-only display/import if CPS accepts file feed'],
        'recommended_add_fields':['brand_name','shop_id','category_id','category_path','is_jd_self_operated','plus_commission_rate','final_price','coupon_after_price','thirty_day_order_count','thirty_day_paid_commission','stock_state'],
        'not_stably_available_fields':field_status['not_stably_available_now'],
        'refresh_frequency':'manual/on-demand after HZ23 candidate pipeline; recommended daily or before CPS import',
        'idempotency_rule':'upsert by jd_sku_id; skip/no-op when source_payload_hash unchanged',
        'short_link_validity_rule':'use link_expire_at if non-empty; refresh before refresh_due_at; current JD Union link validity is represented by collected link_expire_at/link_valid_days, not hard-coded by CPS',
    },
}
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')

print('===== CPS PRODUCT FEED V1 CONTRACT =====')
print('DB_FULL_PATH=aideal_cps_data_lab.cps_jd_union_products')
print('DB_STATUS=not_materialized_or_verified_by_data_lab_export_script')
print(f'FILE_FEED_FULL_PATH={manifest["latest_jsonl"]}')
print(f'SCHEMA_FULL_PATH={manifest["schema_json"]}')
print(f'MANIFEST_FULL_PATH={manifest["latest_jsonl"].replace("latest.jsonl","manifest_latest.json")}')
print(f'CONTRACT_VERSION={contract_version}')
print('===== QUALITY STATS =====')
for key in ['total_rows','distinct_sku_count','duplicate_sku_rows','valid_products','promotion_url_non_empty_count','promotion_url_u_jd_host_count','short_url_non_empty_count','price_non_empty_rate','commission_rate_non_empty_rate','estimated_commission_non_empty_rate','image_url_non_empty_rate','link_expire_at_non_empty_rate','source_payload_hash_non_empty_rate']:
    print(f'{key}={quality[key]}')
print('===== FIELD SUPPORT =====')
print('STABLE_NOW=' + ','.join(field_status['stable_now']))
print('NOT_STABLY_AVAILABLE_NOW=' + ','.join(field_status['not_stably_available_now']))
print('===== FINAL CONCLUSION =====')
fc=report['final_conclusion']
print(f'是否满足 CPS v1 只读消费={fc["cps_v1_readonly_consumption"]}')
print(f'是否满足 CPS 推荐排序={fc["cps_recommendation_ranking"]}')
print('必须补充字段=' + ','.join(fc['must_add_fields']))
print('建议补充字段=' + ','.join(fc['recommended_add_fields']))
print('不能稳定提供的字段=' + ','.join(fc['not_stably_available_fields']))
print(f'刷新频率={fc["refresh_frequency"]}')
print(f'幂等规则={fc["idempotency_rule"]}')
print(f'短链有效期规则={fc["short_link_validity_rule"]}')
print('===== SAMPLE_10_JSON =====')
print(json.dumps(samples,ensure_ascii=False,indent=2,sort_keys=True))
PY
EXPORT_RC=$?

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish CPS product feed v1 contract" \
  "$REPORT" "$SCHEMA" "$MANIFEST" "$QUALITY" "$SAMPLES" \
  > logs/cps_product_feed_v1_contract_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "EXPORT_RC=$EXPORT_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
