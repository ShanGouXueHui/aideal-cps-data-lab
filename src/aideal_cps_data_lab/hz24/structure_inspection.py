from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from playwright.sync_api import sync_playwright

from .audit_settings import AuditSettings, load_audit_settings
from .inspection_dom import (
    RESET_SCROLL_SCRIPT,
    SCROLL_TO_END_SCRIPT,
    pagination_is_single_page,
    snapshot,
)
from .jd_page import JDPageAdapter
from .repository import atomic_json
from .settings import HZ24Settings, load_settings


def _scroll(page, audit: AuditSettings):
    before = snapshot(page)
    for _ in range(audit.scroll_iterations):
        page.evaluate(SCROLL_TO_END_SCRIPT)
        page.wait_for_timeout(audit.scroll_settle_ms)
    after = snapshot(page)
    page.evaluate(RESET_SCROLL_SCRIPT)
    page.wait_for_timeout(audit.scroll_reset_settle_ms)
    return before, after


def _stable(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return bool(
        set(before.get("skus") or [])
        and set(before.get("skus") or []) == set(after.get("skus") or [])
        and before.get("sku_count") == after.get("sku_count")
        and before.get("one_key_count") == after.get("one_key_count")
        and before.get("document_height") == after.get("document_height")
    )


def _inspect_tab(settings, audit, adapter, page, tab):
    if not adapter.click_tab(page, tab):
        return {"tab_name": tab, "ok": False, "reason": "tab_not_found"}
    before, after = _scroll(page, audit)
    found_risk = adapter.risk(page)
    stable = _stable(before, after)
    active = tab in (after.get("active_tabs") or [])
    count = int(after.get("sku_count") or 0)
    buttons = int(after.get("one_key_count") or 0)
    no_pagination = bool(
        active
        and stable
        and not (after.get("paginations") or [])
        and count >= audit.minimum_sku_count
        and buttons == count
    )
    explicit = bool(
        active
        and stable
        and pagination_is_single_page(after.get("paginations") or [])
    )
    method = None
    if no_pagination:
        method = "no_pagination_scroll_stable"
    elif explicit:
        method = "disabled_single_page_pagination"
    before.pop("body_text", None)
    after.pop("body_text", None)
    return {
        "tab_name": tab,
        "ok": not found_risk,
        "risk": found_risk,
        "single_page_confirmed": no_pagination or explicit,
        "single_page_confirmation_method": method,
        "active_tab_matches": active,
        "scroll_stable": stable,
        "before_scroll": before,
        "after_scroll": after,
        **after,
    }


def run_structure_inspection(
    settings: HZ24Settings | None = None,
    audit: AuditSettings | None = None,
) -> int:
    settings = settings or load_settings()
    audit = audit or load_audit_settings(settings)
    result = {
        "schema_version": audit.structure_schema,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": audit.mode,
        "promotion_links_generated": False,
        "tabs": [],
        "risk": [],
        "ok": False,
    }
    adapter = JDPageAdapter(settings)
    with sync_playwright() as playwright:
        page = adapter.connect_page(playwright)
        if page is None:
            result["error"] = "browser_page_missing"
        else:
            if audit.product_page_path not in str(page.url or ""):
                page.goto(
                    audit.product_page_url(settings),
                    wait_until=audit.page_wait_until,
                    timeout=audit.page_navigation_timeout_ms,
                )
                page.wait_for_timeout(audit.page_navigation_settle_ms)
            for tab in settings.special_tabs:
                row = _inspect_tab(settings, audit, adapter, page, tab)
                result["tabs"].append(row)
                if row.get("risk"):
                    result["risk"] = list(row["risk"])
                    break
    result["ok"] = bool(
        len(result["tabs"]) == len(settings.special_tabs)
        and not result["risk"]
        and all(row.get("ok") for row in result["tabs"])
        and all(row.get("single_page_confirmed") for row in result["tabs"])
    )
    atomic_json(audit.structure_report, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1
