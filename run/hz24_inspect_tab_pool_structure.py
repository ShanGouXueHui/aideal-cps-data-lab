#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

TABS = ["超补爆品", "限量高佣", "秒杀专区", "定向高佣", "粉丝爱买", "全部商品"]
STRONG_RISK = ["risk_handler", "京东验证", "快速验证", "安全验证", "验证码", "滑块"]


def snapshot(page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const norm = v => String(v || '').replace(/\s+/g, ' ').trim();
          const visible = el => {
            if (!(el instanceof Element)) return false;
            const s = getComputedStyle(el), r = el.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 2 && r.height > 2;
          };
          const body = document.body ? (document.body.innerText || '') : '';
          const skus = [];
          for (const a of Array.from(document.querySelectorAll('a[href]'))) {
            const m = String(a.href || '').match(/\/(\d{5,})\.html/);
            if (m && !skus.includes(m[1])) skus.push(m[1]);
          }
          const activeTabs = Array.from(document.querySelectorAll('.el-radio-button.is-active, [role="radio"][aria-checked="true"], [role="tab"][aria-selected="true"]'))
            .filter(visible).map(el => norm(el.textContent)).filter(Boolean);
          const paginations = Array.from(document.querySelectorAll('.el-pagination')).filter(visible).map(root => {
            const next = root.querySelector('.btn-next');
            const prev = root.querySelector('.btn-prev');
            const numbers = Array.from(root.querySelectorAll('.el-pager .number')).filter(visible).map(el => ({
              text: norm(el.textContent), active: el.classList.contains('active')
            }));
            const disabled = el => !el || el.hasAttribute('disabled') || el.classList.contains('disabled') || el.getAttribute('aria-disabled') === 'true';
            return {
              text: norm(root.textContent),
              page_numbers: numbers,
              active_page: (numbers.find(x => x.active) || {}).text || null,
              previous_disabled: disabled(prev),
              next_disabled: disabled(next),
              next_present: Boolean(next),
              previous_present: Boolean(prev),
            };
          });
          return {
            url: location.href,
            title: document.title,
            body_text: body,
            active_tabs: activeTabs,
            sku_count: skus.length,
            skus,
            one_key_count: (body.match(/一键领链/g) || []).length,
            paginations,
            document_height: Math.max(
              document.body ? document.body.scrollHeight : 0,
              document.documentElement ? document.documentElement.scrollHeight : 0
            ),
            viewport_height: innerHeight,
            scroll_y: scrollY,
          };
        }
        """
    )


def risk(snapshot_value: dict[str, Any]) -> list[str]:
    text = "\n".join(
        [
            str(snapshot_value.get("url") or ""),
            str(snapshot_value.get("title") or ""),
            str(snapshot_value.get("body_text") or ""),
        ]
    )
    return [marker for marker in STRONG_RISK if marker in text]


def click_tab(page, name: str) -> bool:
    locator = page.get_by_text(name, exact=True)
    candidates = []
    for index in range(locator.count()):
        item = locator.nth(index)
        try:
            if not item.is_visible():
                continue
            score = item.evaluate(
                """
                el => {
                  const cls = typeof el.className === 'string' ? el.className : '';
                  let score = 0;
                  if (el.matches('[role="radio"], label.el-radio-button, [role="tab"]')) score += 30;
                  if (/radio|tab/i.test(cls)) score += 20;
                  const r = el.getBoundingClientRect();
                  if (r.top > 0 && r.top < innerHeight) score += 5;
                  return score;
                }
                """
            )
            candidates.append((int(score), index))
        except Exception:
            continue
    if not candidates:
        return False
    candidates.sort(reverse=True)
    target = locator.nth(candidates[0][1])
    target.scroll_into_view_if_needed(timeout=5000)
    target.click(timeout=8000)
    page.wait_for_timeout(4500)
    return True


def settle_scroll(page) -> tuple[dict[str, Any], dict[str, Any]]:
    before = snapshot(page)
    for _ in range(4):
        page.evaluate(
            """
            () => {
              window.scrollTo(0, Math.max(document.body.scrollHeight, document.documentElement.scrollHeight));
              for (const el of Array.from(document.querySelectorAll('body *'))) {
                if (!(el instanceof HTMLElement)) continue;
                const style = getComputedStyle(el);
                if (!['auto', 'scroll'].includes(style.overflowY)) continue;
                if (el.scrollHeight <= el.clientHeight + 20) continue;
                el.scrollTop = el.scrollHeight;
              }
            }
            """
        )
        page.wait_for_timeout(1800)
    after = snapshot(page)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    return before, after


def pagination_single_page(paginations: list[dict[str, Any]]) -> bool:
    if not paginations:
        return False
    for item in paginations:
        numbers = [
            int(value.get("text"))
            for value in item.get("page_numbers") or []
            if str(value.get("text") or "").isdigit()
        ]
        if not bool(item.get("next_disabled")):
            return False
        if numbers and max(numbers) > 1:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp", default="http://127.0.0.1:19228")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/hz24_tab_pool_structure_latest.json"),
    )
    args = parser.parse_args()

    result: dict[str, Any] = {
        "schema_version": "aideal-hz24-tab-pool-structure/v2",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "read_only_scroll_stability",
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
            page = next(
                (item for item in reversed(pages) if "union.jd.com" in (item.url or "")),
                pages[-1],
            )
            page.set_default_timeout(20000)
            page.bring_to_front()
            if "/proManager/index" not in (page.url or ""):
                page.goto(
                    "https://union.jd.com/proManager/index?pageNo=1",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
                page.wait_for_timeout(6000)

            for name in TABS:
                if not click_tab(page, name):
                    result["tabs"].append(
                        {"tab_name": name, "ok": False, "reason": "tab_not_found"}
                    )
                    continue

                before, after = settle_scroll(page)
                found_risk = risk(after)
                before.pop("body_text", None)
                after.pop("body_text", None)

                before_skus = set(before.get("skus") or [])
                after_skus = set(after.get("skus") or [])
                scroll_stable = bool(
                    before_skus
                    and before_skus == after_skus
                    and int(before.get("sku_count") or 0) == int(after.get("sku_count") or 0)
                    and int(before.get("one_key_count") or 0) == int(after.get("one_key_count") or 0)
                    and int(before.get("document_height") or 0) == int(after.get("document_height") or 0)
                )
                active_tab_matches = name in (after.get("active_tabs") or [])
                no_pagination_single_page = bool(
                    name != "全部商品"
                    and active_tab_matches
                    and scroll_stable
                    and not (after.get("paginations") or [])
                    and int(after.get("sku_count") or 0) > 0
                    and int(after.get("one_key_count") or 0) == int(after.get("sku_count") or 0)
                )
                explicit_pagination_single_page = bool(
                    name != "全部商品"
                    and active_tab_matches
                    and scroll_stable
                    and pagination_single_page(after.get("paginations") or [])
                )
                single_page_confirmed = bool(
                    no_pagination_single_page or explicit_pagination_single_page
                )
                confirmation_method = (
                    "no_pagination_scroll_stable"
                    if no_pagination_single_page
                    else "disabled_single_page_pagination"
                    if explicit_pagination_single_page
                    else None
                )

                result["tabs"].append(
                    {
                        "tab_name": name,
                        "ok": not found_risk,
                        "risk": found_risk,
                        "single_page_confirmed": single_page_confirmed,
                        "single_page_confirmation_method": confirmation_method,
                        "active_tab_matches": active_tab_matches,
                        "scroll_stable": scroll_stable,
                        "before_scroll": before,
                        "after_scroll": after,
                        **after,
                    }
                )
                if found_risk:
                    result["risk"] = found_risk
                    break

            try:
                click_tab(page, "全部商品")
            except Exception:
                pass
            result["ok"] = (
                len(result["tabs"]) == len(TABS)
                and not result["risk"]
                and all(row.get("ok") for row in result["tabs"])
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
