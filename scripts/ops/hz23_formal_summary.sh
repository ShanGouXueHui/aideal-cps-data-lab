#!/usr/bin/env bash
# Publish full HZ23 formal status details to runtime-evidence and print a compact summary.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run

ROUND_ID="${HZ23_ROUND_ID:-hz23_obs_20260624_093503}"
STATUS="reports/hz23_formal_supervisor_status_latest.json"
PROGRESS="reports/hz23_formal_progress_latest.json"
RESUME="reports/hz23_observation_resume_auto_latest.json"
SUMMARY_REPORT="reports/hz23_formal_summary_latest.json"
PID_FILE="run/hz23_formal_supervisor.pid"

python3 - "$ROUND_ID" "$STATUS" "$PROGRESS" "$RESUME" "$SUMMARY_REPORT" "$PID_FILE" <<'PY'
import json, os, sys
from datetime import datetime
from pathlib import Path
round_id=sys.argv[1]
status_path=Path(sys.argv[2])
progress_path=Path(sys.argv[3])
resume_path=Path(sys.argv[4])
summary_report=Path(sys.argv[5])
pid_file=Path(sys.argv[6])

def read_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'parse_error': repr(exc)}

status=read_json(status_path)
progress=read_json(progress_path)
resume=read_json(resume_path)
state=status.get('state') or {}
summary=status.get('summary') or {}
progress_digest=progress.get('summary_digest') or {}
completed=summary.get('completed_pages') or []
unfinished=summary.get('unfinished_pages') or []
if progress_digest:
    completed_count=progress_digest.get('completed_count')
    last_completed=progress_digest.get('last_completed_page')
    unfinished_first_10=progress_digest.get('unfinished_first_10') or []
    scanned_total=progress_digest.get('scanned_total')
    stop_page=progress_digest.get('stop_page')
    stop_reason=progress_digest.get('stop_reason')
    complete=progress_digest.get('commercial_segment_complete')
else:
    completed_count=len(completed)
    last_completed=max(completed) if completed else None
    unfinished_first_10=unfinished[:10]
    scanned_total=summary.get('scanned_total')
    stop_page=summary.get('stop_page')
    stop_reason=summary.get('stop_reason')
    complete=summary.get('commercial_segment_complete')
pid=None
alive=False
if pid_file.exists():
    txt=pid_file.read_text(encoding='utf-8', errors='replace').strip()
    if txt.isdigit():
        pid=int(txt)
        alive=os.path.exists(f'/proc/{pid}')

payload={
  'schema_version':'hz23-formal-summary/v1',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'round_id':round_id,
  'pid':pid,
  'alive':alive,
  'mode':state.get('mode'),
  'extra':state.get('extra'),
  'status_generated_at':status.get('generated_at'),
  'progress_generated_at':progress.get('generated_at'),
  'resume_generated_at':resume.get('generated_at'),
  'commercial_segment_complete':complete,
  'stop_page':stop_page,
  'stop_reason':stop_reason,
  'scanned_total':scanned_total,
  'completed_count':completed_count,
  'last_completed_page':last_completed,
  'unfinished_first_10':unfinished_first_10,
  'details':{
    'status_path':str(status_path),
    'progress_path':str(progress_path),
    'resume_path':str(resume_path),
    'status':status,
    'progress':progress,
    'resume_digest':{
      'schema_version':resume.get('schema_version'),
      'generated_at':resume.get('generated_at'),
      'round_id':resume.get('round_id'),
      'run_rc':resume.get('run_rc'),
      'status':resume.get('status'),
      'stop_page':resume.get('stop_page'),
      'stop_reason':resume.get('stop_reason'),
      'summary_path':resume.get('summary_path'),
      'log_path':resume.get('log_path'),
    }
  }
}
summary_report.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n', encoding='utf-8')
print(f"SUMMARY_REPORT={summary_report}")
print(f"PID={pid}")
print(f"ALIVE={str(alive).lower()}")
print(f"MODE={payload.get('mode')}")
print(f"EXTRA={payload.get('extra')}")
print(f"LAST_COMPLETED_PAGE={last_completed}")
print(f"COMPLETED_COUNT={completed_count}")
print(f"UNFINISHED_FIRST={unfinished_first_10[0] if unfinished_first_10 else None}")
print(f"SCANNED_TOTAL={scanned_total}")
print(f"COMPLETE={complete}")
PY

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish HZ23 formal compact summary" \
  "$SUMMARY_REPORT" "$STATUS" "$PROGRESS" "$RESUME" \
  > logs/hz23_formal_summary_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
