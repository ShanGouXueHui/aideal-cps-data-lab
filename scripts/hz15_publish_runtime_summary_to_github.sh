#!/usr/bin/env bash
# Publish compact HZ15 runtime summary to GitHub.
# Purpose: avoid pasting long logs into chat. This script reads local logs/data,
# writes compact JSON/Markdown reports, commits, rebases, and pushes to GitHub.
# It handles both daytime and resume/overnight log name patterns.
# No exit and no set -e are used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  mkdir -p reports docs/ops logs run data/import
  REPORT_JSON="reports/hz15_runtime_summary_latest.json"
  REPORT_MD="docs/ops/DL2_HZ15_RUNTIME_SUMMARY.md"

  .venv-browser/bin/python - <<'PY'
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT = Path('.')
REPORT_JSON = Path('reports/hz15_runtime_summary_latest.json')
REPORT_MD = Path('docs/ops/DL2_HZ15_RUNTIME_SUMMARY.md')
LATEST_DATA = Path('data/import/hz_jd_union_all_product_full_links_latest.jsonl')

collector_patterns = [
    'logs/hz15_daytime_40_67_no_reset_v6_strict_4000_*.log',
    'logs/hz15_jump_pages_resume_*_no_reset_v6_strict_4000*.log',
]
supervisor_patterns = [
    'logs/hz15_daytime_autostart_40_67_supervisor_*.log',
    'logs/hz15_daytime_40_67_stop_watchdog_*.log',
]

def latest_file(patterns):
    files = []
    for pat in patterns:
        files.extend(Path('.').glob(pat))
    files = [p for p in files if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)

def parse_json_log(path):
    events = []
    plain_tail = []
    if not path or not path.exists():
        return events, plain_tail
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    plain_tail = lines[-80:]
    for line in lines:
        s = line.strip()
        if not s.startswith('{'):
            continue
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                events.append(obj)
        except Exception:
            pass
    return events, plain_tail

def summarize_data(path):
    rows = 0
    ok = 0
    dedup = set()
    pages = set()
    non_numeric = 0
    duplicate_rows = 0
    seen_sku_rows = set()
    missing = {k: 0 for k in ['sku','title','price','commission_rate','estimated_income','short_url','long_url','item_url','jd_command','qr_url','image_url','refresh_due_at']}
    first_ts = None
    last_ts = None
    if not path.exists():
        return {'exists': False}
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        rows += 1
        try:
            obj = json.loads(line)
        except Exception:
            non_numeric += 1
            continue
        sku = str(obj.get('sku') or obj.get('sku_id') or '').strip()
        if sku:
            if sku in seen_sku_rows:
                duplicate_rows += 1
            seen_sku_rows.add(sku)
            dedup.add(sku)
        status = str(obj.get('status') or obj.get('state') or 'ok').lower()
        if status in ('ok', 'success', '') or obj.get('short_url'):
            ok += 1
        page_no = obj.get('page_no') or obj.get('page')
        try:
            if page_no is not None:
                pages.add(int(page_no))
        except Exception:
            pass
        for k in missing:
            v = obj.get(k)
            if v is None or v == '':
                missing[k] += 1
        ts = obj.get('ts') or obj.get('created_at') or obj.get('collected_at')
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts
    return {
        'exists': True,
        'rows': rows,
        'ok': ok,
        'dedup_sku': len(dedup),
        'target_total': 4000,
        'progress_pct': round(len(dedup) / 4000 * 100, 2),
        'first_page': min(pages) if pages else None,
        'last_page': max(pages) if pages else None,
        'page_count': len(pages),
        'duplicate_ok_rows': duplicate_rows,
        'non_json_or_bad_rows': non_numeric,
        'missing': missing,
        'first_ts': first_ts,
        'last_ts': last_ts,
    }

def proc_lines():
    try:
        out = subprocess.check_output(['bash','-lc','pgrep -af "hz15_daytime_autostart_supervisor_40_67|hz15_jump_pages_collector|chrome.*19228" | head -n 100'], text=True)
        return [x for x in out.splitlines() if x.strip()]
    except Exception as e:
        return [f'process_check_error={e!r}']

def pick_last(events, name):
    for e in reversed(events):
        if e.get('event') == name:
            return e
    return None

def pick_tail(events, names, n=30):
    return [e for e in events if e.get('event') in names][-n:]

