#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, os, random, time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

MOD_PATH=Path('run/hz15_jump_pages_collector_v6_no_reset_strict_4000.py')
REPORT=Path('reports/hz17_recover_short_url_page_latest.json')
PAGE_SEQUENCE=os.environ.get('HZ17_PAGE_SEQUENCE','49')
LIMIT=int(os.environ.get('HZ17_LIMIT','30'))
WAIT=int(os.environ.get('HZ17_WAIT','6'))
RETRY=int(os.environ.get('HZ17_RETRY','0'))
FAIL_FUSE=int(os.environ.get('HZ17_FAIL_FUSE','3'))
ITEM_SLEEP_MIN=float(os.environ.get('HZ17_ITEM_SLEEP_MIN','1'))
ITEM_SLEEP_MAX=float(os.environ.get('HZ17_ITEM_SLEEP_MAX','3'))
RISK=['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧']

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def log(event, **kw): print(json.dumps({'ts':now(),'worker':'hz17_recover_short_url_fast','event':event,**kw},ensure_ascii=False,sort_keys=True),flush=True)
def load_mod():
    spec=importlib.util.spec_from_file_location('hz15v6', str(MOD_PATH)); m=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(m); return m
m=load_mod(); hz15=m.hz15; core=m.core; base=m.base

def parse_pages(s:str)->List[int]:
    out=[]
    for part in s.split(','):
        part=part.strip()
        if not part: continue
        if '-' in part:
            a,b=part.split('-',1); out.extend(range(int(a),int(b)+1))
        else: out.append(int(part))
    return [x for x in out if 1<=x<=core.PAGE_MAX]

def page_txt(page):
    try: return page.evaluate("() => document.body ? (document.body.innerText || '') : ''")
    except Exception: return ''
def risk(page):
    hay='\n'.join([page.url or '', page_txt(page)])
    return [x for x in RISK if x in hay]
def snapshot(page):
    info=m.v5.raw_page_info(page)
    return {k:info.get(k) for k in ['url','title','activePageText','oneKeyCount','skuCount','has4000','hasEmpty','pagerText','jumpInputValue','risk']}

def ensure_page(page, page_no:int)->Dict[str,Any]:
    usable=m.current_all_product_4000_usable(page)
    if not usable.get('usable'):
        return {'ok':False,'reason':'not_all_product_4000','info':usable.get('info')}
    active=str((usable.get('info') or {}).get('activePageText') or '')
    if active==str(page_no): return {'ok':True,'mode':'already_on_page','info':usable.get('info')}
    time.sleep(random.uniform(1,3))
    jump=hz15.jump_to_page(page,page_no)
    if not jump.get('ok'): return {'ok':False,'reason':'jump_failed','jump':jump}
    return {'ok':True,'mode':'jumped','jump':jump,'info':snapshot(page)}

def parse_modal(page)->Dict[str,Any]:
    try: return dict(base.parse_modal(page))
    except Exception as e: return {'parse_error':repr(e)}

def link_dates():
    created=datetime.now()
    return created.isoformat(timespec='seconds'), (created+timedelta(days=60)).isoformat(timespec='seconds'), (created+timedelta(days=40)).isoformat(timespec='seconds')

def current_candidate(page, cand:Dict[str,Any], order:int):
    sku=str(cand.get('sku') or '')
    cur, visible=base.find_current_candidate(page, sku, cand.get('scroll_y'))
    return cur, visible or []

def collect_fast(page, cand:Dict[str,Any], state:Dict[str,Any], page_no:int, order:int)->Dict[str,Any]:
    sku=str(cand.get('sku') or '').strip()
    tries=[]
    for attempt in range(1, RETRY+2):
        if risk(page): return {'ok':False,'sku':sku,'reason':'risk_detected','risk':risk(page),'tries':tries}
        try:
            cur, visible=current_candidate(page,cand,order)
            if cur is None:
                tries.append({'attempt':attempt,'err':'candidate_not_visible','visible_head':[x.get('sku') for x in visible[:8]]})
                time.sleep(1)
                continue
            try: base.close_dialog(page)
            except Exception: pass
            click=base.click_candidate(page,cur,min(order,max(0,len(visible)-1)))
            if not click.get('ok'):
                tries.append({'attempt':attempt,'err':'click_failed','click':click})
                time.sleep(1)
                continue
            result={}
            for sec in range(1,WAIT+1):
                page.wait_for_timeout(1000)
                result=parse_modal(page)
                if risk(page):
                    tries.append({'attempt':attempt,'err':'risk_after_click','risk':risk(page),'click':click})
                    return {'ok':False,'sku':sku,'reason':'risk_after_click','tries':tries}
                if result.get('short_url'): break
            try: base.close_dialog(page)
            except Exception: pass
            if not result.get('short_url'):
                tries.append({'attempt':attempt,'err':'fast_short_url_timeout','wait':WAIT,'click':click,'modal_keys':[k for k,v in result.items() if v]})
                continue
            created,expire,refresh=link_dates()
            row={
                'status':'ok','ts':now(),'worker_name':'hz17_recover_short_url_fast','source_menu':'商品推广/全部商品',
                'menu_mode':'hz17_short_url_recovery_fast','promotion_mode':'hz17_logged_in_onekey_fast','run_id':core.RUN_ID,
                'page_no':page_no,'page_order':order,'sku':sku,'sku_source':'hz17_page_candidate',
                'title':cur.get('title') or cand.get('title'),'item_url':cur.get('itemUrl') or cand.get('itemUrl') or f'https://item.jd.com/{sku}.html',
                'image_url':base.normalize_img(cur.get('imageUrl') or cand.get('imageUrl')),
                'price':cur.get('price') or cand.get('price'),'commission_rate':cur.get('rate') or cand.get('rate'),
                'estimated_income':cur.get('income') or cand.get('income'),'short_url':result.get('short_url'),
                'long_url':result.get('long_url'),'qr_url':result.get('qr_url'),'jd_command':result.get('jd_command'),
                'link_created_at':created,'link_expire_at':expire,'link_expire_days':60,
                'refresh_due_at':refresh,'refresh_after_days':40,'refresh_before_expiry_days':20,'refresh_round':state.get('refresh_round',0),
                'click_result':click
            }
            core.append_jsonl(core.OUT,row)
            if sku and sku not in state['known_skus']: state['known_skus'].append(sku)
            state['fail_streak']=0; core.save_state(state)
            core.write_report(state, {'last_page_no':page_no,'last_recovery_sku':sku,'mode':'hz17_short_url_recovery_fast'})
            log('ITEM_OK_FAST',page_no=page_no,sku=sku,short_url=row.get('short_url'),known_sku_count=len(state.get('known_skus') or []))
            return {'ok':True,'sku':sku,'short_url':row.get('short_url'),'attempt':attempt,'tries':tries}
        except Exception as exc:
            tries.append({'attempt':attempt,'err':repr(exc)})
            try: base.close_dialog(page)
            except Exception: pass
            if risk(page): return {'ok':False,'sku':sku,'reason':'risk_after_exception','risk':risk(page),'tries':tries}
            time.sleep(1)
    return {'ok':False,'sku':sku,'reason':'retry_exhausted_fast','tries':tries}

