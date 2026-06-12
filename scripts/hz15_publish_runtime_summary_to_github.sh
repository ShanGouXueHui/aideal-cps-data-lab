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
import json, subprocess
from pathlib import Path
from datetime import datetime

REPORT_JSON = Path('reports/hz15_runtime_summary_latest.json')
REPORT_MD = Path('docs/ops/DL2_HZ15_RUNTIME_SUMMARY.md')
LATEST_DATA = Path('data/import/hz_jd_union_all_product_full_links_latest.jsonl')

collector_patterns = [
    'logs/hz15_daytime_40_67_no_reset_v6_strict_4000_*.log',
    'logs/hz15_jump_pages_resume_*_no_reset_v6_strict_4000*.log',
]
supervisor_patterns = ['logs/hz15_daytime_autostart_40_67_supervisor_*.log']
interesting_names = {
    'HZ14_V4_BOOTSTRAP_MERGE','HZ15_NO_RESET_V6_STRICT_4000_START','STRICT_4000_CURRENT_LIST_OK',
    'STRICT_4000_CURRENT_LIST_NOT_USABLE','PRODUCT_ALL_4000_READY','PAGE_JUMP_SLEEP','PAGE_JUMP',
    'TITLE_ENRICHED_CANDIDATES_V3','STRICT_TITLE_CANDIDATES','PAGE_CANDIDATES','ITEM_OK','ITEM_SKIP',
    'STOP_REQUIRED','CYCLE_DONE'
}

