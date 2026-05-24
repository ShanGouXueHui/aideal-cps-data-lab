#!/usr/bin/env bash
# HZ15 resume progress checker.
# Scope: JD Union 商品推广 / 全部商品 only.
# Reads latest resume/jump-pages logs and cumulative latest JSONL.
# No exit is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  mkdir -p reports docs/ops logs run data/import backups

  LATEST_LOG="$(ls -t \
    logs/hz15_jump_pages_resume_*.log \
    logs/hz15_jump_pages_1_67_*.log \
    logs/hz14_all_product_full_v4_4000_*.log 2>/dev/null | head -n 1 || true)"
  REPORT_JSON="reports/hz15_resume_progress_latest.json"
  REPORT_MD="docs/ops/DL2_HZ15_RESUME_PROGRESS.md"

  echo "===== HZ15 resume progress check ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "LATEST_LOG=$LATEST_LOG"

  python3 - <<PY
import json
import subprocess
from pathlib import Path
from datetime import datetime

latest_log = "$LATEST_LOG"
report_json = Path("$REPORT_JSON")
report_md = Path("$REPORT_MD")
latest_path = Path("data/import/hz_jd_union_all_product_full_links_latest.jsonl")
compat_latest_path = Path("data/import/hz_jd_union_product_all_full_links_latest.jsonl")
state_path = Path("run/hz14_all_product_full_state.json")
runtime_report_path = Path("run/hz14_all_product_full_report_latest.json")
stop_path = Path("run/hz14_STOP_REQUIRED.json")