def page_candidates(page,state,page_no:int)->List[Dict[str,Any]]:
    candidates=base.collect_page_candidates(page)
    known=set(state.get('known_skus') or [])
    fresh=[]; seen=set()
    for cand in candidates:
        sku=str(cand.get('sku') or '').strip(); title=str(cand.get('title') or '').strip()
        if sku.isdigit() and title and sku not in known and sku not in seen:
            fresh.append(cand); seen.add(sku)
    log('PAGE_CANDIDATES_HZ17_FAST',page_no=page_no,total=len(candidates),fresh=len(fresh),sample=[{'sku':x.get('sku'),'title':(x.get('title') or '')[:60]} for x in fresh[:8]])
    return fresh

def main():
    from playwright.sync_api import sync_playwright
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    report={'ts':now(),'pages':parse_pages(PAGE_SEQUENCE),'limit':LIMIT,'retry':RETRY,'wait':WAIT,'results':[]}
    hz15.v4.bootstrap_out_from_history()
    with sync_playwright() as p:
        browser=p.chromium.connect_over_cdp('http://127.0.0.1:19228',timeout=15000)
        page=core.get_active_page(browser); page.set_default_timeout(20000); page.bring_to_front()
        report['initial']=snapshot(page)
        if risk(page):
            report.update(ok=False,reason='risk_initial',risk=risk(page)); REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8'); log('HZ17_DONE',ok=False,reason=report['reason']); return
        total_ok=0; total_fail=0
        for page_no in report['pages']:
            ready=ensure_page(page,page_no); report.setdefault('page_ready',{})[str(page_no)]=ready
            if not ready.get('ok'):
                report.update(ok=False,reason=f'page_{page_no}_not_ready'); break
            state=core.load_state(); state.setdefault('known_skus',[])
            fresh=page_candidates(page,state,page_no)
            consecutive_fail=0; page_ok=0; page_fail=0
            for order,cand in enumerate(fresh[:LIMIT]):
                sku=str(cand.get('sku') or '')
                log('ITEM_START_HZ17_FAST',page_no=page_no,order=order,sku=sku,title=(cand.get('title') or '')[:80])
                res=collect_fast(page,cand,state,page_no,order)
                report['results'].append({'page_no':page_no,'order':order,**res})
                log('ITEM_RESULT_HZ17_FAST',page_no=page_no,sku=res.get('sku'),ok=res.get('ok'),reason=res.get('reason'),attempt=res.get('attempt'),short_url=res.get('short_url'))
                state=core.load_state(); state.setdefault('known_skus',[])
                if res.get('ok'):
                    total_ok+=1; page_ok+=1; consecutive_fail=0
                else:
                    total_fail+=1; page_fail+=1; consecutive_fail+=1
                    if consecutive_fail>=FAIL_FUSE:
                        log('PAGE_FAIL_FUSE_HZ17_FAST',page_no=page_no,consecutive_fail=consecutive_fail,page_ok=page_ok,page_fail=page_fail)
                        break
                time.sleep(random.uniform(ITEM_SLEEP_MIN,ITEM_SLEEP_MAX))
            report.setdefault('page_summary',{})[str(page_no)]={'ok':page_ok,'fail':page_fail,'fresh_initial':len(fresh),'final_snapshot':snapshot(page)}
        state=core.load_state()
        report.update(ok=not bool(report.get('reason')),total_ok=total_ok,total_fail=total_fail,known_sku_count=len(state.get('known_skus') or []),final=snapshot(page))
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
    log('HZ17_DONE',ok=report.get('ok'),total_ok=report.get('total_ok'),total_fail=report.get('total_fail'),known_sku_count=report.get('known_sku_count'))
if __name__=='__main__': main()
