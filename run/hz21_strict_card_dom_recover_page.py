#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, os, re, random, time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List

MOD_PATH=Path('run/hz15_jump_pages_collector_v6_no_reset_strict_4000.py')
REPORT=Path('reports/hz21_strict_card_dom_recover_latest.json')
PAGE_SEQUENCE=os.environ.get('HZ21_PAGE_SEQUENCE','49')
LIMIT=int(os.environ.get('HZ21_LIMIT','20'))
WAIT=int(os.environ.get('HZ21_WAIT','10'))
FAIL_FUSE=int(os.environ.get('HZ21_FAIL_FUSE','6'))
ITEM_SLEEP_MIN=float(os.environ.get('HZ21_ITEM_SLEEP_MIN','1'))
ITEM_SLEEP_MAX=float(os.environ.get('HZ21_ITEM_SLEEP_MAX','3'))
RISK=['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧']

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def log(event, **kw): print(json.dumps({'ts':now(),'worker':'hz21_strict_card_dom','event':event,**kw},ensure_ascii=False,sort_keys=True),flush=True)
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

def ensure_page(page,page_no:int)->Dict[str,Any]:
    usable=m.current_all_product_4000_usable(page)
    if not usable.get('usable'):
        return {'ok':False,'reason':'not_all_product_4000','info':usable.get('info')}
    if str((usable.get('info') or {}).get('activePageText') or '')==str(page_no):
        return {'ok':True,'mode':'already_on_page','info':usable.get('info')}
    time.sleep(random.uniform(1,3)); j=hz15.jump_to_page(page,page_no)
    if not j.get('ok'): return {'ok':False,'reason':'jump_failed','jump':j}
    return {'ok':True,'mode':'jumped','jump':j,'info':snapshot(page)}

def extract_title(raw:str)->str:
    text=re.sub(r'\s+',' ', raw or '').strip()
    if not text: return ''
    m=re.search(r'佣金比例\s*\d+(?:\.\d+)?%\s*(.*?)\s*到手价', text)
    if m:
        return m.group(1).strip()[:180]
    lines=[x.strip() for x in re.split(r'[\n\r]+', raw or '') if x.strip()]
    bad=['预估收益','佣金比例','到手价','我要推广','一键领链','自营','京配','定向','奖励','促销','券','好评','进行中','去报名']
    for line in lines:
        c=re.sub(r'\s+','',line)
        if len(c)>=6 and not any(b in c for b in bad) and not re.fullmatch(r'[￥¥]?\d+(\.\d+)?', c):
            return line[:180]
    return ''

def parse_money(raw:str, pat:str)->str:
    m=re.search(pat, raw or '')
    return m.group(1) if m else ''

def collect_cards(page)->List[Dict[str,Any]]:
    cards=page.evaluate("""
    () => {
      const compact=s=>(s||'').replace(/\s+/g,'').trim();
      const buttons=Array.from(document.querySelectorAll('button,a,span,div'))
        .map((el,idx)=>{const r=el.getBoundingClientRect();return {el,idx,txt:compact(el.innerText||el.textContent),visible:r.width>0&&r.height>0&&r.top>=-300&&r.left>=-120&&r.top<=window.innerHeight+1500,rect:{x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}}})
        .filter(x=>x.visible && x.txt==='一键领链');
      const out=[]; const seen=new Set();
      for (const b of buttons) {
        let cur=b.el, root=null;
        for (let d=0; d<14 && cur; d++,cur=cur.parentElement) {
          const r=cur.getBoundingClientRect(); const raw=cur.innerText||cur.textContent||''; const c=compact(raw);
          if (r.width>=160 && r.height>=100 && c.includes('一键领链') && (c.includes('到手价')||c.includes('佣金'))) { root=cur; break; }
        }
        if (!root) continue;
        const raw=root.innerText||root.textContent||'';
        const links=Array.from(root.querySelectorAll('a[href]')).map(a=>a.href||'');
        const skuLink=links.find(h=>/item\.jd\.com\/(\d+)\.html/.test(h));
        const m=skuLink && skuLink.match(/item\.jd\.com\/(\d+)\.html/);
        const sku=m?m[1]:'';
        if (!sku || seen.has(sku)) continue;
        seen.add(sku);
        const imgs=Array.from(root.querySelectorAll('img')).map(img=>img.currentSrc||img.src||'').filter(Boolean);
        const r=root.getBoundingClientRect();
        out.push({sku,itemUrl:skuLink,links:links.slice(0,5),imageUrl:imgs[0]||'',raw_text:raw,buttonRect:b.rect,rootRect:{x:r.x,y:r.y,w:r.width,h:r.height},buttonIndex:b.idx});
      }
      return out;
    }
    """)
    out=[]
    for c in cards:
        raw=c.get('raw_text') or ''
        c['title']=extract_title(raw)
        c['price']=parse_money(raw, r'到手价\s*[￥¥]\s*([0-9]+(?:\.[0-9]+)?)')
        c['rate']=parse_money(raw, r'佣金比例\s*([0-9]+(?:\.[0-9]+)?%)')
        c['income']=parse_money(raw, r'预估收益\s*[￥¥]\s*([0-9]+(?:\.[0-9]+)?)')
        out.append(c)
    return out

