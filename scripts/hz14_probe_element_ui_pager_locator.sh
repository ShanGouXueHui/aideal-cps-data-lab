#!/usr/bin/env bash
# HZ14 Element UI pager locator probe.
# Use only 商品推广 / 全部商品. Probe .el-pagination/.el-pager with Playwright locators.
# No link collection, no DB write. No exit is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p logs reports docs/ops run backups
  PROBE_LOG="logs/hz14_element_ui_pager_locator_${TS}.log"

  echo "===== HZ14 Element UI pager locator probe ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  pkill -f "python.*run/hz12_product_all_full_collector" 2>/dev/null || true
  pkill -f "python.*run/hz13_multi_channel_collector" 2>/dev/null || true
  sleep 2

  .venv-browser/bin/python - <<'PY' > "$PROBE_LOG" 2>&1
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

OUT = Path('reports/hz14_element_ui_pager_locator_latest.json')
MD = Path('docs/ops/DL2_HZ14_ELEMENT_UI_PAGER_LOCATOR.md')


def page_info(page):
    return page.evaluate("""
    () => {
      const txt = document.body ? (document.body.innerText || '') : '';
      const skus = [];
      for (const a of Array.from(document.querySelectorAll('a[href]'))) {
        const m = (a.href || '').match(/\/(\d{5,})\.html/);
        if (m && !skus.includes(m[1])) skus.push(m[1]);
      }
      return {url: location.href, oneKeyCount: (txt.match(/一键领链/g) || []).length, skuCount: skus.length, skus: skus.slice(0, 100), has4000: txt.includes('共 4000 条') || txt.includes('共4000条'), hasEmpty: txt.includes('抱歉，没有找到相关商品'), tail: txt.slice(-900)};
    }
    """)


def click_all_product(page):
    loc = page.get_by_text('全部商品', exact=True)
    count = loc.count()
    if count <= 0:
        return {'ok': False, 'reason': 'not_found'}
    # The right-most visible one is the channel tab, not category label.
    loc.nth(count - 1).click(timeout=8000)
    return {'ok': True, 'count': count}


def pager_summary(page):
    return page.evaluate("""
    () => {
      const r = el => { const b = el.getBoundingClientRect(); return {x:b.x,y:b.y,w:b.width,h:b.height,cx:b.x+b.width/2,cy:b.y+b.height/2}; };
      const t = el => (el.innerText || el.textContent || '').replace(/\s+/g,' ').trim();
      const p = document.querySelector('.el-pagination');
      return {
        hasPager: !!p,
        pagerText: p ? t(p) : '',
        pagerRect: p ? r(p) : null,
        lis: p ? Array.from(p.querySelectorAll('li')).map((el, i) => ({i, text:t(el), cls:String(el.className||''), rect:r(el)})) : [],
        buttons: p ? Array.from(p.querySelectorAll('button')).map((el, i) => ({i, text:t(el), cls:String(el.className||''), disabled:!!el.disabled, rect:r(el)})) : [],
        inputs: p ? Array.from(p.querySelectorAll('input')).map((el, i) => ({i, value:el.value||'', placeholder:el.placeholder||'', cls:String(el.className||''), rect:r(el)})) : [],
        viewport: {w:window.innerWidth,h:window.innerHeight,scrollY:window.scrollY,bodyScrollHeight:document.body.scrollHeight,bodyClientHeight:document.body.clientHeight}
      };
    }
    """)


def wait_changed(page, before):
    after = None
    changed = False
    for _ in range(25):
        page.wait_for_timeout(1000)
        after = page_info(page)
        if after.get('skus') and after.get('skus')[:40] != before[:40]:
            changed = True
            break
    return changed, after

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:19228', timeout=20000)
    pages = []
    for ctx in browser.contexts:
        pages.extend(ctx.pages)
    page = next((x for x in reversed(pages) if 'union.jd.com' in (x.url or '')), pages[-1])
    page.set_default_timeout(20000)
    page.set_viewport_size({'width': 1920, 'height': 1600})
    page.goto('https://union.jd.com/proManager/index?pageNo=1', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(5000)
    click_all = click_all_product(page)
    page.wait_for_timeout(6000)
    page.evaluate("""() => { document.body.style.zoom='80%'; const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); else window.scrollTo(0, document.body.scrollHeight); }""")
    page.wait_for_timeout(1200)
    start = page_info(page)
    state0 = pager_summary(page)
    results = []
    before = start.get('skus', [])[:40]
    for target in ['2', '3']:
        state_before = pager_summary(page)
        click_result = {'target': target, 'ok': False}
        try:
            li = page.locator('.el-pagination .el-pager li').filter(has_text=target).first
            li.scroll_into_view_if_needed(timeout=5000)
            li.click(timeout=8000)
            click_result = {'target': target, 'ok': True, 'method': 'locator_li'}
        except Exception as e:
            click_result = {'target': target, 'ok': False, 'err': repr(e), 'method': 'locator_li'}
        changed, after = wait_changed(page, before)
        results.append({'target': target, 'click': click_result, 'changed': changed, 'after': after, 'state_before': state_before})
        if after and after.get('skus'):
            before = after.get('skus', [])[:40]
        page.evaluate("""() => { const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); }""")
        page.wait_for_timeout(800)
    next_result = {'ok': False}
    try:
        before_next = before[:]
        nxt = page.locator('.el-pagination button.btn-next').first
        nxt.scroll_into_view_if_needed(timeout=5000)
        nxt.click(timeout=8000)
        changed_next, after_next = wait_changed(page, before_next)
        next_result = {'ok': True, 'changed': changed_next, 'after': after_next}
    except Exception as e:
        next_result = {'ok': False, 'err': repr(e)}
    report = {'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'phase': 'HZ14 Element UI pager locator probe', 'click_all': click_all, 'start': start, 'state0': state0, 'results': results, 'next_result': next_result, 'decision': 'If locator clicks change SKU, implement official HZ14 all-product collector with .el-pager li and btn-next.'}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    MD.write_text('# HZ14 Element UI Pager Locator Probe\n\n' + f"- Generated at: {report['ts']}\n- pager lis: {[x.get('text') for x in state0.get('lis', [])]}\n- results changed: {[x.get('changed') for x in results]}\n- next changed: {next_result.get('changed')}\n", encoding='utf-8')
    print(json.dumps({'report': str(OUT), 'start': {'oneKeyCount': start.get('oneKeyCount'), 'skuCount': start.get('skuCount'), 'has4000': start.get('has4000')}, 'pager': {'hasPager': state0.get('hasPager'), 'lis': [x.get('text') for x in state0.get('lis', [])], 'buttons': state0.get('buttons')}, 'results': [{'target': x.get('target'), 'click_ok': (x.get('click') or {}).get('ok'), 'changed': x.get('changed'), 'after_skuCount': (x.get('after') or {}).get('skuCount')} for x in results], 'next': {'ok': next_result.get('ok'), 'changed': next_result.get('changed'), 'after_skuCount': (next_result.get('after') or {}).get('skuCount')}}, ensure_ascii=False, indent=2), flush=True)
PY

  git add reports/hz14_element_ui_pager_locator_latest.json docs/ops/DL2_HZ14_ELEMENT_UI_PAGER_LOCATOR.md
  git commit -m "docs: add HZ14 Element UI pager locator report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz14_element_ui_pager_locator_latest.json"
  git status --short | head -n 60
fi
