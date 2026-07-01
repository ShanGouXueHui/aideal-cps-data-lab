#!/usr/bin/env bash
# Commercial readiness gate for Data Lab -> AIdeal CPS integration.
# Separates feed contract pass from production data-scale readiness.
# Does not start collectors, browser jobs, MySQL jobs, or downstream sync.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"
mkdir -p logs reports run data/import data/export data/state

REPORT="reports/commercial_readiness_gate_latest.json"
MIN_CANDIDATE_ROWS="${CANDIDATE_MIN_ROWS:-100}"
MIN_SOURCE_ROWS="${SOURCE_MIN_ROWS:-100}"
ROUND_ID="${HZ23_ROUND_ID:-hz23_obs_20260624_093503}"
SUMMARY="reports/hz23_formal_summary_latest.json"
QUALITY="reports/hz23_quality_gate_latest.json"
HZ21="reports/hz21_collector_readiness_latest.json"
CANDIDATE_GATE="reports/hz23_candidate_feed_gate_latest.json"
DIAG="reports/runtime_diagnostics_latest.json"
SOURCE_A="data/import/hz_jd_union_all_product_full_links_latest.jsonl"
SOURCE_B="data/import/hz_jd_union_product_all_full_links_latest.jsonl"
CANDIDATE="data/export/aideal_cps_products_commercial_candidate_latest.jsonl"

git fetch origin runtime-evidence >/dev/null 2>&1 || true
for f in "$SUMMARY" "$QUALITY" "$HZ21" "$CANDIDATE_GATE" "$DIAG"; do
  git checkout origin/runtime-evidence -- "$f" >/dev/null 2>&1 || true
done

python3 - "$REPORT" "$ROUND_ID" "$MIN_CANDIDATE_ROWS" "$MIN_SOURCE_ROWS" "$SUMMARY" "$QUALITY" "$HZ21" "$CANDIDATE_GATE" "$DIAG" "$SOURCE_A" "$SOURCE_B" "$CANDIDATE" <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from aideal_cps_data_lab.hz24.repository import read_jsonl

report=Path(sys.argv[1])
round_id=sys.argv[2]
min_candidate=int(sys.argv[3])
min_source=int(sys.argv[4])
summary_path=Path(sys.argv[5])
quality_path=Path(sys.argv[6])
hz21_path=Path(sys.argv[7])
candidate_gate_path=Path(sys.argv[8])
diag_path=Path(sys.argv[9])
source_a=Path(sys.argv[10])
source_b=Path(sys.argv[11])
candidate_path=Path(sys.argv[12])

def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}

def source_stats(path):
    rows=read_jsonl(path)
    trusted=[]
    ok=[]
    for row in rows:
        if row.get('status') == 'ok':
            ok.append(row)
        if urlparse(str(row.get('short_url') or '')).hostname == 'u.jd.com':
            trusted.append(row)
    return {
        'path':str(path),
        'exists':path.exists(),
        'rows':len(rows),
        'status_ok_rows':len(ok),
        'trusted_short_url_rows':len(trusted),
        'sample_skus':[str(row.get('sku') or '') for row in rows[:10]],
    }

summary=read_json(summary_path)
quality=read_json(quality_path)
hz21=read_json(hz21_path)
candidate_gate=read_json(candidate_gate_path)
diag=read_json(diag_path)
source_a_stats=source_stats(source_a)
source_b_stats=source_stats(source_b)
candidate_rows=read_jsonl(candidate_path)
candidate_count=len(candidate_rows)
source_row_max=max(source_a_stats['rows'], source_b_stats['rows'])
trusted_source_max=max(source_a_stats['trusted_short_url_rows'], source_b_stats['trusted_short_url_rows'])

contract_failures=[]
scale_failures=[]
warnings=[]
if summary.get('commercial_segment_complete') is not True:
    contract_failures.append('hz23_not_complete')
if quality.get('gate_pass') is not True:
    contract_failures.append('hz23_quality_not_pass')
if hz21.get('ready') is not True:
    contract_failures.append('hz21_not_ready')
if candidate_gate.get('gate_pass') is not True:
    contract_failures.append('candidate_feed_contract_not_pass')
if candidate_count <= 0:
    contract_failures.append('candidate_empty')
if source_row_max <= 0:
    contract_failures.append('source_empty')
if candidate_count < min_candidate:
    scale_failures.append('candidate_rows_below_minimum')
if trusted_source_max < min_source:
    scale_failures.append('trusted_source_rows_below_minimum')
if candidate_count == 1:
    warnings.append('single_sku_smoke_only')
if source_row_max == 1:
    warnings.append('source_link_rows_single_object_only')
if (quality.get('scan') or {}).get('scanned_anomalies'):
    warnings.append('hz23_scan_anomalies_present')

contract_ready=not contract_failures
commercial_ready=contract_ready and not scale_failures
payload={
  'schema_version':'commercial-readiness-gate/v1',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'round_id':round_id,
  'contract_ready':contract_ready,
  'commercial_ready':commercial_ready,
  'contract_failures':contract_failures,
  'scale_failures':scale_failures,
  'warnings':warnings,
  'thresholds':{
    'min_candidate_rows':min_candidate,
    'min_source_rows':min_source,
  },
  'hz23':{
    'complete':summary.get('commercial_segment_complete'),
    'completed_count':summary.get('completed_count'),
    'scanned_total':summary.get('scanned_total'),
    'quality_pass':quality.get('gate_pass'),
    'quality_warnings':quality.get('warnings'),
    'scan_anomalies':(quality.get('scan') or {}).get('scanned_anomalies'),
  },
  'hz21':{
    'ready':hz21.get('ready'),
    'hard_failures':hz21.get('hard_failures'),
  },
  'source':{
    'source_a':source_a_stats,
    'source_b':source_b_stats,
    'source_row_max':source_row_max,
    'trusted_source_row_max':trusted_source_max,
  },
  'candidate':{
    'gate_pass':candidate_gate.get('gate_pass'),
    'rows':candidate_count,
    'gate_failures':candidate_gate.get('hard_failures'),
    'validation_ok':((candidate_gate.get('validation') or {}).get('ok')),
    'sample_skus':[str(row.get('sku') or row.get('jd_sku_id') or '') for row in candidate_rows[:10]],
  },
  'diagnostics_generated_at':diag.get('generated_at'),
}
report.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(f'COMMERCIAL_READINESS_REPORT={report}')
print(f'CONTRACT_READY={contract_ready}')
print(f'COMMERCIAL_READY={commercial_ready}')
print(f'CONTRACT_FAILURES={",".join(contract_failures) if contract_failures else "none"}')
print(f'SCALE_FAILURES={",".join(scale_failures) if scale_failures else "none"}')
print(f'WARNINGS={",".join(warnings) if warnings else "none"}')
print(f'MIN_CANDIDATE_ROWS={min_candidate}')
print(f'CANDIDATE_ROWS={candidate_count}')
print(f'MIN_SOURCE_ROWS={min_source}')
print(f'SOURCE_ROW_MAX={source_row_max}')
print(f'TRUSTED_SOURCE_ROW_MAX={trusted_source_max}')
print(f'HZ23_COMPLETE={summary.get("commercial_segment_complete")}')
print(f'HZ23_QUALITY_PASS={quality.get("gate_pass")}')
print(f'HZ21_READY={hz21.get("ready")}')
print(f'CANDIDATE_GATE_PASS={candidate_gate.get("gate_pass")}')
PY
GATE_RC=$?

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish commercial readiness gate" \
  "$REPORT" \
  > logs/commercial_readiness_gate_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "GATE_RC=$GATE_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