def parse_modal(page):
    try: return dict(base.parse_modal(page))
    except Exception as e: return {'parse_error':repr(e)}

def dom_state(page):
    return page.evaluate("""
    () => {
      const txt=document.body?(document.body.innerText||''):'';
      const nodes=Array.from(document.querySelectorAll('.el-dialog,.ant-modal,[role=dialog],.modal,.el-message,.el-notification,.ant-message,.ant-notification')).map((el,i)=>{const r=el.getBoundingClientRect();return {i,cls:String(el.className||'').slice(0,120),visible:r.width>0&&r.height>0,rect:{x:r.x,y:r.y,w:r.width,h:r.height},text:(el.innerText||el.textContent||'').slice(0,800)}}).filter(x=>x.visible||x.text);
      return {bodyHasShort:/https?:\/\/u\.jd\.com\//.test(txt),risk:['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧'].filter(x=>txt.includes(x)||location.href.includes(x)),nodes:nodes.slice(0,12)};
    }
    """)

def link_dates():
    c=datetime.now(); return c.isoformat(timespec='seconds'),(c+timedelta(days=60)).isoformat(timespec='seconds'),(c+timedelta(days=40)).isoformat(timespec='seconds')

def quarantine_unsafe_hz20(state:Dict[str,Any])->Dict[str,Any]:
    rows=core.read_jsonl(core.LATEST)
    keep=[]; removed=[]
    for r in rows:
        if r.get('worker_name')=='hz20_mouse_click' or 'hz20' in str(r.get('menu_mode') or ''):
            removed.append({'sku':r.get('sku'),'short_url':r.get('short_url'),'worker_name':r.get('worker_name'),'menu_mode':r.get('menu_mode')})
        else:
            keep.append(r)
    if removed:
        core.LATEST.parent.mkdir(parents=True, exist_ok=True)
        with core.LATEST.open('w', encoding='utf-8') as f:
            for row in keep:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\\n')
        import shutil
        shutil.copyfile(core.LATEST, core.HZ12_COMPAT_LATEST)
        valid={str(r.get('sku')) for r in keep if str(r.get('sku') or '').isdigit() and r.get('short_url')}
        state['known_skus']=[x for x in (state.get('known_skus') or []) if str(x) in valid]
        core.save_state(state)
    return {'removed_count':len(removed),'removed_sample':removed[:20],'rows_after':len(keep)}

