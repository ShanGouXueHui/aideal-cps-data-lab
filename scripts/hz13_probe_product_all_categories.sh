#!/usr/bin/env bash
# HZ13 product_all category/filter expansion probe.
# Purpose: single product_all path is limited; this probes clickable category/channel/filter texts
# without collecting links or writing production DB.
# No `exit` is used.

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
  PROBE_LOG="logs/hz13_product_all_categories_probe_${TS}.log"

  .venv-browser/bin/python - <<'PY' > "$PROBE_LOG" 2>&1
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

CDP_PORT = 19228
OUT = Path('reports/hz13_product_all_categories_probe_latest.json')
MD = Path('docs/ops/DL2_HZ13_PRODUCT_ALL_CATEGORY_EXPANSION_PROBE.md')

# Candidate terms observed in JD Union product pages. We only probe visibility/counts.
TERMS = [
    '全部商品', '超级补贴', '限量高佣', '秒杀专区', '定向高佣', '粉丝爱买',
    '食品酒水', '家庭清洁', '个护美妆', '医药保健', '生鲜', '数码家电',
    '家居日用', '时尚生活', '母婴', '宠物用品', '玩具', '粮油调味'
]

def get_skus_and_text(page):
    return page.evaluate('''
    () => {
      const txt = document.body.innerText || '';
      const skus = [];
      for (const a of Array.from(document.querySelectorAll('a[href]'))) {
        const h = a.href || '';
        const mm = h.match(/\/(\d{5,})\.html/);
        if (mm && !skus.includes(mm[1])) skus.push(mm[1]);
      }
      const oneKeyCount = (txt.match(/一键领链/g) || []).length;
      return {skus: skus.slice(0, 80), textLen: txt.length, textHead: txt.slice(0,1000), textTail: txt.slice(-1000), oneKeyCount};
    }
    ''')

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(f'http://127.0.0.1:{CDP_PORT}', timeout=15000)
    pages = []
    for ctx in browser.contexts:
        pages.extend(ctx.pages)
    page = next((x for x in reversed(pages) if 'union.jd.com' in (x.url or '')), pages[-1])
    page.set_default_timeout(15000)
    page.goto('https://union.jd.com/proManager/index?pageNo=1', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(5000)

    base_info = get_skus_and_text(page)
    term_results = []
    for term in TERMS:
        item = {'term': term, 'count': 0, 'click_ok': False, 'changed': False, 'oneKeyCount': None, 'skus': [], 'err': None}
        try:
            loc = page.get_by_text(term, exact=True)
            item['count'] = loc.count()
            if item['count'] > 0:
                before = get_skus_and_text(page)['skus'][:10]
                loc.first.click(timeout=5000)
                page.wait_for_timeout(3500)
                after_info = get_skus_and_text(page)
                after = after_info['skus'][:10]
                item['click_ok'] = True
                item['changed'] = bool(after and after != before)
                item['oneKeyCount'] = after_info['oneKeyCount']
                item['skus'] = after_info['skus'][:20]
        except Exception as e:
            item['err'] = repr(e)
        term_results.append(item)

    # DOM map for clickable visible terms.
    dom = page.evaluate('''
    () => {
      const norm = s => (s || '').replace(/\s+/g, ' ').trim();
      const rectOf = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}; };
      const pathOf = el => {
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
        .map((el, idx) => { const r = rectOf(el); return {idx, tag:el.tagName.toLowerCase(), text:norm(el.innerText || el.textContent).slice(0,120), cls:String(el.className||'').slice(0,160), rect:r, visible:r.width>0&&r.height>0&&r.top>-100&&r.top<window.innerHeight+100, path:pathOf(el)}; })
        .filter(x => x.visible && x.text && x.text.length <= 80)
        .slice(0,500);
    }
    ''')

report = {
    'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'phase': 'HZ13 product_all category/filter expansion probe',
    'url': page.url,
    'base': base_info,
    'term_results': term_results,
    'dom_clickables': dom,
    'decision': 'If category/channel clicks change SKU lists, build HZ13 collector over these terms; otherwise switch to query/search keyword expansion.'
}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
MD.write_text('# HZ13 Product All Category Expansion Probe\n\n' + f"- Generated at: {report['ts']}\n- url: {page.url}\n- base_one_key_count: {base_info.get('oneKeyCount')}\n- terms: {len(term_results)}\n", encoding='utf-8')
print(json.dumps({'report': str(OUT), 'base_one_key_count': base_info.get('oneKeyCount'), 'terms': len(term_results), 'changed_terms': [x['term'] for x in term_results if x.get('changed')]}, ensure_ascii=False, indent=2))
PY

  git add reports/hz13_product_all_categories_probe_latest.json docs/ops/DL2_HZ13_PRODUCT_ALL_CATEGORY_EXPANSION_PROBE.md
  git commit -m "docs: add HZ13 category expansion probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz13_product_all_categories_probe_latest.json"
  git status --short | head -n 60
fi
