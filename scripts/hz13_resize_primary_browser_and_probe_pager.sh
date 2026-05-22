#!/usr/bin/env bash
# HZ13 resize primary browser stack and probe full pager controls.
# Purpose:
# - Stop collectors only.
# - Restart primary Xvfb/noVNC/Chrome A with larger display so bottom pager, page numbers,
#   jump input, and 前往 button can be visible in noVNC and DOM.
# - Keep the same Chrome profile and CDP port 19228.
# - Probe pager DOM after resize and push report to GitHub.
# No `exit` is used because the user's shell environment may logout on exit.
# Run on collector server 121.41.111.36 as user cpsdata:
#   cd ~/projects/aideal-cps-data-lab && git fetch origin main && git rebase origin/main && bash scripts/hz13_resize_primary_browser_and_probe_pager.sh

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
  echo "HINT=请在杭州采集机 121.41.111.36 的 cpsdata 用户下执行；不要在生产机 deploy 用户下执行。"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p logs reports docs/ops run .secrets backups

  DISPLAY_ID=":79"
  RFB_PORT="59072"
  NOVNC_PORT="18772"
  CDP_PORT="19228"
  WIDTH="1920"
  HEIGHT="1600"
  PROFILE_DIR="${PROJECT_DIR}/.secrets/jd_union_public_manual_profile"
  CHROME_BIN="/usr/bin/google-chrome"
  PROBE_LOG="logs/hz13_resize_probe_pager_${TS}.log"

  echo "===== HZ13 resize primary browser and probe pager ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop collectors only ====="
  pkill -f "python.*run/hz12_product_all_full_collector" 2>/dev/null || true
  pkill -f "python.*run/hz13_multi_channel_collector" 2>/dev/null || true
  sleep 2

  echo "===== stop primary browser stack :79 / 19228 / 18772 only ====="
  pkill -f "chrome.*remote-debugging-port=${CDP_PORT}" 2>/dev/null || true
  pkill -f "Xvfb ${DISPLAY_ID}" 2>/dev/null || true
  pkill -f "x11vnc.*${RFB_PORT}" 2>/dev/null || true
  pkill -f "websockify.*${NOVNC_PORT}" 2>/dev/null || true
  pkill -f "fluxbox.*${DISPLAY_ID}" 2>/dev/null || true
  sleep 3

  echo "===== start Xvfb ${DISPLAY_ID} ${WIDTH}x${HEIGHT} ====="
  Xvfb "$DISPLAY_ID" -screen 0 "${WIDTH}x${HEIGHT}x24" > "logs/hz13_xvfb_${TS}.log" 2>&1 &
  sleep 1

  echo "===== start fluxbox ====="
  DISPLAY="$DISPLAY_ID" fluxbox > "logs/hz13_fluxbox_${TS}.log" 2>&1 &
  sleep 1

  echo "===== start x11vnc protected if password exists ====="
  if [ -f .secrets/x11vnc.pass ]; then
    x11vnc -display "$DISPLAY_ID" -rfbport "$RFB_PORT" -forever -shared -rfbauth .secrets/x11vnc.pass > "logs/hz13_x11vnc_${TS}.log" 2>&1 &
  else
    x11vnc -display "$DISPLAY_ID" -rfbport "$RFB_PORT" -forever -shared -nopw > "logs/hz13_x11vnc_${TS}.log" 2>&1 &
  fi
  sleep 1

  echo "===== start noVNC ${NOVNC_PORT} ====="
  /usr/bin/websockify --web=/usr/share/novnc "0.0.0.0:${NOVNC_PORT}" "localhost:${RFB_PORT}" > "logs/hz13_websockify_${TS}.log" 2>&1 &
  sleep 1

  echo "===== start Chrome A ${WIDTH}x${HEIGHT} CDP ${CDP_PORT} ====="
  DISPLAY="$DISPLAY_ID" "$CHROME_BIN" \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --window-size="${WIDTH},${HEIGHT}" \
    --start-maximized \
    --lang=zh-CN \
    --user-data-dir="$PROFILE_DIR" \
    --remote-debugging-address=127.0.0.1 \
    --remote-debugging-port="$CDP_PORT" \
    --disable-blink-features=AutomationControlled \
    "https://union.jd.com/proManager/index?pageNo=1" > "logs/hz13_chrome_${TS}.log" 2>&1 &
  sleep 8

  echo "===== probe pager after resize ====="
  .venv-browser/bin/python - <<'PY' > "$PROBE_LOG" 2>&1
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

