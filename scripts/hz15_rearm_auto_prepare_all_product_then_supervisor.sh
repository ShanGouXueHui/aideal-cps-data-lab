#!/usr/bin/env bash
# HZ15 auto prepare all-product page, then re-arm daytime supervisor.
# Purpose:
# - Automate the simple UI adjustment: navigate/click 商品推广 -> 全部商品 -> 搜索全部商品.
# - Verify the current page is usable: 共4000条 + enough 商品/一键领链 + no risk markers.
# - Only after safe verification, archive run/hz14_STOP_REQUIRED.json and restart daytime supervisor.
# - No JD verification bypass. If risk_handler/京东验证 is detected, keep STOP and do not restart.
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
  PROBE_JSON="reports/hz15_rearm_auto_prepare_probe_latest.json"

  echo "===== HZ15 auto prepare all-product page then re-arm supervisor ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== auto prepare and probe browser page ====="
  .venv-browser/bin/python - <<'PY'
import json
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

out = Path('reports/hz15_rearm_auto_prepare_probe_latest.json')
risk_markers = ['risk_handler', '京东验证', '快速验证', '安全验证', '验证码', '滑块', '购物无忧']
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
    'actions': [],
}

def snapshot(page):
    return page.evaluate('''() => {
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
        text: txt.slice(0, 8000),
        oneKeyCount: (txt.match(/一键领链/g) || []).length,
        skuCount: skus.length,
        has4000: txt.includes('共 4000 条') || txt.includes('共4000条'),
        pagerText: pager ? (pager.innerText || pager.textContent || '').replace(/\s+/g, ' ').trim() : '',
        activePageText: active ? (active.innerText || active.textContent || '').replace(/\s+/g, '').trim() : null,
        jumpInputValue: input ? (input.value || '') : null
      }
    }''')

def click_exact_text(page, text):
    return page.evaluate('''(text) => {
      const nodes = Array.from(document.querySelectorAll('button,a,div,span,li'));
      function visible(el) {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
      }
      const candidates = nodes.filter(el => visible(el) && (el.innerText || el.textContent || '').trim() === text);
      if (!candidates.length) return {ok:false, count:0};
      const el = candidates[candidates.length - 1];
      el.scrollIntoView({block:'center', inline:'center'});
      el.click();
      return {ok:true, count:candidates.length, tag: el.tagName, className: String(el.className || '')};
    }''', text)

def click_contains_text(page, text):
    return page.evaluate('''(text) => {
      const nodes = Array.from(document.querySelectorAll('button,a,div,span'));
      function visible(el) {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
      }
      const candidates = nodes.filter(el => visible(el) && (el.innerText || el.textContent || '').trim().includes(text));
      if (!candidates.length) return {ok:false, count:0};
      const el = candidates[0];
      el.scrollIntoView({block:'center', inline:'center'});
      el.click();
      return {ok:true, count:candidates.length, tag: el.tagName, text: (el.innerText || el.textContent || '').trim().slice(0,50)};
    }''', text)

try:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://127.0.0.1:19228', timeout=15000)
        pages = []
        for ctx in browser.contexts:
            pages.extend(ctx.pages)
        page = None
        for pg in reversed(pages):
            if 'union.jd.com' in (pg.url or '') or 'cfe.m.jd.com' in (pg.url or ''):
                page = pg
                break
        if page is None and pages:
            page = pages[-1]
        if page is None:
            report['reason'] = 'no_active_page'
        else:
            page.set_default_timeout(12000)
            page.bring_to_front()
            info0 = snapshot(page)
            report['actions'].append({'initial_url': info0.get('url'), 'initial_pagerText': info0.get('pagerText'), 'initial_skuCount': info0.get('skuCount')})
            hay0 = '\n'.join([info0.get('url') or '', info0.get('title') or '', info0.get('text') or ''])
            risk0 = [m for m in risk_markers if m in hay0]
            if risk0:
                report.update({k: info0.get(k) for k in ['url','title','has4000','oneKeyCount','skuCount','pagerText','activePageText','jumpInputValue']})
                report['risk'] = risk0
                report['reason'] = 'risk_page_detected_before_prepare'
            else:
                if 'union.jd.com/proManager' not in (info0.get('url') or ''):
                    page.goto('https://union.jd.com/proManager/index', wait_until='domcontentloaded', timeout=30000)
                    report['actions'].append({'goto': 'https://union.jd.com/proManager/index'})
                    time.sleep(4)
                # Try to click left menu and the exact 全部商品 tab/button.
                for text in ['商品推广', '全部商品']:
                    try:
                        r = click_exact_text(page, text)
                        report['actions'].append({'click_exact': text, 'result': r})
                        time.sleep(3)
                    except Exception as e:
                        report['actions'].append({'click_exact': text, 'error': repr(e)})
                # Search/refresh the all-product list if the button exists.
                try:
                    r = click_contains_text(page, '搜索全部商品')
                    report['actions'].append({'click_contains': '搜索全部商品', 'result': r})
                    time.sleep(6)
                except Exception as e:
                    report['actions'].append({'click_contains': '搜索全部商品', 'error': repr(e)})
                # Scroll to trigger pagination/list DOM hydration, then back to top-ish.
                for y in [0, 900, 1800, 3000, 999999, 0]:
                    try:
                        page.evaluate('(y) => window.scrollTo(0, y)', y)
                        time.sleep(1.5)
                    except Exception:
                        pass
                # If still not 4000, reload once and re-click 全部商品/search.
                info1 = snapshot(page)
                if not info1.get('has4000'):
                    report['actions'].append({'reload_once': True, 'before_reload_pagerText': info1.get('pagerText')})
                    page.reload(wait_until='domcontentloaded', timeout=30000)
                    time.sleep(5)
                    try:
                        r = click_exact_text(page, '全部商品')
                        report['actions'].append({'after_reload_click_exact': '全部商品', 'result': r})
                        time.sleep(3)
                    except Exception as e:
                        report['actions'].append({'after_reload_click_exact': '全部商品', 'error': repr(e)})
                    try:
                        r = click_contains_text(page, '搜索全部商品')
                        report['actions'].append({'after_reload_click_contains': '搜索全部商品', 'result': r})
                        time.sleep(6)
                    except Exception as e:
                        report['actions'].append({'after_reload_click_contains': '搜索全部商品', 'error': repr(e)})
                    for y in [0, 1200, 2400, 999999, 0]:
                        try:
                            page.evaluate('(y) => window.scrollTo(0, y)', y)
                            time.sleep(1.5)
                        except Exception:
                            pass
                info = snapshot(page)
                hay = '\n'.join([info.get('url') or '', info.get('title') or '', info.get('text') or ''])
                risk = [m for m in risk_markers if m in hay]
                report.update({k: info.get(k) for k in ['url','title','has4000','oneKeyCount','skuCount','pagerText','activePageText','jumpInputValue']})
                report['risk'] = risk
                if risk:
                    report['reason'] = 'risk_page_detected_after_prepare'
                elif report['has4000'] and report['oneKeyCount'] >= 55 and report['skuCount'] >= 55 and '4000' in str(report.get('pagerText') or ''):
                    report['ok'] = True
                    report['reason'] = 'safe_all_product_4000_after_auto_prepare'
                else:
                    report['reason'] = 'not_safe_all_product_4000_after_auto_prepare'
except Exception as e:
    report['reason'] = 'probe_exception'
    report['error'] = repr(e)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
PY
  PREP_RC=$?

  SAFE="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/hz15_rearm_auto_prepare_probe_latest.json')
try:
  x=json.loads(p.read_text(encoding='utf-8'))
  print('true' if x.get('ok') else 'false')
except Exception:
  print('false')
PY
)"

  if [ "$SAFE" = "true" ]; then
    echo "===== safe page confirmed after auto prepare; archive STOP if exists ====="
    if [ -e run/hz14_STOP_REQUIRED.json ]; then
      mv -v run/hz14_STOP_REQUIRED.json "backups/hz14_STOP_REQUIRED.json.auto_prepared_${TS}" || true
    fi
    echo "===== restart daytime autostart supervisor ====="
    bash scripts/hz15_daytime_autostart_pages_40_67_no_reset_v6_strict_4000.sh
    REARM_RESULT=RESTARTED_SUPERVISOR
  else
    echo "===== auto prepare did not reach safe all-product 4000 page; keep STOP and do not restart ====="
    REARM_RESULT=NOT_RESTARTED_AUTO_PREPARE_FAILED
  fi

  git add "$PROBE_JSON"
  git commit -m "docs: add HZ15 auto prepare probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "PREP_RC=$PREP_RC"
  echo "SAFE=$SAFE"
  echo "REARM_RESULT=$REARM_RESULT"
  echo "PROBE=$PROBE_JSON"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
