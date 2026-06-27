#!/usr/bin/env bash
# Rolling latest progress publisher for HZ23 formal supervisor.
# Publishes compact latest-only JSON to runtime-evidence while a resume run is active.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run

ROUND_ID="${HZ23_ROUND_ID:-hz23_obs_20260624_093503}"
RUN_LOG="${HZ23_PROGRESS_RUN_LOG:-}"
TARGET_PID="${HZ23_PROGRESS_TARGET_PID:-}"
INTERVAL="${HZ23_PROGRESS_PUBLISH_INTERVAL_SECONDS:-300}"
REPORT="reports/hz23_formal_progress_latest.json"
SUMMARY="reports/hz23_round_${ROUND_ID}_latest.json"
LOG="logs/hz23_formal_progress_publisher.log"

write_progress() {
  python3 - "$ROUND_ID" "$RUN_LOG" "$TARGET_PID" "$REPORT" "$SUMMARY" <<'PY'
import json, os, sys
from datetime import datetime
from pathlib import Path
round_id=sys.argv[1]
run_log=Path(sys.argv[2]) if sys.argv[2] else None
target_pid=sys.argv[3]
report=Path(sys.argv[4])
summary_path=Path(sys.argv[5])
summary={}
if summary_path.exists():
    try: summary=json.loads(summary_path.read_text(encoding='utf-8'))
    except Exception as exc: summary={'parse_error':repr(exc)}
log_tail=[]
if run_log and run_log.exists():
    log_tail=run_log.read_text(encoding='utf-8', errors='replace').splitlines()[-120:]
completed=summary.get('completed_pages') or []
unfinished=summary.get('unfinished_pages') or []
payload={
  'schema_version':'hz23-formal-progress/v1',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'round_id':round_id,
  'target_pid':int(target_pid) if str(target_pid).isdigit() else target_pid,
  'target_alive': bool(str(target_pid).isdigit() and os.path.exists(f'/proc/{target_pid}')),
  'summary_path':str(summary_path),
  'run_log':str(run_log) if run_log else None,
  'summary_digest':{
    'commercial_segment_complete':summary.get('commercial_segment_complete'),
    'stop_page':summary.get('stop_page'),
    'stop_reason':summary.get('stop_reason'),
    'scanned_total':summary.get('scanned_total'),
    'catalog_new':summary.get('catalog_new'),
    'catalog_changed':summary.get('catalog_changed'),
    'catalog_unchanged':summary.get('catalog_unchanged'),
    'completed_count':len(completed),
    'last_completed_page':max(completed) if completed else None,
    'unfinished_first_10':unfinished[:10],
  },
  'log_tail':log_tail,
}
report.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
PY
}

while true; do
  write_progress
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ23 formal rolling progress" \
    "$REPORT" \
    > logs/hz23_formal_progress_publish.log 2>&1 || true
  echo "$(date '+%F %T') HZ23_PROGRESS_PUBLISHED round=$ROUND_ID target_pid=$TARGET_PID report=$REPORT" >> "$LOG"
  if [ -n "$TARGET_PID" ] && ! kill -0 "$TARGET_PID" 2>/dev/null; then
    break
  fi
  sleep "$INTERVAL"
done
