#!/usr/bin/env bash
# HZ12 product_all scroll container + pager probe v2.
# No collection, no link click, no production DB write.
# It probes SPA scroll containers and all elements containing 上一页/下一页/前往.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p logs reports docs/ops run
  PROBE_LOG="logs/hz12w_product_all_scroll_pager_probe_v2_${TS}.log"

  .venv-browser/bin/python - <<'PY' > "$PROBE_LOG" 2>&1
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

CDP_PORT = 19228
OUT = Path('reports/hz12w_product_all_scroll_pager_probe_v2_latest.json')
MD = Path('docs/ops/DL2_HZ12W_PRODUCT_ALL_SCROLL_PAGER_PROBE_V2.md')

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(f'http://127.0.0.1:{CDP_PORT}', timeout=15000)
    pages = []
    for ctx in browser.contexts:
        pages.extend(ctx.pages)
    page = next((x for x in reversed(pages) if 'union.jd.com' in (x.url or '')), pages[-1])
    page.set_default_timeout(15000)
    if 'proManager/index' not in (page.url or ''):
        page.goto('https://union.jd.com/proManager/index?pageNo=1', wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(4000)

    data = page.evaluate('''
    () => {
      const norm = s => (s || '').replace(/\s+/g, ' ').trim();
      const compact = s => (s || '').replace(/\s+/g, '').trim();
      const rectOf = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}; };
      const isVisible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.top > -300 && r.top < window.innerHeight + 500; };
      const cssPath = el => {
        const parts = [];
        let cur = el;
        for (let i=0; cur && cur.nodeType === 1 && i<6; i++, cur=cur.parentElement) {
          let part = cur.tagName.toLowerCase();
          if (cur.id) part += '#' + cur.id;
          const cls = String(cur.className || '').trim().split(/\s+/).filter(Boolean).slice(0,3).join('.');
          if (cls) part += '.' + cls;
          parts.push(part);
        }
        return parts.join(' < ');
      };

      const all = Array.from(document.querySelectorAll('*'));
      const scrollables = all.map((el, idx) => {
        const r = rectOf(el);
        const style = window.getComputedStyle(el);
        const txt = norm(el.innerText || el.textContent || '');
        return {
          idx,
          tag: el.tagName.toLowerCase(),
          id: el.id || '',
          cls: String(el.className || '').slice(0,160),
          path: cssPath(el),
          rect: r,
          scrollTop: el.scrollTop || 0,
          scrollHeight: el.scrollHeight || 0,
          clientHeight: el.clientHeight || 0,
          overflowY: style.overflowY,
          visible: isVisible(el),
          textSample: txt.slice(0,240),
          textTail: txt.slice(-240),
          oneKeyCount: (txt.match(/一键领链/g) || []).length,
          hasPager: txt.includes('上一页') || txt.includes('下一页') || txt.includes('前往')
        };
      }).filter(x => x.scrollHeight > x.clientHeight + 40 || x.oneKeyCount > 5 || x.hasPager)
        .sort((a,b) => (b.oneKeyCount - a.oneKeyCount) || ((b.scrollHeight-b.clientHeight) - (a.scrollHeight-a.clientHeight)))
        .slice(0,80);

      const pagerElements = all.map((el, idx) => {
        const txt = norm(el.innerText || el.textContent || '');
        const c = compact(txt);
        return {
          idx,
          tag: el.tagName.toLowerCase(),
          id: el.id || '',
          cls: String(el.className || '').slice(0,180),
          role: String(el.getAttribute('role') || ''),
          aria: String(el.getAttribute('aria-label') || ''),
          type: String(el.getAttribute('type') || ''),
          disabled: !!el.disabled || el.getAttribute('disabled') !== null || String(el.className || '').includes('disabled') || el.getAttribute('aria-disabled') === 'true',
          visible: isVisible(el),
          rect: rectOf(el),
          text: txt.slice(0,300),
          compactText: c.slice(0,300),
          path: cssPath(el)
        };
      }).filter(x => x.text.includes('上一页') || x.text.includes('下一页') || x.text.includes('前往') || x.compactText === '>' || x.compactText === '›' || x.aria.includes('下一页') || x.cls.includes('next') || x.cls.includes('page') || x.tag === 'input')
        .slice(-200);

      const inputs = Array.from(document.querySelectorAll('input')).map((el, idx) => ({idx, value:el.value||'', placeholder:el.placeholder||'', type:el.type||'', cls:String(el.className||'').slice(0,120), visible:isVisible(el), rect:rectOf(el), path:cssPath(el)}));

      return {
        url: location.href,
        title: document.title,
        innerWidth: window.innerWidth,
        innerHeight: window.innerHeight,
        windowScroll: {x: window.scrollX, y: window.scrollY},
        body: {scrollTop: document.body.scrollTop, scrollHeight: document.body.scrollHeight, clientHeight: document.body.clientHeight, textTail: (document.body.innerText||'').slice(-1200)},
        documentElement: {scrollTop: document.documentElement.scrollTop, scrollHeight: document.documentElement.scrollHeight, clientHeight: document.documentElement.clientHeight},
        scrollables,
        pagerElements,
        inputs
      };
    }
    ''')

report = {
    'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'phase': 'HZ12W product_all scroll and pager probe v2',
    'data': data,
    'decision': 'Use scrollables and pagerElements to build exact product_all pagination/jump selector. No collection is performed.'
}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
MD.write_text('# HZ12W Product All Scroll/Pager Probe V2\n\n' + f"- Generated at: {report['ts']}\n- url: {data.get('url')}\n- scrollables: {len(data.get('scrollables') or [])}\n- pagerElements: {len(data.get('pagerElements') or [])}\n- inputs: {len(data.get('inputs') or [])}\n", encoding='utf-8')
print(json.dumps({'report': str(OUT), 'url': data.get('url'), 'scrollables': len(data.get('scrollables') or []), 'pagerElements': len(data.get('pagerElements') or []), 'inputs': len(data.get('inputs') or [])}, ensure_ascii=False, indent=2))
PY

  git add reports/hz12w_product_all_scroll_pager_probe_v2_latest.json docs/ops/DL2_HZ12W_PRODUCT_ALL_SCROLL_PAGER_PROBE_V2.md
  git commit -m "docs: add HZ12W scroll and pager DOM probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz12w_product_all_scroll_pager_probe_v2_latest.json"
  git status --short | head -n 60
fi
