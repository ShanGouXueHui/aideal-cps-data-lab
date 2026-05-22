#!/usr/bin/env python3
"""HZ12 product_all v7 runner.

v7 uses the successful HZ12X probe result: Playwright exact-text click on the
visible 下一页 control changes the SKU list. It keeps v5 strict-title quality gate
and replaces the pager step with page.get_by_text('下一页', exact=True).last.click().
"""

from __future__ import annotations

import importlib.util
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

V5_PATH = Path("run/hz12_product_all_full_collector_v5.py")


def load_v5():
    if not V5_PATH.exists():
        raise RuntimeError(f"missing v5 runner: {V5_PATH}")
    spec = importlib.util.spec_from_file_location("hz12_v5", str(V5_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v5 = load_v5()
base = v5.base
base.collect_page_candidates = v5.collect_page_candidates_strict_title


def current_page_skus(page) -> List[str]:
    try:
        cards = base.collect_page_candidates(page)
    except Exception:
        cards = []
    out: List[str] = []
    for card in cards:
        sku = str(card.get("sku") or "").strip()
        if sku and sku not in out:
            out.append(sku)
    return out[:20]


def click_next_by_exact_text(page, state: Dict[str, Any]) -> Dict[str, Any]:
    before = current_page_skus(page)[:8]
    click_result: Dict[str, Any] = {"ok": False}

    try:
        locator = page.get_by_text("下一页", exact=True)
        count = locator.count()
        if count <= 0:
            click_result = {"ok": False, "reason": "no_exact_next_text", "count": count}
        else:
            locator.last.click(timeout=8000)
            click_result = {"ok": True, "method": "get_by_text_exact_last", "count": count}
    except Exception as exc:
        click_result = {"ok": False, "reason": "click_exception", "err": repr(exc)}

    if not click_result.get("ok"):
        base.log("PRODUCT_NEXT_TEXT_FAIL", result=click_result)
        return click_result

    changed = False
    after: List[str] = []
    for _ in range(20):
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
        "click": click_result,
    }
    base.log("PRODUCT_NEXT_TEXT", result=result)
    return result


def full_cycle_v7(page, state: Dict[str, Any]) -> int:
    processed = 0
    unchanged = 0
    page_no = int(state.get("current_page_no") or base.PAGE_START)

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
            title = str(cand.get("title") or "").strip()
            if sku.isdigit() and title and sku not in seen and sku not in fresh_skus:
                fresh.append(cand)
                fresh_skus.add(sku)

        base.log(
            "PAGE_CANDIDATES",
            page_no=page_no,
            total=len(candidates),
            fresh=len(fresh),
            processed=processed,
            page_info=info,
            total_hint=total_hint,
            sample=[{"sku": x.get("sku"), "title": (x.get("title") or "")[:60]} for x in fresh[:6]],
        )

        for order, cand in enumerate(fresh[:base.ITEMS_PER_PAGE_LIMIT]):
            try:
                row = base.collect_one(page, cand, state, page_no, order)
                if row:
                    processed += 1
                    base.write_report(state, {"last_cycle_processed": processed, "last_page_no": page_no})
                time.sleep(random.uniform(base.ITEM_SLEEP_MIN, base.ITEM_SLEEP_MAX))
            except Exception as exc:
                state["fail_streak"] = int(state.get("fail_streak") or 0) + 1
                state["last_event"] = {"event": "ITEM_FAIL", "ts": base.now(), "page_no": page_no, "sku": cand.get("sku"), "error": repr(exc)}
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

        next_res = click_next_by_exact_text(page, state)
        base.write_report(state, {"last_cycle_processed": processed, "last_page_no": page_no, "last_product_next_text": next_res})

        if next_res.get("ok") and next_res.get("changed"):
            unchanged = 0
            page_no = int(state.get("current_page_no") or page_no + 1)
            time.sleep(random.uniform(base.PAGE_SLEEP_MIN, base.PAGE_SLEEP_MAX))
            continue

        unchanged += 1
        if unchanged >= base.EMPTY_PAGE_LIMIT:
            base.log("PRODUCT_NEXT_TEXT_UNCHANGED_LIMIT", page_no=page_no, count=unchanged, last_next=next_res)
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


base.full_cycle = full_cycle_v7


if __name__ == "__main__":
    base.main()
