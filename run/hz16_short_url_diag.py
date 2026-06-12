#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, os, time, random
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

PAGE_NO=int(os.environ.get('HZ16_DIAG_PAGE','49'))
LIMIT=int(os.environ.get('HZ16_DIAG_LIMIT','6'))
WAIT=int(os.environ.get('HZ16_DIAG_WAIT','12'))
REPORT=Path('reports/hz16_short_url_diag_latest.json')
MOD_PATH=Path('run/hz15_jump_pages_collector_v6_no_reset_strict_4000.py')
RISK=['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧']

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def out(event, **kw): print(json.dumps({'ts':now(),'worker':'hz16_short_url_diag','event':event,**kw},ensure_ascii=False,sort_keys=True),flush=True)
def load_mod():
    spec=importlib.util.spec_from_file_location('hz15v6', str(MOD_PATH)); m=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(m); return m
m=load_mod(); hz15=m.hz15; core=m.core; base=m.base

def page_text(page):
    try: return page.evaluate("() => document.body ? (document.body.innerText || '') : ''")
    except Exception: return ''
def risks(page):
    txt='\n'.join([page.url or '', page_text(page)])
    return [x for x in RISK if x in txt]
def page_info(page):
    info=m.v5.raw_page_info(page)
    return {k:info.get(k) for k in ['url','title','activePageText','oneKeyCount','skuCount','has4000','hasEmpty','pagerText','jumpInputValue','risk']}
def modal_state(page):
    try: parsed=dict(base.parse_modal(page))
    except Exception as e: parsed={'parse_error':repr(e)}
    dom=page.evaluate("""
    () => {
      const txt=document.body?(document.body.innerText||''):'';
      const dialogs=Array.from(document.querySelectorAll('.el-dialog,.ant-modal,[role=dialog],.modal')).map((el,i)=>{const r=el.getBoundingClientRect();return {i,visible:r.width>0&&r.height>0,text:(el.innerText||el.textContent||'').slice(0,800),rect:{x:r.x,y:r.y,w:r.width,h:r.height},cls:String(el.className||'').slice(0,100)}}).filter(x=>x.visible);
      const urls=Array.from(txt.matchAll(/https?:\/\/[^\s"'<>]+/g)).map(m=>m[0]).slice(0,15);
      return {dialogCount:dialogs.length,dialogs,urls,hasShort:/https?:\/\/u\.jd\.com\//.test(txt),risk:['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧'].filter(x=>txt.includes(x)||location.href.includes(x))};
    }
    """)
    return {'parsed':parsed,'dom':dom}

def diagnose_one(page,cand,order):
    sku=str(cand.get('sku') or '')
    res={'sku':sku,'title':(cand.get('title') or '')[:100],'order':order,'class':'unknown','click':None,'polls':[]}
    if risks(page): res['class']='risk_before'; res['risk']=risks(page); return res
    try:
        cur, visible = base.find_current_candidate(page, sku, cand.get('scroll_y'))
        res['visible_head']=[x.get('sku') for x in (visible or [])[:8]]
        if cur is None: res['class']='not_visible'; return res
        try: base.close_dialog(page)
        except Exception: pass
        click=base.click_candidate(page, cur, min(order, max(0,len(visible)-1)))
        res['click']=click
        if not click.get('ok'): res['class']='click_failed'; return res
        for sec in range(1, WAIT+1):
            page.wait_for_timeout(1000)
            ms=modal_state(page); p=ms.get('parsed') or {}; d=ms.get('dom') or {}
            res['polls'].append({'sec':sec,'short_url':p.get('short_url'),'long_url':p.get('long_url'),'keys':[k for k,v in p.items() if v],'dialogCount':d.get('dialogCount'),'hasShort':d.get('hasShort'),'risk':d.get('risk'),'urls':d.get('urls',[])[:5]})
            if d.get('risk'): res['class']='risk_after'; break
            if p.get('short_url'): res['class']='short_url_found'; break
            if sec in (3, WAIT): res.setdefault('snapshots',[]).append({'sec':sec,'modal':ms})
        if res['class']=='unknown':
            last=res['polls'][-1] if res['polls'] else {}
            if (last.get('dialogCount') or 0)<=0: res['class']='modal_not_opened'
            elif last.get('hasShort'): res['class']='parser_missed'
            else: res['class']='modal_no_short_url'
    except Exception as e:
        res['class']='exception'; res['error']=repr(e)
    finally:
        try: base.close_dialog(page)
        except Exception: pass
    return res

def main():
    from playwright.sync_api import sync_playwright
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    rep={'ts':now(),'page_no':PAGE_NO,'limit':LIMIT,'wait':WAIT,'results':[]}
    with sync_playwright() as p:
        browser=p.chromium.connect_over_cdp('http://127.0.0.1:19228',timeout=15000)
        page=core.get_active_page(browser); page.set_default_timeout(20000); page.bring_to_front()
        rep['initial']=page_info(page)
        if risks(page): rep.update(ok=False,reason='risk_initial'); REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8'); out('DONE',ok=False,reason=rep['reason']); return
        ready=m.current_all_product_4000_usable(page)
        if not ready.get('usable'): rep.update(ok=False,reason='not_all_product_4000',info=ready.get('info')); REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8'); out('DONE',ok=False,reason=rep['reason']); return
        if str(ready['info'].get('activePageText') or '') != str(PAGE_NO):
            time.sleep(random.uniform(2,5)); rep['jump']=hz15.jump_to_page(page,PAGE_NO)
            if not rep['jump'].get('ok'): rep.update(ok=False,reason='jump_failed'); REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8'); out('DONE',ok=False,reason=rep['reason']); return
        rep['after_jump']=page_info(page)
        state=core.load_state(); known=set(state.get('known_skus') or [])
        cands=base.collect_page_candidates(page); fresh=[]; seen=set()
        for c in cands:
            sku=str(c.get('sku') or ''); title=str(c.get('title') or '')
            if sku.isdigit() and title and sku not in known and sku not in seen:
                fresh.append(c); seen.add(sku)
        rep['candidate_summary']={'total':len(cands),'fresh':len(fresh),'sample':[{'sku':x.get('sku'),'title':(x.get('title') or '')[:80]} for x in fresh[:10]]}
        for i,c in enumerate(fresh[:LIMIT]):
            out('ITEM_START',sku=c.get('sku'),title=(c.get('title') or '')[:80])
            r=diagnose_one(page,c,i); rep['results'].append(r); out('ITEM_RESULT',sku=r.get('sku'),cls=r.get('class'),click=r.get('click'))
            time.sleep(random.uniform(2,4))
    counts={}
    for r in rep['results']: counts[r.get('class')]=counts.get(r.get('class'),0)+1
    rep['class_counts']=counts; rep['ok']=True
    if counts.get('modal_no_short_url',0)>=max(2,LIMIT//2): rep['diagnosis']='modal_open_but_no_short_url'
    elif counts.get('modal_not_opened',0)>=max(2,LIMIT//2): rep['diagnosis']='click_flow_not_opening_modal'
    elif counts.get('parser_missed'): rep['diagnosis']='parser_missed_short_url'
    elif counts.get('short_url_found'): rep['diagnosis']='collector_timing_or_state_issue'
    elif counts.get('risk_after') or counts.get('risk_before'): rep['diagnosis']='risk_related'
    else: rep['diagnosis']='mixed_or_insufficient'
    REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
    out('DONE',ok=True,page_no=PAGE_NO,diagnosis=rep.get('diagnosis'),class_counts=counts)
if __name__=='__main__': main()
