#!/usr/bin/env bash
# HZ14 jump-input navigation probe.
# Purpose:
# - Direct URL pageNo was not reliable: pageNo changed in URL but SKU list often stayed same.
# - This script probes the real UI paginator: fill bottom page input and click 前往.
# - No link collection, no DB write.
# - Uses current Chrome/CDP 19228.
# No `exit` is used because the user's shell environment may logout on exit.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
  echo "HINT=请在杭州采集机 121.41.111.36 的 cpsdata 用户下执行；不要在生产机 deploy 用户下执行。"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p logs reports docs/ops run backups
  PROBE_LOG="logs/hz14_jump_input_probe_${TS}.log"

  echo "===== HZ14 jump input probe ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  .venv-browser/bin/python - <<'PY' > "$PROBE_LOG" 2>&1
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

CDP_PORT = 19228
OUT = Path('reports/hz14_jump_input_probe_latest.json')
MD = Path('docs/ops/DL2_HZ14_JUMP_INPUT_PROBE.md')
TARGET_PAGES = [13, 14, 20]


def get_info(page):
    return page.evaluate('''
    () => {
      const txt = document.body ? (document.body.innerText || '') : '';
      const skus = [];
      for (const a of Array.from(document.querySelectorAll('a[href]'))) {
        const h = a.href || '';
        const m = h.match(/\/(\d{5,})\.html/);
        if (m && !skus.includes(m[1])) skus.push(m[1]);
      }
      return {
        url: location.href,
        title: document.title,
        textLen: txt.length,
        oneKeyCount: (txt.match(/一键领链/g) || []).length,
        skuCount: skus.length,
        skus: skus.slice(0, 60),
        bodyTail: txt.slice(-1200),
        risk: ['验证码','安全验证','登录注册','请登录','风险','滑块'].filter(x => txt.includes(x))
      };
    }
    ''')


def probe_controls(page):
    return page.evaluate('''
    () => {
      const norm = s => (s || '').replace(/\s+/g, ' ').trim();
      const compact = s => (s || '').replace(/\s+/g, '').trim();
      const rectOf = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}; };
      const visible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.top > -200 && r.top < window.innerHeight + 240; };
      const pathOf = el => {
        const parts = [];
        let cur = el;
        for (let i=0; cur && cur.nodeType === 1 && i<8; i++, cur=cur.parentElement) {
          let part = cur.tagName.toLowerCase();
          if (cur.id) part += '#' + cur.id;
          const cls = String(cur.className || '').trim().split(/\s+/).filter(Boolean).slice(0,4).join('.');
          if (cls) part += '.' + cls;
          parts.push(part);
        }
        return parts.join(' < ');
      };
      const all = Array.from(document.querySelectorAll('button,a,span,div,li,input'));
      const mapped = all.map((el, idx) => {
        const tag = el.tagName.toLowerCase();
        const txt = tag === 'input' ? (el.value || el.placeholder || '') : norm(el.innerText || el.textContent);
        const cls = String(el.className || '');
        const aria = String(el.getAttribute('aria-label') || '');
        const type = String(el.getAttribute('type') || '');
        const r = rectOf(el);
        const c = compact(txt);
        return {idx, tag, text:String(txt).slice(0,160), compactText:c.slice(0,160), cls:cls.slice(0,180), aria, type, visible:visible(el), rect:r, path:pathOf(el)};
      }).filter(x => x.visible);
      return {
        inputs: mapped.filter(x => x.tag === 'input'),
        goButtons: mapped.filter(x => x.compactText === '前往'),
        numbers: mapped.filter(x => /^\d+$/.test(x.compactText) && x.rect.w <= 120 && x.rect.h <= 80).slice(-120),
        nextButtons: mapped.filter(x => x.compactText === '下一页' || x.cls.includes('next')).slice(-80),
        pagerLike: mapped.filter(x => x.text.includes('上一页') || x.text.includes('下一页') || x.text.includes('前往') || x.text.includes('选择页面') || /^\d+$/.test(x.compactText) || x.tag === 'input' || x.cls.includes('page') || x.cls.includes('pager') || x.cls.includes('pagination')).slice(-240),
        viewport: {w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio, scrollY: window.scrollY, bodyScrollHeight: document.body.scrollHeight, bodyClientHeight: document.body.clientHeight}
      };
    }
    ''')


