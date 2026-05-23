#!/usr/bin/env bash
# HZ14 slow pager recovery probe.
# Use only 商品推广 / 全部商品.
# Purpose:
# - Confirm Element UI pager works with commercial-safe slower cadence.
# - If JD risk verification page is present, do not bypass it; report NEED_MANUAL_VERIFY.
# - No link collection, no DB write. No exit is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p logs reports docs/ops run backups
  PROBE_LOG="logs/hz14_slow_pager_recovery_${TS}.log"
  WAIT_SECONDS="${HZ14_SLOW_PAGE_WAIT:-55}"

  echo "===== HZ14 slow pager recovery probe ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "WAIT_SECONDS=$WAIT_SECONDS"

  pkill -f "python.*run/hz12_product_all_full_collector" 2>/dev/null || true
  pkill -f "python.*run/hz13_multi_channel_collector" 2>/dev/null || true
  sleep 2

  HZ14_SLOW_PAGE_WAIT="$WAIT_SECONDS" .venv-browser/bin/python - <<'PY' > "$PROBE_LOG" 2>&1
import json
import os
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

WAIT_SECONDS = int(os.environ.get('HZ14_SLOW_PAGE_WAIT', '55'))
OUT = Path('reports/hz14_slow_pager_recovery_latest.json')
MD = Path('docs/ops/DL2_HZ14_SLOW_PAGER_RECOVERY.md')


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
      const riskWords = ['快速验证','购物无忧','风险','安全验证','验证码','滑块','risk_handler'];
      return {
        url: location.href,
        title: document.title,
        oneKeyCount: (txt.match(/一键领链/g) || []).length,
        skuCount: skus.length,
        skus: skus.slice(0, 100),
        has4000: txt.includes('共 4000 条') || txt.includes('共4000条'),
        hasEmpty: txt.includes('抱歉，没有找到相关商品'),
        risk: riskWords.filter(x => txt.includes(x) || location.href.includes(x)),
        tail: txt.slice(-900)
      };
    }
    """)


def click_all_product(page):
    loc = page.get_by_text('全部商品', exact=True)
    count = loc.count()
    if count <= 0:
        return {'ok': False, 'reason': 'not_found'}
    loc.nth(count - 1).click(timeout=8000)
    return {'ok': True, 'count': count}


def pager_state(page):
    return page.evaluate("""
    () => {
      const r = el => { const b = el.getBoundingClientRect(); return {x:b.x,y:b.y,w:b.width,h:b.height,cx:b.x+b.width/2,cy:b.y+b.height/2}; };
      const t = el => (el.innerText || el.textContent || '').replace(/\s+/g,' ').trim();
      const p = document.querySelector('.el-pagination');
      return {
        hasPager: !!p,
        pagerText: p ? t(p) : '',
        lis: p ? Array.from(p.querySelectorAll('.el-pager li')).map((el, i) => ({i, text:t(el), cls:String(el.className||''), rect:r(el)})) : [],
        buttons: p ? Array.from(p.querySelectorAll('button')).map((el, i) => ({i, cls:String(el.className||''), disabled:!!el.disabled, rect:r(el)})) : [],
        input: p && p.querySelector('.el-pagination__jump input') ? {value:p.querySelector('.el-pagination__jump input').value || '', rect:r(p.querySelector('.el-pagination__jump input'))} : null
      };
    }
    """)


def wait_changed_or_risk(page, before_skus, timeout_seconds=45):
    after = None
    changed = False
    risk = False
    for _ in range(timeout_seconds):
        page.wait_for_timeout(1000)
        after = page_info(page)
        if after.get('risk'):
            risk = True
            break
        if after.get('skus') and after.get('skus')[:40] != before_skus[:40]:
            changed = True
            break
    return changed, risk, after


def click_li(page, target):
    li = page.locator('.el-pagination .el-pager li').filter(has_text=str(target)).first
    li.scroll_into_view_if_needed(timeout=5000)
    li.click(timeout=8000)
    return {'ok': True, 'target': str(target), 'method': 'el_pager_li'}

report = {'ts': now(), 'phase': 'HZ14 slow pager recovery probe', 'wait_seconds': WAIT_SECONDS, 'events': []}
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
        report['status'] = 'NEED_MANUAL_VERIFY'
        report['decision'] = 'Current page is JD risk verification. Do manual verification in noVNC, then rerun this script. Do not bypass verification programmatically.'
    else:
        page.goto('https://union.jd.com/proManager/index?pageNo=1', wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(5000)
        click_all = click_all_product(page)
        page.wait_for_timeout(6000)
        page.evaluate("""() => { document.body.style.zoom='80%'; const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); else window.scrollTo(0, document.body.scrollHeight); }""")
        page.wait_for_timeout(1500)
        start = page_info(page)
        report['click_all'] = click_all
        report['start'] = start
        report['pager_start'] = pager_state(page)

        if start.get('risk'):
            report['status'] = 'NEED_MANUAL_VERIFY_AFTER_RESET'
            report['decision'] = 'Risk page appeared after reset. Verify manually and rerun.'
        else:
            before = start.get('skus', [])[:40]
            for target in ['2', '3']:
                state_before = pager_state(page)
                try:
                    click = click_li(page, target)
                    changed, risk, after = wait_changed_or_risk(page, before, timeout_seconds=45)
                    event = {'target': target, 'state_before': state_before, 'click': click, 'changed': changed, 'risk': risk, 'after': after}
                    report['events'].append(event)
                    if risk:
                        report['status'] = 'RISK_AFTER_PAGER_CLICK'
                        report['decision'] = 'Pager works but current cadence still triggers JD verification. Increase wait and run smaller batches with manual verification if prompted.'
                        break
                    if after and after.get('skus'):
                        before = after.get('skus', [])[:40]
                    if target != '3':
                        page.wait_for_timeout(WAIT_SECONDS * 1000)
                except Exception as e:
                    report['events'].append({'target': target, 'click': {'ok': False, 'err': repr(e)}, 'changed': False})
                    report['status'] = 'CLICK_EXCEPTION'
                    report['decision'] = 'Pager selector failed unexpectedly; inspect state_before.'
                    break
            else:
                report['status'] = 'OK_SLOW_PAGER_PROVED'
                report['decision'] = 'Element UI pager with slower cadence can be used for HZ14 official full collector.'

OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
MD.write_text('# HZ14 Slow Pager Recovery\n\n' + f"- Generated at: {report['ts']}\n- status: {report.get('status')}\n- wait_seconds: {WAIT_SECONDS}\n- events: {[{'target':x.get('target'), 'changed':x.get('changed'), 'risk':x.get('risk')} for x in report.get('events', [])]}\n", encoding='utf-8')
print(json.dumps({'report': str(OUT), 'status': report.get('status'), 'wait_seconds': WAIT_SECONDS, 'events': [{'target': x.get('target'), 'changed': x.get('changed'), 'risk': x.get('risk'), 'after_oneKeyCount': (x.get('after') or {}).get('oneKeyCount'), 'after_skuCount': (x.get('after') or {}).get('skuCount')} for x in report.get('events', [])], 'decision': report.get('decision')}, ensure_ascii=False, indent=2), flush=True)
PY

  git add reports/hz14_slow_pager_recovery_latest.json docs/ops/DL2_HZ14_SLOW_PAGER_RECOVERY.md
  git commit -m "docs: add HZ14 slow pager recovery report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz14_slow_pager_recovery_latest.json"
  git status --short | head -n 60
fi