def latest_file(patterns):
    files=[]
    for pat in patterns:
        files.extend(Path('.').glob(pat))
    files=[p for p in files if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None

def parse_json_log(path):
    events=[]; tail=[]
    if not path or not path.exists():
        return events, tail
    lines=path.read_text(encoding='utf-8', errors='replace').splitlines()
    tail=lines[-80:]
    for line in lines:
        s=line.strip()
        if s.startswith('{'):
            try:
                obj=json.loads(s)
                if isinstance(obj, dict): events.append(obj)
            except Exception:
                pass
    return events, tail

def summarize_data(path):
    rows=ok=bad=dups=0; dedup=set(); seen=set(); pages=set()
    missing={k:0 for k in ['sku','title','price','commission_rate','estimated_income','short_url','long_url','item_url','jd_command','qr_url','image_url','refresh_due_at']}
    if not path.exists(): return {'exists': False}
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip(): continue
        rows += 1
        try: obj=json.loads(line)
        except Exception:
            bad += 1; continue
        sku=str(obj.get('sku') or obj.get('sku_id') or '').strip()
        if sku:
            if sku in seen: dups += 1
            seen.add(sku); dedup.add(sku)
        if str(obj.get('status') or obj.get('state') or 'ok').lower() in ('ok','success','') or obj.get('short_url'):
            ok += 1
        try:
            pn=obj.get('page_no') or obj.get('page')
            if pn is not None: pages.add(int(pn))
        except Exception: pass
        for k in missing:
            v=obj.get(k)
            if v is None or v == '': missing[k] += 1
    return {'exists': True,'rows': rows,'ok': ok,'dedup_sku': len(dedup),'target_total': 4000,
            'progress_pct': round(len(dedup)/4000*100,2),'first_page': min(pages) if pages else None,
            'last_page': max(pages) if pages else None,'page_count': len(pages),
            'duplicate_ok_rows': dups,'non_json_or_bad_rows': bad,'missing': missing}

def proc_lines():
    try:
        out=subprocess.check_output(['ps','-eo','pid=,args='], text=True)
        keep=[]
        for x in out.splitlines():
            if 'hz15_daytime_autostart_supervisor_40_67' in x or 'hz15_jump_pages_collector_v6_no_reset_strict_4000.py' in x or 'chrome.*19228' in x or ('chrome' in x and 'remote-debugging-port=19228' in x):
                if 'pgrep -af' not in x and 'ps -eo' not in x and 'grep' not in x:
                    keep.append(x.strip())
        return keep[:100]
    except Exception as e:
        return [f'process_check_error={e!r}']

def last(events, name):
    for e in reversed(events):
        if e.get('event') == name: return e
    return None

def tail(events, names, n=30):
    return [e for e in events if e.get('event') in names][-n:]

collector_log=latest_file(collector_patterns)
supervisor_log=latest_file(supervisor_patterns)
collector_events, collector_plain_tail=parse_json_log(collector_log)
supervisor_tail=supervisor_log.read_text(encoding='utf-8', errors='replace').splitlines()[-120:] if supervisor_log and supervisor_log.exists() else []
procs=proc_lines()
report={
    'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'phase': 'HZ15 runtime summary publisher',
    'data': summarize_data(LATEST_DATA),
    'latest_collector_log': str(collector_log) if collector_log else None,
    'latest_collector_log_mtime': datetime.fromtimestamp(collector_log.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') if collector_log else None,
    'latest_supervisor_log': str(supervisor_log) if supervisor_log else None,
    'latest_supervisor_log_mtime': datetime.fromtimestamp(supervisor_log.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') if supervisor_log else None,
    'processes': procs,
    'process_alive': any('hz15_jump_pages_collector_v6_no_reset_strict_4000.py' in x for x in procs),
    'supervisor_alive': any('hz15_daytime_autostart_supervisor_40_67' in x for x in procs),
    'stop_exists': Path('run/hz14_STOP_REQUIRED.json').exists(),
    'collector_event_count': len(collector_events),
    'interesting_events_tail': tail(collector_events, interesting_names, 30),
    'last_start': last(collector_events,'HZ15_NO_RESET_V6_STRICT_4000_START'),
    'last_ready': last(collector_events,'PRODUCT_ALL_4000_READY'),
    'last_page_jump_sleep': last(collector_events,'PAGE_JUMP_SLEEP'),
    'last_page_jump': last(collector_events,'PAGE_JUMP'),
    'last_page_candidates': last(collector_events,'PAGE_CANDIDATES'),
    'last_item_ok': last(collector_events,'ITEM_OK'),
    'last_item_skip': last(collector_events,'ITEM_SKIP'),
    'last_stop_required': last(collector_events,'STOP_REQUIRED'),
    'last_cycle_done': last(collector_events,'CYCLE_DONE'),
    'collector_plain_tail_80': collector_plain_tail,
    'supervisor_tail_120': supervisor_tail,
}
if report['stop_exists']:
    try: report['stop']=json.loads(Path('run/hz14_STOP_REQUIRED.json').read_text(encoding='utf-8'))
    except Exception as e: report['stop']={'error':repr(e)}
else:
    report['stop']=None
REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')

md=[]
md.append('# DL2 HZ15 Runtime Summary\n')
md.append(f'- ts: `{report["ts"]}`')
md.append(f'- latest_collector_log: `{report["latest_collector_log"]}`')
md.append(f'- latest_supervisor_log: `{report["latest_supervisor_log"]}`')
d=report['data']
if d.get('exists'):
    md.append(f'- dedup_sku: `{d.get("dedup_sku")}` / 4000 (`{d.get("progress_pct")}%`)')
    md.append(f'- ok: `{d.get("ok")}`, rows: `{d.get("rows")}`, page_range: `{d.get("first_page")}-{d.get("last_page")}`, page_count: `{d.get("page_count")}`')
    md.append(f'- duplicate_ok_rows: `{d.get("duplicate_ok_rows")}`, bad_rows: `{d.get("non_json_or_bad_rows")}`')
    md.append(f'- missing: `{json.dumps(d.get("missing"), ensure_ascii=False)}`')
md.append(f'- process_alive: `{report["process_alive"]}`, supervisor_alive: `{report["supervisor_alive"]}`, stop_exists: `{report["stop_exists"]}`')
for key in ['last_start','last_ready','last_page_jump_sleep','last_page_jump','last_page_candidates','last_item_ok','last_item_skip','last_stop_required','last_cycle_done']:
    md.append(f'\n## {key}\n```json\n{json.dumps(report.get(key), ensure_ascii=False, indent=2)}\n```')
md.append('\n## process tail\n```text\n'+'\n'.join(procs[-20:])+'\n```')
md.append('\n## supervisor tail\n```text\n'+'\n'.join(supervisor_tail[-40:])+'\n```')
REPORT_MD.write_text('\n'.join(md), encoding='utf-8')
print(json.dumps({'report': str(REPORT_JSON),'md': str(REPORT_MD),'dedup_sku': d.get('dedup_sku'),'progress_pct': d.get('progress_pct'),'latest_collector_log': report['latest_collector_log'],'process_alive': report['process_alive'],'supervisor_alive': report['supervisor_alive'],'stop_exists': report['stop_exists']}, ensure_ascii=False, indent=2))
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
