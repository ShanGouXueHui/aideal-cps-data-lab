#!/usr/bin/env python3
"""HZ15 jump-pages collector v5 no-reset.

Fix over v4:
- v4 imported HZ15 v2, whose strict_page_info monkey-patched v1.page_info and
  recursively called itself, causing RecursionError before any page work.
- v5 imports the original HZ15 jump-pages module directly and defines its own
  raw_page_info/strict risk functions. No recursive monkey patch is used.

Behavior:
- If current browser page is already a usable 商品推广/全部商品 list, do not reset
  to pageNo=1 and do not click 商品推广/全部商品 again.
- Jump directly to the configured page sequence, e.g. 11-20.
- Strict risk verification detection only; no bypass.
- Cumulative latest bootstrap and bad-SKU skip behavior are inherited from the
  HZ14 v4/v3 dependency chain.
"""

from __future__ import annotations

import importlib.util
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List

HZ15_ORIG_PATH = Path("run/hz15_jump_pages_collector.py")


def load_hz15_orig():
    if not HZ15_ORIG_PATH.exists():
        raise RuntimeError(f"missing dependency: {HZ15_ORIG_PATH}")
    spec = importlib.util.spec_from_file_location("hz15_orig", str(HZ15_ORIG_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


hz15 = load_hz15_orig()  # original jump-pages module, not v2/v3/v4 wrapper
core = hz15.v1           # HZ14/HZ12 compatible core module
base = hz15.base         # page/modal helper module

STRICT_RISK_MARKERS = [
    "risk_handler",
    "京东验证",
    "快速验证",
    "安全验证",
    "验证码",
    "滑块",
    "购物无忧",
]

PAGE_SEQUENCE_ENV = os.environ.get("HZ15_PAGE_SEQUENCE", "")
PAGE_START = int(os.environ.get("HZ15_PAGE_START", "11"))
PAGE_END = int(os.environ.get("HZ15_PAGE_END", "20"))
RUN_ONCE = os.environ.get("HZ15_RUN_ONCE", os.environ.get("HZ14_RUN_ONCE", "true")).lower() in {"1", "true", "yes"}


def strict_page_text(page) -> str:
    try:
        return page.evaluate("() => document.body ? (document.body.innerText || '') : ''")
    except Exception:
        return ""


def strict_risk_info(page) -> List[str]:
    txt = strict_page_text(page)
    url = page.url or ""
    title = ""
    try:
        title = page.title() or ""
    except Exception:
        title = ""
    haystack = "\n".join([url, title, txt])
    return [x for x in STRICT_RISK_MARKERS if x in haystack]


def strict_check_risk(page, context: str) -> None:
    risk = strict_risk_info(page)
    if risk:
        core.stop_required("jd_risk_verification_required", context=context, url=page.url, risk=risk)


def raw_page_info(page) -> Dict[str, Any]:
    info = page.evaluate(
        """
        () => {
          const txt = document.body ? (document.body.innerText || '') : '';
          const skus = [];
          for (const a of Array.from(document.querySelectorAll('a[href]'))) {
            const m = (a.href || '').match(/\/(\d{5,})\.html/);
            if (m && !skus.includes(m[1])) skus.push(m[1]);
          }
          const pager = document.querySelector('.el-pagination');
          const active = pager ? Array.from(pager.querySelectorAll('.el-pager li')).find(el => String(el.className || '').includes('active')) : null;
          const input = pager ? pager.querySelector('.el-pagination__jump input, input.el-input__inner') : null;
          return {
            url: location.href,
            title: document.title,
            oneKeyCount: (txt.match(/一键领链/g) || []).length,
            skuCount: skus.length,
            skus: skus.slice(0, 100),
            has4000: txt.includes('共 4000 条') || txt.includes('共4000条'),
            hasEmpty: txt.includes('抱歉，没有找到相关商品'),
            pagerText: pager ? (pager.innerText || pager.textContent || '').replace(/\s+/g, ' ').trim() : '',
            activePageText: active ? (active.innerText || active.textContent || '').replace(/\s+/g, '').trim() : null,
            jumpInputValue: input ? (input.value || '') : null
          };
        }
        """
    )
    info["risk"] = strict_risk_info(page)
    return info


# Patch original HZ15 module and HZ14 core to strict non-recursive risk/page info.
core.RISK_MARKERS = STRICT_RISK_MARKERS
core.risk_info = strict_risk_info
core.check_risk = strict_check_risk
hz15.page_info = raw_page_info


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
    info = raw_page_info(page)
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
    core.check_risk(page, "hz15_v5_after_ready")
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
        core.write_report(state, {"last_page_no": page_no, "last_page_processed": n, "cycle_processed": processed_total, "page_sequence": pages, "mode": "hz15_v5_no_reset"})
    return processed_total


from playwright.sync_api import sync_playwright


def main() -> None:
    if core.STOP_PATH.exists():
        core.stop_required("existing_stop_file_present")
    pages = build_page_sequence()
    hz15.v4.bootstrap_out_from_history()
    core.log("HZ15_NO_RESET_V5_START", target_total=core.TARGET_TOTAL, pages=pages, item_sleep=[core.ITEM_SLEEP_MIN, core.ITEM_SLEEP_MAX], page_sleep=[core.PAGE_SLEEP_MIN, core.PAGE_SLEEP_MAX], run_once=RUN_ONCE)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{base.CDP_PORT}", timeout=15000)
        page = core.get_active_page(browser)
        page.set_default_timeout(20000)
        while True:
            state = core.load_state()
            if len(state.get("known_skus") or []) >= core.TARGET_TOTAL:
                core.write_report(state, {"sleep_reason": "target_total_reached", "mode": "hz15_v5_no_reset"})
                core.log("SLEEP_TARGET_TOTAL", known_sku_count=len(state.get("known_skus") or []), target_total=core.TARGET_TOTAL)
                if RUN_ONCE:
                    break
                time.sleep(core.CYCLE_SLEEP)
                continue
            n = run_pages_no_reset(page, state, pages)
            state = core.load_state()
            core.write_report(state, {"cycle_finished": True, "cycle_processed": n, "page_sequence": pages, "mode": "hz15_v5_no_reset"})
            core.log("CYCLE_DONE", processed=n, known_sku_count=len(state.get("known_skus") or []))
            if RUN_ONCE:
                break
            time.sleep(core.CYCLE_SLEEP)


if __name__ == "__main__":
    main()
