#!/usr/bin/env bash
# HZ15 no-reset v4 progress checker. No exit and no set -e are used.
PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  mkdir -p reports docs/ops logs run data/import backups
  LATEST_LOG="$(ls -t logs/hz15_jump_pages_resume_11_20_no_reset_v4_*.log logs/hz15_jump_pages_resume_11_20_no_reset_v3_*.log logs/hz15_jump_pages_resume_11_20_ultraslow_v2_*.log 2>/dev/null | head -n 1 || true)"
  REPORT_JSON="reports/hz15_no_reset_v4_progress_latest.json"
  REPORT_MD="docs/ops/DL2_HZ15_NO_RESET_V4_PROGRESS.md"
  echo "===== HZ15 no-reset v4 progress check ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "LATEST_LOG=$LATEST_LOG"
  python3 - <<PY
import json, subprocess
from pathlib import Path
from datetime import datetime
log_path = Path("$LATEST_LOG") if "$LATEST_LOG" else None
text = log_path.read_text(encoding='utf-8', errors='ignore') if log_path and log_path.exists() else ''
lines = text.splitlines()
events=[]
for line in lines:
    if line.strip().startswith('{'):
        try:
            events.append(json.loads(line))
        except Exception:
            pass
interesting_names = {
  'HZ15_NO_RESET_V4_START','HZ14_V4_BOOTSTRAP_MERGE','NO_RESET_CURRENT_LIST_OK',
  'NO_RESET_CURRENT_LIST_NOT_USABLE','PRODUCT_ALL_READY','PAGE_JUMP_SLEEP','PAGE_JUMP',
  'PAGE_CANDIDATES','ITEM_OK','ITEM_FAIL','ITEM_SKIP','STOP_REQUIRED','CYCLE_DONE'
}
interesting=[e for e in events if e.get('event') in interesting_names]
rows=[]
p=Path('data/import/hz_jd_union_all_product_full_links_latest.jsonl')
if p.exists():
    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
ok=[x for x in rows if x.get('status')=='ok' and x.get('short_url')]
dedup=sorted({str(x.get('sku') or '').strip() for x in ok if x.get('sku')})
pages=sorted({int(x.get('page_no')) for x in ok if str(x.get('page_no') or '').isdigit()})
missing={
 'title': sum(1 for x in ok if not x.get('title')),
 'image_url': sum(1 for x in ok if not x.get('image_url')),
 'short_url': sum(1 for x in ok if not x.get('short_url')),
 'price': sum(1 for x in ok if not x.get('price')),
 'commission_rate': sum(1 for x in ok if not x.get('commission_rate')),
 'estimated_income': sum(1 for x in ok if not x.get('estimated_income')),
}
proc=subprocess.run(['pgrep','-af','hz15_jump_pages_collector|hz14_all_product_full_collector'], text=True, capture_output=True)
report={
 'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
 'latest_log': str(log_path) if log_path else '',
 'process_alive': bool(proc.stdout.strip()),
 'processes': proc.stdout.splitlines()[:20],
 'counts': {'rows':len(rows),'ok':len(ok),'dedup_sku':len(dedup),'page_count':len(pages),'first_page':pages[0] if pages else None,'last_page':pages[-1] if pages else None,'progress_pct':round(len(dedup)/4000*100,2)},
 'missing': missing,
 'stop_exists': Path('run/hz14_STOP_REQUIRED.json').exists(),
 'event_count': len(events),
 'interesting_event_count': len(interesting),
 'interesting_events_tail': interesting[-120:],
 'plain_tail_80': lines[-80:],
 'decision': 'Continue if process_alive=true, stop=false, ITEM_OK grows, and PAGE_JUMP works. If exited with no events, inspect plain_tail_80.'
}
Path('$REPORT_JSON').write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
Path('$REPORT_MD').write_text('# HZ15 No-Reset V4 Progress\n\n' + f"- Generated at: {report['ts']}\n- process_alive: {report['process_alive']}\n- stop_exists: {report['stop_exists']}\n- counts: {report['counts']}\n- missing: {missing}\n- event_count: {report['event_count']}\n- interesting_event_count: {report['interesting_event_count']}\n", encoding='utf-8')
print(json.dumps({'report':'$REPORT_JSON','latest_log':str(log_path) if log_path else '', 'process_alive':report['process_alive'], 'stop_exists':report['stop_exists'], 'counts':report['counts'], 'missing':missing, 'event_count':report['event_count'], 'interesting_event_count':report['interesting_event_count']}, ensure_ascii=False, indent=2))
PY
  git add "$REPORT_JSON" "$REPORT_MD"
  git commit -m "docs: add HZ15 no-reset v4 progress report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true
  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "REPORT=$REPORT_JSON"
  echo "LATEST_LOG=$LATEST_LOG"
  git status --short | head -n 60
fi
