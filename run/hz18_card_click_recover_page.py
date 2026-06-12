#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, os, random, time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List

MOD_PATH=Path('run/hz15_jump_pages_collector_v6_no_reset_strict_4000.py')
REPORT=Path('reports/hz18_card_click_recover_latest.json')
PAGE_SEQUENCE=os.environ.get('HZ18_PAGE_SEQUENCE','49')
LIMIT=int(os.environ.get('HZ18_LIMIT','20'))
WAIT=int(os.environ.get('HZ18_WAIT','8'))
FAIL_FUSE=int(os.environ.get('HZ18_FAIL_FUSE','5'))
ITEM_SLEEP_MIN=float(os.environ.get('HZ18_ITEM_SLEEP_MIN','1'))
ITEM_SLEEP_MAX=float(os.environ.get('HZ18_ITEM_SLEEP_MAX','3'))
RISK=['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧']

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def log(event, **kw): print(json.dumps({'ts':now(),'worker':'hz18_card_click','event':event,**kw},ensure_ascii=False,sort_keys=True),flush=True)
def load_mod():
    spec=importlib.util.spec_from_file_location('hz15v6', str(MOD_PATH)); m=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(m); return m
m=load_mod(); hz15=m.hz15; core=m.core; base=m.base

def pages(s:str)->List[int]:
    out=[]
    for p in s.split(','):
        p=p.strip()
        if not p: continue
        if '-' in p:
            a,b=p.split('-',1); out.extend(range(int(a),int(b)+1))
        else: out.append(int(p))
    return [x for x in out if 1<=x<=core.PAGE_MAX]

def body(page):
    try: return page.evaluate("() => document.body ? (document.body.innerText || '') : ''")
    except Exception: return ''
def risk(page):
    hay='\n'.join([page.url or '', body(page)])
    return [x for x in RISK if x in hay]
def snapshot(page):
    info=m.v5.raw_page_info(page)
    return {k:info.get(k) for k in ['url','title','activePageText','oneKeyCount','skuCount','has4000','hasEmpty','pagerText','jumpInputValue','risk']}

def ensure_page(page, page_no:int)->Dict[str,Any]:
    usable=m.current_all_product_4000_usable(page)
    if not usable.get('usable'):
        return {'ok':False,'reason':'not_all_product_4000','info':usable.get('info')}
    if str((usable.get('info') or {}).get('activePageText') or '')==str(page_no):
        return {'ok':True,'mode':'already_on_page','info':usable.get('info')}
    time.sleep(random.uniform(1,3))
    j=hz15.jump_to_page(page,page_no)
    if not j.get('ok'): return {'ok':False,'reason':'jump_failed','jump':j}
    return {'ok':True,'mode':'jumped','jump':j,'info':snapshot(page)}

def parse_modal(page):
    try: return dict(base.parse_modal(page))
    except Exception as e: return {'parse_error':repr(e)}

def link_dates():
    c=datetime.now(); return c.isoformat(timespec='seconds'),(c+timedelta(days=60)).isoformat(timespec='seconds'),(c+timedelta(days=40)).isoformat(timespec='seconds')