def click_card(page, card:Dict[str,Any])->Dict[str,Any]:
    sku=str(card.get('sku') or '').strip()
    token=f"hz21_{sku}_{int(time.time()*1000)}"
    mark=page.evaluate("""
    ({sku,token}) => {
      const compact=s=>(s||'').replace(/\s+/g,'').trim();
      const links=Array.from(document.querySelectorAll('a[href]')).filter(a=>(a.href||'').includes('/'+sku+'.html') || (a.href||'').includes(sku));
      const rows=[];
      for (const a of links) {
        let cur=a, root=null;
        for (let d=0; d<16 && cur; d++,cur=cur.parentElement) {
          const r=cur.getBoundingClientRect(); const raw=cur.innerText||cur.textContent||''; const c=compact(raw);
          if (r.width>=160 && r.height>=100 && c.includes('一键领链') && (c.includes('到手价')||c.includes('佣金'))) { root=cur; break; }
        }
        if (!root) continue;
        const btn=Array.from(root.querySelectorAll('button,a,span,div')).find(el=>compact(el.innerText||el.textContent)==='一键领链');
        if (!btn) continue;
        btn.setAttribute('data-hz21-token', token);
        root.setAttribute('data-hz21-root', token);
        const br=btn.getBoundingClientRect(); const rr=root.getBoundingClientRect();
        rows.push({rootText:(root.innerText||root.textContent||'').slice(0,500), itemUrl:a.href, rootRect:{x:rr.x,y:rr.y,w:rr.width,h:rr.height}, buttonRect:{x:br.x,y:br.y,w:br.width,h:br.height,cx:br.x+br.width/2,cy:br.y+br.height/2}});
      }
      rows.sort((a,b)=>a.rootRect.y-b.rootRect.y);
      if (!rows.length) return {ok:false, reason:'exact_sku_button_not_found', sku};
      const el=document.querySelector('[data-hz21-token="'+token+'"]');
      el.scrollIntoView({block:'center',inline:'center'});
      return {ok:true, method:'exact_sku_token_marked', sku, token, matched:rows[0]};
    }
    """, {'sku':sku,'token':token})
    if not mark.get('ok'):
        return mark
    page.wait_for_timeout(600)
    selector=f'[data-hz21-token="{token}"]'
    loc=page.locator(selector).first
    try:
        loc.scroll_into_view_if_needed(timeout=5000)
    except Exception as exc:
        mark['scroll_error']=repr(exc)
    for _ in range(4):
        box=loc.bounding_box(timeout=5000)
        if not box:
            return {'ok':False,'reason':'bounding_box_missing','sku':sku,'mark':mark}
        inner=page.evaluate('() => window.innerHeight')
        if box['y'] < 150 or box['y'] > inner-120:
            page.evaluate("""
            (sel) => {
              const el=document.querySelector(sel);
              if (!el) return;
              const r=el.getBoundingClientRect();
              window.scrollBy(0, r.top - window.innerHeight*0.55);
            }
            """, selector)
            page.wait_for_timeout(500)
        else:
            break
    box=loc.bounding_box(timeout=5000)
    if not box:
        return {'ok':False,'reason':'bounding_box_missing_after_adjust','sku':sku,'mark':mark}
    x=box['x']+box['width']/2; y=box['y']+box['height']/2
    hit=page.evaluate("""
    ({x,y,token}) => {
      const el=document.elementFromPoint(x,y);
      const m=el && el.closest('[data-hz21-token="'+token+'"]');
      return {ok:!!m, tag:el?el.tagName:null, text:el?(el.innerText||el.textContent||'').replace(/\s+/g,'').slice(0,50):null, cls:el?String(el.className||'').slice(0,100):null};
    }
    """, {'x':x,'y':y,'token':token})
    if not hit.get('ok'):
        return {'ok':False,'reason':'hit_test_not_target_button','sku':sku,'mark':mark,'box':box,'hit':hit}
    page.mouse.move(x,y); page.wait_for_timeout(150); page.mouse.down(); page.wait_for_timeout(120); page.mouse.up()
    return {'ok':True,'method':'hz21_exact_sku_locator_safe_mouse_click','sku':sku,'token':token,'box':box,'mouse_click':{'x':x,'y':y},'hit':hit,'matched':mark.get('matched')}

