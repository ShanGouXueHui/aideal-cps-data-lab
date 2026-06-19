from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from playwright.sync_api import sync_playwright

from aideal_cps_data_lab.hz24.jd_page import JDPageAdapter
from aideal_cps_data_lab.hz24.repository import atomic_json
from aideal_cps_data_lab.hz24.settings import HZ24Settings, load_settings

SNAPSHOT_SCRIPT = """
() => {
  const text = document.body ? (document.body.innerText || '') : '';
  const skus = [];
  for (const anchor of Array.from(document.querySelectorAll('a[href]'))) {
    const match = String(anchor.href || '').match(/\/(\d{5,})\.html/);
    if (match && !skus.includes(match[1])) skus.push(match[1]);
  }
  const pagers = Array.from(document.querySelectorAll('.el-pagination')).map((pager, index) => {
    const active = Array.from(pager.querySelectorAll('.el-pager li')).find(
      element => String(element.className || '').includes('active')
    );
    const input = pager.querySelector('.el-pagination__jump input, input.el-input__inner');
    return {
      index,
      text: (pager.innerText || pager.textContent || '').replace(/\s+/g, ' ').trim(),
      active: active ? (active.innerText || active.textContent || '').replace(/\s+/g, '').trim() : null,
      input: input ? (input.value || '') : null
    };
  });
  const pager = pagers.find(item => item.text.includes('4000')) || pagers[0] || {};
  return {
    url: location.href,
    title: document.title,
    has4000: text.includes('共 4000 条') || text.includes('共4000条'),
    oneKeyCount: (text.match(/一键领链/g) || []).length,
    skuCount: skus.length,
    pagerText: pager.text || '',
    activePageText: pager.active || null,
    jumpInputValue: pager.input || null,
    skus: skus.slice(0, 12),
    pagers
  };
}
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def snapshot(page, adapter: JDPageAdapter) -> dict[str, Any]:
    info = dict(page.evaluate(SNAPSHOT_SCRIPT))
    info["risk"] = adapter.risk(page)
    return info


def all_product_ready(info: dict[str, Any]) -> bool:
    return bool(
        not info.get("risk")
        and info.get("has4000")
        and int(info.get("oneKeyCount") or 0) >= 55
        and int(info.get("skuCount") or 0) >= 55
        and "4000" in str(info.get("pagerText") or "")
    )


def click_all_product(page) -> dict[str, Any]:
    locator = page.get_by_text("全部商品", exact=True)
    visible: list[int] = []
    for index in range(locator.count()):
        try:
            if locator.nth(index).is_visible():
                visible.append(index)
        except Exception:
            continue
    if not visible:
        return {
            "ok": False,
            "reason": "all_product_tab_not_found",
            "count": locator.count(),
        }
    index = visible[-1]
    target = locator.nth(index)
    target.scroll_into_view_if_needed(timeout=5000)
    target.click(timeout=8000)
    return {
        "ok": True,
        "method": "playwright_exact_text_click",
        "count": locator.count(),
        "index": index,
    }


def jump_page(page, target_page: int) -> dict[str, Any]:
    pagers = page.locator(".el-pagination")
    chosen = None
    for index in range(pagers.count()):
        pager = pagers.nth(index)
        try:
            if "4000" in (pager.inner_text(timeout=2000) or ""):
                chosen = pager
                break
        except Exception:
            continue
    if chosen is None:
        return {"ok": False, "reason": "no_4000_pager", "pager_count": pagers.count()}
    chosen.scroll_into_view_if_needed(timeout=5000)
    field = chosen.locator(
        ".el-pagination__jump input, input.el-input__inner"
    ).first
    field.click(timeout=5000)
    field.fill(str(target_page), timeout=5000)
    field.press("Enter", timeout=5000)
    return {"ok": True, "method": "4000_pager_locator_fill_enter"}


def wait_until(
    page,
    adapter: JDPageAdapter,
    predicate: Callable[[dict[str, Any]], bool],
    seconds: int,
) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(seconds):
        time.sleep(1)
        last = snapshot(page, adapter)
        if last.get("risk") or predicate(last):
            return last
    return last or snapshot(page, adapter)


def product_page_url(settings: HZ24Settings) -> str:
    browser = settings.browser
    return f"{browser.page_scheme}://{browser.page_host}/proManager/index?pageNo=1"


def prepare_page(
    target_page: int,
    settings: HZ24Settings | None = None,
) -> dict[str, Any]:
    settings = settings or load_settings()
    report: dict[str, Any] = {"ts": now(), "target_page": target_page, "ok": False}
    adapter = JDPageAdapter(settings)
    with sync_playwright() as playwright:
        page = adapter.connect_page(playwright)
        if page is None:
            report["reason"] = "browser_page_missing"
            return report
        before = snapshot(page, adapter)
        report["before"] = before
        if before.get("risk"):
            report["reason"] = "risk_before"
            return report
        if "/proManager/index" not in str(page.url or ""):
            page.goto(
                product_page_url(settings),
                wait_until="domcontentloaded",
                timeout=45000,
            )
            page.wait_for_timeout(6000)
        current = snapshot(page, adapter)
        if not all_product_ready(current):
            report["click_all_product"] = click_all_product(page)
            current = wait_until(page, adapter, all_product_ready, 30)
        report["after_all_product"] = current
        return complete_jump(page, adapter, target_page, current, report)


def complete_jump(
    page,
    adapter: JDPageAdapter,
    target_page: int,
    current: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    if current.get("risk"):
        report["reason"] = "risk_after_all_product"
    elif not all_product_ready(current):
        report["reason"] = "all_product_4000_not_ready"
    elif str(current.get("activePageText") or "") == str(target_page):
        report.update(ok=True, reason="safe_all_product_4000_page", after=current)
    else:
        report["jump_action"] = jump_page(page, target_page)
        after = wait_until(
            page,
            adapter,
            lambda value: all_product_ready(value)
            and str(value.get("activePageText") or "") == str(target_page),
            45,
        )
        report["after"] = after
        if after.get("risk"):
            report["reason"] = "risk_after_jump"
        elif all_product_ready(after) and str(after.get("activePageText") or "") == str(target_page):
            report.update(ok=True, reason="safe_all_product_4000_page")
        else:
            report["reason"] = "jump_not_safe_page"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target_page", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = prepare_page(args.target_page)
    atomic_json(args.output, report)
    print(
        json.dumps(
            {
                "event": "HZ22_PREP_DONE",
                "page": args.target_page,
                "ok": report.get("ok"),
                "reason": report.get("reason"),
                "after": report.get("after"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report.get("ok") else 1
