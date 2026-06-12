#!/usr/bin/env bash
# Repair current browser from /entire or any non-product page back to 商品推广/全部商品 page 49,
# then run the HZ21 safe locator click smoke. No exit and no set -e are used.
PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  mkdir -p logs reports docs/ops run data/import
  TS="$(date +%Y%m%d_%H%M%S)"
  PREP_LOG="logs/hz21_prepare_page49_${TS}.log"

  echo "===== HZ21 prepare page49 then run safe locator ====="
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

  echo "===== prepare browser to proManager page49 ====="
  .venv-browser/bin/python - <<'PY' > "$PREP_LOG" 2>&1
import json, time
from datetime import datetime
from playwright.sync_api import sync_playwright
RISK=['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧']
def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def emit(event, **kw): print(json.dumps({'ts':now(),'event':event,**kw},ensure_ascii=False,sort_keys=True), flush=True)
def txt(page):
    try: return page.evaluate("() => document.body ? (document.body.innerText || '') : ''")
    except Exception: return ''
def info(page):
    return page.evaluate("""
    () => {
      const t=document.body?(document.body.innerText||''):'';
      const pager=document.querySelector('.el-pagination');
      const active=pager?Array.from(pager.querySelectorAll('.el-pager li')).find(el=>String(el.className||'').includes('active')):null;
      const input=pager?pager.querySelector('.el-pagination__jump input, input.el-input__inner'):null;
      const skus=[];
      for (const a of Array.from(document.querySelectorAll('a[href]'))) { const m=(a.href||'').match(/\/(\d{5,})\.html/); if (m && !skus.includes(m[1])) skus.push(m[1]); }
      return {url:location.href,title:document.title,has4000:t.includes('共 4000 条')||t.includes('共4000条'),oneKeyCount:(t.match(/一键领链/g)||[]).length,skuCount:skus.length,pagerText:pager?(pager.innerText||pager.textContent||'').replace(/\s+/g,' ').trim():'',activePageText:active?(active.innerText||active.textContent||'').replace(/\s+/g,'').trim():null,jumpInputValue:input?(input.value||''):null,risk:['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧'].filter(x=>t.includes(x)||location.href.includes(x)),skus:skus.slice(0,10)};
    }
    """)
with sync_playwright() as p:
    browser=p.chromium.connect_over_cdp('http://127.0.0.1:19228',timeout=15000)
    pages=[pg for c in browser.contexts for pg in c.pages]
    page=None
    for pg in pages:
        if 'union.jd.com' in (pg.url or ''):
            page=pg
            break
    page=page or pages[0]
    page.set_default_timeout(20000)
    page.bring_to_front()
    emit('BEFORE', info=info(page))
    if info(page).get('risk'):
        emit('STOP_RISK', info=info(page))
    else:
        page.goto('https://union.jd.com/proManager/index?pageNo=49', wait_until='domcontentloaded', timeout=45000)
        page.wait_for_timeout(8000)
        # Force hydration by scrolling; pageNo parameter usually restores the list if the session is valid.
        for y in [0, 500, 1000, 1500, 500, 0]:
            page.evaluate('(y)=>window.scrollTo(0,y)', y)
            page.wait_for_timeout(700)
        emit('AFTER_GOTO', info=info(page))
PY
  PREP_RC=$?

  echo "===== prepare log tail ====="
  tail -n 80 "$PREP_LOG" || true

  echo "===== run safe locator script ====="
  bash scripts/hz21_patch_safe_locator_click_and_run.sh
  RUN_RC=$?

  echo "===== SUMMARY ====="
  echo "PREP_RC=$PREP_RC"
  echo "RUN_RC=$RUN_RC"
  echo "PREP_LOG=$PREP_LOG"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
