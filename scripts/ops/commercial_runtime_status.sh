#!/usr/bin/env bash
# Compact read-only runtime status for Data Lab commercialization.
# Does not start collectors, browser jobs, MySQL jobs, or downstream sync.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run data/export

SUMMARY="reports/hz23_formal_summary_latest.json"
STATUS="reports/hz23_formal_supervisor_status_latest.json"
PROGRESS="reports/hz23_formal_progress_latest.json"
RESUME="reports/hz23_observation_resume_auto_latest.json"
QUALITY="reports/hz23_quality_gate_latest.json"
HZ21="reports/hz21_collector_readiness_latest.json"
CANDIDATE="reports/hz23_candidate_feed_gate_latest.json"

FETCH_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
git fetch origin main runtime-evidence >/dev/null 2>&1 || true
CHECKOUT_RC=0
MISSING_REPORTS=""
for f in "$SUMMARY" "$STATUS" "$PROGRESS" "$RESUME" "$QUALITY" "$HZ21" "$CANDIDATE"; do
  git checkout origin/runtime-evidence -- "$f" >/dev/null 2>&1
  RC=$?
  if [ "$RC" != "0" ]; then
    CHECKOUT_RC=1
    MISSING_REPORTS="$MISSING_REPORTS $f"
  fi
done

echo "===== AIDEAL DATA LAB RUNTIME STATUS ====="
echo "GENERATED_AT=$FETCH_TS"
echo "MAIN_HEAD=$(git rev-parse --short origin/main 2>/dev/null)"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
echo "CHECKOUT_RC=$CHECKOUT_RC"
echo "MISSING_REPORTS=${MISSING_REPORTS# }"

python3 - "$SUMMARY" "$STATUS" "$RESUME" "$QUALITY" "$HZ21" "$CANDIDATE" <<'PY'
import json, sys
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

summary=read(sys.argv[1])
status=read(sys.argv[2])
resume=read(sys.argv[3])
quality=read(sys.argv[4])
hz21=read(sys.argv[5])
candidate=read(sys.argv[6])
state=status.get('state') or {}
qscan=quality.get('scan') or {}
qcollect=quality.get('collect') or {}
hz21_values=hz21.get('values') or {}
cand_sources=candidate.get('sources') or {}
cand=candidate.get('candidate') or {}

print('===== HZ23 FORMAL =====')
print(f"HZ23_MODE={summary.get('mode') or state.get('mode')}")
print(f"HZ23_EXTRA={summary.get('extra') or state.get('extra')}")
print(f"HZ23_ALIVE={summary.get('alive')}")
print(f"HZ23_COMPLETE={summary.get('commercial_segment_complete')}")
print(f"HZ23_COMPLETED_COUNT={summary.get('completed_count')}")
print(f"HZ23_LAST_COMPLETED_PAGE={summary.get('last_completed_page')}")
print(f"HZ23_SCANNED_TOTAL={summary.get('scanned_total')}")
print(f"HZ23_RESUME_STATUS={resume.get('status')}")
print(f"HZ23_RESUME_RC={resume.get('run_rc')}")
print(f"HZ23_RESUME_LOG={resume.get('log_path')}")

print('===== QUALITY GATES =====')
print(f"HZ23_QUALITY_PASS={quality.get('gate_pass')}")
print(f"HZ23_QUALITY_FAILURES={quality.get('hard_failures')}")
print(f"HZ23_QUALITY_WARNINGS={quality.get('warnings')}")
print(f"HZ23_SCAN_ANOMALIES={qscan.get('scanned_anomalies')}")
print(f"HZ23_COLLECT_UNAVAILABLE_COUNT={qcollect.get('collect_unavailable_count')}")
print(f"HZ23_COLLECT_UNEXPECTED={qcollect.get('collect_unavailable_unexpected')}")

print('===== HZ21 COLLECTOR =====')
print(f"HZ21_READY={hz21.get('ready')}")
print(f"HZ21_FAILURES={hz21.get('hard_failures')}")
print(f"HZ21_RUNTIME_SOURCE_EXISTS={(hz21.get('checks') or {}).get('runtime_source_exists')}")
print(f"HZ21_RUNTIME_COMPILE_OK={(hz21.get('checks') or {}).get('runtime_source_py_compile_ok')}")
print(f"HZ21_RUNTIME_SHA256={hz21_values.get('runtime_source_sha256')}")
print(f"HZ21_LATEST_OK={hz21_values.get('latest_report_ok')}")
print(f"HZ21_LATEST_REASON={hz21_values.get('latest_report_reason')}")

print('===== CANDIDATE FEED =====')
print(f"CANDIDATE_GATE_PASS={candidate.get('gate_pass')}")
print(f"CANDIDATE_FAILURES={candidate.get('hard_failures')}")
print(f"CANDIDATE_WARNINGS={candidate.get('warnings')}")
print(f"CANDIDATE_SOURCE_A_ROWS={cand_sources.get('source_a_rows')}")
print(f"CANDIDATE_SOURCE_B_ROWS={cand_sources.get('source_b_rows')}")
print(f"CANDIDATE_ROWS={cand.get('rows')}")
print(f"CANDIDATE_ELIGIBLE_SKU_COUNT={cand.get('eligible_sku_count')}")
print(f"CANDIDATE_COMMERCIAL_ENABLED={cand.get('commercial_enabled')}")
print(f"CANDIDATE_FEED_STATUS={cand.get('feed_status')}")
print(f"CANDIDATE_MANIFEST_FAILURES={cand.get('gate_failures')}")
PY

echo "===== PROCESS SNAPSHOT ====="
for pattern in \
  "hz23_formal_supervisor.sh" \
  "hz23_mainline_refresh.sh" \
  "hz22_prepare_all_product_page.py" \
  "hz23_scan_current_page.py" \
  "hz21_run_strong_risk_collector.sh" \
  "hz23_candidate_feed_gate.sh"; do
  count="$(pgrep -fc "$pattern" 2>/dev/null || true)"
  echo "PROC_COUNT[$pattern]=$count"
done
ps -eo pid,ppid,stat,lstart,cmd | grep -E 'hz23_formal_supervisor|hz23_mainline_refresh|hz22_prepare_all_product_page|hz23_scan_current_page|hz21_run_strong_risk_collector|hz23_candidate_feed_gate' | grep -v grep | head -n 40 || true

echo "===== LOG PATHS ====="
echo "FORMAL_SUPERVISOR_LOG=logs/hz23_formal_supervisor.nohup.log"
echo "FORMAL_SUMMARY_PUBLISH_LOG=logs/hz23_formal_summary_publish.log"
echo "QUALITY_GATE_PUBLISH_LOG=logs/hz23_quality_gate_publish.log"
echo "HZ21_READINESS_PUBLISH_LOG=logs/hz21_collector_readiness_publish.log"
echo "CANDIDATE_FINALIZE_LOG=logs/hz23_candidate_finalize.log"
echo "CANDIDATE_GATE_PUBLISH_LOG=logs/hz23_candidate_feed_gate_publish.log"

if [ "${STATUS_TAIL:-0}" = "1" ]; then
  echo "===== TAIL formal supervisor 120 ====="
  tail -n 120 logs/hz23_formal_supervisor.nohup.log 2>/dev/null || true
  echo "===== TAIL candidate finalize 120 ====="
  tail -n 120 logs/hz23_candidate_finalize.log 2>/dev/null || true
  echo "===== TAIL candidate publish 80 ====="
  tail -n 80 logs/hz23_candidate_feed_gate_publish.log 2>/dev/null || true
fi
