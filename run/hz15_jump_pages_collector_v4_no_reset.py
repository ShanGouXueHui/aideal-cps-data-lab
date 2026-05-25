#!/usr/bin/env python3
"""HZ15 jump-pages collector v4 no-reset.

Fix over v3:
- v3 used the HZ15 module alias for HZ14 helper functions such as log/load_state,
  which can make the worker exit before writing JSON events.
- v4 keeps two explicit aliases:
  * hz15: the HZ15 jump-pages module
  * core: the HZ14/HZ12 compatible collector core module inside hz15.v1

Behavior:
- If current browser page is already a usable 商品推广/全部商品 list, do not reset
  to pageNo=1 and do not click the channel again.
- Use jump input for pages 11..20.
- Keep strict risk detection from HZ15 v2.
"""

from __future__ import annotations

import importlib.util
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List

V2_PATH = Path("run/hz15_jump_pages_collector_v2.py")


def load_v2():
    if not V2_PATH.exists():
        raise RuntimeError(f"missing dependency: {V2_PATH}")
    spec = importlib.util.spec_from_file_location("hz15_v2", str(V2_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


hz15_v2 = load_v2()
hz15 = hz15_v2.v1          # run/hz15_jump_pages_collector.py module
core = hz15.v1             # HZ14/HZ12 compatible core module
base = hz15.base           # original page/modal helper base module

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


def current_page_usable(page) -> Dict[str, Any]:
    info = hz15_v2.strict_page_info(page)
    usable = bool((info.get("oneKeyCount") or 0) > 0 and (info.get("skuCount") or 0) > 0 and not info.get("risk"))
    return {"usable": usable, "info": info}


def ensure_product_list_without_reset(page) -> Dict[str, Any]:
    probe = current_page_usable(page)
    short = {k: probe["info"].get(k) for k in ["url", "activePageText", "oneKeyCount", "skuCount", "has4000", "risk"]}
    if probe["usable"]:
        core.log("NO_RESET_CURRENT_LIST_OK", info=short)
        try:
            page.evaluate("""() => { document.body.style.zoom='80%'; const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); }""")
        except Exception:
            pass
        return {"ok": True, "mode": "current_page", "info": probe["info"]}
    core.log("NO_RESET_CURRENT_LIST_NOT_USABLE", info=short)
    return hz15.reset_product_all(page)


def run_pages_no_reset(page, state: Dict[str, Any], pages: List[int]) -> int:
    ready = ensure_product_list_without_reset(page)
    core.log("PRODUCT_ALL_READY", result=ready)
    core.check_risk(page, "hz15_v4_after_ready")
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
        core.write_report(state, {"last_page_no": page_no, "last_page_processed": n, "cycle_processed": processed_total, "page_sequence": pages, "mode": "hz15_v4_no_reset"})
    return processed_total


from playwright.sync_api import sync_playwright


def main() -> None:
    if core.STOP_PATH.exists():
        core.stop_required("existing_stop_file_present")
    pages = build_page_sequence()
    hz15.v4.bootstrap_out_from_history()
    core.log("HZ15_NO_RESET_V4_START", target_total=core.TARGET_TOTAL, pages=pages, item_sleep=[core.ITEM_SLEEP_MIN, core.ITEM_SLEEP_MAX], page_sleep=[core.PAGE_SLEEP_MIN, core.PAGE_SLEEP_MAX], run_once=RUN_ONCE)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{base.CDP_PORT}", timeout=15000)
        page = core.get_active_page(browser)
        page.set_default_timeout(20000)
        while True:
            state = core.load_state()
            if len(state.get("known_skus") or []) >= core.TARGET_TOTAL:
                core.write_report(state, {"sleep_reason": "target_total_reached", "mode": "hz15_v4_no_reset"})
                core.log("SLEEP_TARGET_TOTAL", known_sku_count=len(state.get("known_skus") or []), target_total=core.TARGET_TOTAL)
                if RUN_ONCE:
                    break
                time.sleep(core.CYCLE_SLEEP)
                continue
            n = run_pages_no_reset(page, state, pages)
            state = core.load_state()
            core.write_report(state, {"cycle_finished": True, "cycle_processed": n, "page_sequence": pages, "mode": "hz15_v4_no_reset"})
            core.log("CYCLE_DONE", processed=n, known_sku_count=len(state.get("known_skus") or []))
            if RUN_ONCE:
                break
            time.sleep(core.CYCLE_SLEEP)


if __name__ == "__main__":
    main()
