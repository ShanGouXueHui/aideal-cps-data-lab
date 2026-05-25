#!/usr/bin/env python3
"""HZ15 jump-pages collector v6 no-reset strict-4000 gate.

Fix over v5:
- v5 correctly avoided reset, but accepted a non-commercial list page as usable:
  oneKeyCount=50, pagerText='共 0 条1前往页', has4000=false. That page has no visible
  jump input, so page 11 jump failed.
- v6 only runs when the current browser page is the proven 商品推广 / 全部商品 list:
  has4000=true, oneKeyCount>=55, skuCount>=55, and no strict risk signals.
- If the page is not the 4000 all-product list, v6 stops with
  manual_product_all_4000_required and does not reset/click automatically.

Scope:
- JD Union 商品推广 / 全部商品 only.
- No reset to pageNo=1.
- No automatic channel click.
- Strict risk detection and cumulative latest inherited from v5.
"""

from __future__ import annotations

import importlib.util
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List

V5_PATH = Path("run/hz15_jump_pages_collector_v5_no_reset.py")


def load_v5():
    if not V5_PATH.exists():
        raise RuntimeError(f"missing dependency: {V5_PATH}")
    spec = importlib.util.spec_from_file_location("hz15_v5", str(V5_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v5 = load_v5()
hz15 = v5.hz15
core = v5.core
base = v5.base

PAGE_SEQUENCE_ENV = os.environ.get("HZ15_PAGE_SEQUENCE", "")
PAGE_START = int(os.environ.get("HZ15_PAGE_START", "11"))
PAGE_END = int(os.environ.get("HZ15_PAGE_END", "20"))
RUN_ONCE = os.environ.get("HZ15_RUN_ONCE", os.environ.get("HZ14_RUN_ONCE", "true")).lower() in {"1", "true", "yes"}


def build_page_sequence() -> List[int]:
    if PAGE_SEQUENCE_ENV.strip():
        nums: List[int] = []
        for part in PAGE_SEQUENCE_ENV.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                nums.extend(range(int(a), int(b) + 1))
            else:
                nums.append(int(part))
        return [x for x in nums if 1 <= x <= core.PAGE_MAX]
    return list(range(max(1, PAGE_START), min(core.PAGE_MAX, PAGE_END) + 1))


def current_all_product_4000_usable(page) -> Dict[str, Any]:
    info = v5.raw_page_info(page)
    pager_text = str(info.get("pagerText") or "")
    usable = bool(
        not info.get("risk")
        and bool(info.get("has4000"))
        and (info.get("oneKeyCount") or 0) >= 55
        and (info.get("skuCount") or 0) >= 55
        and ("4000" in pager_text)
    )
    return {"usable": usable, "info": info}


def ensure_all_product_4000_without_reset(page) -> Dict[str, Any]:
    probe = current_all_product_4000_usable(page)
    info = probe["info"]
    short = {k: info.get(k) for k in ["url", "activePageText", "oneKeyCount", "skuCount", "has4000", "pagerText", "jumpInputValue", "risk"]}
    if probe["usable"]:
        core.log("STRICT_4000_CURRENT_LIST_OK", info=short)
        try:
            page.evaluate("""() => { document.body.style.zoom='80%'; const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); }""")
        except Exception:
            pass
        return {"ok": True, "mode": "current_all_product_4000", "info": info}
    core.log("STRICT_4000_CURRENT_LIST_NOT_USABLE", info=short)
    core.stop_required("manual_product_all_4000_required", info=short)
    return {"ok": False, "mode": "manual_required", "info": info}


def run_pages_strict_4000(page, state: Dict[str, Any], pages: List[int]) -> int:
    ready = ensure_all_product_4000_without_reset(page)
    core.log("PRODUCT_ALL_4000_READY", result=ready)
    core.check_risk(page, "hz15_v6_after_ready")
    processed_total = 0
    for page_no in pages:
        state = core.load_state()
        if len(state.get("known_skus") or []) >= core.TARGET_TOTAL:
            core.log("TARGET_TOTAL_REACHED", known_sku_count=len(state.get("known_skus") or []), target_total=core.TARGET_TOTAL)
            break
        sleep_s = random.uniform(core.PAGE_SLEEP_MIN, core.PAGE_SLEEP_MAX)
        core.log("PAGE_JUMP_SLEEP", target_page=page_no, seconds=round(sleep_s, 2))
        time.sleep(sleep_s)
        jump = hz15.jump_to_page(page, page_no)
        if not jump.get("ok"):
            core.stop_required("page_jump_failed", page_no=page_no, jump_result=jump)
        state["current_page_no"] = page_no
        core.save_state(state)
        n = core.collect_current_page(page, state, page_no)
        processed_total += n
        state = core.load_state()
        pages_done = state.setdefault("pages_done", [])
        if page_no not in pages_done:
            pages_done.append(page_no)
        core.save_state(state)
        core.write_report(state, {"last_page_no": page_no, "last_page_processed": n, "cycle_processed": processed_total, "page_sequence": pages, "mode": "hz15_v6_no_reset_strict_4000"})
    return processed_total


from playwright.sync_api import sync_playwright


def main() -> None:
    if core.STOP_PATH.exists():
        core.stop_required("existing_stop_file_present")
    pages = build_page_sequence()
    hz15.v4.bootstrap_out_from_history()
    core.log("HZ15_NO_RESET_V6_STRICT_4000_START", target_total=core.TARGET_TOTAL, pages=pages, item_sleep=[core.ITEM_SLEEP_MIN, core.ITEM_SLEEP_MAX], page_sleep=[core.PAGE_SLEEP_MIN, core.PAGE_SLEEP_MAX], run_once=RUN_ONCE)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{base.CDP_PORT}", timeout=15000)
        page = core.get_active_page(browser)
        page.set_default_timeout(20000)
        while True:
            state = core.load_state()
            if len(state.get("known_skus") or []) >= core.TARGET_TOTAL:
                core.write_report(state, {"sleep_reason": "target_total_reached", "mode": "hz15_v6_no_reset_strict_4000"})
                core.log("SLEEP_TARGET_TOTAL", known_sku_count=len(state.get("known_skus") or []), target_total=core.TARGET_TOTAL)
                if RUN_ONCE:
                    break
                time.sleep(core.CYCLE_SLEEP)
                continue
            n = run_pages_strict_4000(page, state, pages)
            state = core.load_state()
            core.write_report(state, {"cycle_finished": True, "cycle_processed": n, "page_sequence": pages, "mode": "hz15_v6_no_reset_strict_4000"})
            core.log("CYCLE_DONE", processed=n, known_sku_count=len(state.get("known_skus") or []))
            if RUN_ONCE:
                break
            time.sleep(core.CYCLE_SLEEP)


if __name__ == "__main__":
    main()
