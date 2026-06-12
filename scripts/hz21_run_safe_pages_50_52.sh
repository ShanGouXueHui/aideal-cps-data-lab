#!/usr/bin/env bash
# Run HZ21 strict safe-locator recovery for pages 50-52.
# It prepares each page through the 4000-row pager before collection.
# No exit and no set -e are used.
PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  mkdir -p logs reports docs/ops run data/import
  TS="$(date +%Y%m%d_%H%M%S)"
  LOG="logs/hz21_safe_pages_50_52_${TS}.log"
  MD="docs/ops/DL2_HZ21_SAFE_PAGES_50_52_SMOKE.md"
  SUMMARY_JSON="reports/hz21_safe_pages_50_52_latest.json"

  echo "===== HZ21 safe pages 50-52 smoke =====" | tee -a "$LOG"
  echo "PWD=$(pwd)" | tee -a "$LOG"
  echo "USER=$(whoami)" | tee -a "$LOG"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a "$LOG"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)" | tee -a "$LOG"

  echo "===== stop collectors only =====" | tee -a "$LOG"
  pkill -f "run/hz17_recover_short_url_page.py" || true
  pkill -f "run/hz18_card_click_recover_page.py" || true
  pkill -f "run/hz20_mouse_click_recover_page.py" || true
  pkill -f "run/hz21_strict_card_dom_recover_page.py" || true
  pkill -f "hz15_jump_pages_collector_v6_no_reset_strict_4000.py" || true
  sleep 2

  echo "===== static check =====" | tee -a "$LOG"
  .venv-browser/bin/python -m py_compile run/hz21_strict_card_dom_recover_page.py | tee -a "$LOG"
  STATIC_RC=${PIPESTATUS[0]}

  TOTAL_OK=0
  TOTAL_FAIL=0
  PAGES_OK=0
  PAGES_FAIL=0
  : > reports/hz21_safe_pages_50_52_per_page.jsonl

  for PAGE_NO in 50 51 52; do
    echo "===== prepare page ${PAGE_NO} through 4000 pager =====" | tee -a "$LOG"
    PREP_JSON="reports/hz21_prepare_4000_pager_page${PAGE_NO}_latest.json"
    .venv-browser/bin/python - "$PAGE_NO" "$PREP_JSON" <<'PY' 2>&1 | tee -a "$LOG"
import json, sys, time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
page_no=int(sys.argv[1])
out=Path(sys.argv[2])
def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def snap(page):
    return page.evaluate('''() => {
      const txt=document.body?(document.body.innerText||''):'';
      const skus=[];
      for (const a of Array.from(document.querySelectorAll('a[href]'))) { const m=(a.href||'').match(/\/(\d{5,})\.html/); if (m && !skus.includes(m[1])) skus.push(m[1]); }
      const pagers=Array.from(document.querySelectorAll('.el-pagination')).map((p,i)=>{const active=Array.from(p.querySelectorAll('.el-pager li')).find(el=>String(el.className||'').includes('active')); const input=p.querySelector('.el-pagination__jump input, input.el-input__inner'); return {i,text:(p.innerText||p.textContent||'').replace(/\s+/g,' ').trim(),active:active?(active.innerText||active.textContent||'').replace(/\s+/g,'').trim():null,input:input?(input.value||''):null};});
      const pager=pagers.find(p=>p.text.includes('4000')) || pagers[0] || {};
      return {url:location.href,title:document.title,has4000:txt.includes('共 4000 条')||txt.includes('共4000条'),oneKeyCount:(txt.match(/一键领链/g)||[]).length,skuCount:skus.length,pagerText:pager.text||'',activePageText:pager.active||null,jumpInputValue:pager.input||null,risk:['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧'].filter(x=>txt.includes(x)||location.href.includes(x)),skus:skus.slice(0,12),pagers:pagers};
    }''')