CDP_PORT = 19228
OUT = Path('reports/hz13_resized_pager_probe_latest.json')
MD = Path('docs/ops/DL2_HZ13_RESIZED_PAGER_PROBE.md')

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
    data = page.evaluate('''
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
      const items = all.map((el, idx) => {
        const tag = el.tagName.toLowerCase();
        const txt = tag === 'input' ? (el.value || el.placeholder || '') : norm(el.innerText || el.textContent);
        const cls = String(el.className || '');
        const aria = String(el.getAttribute('aria-label') || '');
        const role = String(el.getAttribute('role') || '');
        const type = String(el.getAttribute('type') || '');
        const disabled = !!el.disabled || el.getAttribute('disabled') !== null || cls.includes('disabled') || cls.includes('is-disabled') || el.getAttribute('aria-disabled') === 'true';
        const r = rectOf(el);
        const c = compact(txt);
        return {idx, tag, text:String(txt).slice(0,160), compactText:c.slice(0,160), cls:cls.slice(0,180), aria, role, type, disabled, visible:visible(el), rect:r, path:pathOf(el)};
      }).filter(x => x.visible && (
        x.tag === 'input' ||
        x.text.includes('上一页') || x.text.includes('下一页') || x.text.includes('前往') || x.text.includes('选择页面') || x.text.includes('/67') || x.text.includes('67') ||
        x.compactText === '>' || x.compactText === '›' || /^\d+$/.test(x.compactText) ||
        x.cls.includes('page') || x.cls.includes('pager') || x.cls.includes('next') || x.cls.includes('pagination') || x.aria.includes('页')
      ));
      return {
        url: location.href,
        title: document.title,
        innerWidth: window.innerWidth,
        innerHeight: window.innerHeight,
        dpr: window.devicePixelRatio,
        scroll: {x: window.scrollX, y: window.scrollY},
        body: {scrollHeight: document.body.scrollHeight, clientHeight: document.body.clientHeight, textTail:(document.body.innerText || '').slice(-1600)},
        documentElement: {scrollHeight: document.documentElement.scrollHeight, clientHeight: document.documentElement.clientHeight},
        oneKeyCount: ((document.body.innerText || '').match(/一键领链/g) || []).length,
        pagerLike: items.slice(-240),
        inputs: items.filter(x => x.tag === 'input'),
        exactNumbers: items.filter(x => /^\d+$/.test(x.compactText)).slice(-120),
        nextButtons: items.filter(x => x.text.replace(/\s+/g,'').trim() === '下一页' || x.cls.includes('next')).slice(-80),
        goButtons: items.filter(x => x.text.replace(/\s+/g,'').trim() === '前往').slice(-40)
      };
    }
    ''')

report = {
    'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'phase': 'HZ13 resized primary browser pager probe',
    'data': data,
    'decision': 'If inputs/goButtons/exactNumbers are visible, implement page number/jump navigation; otherwise continue channel expansion.'
}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
MD.write_text('# HZ13 Resized Pager Probe\n\n' + f"- Generated at: {report['ts']}\n- viewport: {data.get('innerWidth')}x{data.get('innerHeight')}\n- oneKeyCount: {data.get('oneKeyCount')}\n- inputs: {len(data.get('inputs') or [])}\n- numbers: {len(data.get('exactNumbers') or [])}\n- nextButtons: {len(data.get('nextButtons') or [])}\n- goButtons: {len(data.get('goButtons') or [])}\n", encoding='utf-8')
print(json.dumps({'report': str(OUT), 'viewport': f"{data.get('innerWidth')}x{data.get('innerHeight')}", 'oneKeyCount': data.get('oneKeyCount'), 'inputs': len(data.get('inputs') or []), 'numbers': len(data.get('exactNumbers') or []), 'nextButtons': len(data.get('nextButtons') or []), 'goButtons': len(data.get('goButtons') or [])}, ensure_ascii=False, indent=2))
PY

  echo "===== commit and push resized pager probe ====="
  git add reports/hz13_resized_pager_probe_latest.json docs/ops/DL2_HZ13_RESIZED_PAGER_PROBE.md
  git commit -m "docs: add HZ13 resized pager probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== process/port check ====="
  pgrep -af "Xvfb :79|x11vnc.*59072|websockify.*18772|chrome.*19228|hz12_product_all_full_collector|hz13_multi_channel_collector" | head -n 100 || true
  ss -lntp 2>/dev/null | grep -E ':18772|:59072|:19228' || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz13_resized_pager_probe_latest.json"
  echo "NOVNC_URL=http://121.41.111.36:18772/vnc.html"
  git status --short | head -n 60
fi
