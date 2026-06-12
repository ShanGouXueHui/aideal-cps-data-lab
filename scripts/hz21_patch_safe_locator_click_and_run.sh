#!/usr/bin/env bash
# Patch HZ21 click_card to use exact SKU locator token + safe hit-test, then run page49 smoke.
# No exit and no set -e are used.
PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  mkdir -p logs reports docs/ops run data/import
  TS="$(date +%Y%m%d_%H%M%S)"
  LOG="logs/hz21_safe_locator_click_page49_smoke_${TS}.log"
  JSON="reports/hz21_strict_card_dom_recover_latest.json"
  MD="docs/ops/DL2_HZ21_STRICT_CARD_DOM_PAGE49_SMOKE.md"

  echo "===== patch HZ21 safe locator click and run ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  python3 - <<'PY'
from pathlib import Path
p=Path('run/hz21_strict_card_dom_recover_page.py')
s=p.read_text(encoding='utf-8')
start=s.index('def click_card(page, card:Dict[str,Any])->Dict[str,Any]:')
end=s.index('\ndef collect_one(page,card:Dict[str,Any],state:Dict[str,Any],page_no:int,order:int)->Dict[str,Any]:', start)
new=r'''def click_card(page, card:Dict[str,Any])->Dict[str,Any]:
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
'''
s=s[:start]+new+s[end:]
p.write_text(s, encoding='utf-8')
print('PATCHED=1')
PY
  PATCH_RC=$?

  echo "===== stop collectors only, keep browser/supervisor ====="
  pkill -f "run/hz17_recover_short_url_page.py" || true
  pkill -f "run/hz18_card_click_recover_page.py" || true
  pkill -f "run/hz20_mouse_click_recover_page.py" || true
  pkill -f "run/hz21_strict_card_dom_recover_page.py" || true
  pkill -f "hz15_jump_pages_collector_v6_no_reset_strict_4000.py" || true
  sleep 3
  pgrep -af "hz15_daytime_autostart_supervisor_40_67|hz21_strict|chrome.*19228" | head -n 80 || true

  echo "===== static check ====="
  .venv-browser/bin/python -m py_compile run/hz21_strict_card_dom_recover_page.py
  STATIC_RC=$?

  echo "===== run HZ21 safe locator click smoke ====="
  HZ21_PAGE_SEQUENCE=49 HZ21_LIMIT=20 HZ21_WAIT=10 HZ21_FAIL_FUSE=6 HZ21_ITEM_SLEEP_MIN=1 HZ21_ITEM_SLEEP_MAX=3 .venv-browser/bin/python run/hz21_strict_card_dom_recover_page.py > "$LOG" 2>&1
  HZ21_RC=$?

  echo "===== render markdown summary ====="
  python3 - <<'PY'
import json
from pathlib import Path
j=Path('reports/hz21_strict_card_dom_recover_latest.json')
md=Path('docs/ops/DL2_HZ21_STRICT_CARD_DOM_PAGE49_SMOKE.md')
if not j.exists():
    latest=sorted(Path('logs').glob('hz21_safe_locator_click_page49_smoke_*.log'), key=lambda p:p.stat().st_mtime)[-1]
    md.write_text('# DL2 HZ21 Safe Locator Click Smoke\n\nNo JSON report found.\n\n```text\n'+latest.read_text(encoding='utf-8', errors='replace')[-8000:]+'\n```\n', encoding='utf-8')
else:
    x=json.loads(j.read_text(encoding='utf-8'))
    lines=['# DL2 HZ21 Safe Locator Click Smoke','']
    for k in ['ts','ok','reason','pages','limit','wait','total_ok','total_fail','known_sku_count','quarantine']:
        lines.append(f'- {k}: `{x.get(k)}`')
    lines.append(f'- page_summary: `{json.dumps(x.get("page_summary"), ensure_ascii=False)}`')
    lines.append('\n## results tail\n```json')
    lines.append(json.dumps((x.get('results') or [])[-30:], ensure_ascii=False, indent=2)[:22000])
    lines.append('```')
    md.write_text('\n'.join(lines), encoding='utf-8')
PY

  echo "===== commit reports/data/log ====="
  git add "$JSON" "$MD" "$LOG" run/hz21_strict_card_dom_recover_page.py scripts/hz21_patch_safe_locator_click_and_run.sh data/import/hz_jd_union_all_product_full_links_latest.jsonl data/import/hz_jd_union_product_all_full_links_latest.jsonl run/hz14_all_product_full_report_latest.json run/hz14_all_product_full_state.json 2>/dev/null || true
  git commit -m "docs: publish HZ21 safe locator click smoke" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "PATCH_RC=$PATCH_RC"
  echo "STATIC_RC=$STATIC_RC"
  echo "HZ21_RC=$HZ21_RC"
  echo "LOG=$LOG"
  echo "REPORT=$JSON"
  echo "MD=$MD"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
