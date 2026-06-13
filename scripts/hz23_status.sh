#!/usr/bin/env bash
PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1

echo "===== service ====="
sudo systemctl is-active aideal-hz23-observer.service 2>/dev/null || true
sudo systemctl status aideal-hz23-observer.service --no-pager -l 2>/dev/null | sed -n '1,35p' || true

echo "===== observer state ====="
python3 - <<'PY'
import json
from pathlib import Path
for name in ['run/hz23_observer_state.json','reports/hz23_observer_status_latest.json','reports/hz23_round_latest.json','data/export/aideal_cps_products_commercial_candidate_manifest.json']:
    p=Path(name)
    print(f'FILE={name} EXISTS={p.exists()}')
    if not p.exists():
        continue
    try:
        x=json.loads(p.read_text(encoding='utf-8'))
    except Exception as exc:
        print('ERROR=',repr(exc)); continue
    if name.endswith('observer_state.json'):
        print(json.dumps({k:x.get(k) for k in ['created_at','next_full_due_at','next_probe_due_at','last_probe_at','last_full_started_at','last_full_finished_at','last_full_round_id','last_full_complete','last_stop_reason','requires_manual','successful_full_rounds']},ensure_ascii=False,indent=2))
    elif name.endswith('observer_status_latest.json'):
        print(json.dumps({'ts':x.get('ts'),'mode':x.get('mode')},ensure_ascii=False,indent=2))
    elif name.endswith('round_latest.json'):
        print(json.dumps({k:x.get(k) for k in ['round_id','commercial_segment_complete','completed_pages','unfinished_pages','total_ok','total_fail','scanned_total','catalog_new','catalog_changed','catalog_unchanged','last_known_sku_count','stop_page','stop_reason','duration_seconds']},ensure_ascii=False,indent=2))
    else:
        print(json.dumps({k:x.get(k) for k in ['generated_at','round_id','trusted_dedup_sku_count','catalog_index_sku_count','round_seen_sku_count','eligible_sku_count','rejected','duplicate_sku_count','round_complete','observation_ready','commercial_enabled']},ensure_ascii=False,indent=2))
PY

echo "===== observer log tail ====="
tail -n 80 logs/hz23_observer.log 2>/dev/null || true

echo "===== SUMMARY ====="
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
git status --short | head -n 60
