#!/usr/bin/env bash
# HZ14 text-node page-number click probe.
# Use only 商品推广/全部商品. The pager text is exposed as combined text like 12345667,
# so this probe locates the text node containing that pager cluster, computes the client
# rect for character '2' and '3', clicks the center, and verifies SKU changes.
# No link collection, no DB write. No `exit` is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
  echo "HINT=请在杭州采集机 121.41.111.36 的 cpsdata 用户下执行。"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p logs reports docs/ops run backups
  PROBE_LOG="logs/hz14_textnode_page_number_click_${TS}.log"

  echo "===== HZ14 text-node page number click probe ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop collectors only, keep Chrome/noVNC ====="
  pkill -f "python.*run/hz12_product_all_full_collector" 2>/dev/null || true
  pkill -f "python.*run/hz13_multi_channel_collector" 2>/dev/null || true
  sleep 2

  .venv-browser/bin/python - <<'PY' > "$PROBE_LOG" 2>&1
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

CDP_PORT = 19228
OUT = Path('reports/hz14_textnode_page_number_click_latest.json')
MD = Path('docs/ops/DL2_HZ14_TEXTNODE_PAGE_NUMBER_CLICK.md')


def info(page):
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
        oneKeyCount: (txt.match(/一键领链/g) || []).length,
        skuCount: skus.length,
        skus: skus.slice(0, 100),
        hasEmpty: txt.includes('抱歉，没有找到相关商品'),
        has4000: txt.includes('共 4000 条') || txt.includes('共4000条'),
        tail: txt.slice(-1200),
        risk: ['验证码','安全验证','登录注册','请登录','风险','滑块'].filter(x => txt.includes(x))
      };
    }
    ''')


def click_product_all(page):
    return page.evaluate('''
    () => {
      const norm = s => (s || '').replace(/\s+/g, '').trim();
      const rectOf = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}; };
      const visible = el => { const r=el.getBoundingClientRect(); return r.width>0 && r.height>0 && r.top>-80 && r.top<window.innerHeight+120; };
      const candidates = Array.from(document.querySelectorAll('button,a,span,div,label'))
        .map((el,idx)=>{ const r=rectOf(el); return {el,idx,text:norm(el.innerText||el.textContent),cls:String(el.className||'').slice(0,160),rect:r,visible:visible(el)}; })
        .filter(x => x.visible && x.text === '全部商品' && x.rect.y > 120 && x.rect.y < 420)
        .sort((a,b)=> (b.rect.x-a.rect.x) || (a.rect.y-b.rect.y));
      if (!candidates.length) return {ok:false, reason:'product_all_tab_not_found'};
      const t=candidates[0];
      t.el.click();
      return {ok:true, clicked:{idx:t.idx,text:t.text,cls:t.cls,rect:t.rect}};
    }
    ''')


def textnode_targets(page):
    return page.evaluate('''
    () => {
      const rectObj = r => ({x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2});
      const pathOf = el => {
        const parts=[]; let cur=el;
        for(let i=0; cur && cur.nodeType===1 && i<8; i++,cur=cur.parentElement){
          let part=cur.tagName.toLowerCase();
          if(cur.id) part+='#'+cur.id;
          const cls=String(cur.className||'').trim().split(/\s+/).filter(Boolean).slice(0,5).join('.');
          if(cls) part+='.'+cls;
          parts.push(part);
        }
        return parts.join(' < ');
      };
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const out = [];
      let node;
      while ((node = walker.nextNode())) {
        const raw = node.nodeValue || '';
        const compact = raw.replace(/\s+/g, '').trim();
        if (!compact) continue;
        const parent = node.parentElement;
        if (!parent) continue;
        const parentText = (parent.innerText || parent.textContent || '').replace(/\s+/g,'').trim();
        const related = compact.includes('12345667') || parentText.includes('共4000条') || parentText.includes('前往页') || parentText.includes('上一页') || parentText.includes('下一页');
        if (!related) continue;
        const parentRect = parent.getBoundingClientRect();
        if (!(parentRect.width > 0 && parentRect.height > 0)) continue;
        const chars = [];
        for (const ch of ['1','2','3','4','5','6','67']) {
          const idx = compact.indexOf(ch);
          if (idx < 0) continue;
          // Map compact index back to raw index approximately.
          let rawIndex = -1;
          let seen = 0;
          for (let i=0; i<raw.length; i++) {
            if (/\s/.test(raw[i])) continue;
            if (seen === idx) { rawIndex = i; break; }
            seen++;
          }
          if (rawIndex < 0) continue;
          const range = document.createRange();
          try {
            range.setStart(node, rawIndex);
            range.setEnd(node, Math.min(raw.length, rawIndex + ch.length));
            const rects = Array.from(range.getClientRects()).map(rectObj).filter(r => r.w > 0 && r.h > 0);
            chars.push({ch, compactIndex:idx, rawIndex, rects});
          } catch (e) {
            chars.push({ch, compactIndex:idx, rawIndex, err:String(e)});
          }
        }
        out.push({raw:raw.slice(0,200), compact:compact.slice(0,200), parentText:parentText.slice(0,400), parentRect:rectObj(parentRect), parentClass:String(parent.className||'').slice(0,180), path:pathOf(parent), chars});
      }
      return {viewport:{w:window.innerWidth,h:window.innerHeight,scrollY:window.scrollY,bodyScrollHeight:document.body.scrollHeight,bodyClientHeight:document.body.clientHeight}, targets:out.slice(-80), bodyTail:(document.body.innerText||'').slice(-1200)};
    }
    ''')


def first_rect_for_char(targets, ch):
    best = []
    for t in targets.get('targets') or []:
        for c in t.get('chars') or []:
            if c.get('ch') == ch and c.get('rects'):
                for r in c['rects']:
                    # Prefer pager lower area.
                    score = r.get('y',0) + (100 if '12345667' in (t.get('compact') or '') else 0)
                    best.append((score, t, c, r))
    if not best:
        return None
    best.sort(key=lambda x: -x[0])
    return {'target': best[0][1], 'char': best[0][2], 'rect': best[0][3]}

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(f'http://127.0.0.1:{CDP_PORT}', timeout=20000)
    pages=[]
    for ctx in browser.contexts:
        pages.extend(ctx.pages)
    page = next((x for x in reversed(pages) if 'union.jd.com' in (x.url or '')), pages[-1])
    page.set_default_timeout(20000)
    page.set_viewport_size({'width': 1920, 'height': 1600})
    page.goto('https://union.jd.com/proManager/index?pageNo=1', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(5000)
    click_all = click_product_all(page)
    page.wait_for_timeout(6000)
    page.evaluate("""
    () => {
      document.body.style.zoom = '80%';
      window.scrollTo(0, document.body.scrollHeight);
    }
    """)
    page.wait_for_timeout(2000)
    start = info(page)
    targets = textnode_targets(page)
    results=[]
    last_skus=start.get('skus', [])[:40]
    for ch in ['2','3']:
        hit = first_rect_for_char(targets, ch)
        if not hit:
            results.append({'ch':ch,'hit':None,'changed':False,'reason':'no_char_rect'})
            continue
        r = hit['rect']
        page.mouse.click(float(r['cx']), float(r['cy']))
        changed=False
        after=None
        for _ in range(30):
            page.wait_for_timeout(1000)
            after=info(page)
            if after.get('skus') and after.get('skus')[:40] != last_skus:
                changed=True
                break
        results.append({'ch':ch,'hit':hit,'clicked_xy':{'x':r['cx'],'y':r['cy']},'changed':changed,'after':after})
        if after and after.get('skus'):
            last_skus=after.get('skus')[:40]
        # Refresh text targets after possible page change.
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)
        targets = textnode_targets(page)
    report={'ts':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'phase':'HZ14 text-node page-number click probe','click_product_all':click_all,'start':start,'targets':targets,'results':results,'decision':'If character rect clicks change SKU lists, implement collector using text-node Range rects for visible numeric pager.'}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    MD.write_text('# HZ14 Text-node Page Number Click\n\n' + f"- Generated at: {report['ts']}\n- start oneKeyCount: {start.get('oneKeyCount')}\n- target nodes: {len(targets.get('targets') or [])}\n- changed: {[x.get('changed') for x in results]}\n", encoding='utf-8')
    print(json.dumps({'report':str(OUT),'click_product_all_ok':click_all.get('ok'),'start':{'oneKeyCount':start.get('oneKeyCount'),'skuCount':start.get('skuCount'),'has4000':start.get('has4000')},'target_nodes':len(targets.get('targets') or []),'results':[{'ch':x.get('ch'),'has_hit':bool(x.get('hit')),'changed':x.get('changed'),'reason':x.get('reason'),'after_skuCount':(x.get('after') or {}).get('skuCount')} for x in results]}, ensure_ascii=False, indent=2), flush=True)
PY

  git add reports/hz14_textnode_page_number_click_latest.json docs/ops/DL2_HZ14_TEXTNODE_PAGE_NUMBER_CLICK.md
  git commit -m "docs: add HZ14 text-node page number click report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz14_textnode_page_number_click_latest.json"
  git status --short | head -n 60
fi
