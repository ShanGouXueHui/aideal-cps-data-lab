#!/usr/bin/env bash
# Prepare 商品推广/全部商品 page 49 by targeting the pagination block whose text contains 4000,
# then run HZ21 safe locator smoke. No exit and no set -e are used.
PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  mkdir -p logs reports docs/ops run data/import
  TS="$(date +%Y%m%d_%H%M%S)"
  PREP_LOG="logs/hz21_prepare_4000_pager_page49_${TS}.log"
  PREP_JSON="reports/hz21_prepare_4000_pager_page49_latest.json"

  echo "===== HZ21 prepare page49 by 4000 pager then run ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop collectors only ====="
  pkill -f "run/hz17_recover_short_url_page.py" || true
  pkill -f "run/hz18_card_click_recover_page.py" || true
  pkill -f "run/hz20_mouse_click_recover_page.py" || true
  pkill -f "run/hz21_strict_card_dom_recover_page.py" || true
  pkill -f "hz15_jump_pages_collector_v6_no_reset_strict_4000.py" || true
  sleep 2

  echo "===== prepare all-product page1 using existing HZ15 prepare-only ====="
  python3 - <<'PY'
from pathlib import Path
src = Path('scripts/hz15_rearm_auto_prepare_all_product_then_supervisor.sh').read_text(encoding='utf-8')
src = src.replace(
'''    echo "===== restart daytime autostart supervisor ====="
    bash scripts/hz15_daytime_autostart_pages_40_67_no_reset_v6_strict_4000.sh
    REARM_RESULT=RESTARTED_SUPERVISOR''',
'''    echo "===== safe page confirmed; skip HZ15 supervisor restart for HZ21 smoke ====="
    REARM_RESULT=SAFE_PREPARED_NO_SUPERVISOR'''
)
Path('run/hz21_prepare_only_from_hz15_rearm.sh').write_text(src, encoding='utf-8')
print('WRAPPER_READY=1')
PY
  bash run/hz21_prepare_only_from_hz15_rearm.sh >/tmp/hz21_prepare_only_stdout.log 2>&1
  PREP1_RC=$?
  tail -n 60 /tmp/hz21_prepare_only_stdout.log || true

  echo "===== jump to page49 using the pager that contains 4000 ====="
  .venv-browser/bin/python - <<'PY' > "$PREP_LOG" 2>&1
import json, time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
OUT=Path('reports/hz21_prepare_4000_pager_page49_latest.json')
RISK=['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧']
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
def emit(event, **kw): print(json.dumps({'ts':now(),'event':event,**kw},ensure_ascii=False,sort_keys=True), flush=True)
rep={'ts':now(),'ok':False,'target_page':49,'steps':[]}
with sync_playwright() as p:
    browser=p.chromium.connect_over_cdp('http://127.0.0.1:19228',timeout=15000)
    pages=[pg for c in browser.contexts for pg in c.pages]
    page=None
    for pg in reversed(pages):
        if 'union.jd.com' in (pg.url or ''):
            page=pg; break
    page=page or pages[-1]
    page.set_default_timeout(20000); page.bring_to_front()
    rep['before']=snap(page); emit('BEFORE', info=rep['before'])
    if rep['before'].get('risk'):
        rep['reason']='risk_before'
    elif not rep['before'].get('has4000'):
        rep['reason']='not_4000_before_jump'
    else:
        result=page.evaluate('''(target) => {
          const pagers=Array.from(document.querySelectorAll('.el-pagination'));
          const p=pagers.find(x=>((x.innerText||x.textContent||'').includes('4000')));
          if (!p) return {ok:false,reason:'no_4000_pager',pagerCount:pagers.length};
          p.scrollIntoView({block:'center',inline:'center'});
          const input=p.querySelector('.el-pagination__jump input, input.el-input__inner');
          if (!input) return {ok:false,reason:'no_jump_input',text:(p.innerText||p.textContent||'').replace(/\s+/g,' ').trim()};
          input.focus(); input.value=''; input.dispatchEvent(new Event('input',{bubbles:true})); input.value=String(target); input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true})); input.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));
          return {ok:true,method:'4000_pager_input_enter',text:(p.innerText||p.textContent||'').replace(/\s+/g,' ').trim()};
        }''', 49)
        rep['jump_action']=result; emit('JUMP_ACTION', result=result)
        good=None
        for i in range(45):
            time.sleep(1)
            info=snap(page)
            if info.get('risk'):
                rep['reason']='risk_after_jump'; good=info; break
            if info.get('has4000') and info.get('oneKeyCount',0)>=55 and info.get('skuCount',0)>=55 and str(info.get('activePageText'))=='49':
                good=info; rep['ok']=True; rep['reason']='safe_all_product_4000_page49'; break
        rep['after']=good or snap(page)
        if not rep.get('reason'):
            rep['reason']='jump_not_safe_page49'
OUT.write_text(json.dumps(rep,ensure_ascii=False,indent=2,sort_keys=True), encoding='utf-8')
emit('DONE', ok=rep.get('ok'), reason=rep.get('reason'), after=rep.get('after'))
PY
  PREP2_RC=$?
  tail -n 120 "$PREP_LOG" || true

  SAFE="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/hz21_prepare_4000_pager_page49_latest.json')
try:
  x=json.loads(p.read_text(encoding='utf-8'))
  print('true' if x.get('ok') else 'false')
except Exception:
  print('false')
PY
)"

  if [ "$SAFE" = "true" ]; then
    echo "===== run HZ21 safe locator on verified page49 ====="
    bash scripts/hz21_patch_safe_locator_click_and_run.sh
    RUN_RC=$?
  else
    echo "HZ21_SKIPPED=prepare_page49_not_safe"
    RUN_RC=99
  fi

  echo "===== commit prepare report/log ====="
  git add "$PREP_JSON" "$PREP_LOG" reports/hz21_strict_card_dom_recover_latest.json docs/ops/DL2_HZ21_STRICT_CARD_DOM_PAGE49_SMOKE.md data/import/hz_jd_union_all_product_full_links_latest.jsonl data/import/hz_jd_union_product_all_full_links_latest.jsonl run/hz14_all_product_full_report_latest.json run/hz14_all_product_full_state.json 2>/dev/null || true
  git commit -m "docs: publish HZ21 4000 pager page49 smoke" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "PREP1_RC=$PREP1_RC"
  echo "PREP2_RC=$PREP2_RC"
  echo "SAFE=$SAFE"
  echo "RUN_RC=$RUN_RC"
  echo "PREP_LOG=$PREP_LOG"
  echo "PREP_JSON=$PREP_JSON"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
