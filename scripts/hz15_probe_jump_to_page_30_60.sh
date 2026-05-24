#!/usr/bin/env bash
# HZ15 jump-to-page probe for 商品推广 / 全部商品 only.
# Purpose:
# - Stop current HZ14 collector to avoid page-control conflicts.
# - Use Element UI pager jump input to test direct jumps to page 30 and page 60.
# - No link collection, no DB write.
# - If JD risk verification appears, report it and do not bypass.
# No exit is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
  echo "HINT=请在杭州采集机 121.41.111.36 的 cpsdata 用户下执行。"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p logs reports docs/ops run backups
  PROBE_LOG="logs/hz15_jump_to_page_30_60_${TS}.log"

  echo "===== HZ15 jump to page 30/60 probe ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop HZ14 collector only, keep Chrome/noVNC ====="
  pkill -f "python.*run/hz14_all_product_full_collector" 2>/dev/null || true
  sleep 3

  .venv-browser/bin/python - <<'PY' > "$PROBE_LOG" 2>&1
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

OUT = Path('reports/hz15_jump_to_page_30_60_latest.json')
MD = Path('docs/ops/DL2_HZ15_JUMP_TO_PAGE_30_60.md')
TARGETS = [30, 60]
RISK_WORDS = ['快速验证','购物无忧','风险','安全验证','验证码','滑块','risk_handler']


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def page_info(page):
    return page.evaluate("""
    () => {
      const txt = document.body ? (document.body.innerText || '') : '';
      const skus = [];
      for (const a of Array.from(document.querySelectorAll('a[href]'))) {
        const m = (a.href || '').match(/\/(\d{5,})\.html/);
        if (m && !skus.includes(m[1])) skus.push(m[1]);
      }
      const pager = document.querySelector('.el-pagination');
      const active = pager ? Array.from(pager.querySelectorAll('.el-pager li')).find(el => String(el.className || '').includes('active')) : null;
      const input = pager ? pager.querySelector('.el-pagination__jump input, input.el-input__inner') : null;
      return {
        url: location.href,
        title: document.title,
        oneKeyCount: (txt.match(/一键领链/g) || []).length,
        skuCount: skus.length,
        skus: skus.slice(0, 100),
        has4000: txt.includes('共 4000 条') || txt.includes('共4000条'),
        hasEmpty: txt.includes('抱歉，没有找到相关商品'),
        pagerText: pager ? (pager.innerText || pager.textContent || '').replace(/\s+/g, ' ').trim() : '',
        activePageText: active ? (active.innerText || active.textContent || '').replace(/\s+/g, '').trim() : null,
        jumpInputValue: input ? (input.value || '') : null,
        risk: ['快速验证','购物无忧','风险','安全验证','验证码','滑块','risk_handler'].filter(x => txt.includes(x) || location.href.includes(x)),
        tail: txt.slice(-1200)
      };
    }
    """)


def click_product_all(page):
    loc = page.get_by_text('全部商品', exact=True)
    count = loc.count()
    if count <= 0:
        return {'ok': False, 'reason': 'not_found'}
    loc.nth(count - 1).click(timeout=8000)
    return {'ok': True, 'count': count}


