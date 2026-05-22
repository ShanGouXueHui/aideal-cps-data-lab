#!/usr/bin/env bash
# HZ13 multi-channel smoke runner.
# No `exit` is used because the user's shell environment may logout on exit.
# Run on collector server 121.41.111.36 as user cpsdata:
#   cd ~/projects/aideal-cps-data-lab && git fetch origin main && git rebase origin/main && bash scripts/hz13_run_multi_channel_smoke_and_report.sh

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
  echo "HINT=请在杭州采集机 121.41.111.36 的 cpsdata 用户下执行；不要在生产机 deploy 用户下执行。"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p backups logs reports docs/ops run data/import

  echo "===== HZ13 multi-channel smoke start ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop old HZ12/HZ13 worker only, keep Chrome ====="
  pkill -f "python.*run/hz12_product_all_full_collector" 2>/dev/null || true
  pkill -f "python.*run/hz13_multi_channel_collector" 2>/dev/null || true
  sleep 3

  echo "===== backup HZ13 smoke state/latest only ====="
  for f in \
    run/hz13_STOP_REQUIRED.json \
    run/hz13_multi_channel_state.json \
    run/hz13_multi_channel_report_latest.json \
    data/import/hz_jd_union_multi_channel_links_latest.jsonl
  do
    if [ -e "$f" ]; then
      mv -v "$f" "backups/$(basename "$f").before_hz13_smoke_${TS}" || true
    fi
  done

  echo "===== static check ====="
  .venv-browser/bin/python -m py_compile \
    run/hz12_product_all_full_collector.py \
    run/hz12_product_all_full_collector_v3.py \
    run/hz12_product_all_full_collector_v5.py \
    run/hz12_product_all_full_collector_v7.py \
    run/hz12_product_all_full_collector_v8.py \
    run/hz13_multi_channel_collector.py
  STATIC_RC=$?

  if [ "$STATIC_RC" != "0" ]; then
    SMOKE_RC=SKIPPED
    SMOKE_LOG=""
    echo "STATIC_CHECK_FAILED"
  else
    echo "===== run HZ13 smoke target 180 ====="
    SMOKE_LOG="logs/hz13_multi_channel_smoke_${TS}.log"
    (
      export HZ13_RUN_ONCE=true
      export HZ13_TARGET_TOTAL=180
      export HZ13_CHANNELS="全部商品,超级补贴,限量高佣,秒杀专区,定向高佣,粉丝爱买"
      export HZ13_CHANNEL_PAGE_MAX=4
      export HZ13_CHANNEL_STALE_LIMIT=2
      export HZ13_ITEM_SLEEP_MIN=3
      export HZ13_ITEM_SLEEP_MAX=6
      export HZ13_PAGE_SLEEP_MIN=2
      export HZ13_PAGE_SLEEP_MAX=4
      timeout 7200 .venv-browser/bin/python run/hz13_multi_channel_collector.py
    ) > "$SMOKE_LOG" 2>&1
    SMOKE_RC=$?
  fi

  echo "===== generate HZ13 smoke report ====="
  python3 - <<PY
import json
from pathlib import Path
from datetime import datetime

log_path = "$SMOKE_LOG"
latest = Path('data/import/hz_jd_union_multi_channel_links_latest.jsonl')
stop = Path('run/hz13_STOP_REQUIRED.json')
state = Path('run/hz13_multi_channel_state.json')
runtime_report = Path('run/hz13_multi_channel_report_latest.json')

def read_json(path):
    p = Path(path)
    if not p.exists(): return None
    try: return json.loads(p.read_text(encoding='utf-8', errors='ignore'))
    except Exception as e: return {'_read_error': repr(e)}

def read_jsonl(path):
    rows=[]
    p=Path(path)
    if p.exists():
        target=p.resolve() if p.is_symlink() else p
        for line in target.read_text(encoding='utf-8', errors='ignore').splitlines():
            if not line.strip(): continue
            try: rows.append(json.loads(line))
            except Exception: pass
    return rows

