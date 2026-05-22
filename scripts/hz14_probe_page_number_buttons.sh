#!/usr/bin/env bash
# HZ14 page-number button probe.
# Goal: verify real bottom pager number buttons, e.g. 13/14, can be clicked.
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
  PROBE_LOG="logs/hz14_page_number_buttons_probe_${TS}.log"

  echo "===== HZ14 page number buttons probe ====="
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
OUT = Path('reports/hz14_page_number_buttons_probe_latest.json')
MD = Path('docs/ops/DL2_HZ14_PAGE_NUMBER_BUTTONS_PROBE.md')
TARGETS = [13, 14]


def get_info(page):
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
        textLen: txt.length,
        oneKeyCount: (txt.match(/一键领链/g) || []).length,
        skuCount: skus.length,
        skus: skus.slice(0, 80),
        tail: txt.slice(-1600),
        risk: ['验证码','安全验证','登录注册','请登录','风险','滑块'].filter(x => txt.includes(x))
      };
    }
    ''')


def pager_snapshot(page):
    return page.evaluate('''
    () => {
      const norm = s => (s || '').replace(/\s+/g, ' ').trim();
      const compact = s => (s || '').replace(/\s+/g, '').trim();
      const rectOf = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}; };
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
      const visible = el => { const r=el.getBoundingClientRect(); return r.width>0 && r.height>0 && r.top>-250 && r.top<window.innerHeight+260; };
      const all = Array.from(document.querySelectorAll('button,a,span,div,li,input'));
      const mapped = all.map((el,idx)=>{
        const tag=el.tagName.toLowerCase();
        const txt = tag==='input' ? (el.value || el.placeholder || '') : norm(el.innerText || el.textContent);
        const cls=String(el.className||''); const c=compact(txt); const r=rectOf(el);
        const ancText = norm([el.parentElement, el.parentElement?.parentElement, el.parentElement?.parentElement?.parentElement].filter(Boolean).map(x=>x.innerText||x.textContent||'').join(' ')).slice(0,500);
        return {idx,tag,text:String(txt).slice(0,160),compactText:c.slice(0,160),cls:cls.slice(0,180),rect:r,visible:visible(el),path:pathOf(el),ancestorText:ancText};
      }).filter(x=>x.visible);
      const pagerContainers = mapped.filter(x =>
        x.text.includes('上一页') || x.text.includes('下一页') || x.text.includes('前往') ||
        x.ancestorText.includes('上一页') || x.ancestorText.includes('下一页') || x.ancestorText.includes('前往') ||
        x.cls.includes('pagination') || x.cls.includes('pager') || x.cls.includes('page')
      ).slice(-260);
      const pageNumbers = mapped.filter(x => /^\d+$/.test(x.compactText) && x.rect.w <= 90 && x.rect.h <= 70 && x.rect.y > window.innerHeight*0.35)
        .sort((a,b)=> (b.rect.y-a.rect.y) || (a.rect.x-b.rect.x));
      return {
        viewport:{w:window.innerWidth,h:window.innerHeight,dpr:window.devicePixelRatio,scrollY:window.scrollY,bodyScrollHeight:document.body.scrollHeight,bodyClientHeight:document.body.clientHeight},
        bodyTail:(document.body.innerText||'').slice(-1600),
        pagerContainers,
        pageNumbers:pageNumbers.slice(-160),
        targetNumbers: pageNumbers.filter(x => ['13','14','15','67','1','2'].includes(x.compactText)).slice(-80)
      };
    }
    ''')


def click_page_number(page, target):
    return page.evaluate('''
    (target) => {
      const norm = s => (s || '').replace(/\s+/g, '').trim();
      const rectOf = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}; };
      const visible = el => { const r=el.getBoundingClientRect(); return r.width>0 && r.height>0 && r.top>-250 && r.top<window.innerHeight+260; };
      const all = Array.from(document.querySelectorAll('button,a,span,div,li'));
      const candidates = all.map((el,idx)=>{
        const txt=norm(el.innerText||el.textContent);
        const cls=String(el.className||''); const r=rectOf(el);
        const parentText = [el.parentElement, el.parentElement?.parentElement, el.parentElement?.parentElement?.parentElement].filter(Boolean).map(x=>(x.innerText||x.textContent||'').replace(/\s+/g,'').trim()).join('|').slice(0,500);
        const pagerLike = parentText.includes('上一页') || parentText.includes('下一页') || parentText.includes('前往') || cls.includes('page') || cls.includes('pager') || cls.includes('pagination');
        return {el,idx,text:txt,cls:cls.slice(0,160),rect:r,visible:visible(el),pagerLike,parentText:parentText.slice(0,220)};
      }).filter(x => x.visible && x.text === String(target) && x.rect.w <= 90 && x.rect.h <= 70 && x.rect.y > window.innerHeight*0.35 && x.pagerLike);
      candidates.sort((a,b)=> (b.rect.y-a.rect.y) || (a.rect.x-b.rect.x));
      if(!candidates.length) return {ok:false,reason:'page_number_not_found',target,candidates:[]};
      const t=candidates[0];
      t.el.scrollIntoView({block:'center', inline:'center'});
      t.el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true,cancelable:true,view:window}));
      t.el.click();
      return {ok:true,method:'dom_click_page_number',target,clicked:{idx:t.idx,text:t.text,cls:t.cls,rect:t.rect,parentText:t.parentText}};
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
    # Bottom pager appears above the fixed batch bar in the user's screenshot. Keep viewport large and apply slight zoom-out.
    page.evaluate("""
    () => {
      document.body.style.zoom = '90%';
      window.scrollTo(0, document.body.scrollHeight);
    }
    """)
    page.wait_for_timeout(1500)
    before = get_info(page)
    snap_before = pager_snapshot(page)
    results=[]
    last_skus=before['skus'][:30]
    for target in TARGETS:
        click=click_page_number(page,target)
        changed=False
        after=None
        for _ in range(24):
            page.wait_for_timeout(1000)
            after=get_info(page)
            if after.get('skus') and after.get('skus')[:30] != last_skus:
                changed=True
                break
        snap_after=pager_snapshot(page)
        results.append({'target':target,'click':click,'changed':changed,'before_skus':last_skus[:10],'after':after,'snap_after_summary':{'pageNumbers':len(snap_after.get('pageNumbers') or []),'targetNumbers':snap_after.get('targetNumbers',[])[:30],'viewport':snap_after.get('viewport')}})
        if after and after.get('skus'):
            last_skus=after['skus'][:30]
    report={'ts':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'phase':'HZ14 page number buttons probe','before':before,'snap_before':snap_before,'results':results,'decision':'If page number button clicks change SKU lists, build collector over page number/jump controls instead of URL or next text.'}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    MD.write_text('# HZ14 Page Number Buttons Probe\n\n' + f"- Generated at: {report['ts']}\n- snap_before pageNumbers: {len(snap_before.get('pageNumbers') or [])}\n- snap_before targets: {len(snap_before.get('targetNumbers') or [])}\n- changed: {[x.get('changed') for x in results]}\n", encoding='utf-8')
    print(json.dumps({'report':str(OUT),'before_oneKeyCount':before.get('oneKeyCount'),'snap_before':{'pageNumbers':len(snap_before.get('pageNumbers') or []),'targetNumbers':len(snap_before.get('targetNumbers') or []),'viewport':snap_before.get('viewport')},'results':[{'target':x['target'],'click_ok':(x['click'] or {}).get('ok'),'changed':x['changed'],'reason':(x['click'] or {}).get('reason')} for x in results]}, ensure_ascii=False, indent=2), flush=True)
PY

  git add reports/hz14_page_number_buttons_probe_latest.json docs/ops/DL2_HZ14_PAGE_NUMBER_BUTTONS_PROBE.md
  git commit -m "docs: add HZ14 page number buttons probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz14_page_number_buttons_probe_latest.json"
  git status --short | head -n 60
fi
