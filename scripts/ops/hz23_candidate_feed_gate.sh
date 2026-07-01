#!/usr/bin/env bash
# HZ23 candidate feed generation and validation gate.
# Does not access browser, JD, HZ24 collector, MySQL, or AIdeal CPS.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"
mkdir -p logs reports run data/import data/export data/state

ROUND_ID="${HZ23_ROUND_ID:-hz23_obs_20260624_093503}"
ROUND_SUMMARY="reports/hz23_round_${ROUND_ID}_latest.json"
CANDIDATE="data/export/aideal_cps_products_commercial_candidate_latest.jsonl"
MANIFEST="data/export/aideal_cps_products_commercial_candidate_manifest.json"
VALIDATION="reports/hz23_candidate_feed_validation_latest.json"
GATE="reports/hz23_candidate_feed_gate_latest.json"
SOURCE_A="data/import/hz_jd_union_all_product_full_links_latest.jsonl"
SOURCE_B="data/import/hz_jd_union_product_all_full_links_latest.jsonl"

git fetch origin runtime-evidence >/dev/null 2>&1 || true
git checkout origin/runtime-evidence -- "$ROUND_SUMMARY" >/dev/null 2>&1
CHECKOUT_RC=$?

.venv-browser/bin/python run/hz23_finalize_round.py "$ROUND_ID" "$ROUND_SUMMARY" > logs/hz23_candidate_finalize.log 2>&1
FINALIZE_RC=$?

python3 - "$CANDIDATE" "$MANIFEST" "$VALIDATION" <<'PY'
import json, sys
from pathlib import Path
from aideal_cps_data_lab.application.candidate_validation import validate_candidate
candidate=Path(sys.argv[1])
manifest=Path(sys.argv[2])
out=Path(sys.argv[3])
report=validate_candidate(candidate, manifest).as_dict()
out.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n', encoding='utf-8')
print(json.dumps({'event':'HZ23_CANDIDATE_VALIDATE_DONE', **report}, ensure_ascii=False, sort_keys=True))
PY
VALIDATE_RC=$?

python3 - "$ROUND_ID" "$ROUND_SUMMARY" "$SOURCE_A" "$SOURCE_B" "$CANDIDATE" "$MANIFEST" "$VALIDATION" "$GATE" "$CHECKOUT_RC" "$FINALIZE_RC" "$VALIDATE_RC" <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path
round_id=sys.argv[1]
summary_path=Path(sys.argv[2])
source_a=Path(sys.argv[3])
source_b=Path(sys.argv[4])
candidate_path=Path(sys.argv[5])
manifest_path=Path(sys.argv[6])
validation_path=Path(sys.argv[7])
gate_path=Path(sys.argv[8])
checkout_rc=int(sys.argv[9])
finalize_rc=int(sys.argv[10])
validate_rc=int(sys.argv[11])

def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}

def count_jsonl(path):
    if not path.exists():
        return 0
    count=0
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if line.strip():
            count += 1
    return count

summary=read_json(summary_path)
manifest=read_json(manifest_path)
validation=read_json(validation_path)
source_a_count=count_jsonl(source_a)
source_b_count=count_jsonl(source_b)
candidate_count=count_jsonl(candidate_path)
selected_source=str(manifest.get('source_file') or '')

hard_failures=[]
warnings=[]
if checkout_rc != 0:
    hard_failures.append(f'summary_checkout_failed:{checkout_rc}')
if summary.get('commercial_segment_complete') is not True:
    hard_failures.append('round_not_complete')
if source_a_count == 0 and source_b_count == 0:
    hard_failures.append('source_links_missing_or_empty')
if finalize_rc not in (0, 1):
    hard_failures.append(f'finalize_failed:{finalize_rc}')
if validate_rc != 0:
    hard_failures.append(f'validation_entry_failed:{validate_rc}')
if validation.get('ok') is not True:
    hard_failures.append('candidate_validation_not_ok')
if candidate_count <= 0:
    hard_failures.append('candidate_empty')
if manifest.get('commercial_enabled') is not False:
    hard_failures.append('commercial_enabled_not_false')
if manifest.get('feed_status') != 'candidate':
    hard_failures.append('feed_status_not_candidate')
if manifest.get('round_id') != round_id:
    warnings.append('manifest_round_id_differs')
if finalize_rc == 1 and candidate_count > 0 and validation.get('ok') is True:
    warnings.append('finalize_reported_not_promoted_but_candidate_valid')

payload={
  'schema_version':'hz23-candidate-feed-gate/v1',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'round_id':round_id,
  'gate_pass':not hard_failures,
  'hard_failures':hard_failures,
  'warnings':warnings,
  'rc':{'checkout':checkout_rc,'finalize':finalize_rc,'validate':validate_rc},
  'sources':{
    'source_a':str(source_a),'source_a_rows':source_a_count,
    'source_b':str(source_b),'source_b_rows':source_b_count,
    'manifest_source_file':selected_source,
  },
  'candidate':{
    'path':str(candidate_path),
    'rows':candidate_count,
    'manifest_path':str(manifest_path),
    'manifest_row_count':manifest.get('row_count'),
    'eligible_sku_count':manifest.get('eligible_sku_count'),
    'duplicate_sku_count':manifest.get('duplicate_sku_count'),
    'data_sha256':manifest.get('data_sha256'),
    'candidate_integrity_ready':manifest.get('candidate_integrity_ready'),
    'commercial_enabled':manifest.get('commercial_enabled'),
    'feed_status':manifest.get('feed_status'),
    'gate_failures':manifest.get('gate_failures'),
    'rejected':manifest.get('rejected'),
  },
  'validation':validation,
}
gate_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(f'CANDIDATE_GATE_REPORT={gate_path}')
print(f'CANDIDATE_GATE_PASS={payload["gate_pass"]}')
print(f'HARD_FAILURES={",".join(hard_failures) if hard_failures else "none"}')
print(f'WARNINGS={",".join(warnings) if warnings else "none"}')
print(f'SOURCE_A_ROWS={source_a_count}')
print(f'SOURCE_B_ROWS={source_b_count}')
print(f'MANIFEST_SOURCE_FILE={selected_source}')
print(f'CANDIDATE_ROWS={candidate_count}')
print(f'MANIFEST_ROW_COUNT={manifest.get("row_count")}')
print(f'ELIGIBLE_SKU_COUNT={manifest.get("eligible_sku_count")}')
print(f'DUPLICATE_SKU_COUNT={manifest.get("duplicate_sku_count")}')
print(f'CANDIDATE_INTEGRITY_READY={manifest.get("candidate_integrity_ready")}')
print(f'COMMERCIAL_ENABLED={manifest.get("commercial_enabled")}')
print(f'FEED_STATUS={manifest.get("feed_status")}')
print(f'MANIFEST_GATE_FAILURES={manifest.get("gate_failures")}')
print(f'VALIDATION_OK={validation.get("ok")}')
print(f'VALIDATION_ERRORS={validation.get("errors")}')
PY
GATE_RC=$?

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish HZ23 candidate feed gate" \
  "$VALIDATION" "$GATE" "$MANIFEST" \
  > logs/hz23_candidate_feed_gate_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "CHECKOUT_RC=$CHECKOUT_RC"
echo "FINALIZE_RC=$FINALIZE_RC"
echo "VALIDATE_RC=$VALIDATE_RC"
echo "GATE_RC=$GATE_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
