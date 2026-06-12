#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, os, time
from pathlib import Path
from datetime import datetime

MOD_PATH=Path('run/hz15_jump_pages_collector_v6_no_reset_strict_4000.py')
REPORT=Path('reports/hz19_visual_probe_failed_sku_latest.json')
PAGE_NO=int(os.environ.get('HZ19_PAGE','49'))
SKU=os.environ.get('HZ19_SKU','100016509578')
TITLE_KEY=os.environ.get('HZ19_TITLE_KEY','佳帮手折叠扫把簸箕')
HOLD_SECONDS=int(os.environ.get('HZ19_HOLD_SECONDS','300'))
RISK=['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧']

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def log(event, **kw): print(json.dumps({'ts':now(),'worker':'hz19_visual_probe','event':event,**kw},ensure_ascii=False,sort_keys=True),flush=True)
def load_mod():
    spec=importlib.util.spec_from_file_location('hz15v6', str(MOD_PATH)); m=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(m); return m
m=load_mod(); hz15=m.hz15; core=m.core

def text(page):
    try: return page.evaluate("() => document.body ? (document.body.innerText || '') : ''")
    except Exception: return ''
def risk(page):
    hay='\n'.join([page.url or '', text(page)])
    return [x for x in RISK if x in hay]
def snapshot(page):
    info=m.v5.raw_page_info(page)
    return {k:info.get(k) for k in ['url','title','activePageText','oneKeyCount','skuCount','has4000','hasEmpty','pagerText','jumpInputValue','risk']}

def ensure_page(page):
    usable=m.current_all_product_4000_usable(page)
    if not usable.get('usable'):
        return {'ok':False,'reason':'not_all_product_4000','info':usable.get('info')}
    if str((usable.get('info') or {}).get('activePageText') or '')==str(PAGE_NO):
        return {'ok':True,'mode':'already_on_page','info':usable.get('info')}
    j=hz15.jump_to_page(page,PAGE_NO)
    if not j.get('ok'): return {'ok':False,'reason':'jump_failed','jump':j}
    return {'ok':True,'mode':'jumped','jump':j,'info':snapshot(page)}

def click_card(page):
    return page.evaluate("""
    ({sku,titleKey}) => {
      const compact=s=>(s||'').replace(/\s+/g,'').trim();
      const buttons=Array.from(document.querySelectorAll('button,a,span,div'))
        .map((el,idx)=>{const r=el.getBoundingClientRect();return {el,idx,txt:compact(el.innerText||el.textContent),visible:r.width>0&&r.height>0&&r.top>=-200&&r.left>=-100&&r.top<=window.innerHeight+1200,rect:{x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}}})
        .filter(x=>x.visible && x.txt==='一键领链');
      const cands=[];
      for (const b of buttons) {
        let cur=b.el, root=null;
        for (let d=0; d<14 && cur; d++,cur=cur.parentElement) {
          const r=cur.getBoundingClientRect();
          const raw=cur.innerText||cur.textContent||'';
          const c=compact(raw);
          if (r.width>=160 && r.height>=100 && c.includes('一键领链') && (c.includes('到手价')||c.includes('佣金'))) { root=cur; break; }
        }
        if (!root) continue;
        const raw=root.innerText||root.textContent||'';
        const c=compact(raw);
        const links=Array.from(root.querySelectorAll('a[href]')).map(a=>a.href||'');
        let score=0, reasons=[];
        if (links.some(h=>h.includes('/'+sku+'.html')||h.includes(sku))) {score+=100; reasons.push('sku_link')}
        if (c.includes(sku)) {score+=60; reasons.push('sku_text')}
        if (titleKey && c.includes(compact(titleKey))) {score+=50; reasons.push('title_key')}
        const r=root.getBoundingClientRect();
        cands.push({button:b,root,score,reasons,rootText:raw.slice(0,600),links:links.slice(0,5),rootRect:{x:r.x,y:r.y,w:r.width,h:r.height},buttonRect:b.rect});
      }
      cands.sort((a,b)=>b.score-a.score || a.buttonRect.y-b.buttonRect.y);
      if (!cands.length) return {ok:false,reason:'no_card_candidates',button_count:buttons.length};
      const t=cands[0];
      t.button.el.scrollIntoView({block:'center',inline:'center'});
      t.button.el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true,cancelable:true,view:window}));
      t.button.el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window}));
      t.button.el.click();
      t.button.el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,view:window}));
      return {ok:true,method:'card_scoped_onekey_visual_probe',score:t.score,reasons:t.reasons,button_count:buttons.length,matched:{rootText:t.rootText,links:t.links,rootRect:t.rootRect,buttonRect:t.buttonRect}};
    }
    """, {'sku':SKU,'titleKey':TITLE_KEY})

def dom_probe(page):
    return page.evaluate("""
    () => {
      const txt=document.body?(document.body.innerText||''):'';
      const nodes=Array.from(document.querySelectorAll('.el-dialog,.ant-modal,[role=dialog],.modal,.el-message,.el-notification,.ant-message,.ant-notification,.semi-toast,.semi-modal')).map((el,i)=>{const r=el.getBoundingClientRect();return {i,tag:el.tagName,cls:String(el.className||'').slice(0,160),visible:r.width>0&&r.height>0,rect:{x:r.x,y:r.y,w:r.width,h:r.height},text:(el.innerText||el.textContent||'').slice(0,1500)}}).filter(x=>x.visible||x.text);
      return {url:location.href,title:document.title,bodyTail:txt.slice(-2000),bodyHasRisk:['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧'].filter(x=>txt.includes(x)||location.href.includes(x)),bodyHasShort:/https?:\/\/u\.jd\.com\//.test(txt),nodes:nodes.slice(0,30)};
    }
    """)

def main():
    from playwright.sync_api import sync_playwright
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    rep={'ts':now(),'page':PAGE_NO,'sku':SKU,'title_key':TITLE_KEY,'hold_seconds':HOLD_SECONDS}
    with sync_playwright() as p:
        browser=p.chromium.connect_over_cdp('http://127.0.0.1:19228',timeout=15000)
        page=core.get_active_page(browser); page.set_default_timeout(20000); page.bring_to_front()
        rep['initial']=snapshot(page); rep['ready']=ensure_page(page); rep['before_click']=snapshot(page)
        if risk(page):
            rep.update(ok=False,reason='risk_before',risk=risk(page))
        elif not rep['ready'].get('ok'):
            rep.update(ok=False,reason='page_not_ready')
        else:
            rep['click']=click_card(page)
            page.wait_for_timeout(2000)
            rep['after_2s']=dom_probe(page)
            log('VISUAL_READY_TAKE_SCREENSHOT_NOW',sku=SKU,page=PAGE_NO,hold_seconds=HOLD_SECONDS,click=rep.get('click'),after_2s_summary={'bodyHasShort':rep['after_2s'].get('bodyHasShort'),'bodyHasRisk':rep['after_2s'].get('bodyHasRisk'),'nodes':len(rep['after_2s'].get('nodes') or [])})
            time.sleep(HOLD_SECONDS)
            rep['after_hold']=dom_probe(page)
            rep['ok']=True
    REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
    log('HZ19_DONE',ok=rep.get('ok'),reason=rep.get('reason'),sku=SKU)
if __name__=='__main__': main()