def reset_product_all(page):
    page.goto('https://union.jd.com/proManager/index?pageNo=1', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(5000)
    before = page_info(page)
    if before.get('risk'):
        return {'ok': False, 'risk': before.get('risk'), 'info': before}
    click = click_product_all(page)
    page.wait_for_timeout(6000)
    page.evaluate("""() => { document.body.style.zoom='80%'; const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); else window.scrollTo(0, document.body.scrollHeight); }""")
    page.wait_for_timeout(1500)
    info = page_info(page)
    return {'ok': not bool(info.get('risk')), 'click_product_all': click, 'info': info, 'risk': info.get('risk')}


def jump_to(page, target_page):
    before = page_info(page)
    if before.get('risk'):
        return {'target_page': target_page, 'ok': False, 'risk': before.get('risk'), 'before': before, 'reason': 'risk_before_jump'}
    before_skus = before.get('skus') or []
    click_result = {'ok': False}
    try:
        page.evaluate("""() => { const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); }""")
        page.wait_for_timeout(800)
        inp = page.locator('.el-pagination .el-pagination__jump input, .el-pagination input.el-input__inner').first
        inp.scroll_into_view_if_needed(timeout=5000)
        inp.click(timeout=5000)
        inp.fill(str(target_page), timeout=5000)
        page.wait_for_timeout(300)
        inp.press('Enter', timeout=5000)
        click_result = {'ok': True, 'method': 'locator_fill_enter'}
    except Exception as e1:
        click_result = {'ok': False, 'method': 'locator_fill_enter', 'err': repr(e1)}
        try:
            js_res = page.evaluate("""
            (targetPage) => {
              const pager = document.querySelector('.el-pagination');
              if (!pager) return {ok:false, reason:'no_el_pagination'};
              const input = pager.querySelector('.el-pagination__jump input, input.el-input__inner');
              if (!input) return {ok:false, reason:'no_jump_input'};
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              input.scrollIntoView({block:'center', inline:'center'});
              input.focus();
              setter.call(input, String(targetPage));
              input.dispatchEvent(new Event('input', {bubbles:true}));
              input.dispatchEvent(new Event('change', {bubbles:true}));
              input.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true}));
              input.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true}));
              return {ok:true, method:'js_set_enter', value: input.value};
            }
            """, target_page)
            click_result = js_res
        except Exception as e2:
            click_result = {'ok': False, 'method': 'js_set_enter', 'err': repr(e2), 'previous': click_result}
    changed = False
    after = None
    for _ in range(60):
        page.wait_for_timeout(1000)
        after = page_info(page)
        if after.get('risk'):
            return {'target_page': target_page, 'click': click_result, 'changed': False, 'risk': after.get('risk'), 'before': before, 'after': after, 'reason': 'risk_after_jump'}
        after_skus = after.get('skus') or []
        active = str(after.get('activePageText') or '')
        url = str(after.get('url') or '')
        if after_skus and (after_skus[:40] != before_skus[:40] or active == str(target_page) or f'pageNo={target_page}' in url):
            changed = True
            break
    return {
        'target_page': target_page,
        'click': click_result,
        'changed': changed,
        'before': {'url': before.get('url'), 'activePageText': before.get('activePageText'), 'skuCount': before.get('skuCount'), 'skus': before_skus[:10]},
        'after': after,
        'ok': bool(changed and after and not after.get('risk')),
    }

report = {'ts': now(), 'phase': 'HZ15 jump-to-page 30/60 probe', 'targets': TARGETS, 'events': []}
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:19228', timeout=20000)
    pages = []
    for ctx in browser.contexts:
        pages.extend(ctx.pages)
    page = next((x for x in reversed(pages) if 'union.jd.com' in (x.url or '') or 'jd.com' in (x.url or '')), pages[-1])
    page.set_default_timeout(20000)
    page.set_viewport_size({'width': 1920, 'height': 1600})
    initial = page_info(page)
    report['initial'] = initial
    if initial.get('risk'):
        report['status'] = 'NEED_MANUAL_VERIFY_BEFORE_PROBE'
        report['decision'] = 'Current page is JD risk verification; manually verify in noVNC, then rerun.'
    else:
        reset = reset_product_all(page)
        report['reset'] = reset
        if reset.get('risk'):
            report['status'] = 'NEED_MANUAL_VERIFY_AFTER_RESET'
            report['decision'] = 'Risk page appeared after reset; manually verify and rerun.'
        else:
            for t in TARGETS:
                res = jump_to(page, t)
                report['events'].append(res)
                if res.get('risk'):
                    report['status'] = 'RISK_AFTER_JUMP'
                    report['decision'] = 'Jump triggered risk verification. Do not bypass; verify manually before next collector run.'
                    break
                page.wait_for_timeout(5000)
            else:
                report['status'] = 'OK' if all(x.get('ok') for x in report['events']) else 'PARTIAL_OR_FAILED'
                report['decision'] = 'If page 30/60 jumps are OK, next collector can use jump input to shard pages instead of sequential next-only crawling.'

OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
MD.write_text('# HZ15 Jump to Page 30/60 Probe\n\n' + f"- Generated at: {report['ts']}\n- status: {report.get('status')}\n- events: {[{'target':x.get('target_page'), 'ok':x.get('ok'), 'changed':x.get('changed'), 'risk':x.get('risk'), 'active':(x.get('after') or {}).get('activePageText'), 'url':(x.get('after') or {}).get('url')} for x in report.get('events', [])]}\n", encoding='utf-8')
print(json.dumps({'report': str(OUT), 'status': report.get('status'), 'events': [{'target': x.get('target_page'), 'ok': x.get('ok'), 'changed': x.get('changed'), 'risk': x.get('risk'), 'active': (x.get('after') or {}).get('activePageText'), 'url': (x.get('after') or {}).get('url'), 'skuCount': (x.get('after') or {}).get('skuCount')} for x in report.get('events', [])], 'decision': report.get('decision')}, ensure_ascii=False, indent=2), flush=True)
PY

  git add reports/hz15_jump_to_page_30_60_latest.json docs/ops/DL2_HZ15_JUMP_TO_PAGE_30_60.md
  git commit -m "docs: add HZ15 jump-to-page 30/60 probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz15_jump_to_page_30_60_latest.json"
  git status --short | head -n 60
fi
