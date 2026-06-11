#!/usr/bin/env bash
# HZ15 re-arm helper after manual JD verification.
# Purpose:
# - The daytime supervisor exits when run/hz14_STOP_REQUIRED.json exists.
# - After you manually pass JD verification and return to 商品推广 / 全部商品 / 共4000条,
#   run this script. It probes the current browser DOM via CDP.
# - Only if the page is safe 4000-list, it archives STOP and restarts the daytime autostart supervisor.
# - If the browser is still on risk_handler / 京东验证, it keeps STOP and does not restart.
# No exit and no set -e are used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p backups logs reports docs/ops run data/import
  PROBE_JSON="reports/hz15_rearm_daytime_probe_latest.json"

  echo "===== HZ15 re-arm daytime supervisor after manual verification ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== probe current browser page ====="
  .venv-browser/bin/python - <<'PY'
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

out = Path('reports/hz15_rearm_daytime_probe_latest.json')
markers = ['risk_handler', '京东验证', '快速验证', '安全验证', '验证码', '滑块', '购物无忧']
report = {
    'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'ok': False,
    'reason': 'unknown',
    'url': None,
    'title': None,
    'has4000': False,
    'oneKeyCount': 0,
    'skuCount': 0,
    'pagerText': '',
    'activePageText': None,
    'jumpInputValue': None,
    'risk': [],
}
try:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://127.0.0.1:19228', timeout=15000)
        pages = []
        for ctx in browser.contexts:
            pages.extend(ctx.pages)
        page = pages[-1] if pages else None
        if page is None:
            report['reason'] = 'no_active_page'
        else:
            page.set_default_timeout(8000)
            info = page.evaluate('''() => {
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
                text: txt.slice(0, 5000),
                oneKeyCount: (txt.match(/一键领链/g) || []).length,
                skuCount: skus.length,
                has4000: txt.includes('共 4000 条') || txt.includes('共4000条'),
                pagerText: pager ? (pager.innerText || pager.textContent || '').replace(/\s+/g, ' ').trim() : '',
                activePageText: active ? (active.innerText || active.textContent || '').replace(/\s+/g, '').trim() : null,
                jumpInputValue: input ? (input.value || '') : null
              }
            }''')
            haystack = '\n'.join([info.get('url') or '', info.get('title') or '', info.get('text') or ''])
            risk = [m for m in markers if m in haystack]
            report.update({k: info.get(k) for k in ['url','title','has4000','oneKeyCount','skuCount','pagerText','activePageText','jumpInputValue']})
            report['risk'] = risk
            if risk:
                report['reason'] = 'risk_page_detected'
            elif report['has4000'] and report['oneKeyCount'] >= 55 and report['skuCount'] >= 55 and '4000' in str(report.get('pagerText') or ''):
                report['ok'] = True
                report['reason'] = 'safe_all_product_4000'
            else:
                report['reason'] = 'not_safe_all_product_4000'
except Exception as e:
    report['reason'] = 'probe_exception'
    report['error'] = repr(e)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
PY
  PROBE_RC=$?

  SAFE="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/hz15_rearm_daytime_probe_latest.json')
try:
  x=json.loads(p.read_text(encoding='utf-8'))
  print('true' if x.get('ok') else 'false')
except Exception:
  print('false')
PY
)"

  if [ "$SAFE" = "true" ]; then
    echo "===== safe page confirmed; archive STOP if exists ====="
    if [ -e run/hz14_STOP_REQUIRED.json ]; then
      mv -v run/hz14_STOP_REQUIRED.json "backups/hz14_STOP_REQUIRED.json.manual_verified_${TS}" || true
    fi
    echo "===== restart daytime autostart supervisor ====="
    bash scripts/hz15_daytime_autostart_pages_40_67_no_reset_v6_strict_4000.sh
    REARM_RESULT=RESTARTED_SUPERVISOR
  else
    echo "===== current browser page is not safe all-product 4000 page; keep STOP and do not restart ====="
    REARM_RESULT=NOT_RESTARTED_NEED_MANUAL_VERIFY
  fi

  git add "$PROBE_JSON"
  git commit -m "docs: add HZ15 rearm probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "PROBE_RC=$PROBE_RC"
  echo "SAFE=$SAFE"
  echo "REARM_RESULT=$REARM_RESULT"
  echo "PROBE=$PROBE_JSON"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
