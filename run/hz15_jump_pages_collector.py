#!/usr/bin/env python3
"""HZ15 jump-pages all-product collector.

Scope:
- 商品推广 / 全部商品 only.
- Bootstrap cumulative latest from historical HZ12/HZ14 JSONL files.
- Use Element UI jump input (.el-pagination__jump input / input.el-input__inner)
  to navigate target pages directly, proven by HZ15 page 30/60 probe.
- Reuse HZ14 v4/v3 commercial collection logic:
  * strict SKU/title/link parsing
  * skip single bad SKU for short_url_not_found / click_failed
  * STOP_REQUIRED on JD risk verification; no bypass.
"""

from __future__ import annotations

import importlib.util
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

V4_PATH = Path("run/hz14_all_product_full_collector_v4.py")


def load_v4():
    if not V4_PATH.exists():
        raise RuntimeError(f"missing dependency: {V4_PATH}")
    spec = importlib.util.spec_from_file_location("hz14_v4", str(V4_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v4 = load_v4()
v1 = v4.v1
base = v1.base

# Override worker label after importing HZ14 modules.
v1.WORKER = os.environ.get("HZ15_WORKER_NAME", "hz15_jump_pages")
v1.TARGET_TOTAL = int(os.environ.get("HZ15_TARGET_TOTAL", os.environ.get("HZ14_TARGET_TOTAL", "4000")))
v1.PAGE_MAX = int(os.environ.get("HZ15_PAGE_MAX", os.environ.get("HZ14_PAGE_MAX", "67")))
v1.ITEMS_PER_PAGE_LIMIT = int(os.environ.get("HZ15_ITEMS_PER_PAGE_LIMIT", os.environ.get("HZ14_ITEMS_PER_PAGE_LIMIT", "60")))
v1.ITEM_SLEEP_MIN = float(os.environ.get("HZ15_ITEM_SLEEP_MIN", os.environ.get("HZ14_ITEM_SLEEP_MIN", "6")))
v1.ITEM_SLEEP_MAX = float(os.environ.get("HZ15_ITEM_SLEEP_MAX", os.environ.get("HZ14_ITEM_SLEEP_MAX", "12")))
v1.PAGE_SLEEP_MIN = float(os.environ.get("HZ15_PAGE_SLEEP_MIN", os.environ.get("HZ14_PAGE_SLEEP_MIN", "55")))
v1.PAGE_SLEEP_MAX = float(os.environ.get("HZ15_PAGE_SLEEP_MAX", os.environ.get("HZ14_PAGE_SLEEP_MAX", "95")))
v1.MAX_FAIL_STREAK = int(os.environ.get("HZ15_MAX_FAIL_STREAK", os.environ.get("HZ14_MAX_FAIL_STREAK", "3")))

PAGE_SEQUENCE_ENV = os.environ.get("HZ15_PAGE_SEQUENCE", "")
PAGE_START = int(os.environ.get("HZ15_PAGE_START", "1"))
PAGE_END = int(os.environ.get("HZ15_PAGE_END", str(v1.PAGE_MAX)))
RUN_ONCE = os.environ.get("HZ15_RUN_ONCE", os.environ.get("HZ14_RUN_ONCE", "false")).lower() in {"1", "true", "yes"}
JUMP_RETRY = int(os.environ.get("HZ15_JUMP_RETRY", "2"))


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


def page_info(page) -> Dict[str, Any]:
    return page.evaluate(
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
            oneKeyCount: (txt.match(/一键领链/g) || []).length,
            skuCount: skus.length,
            skus: skus.slice(0, 100),
            has4000: txt.includes('共 4000 条') || txt.includes('共4000条'),
            hasEmpty: txt.includes('抱歉，没有找到相关商品'),
            pagerText: pager ? (pager.innerText || pager.textContent || '').replace(/\s+/g, ' ').trim() : '',
            activePageText: active ? (active.innerText || active.textContent || '').replace(/\s+/g, '').trim() : null,
            jumpInputValue: input ? (input.value || '') : null,
            risk: ['快速验证','购物无忧','风险','安全验证','验证码','滑块','risk_handler'].filter(x => txt.includes(x) || location.href.includes(x))
          };
        }
        """
    )


def reset_product_all(page) -> Dict[str, Any]:
    page.goto("https://union.jd.com/proManager/index?pageNo=1", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(5000)
    v1.check_risk(page, "hz15_after_goto_product_manager")
    click_res = v1.click_product_all(page)
    page.wait_for_timeout(6000)
    v1.check_risk(page, "hz15_after_click_product_all")
    page.evaluate("""() => { document.body.style.zoom='80%'; const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); else window.scrollTo(0, document.body.scrollHeight); }""")
    page.wait_for_timeout(1200)
    info = page_info(page)
    return {"click_product_all": click_res, "page_info": info}


def jump_to_page(page, target_page: int) -> Dict[str, Any]:
    v1.check_risk(page, f"hz15_before_jump_{target_page}")
    before = page_info(page)
    before_skus = before.get("skus") or []
    last_result: Dict[str, Any] = {}
    for attempt in range(1, JUMP_RETRY + 1):
        try:
            page.evaluate("""() => { const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); else window.scrollTo(0, document.body.scrollHeight); }""")
            page.wait_for_timeout(800)
            inp = page.locator(".el-pagination .el-pagination__jump input, .el-pagination input.el-input__inner").first
            inp.scroll_into_view_if_needed(timeout=5000)
            inp.click(timeout=5000)
            inp.fill(str(target_page), timeout=5000)
            page.wait_for_timeout(300)
            inp.press("Enter", timeout=5000)
            click_result = {"ok": True, "method": "locator_fill_enter", "attempt": attempt}
        except Exception as exc:
            click_result = {"ok": False, "method": "locator_fill_enter", "attempt": attempt, "err": repr(exc)}
        changed = False
        after: Optional[Dict[str, Any]] = None
        for _ in range(60):
            page.wait_for_timeout(1000)
            v1.check_risk(page, f"hz15_after_jump_{target_page}")
            after = page_info(page)
            after_skus = after.get("skus") or []
            active = str(after.get("activePageText") or "")
            url = str(after.get("url") or "")
            if after_skus and (after_skus[:40] != before_skus[:40] or active == str(target_page) or f"pageNo={target_page}" in url):
                changed = True
                break
        last_result = {"ok": bool(changed and after), "changed": changed, "target_page": target_page, "attempt": attempt, "click": click_result, "before": {"url": before.get("url"), "activePageText": before.get("activePageText"), "skuCount": before.get("skuCount"), "skus": before_skus[:8]}, "after": after}
        v1.log("PAGE_JUMP", target_page=target_page, result=last_result)
        if last_result["ok"]:
            return last_result
        time.sleep(random.uniform(10, 20))
    return last_result


def run_pages(page, state: Dict[str, Any], pages: List[int]) -> int:
    reset = reset_product_all(page)
    v1.log("PRODUCT_ALL_RESET", result=reset)
    v1.check_risk(page, "hz15_after_reset")
    processed_total = 0
    for page_no in pages:
        state = v1.load_state()
        if len(state.get("known_skus") or []) >= v1.TARGET_TOTAL:
            v1.log("TARGET_TOTAL_REACHED", known_sku_count=len(state.get("known_skus") or []), target_total=v1.TARGET_TOTAL)
            break
        if page_no != 1:
            sleep_s = random.uniform(v1.PAGE_SLEEP_MIN, v1.PAGE_SLEEP_MAX)
            v1.log("PAGE_JUMP_SLEEP", target_page=page_no, seconds=round(sleep_s, 2))
            time.sleep(sleep_s)
            jump = jump_to_page(page, page_no)
            if not jump.get("ok"):
                v1.stop_required("page_jump_failed", page_no=page_no, jump_result=jump)
        else:
            info = page_info(page)
            if str(info.get("activePageText") or "1") != "1":
                jump = jump_to_page(page, 1)
                if not jump.get("ok"):
                    v1.stop_required("page_jump_failed", page_no=1, jump_result=jump)
        state["current_page_no"] = page_no
        v1.save_state(state)
        n = v1.collect_current_page(page, state, page_no)
        processed_total += n
        state = v1.load_state()
        pages_done = state.setdefault("pages_done", [])
        if page_no not in pages_done:
            pages_done.append(page_no)
        v1.save_state(state)
        v1.write_report(state, {"last_page_no": page_no, "last_page_processed": n, "cycle_processed": processed_total, "page_sequence": pages})
    return processed_total


from playwright.sync_api import sync_playwright


def main() -> None:
    if v1.STOP_PATH.exists():
        v1.stop_required("existing_stop_file_present")
    pages = build_page_sequence()
    # Keep cumulative latest stable before every run.
    v4.bootstrap_out_from_history()
    v1.log("HZ15_JUMP_PAGES_START", target_total=v1.TARGET_TOTAL, pages=pages, item_sleep=[v1.ITEM_SLEEP_MIN, v1.ITEM_SLEEP_MAX], page_sleep=[v1.PAGE_SLEEP_MIN, v1.PAGE_SLEEP_MAX], run_once=RUN_ONCE)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{base.CDP_PORT}", timeout=15000)
        page = v1.get_active_page(browser)
        page.set_default_timeout(20000)
        while True:
            state = v1.load_state()
            if len(state.get("known_skus") or []) >= v1.TARGET_TOTAL:
                v1.write_report(state, {"sleep_reason": "target_total_reached"})
                v1.log("SLEEP_TARGET_TOTAL", known_sku_count=len(state.get("known_skus") or []), target_total=v1.TARGET_TOTAL)
                if RUN_ONCE:
                    break
                time.sleep(v1.CYCLE_SLEEP)
                continue
            n = run_pages(page, state, pages)
            state = v1.load_state()
            v1.write_report(state, {"cycle_finished": True, "cycle_processed": n, "page_sequence": pages})
            v1.log("CYCLE_DONE", processed=n, known_sku_count=len(state.get("known_skus") or []))
            if RUN_ONCE:
                break
            time.sleep(v1.CYCLE_SLEEP)


if __name__ == "__main__":
    main()
