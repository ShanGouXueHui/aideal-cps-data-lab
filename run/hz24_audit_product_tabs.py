#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, sync_playwright

STRONG_RISK = ["risk_handler", "京东验证", "快速验证", "安全验证", "验证码", "滑块"]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def visible(locator: Locator) -> list[int]:
    result: list[int] = []
    for index in range(locator.count()):
        try:
            if locator.nth(index).is_visible():
                result.append(index)
        except Exception:
            pass
    return result


def snapshot(page) -> dict[str, Any]:
    data = page.evaluate(
        """
        () => {
          const text = document.body ? (document.body.innerText || '') : '';
          const skus = [];
          for (const a of Array.from(document.querySelectorAll('a[href]'))) {
            const m = String(a.href || '').match(/\/(\d{5,})\.html/);
            if (m && !skus.includes(m[1])) skus.push(m[1]);
          }
          const pagerTexts = Array.from(document.querySelectorAll('.el-pagination'))
            .map(x => (x.innerText || x.textContent || '').replace(/\s+/g, ' ').trim())
            .filter(Boolean);
          const totals = Array.from(text.matchAll(/共\s*(\d+)\s*条/g)).map(m => Number(m[1]));
          return {
            url: location.href,
            title: document.title,
            body_text: text,
            skus,
            one_key_count: (text.match(/一键领链/g) || []).length,
            pager_texts: pagerTexts,
            totals
          };
        }
        """
    )
    haystack = "\n".join(
        [str(data.get("url") or ""), str(data.get("title") or ""), str(data.pop("body_text", ""))]
    )
    data["risk"] = [marker for marker in STRONG_RISK if marker in haystack]
    return data


def tab_texts(page) -> list[str]:
    all_product = page.get_by_text("全部商品", exact=True)
    visible_all = visible(all_product)
    if not visible_all:
        return []
    target = all_product.nth(visible_all[-1])
    candidates: Locator | None = None
    try:
        container = target.locator("xpath=ancestor::*[contains(@class,'el-tabs')][1]")
        if container.count():
            candidates = container.locator("[role='tab'], .el-tabs__item")
    except Exception:
        candidates = None
    if candidates is None or candidates.count() == 0:
        candidates = page.locator("[role='tab'], .el-tabs__item")

    texts: list[str] = []
    for index in visible(candidates):
        try:
            text = " ".join(candidates.nth(index).inner_text(timeout=2000).split())
        except Exception:
            continue
        if text and len(text) <= 40 and text not in texts:
            texts.append(text)
    if "全部商品" not in texts:
        texts.insert(0, "全部商品")
    return texts


def click_tab(page, text: str) -> dict[str, Any]:
    locator = page.get_by_text(text, exact=True)
    indices = visible(locator)
    if not indices:
        return {"ok": False, "reason": "tab_not_found"}
    target = locator.nth(indices[-1])
    target.scroll_into_view_if_needed(timeout=5000)
    target.click(timeout=8000)
    page.wait_for_timeout(5000)
    snap = snapshot(page)
    return {"ok": not bool(snap.get("risk")), "snapshot": snap}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only first-page overlap audit for JD promotion tabs.")
    parser.add_argument("--output", type=Path, default=Path("reports/hz24_product_tab_audit_latest.json"))
    parser.add_argument("--cdp", default="http://127.0.0.1:19228")
    args = parser.parse_args()

    result: dict[str, Any] = {
        "schema_version": "aideal-hz24-product-tab-audit/v1",
        "generated_at": now(),
        "mode": "read_only_first_page",
        "promotion_links_generated": False,
        "tabs": [],
        "risk": [],
        "ok": False,
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(args.cdp, timeout=15000)
        pages = [page for context in browser.contexts for page in context.pages]
        if not pages:
            result["error"] = "browser_page_missing"
        else:
            page = next((item for item in reversed(pages) if "union.jd.com" in (item.url or "")), pages[-1])
            page.set_default_timeout(20000)
            page.bring_to_front()
            if "/proManager/index" not in (page.url or ""):
                page.goto("https://union.jd.com/proManager/index?pageNo=1", wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(6000)

            before = snapshot(page)
            if before.get("risk"):
                result["risk"] = before["risk"]
                result["error"] = "risk_before_audit"
            else:
                names = tab_texts(page)
                result["detected_tab_names"] = names
                all_skus: set[str] = set()
                tab_rows: list[dict[str, Any]] = []
                for name in names:
                    clicked = click_tab(page, name)
                    snap = clicked.get("snapshot") or {}
                    row = {
                        "tab_name": name,
                        "ok": clicked.get("ok") is True,
                        "reason": clicked.get("reason"),
                        "url": snap.get("url"),
                        "title": snap.get("title"),
                        "display_total_candidates": snap.get("totals") or [],
                        "pager_texts": snap.get("pager_texts") or [],
                        "first_page_sku_count": len(snap.get("skus") or []),
                        "first_page_skus": snap.get("skus") or [],
                        "one_key_count": snap.get("one_key_count") or 0,
                        "risk": snap.get("risk") or [],
                    }
                    tab_rows.append(row)
                    if name == "全部商品":
                        all_skus = set(row["first_page_skus"])
                    if row["risk"]:
                        result["risk"] = row["risk"]
                        break
                    time.sleep(3)

                for row in tab_rows:
                    skus = set(row["first_page_skus"])
                    intersection = skus & all_skus
                    union = skus | all_skus
                    row["overlap_with_all_count"] = len(intersection)
                    row["unique_vs_all_count"] = len(skus - all_skus)
                    row["jaccard_with_all"] = round(len(intersection) / len(union), 4) if union else None
                result["tabs"] = tab_rows
                result["ok"] = bool(tab_rows) and not result["risk"] and all(row["ok"] for row in tab_rows)

                if "全部商品" in names:
                    try:
                        click_tab(page, "全部商品")
                    except Exception:
                        pass

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