def jump_by_input(page, target_page):
    return page.evaluate('''
    (targetPage) => {
      const norm = s => (s || '').replace(/\s+/g, '').trim();
      const rectOf = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}; };
      const visible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.top > -200 && r.top < window.innerHeight + 240; };
      const allInputs = Array.from(document.querySelectorAll('input')).map((el, idx) => ({el, idx, value: el.value || '', placeholder: el.placeholder || '', type: el.type || '', rect: rectOf(el), visible: visible(el), cls: String(el.className || '')})).filter(x => x.visible && x.rect.w <= 180 && x.rect.h <= 80);
      const allBtns = Array.from(document.querySelectorAll('button,a,span,div,li')).map((el, idx) => ({el, idx, text: norm(el.innerText || el.textContent), cls: String(el.className || ''), rect: rectOf(el), visible: visible(el)})).filter(x => x.visible && x.rect.w <= 160 && x.rect.h <= 90);
      const goBtns = allBtns.filter(x => x.text === '前往' || x.text === 'GO' || x.text === 'Go' || x.text === '确定' || x.text === '跳转');
      allInputs.sort((a,b) => (b.rect.y - a.rect.y) || (b.rect.x - a.rect.x));
      goBtns.sort((a,b) => (b.rect.y - a.rect.y) || (b.rect.x - a.rect.x));
      if (!allInputs.length) return {ok:false, reason:'no_visible_input', inputs: [], goButtons: goBtns.map(x => ({idx:x.idx,text:x.text,cls:x.cls.slice(0,120),rect:x.rect}))};
      let input = allInputs[0];
      let go = goBtns[0] || null;
      if (goBtns.length) {
        let best = null;
        for (const inp of allInputs) {
          for (const btn of goBtns) {
            const dy = Math.abs(inp.rect.cy - btn.rect.cy);
            const dx = Math.abs(inp.rect.cx - btn.rect.cx);
            const score = dy * 10 + dx;
            if (!best || score < best.score) best = {inp, btn, score};
          }
        }
        if (best) { input = best.inp; go = best.btn; }
      }
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      input.el.focus();
      input.el.select && input.el.select();
      setter.call(input.el, String(targetPage));
      input.el.dispatchEvent(new Event('input', {bubbles:true}));
      input.el.dispatchEvent(new Event('change', {bubbles:true}));
      if (go) {
        go.el.scrollIntoView({block:'center', inline:'center'});
        go.el.dispatchEvent(new MouseEvent('mouseover', {bubbles:true, cancelable:true, view:window}));
        go.el.click();
        return {ok:true, method:'input_go', targetPage, input:{idx:input.idx,value:input.value,placeholder:input.placeholder,type:input.type,cls:input.cls.slice(0,120),rect:input.rect}, go:{idx:go.idx,text:go.text,cls:go.cls.slice(0,120),rect:go.rect}};
      }
      input.el.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true}));
      input.el.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true}));
      return {ok:true, method:'input_enter', targetPage, input:{idx:input.idx,value:input.value,placeholder:input.placeholder,type:input.type,cls:input.cls.slice(0,120),rect:input.rect}, go:null};
    }
    ''', target_page)


with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(f'http://127.0.0.1:{CDP_PORT}', timeout=20000)
    pages = []
    for ctx in browser.contexts:
        pages.extend(ctx.pages)
    page = next((x for x in reversed(pages) if 'union.jd.com' in (x.url or '')), pages[-1])
    page.set_default_timeout(20000)
    page.set_viewport_size({'width': 1920, 'height': 1600})
    page.goto('https://union.jd.com/proManager/index?pageNo=1', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(5000)
    page.evaluate('() => window.scrollTo(0, document.body.scrollHeight)')
    page.wait_for_timeout(1200)
    before = get_info(page)
    controls_before = probe_controls(page)
    results = []
    last_skus = before['skus'][:20]
    for target in TARGET_PAGES:
        click = jump_by_input(page, target)
        changed = False
        after = None
        for _ in range(24):
            page.wait_for_timeout(1000)
            after = get_info(page)
            if after.get('skus') and after.get('skus')[:20] != last_skus:
                changed = True
                break
        controls_after = probe_controls(page)
        results.append({'target_page': target, 'click': click, 'changed': changed, 'before_skus': last_skus[:10], 'after': after, 'controls_after': {'inputs': controls_after.get('inputs', []), 'goButtons': controls_after.get('goButtons', []), 'numbers': controls_after.get('numbers', [])[-30:], 'viewport': controls_after.get('viewport')}})
        if after and after.get('skus'):
            last_skus = after['skus'][:20]
    report = {
        'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'phase': 'HZ14 jump input navigation probe',
        'before': before,
        'controls_before': controls_before,
        'results': results,
        'decision': 'If input_go/input_enter changes SKU lists, build jump-page collector. If inputs/go are not visible, continue resize/zoom or use exact page number click.'
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    MD.write_text('# HZ14 Jump Input Navigation Probe\n\n' + f"- Generated at: {report['ts']}\n- controls_before inputs: {len(controls_before.get('inputs') or [])}\n- goButtons: {len(controls_before.get('goButtons') or [])}\n- changed: {[x.get('changed') for x in results]}\n", encoding='utf-8')
    print(json.dumps({'report': str(OUT), 'before_oneKeyCount': before.get('oneKeyCount'), 'controls_before': {'inputs': len(controls_before.get('inputs') or []), 'goButtons': len(controls_before.get('goButtons') or []), 'numbers': len(controls_before.get('numbers') or [])}, 'results': [{'target_page': x['target_page'], 'changed': x['changed'], 'click_ok': (x['click'] or {}).get('ok'), 'method': (x['click'] or {}).get('method'), 'after_oneKeyCount': (x.get('after') or {}).get('oneKeyCount'), 'after_skuCount': (x.get('after') or {}).get('skuCount')} for x in results]}, ensure_ascii=False, indent=2), flush=True)
PY

  git add reports/hz14_jump_input_probe_latest.json docs/ops/DL2_HZ14_JUMP_INPUT_PROBE.md
  git commit -m "docs: add HZ14 jump input probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz14_jump_input_probe_latest.json"
  git status --short | head -n 60
fi
