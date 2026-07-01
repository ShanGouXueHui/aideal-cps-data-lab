#!/usr/bin/env bash
# One-command commercial candidate pipeline gate.
# Runs candidate feed gate, runtime diagnostics, and commercial readiness gate.
# Does not start browser/JD collection, HZ24, MySQL, or downstream AIdeal CPS sync.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run data/import data/export data/state

PIPELINE_LOG="logs/commercial_candidate_pipeline.log"
: > "$PIPELINE_LOG"

echo "===== COMMERCIAL CANDIDATE PIPELINE =====" | tee -a "$PIPELINE_LOG"
echo "STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$PIPELINE_LOG"

git fetch origin main runtime-evidence >> "$PIPELINE_LOG" 2>&1
git reset --hard origin/main >> "$PIPELINE_LOG" 2>&1
SYNC_RC=$?
echo "SYNC_RC=$SYNC_RC" | tee -a "$PIPELINE_LOG"
echo "MAIN_HEAD=$(git rev-parse --short HEAD 2>/dev/null)" | tee -a "$PIPELINE_LOG"

bash scripts/ops/hz23_candidate_feed_gate.sh >> "$PIPELINE_LOG" 2>&1
CANDIDATE_RC=$?
echo "CANDIDATE_PIPELINE_RC=$CANDIDATE_RC" | tee -a "$PIPELINE_LOG"

bash scripts/ops/publish_runtime_diagnostics.sh >> "$PIPELINE_LOG" 2>&1
DIAG_RC=$?
echo "DIAGNOSTICS_PIPELINE_RC=$DIAG_RC" | tee -a "$PIPELINE_LOG"

bash scripts/ops/commercial_readiness_gate.sh >> "$PIPELINE_LOG" 2>&1
READINESS_RC=$?
echo "READINESS_PIPELINE_RC=$READINESS_RC" | tee -a "$PIPELINE_LOG"

git fetch origin runtime-evidence >> "$PIPELINE_LOG" 2>&1

python3 - <<'PY' | tee -a "$PIPELINE_LOG"
import json
from pathlib import Path

def read(path):
    p=Path(path)
    if not p.exists():
        return {}
    try:
        value=json.loads(p.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

candidate=read('reports/hz23_candidate_feed_gate_latest.json')
readiness=read('reports/commercial_readiness_gate_latest.json')
diag=read('reports/runtime_diagnostics_latest.json')
source_diag=(diag.get('jsonl_sources') or {})
source_a=source_diag.get('data/import/hz_jd_union_all_product_full_links_latest.jsonl') or {}
candidate_diag=source_diag.get('data/export/aideal_cps_products_commercial_candidate_latest.jsonl') or {}

print('===== COMPACT RESULT =====')
print(f'CANDIDATE_GATE_PASS={candidate.get("gate_pass")}')
print(f'CANDIDATE_FAILURES={candidate.get("hard_failures")}')
print(f'CANDIDATE_ROWS={(candidate.get("candidate") or {}).get("rows")}')
print(f'ELIGIBLE_SKU_COUNT={(candidate.get("candidate") or {}).get("eligible_sku_count")}')
print(f'VALIDATION_OK={(candidate.get("validation") or {}).get("ok")}')
print(f'SOURCE_A_VALID={source_a.get("valid_json_objects")}')
print(f'SOURCE_A_OK={source_a.get("status_ok_rows")}')
print(f'SOURCE_A_TRUSTED={source_a.get("trusted_short_url_rows")}')
print(f'CANDIDATE_VALID={candidate_diag.get("valid_json_objects")}')
print(f'CANDIDATE_TRUSTED={candidate_diag.get("trusted_short_url_rows")}')
print(f'CONTRACT_READY={readiness.get("contract_ready")}')
print(f'COMMERCIAL_READY={readiness.get("commercial_ready")}')
print(f'CONTRACT_FAILURES={readiness.get("contract_failures")}')
print(f'SCALE_FAILURES={readiness.get("scale_failures")}')
print(f'WARNINGS={readiness.get("warnings")}')
print(f'MIN_CANDIDATE_ROWS={(readiness.get("thresholds") or {}).get("min_candidate_rows")}')
print(f'COMMERCIAL_CANDIDATE_ROWS={(readiness.get("candidate") or {}).get("rows")}')
print(f'SOURCE_ROW_MAX={(readiness.get("source") or {}).get("source_row_max")}')
print(f'TRUSTED_SOURCE_ROW_MAX={(readiness.get("source") or {}).get("trusted_source_row_max")}')
print(f'DIAGNOSTICS_GENERATED_AT={diag.get("generated_at")}')
PY
COMPACT_RC=$?

echo "PIPELINE_LOG=$PIPELINE_LOG"
echo "COMPACT_RC=$COMPACT_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
echo "FINISHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [ "$SYNC_RC" != "0" ] || [ "$CANDIDATE_RC" != "0" ] || [ "$DIAG_RC" != "0" ] || [ "$READINESS_RC" != "0" ] || [ "$COMPACT_RC" != "0" ]; then
  exit 1
fi
exit 0