collector_log = latest_file(collector_patterns)
supervisor_log = latest_file(supervisor_patterns)
collector_events, collector_plain_tail = parse_json_log(collector_log)
supervisor_lines = supervisor_log.read_text(encoding='utf-8', errors='replace').splitlines()[-120:] if supervisor_log and supervisor_log.exists() else []
interesting_names = {
    'HZ14_V4_BOOTSTRAP_MERGE', 'HZ15_NO_RESET_V6_STRICT_4000_START', 'STRICT_4000_CURRENT_LIST_OK',
    'STRICT_4000_CURRENT_LIST_NOT_USABLE', 'PRODUCT_ALL_4000_READY', 'PAGE_JUMP_SLEEP', 'PAGE_JUMP',
    'TITLE_ENRICHED_CANDIDATES_V3', 'STRICT_TITLE_CANDIDATES', 'PAGE_CANDIDATES', 'ITEM_OK', 'ITEM_SKIP',
    'STOP_REQUIRED', 'CYCLE_DONE'
}
report = {
    'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'phase': 'HZ15 runtime summary publisher',
    'data': summarize_data(LATEST_DATA),
    'latest_collector_log': str(collector_log) if collector_log else None,
    'latest_collector_log_mtime': datetime.fromtimestamp(collector_log.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') if collector_log else None,
    'latest_supervisor_log': str(supervisor_log) if supervisor_log else None,
    'latest_supervisor_log_mtime': datetime.fromtimestamp(supervisor_log.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') if supervisor_log else None,
    'processes': proc_lines(),
    'process_alive': any('hz15_jump_pages_collector' in x for x in proc_lines()),
    'supervisor_alive': any('hz15_daytime_autostart_supervisor_40_67' in x for x in proc_lines()),
    'stop_exists': Path('run/hz14_STOP_REQUIRED.json').exists(),
    'stop': None,
    'collector_event_count': len(collector_events),
    'interesting_events_tail': pick_tail(collector_events, interesting_names, 30),
    'last_start': pick_last(collector_events, 'HZ15_NO_RESET_V6_STRICT_4000_START'),
    'last_ready': pick_last(collector_events, 'PRODUCT_ALL_4000_READY'),
    'last_page_jump_sleep': pick_last(collector_events, 'PAGE_JUMP_SLEEP'),
    'last_page_jump': pick_last(collector_events, 'PAGE_JUMP'),
    'last_page_candidates': pick_last(collector_events, 'PAGE_CANDIDATES'),
    'last_item_ok': pick_last(collector_events, 'ITEM_OK'),
    'last_item_skip': pick_last(collector_events, 'ITEM_SKIP'),
    'last_stop_required': pick_last(collector_events, 'STOP_REQUIRED'),
    'last_cycle_done': pick_last(collector_events, 'CYCLE_DONE'),
    'collector_plain_tail_80': collector_plain_tail,
    'supervisor_tail_120': supervisor_lines,
}
if report['stop_exists']:
    try:
        report['stop'] = json.loads(Path('run/hz14_STOP_REQUIRED.json').read_text(encoding='utf-8'))
    except Exception as e:
        report['stop'] = {'error': repr(e)}
REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')

md = []
md.append('# DL2 HZ15 Runtime Summary\n')
md.append(f'- ts: `{report["ts"]}`')
md.append(f'- latest_collector_log: `{report["latest_collector_log"]}`')
md.append(f'- latest_supervisor_log: `{report["latest_supervisor_log"]}`')
data = report['data']
if data.get('exists'):
    md.append(f'- dedup_sku: `{data.get("dedup_sku")}` / 4000 (`{data.get("progress_pct")}%`)')
    md.append(f'- ok: `{data.get("ok")}`, rows: `{data.get("rows")}`, page_range: `{data.get("first_page")}-{data.get("last_page")}`, page_count: `{data.get("page_count")}`')
    md.append(f'- duplicate_ok_rows: `{data.get("duplicate_ok_rows")}`, bad_rows: `{data.get("non_json_or_bad_rows")}`')
    md.append(f'- missing: `{json.dumps(data.get("missing"), ensure_ascii=False)}`')
md.append(f'- process_alive: `{report["process_alive"]}`, supervisor_alive: `{report["supervisor_alive"]}`, stop_exists: `{report["stop_exists"]}`')
for key in ['last_start','last_ready','last_page_jump_sleep','last_page_jump','last_page_candidates','last_item_ok','last_item_skip','last_stop_required','last_cycle_done']:
    val = report.get(key)
    md.append(f'\n## {key}\n```json\n{json.dumps(val, ensure_ascii=False, indent=2)}\n```')
md.append('\n## process tail\n```text\n' + '\n'.join(report['processes'][-20:]) + '\n```')
md.append('\n## supervisor tail\n```text\n' + '\n'.join(supervisor_lines[-40:]) + '\n```')
REPORT_MD.write_text('\n'.join(md), encoding='utf-8')
print(json.dumps({
    'report': str(REPORT_JSON),
    'md': str(REPORT_MD),
    'dedup_sku': data.get('dedup_sku'),
    'progress_pct': data.get('progress_pct'),
    'latest_collector_log': report['latest_collector_log'],
    'process_alive': report['process_alive'],
    'supervisor_alive': report['supervisor_alive'],
    'stop_exists': report['stop_exists'],
}, ensure_ascii=False, indent=2))
PY
  PUBLISH_RC=$?

  git add "$REPORT_JSON" "$REPORT_MD"
  git commit -m "docs: publish HZ15 runtime summary" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "PUBLISH_RC=$PUBLISH_RC"
  echo "REPORT=$REPORT_JSON"
  echo "MD=$REPORT_MD"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
