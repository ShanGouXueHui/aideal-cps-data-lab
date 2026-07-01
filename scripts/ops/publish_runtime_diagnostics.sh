#!/usr/bin/env bash
# Publish bounded runtime diagnostics to runtime-evidence for remote review.
# Does not start collectors, browser jobs, MySQL jobs, or downstream sync.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"
mkdir -p logs reports run data/import data/export

REPORT="reports/runtime_diagnostics_latest.json"
TAIL_LINES="${DIAG_TAIL_LINES:-160}"

python3 - "$REPORT" "$TAIL_LINES" <<'PY'
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from aideal_cps_data_lab.hz24.repository import read_jsonl

report=Path(sys.argv[1])
tail_lines=int(sys.argv[2])

log_paths=[
  'logs/hz23_formal_supervisor.nohup.log',
  'logs/hz23_formal_summary_publish.log',
  'logs/hz23_quality_gate_publish.log',
  'logs/hz21_collector_readiness_publish.log',
  'logs/hz23_candidate_finalize.log',
  'logs/hz23_candidate_feed_gate_publish.log',
]
json_paths=[
  'reports/hz23_formal_summary_latest.json',
  'reports/hz23_quality_gate_latest.json',
  'reports/hz21_collector_readiness_latest.json',
  'reports/hz23_candidate_feed_gate_latest.json',
  'reports/hz23_candidate_feed_validation_latest.json',
  'data/export/aideal_cps_products_commercial_candidate_manifest.json',
]
source_paths=[
  'data/import/hz_jd_union_all_product_full_links_latest.jsonl',
  'data/import/hz_jd_union_product_all_full_links_latest.jsonl',
  'data/export/aideal_cps_products_commercial_candidate_latest.jsonl',
]

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def tail_text(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    text=path.read_text(encoding='utf-8', errors='replace').splitlines()
    return text[-n:]

def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'parse_error':repr(exc)}

def raw_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding='utf-8', errors='replace').splitlines() if line.strip())

def jsonl_diag(path: Path):
    out={'path':str(path),'exists':path.exists(),'bytes':0,'sha256':None,'nonblank_lines':0,'valid_json_objects':0,'status_ok_rows':0,'trusted_short_url_rows':0,'first_records':[]}
    if not path.exists():
        return out
    raw=path.read_bytes()
    out['bytes']=len(raw)
    out['sha256']=sha256_bytes(raw)
    out['nonblank_lines']=raw_line_count(path)
    rows=read_jsonl(path)
    out['valid_json_objects']=len(rows)
    for idx,value in enumerate(rows, start=1):
        if value.get('status') == 'ok':
            out['status_ok_rows'] += 1
        if urlparse(str(value.get('short_url') or '')).hostname == 'u.jd.com':
            out['trusted_short_url_rows'] += 1
        if len(out['first_records']) < 5:
            out['first_records'].append({
                'index':idx,
                'keys':sorted(value.keys())[:40],
                'sku':value.get('sku'),
                'status':value.get('status'),
                'has_short_url':bool(value.get('short_url')),
                'short_url_host':urlparse(str(value.get('short_url') or '')).hostname,
                'title_present':bool(value.get('title')),
                'price_present':bool(value.get('price')),
            })
    return out

logs={}
for p in log_paths:
    path=Path(p)
    logs[p]={'exists':path.exists(),'bytes':path.stat().st_size if path.exists() else 0,'tail':tail_text(path, tail_lines)}

json_reports={}
for p in json_paths:
    path=Path(p)
    value=read_json(path)
    json_reports[p]={'exists':path.exists(),'bytes':path.stat().st_size if path.exists() else 0,'content':value}

sources={p:jsonl_diag(Path(p)) for p in source_paths}

payload={
  'schema_version':'runtime-diagnostics/v2',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'tail_lines':tail_lines,
  'cwd':os.getcwd(),
  'logs':logs,
  'json_reports':json_reports,
  'jsonl_sources':sources,
}
report.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(f'DIAGNOSTICS_REPORT={report}')
print(f'TAIL_LINES={tail_lines}')
for p,d in sources.items():
    print(f'SOURCE_DIAG[{p}]=exists:{d["exists"]},lines:{d["nonblank_lines"]},valid:{d["valid_json_objects"]},ok:{d["status_ok_rows"]},trusted:{d["trusted_short_url_rows"]},sha:{d["sha256"]}')
for p,d in logs.items():
    print(f'LOG_DIAG[{p}]=exists:{d["exists"]},bytes:{d["bytes"]},tail_lines:{len(d["tail"])}')
PY
DIAG_RC=$?

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish runtime diagnostics" \
  "$REPORT" \
  > logs/runtime_diagnostics_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "DIAG_RC=$DIAG_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
