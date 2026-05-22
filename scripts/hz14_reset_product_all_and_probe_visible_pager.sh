#!/usr/bin/env bash
# HZ14 reset to 商品推广/全部商品 and probe visible pager buttons.
# No link collection, no DB write. No `exit` is used.
# Run on collector server 121.41.111.36 as user cpsdata:
#   cd ~/projects/aideal-cps-data-lab && git fetch origin main && git rebase origin/main && bash scripts/hz14_reset_product_all_and_probe_visible_pager.sh

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
  PROBE_LOG="logs/hz14_reset_product_all_visible_pager_${TS}.log"

  echo "===== HZ14 reset product_all and probe visible pager ====="
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
OUT = Path('reports/hz14_reset_product_all_visible_pager_latest.json')
MD = Path('docs/ops/DL2_HZ14_RESET_PRODUCT_ALL_VISIBLE_PAGER.md')

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
        title: document.title,
        oneKeyCount: (txt.match(/一键领链/g) || []).length,
        skuCount: skus.length,
        skus: skus.slice(0, 80),
        hasEmpty: txt.includes('抱歉，没有找到相关商品'),
        has4000: txt.includes('共 4000 条') || txt.includes('共4000条'),
        has67: txt.includes('67'),
        tail: txt.slice(-1600),
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
        .map((el,idx)=>{
          const r=rectOf(el); const txt=norm(el.innerText||el.textContent); const cls=String(el.className||'');
          const parentText=[el.parentElement, el.parentElement?.parentElement].filter(Boolean).map(x=>norm(x.innerText||x.textContent)).join('|').slice(0,500);
          return {el,idx,text:txt,cls:cls.slice(0,160),rect:r,visible:visible(el),parentText};
        })
        .filter(x => x.visible && x.text === '全部商品' && x.rect.y > 120 && x.rect.y < 420);
      // Prefer the channel tab row: rightmost exact 全部商品 in the tabs region.
      candidates.sort((a,b)=> (b.rect.x-a.rect.x) || (a.rect.y-b.rect.y));
      if (!candidates.length) return {ok:false, reason:'product_all_tab_not_found'};
      const t=candidates[0];
      t.el.scrollIntoView({block:'center', inline:'center'});
      t.el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true,cancelable:true,view:window}));
      t.el.click();
      return {ok:true, clicked:{idx:t.idx,text:t.text,cls:t.cls,rect:t.rect,parentText:t.parentText}};
    }
    ''')

def pager_snapshot(page):
    return page.evaluate('''
    () => {
      const norm = s => (s || '').replace(/\s+/g, ' ').trim();
      const compact = s => (s || '').replace(/\s+/g, '').trim();
      const rectOf = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}; };
      const visible = el => { const r=el.getBoundingClientRect(); return r.width>0 && r.height>0 && r.top>-400 && r.top<window.innerHeight+400; };
      const pathOf = el => {
        const parts=[]; let cur=el;
        for(let i=0; cur && cur.nodeType===1 && i<8; i++,cur=cur.parentElement){
          let part=cur.tagName.toLowerCase();
          if(cur.id) part+='#'+cur.id;
          const cls=String(cur.className||'').trim().split(/\s+/).filter(Boolean).slice(0,4).join('.');
          if(cls) part+='.'+cls;
          parts.push(part);
        }
        return parts.join(' < ');
      };
      const all = Array.from(document.querySelectorAll('button,a,span,div,li,input'));
      const mapped = all.map((el,idx)=>{
        const tag=el.tagName.toLowerCase();
        const txt = tag==='input' ? (el.value || el.placeholder || '') : norm(el.innerText || el.textContent);
        const cls=String(el.className||''); const c=compact(txt); const r=rectOf(el);
        const parentText=[el.parentElement, el.parentElement?.parentElement, el.parentElement?.parentElement?.parentElement].filter(Boolean).map(x=>norm(x.innerText||x.textContent)).join(' | ').slice(0,700);
        return {idx,tag,text:String(txt).slice(0,180),compactText:c.slice(0,180),cls:cls.slice(0,200),rect:r,visible:visible(el),path:pathOf(el),parentText};
      }).filter(x=>x.visible);
      const pagerLike = mapped.filter(x =>
        x.text.includes('上一页') || x.text.includes('下一页') || x.text.includes('前往') || x.text.includes('共') ||
        x.parentText.includes('上一页') || x.parentText.includes('下一页') || x.parentText.includes('前往') || x.parentText.includes('共 4000') || x.parentText.includes('共4000') ||
        x.cls.includes('pagination') || x.cls.includes('pager') || x.cls.includes('page') || x.cls.includes('next') || x.tag==='input'
      );
      const pageNumbers = mapped.filter(x => /^\d+$/.test(x.compactText) && x.rect.w <= 100 && x.rect.h <= 80 && x.rect.y > window.innerHeight*0.35);
      const exact13 = mapped.filter(x => x.compactText === '13' && x.rect.w <= 100 && x.rect.h <= 80);
      return {
        viewport:{w:window.innerWidth,h:window.innerHeight,dpr:window.devicePixelRatio,scrollY:window.scrollY,bodyScrollHeight:document.body.scrollHeight,bodyClientHeight:document.body.clientHeight,documentScrollHeight:document.documentElement.scrollHeight,documentClientHeight:document.documentElement.clientHeight},
        bodyTail:(document.body.innerText||'').slice(-1800),
        inputs:mapped.filter(x=>x.tag==='input'),
        pagerLike:pagerLike.slice(-300),
        pageNumbers:pageNumbers.slice(-180),
        exact13:exact13.slice(-60)
      };
    }
    ''')

def click_number(page, target):
    return page.evaluate('''
    (target) => {
      const norm = s => (s || '').replace(/\s+/g, '').trim();
      const rectOf = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}; };
      const visible = el => { const r=el.getBoundingClientRect(); return r.width>0 && r.height>0 && r.top>-400 && r.top<window.innerHeight+400; };
      const all = Array.from(document.querySelectorAll('button,a,span,div,li'));
      const candidates = all.map((el,idx)=>{
        const txt=norm(el.innerText||el.textContent); const cls=String(el.className||''); const r=rectOf(el);
        const parentText=[el.parentElement, el.parentElement?.parentElement, el.parentElement?.parentElement?.parentElement].filter(Boolean).map(x=>norm(x.innerText||x.textContent)).join('|').slice(0,700);
        const pagerLike = parentText.includes('上一页') || parentText.includes('下一页') || parentText.includes('前往') || parentText.includes('共4000') || parentText.includes('共 4000') || cls.includes('page') || cls.includes('pager') || cls.includes('pagination');
        return {el,idx,text:txt,cls:cls.slice(0,180),rect:r,visible:visible(el),pagerLike,parentText:parentText.slice(0,260)};
      }).filter(x => x.visible && x.text === String(target) && x.rect.w <= 100 && x.rect.h <= 80 && x.rect.y > window.innerHeight*0.35 && x.pagerLike);
      candidates.sort((a,b)=> (b.rect.y-a.rect.y) || (a.rect.x-b.rect.x));
      if(!candidates.length) return {ok:false,reason:'page_number_not_found',target,candidates:[]};
      const t=candidates[0];
      t.el.scrollIntoView({block:'center', inline:'center'});
      t.el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true,cancelable:true,view:window}));
      t.el.click();
      return {ok:true,method:'click_visible_page_number',target,clicked:{idx:t.idx,text:t.text,cls:t.cls,rect:t.rect,parentText:t.parentText}};
    }
    ''', target)

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
    # Ensure actual 全部商品 tab, not 超级补贴/other channel.
    click_all = click_product_all(page)
    page.wait_for_timeout(6000)
    for _ in range(10):
        cur = info(page)
        if cur['oneKeyCount'] > 0 and not cur['hasEmpty']:
            break
        page.wait_for_timeout(1000)
    # Large viewport + zoom-out; keep top product list visible and bottom pager more likely exposed.
    page.evaluate("""
    () => {
      document.body.style.zoom = '80%';
      window.scrollTo(0, document.body.scrollHeight);
    }
    """)
    page.wait_for_timeout(2000)
    before = info(page)
    snap_before = pager_snapshot(page)
    click13 = click_number(page, 13)
    changed=False
    after=None
    for _ in range(30):
        page.wait_for_timeout(1000)
        after=info(page)
        if after.get('skus') and before.get('skus') and after.get('skus')[:30] != before.get('skus')[:30]:
            changed=True
            break
    snap_after = pager_snapshot(page)
    report={
        'ts':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'phase':'HZ14 reset product_all visible pager probe',
        'click_product_all':click_all,
        'before':before,
        'snap_before_summary':{'inputs':len(snap_before.get('inputs') or []),'pageNumbers':len(snap_before.get('pageNumbers') or []),'exact13':len(snap_before.get('exact13') or []),'viewport':snap_before.get('viewport'),'bodyTail':snap_before.get('bodyTail')},
        'snap_before':snap_before,
        'click13':click13,
        'changed':changed,
        'after':after,
        'snap_after_summary':{'inputs':len(snap_after.get('inputs') or []),'pageNumbers':len(snap_after.get('pageNumbers') or []),'exact13':len(snap_after.get('exact13') or []),'viewport':snap_after.get('viewport')},
        'decision':'Use only 商品推广/全部商品. If click13 changed, implement all-pages collector by visible page numbers/jump controls. If pager still hidden, restart display to larger canvas or collect via current-page visible cards plus manual pager calibration.'
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    MD.write_text('# HZ14 Reset Product All Visible Pager\n\n' + f"- Generated at: {report['ts']}\n- before oneKeyCount: {before.get('oneKeyCount')}\n- before skuCount: {before.get('skuCount')}\n- before hasEmpty: {before.get('hasEmpty')}\n- pageNumbers: {len(snap_before.get('pageNumbers') or [])}\n- exact13: {len(snap_before.get('exact13') or [])}\n- click13: {click13}\n- changed: {changed}\n", encoding='utf-8')
    print(json.dumps({'report':str(OUT),'click_product_all_ok':click_all.get('ok'),'before':{'oneKeyCount':before.get('oneKeyCount'),'skuCount':before.get('skuCount'),'hasEmpty':before.get('hasEmpty'),'has4000':before.get('has4000')},'snap_before':{'inputs':len(snap_before.get('inputs') or []),'pageNumbers':len(snap_before.get('pageNumbers') or []),'exact13':len(snap_before.get('exact13') or []),'viewport':snap_before.get('viewport')},'click13':{'ok':click13.get('ok'),'reason':click13.get('reason')},'changed':changed}, ensure_ascii=False, indent=2), flush=True)
PY

  git add reports/hz14_reset_product_all_visible_pager_latest.json docs/ops/DL2_HZ14_RESET_PRODUCT_ALL_VISIBLE_PAGER.md
  git commit -m "docs: add HZ14 reset product-all visible pager report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz14_reset_product_all_visible_pager_latest.json"
  git status --short | head -n 60
fi
