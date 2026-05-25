#!/usr/bin/env python3
"""HZ15 jump-pages collector v3 no-reset.

Fix over v2:
- v2 still resets to proManager/index?pageNo=1 and clicks 商品推广/全部商品 at start.
  That can call color_unionSearchGoods immediately and trigger JD verification even
  when the noVNC page is already on a valid 商品推广/全部商品 list page.
- v3 skips reset/click if the current browser page is already a usable JD Union
  product list: oneKeyCount > 0 and not risk. It then jumps directly to the target
  page sequence such as 11-20.

Scope:
- 商品推广 / 全部商品 only.
- Strict risk detection inherited from HZ15 v2.
- Cumulative latest bootstrap inherited from HZ15/HZ14 chain.
- No risk bypass.
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


v2 = load_v2()
v1 = v2.v1
base_v1 = v2.base_v1
base = v1.base

# v2 has already patched strict risk detectors during import.

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
        return [x for x in nums if 1 <= x <= v1.PAGE_MAX]
    return list(range(max(1, PAGE_START), min(v1.PAGE_MAX, PAGE_END) + 1))


def current_page_usable(page) -> Dict[str, Any]:
    info = v2.strict_page_info(page)
    usable = bool((info.get("oneKeyCount") or 0) > 0 and (info.get("skuCount") or 0) > 0 and not info.get("risk"))
    return {"usable": usable, "info": info}


def ensure_product_list_without_reset(page) -> Dict[str, Any]:
    probe = current_page_usable(page)
    if probe["usable"]:
        v1.log("NO_RESET_CURRENT_LIST_OK", info={k: probe["info"].get(k) for k in ["url", "activePageText", "oneKeyCount", "skuCount", "has4000", "risk"]})
        try:
            page.evaluate("""() => { document.body.style.zoom='80%'; const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); }""")
        except Exception:
            pass
        return {"ok": True, "mode": "current_page", "info": probe["info"]}
    # Last resort: use original reset; this can still trigger verification but keeps a fallback.
    v1.log("NO_RESET_CURRENT_LIST_NOT_USABLE", info={k: probe["info"].get(k) for k in ["url", "activePageText", "oneKeyCount", "skuCount", "has4000", "risk"]})
    return v1.reset_product_all(page)


def run_pages_no_reset(page, state: Dict[str, Any], pages: List[int]) -> int:
    start = ensure_product_list_without_reset(page)
    v1.log("PRODUCT_ALL_READY", result=start)
    v1.check_risk(page, "hz15_v3_after_ready")
    processed_total = 0
    for page_no in pages:
        state = v1.load_state()
        if len(state.get("known_skus") or []) >= v1.TARGET_TOTAL:
            v1.log("TARGET_TOTAL_REACHED", known_sku_count=len(state.get("known_skus") or []), target_total=v1.TARGET_TOTAL)
            break
        sleep_s = random.uniform(v1.PAGE_SLEEP_MIN, v1.PAGE_SLEEP_MAX)
        v1.log("PAGE_JUMP_SLEEP", target_page=page_no, seconds=round(sleep_s, 2))
        time.sleep(sleep_s)
        jump = v1.jump_to_page(page, page_no)
        if not jump.get("ok"):
            v1.stop_required("page_jump_failed", page_no=page_no, jump_result=jump)
        state["current_page_no"] = page_no
        v1.save_state(state)
        n = v1.collect_current_page(page, state, page_no)
        processed_total += n
        state = v1.load_state()
        pages_done = state.setdefault("pages_done", [])
        if page_no not in pages_done:
            pages_done.append(page_no)
        v1.save_state(state)
        v1.write_report(state, {"last_page_no": page_no, "last_page_processed": n, "cycle_processed": processed_total, "page_sequence": pages, "mode": "hz15_v3_no_reset"})
    return processed_total


from playwright.sync_api import sync_playwright


def main() -> None:
    if v1.STOP_PATH.exists():
        v1.stop_required("existing_stop_file_present")
    pages = build_page_sequence()
    v1.v4.bootstrap_out_from_history()
    v1.log("HZ15_NO_RESET_JUMP_PAGES_START", target_total=v1.TARGET_TOTAL, pages=pages, item_sleep=[v1.ITEM_SLEEP_MIN, v1.ITEM_SLEEP_MAX], page_sleep=[v1.PAGE_SLEEP_MIN, v1.PAGE_SLEEP_MAX], run_once=RUN_ONCE)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{base.CDP_PORT}", timeout=15000)
        page = v1.get_active_page(browser)
        page.set_default_timeout(20000)
        while True:
            state = v1.load_state()
            if len(state.get("known_skus") or []) >= v1.TARGET_TOTAL:
                v1.write_report(state, {"sleep_reason": "target_total_reached", "mode": "hz15_v3_no_reset"})
                v1.log("SLEEP_TARGET_TOTAL", known_sku_count=len(state.get("known_skus") or []), target_total=v1.TARGET_TOTAL)
                if RUN_ONCE:
                    break
                time.sleep(v1.CYCLE_SLEEP)
                continue
            n = run_pages_no_reset(page, state, pages)
            state = v1.load_state()
            v1.write_report(state, {"cycle_finished": True, "cycle_processed": n, "page_sequence": pages, "mode": "hz15_v3_no_reset"})
            v1.log("CYCLE_DONE", processed=n, known_sku_count=len(state.get("known_skus") or []))
            if RUN_ONCE:
                break
            time.sleep(v1.CYCLE_SLEEP)


if __name__ == "__main__":
    main()
