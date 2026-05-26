#!/usr/bin/env bash
# HZ15 no-reset v6 latest-segment progress checker.
# Fixes older checker that only matched 11_20 logs.
# Scope: JD Union 商品推广 / 全部商品 only.
# No exit and no set -e are used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  mkdir -p reports docs/ops logs run data/import backups

  LATEST_LOG="$(find logs -maxdepth 1 -type f -name 'hz15_jump_pages_resume_*_no_reset_v6_strict_4000_*.log' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2- || true)"
  REPORT_JSON="reports/hz15_no_reset_v6_latest_segment_progress_latest.json"
  REPORT_MD="docs/ops/DL2_HZ15_NO_RESET_V6_LATEST_SEGMENT_PROGRESS.md"

  echo "===== HZ15 no-reset v6 latest-segment progress check ====="
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
names={
 'HZ15_NO_RESET_V6_STRICT_4000_START','HZ14_V4_BOOTSTRAP_MERGE',
 'STRICT_4000_CURRENT_LIST_OK','STRICT_4000_CURRENT_LIST_NOT_USABLE',
 'PRODUCT_ALL_4000_READY','PAGE_JUMP_SLEEP','PAGE_JUMP','PAGE_CANDIDATES',
 'ITEM_OK','ITEM_FAIL','ITEM_SKIP','STOP_REQUIRED','CYCLE_DONE','TARGET_TOTAL_REACHED'
}
interesting=[e for e in events if e.get('event') in names]
rows=[]
p=Path('data/import/hz_jd_union_all_product_full_links_latest.jsonl')
if p.exists():
    target=p.resolve() if p.is_symlink() else p
    for line in target.read_text(encoding='utf-8', errors='ignore').splitlines():
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
 'title':sum(1 for x in ok if not x.get('title')),
 'image_url':sum(1 for x in ok if not x.get('image_url')),
 'item_url':sum(1 for x in ok if not x.get('item_url')),
 'price':sum(1 for x in ok if not x.get('price')),
 'commission_rate':sum(1 for x in ok if not x.get('commission_rate')),
 'estimated_income':sum(1 for x in ok if not x.get('estimated_income')),
 'short_url':sum(1 for x in ok if not x.get('short_url')),
 'long_url':sum(1 for x in ok if not x.get('long_url')),
 'qr_url':sum(1 for x in ok if not x.get('qr_url')),
 'jd_command':sum(1 for x in ok if not x.get('jd_command')),
 'refresh_due_at':sum(1 for x in ok if not x.get('refresh_due_at')),
}
proc=subprocess.run(['pgrep','-af','hz15_jump_pages_collector|hz14_all_product_full_collector'], text=True, capture_output=True)
processes=[x for x in proc.stdout.splitlines() if x.strip()]
stop_path=Path('run/hz14_STOP_REQUIRED.json')
stop=None
if stop_path.exists():
    try:
        stop=json.loads(stop_path.read_text(encoding='utf-8', errors='ignore'))
    except Exception as e:
        stop={'read_error':repr(e)}
page_jumps=[e for e in interesting if e.get('event')=='PAGE_JUMP']
item_ok=[e for e in interesting if e.get('event')=='ITEM_OK']
cycle_done=[e for e in interesting if e.get('event')=='CYCLE_DONE']
last_page_jump=page_jumps[-1] if page_jumps else None
last_item_ok=item_ok[-1] if item_ok else None
report={
 'ts':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
 'phase':'HZ15 no-reset v6 latest-segment progress check',
 'latest_log':str(log_path) if log_path else '',
 'process_alive':any('hz15_jump_pages_collector' in x for x in processes),
 'processes':processes[:20],
 'stop_exists':stop_path.exists(),
 'stop':stop,
 'counts':{'rows':len(rows),'ok':len(ok),'dedup_sku':len(dedup),'non_numeric':sum(1 for x in ok if not str(x.get('sku') or '').isdigit()),'duplicate_ok_rows':len(ok)-len(dedup),'page_count':len(pages),'first_page':pages[0] if pages else None,'last_page':pages[-1] if pages else None,'target_total':4000,'progress_pct':round(len(dedup)/4000*100,2)},
 'missing':missing,
 'event_count':len(events),
 'interesting_event_count':len(interesting),
 'last_page_jump':last_page_jump,
 'last_item_ok':last_item_ok,
 'cycle_done_tail':cycle_done[-3:],
 'interesting_events_tail':interesting[-180:],
 'plain_tail_80':lines[-80:],
 'decision':'For latest segment, continue if process_alive=true and stop=false. If CYCLE_DONE appears, start next 10-page segment. If latest_log is not current segment, inspect find/sort output.'
}
Path('$REPORT_JSON').write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
Path('$REPORT_MD').write_text('# HZ15 No-Reset V6 Latest-Segment Progress\n\n' + f"- Generated at: {report['ts']}\n- latest_log: {report['latest_log']}\n- process_alive: {report['process_alive']}\n- stop_exists: {report['stop_exists']}\n- counts: {report['counts']}\n- missing: {missing}\n- event_count: {report['event_count']}\n- interesting_event_count: {report['interesting_event_count']}\n- last_page_jump: {last_page_jump}\n- last_item_ok: {last_item_ok}\n- cycle_done_tail: {cycle_done[-3:]}\n", encoding='utf-8')
print(json.dumps({'report':'$REPORT_JSON','latest_log':str(log_path) if log_path else '', 'process_alive':report['process_alive'], 'stop_exists':report['stop_exists'], 'counts':report['counts'], 'last_page_jump':last_page_jump, 'last_item_ok':last_item_ok, 'cycle_done_count':len(cycle_done)}, ensure_ascii=False, indent=2))
PY

  git add "$REPORT_JSON" "$REPORT_MD"
  git commit -m "docs: add HZ15 v6 latest-segment progress report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "REPORT=$REPORT_JSON"
  echo "LATEST_LOG=$LATEST_LOG"
  git status --short | head -n 60
fi
