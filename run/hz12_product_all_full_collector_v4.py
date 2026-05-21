#!/usr/bin/env python3
"""HZ12 product_all v4 runner with UI pagination.

Rationale:
- product_all URL pageNo can show repeated data in the SPA.
- The official page has a bottom pager with 上一页 / 下一页 / 前往.
- v4 keeps the validated v3 title/click flow, but overrides full_cycle to advance pages via the live UI pager instead of URL-only navigation.
"""

from __future__ import annotations

import importlib.util
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

V3_PATH = Path("run/hz12_product_all_full_collector_v3.py")


def load_v3():
    if not V3_PATH.exists():
        raise RuntimeError(f"missing v3 runner: {V3_PATH}")
    spec = importlib.util.spec_from_file_location("hz12_v3", str(V3_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v3 = load_v3()
base = v3.base
base.collect_page_candidates = v3.collect_page_candidates_v3


def current_page_skus(page) -> List[str]:
    try:
        cards = base.collect_page_candidates(page)
    except Exception:
        cards = []
    out: List[str] = []
    for c in cards:
        sku = str(c.get("sku") or "").strip()
        if sku and sku not in out:
            out.append(sku)
    return out[:20]


def click_product_all_next_page(page, state: Dict[str, Any]) -> Dict[str, Any]:
    before = current_page_skus(page)[:8]
    try:
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)
    except Exception:
        pass

    click_res = page.evaluate(
        """
        () => {
          const norm = s => (s || '').replace(/\s+/g, '').trim();
          const nodes = Array.from(document.querySelectorAll('button,a,span,div,li'));
          const mapped = nodes.map((el, idx) => {
            const r = el.getBoundingClientRect();
            const txt = norm(el.innerText || el.textContent);
            const cls = String(el.className || '');
            const aria = String(el.getAttribute('aria-label') || '');
            const disabled = el.disabled || el.getAttribute('disabled') !== null || cls.includes('disabled') || cls.includes('is-disabled') || el.getAttribute('aria-disabled') === 'true';
            const visible = r.width > 0 && r.height > 0 && r.top >= -150 && r.left >= -80 && r.top <= window.innerHeight + 220;
            return {el, idx, txt, cls, aria, disabled, visible, rect:{x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2}};
          });
          const candidates = mapped.filter(x => x.visible && !x.disabled && (
              x.txt === '下一页' || x.txt.includes('下一页') ||
              x.cls.includes('btn-next') || x.cls === 'next' || x.cls.includes(' next') ||
              x.aria.includes('下一页') || x.aria.toLowerCase().includes('next')
            ))
            .sort((a,b) => {
              const at = a.txt === '下一页' ? 0 : 1;
              const bt = b.txt === '下一页' ? 0 : 1;
              if (at !== bt) return at - bt;
              return b.rect.y - a.rect.y;
            });
          if (!candidates.length) {
            return {ok:false, reason:'next_not_found', samples:mapped.filter(x => x.txt.includes('上一页') || x.txt.includes('下一页') || x.cls.includes('next')).slice(-30).map(x => ({idx:x.idx,txt:x.txt,cls:x.cls.slice(0,120),aria:x.aria,disabled:x.disabled,visible:x.visible,rect:x.rect}))};
          }
          const t = candidates[0];
          t.el.scrollIntoView({block:'center', inline:'center'});
          t.el.dispatchEvent(new MouseEvent('mouseover', {bubbles:true, cancelable:true, view:window}));
          t.el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true, view:window}));
          t.el.click();
          t.el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true, view:window}));
          return {ok:true, clicked:{idx:t.idx,txt:t.txt,cls:t.cls.slice(0,120),aria:t.aria,rect:t.rect}};
        }
        """
    )

    if not click_res.get("ok"):
        base.log("PRODUCT_NEXT_PAGE_FAIL", result=click_res)
        return click_res

    changed = False
    after: List[str] = []
    for _ in range(18):
        page.wait_for_timeout(1000)
        after = current_page_skus(page)[:8]
        if after and after != before:
            changed = True
            break

    if changed:
        state["current_page_no"] = int(state.get("current_page_no") or 1) + 1
        base.save_state(state)

    result = {
        "ok": True,
        "changed": changed,
        "page_no": state.get("current_page_no"),
        "before_skus": before[:5],
        "after_skus": after[:5],
        "clicked": click_res.get("clicked"),
    }
    base.log("PRODUCT_NEXT_PAGE", result=result)
    return result


def full_cycle_v4(page, state: Dict[str, Any]) -> int:
    processed = 0
    no_next_or_unchanged = 0
    page_no = int(state.get("current_page_no") or base.PAGE_START)

    # Start from the official first product_all page for each full refresh.
    if page_no <= base.PAGE_START:
        page.goto(base.URL_TEMPLATE.format(page_no=base.PAGE_START), wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        state["current_page_no"] = base.PAGE_START
        base.save_state(state)

    while page_no <= base.PAGE_MAX:
        state["current_page_no"] = page_no
        base.save_state(state)

        info = base.check_page(page)
        total_hint = base.extract_page_total(page)
        if total_hint:
            state["page_total_hint"] = total_hint
            base.save_state(state)

        candidates = base.collect_page_candidates(page)
        seen = set(state.get("known_skus") or [])
        fresh: List[Dict[str, Any]] = []
        fresh_skus = set()
        for cand in candidates:
            sku = str(cand.get("sku") or "").strip()
            if sku.isdigit() and sku not in seen and sku not in fresh_skus:
                fresh.append(cand)
                fresh_skus.add(sku)

        base.log("PAGE_CANDIDATES", page_no=page_no, total=len(candidates), fresh=len(fresh), processed=processed, page_info=info, total_hint=total_hint, sample=[{"sku": x.get("sku"), "title": (x.get("title") or "")[:60]} for x in fresh[:6]])

        for order, cand in enumerate(fresh[:base.ITEMS_PER_PAGE_LIMIT]):
            try:
                row = base.collect_one(page, cand, state, page_no, order)
                if row:
                    processed += 1
                    base.write_report(state, {"last_cycle_processed": processed, "last_page_no": page_no})
                time.sleep(random.uniform(base.ITEM_SLEEP_MIN, base.ITEM_SLEEP_MAX))
            except Exception as exc:
                state["fail_streak"] = int(state.get("fail_streak") or 0) + 1
                state["last_event"] = {"event":"ITEM_FAIL", "ts":base.now(), "page_no":page_no, "sku":cand.get("sku"), "error":repr(exc)}
                base.save_state(state)
                base.log("ITEM_FAIL", page_no=page_no, sku=cand.get("sku"), err=repr(exc), fail_streak=state["fail_streak"])
                base.close_dialog(page)
                if state["fail_streak"] >= base.MAX_FAIL_STREAK:
                    base.stop_required("max_fail_streak_reached", page_no=page_no, sku=cand.get("sku"), fail_streak=state["fail_streak"], last_error=repr(exc))
                time.sleep(random.uniform(20, 40))

        base.write_report(state, {"last_cycle_processed": processed, "last_page_no": page_no})

        if len(state.get("known_skus") or []) >= base.TARGET_TOTAL:
            base.log("TARGET_TOTAL_REACHED", known_sku_count=len(state["known_skus"]), target_total=base.TARGET_TOTAL)
            break

        next_res = click_product_all_next_page(page, state)
        base.write_report(state, {"last_cycle_processed": processed, "last_page_no": page_no, "last_product_next": next_res})

        if next_res.get("ok") and next_res.get("changed"):
            no_next_or_unchanged = 0
            page_no = int(state.get("current_page_no") or page_no + 1)
            time.sleep(random.uniform(base.PAGE_SLEEP_MIN, base.PAGE_SLEEP_MAX))
            continue

        no_next_or_unchanged += 1
        if no_next_or_unchanged >= base.EMPTY_PAGE_LIMIT:
            base.log("PRODUCT_NEXT_UNCHANGED_LIMIT", page_no=page_no, count=no_next_or_unchanged, last_next=next_res)
            break
        time.sleep(random.uniform(base.PAGE_SLEEP_MIN, base.PAGE_SLEEP_MAX))

    state["last_full_cycle_finished_at"] = base.now()
    state["next_refresh_due_at"] = (datetime.now() + timedelta(days=base.REFRESH_AFTER_DAYS)).isoformat(timespec="seconds")
    state["current_page_no"] = base.PAGE_START
    state["round_seen_skus"] = []
    base.save_state(state)
    merged = base.dedup_latest_by_sku()
    base.write_report(state, {"cycle_finished": True, "cycle_processed": processed, "dedup_after_cycle": len(merged)})
    return processed


base.full_cycle = full_cycle_v4


if __name__ == "__main__":
    base.main()