def card_click(page, sku:str, title:str)->Dict[str,Any]:
    return page.evaluate("""
    ({sku,title}) => {
      const norm=s=>(s||'').replace(/\s+/g,' ').trim();
      const compact=s=>(s||'').replace(/\s+/g,'').trim();
      const titleKey=compact(title).slice(0,18);
      const candidates=[];
      const buttons=Array.from(document.querySelectorAll('button,a,span,div'))
        .map((el,idx)=>{const r=el.getBoundingClientRect();return {el,idx,txt:compact(el.innerText||el.textContent),visible:r.width>0&&r.height>0&&r.top>=-200&&r.left>=-100&&r.top<=window.innerHeight+1200,rect:{x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}}})
        .filter(x=>x.visible && x.txt==='一键领链');
      for (const b of buttons) {
        let cur=b.el, root=null;
        for (let d=0; d<14 && cur; d++, cur=cur.parentElement) {
          const r=cur.getBoundingClientRect();
          const txt=cur.innerText||cur.textContent||'';
          const c=compact(txt);
          if (r.width>=160 && r.height>=100 && c.includes('一键领链') && (c.includes('到手价')||c.includes('佣金'))) { root=cur; break; }
        }
        if (!root) continue;
        const r=root.getBoundingClientRect();
        const raw=root.innerText||root.textContent||'';
        const c=compact(raw);
        const links=Array.from(root.querySelectorAll('a[href]')).map(a=>a.href||'');
        let score=0, reasons=[];
        if (links.some(h=>h.includes('/'+sku+'.html')||h.includes(sku))) { score+=100; reasons.push('sku_link'); }
        if (sku && c.includes(sku)) { score+=60; reasons.push('sku_text'); }
        if (titleKey && c.includes(titleKey)) { score+=50; reasons.push('title_key'); }
        candidates.push({button:b, root, score, reasons, rootText:raw.slice(0,400), links:links.slice(0,5), rect:{x:r.x,y:r.y,w:r.width,h:r.height}, buttonRect:b.rect});
      }
      candidates.sort((a,b)=>b.score-a.score || a.buttonRect.y-b.buttonRect.y);
      if (!candidates.length) return {ok:false,reason:'no_card_candidates',button_count:buttons.length};
      const t=candidates[0];
      if (t.score<=0) return {ok:false,reason:'no_candidate_match',button_count:buttons.length,top:candidates.slice(0,5).map(x=>({score:x.score,reasons:x.reasons,rootText:x.rootText,links:x.links,rect:x.rect,buttonRect:x.buttonRect}))};
      t.button.el.scrollIntoView({block:'center',inline:'center'});
      t.button.el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true,cancelable:true,view:window}));
      t.button.el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window}));
      t.button.el.click();
      t.button.el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,view:window}));
      return {ok:true,method:'card_scoped_onekey',score:t.score,reasons:t.reasons,button_count:buttons.length,matched:{rootText:t.rootText,links:t.links,rect:t.rect,buttonRect:t.buttonRect}};
    }
    """, {'sku':sku,'title':title})

def collect_one(page,cand:Dict[str,Any],state:Dict[str,Any],page_no:int,order:int)->Dict[str,Any]:
    sku=str(cand.get('sku') or '').strip(); title=str(cand.get('title') or '').strip()
    tries=[]
    if risk(page): return {'ok':False,'sku':sku,'reason':'risk_before','risk':risk(page)}
    try:
        try: base.close_dialog(page)
        except Exception: pass
        click=card_click(page,sku,title)
        if not click.get('ok'):
            return {'ok':False,'sku':sku,'reason':'card_click_failed','click':click}
        result={}
        for sec in range(1,WAIT+1):
            page.wait_for_timeout(1000)
            result=parse_modal(page)
            if risk(page): return {'ok':False,'sku':sku,'reason':'risk_after_click','risk':risk(page),'click':click}
            if result.get('short_url'): break
        try: base.close_dialog(page)
        except Exception: pass
        if not result.get('short_url'):
            return {'ok':False,'sku':sku,'reason':'short_url_timeout','click':click,'modal_keys':[k for k,v in result.items() if v]}
        created,expire,refresh=link_dates()
        row={'status':'ok','ts':now(),'worker_name':'hz18_card_click','source_menu':'商品推广/全部商品','menu_mode':'hz18_card_click_recovery','promotion_mode':'hz18_card_scoped_onekey','run_id':core.RUN_ID,'page_no':page_no,'page_order':order,'sku':sku,'sku_source':'hz18_card_candidate','title':title,'item_url':cand.get('itemUrl') or f'https://item.jd.com/{sku}.html','image_url':base.normalize_img(cand.get('imageUrl')),'price':cand.get('price'),'commission_rate':cand.get('rate'),'estimated_income':cand.get('income'),'short_url':result.get('short_url'),'long_url':result.get('long_url'),'qr_url':result.get('qr_url'),'jd_command':result.get('jd_command'),'link_created_at':created,'link_expire_at':expire,'link_expire_days':60,'refresh_due_at':refresh,'refresh_after_days':40,'refresh_before_expiry_days':20,'refresh_round':state.get('refresh_round',0),'click_result':click}
        core.append_jsonl(core.OUT,row)
        if sku and sku not in state['known_skus']: state['known_skus'].append(sku)
        state['fail_streak']=0; core.save_state(state); core.write_report(state,{'last_page_no':page_no,'last_hz18_sku':sku,'mode':'hz18_card_click_recovery'})
        log('ITEM_OK_HZ18',page_no=page_no,sku=sku,short_url=row.get('short_url'),known_sku_count=len(state.get('known_skus') or []))
        return {'ok':True,'sku':sku,'short_url':row.get('short_url'),'click':click}
    except Exception as e:
        try: base.close_dialog(page)
        except Exception: pass
        return {'ok':False,'sku':sku,'reason':'exception','err':repr(e),'tries':tries}

