#!/usr/bin/env bash
# HZ14 direct pageNo navigation probe.
# Purpose:
# - Verify https://union.jd.com/proManager/index?pageNo=N can directly jump pages.
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
  PROBE_LOG="logs/hz14_direct_pageno_probe_${TS}.log"

  echo "===== HZ14 direct pageNo probe ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  .venv-browser/bin/python - <<'PY' > "$PROBE_LOG" 2>&1
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

CDP_PORT = 19228
OUT = Path('reports/hz14_direct_pageno_probe_latest.json')
MD = Path('docs/ops/DL2_HZ14_DIRECT_PAGENO_PROBE.md')
PAGES = [1, 2, 13, 20, 67]
BASE_URL = 'https://union.jd.com/proManager/index?pageNo={page_no}'

def body_info(page):
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
        skus: skus.slice(0, 40),
        pagerTail: txt.slice(-900),
        risk: ['验证码','安全验证','登录注册','请登录','风险','滑块'].filter(x => txt.includes(x))
      };
    }
    ''')

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(f'http://127.0.0.1:{CDP_PORT}', timeout=20000)
    pages = []
    for ctx in browser.contexts:
        pages.extend(ctx.pages)
    page = next((x for x in reversed(pages) if 'union.jd.com' in (x.url or '')), pages[-1])
    page.set_default_timeout(20000)
    results = []
    for n in PAGES:
        url = BASE_URL.format(page_no=n)
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(5000)
            # Scroll bottom once so lazy product/pager state is materialized.
            page.evaluate('() => window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(1200)
            info = body_info(page)
            info['requested_page_no'] = n
            info['ok'] = info.get('oneKeyCount', 0) > 0 and not info.get('risk')
            results.append(info)
            print(json.dumps({'event':'PAGE_PROBE','page_no':n,'ok':info['ok'],'oneKeyCount':info['oneKeyCount'],'skuCount':info['skuCount'],'url':info['url'],'risk':info['risk']}, ensure_ascii=False), flush=True)
        except Exception as e:
            results.append({'requested_page_no': n, 'ok': False, 'err': repr(e)})
            print(json.dumps({'event':'PAGE_PROBE_FAIL','page_no':n,'err':repr(e)}, ensure_ascii=False), flush=True)
    sku_sets = {str(x.get('requested_page_no')): x.get('skus') or [] for x in results}
    unique_by_page = {}
    for k, v in sku_sets.items():
        unique_by_page[k] = len(set(v))
    changed = {}
    keys = list(sku_sets)
    for i in range(1, len(keys)):
        changed[f'{keys[i-1]}->{keys[i]}'] = bool(sku_sets[keys[i]] and sku_sets[keys[i]] != sku_sets[keys[i-1]])
    report = {
        'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'phase': 'HZ14 direct pageNo navigation probe',
        'pages': PAGES,
        'results': results,
        'unique_by_page': unique_by_page,
        'changed': changed,
        'decision': 'If pageNo direct navigation has ok=true and changed SKU lists for requested pages, use direct URL pageNo collector instead of clicking pager.'
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    MD.write_text('# HZ14 Direct pageNo Navigation Probe\n\n' + f"- Generated at: {report['ts']}\n- changed: {changed}\n- unique_by_page: {unique_by_page}\n", encoding='utf-8')
    print(json.dumps({'report': str(OUT), 'changed': changed, 'unique_by_page': unique_by_page, 'ok_pages': [x.get('requested_page_no') for x in results if x.get('ok')]}, ensure_ascii=False, indent=2), flush=True)
PY

  git add reports/hz14_direct_pageno_probe_latest.json docs/ops/DL2_HZ14_DIRECT_PAGENO_PROBE.md
  git commit -m "docs: add HZ14 direct pageNo probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz14_direct_pageno_probe_latest.json"
  git status --short | head -n 60
fi
