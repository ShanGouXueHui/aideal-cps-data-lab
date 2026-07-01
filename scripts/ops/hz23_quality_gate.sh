#!/usr/bin/env bash
# HZ23 observation quality gate.
# Reads runtime-evidence reports only. Does not access browser, JD, HZ24, MySQL, or AIdeal CPS.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run

ROUND_ID="${HZ23_ROUND_ID:-hz23_obs_20260624_093503}"
ROUND_PAGE_START="${HZ23_ROUND_PAGE_START:-1}"
PAGE_END="${HZ23_PAGE_END:-67}"
EXPECTED_PER_PAGE="${HZ23_EXPECTED_PER_PAGE:-60}"

ROUND_SUMMARY="reports/hz23_round_${ROUND_ID}_latest.json"
STATUS="reports/hz23_formal_supervisor_status_latest.json"
RESUME="reports/hz23_observation_resume_auto_latest.json"
FORMAL_SUMMARY="reports/hz23_formal_summary_latest.json"
GATE_REPORT="reports/hz23_quality_gate_latest.json"

git fetch origin runtime-evidence >/dev/null 2>&1 || true
git checkout origin/runtime-evidence -- "$ROUND_SUMMARY" "$STATUS" "$RESUME" "$FORMAL_SUMMARY" >/dev/null 2>&1
CHECKOUT_RC=$?

python3 - "$ROUND_ID" "$ROUND_PAGE_START" "$PAGE_END" "$EXPECTED_PER_PAGE" "$ROUND_SUMMARY" "$STATUS" "$RESUME" "$GATE_REPORT" "$CHECKOUT_RC" <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path

round_id=sys.argv[1]
page_start=int(sys.argv[2])
page_end=int(sys.argv[3])
expected_per_page=int(sys.argv[4])
round_summary_path=Path(sys.argv[5])
status_path=Path(sys.argv[6])
resume_path=Path(sys.argv[7])
gate_report_path=Path(sys.argv[8])
checkout_rc=int(sys.argv[9])
expected_pages=list(range(page_start, page_end + 1))

def read_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'parse_error': repr(exc)}

round_summary=read_json(round_summary_path)
status=read_json(status_path)
resume=read_json(resume_path)

completed_pages=sorted(int(v) for v in (round_summary.get('completed_pages') or []) if isinstance(v, int))
completed_set=set(completed_pages)
expected_set=set(expected_pages)
missing_pages=[p for p in expected_pages if p not in completed_set]
extra_pages=[p for p in completed_pages if p not in expected_set]

rows=round_summary.get('rows') or []
row_by_page={}
for row in rows:
    page=row.get('page')
    if isinstance(page, int):
        row_by_page[page]=row

missing_rows=[p for p in expected_pages if p not in row_by_page]
scanned_anomalies=[]
scan_not_ok=[]
collect_unexpected=[]
collect_unavailable_pages=[]
expected_collect_reason='hz21_collector_not_mainlined'
for page in expected_pages:
    row=row_by_page.get(page)
    if not row:
        continue
    scanned=row.get('scanned')
    if scanned != expected_per_page:
        scanned_anomalies.append({'page': page, 'scanned': scanned})
    if row.get('scan_ok') is not True or row.get('ok') is not True:
        scan_not_ok.append({'page': page, 'ok': row.get('ok'), 'scan_ok': row.get('scan_ok'), 'reason': row.get('reason')})
    if row.get('collect_unavailable') is True:
        collect_unavailable_pages.append(page)
        if row.get('reason') != expected_collect_reason:
            collect_unexpected.append({'page': page, 'reason': row.get('reason')})

scanned_sum=sum(int((row_by_page.get(p) or {}).get('scanned') or 0) for p in expected_pages)
expected_scanned_total=len(expected_pages) * expected_per_page
summary_scanned_total=round_summary.get('scanned_total')

state=status.get('state') or {}
status_summary=status.get('summary') or {}
state_mode=state.get('mode')
state_extra=state.get('extra')
resume_status=resume.get('status')
resume_rc=resume.get('run_rc')
stop_reason=round_summary.get('stop_reason') or status_summary.get('stop_reason')