def fresh_candidates(page,state)->List[Dict[str,Any]]:
    cands=base.collect_page_candidates(page); known=set(state.get('known_skus') or [])
    out=[]; seen=set()
    for c in cands:
        sku=str(c.get('sku') or '').strip(); title=str(c.get('title') or '').strip()
        if sku.isdigit() and title and sku not in known and sku not in seen:
            out.append(c); seen.add(sku)
    return out

def main():
    from playwright.sync_api import sync_playwright
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    rep={'ts':now(),'pages':pages(PAGE_SEQUENCE),'limit':LIMIT,'wait':WAIT,'results':[]}
    hz15.v4.bootstrap_out_from_history()
    with sync_playwright() as p:
        browser=p.chromium.connect_over_cdp('http://127.0.0.1:19228',timeout=15000)
        page=core.get_active_page(browser); page.set_default_timeout(20000); page.bring_to_front(); rep['initial']=snapshot(page)
        total_ok=total_fail=0
        if risk(page): rep.update(ok=False,reason='risk_initial',risk=risk(page))
        else:
            for page_no in rep['pages']:
                ready=ensure_page(page,page_no); rep.setdefault('page_ready',{})[str(page_no)]=ready
                if not ready.get('ok'): rep.update(ok=False,reason=f'page_{page_no}_not_ready'); break
                state=core.load_state(); state.setdefault('known_skus',[])
                fresh=fresh_candidates(page,state)
                log('PAGE_CANDIDATES_HZ18',page_no=page_no,total=len(fresh),sample=[{'sku':x.get('sku'),'title':(x.get('title') or '')[:60]} for x in fresh[:8]])
                consecutive=0; page_ok=page_fail=0
                for order,c in enumerate(fresh[:LIMIT]):
                    log('ITEM_START_HZ18',page_no=page_no,order=order,sku=c.get('sku'),title=(c.get('title') or '')[:80])
                    r=collect_one(page,c,state,page_no,order); rep['results'].append({'page_no':page_no,'order':order,**r})
                    log('ITEM_RESULT_HZ18',page_no=page_no,sku=r.get('sku'),ok=r.get('ok'),reason=r.get('reason'),short_url=r.get('short_url'))
                    state=core.load_state(); state.setdefault('known_skus',[])
                    if r.get('ok'):
                        total_ok+=1; page_ok+=1; consecutive=0
                    else:
                        total_fail+=1; page_fail+=1; consecutive+=1
                        if consecutive>=FAIL_FUSE:
                            log('PAGE_FAIL_FUSE_HZ18',page_no=page_no,consecutive_fail=consecutive,page_ok=page_ok,page_fail=page_fail); break
                    time.sleep(random.uniform(ITEM_SLEEP_MIN,ITEM_SLEEP_MAX))
                rep.setdefault('page_summary',{})[str(page_no)]={'ok':page_ok,'fail':page_fail,'fresh_initial':len(fresh),'final_snapshot':snapshot(page)}
        state=core.load_state(); rep.update(ok=not bool(rep.get('reason')),total_ok=total_ok,total_fail=total_fail,known_sku_count=len(state.get('known_skus') or []),final=snapshot(page))
    REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
    log('HZ18_DONE',ok=rep.get('ok'),total_ok=rep.get('total_ok'),total_fail=rep.get('total_fail'),known_sku_count=rep.get('known_sku_count'))
if __name__=='__main__': main()