def events(path):
    out=[]
    p=Path(path)
    if not path or not p.exists(): return out
    keep={'HZ13_MULTI_CHANNEL_START','CHANNEL_OPEN','PAGE_CANDIDATES','ITEM_OK','ITEM_FAIL','STOP_REQUIRED','TARGET_TOTAL_REACHED','CHANNEL_NEXT','CHANNEL_STALE_LIMIT','CYCLE_DONE'}
    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        if not line.strip().startswith('{'): continue
        try: x=json.loads(line)
        except Exception: continue
        if x.get('event') in keep: out.append(x)
    return out[-320:]

rows=read_jsonl(latest)
ok=[x for x in rows if x.get('status')=='ok' and x.get('short_url')]
skus={str(x.get('sku')) for x in ok if x.get('sku')}
non_numeric=[x for x in ok if not str(x.get('sku') or '').isdigit()]
channels={}
for x in ok:
    c=str(x.get('channel') or 'unknown')
    channels[c]=channels.get(c,0)+1
missing={
    'title': sum(1 for x in ok if not x.get('title')),
    'image_url': sum(1 for x in ok if not x.get('image_url')),
    'item_url': sum(1 for x in ok if not x.get('item_url')),
    'price': sum(1 for x in ok if not x.get('price')),
    'commission_rate': sum(1 for x in ok if not x.get('commission_rate')),
    'estimated_income': sum(1 for x in ok if not x.get('estimated_income')),
    'long_url': sum(1 for x in ok if not x.get('long_url')),
    'qr_url': sum(1 for x in ok if not x.get('qr_url')),
    'jd_command': sum(1 for x in ok if not x.get('jd_command')),
    'refresh_due_at': sum(1 for x in ok if not x.get('refresh_due_at')),
}
ev=events(log_path)
report={
    'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'phase': 'HZ13 multi-channel smoke',
    'return_codes': {'static': '$STATIC_RC', 'smoke': '$SMOKE_RC'},
    'log': log_path,
    'stop_exists': stop.exists(),
    'stop': read_json(stop),
    'counts': {'rows': len(rows), 'ok': len(ok), 'dedup_sku': len(skus), 'non_numeric': len(non_numeric), 'duplicate_ok_rows': len(ok)-len(skus)},
    'channels': channels,
    'missing': missing,
    'runtime_report': read_json(runtime_report),
    'state': read_json(state),
    'events_tail': ev,
    'sample_last_20': [{'channel':x.get('channel'),'page_no':x.get('page_no'),'sku':x.get('sku'),'short_url':x.get('short_url'),'title':(x.get('title') or '')[:90]} for x in ok[-20:]],
    'decision': 'If multiple channels contribute, missing=0, stop=false, and ok grows beyond single-path plateau, start HZ13 full 4000.'
}
Path('reports/hz13_multi_channel_smoke_latest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
Path('docs/ops/DL2_HZ13_MULTI_CHANNEL_SMOKE.md').write_text('# HZ13 Multi Channel Smoke\n\n' + f"- Generated at: {report['ts']}\n- counts: {report['counts']}\n- channels: {channels}\n- missing: {missing}\n- stop_exists: {report['stop_exists']}\n", encoding='utf-8')
print(json.dumps({'report':'reports/hz13_multi_channel_smoke_latest.json','counts':report['counts'],'channels':channels,'missing':missing,'stop_exists':report['stop_exists']}, ensure_ascii=False, indent=2))
PY

  echo "===== commit and push HZ13 smoke report ====="
  git add reports/hz13_multi_channel_smoke_latest.json docs/ops/DL2_HZ13_MULTI_CHANNEL_SMOKE.md
  git commit -m "docs: add HZ13 multi-channel smoke report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "SMOKE_RC=$SMOKE_RC"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "SMOKE_LOG=$SMOKE_LOG"
  echo "REPORT=reports/hz13_multi_channel_smoke_latest.json"
  git status --short | head -n 60
fi