def read_json(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8', errors='ignore'))
    except Exception as e:
        return {'_read_error': repr(e), '_path': str(p)}

def read_jsonl(path):
    p = Path(path)
    rows = []
    if p.exists():
        target = p.resolve() if p.is_symlink() else p
        for line in target.read_text(encoding='utf-8', errors='ignore').splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows

def parse_dt(s):
    if not s:
        return None
    for fmt in (None, '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.fromisoformat(str(s)) if fmt is None else datetime.strptime(str(s), fmt)
        except Exception:
            pass
    return None

def pgrep(pattern):
    try:
        r = subprocess.run(['pgrep', '-af', pattern], text=True, capture_output=True)
        return [x for x in r.stdout.splitlines() if x.strip()]
    except Exception as e:
        return [f'pgrep_error:{e!r}']

def events(path, limit=560):
    p = Path(path)
    out = []
    if not path or not p.exists():
        return out
    keep = {
        'HZ15_JUMP_PAGES_START', 'HZ14_V4_BOOTSTRAP_MERGE', 'PRODUCT_ALL_RESET',
        'PAGE_JUMP', 'PAGE_JUMP_SLEEP', 'PAGE_CANDIDATES', 'ITEM_OK', 'ITEM_FAIL',
        'ITEM_SKIP', 'STOP_REQUIRED', 'TARGET_TOTAL_REACHED', 'SLEEP_TARGET_TOTAL', 'CYCLE_DONE'
    }
    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        if not line.strip().startswith('{'):
            continue
        try:
            x = json.loads(line)
        except Exception:
            continue
        if x.get('event') in keep:
            out.append(x)
    return out[-limit:]

rows = read_jsonl(latest_path)
ok = [x for x in rows if x.get('status') == 'ok' and x.get('short_url')]
skus = [str(x.get('sku') or '').strip() for x in ok if x.get('sku')]
dedup = sorted(set(skus))
non_numeric = [x for x in ok if not str(x.get('sku') or '').isdigit()]
pages = sorted({int(x.get('page_no')) for x in ok if str(x.get('page_no') or '').isdigit()})
missing = {
    'title': sum(1 for x in ok if not x.get('title')),
    'image_url': sum(1 for x in ok if not x.get('image_url')),
    'item_url': sum(1 for x in ok if not x.get('item_url')),
    'price': sum(1 for x in ok if not x.get('price')),
    'commission_rate': sum(1 for x in ok if not x.get('commission_rate')),
    'estimated_income': sum(1 for x in ok if not x.get('estimated_income')),
    'short_url': sum(1 for x in ok if not x.get('short_url')),
    'long_url': sum(1 for x in ok if not x.get('long_url')),
    'qr_url': sum(1 for x in ok if not x.get('qr_url')),
    'jd_command': sum(1 for x in ok if not x.get('jd_command')),
    'refresh_due_at': sum(1 for x in ok if not x.get('refresh_due_at')),
}
first_ts = None
last_ts = None
for x in ok:
    dt = parse_dt(x.get('link_created_at') or x.get('ts'))
    if dt:
        first_ts = dt if first_ts is None or dt < first_ts else first_ts
        last_ts = dt if last_ts is None or dt > last_ts else last_ts
runtime_hours = None
per_hour = None
eta_hours_to_4000 = None
if first_ts and last_ts and last_ts > first_ts:
    runtime_hours = max((last_ts - first_ts).total_seconds() / 3600, 1/60)
    per_hour = len(ok) / runtime_hours
    if per_hour > 0:
        eta_hours_to_4000 = max(0, (4000 - len(dedup)) / per_hour)

ev = events(latest_log)
bootstrap_events = [x for x in ev if x.get('event') == 'HZ14_V4_BOOTSTRAP_MERGE']
start_events = [x for x in ev if x.get('event') == 'HZ15_JUMP_PAGES_START']
page_jump_events = [x for x in ev if x.get('event') == 'PAGE_JUMP']
page_jump_ok = [x for x in page_jump_events if (x.get('result') or {}).get('ok')]
item_ok_events = [x for x in ev if x.get('event') == 'ITEM_OK']
item_skip_events = [x for x in ev if x.get('event') == 'ITEM_SKIP']
item_fail_events = [x for x in ev if x.get('event') == 'ITEM_FAIL']
stop_events = [x for x in ev if x.get('event') == 'STOP_REQUIRED']
processes = pgrep('hz15_jump_pages_collector|hz14_all_product_full_collector|chrome.*19228')
process_alive = any('hz15_jump_pages_collector' in p for p in processes)
report = {
    'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'phase': 'HZ15 resume cumulative progress check',
    'latest_log': latest_log,
    'process_alive': process_alive,
    'processes': processes,
    'stop_exists': stop_path.exists(),
    'stop': read_json(stop_path),
    'counts': {
        'rows': len(rows),
        'ok': len(ok),
        'dedup_sku': len(dedup),
        'non_numeric': len(non_numeric),
        'duplicate_ok_rows': len(ok) - len(dedup),
        'page_count': len(pages),
        'first_page': pages[0] if pages else None,
        'last_page': pages[-1] if pages else None,
        'target_total': 4000,
        'progress_pct': round(len(dedup) / 4000 * 100, 2),
    },
    'missing': missing,
    'bootstrap': bootstrap_events[-1] if bootstrap_events else None,
    'start': start_events[-1] if start_events else None,
    'jump': {
        'page_jump_events_tail': len(page_jump_events),
        'page_jump_ok_tail': len(page_jump_ok),
        'last_page_jump': page_jump_events[-1] if page_jump_events else None,
    },
    'failures': {
        'item_fail_events_tail': len(item_fail_events),
        'item_skip_events_tail': len(item_skip_events),
        'stop_events_tail': len(stop_events),
        'last_fail': item_fail_events[-1] if item_fail_events else None,
        'last_skip': item_skip_events[-1] if item_skip_events else None,
    },
    'throughput': {
        'first_ts': first_ts.isoformat(timespec='seconds') if first_ts else None,
        'last_ts': last_ts.isoformat(timespec='seconds') if last_ts else None,
        'runtime_hours_est': round(runtime_hours, 3) if runtime_hours else None,
        'estimated_ok_per_hour': round(per_hour, 2) if per_hour else None,
        'eta_hours_to_4000': round(eta_hours_to_4000, 2) if eta_hours_to_4000 is not None else None,
    },
    'runtime_report': read_json(runtime_report_path),
    'state': read_json(state_path),
    'events_tail': ev,
    'sample_last_20': [{'page_no': x.get('page_no'), 'sku': x.get('sku'), 'short_url': x.get('short_url'), 'title': (x.get('title') or '')[:90], 'price': x.get('price'), 'commission_rate': x.get('commission_rate'), 'estimated_income': x.get('estimated_income')} for x in ok[-20:]],
    'compat_latest_exists': compat_latest_path.exists(),
    'decision': 'Continue if process_alive=true, stop=false, jump ok, latest cumulative grows, skips do not stop the job, and missing new rows are acceptable. If risk STOP exists, verify manually and resume with slower/smaller page segment.'
}
report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
md = []
md.append('# HZ15 Resume Progress')
md.append('')
md.append(f"- Generated at: {report['ts']}")
md.append(f"- process_alive: {process_alive}")
md.append(f"- stop_exists: {report['stop_exists']}")
md.append(f"- counts: {report['counts']}")
md.append(f"- missing: {missing}")
md.append(f"- jump: {report['jump']}")
md.append(f"- failures: {report['failures']}")
md.append(f"- throughput: {report['throughput']}")
md.append('')
report_md.write_text('\n'.join(md), encoding='utf-8')
print(json.dumps({'report': str(report_json), 'process_alive': process_alive, 'stop_exists': report['stop_exists'], 'counts': report['counts'], 'missing': missing, 'jump': report['jump'], 'failures': report['failures'], 'throughput': report['throughput']}, ensure_ascii=False, indent=2))
PY

  git add "$REPORT_JSON" "$REPORT_MD"
  git commit -m "docs: add HZ15 resume progress report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "REPORT=$REPORT_JSON"
  echo "LATEST_LOG=$LATEST_LOG"
  git status --short | head -n 60
fi
