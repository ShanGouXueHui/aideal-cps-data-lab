#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, sync_playwright

STRONG_RISK = ["risk_handler", "京东验证", "快速验证", "安全验证", "验证码", "滑块"]
EXCLUDED_LABELS = {
    "一键领链",
    "搜索",
    "查询",
    "重置",
    "筛选",
    "展开",
    "收起",
    "上一页",
    "下一页",
    "前往页",
}


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


def discover_tab_groups(page) -> list[dict[str, Any]]:
    return page.evaluate(
        """
        () => {
          const normalize = value => String(value || '').replace(/\s+/g, ' ').trim();
          const visible = element => {
            if (!(element instanceof Element)) return false;
            const style = getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' &&
              Number(style.opacity || 1) !== 0 && rect.width > 2 && rect.height > 2;
          };
          const excluded = new Set([
            '一键领链','搜索','查询','重置','筛选','展开','收起','上一页','下一页','前往页'
          ]);
          const allNodes = Array.from(document.querySelectorAll('body *'))
            .filter(node => visible(node) && normalize(node.textContent) === '全部商品');
          const groups = [];
          for (const anchor of allNodes) {
            const anchorRect = anchor.getBoundingClientRect();
            let container = anchor;
            for (let depth = 0; depth < 7 && container; depth += 1, container = container.parentElement) {
              const selector = [
                '[role="tab"]','[role="menuitem"]','a','button','li',
                '[tabindex]','[class*="tab"]','[class*="Tab"]',
                '[class*="menu"]','[class*="Menu"]','[class*="nav"]','[class*="Nav"]',
                '[class*="item"]','[class*="Item"]'
              ].join(',');
              const candidates = Array.from(container.querySelectorAll(selector));
              const rows = [];
              for (const node of candidates) {
                if (!visible(node)) continue;
                const text = normalize(node.textContent);
                if (!text || text.length > 24 || excluded.has(text)) continue;
                if (/^共\s*\d+\s*条/.test(text) || /^\d+$/.test(text)) continue;
                if (text.includes('一键领链')) continue;
                const rect = node.getBoundingClientRect();
                if (Math.abs(rect.top - anchorRect.top) > 45) continue;
                const style = getComputedStyle(node);
                const className = typeof node.className === 'string' ? node.className : '';
                const clickable = node.matches('a,button,[role="tab"],[role="menuitem"],[tabindex]') ||
                  style.cursor === 'pointer' || /tab|menu|nav|item/i.test(className);
                if (!clickable) continue;
                rows.push({
                  text,
                  tag: node.tagName.toLowerCase(),
                  class_name: className.slice(0, 240),
                  role: node.getAttribute('role'),
                  top: Math.round(rect.top),
                  left: Math.round(rect.left),
                  width: Math.round(rect.width),
                  height: Math.round(rect.height),
                  cursor: style.cursor,
                });
              }
              const unique = [];
              const seen = new Set();
              for (const row of rows.sort((a,b) => a.left - b.left)) {
                if (!seen.has(row.text)) {
                  seen.add(row.text);
                  unique.push(row);
                }
              }
              if (!seen.has('全部商品') || unique.length < 2 || unique.length > 15) continue;
              const className = typeof container.className === 'string' ? container.className : '';
              let score = unique.length * 10 - depth * 2;
              if (/tab|menu|nav|category|type/i.test(className)) score += 20;
              if (container.getAttribute('role') === 'tablist') score += 30;
              const signature = unique.map(row => row.text).join('|');
              groups.push({
                depth,
                score,
                signature,
                container_tag: container.tagName.toLowerCase(),
                container_class: className.slice(0, 300),
                container_role: container.getAttribute('role'),
                anchor_top: Math.round(anchorRect.top),
                items: unique,
              });
            }
          }
          const dedup = new Map();
          for (const group of groups) {
            const old = dedup.get(group.signature);
            if (!old || group.score > old.score) dedup.set(group.signature, group);
          }
          return Array.from(dedup.values()).sort((a,b) => b.score - a.score);
        }
        """
    )


def tab_texts(page) -> tuple[list[str], list[dict[str, Any]]]:
    groups = discover_tab_groups(page)
    if groups:
        names = [str(item.get("text") or "") for item in groups[0].get("items") or []]
        names = [name for name in names if name and name not in EXCLUDED_LABELS]
        if "全部商品" in names and len(names) >= 2:
            return names, groups

    standard = page.locator("[role='tab'], .el-tabs__item")
    texts: list[str] = []
    for index in visible(standard):
        try:
            text = " ".join(standard.nth(index).inner_text(timeout=2000).split())
        except Exception:
            continue
        if text and len(text) <= 40 and text not in texts:
            texts.append(text)
    if "全部商品" not in texts:
        all_product = page.get_by_text("全部商品", exact=True)
        if visible(all_product):
            texts.insert(0, "全部商品")
    return texts, groups


def best_visible_text_target(page, text: str) -> Locator | None:
    locator = page.get_by_text(text, exact=True)
    indices = visible(locator)
    if not indices:
        return None
    scored: list[tuple[int, int]] = []
    for index in indices:
        item = locator.nth(index)
        try:
            score = item.evaluate(
                """
                node => {
                  const style = getComputedStyle(node);
                  const cls = typeof node.className === 'string' ? node.className : '';
                  let score = 0;
                  if (node.matches('a,button,[role="tab"],[role="menuitem"],[tabindex]')) score += 20;
                  if (style.cursor === 'pointer') score += 10;
                  if (/tab|menu|nav|item/i.test(cls)) score += 10;
                  const rect = node.getBoundingClientRect();
                  if (rect.top > 0 && rect.top < innerHeight) score += 5;
                  return score;
                }
                """
            )
        except Exception:
            score = 0
        scored.append((int(score), index))
    scored.sort(reverse=True)
    return locator.nth(scored[0][1])


def click_tab(page, text: str) -> dict[str, Any]:
    target = best_visible_text_target(page, text)
    if target is None:
        return {"ok": False, "reason": "tab_not_found"}
    try:
        target.scroll_into_view_if_needed(timeout=5000)
        target.click(timeout=8000)
    except Exception as exc:
        return {"ok": False, "reason": f"tab_click_failed:{type(exc).__name__}"}
    page.wait_for_timeout(5000)
    snap = snapshot(page)
    return {"ok": not bool(snap.get("risk")), "snapshot": snap}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only first-page overlap audit for JD promotion tabs.")
    parser.add_argument("--output", type=Path, default=Path("reports/hz24_product_tab_audit_latest.json"))
    parser.add_argument("--cdp", default="http://127.0.0.1:19228")
    args = parser.parse_args()

    result: dict[str, Any] = {
        "schema_version": "aideal-hz24-product-tab-audit/v2",
        "generated_at": now(),
        "mode": "read_only_first_page",
        "promotion_links_generated": False,
        "tabs": [],
        "candidate_tab_groups": [],
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
                names, groups = tab_texts(page)
                result["candidate_tab_groups"] = groups[:10]
                result["detected_tab_names"] = names
                if len(names) < 2:
                    result["error"] = "multiple_tabs_not_detected"
                else:
                    ordered_names = ["全部商品"] + [name for name in names if name != "全部商品"]
                    all_skus: set[str] = set()
                    tab_rows: list[dict[str, Any]] = []
                    for name in ordered_names:
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
