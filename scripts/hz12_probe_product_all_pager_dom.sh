#!/usr/bin/env bash
# HZ12 product_all pager DOM probe. No collection, no production DB write.
# Run on collector server as cpsdata:
#   cd ~/projects/aideal-cps-data-lab && git fetch origin main && git rebase origin/main && bash scripts/hz12_probe_product_all_pager_dom.sh

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p logs reports docs/ops run
  PROBE_LOG="logs/hz12v_product_all_pager_dom_probe_${TS}.log"

  .venv-browser/bin/python - <<'PY' > "$PROBE_LOG" 2>&1
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

CDP_PORT = 19228
OUT = Path('reports/hz12v_product_all_pager_dom_probe_latest.json')
MD = Path('docs/ops/DL2_HZ12V_PRODUCT_ALL_PAGER_DOM_PROBE.md')

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
    page.evaluate('() => window.scrollTo(0, document.body.scrollHeight)')
    page.wait_for_timeout(1500)
    data = page.evaluate('''
    () => {
      const norm = s => (s || '').replace(/\s+/g, '').trim();
      const rectOf = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}; };
      const visible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.top >= -200 && r.top <= window.innerHeight + 300; };
      const all = Array.from(document.querySelectorAll('button,a,li,span,div,input'));
      const items = all.map((el, idx) => {
        const tag = el.tagName.toLowerCase();
        const txt = tag === 'input' ? (el.value || el.placeholder || '') : norm(el.innerText || el.textContent);
        const cls = String(el.className || '');
        const aria = String(el.getAttribute('aria-label') || '');
        const role = String(el.getAttribute('role') || '');
        const type = String(el.getAttribute('type') || '');
        const r = rectOf(el);
        return {idx, tag, txt: String(txt).slice(0,120), cls: cls.slice(0,160), aria, role, type, visible: visible(el), rect: r};
      }).filter(x => x.visible && (
        x.tag === 'input' || x.txt.includes('上一页') || x.txt.includes('下一页') || x.txt.includes('前往') || x.txt.includes('共') || x.txt === '>' || x.txt === '›' || x.cls.includes('page') || x.cls.includes('next') || x.cls.includes('pager') || x.aria.includes('页') || x.aria.toLowerCase().includes('next')
      ));
      return {
        url: location.href,
        title: document.title,
        innerWidth: window.innerWidth,
        innerHeight: window.innerHeight,
        scrollY: window.scrollY,
        bodyTextTail: (document.body.innerText || '').slice(-1200),
        pagerCandidates: items,
      };
    }
    ''')

report = {
    'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'phase': 'HZ12V product_all pager DOM probe',
    'data': data,
    'decision': 'Use this probe to build a precise pager jump/click selector. No data collection is performed.'
}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
MD.write_text('# HZ12V Product All Pager DOM Probe\n\n' + f"- Generated at: {report['ts']}\n- url: {data.get('url')}\n- candidates: {len(data.get('pagerCandidates') or [])}\n", encoding='utf-8')
print(json.dumps({'report': str(OUT), 'url': data.get('url'), 'candidates': len(data.get('pagerCandidates') or []), 'log': 'probe'}, ensure_ascii=False, indent=2))
PY

  git add reports/hz12v_product_all_pager_dom_probe_latest.json docs/ops/DL2_HZ12V_PRODUCT_ALL_PAGER_DOM_PROBE.md
  git commit -m "docs: add HZ12V pager DOM probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz12v_product_all_pager_dom_probe_latest.json"
  git status --short | head -n 60
fi