rep={'ts':now(),'target_page':page_no,'ok':False}
with sync_playwright() as p:
    browser=p.chromium.connect_over_cdp('http://127.0.0.1:19228',timeout=15000)
    pages=[pg for c in browser.contexts for pg in c.pages]
    page=None
    for pg in reversed(pages):
        if 'union.jd.com' in (pg.url or ''):
            page=pg; break
    page=page or pages[-1]
    page.set_default_timeout(20000); page.bring_to_front()
    before=snap(page); rep['before']=before
    if before.get('risk'):
        rep['reason']='risk_before'
    else:
        if not before.get('has4000'):
            page.goto('https://union.jd.com/proManager/index?pageNo=1', wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(7000)
        action=page.evaluate('''(target) => {
          const pagers=Array.from(document.querySelectorAll('.el-pagination'));
          const p=pagers.find(x=>((x.innerText||x.textContent||'').includes('4000')));
          if (!p) return {ok:false,reason:'no_4000_pager',pagerCount:pagers.length};
          p.scrollIntoView({block:'center',inline:'center'});
          const input=p.querySelector('.el-pagination__jump input, input.el-input__inner');
          if (!input) return {ok:false,reason:'no_jump_input',text:(p.innerText||p.textContent||'').replace(/\s+/g,' ').trim()};
          input.focus(); input.value=''; input.dispatchEvent(new Event('input',{bubbles:true})); input.value=String(target); input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true})); input.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));
          return {ok:true,method:'4000_pager_input_enter',text:(p.innerText||p.textContent||'').replace(/\s+/g,' ').trim()};
        }''', page_no)
        rep['jump_action']=action
        good=None
        for i in range(45):
            time.sleep(1)
            info=snap(page)
            if info.get('risk'):
                rep['reason']='risk_after_jump'; good=info; break
            if info.get('has4000') and info.get('oneKeyCount',0)>=55 and info.get('skuCount',0)>=55 and str(info.get('activePageText'))==str(page_no):
                good=info; rep['ok']=True; rep['reason']='safe_all_product_4000_page'; break
        rep['after']=good or snap(page)
        if not rep.get('reason'):
            rep['reason']='jump_not_safe_page'
out.write_text(json.dumps(rep,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
print(json.dumps({'event':'PREP_DONE','page':page_no,'ok':rep.get('ok'),'reason':rep.get('reason'),'after':rep.get('after')}, ensure_ascii=False))
PY
    PREP_RC=${PIPESTATUS[0]}

    SAFE="$(python3 - "$PREP_JSON" <<'PY'
import json, sys
from pathlib import Path
p=Path(sys.argv[1])
try:
  x=json.loads(p.read_text(encoding='utf-8'))
  print('true' if x.get('ok') else 'false')
except Exception:
  print('false')
PY
)"
    echo "PAGE=${PAGE_NO} PREP_RC=${PREP_RC} SAFE=${SAFE}" | tee -a "$LOG"

    if [ "$SAFE" = "true" ]; then
      echo "===== run HZ21 for page ${PAGE_NO} =====" | tee -a "$LOG"
      HZ21_PAGE_SEQUENCE="$PAGE_NO" HZ21_LIMIT=25 HZ21_WAIT=10 HZ21_FAIL_FUSE=6 HZ21_ITEM_SLEEP_MIN=1 HZ21_ITEM_SLEEP_MAX=3 .venv-browser/bin/python run/hz21_strict_card_dom_recover_page.py 2>&1 | tee -a "$LOG"
      HZ21_RC=${PIPESTATUS[0]}
      cp reports/hz21_strict_card_dom_recover_latest.json "reports/hz21_safe_page_${PAGE_NO}_latest.json" 2>/dev/null || true
      python3 - "$PAGE_NO" "$HZ21_RC" <<'PY' | tee -a "$LOG"
import json, sys
from pathlib import Path
page=sys.argv[1]; rc=int(sys.argv[2])
p=Path('reports/hz21_strict_card_dom_recover_latest.json')
x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
row={'page':int(page),'rc':rc,'ok':x.get('ok'),'reason':x.get('reason'),'total_ok':x.get('total_ok',0),'total_fail':x.get('total_fail',0),'known_sku_count':x.get('known_sku_count'), 'page_summary': (x.get('page_summary') or {}).get(str(page))}
Path('reports/hz21_safe_pages_50_52_per_page.jsonl').open('a',encoding='utf-8').write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
print(json.dumps({'event':'HZ21_PAGE_DONE', **row}, ensure_ascii=False))
PY
    else
      HZ21_RC=99
      echo "PAGE=${PAGE_NO} HZ21_SKIPPED=prepare_not_safe" | tee -a "$LOG"
      python3 - "$PAGE_NO" <<'PY'
import json, sys
from pathlib import Path
row={'page':int(sys.argv[1]),'rc':99,'ok':False,'reason':'prepare_not_safe','total_ok':0,'total_fail':0}
Path('reports/hz21_safe_pages_50_52_per_page.jsonl').open('a',encoding='utf-8').write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
PY
    fi
    sleep 5
  done

  python3 - <<'PY'
import json
from pathlib import Path
rows=[]
p=Path('reports/hz21_safe_pages_50_52_per_page.jsonl')
if p.exists():
  rows=[json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
out={'pages':[50,51,52],'rows':rows,'total_ok':sum(int(r.get('total_ok') or 0) for r in rows),'total_fail':sum(int(r.get('total_fail') or 0) for r in rows),'last_known_sku_count': rows[-1].get('known_sku_count') if rows else None}
Path('reports/hz21_safe_pages_50_52_latest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
md=['# DL2 HZ21 Safe Pages 50-52 Smoke','', '```json', json.dumps(out,ensure_ascii=False,indent=2), '```']
Path('docs/ops/DL2_HZ21_SAFE_PAGES_50_52_SMOKE.md').write_text('\n'.join(md),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,sort_keys=True))
PY

  echo "===== commit reports/data/log =====" | tee -a "$LOG"
  git add reports/hz21_safe_pages_50_52_latest.json reports/hz21_safe_pages_50_52_per_page.jsonl reports/hz21_safe_page_*_latest.json reports/hz21_prepare_4000_pager_page*_latest.json docs/ops/DL2_HZ21_SAFE_PAGES_50_52_SMOKE.md "$LOG" data/import/hz_jd_union_all_product_full_links_latest.jsonl data/import/hz_jd_union_product_all_full_links_latest.jsonl run/hz14_all_product_full_report_latest.json run/hz14_all_product_full_state.json 2>/dev/null || true
  git commit -m "docs: publish HZ21 safe pages 50-52 smoke" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "LOG=$LOG"
  echo "SUMMARY_JSON=$SUMMARY_JSON"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
