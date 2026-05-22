#!/usr/bin/env bash
# HZ14 visible next page-number probe.
# Goal: use only 商品推广/全部商品 and click visible numeric pager buttons sequentially,
# e.g. 1 -> 2 -> 3, rather than URL pageNo, channel tabs, or hidden jump controls.
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
  PROBE_LOG="logs/hz14_visible_next_page_number_probe_${TS}.log"

  echo "===== HZ14 visible next page number probe ====="
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
OUT = Path('reports/hz14_visible_next_page_number_probe_latest.json')
MD = Path('docs/ops/DL2_HZ14_VISIBLE_NEXT_PAGE_NUMBER_PROBE.md')


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
      const cur = (() => {
        const m = txt.match(/共\s*4000\s*条[\s\S]{0,120}?([1-9]\d*)\s*前往/);
        return m ? m[1] : null;
      })();
      return {
        url: location.href,
        title: document.title,
        oneKeyCount: (txt.match(/一键领链/g) || []).length,
        skuCount: skus.length,
        skus: skus.slice(0, 100),
        hasEmpty: txt.includes('抱歉，没有找到相关商品'),
        has4000: txt.includes('共 4000 条') || txt.includes('共4000条'),
        tail: txt.slice(-1800),
        currentTextGuess: cur,
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


def page_numbers(page):
    return page.evaluate('''
    () => {
      const norm = s => (s || '').replace(/\s+/g, '').trim();
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
      const all = Array.from(document.querySelectorAll('button,a,span,div,li'));
      const candidates = all.map((el,idx)=>{
        const txt=norm(el.innerText||el.textContent);
        const cls=String(el.className||''); const r=rectOf(el);
        const parentText=[el.parentElement, el.parentElement?.parentElement, el.parentElement?.parentElement?.parentElement].filter(Boolean).map(x=>norm(x.innerText||x.textContent)).join('|').slice(0,700);
        const pagerLike = parentText.includes('上一页') || parentText.includes('下一页') || parentText.includes('前往') || parentText.includes('共4000') || parentText.includes('共 4000') || cls.includes('page') || cls.includes('pager') || cls.includes('pagination');
        const active = cls.includes('active') || cls.includes('checked') || cls.includes('selected') || cls.includes('current');
        return {el,idx,text:txt,cls:cls.slice(0,180),rect:r,visible:visible(el),pagerLike,parentText:parentText.slice(0,300),path:pathOf(el),active};
      }).filter(x => x.visible && /^\d+$/.test(x.text) && x.rect.w <= 120 && x.rect.h <= 90 && x.rect.y > window.innerHeight*0.35 && x.pagerLike);
      candidates.sort((a,b)=> (b.rect.y-a.rect.y) || (a.rect.x-b.rect.x));
      return candidates.map(x => ({idx:x.idx,text:x.text,cls:x.cls,rect:x.rect,parentText:x.parentText,path:x.path,active:x.active}));
    }
    ''')


def click_visible_number(page, target_text):
    return page.evaluate('''
    (targetText) => {
      const norm = s => (s || '').replace(/\s+/g, '').trim();
      const rectOf = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}; };
      const visible = el => { const r=el.getBoundingClientRect(); return r.width>0 && r.height>0 && r.top>-400 && r.top<window.innerHeight+400; };
      const all = Array.from(document.querySelectorAll('button,a,span,div,li'));
      const candidates = all.map((el,idx)=>{
        const txt=norm(el.innerText||el.textContent); const cls=String(el.className||''); const r=rectOf(el);
        const parentText=[el.parentElement, el.parentElement?.parentElement, el.parentElement?.parentElement?.parentElement].filter(Boolean).map(x=>norm(x.innerText||x.textContent)).join('|').slice(0,700);
        const pagerLike = parentText.includes('上一页') || parentText.includes('下一页') || parentText.includes('前往') || parentText.includes('共4000') || parentText.includes('共 4000') || cls.includes('page') || cls.includes('pager') || cls.includes('pagination');
        return {el,idx,text:txt,cls:cls.slice(0,180),rect:r,visible:visible(el),pagerLike,parentText:parentText.slice(0,260)};
      }).filter(x => x.visible && x.text === String(targetText) && x.rect.w <= 120 && x.rect.h <= 90 && x.rect.y > window.innerHeight*0.35 && x.pagerLike);
      candidates.sort((a,b)=> (b.rect.y-a.rect.y) || (a.rect.x-b.rect.x));
      if(!candidates.length) return {ok:false,reason:'visible_number_not_found',targetText};
      const t=candidates[0];
      t.el.scrollIntoView({block:'center', inline:'center'});
      t.el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true,cancelable:true,view:window}));
      t.el.click();
      return {ok:true,method:'click_visible_number',targetText,clicked:{idx:t.idx,text:t.text,cls:t.cls,rect:t.rect,parentText:t.parentText}};
    }
    ''', str(target_text))

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
    nums_start = page_numbers(page)
    results=[]
    last_skus=start.get('skus', [])[:40]
    # Click visible 2 then visible 3. This avoids hidden 13 and proves sequential page-number navigation.
    for target in ['2','3']:
        nums_before = page_numbers(page)
        click = click_visible_number(page, target)
        changed=False
        after=None
        for _ in range(30):
            page.wait_for_timeout(1000)
            after=info(page)
            if after.get('skus') and after.get('skus')[:40] != last_skus:
                changed=True
                break
        nums_after = page_numbers(page)
        results.append({'target':target,'nums_before':nums_before,'click':click,'changed':changed,'before_skus':last_skus[:10],'after':after,'nums_after':nums_after})
        if after and after.get('skus'):
            last_skus = after.get('skus')[:40]
    report={
        'ts':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'phase':'HZ14 visible next page-number probe',
        'click_product_all':click_all,
        'start':start,
        'nums_start':nums_start,
        'results':results,
        'decision':'If visible page-number clicks 2/3 change SKU lists, implement collector using visible next numeric page buttons across 1..67 for 商品推广/全部商品 only.'
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    MD.write_text('# HZ14 Visible Next Page Number Probe\n\n' + f"- Generated at: {report['ts']}\n- start oneKeyCount: {start.get('oneKeyCount')}\n- nums_start: {[x.get('text') for x in nums_start]}\n- changed: {[x.get('changed') for x in results]}\n", encoding='utf-8')
    print(json.dumps({'report':str(OUT),'click_product_all_ok':click_all.get('ok'),'start':{'oneKeyCount':start.get('oneKeyCount'),'skuCount':start.get('skuCount'),'has4000':start.get('has4000')},'nums_start':[x.get('text') for x in nums_start],'results':[{'target':x['target'],'click_ok':(x.get('click') or {}).get('ok'),'changed':x.get('changed'),'reason':(x.get('click') or {}).get('reason'),'after_skuCount':(x.get('after') or {}).get('skuCount'),'nums_after':[n.get('text') for n in x.get('nums_after', [])]} for x in results]}, ensure_ascii=False, indent=2), flush=True)
PY

  git add reports/hz14_visible_next_page_number_probe_latest.json docs/ops/DL2_HZ14_VISIBLE_NEXT_PAGE_NUMBER_PROBE.md
  git commit -m "docs: add HZ14 visible next page-number probe report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PROBE_LOG=$PROBE_LOG"
  echo "REPORT=reports/hz14_visible_next_page_number_probe_latest.json"
  git status --short | head -n 60
fi
