#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from playwright.sync_api import sync_playwright

TARGET_PAGE = int(sys.argv[1])
OUT = Path(sys.argv[2])
STRONG_RISK = ["risk_handler", "京东验证", "快速验证", "安全验证", "验证码", "滑块"]


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def snap(page) -> Dict[str, Any]:
    info = page.evaluate(
        """
        () => {
          const txt = document.body ? (document.body.innerText || '') : '';
          const skus = [];
          for (const a of Array.from(document.querySelectorAll('a[href]'))) {
            const m = (a.href || '').match(/\/(\d{5,})\.html/);
            if (m && !skus.includes(m[1])) skus.push(m[1]);
          }
          const pagers = Array.from(document.querySelectorAll('.el-pagination')).map((p, i) => {
            const active = Array.from(p.querySelectorAll('.el-pager li')).find(el => String(el.className || '').includes('active'));
            const input = p.querySelector('.el-pagination__jump input, input.el-input__inner');
            return {
              i,
              text: (p.innerText || p.textContent || '').replace(/\s+/g, ' ').trim(),
              active: active ? (active.innerText || active.textContent || '').replace(/\s+/g, '').trim() : null,
              input: input ? (input.value || '') : null
            };
          });
          const pager = pagers.find(p => p.text.includes('4000')) || pagers[0] || {};
          return {
            url: location.href,
            title: document.title,
            text: txt,
            has4000: txt.includes('共 4000 条') || txt.includes('共4000条'),
            oneKeyCount: (txt.match(/一键领链/g) || []).length,
            skuCount: skus.length,
            pagerText: pager.text || '',
            activePageText: pager.active || null,
            jumpInputValue: pager.input || null,
            skus: skus.slice(0, 12),
            pagers
          };
        }
        """
    )
    hay = "\n".join([str(info.get("url") or ""), str(info.get("title") or ""), str(info.pop("text", ""))])
    info["risk"] = [x for x in STRONG_RISK if x in hay]
    return info


def all_product_ready(info: Dict[str, Any]) -> bool:
    return bool(
        not info.get("risk")
        and info.get("has4000")
        and int(info.get("oneKeyCount") or 0) >= 55
        and int(info.get("skuCount") or 0) >= 55
        and "4000" in str(info.get("pagerText") or "")
    )


def click_all_product(page) -> Dict[str, Any]:
    loc = page.get_by_text("全部商品", exact=True)
    count = loc.count()
    visible = []
    for i in range(count):
        try:
            if loc.nth(i).is_visible():
                visible.append(i)
        except Exception:
            pass
    if not visible:
        return {"ok": False, "reason": "all_product_tab_not_found", "count": count}
    idx = visible[-1]
    target = loc.nth(idx)
    target.scroll_into_view_if_needed(timeout=5000)
    target.click(timeout=8000)
    return {"ok": True, "method": "playwright_exact_text_click", "count": count, "index": idx}


def jump_4000_pager(page, target_page: int) -> Dict[str, Any]:
    pagers = page.locator(".el-pagination")
    count = pagers.count()
    chosen = None
    for i in range(count):
        p = pagers.nth(i)
        try:
            if "4000" in (p.inner_text(timeout=2000) or ""):
                chosen = p
                break
        except Exception:
            pass
    if chosen is None:
        return {"ok": False, "reason": "no_4000_pager", "pager_count": count}
    chosen.scroll_into_view_if_needed(timeout=5000)
    inp = chosen.locator(".el-pagination__jump input, input.el-input__inner").first
    inp.click(timeout=5000)
    inp.fill(str(target_page), timeout=5000)
    inp.press("Enter", timeout=5000)
    return {"ok": True, "method": "4000_pager_locator_fill_enter"}


def wait_until(page, predicate, seconds: int):
    last = None
    for _ in range(seconds):
        time.sleep(1)
        last = snap(page)
        if last.get("risk") or predicate(last):
            return last
    return last or snap(page)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rep: Dict[str, Any] = {"ts": now(), "target_page": TARGET_PAGE, "ok": False}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:19228", timeout=15000)
        pages = [pg for ctx in browser.contexts for pg in ctx.pages]
        page = next((pg for pg in reversed(pages) if "union.jd.com" in (pg.url or "")), pages[-1])
        page.set_default_timeout(20000)
        page.bring_to_front()
        before = snap(page)
        rep["before"] = before
        if before.get("risk"):
            rep["reason"] = "risk_before"
        else:
            if "/proManager/index" not in (page.url or ""):
                page.goto("https://union.jd.com/proManager/index?pageNo=1", wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(6000)
            current = snap(page)
            if not all_product_ready(current):
                rep["click_all_product"] = click_all_product(page)
                current = wait_until(page, all_product_ready, 30)
            rep["after_all_product"] = current
            if current.get("risk"):
                rep["reason"] = "risk_after_all_product"
            elif not all_product_ready(current):
                rep["reason"] = "all_product_4000_not_ready"
            elif str(current.get("activePageText") or "") == str(TARGET_PAGE):
                rep["ok"] = True
                rep["reason"] = "safe_all_product_4000_page"
                rep["after"] = current
            else:
                rep["jump_action"] = jump_4000_pager(page, TARGET_PAGE)
                after = wait_until(
                    page,
                    lambda x: all_product_ready(x) and str(x.get("activePageText") or "") == str(TARGET_PAGE),
                    45,
                )
                rep["after"] = after
                if after.get("risk"):
                    rep["reason"] = "risk_after_jump"
                elif all_product_ready(after) and str(after.get("activePageText") or "") == str(TARGET_PAGE):
                    rep["ok"] = True
                    rep["reason"] = "safe_all_product_4000_page"
                else:
                    rep["reason"] = "jump_not_safe_page"
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"event": "HZ22_PREP_DONE", "page": TARGET_PAGE, "ok": rep.get("ok"), "reason": rep.get("reason"), "after": rep.get("after")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
