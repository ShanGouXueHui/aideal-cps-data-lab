#!/usr/bin/env bash
# Offline only: rebuild overlap analysis from the five verified special tabs.
# No JD operation, observer restart, or MySQL access. No set -e.

cd "${HOME}/projects/aideal-cps-data-lab"
if [ "$?" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=project_directory_missing"
  exit 1
fi
mkdir -p logs reports run backups

SOURCE="reports/hz24_tab_pool_structure_latest.json"
SPECIAL="reports/hz24_tab_pool_structure_special_verified_latest.json"
BACKUP="backups/hz24_tab_pool_structure_before_finalize_$(date +%Y%m%d_%H%M%S).json"

python3 - "$SOURCE" "$SPECIAL" <<'PY'
import hashlib,json,sys
from pathlib import Path
source=Path(sys.argv[1]); out=Path(sys.argv[2])
x=json.loads(source.read_text(encoding='utf-8'))
names=['超补爆品','限量高佣','秒杀专区','定向高佣','粉丝爱买']
rows={str(r.get('tab_name') or ''):r for r in x.get('tabs') or [] if isinstance(r,dict)}
fail=[]
for name in names:
    row=rows.get(name) or {}
    if not row: fail.append(name+':missing')
    elif row.get('ok') is not True: fail.append(name+':not_ok')
    elif row.get('risk'): fail.append(name+':risk')
    elif row.get('single_page_confirmed') is not True: fail.append(name+':not_single_page')
    elif not row.get('skus'): fail.append(name+':empty')
if fail:
    print('VERIFY_FAILURES='+','.join(fail))
    raise SystemExit(1)
raw=source.read_bytes()
y={
 'schema_version':'aideal-hz24-special-tabs-verified/v1',
 'generated_at':x.get('generated_at'),
 'source_structure_file':str(source),
 'source_structure_sha256':hashlib.sha256(raw).hexdigest(),
 'mode':'offline_verified_special_tabs',
 'ok':True,
 'risk':[],
 'tabs':[rows[name] for name in names],
}
tmp=out.with_suffix(out.suffix+'.tmp')
tmp.write_text(json.dumps(y,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
tmp.replace(out)
print('VERIFIED_TAB_COUNT=5')
PY
VERIFY_RC=$?

if [ "$VERIFY_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=verify_special_tabs"
  echo "VERIFY_RC=$VERIFY_RC"
  exit 1
fi

cp -a "$SOURCE" "$BACKUP"
BACKUP_RC=$?
cp -a "$SPECIAL" "$SOURCE"
SWAP_RC=$?

rm -f reports/hz24_tab_overlap_analysis_latest.json
if [ "$BACKUP_RC" = "0" ] && [ "$SWAP_RC" = "0" ]; then
  PYTHONPATH=src python3 scripts/hz24_analyze_tab_overlap.py \
    > logs/hz24_finalize_verified_special_tabs.log 2>&1
  ANALYZE_RC=$?
else
  ANALYZE_RC=99
fi

cp -a "$BACKUP" "$SOURCE"
RESTORE_RC=$?

PUBLISH_RC=99
if [ "$ANALYZE_RC" = "0" ] && [ "$RESTORE_RC" = "0" ]; then
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: finalize verified HZ24 special-tab overlap" \
    "$SPECIAL" \
    reports/hz24_tab_overlap_analysis_latest.json \
    > logs/hz24_finalize_publish.log 2>&1
  PUBLISH_RC=$?
fi

METRICS="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/hz24_tab_overlap_analysis_latest.json')
x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
print('ANALYSIS_READY='+str(bool(x.get('analysis_ready'))).lower())
print('STRUCTURE_GENERATED_AT='+str(x.get('structure_generated_at') or ''))
print('STRUCTURE_SHA256='+str(x.get('structure_sha256') or ''))
print('SPECIAL_TAB_UNION_SKU_COUNT='+str(x.get('special_tab_union_sku_count') or 0))
print('SPECIAL_UNION_OVERLAP_WITH_CANDIDATE_COUNT='+str(x.get('special_union_overlap_with_candidate_count') or 0))
print('SPECIAL_UNION_INCREMENT_VS_CANDIDATE_COUNT='+str(x.get('special_union_increment_vs_candidate_count') or 0))
print('SPECIAL_UNION_PROMOTION_LINK_REQUIRED_COUNT='+str(x.get('special_union_promotion_link_required_count') or 0))
print('RECOMMENDED_NEXT_STEP='+str(x.get('recommended_next_step') or ''))
print('ANALYSIS_FAILURES='+(','.join(x.get('failures') or []) or '-'))
PY
)"

STATUS=PASS
if [ "$VERIFY_RC" != "0" ] || [ "$BACKUP_RC" != "0" ] || [ "$SWAP_RC" != "0" ] || [ "$ANALYZE_RC" != "0" ] || [ "$RESTORE_RC" != "0" ] || [ "$PUBLISH_RC" != "0" ]; then STATUS=FAIL; fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "VERIFY_RC=$VERIFY_RC"
echo "BACKUP_RC=$BACKUP_RC"
echo "SWAP_RC=$SWAP_RC"
echo "ANALYZE_RC=$ANALYZE_RC"
echo "RESTORE_RC=$RESTORE_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
printf '%s\n' "$METRICS"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = PASS ]
