#!/usr/bin/env bash
# HZ12 v8 restart full collection from existing latest JSONL.
# No `exit` is used because the user's shell environment may logout on exit.
# This keeps already collected latest data, rebuilds known_skus into state, and
# restarts collector with v8 reposition-next logic.
# Run on collector server 121.41.111.36 as user cpsdata:
#   cd ~/projects/aideal-cps-data-lab && git fetch origin main && git rebase origin/main && bash scripts/hz12_restart_v8_from_existing_latest.sh

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

  echo "===== HZ12 v8 restart from existing latest ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop old HZ12 worker only, keep Chrome ====="
  pkill -f "python.*run/hz12_product_all_full_collector" 2>/dev/null || true
  sleep 3

  echo "===== backup old STOP/state/report only; keep latest data ====="
  for f in \
    run/hz12_product_all_STOP_REQUIRED.json \
    run/hz12_product_all_full_state.json \
    run/hz12_product_all_full_report_latest.json
  do
    if [ -e "$f" ]; then
      mv -v "$f" "backups/$(basename "$f").before_hz12aa_v8_restart_${TS}" || true
    fi
  done

  echo "===== static check ====="
  .venv-browser/bin/python -m py_compile \
    run/hz12_product_all_full_collector.py \
    run/hz12_product_all_full_collector_v3.py \
    run/hz12_product_all_full_collector_v5.py \
    run/hz12_product_all_full_collector_v7.py \
    run/hz12_product_all_full_collector_v8.py
  STATIC_RC=$?

  if [ "$STATIC_RC" != "0" ]; then
    HZ12_PID=SKIPPED
    HZ12_LOG=""
    echo "STATIC_CHECK_FAILED"
  else
    echo "===== rebuild state from existing latest ====="
    python3 - <<'PY'
import json
from pathlib import Path
from datetime import datetime
latest = Path('data/import/hz_jd_union_product_all_full_links_latest.jsonl')
rows=[]
if latest.exists():
    target = latest.resolve() if latest.is_symlink() else latest
    for line in target.read_text(encoding='utf-8', errors='ignore').splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
ok=[x for x in rows if x.get('status')=='ok' and x.get('short_url')]
skus=[]
last_page=1
for x in ok:
    sku=str(x.get('sku') or '').strip()
    if sku and sku not in skus:
        skus.append(sku)
    try:
        last_page=max(last_page, int(x.get('page_no') or 1))
    except Exception:
        pass
state={
    'run_id': datetime.now().strftime('%Y%m%d_%H%M%S'),
    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'target_total': 4000,
    'known_skus': skus,
    'known_sku_count': len(skus),
    'round_seen_skus': skus[:],
    'round_seen_sku_count': len(skus),
    'current_page_no': max(1, last_page),
    'empty_page_streak': 0,
    'fail_streak': 0,
    'refresh_round': 0,
    'last_full_cycle_finished_at': None,
    'next_refresh_due_at': None,
    'last_event': {'event':'STATE_REBUILT_FROM_LATEST','ts':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'known_sku_count':len(skus),'last_page':last_page},
}
Path('run/hz12_product_all_full_state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
print(json.dumps({'rebuilt_known_sku':len(skus),'current_page_no':state['current_page_no']}, ensure_ascii=False))
PY

    echo "===== start background v8 full target 4000 ====="
    HZ12_LOG="logs/hz12aa_product_all_v8_reposition_full_4000_${TS}.log"
    (
      set -a
      . config/hz12_product_all_full.env
      set +a
      export HZ12_RUN_ONCE=false
      export HZ12_PAGE_MAX=260
      export HZ12_TARGET_TOTAL=4000
      export HZ12_ITEMS_PER_PAGE_LIMIT=20
      export HZ12_ITEM_SLEEP_MIN=4
      export HZ12_ITEM_SLEEP_MAX=8
      export HZ12_PAGE_SLEEP_MIN=2
      export HZ12_PAGE_SLEEP_MAX=4
      nohup .venv-browser/bin/python run/hz12_product_all_full_collector_v8.py > "$HZ12_LOG" 2>&1 &
      echo $! > run/hz12_product_all_full.pid
    )
    sleep 5
    HZ12_PID="$(cat run/hz12_product_all_full.pid 2>/dev/null || true)"
  fi

  echo "===== initial status ====="
  pgrep -af "hz12_product_all_full_collector|chrome.*19228|chrome.*19229" | head -n 80 || true
  if [ -n "${HZ12_LOG:-}" ] && [ -f "$HZ12_LOG" ]; then
    tail -n 80 "$HZ12_LOG" || true
  fi

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "HZ12_PID=$HZ12_PID"
  echo "HZ12_LOG=$HZ12_LOG"
  echo "REPORT=run/hz12_product_all_full_report_latest.json"
  echo "LATEST=data/import/hz_jd_union_product_all_full_links_latest.jsonl"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