def collect_one(page,card:Dict[str,Any],state:Dict[str,Any],page_no:int,order:int)->Dict[str,Any]:
    sku=str(card.get('sku') or '').strip()
    if risk(page): return {'ok':False,'sku':sku,'reason':'risk_before','risk':risk(page)}
    try:
        try: base.close_dialog(page)
        except Exception: pass
        click=click_card(page,card)
        if not click.get('ok'): return {'ok':False,'sku':sku,'reason':'click_failed','click':click}
        result={}; last_dom={}
        for sec in range(1,WAIT+1):
            page.wait_for_timeout(1000)
            result=parse_modal(page); last_dom=dom_state(page)
            if risk(page): return {'ok':False,'sku':sku,'reason':'risk_after_click','risk':risk(page),'click':click,'dom':last_dom}
            if result.get('short_url'): break
        try: base.close_dialog(page)
        except Exception: pass
        if not result.get('short_url'):
            return {'ok':False,'sku':sku,'reason':'short_url_timeout','click':click,'modal_keys':[k for k,v in result.items() if v],'dom':last_dom}
        created,expire,refresh=link_dates()
        row={'status':'ok','ts':now(),'worker_name':'hz21_strict_card_dom','source_menu':'商品推广/全部商品','menu_mode':'hz21_strict_card_dom_recovery','promotion_mode':'hz21_strict_sku_mouse_onekey','run_id':core.RUN_ID,'page_no':page_no,'page_order':order,'sku':sku,'sku_source':'hz21_card_item_href','title':card.get('title'),'item_url':card.get('itemUrl') or f'https://item.jd.com/{sku}.html','image_url':base.normalize_img(card.get('imageUrl')),'price':card.get('price'),'commission_rate':card.get('rate'),'estimated_income':card.get('income'),'short_url':result.get('short_url'),'long_url':result.get('long_url'),'qr_url':result.get('qr_url'),'jd_command':result.get('jd_command'),'link_created_at':created,'link_expire_at':expire,'link_expire_days':60,'refresh_due_at':refresh,'refresh_after_days':40,'refresh_before_expiry_days':20,'refresh_round':state.get('refresh_round',0),'click_result':click}
        core.append_jsonl(core.OUT,row)
        if sku and sku not in state['known_skus']: state['known_skus'].append(sku)
        state['fail_streak']=0; core.save_state(state); core.write_report(state,{'last_page_no':page_no,'last_hz21_sku':sku,'mode':'hz21_strict_card_dom_recovery'})
        log('ITEM_OK_HZ21',page_no=page_no,sku=sku,short_url=row.get('short_url'),known_sku_count=len(state.get('known_skus') or []))
        return {'ok':True,'sku':sku,'short_url':row.get('short_url'),'click':click}
    except Exception as e:
        try: base.close_dialog(page)
        except Exception: pass
        return {'ok':False,'sku':sku,'reason':'exception','err':repr(e)}

def main():
    from playwright.sync_api import sync_playwright
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    rep={'ts':now(),'pages':pages(PAGE_SEQUENCE),'limit':LIMIT,'wait':WAIT,'results':[]}
    hz15.v4.bootstrap_out_from_history()
    state=core.load_state(); state.setdefault('known_skus',[])
    rep['quarantine']=quarantine_unsafe_hz20(state)
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
                known=set(state.get('known_skus') or [])
                cards=[c for c in collect_cards(page) if str(c.get('sku') or '').isdigit() and c.get('title') and str(c.get('sku')) not in known]
                seen=set(); fresh=[]
                for c in cards:
                    if c['sku'] not in seen:
                        fresh.append(c); seen.add(c['sku'])
                log('PAGE_CANDIDATES_HZ21',page_no=page_no,total=len(cards),fresh=len(fresh),sample=[{'sku':x.get('sku'),'title':(x.get('title') or '')[:60]} for x in fresh[:8]])
                consecutive=0; page_ok=page_fail=0
                for order,c in enumerate(fresh[:LIMIT]):
                    log('ITEM_START_HZ21',page_no=page_no,order=order,sku=c.get('sku'),title=(c.get('title') or '')[:80])
                    r=collect_one(page,c,state,page_no,order); rep['results'].append({'page_no':page_no,'order':order,**r})
                    log('ITEM_RESULT_HZ21',page_no=page_no,sku=r.get('sku'),ok=r.get('ok'),reason=r.get('reason'),short_url=r.get('short_url'))
                    state=core.load_state(); state.setdefault('known_skus',[])
                    if r.get('ok'):
                        total_ok+=1; page_ok+=1; consecutive=0
                    else:
                        total_fail+=1; page_fail+=1; consecutive+=1
                        if consecutive>=FAIL_FUSE:
                            log('PAGE_FAIL_FUSE_HZ21',page_no=page_no,consecutive_fail=consecutive,page_ok=page_ok,page_fail=page_fail); break
                    time.sleep(random.uniform(ITEM_SLEEP_MIN,ITEM_SLEEP_MAX))
                rep.setdefault('page_summary',{})[str(page_no)]={'ok':page_ok,'fail':page_fail,'fresh_initial':len(fresh),'final_snapshot':snapshot(page)}
        state=core.load_state(); rep.update(ok=not bool(rep.get('reason')),total_ok=total_ok,total_fail=total_fail,known_sku_count=len(state.get('known_skus') or []),final=snapshot(page))
    REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
    log('HZ21_DONE',ok=rep.get('ok'),total_ok=rep.get('total_ok'),total_fail=rep.get('total_fail'),known_sku_count=rep.get('known_sku_count'),quarantine=rep.get('quarantine'))
if __name__=='__main__': main()