final_error=[]
for value in (state_extra, stop_reason):
    text=str(value or '')
    if 'risk' in text or 'prep_entry_failed' in text:
        final_error.append(text)

hard_failures=[]
warnings=[]
if checkout_rc != 0:
    hard_failures.append(f'runtime_evidence_checkout_failed:{checkout_rc}')
if round_summary.get('commercial_segment_complete') is not True:
    hard_failures.append('commercial_segment_not_complete')
if completed_pages != expected_pages:
    hard_failures.append('completed_pages_not_exact')
if missing_rows:
    hard_failures.append('missing_rows')
if scan_not_ok:
    hard_failures.append('scan_not_ok')
if collect_unexpected:
    hard_failures.append('collect_unexpected_reason')
if state_mode != 'complete':
    hard_failures.append(f'supervisor_not_complete:{state_mode}')
if resume_status != 'complete' or resume_rc != 0:
    hard_failures.append(f'resume_not_complete:{resume_status}:{resume_rc}')
if final_error:
    hard_failures.append('final_error_marker')

if scanned_sum != expected_scanned_total or summary_scanned_total != expected_scanned_total or scanned_anomalies:
    warnings.append('scanned_total_or_page_count_not_exact')
if len(collect_unavailable_pages) == len(expected_pages):
    warnings.append('collect_unavailable_expected_until_hz21_mainlined')
elif collect_unavailable_pages:
    warnings.append('partial_collect_unavailable')

passed=not hard_failures
payload={
  'schema_version':'hz23-quality-gate/v1',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'round_id':round_id,
  'gate_pass':passed,
  'hard_failures':hard_failures,
  'warnings':warnings,
  'completion':{
    'completed_count':len(completed_pages),
    'last_completed_page':max(completed_pages) if completed_pages else None,
    'missing_pages':missing_pages,
    'extra_pages':extra_pages,
    'commercial_segment_complete':round_summary.get('commercial_segment_complete'),
  },
  'scan':{
    'expected_scanned_total':expected_scanned_total,
    'summary_scanned_total':summary_scanned_total,
    'row_scanned_sum':scanned_sum,
    'missing_rows':missing_rows,
    'scanned_anomalies':scanned_anomalies,
    'scan_not_ok':scan_not_ok,
  },
  'runtime_state':{
    'state_mode':state_mode,
    'state_extra':state_extra,
    'resume_status':resume_status,
    'resume_rc':resume_rc,
    'stop_reason':stop_reason,
    'final_error':final_error,
  },
  'collect':{
    'expected_reason':expected_collect_reason,
    'collect_unavailable_count':len(collect_unavailable_pages),
    'collect_unavailable_unexpected':collect_unexpected,
  }
}
gate_report_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n', encoding='utf-8')

print(f'GATE_REPORT={gate_report_path}')
print(f'GATE_PASS={str(passed)}')
print(f'HARD_FAILURES={",".join(hard_failures) if hard_failures else "none"}')
print(f'WARNINGS={",".join(warnings) if warnings else "none"}')
print(f'COMPLETED_COUNT={len(completed_pages)}')
print(f'MISSING_PAGES={missing_pages}')
print(f'EXPECTED_SCANNED_TOTAL={expected_scanned_total}')
print(f'SUMMARY_SCANNED_TOTAL={summary_scanned_total}')
print(f'ROW_SCANNED_SUM={scanned_sum}')
print(f'SCANNED_ANOMALIES={scanned_anomalies}')
print(f'SCAN_NOT_OK={scan_not_ok}')
print(f'FINAL_MODE={state_mode}')
print(f'RESUME_STATUS={resume_status}')
print(f'COLLECT_UNAVAILABLE_COUNT={len(collect_unavailable_pages)}')
print(f'COLLECT_UNAVAILABLE_UNEXPECTED={collect_unexpected}')
PY
GATE_RC=$?

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish HZ23 quality gate" \
  "$GATE_REPORT" \
  > logs/hz23_quality_gate_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "GATE_RC=$GATE_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
