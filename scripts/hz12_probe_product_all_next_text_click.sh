#!/usr/bin/env bash
# HZ12 product_all exact-text next click probe.
# It does not collect links and does not write production DB. It only tries to
# advance one page using the visible 下一页 text and verifies whether SKU list changes.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p logs reports docs/ops run
  PROBE_LOG="logs/hz12x_product_all_next_text_click_probe_${TS}.log"

  .venv-browser/bin/python - <<'PY' > "$PROBE_LOG" 2>&1
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

CDP_PORT = 19228
OUT = Path('reports/hz12x_product_all_next_text_click_probe_latest.json')
MD = Path('docs/ops/DL2_HZ12X_PRODUCT_ALL_NEXT_TEXT_CLICK_PROBE.md')

def get_skus(page):
    return page.evaluate('''
    () => {
      const txt = document.body.innerText || '';
      const matches = Array.from(txt.matchAll(/(?:item\.jd\.com\/(\d{5,})\.html|sku[=:： ]*(\d{5,}))/ig));
      const out = [];
      for (const m of matches) {
        const s = m[1] || m[2];
        if (s && !out.includes(s)) out.push(s);
      }
      // Fallback: infer from product links in DOM.
      for (const a of Array.from(document.querySelectorAll('a[href]'))) {
        const h = a.href || '';
        const mm = h.match(/\/(\d{5,})\.html/);
        if (mm && !out.includes(mm[1])) out.push(mm[1]);
      }
      return out.slice(0, 30);
    }
    ''')

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
    before = get_skus(page)
    before_text_tail = page.evaluate("() => (document.body.innerText || '').slice(-600)")

    candidates = page.evaluate('''
    () => {
      const norm = s => (s || '').replace(/\s+/g, '').trim();
      const cssPath = el => {
        const parts = [];
        let cur = el;
        for (let i=0; cur && cur.nodeType === 1 && i<7; i++, cur=cur.parentElement) {
          let part = cur.tagName.toLowerCase();
          if (cur.id) part += '#' + cur.id;
          const cls = String(cur.className || '').trim().split(/\s+/).filter(Boolean).slice(0,4).join('.');
          if (cls) part += '.' + cls;
          parts.push(part);
        }
        return parts.join(' < ');
      };
      return Array.from(document.querySelectorAll('button,a,span,div,li'))
        .map((el, idx) => { const r = el.getBoundingClientRect(); return {idx, tag:el.tagName.toLowerCase(), text:norm(el.innerText||el.textContent), cls:String(el.className||'').slice(0,120), visible:r.width>0&&r.height>0, rect:{x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}, path:cssPath(el)}; })
        .filter(x => x.text === '下一页' || x.text.includes('上一页下一页') || x.text.includes('上一页 下一页') || x.cls.includes('next'))
        .slice(-80);
    }
    ''')

    click_results = []
    changed = False
    after = []

    # Try Playwright exact text first; it often resolves text nodes inside spans better than raw DOM filters.
    try:
        loc = page.get_by_text('下一页', exact=True)
        count = loc.count()
        click_results.append({'method': 'get_by_text_exact_count', 'count': count})
        if count > 0:
            loc.last.click(timeout=5000)
            click_results.append({'method': 'get_by_text_exact_last_click', 'ok': True})
    except Exception as e:
        click_results.append({'method': 'get_by_text_exact_last_click', 'ok': False, 'err': repr(e)})

    for _ in range(15):
        page.wait_for_timeout(1000)
        after = get_skus(page)
        if after and after != before:
            changed = True
            break

    # If exact text did not work, try coordinate click on the smallest candidate whose visible text is exactly 下一页.
    if not changed:
        try:
            exact = [x for x in candidates if x.get('text') == '下一页' and x.get('visible')]
            exact.sort(key=lambda x: (x['rect']['w'] * x['rect']['h'], -x['rect']['y']))
            if exact:
                t = exact[0]
                page.mouse.click(t['rect']['cx'], t['rect']['cy'])
                click_results.append({'method': 'mouse_small_exact_text', 'ok': True, 'target': t})
                for _ in range(15):
                    page.wait_for_timeout(1000)
                    after = get_skus(page)
                    if after and after != before:
                        changed = True
                        break
            else:
                click_results.append({'method': 'mouse_small_exact_text', 'ok': False, 'reason': 'no_exact_candidate'})
        except Exception as e:
            click_results.append({'method': 'mouse_small_exact_text', 'ok': False, 'err': repr(e)})

    after_text_tail = page.evaluate("() => (document.body.innerText || '').slice(-600)")
    report = {
        'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'phase': 'HZ12X product_all next exact text click probe',
        'url': page.url,
        'changed': changed,
        'before_skus': before[:10],
        'after_skus': after[:10],
        'candidates': candidates,
        'click_results': click_results,
        'before_text_tail': before_text_tail,
        'after_text_tail': after_text_tail,
        'decision': 'If changed=true, use the successful method for v7 pager. If false, use category/search strategy instead of pager.'
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    MD.write_text('# HZ12X Product All Next Text Click Probe\n\n' + f"- Generated at: {report['ts']}\n- changed: {changed}\n- candidates: {len(candidates)}\n", encoding='utf-8')
    print(json.dumps({'report': str(OUT), 'changed': changed, 'candidates': len(candidates), 'click_results': click_results[-3:]}, ensure_ascii=False, indent=2))
PY

  git add reports/hz12x_product_all_next_text_click_probe_latest.json docs/ops/DL2_HZ12X_PRODUCT_ALL_NEXT_TEXT_CLICK_PROBE.md
  git commit -m "docs: add HZ12X next text click probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz12x_product_all_next_text_click_probe_latest.json"
  git status --short | head -n 60
fi
