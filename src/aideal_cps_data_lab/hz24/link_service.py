from __future__ import annotations

from typing import Any

from .jd_page import JDPageAdapter
from .records import build_linked_row
from .repository import upsert_jsonl_by_sku
from .settings import HZ24Settings


def collect_link(
    settings: HZ24Settings,
    page_adapter: JDPageAdapter,
    page,
    card: dict[str, Any],
    queue_row: dict[str, Any],
    tab: str,
) -> dict[str, Any]:
    sku = str(card.get("sku") or "")
    current_risk = page_adapter.risk(page)
    if current_risk:
        return {
            "ok": False,
            "sku": sku,
            "reason": "risk_before",
            "risk": current_risk,
        }

    try:
        page_adapter.close_dialog(page)
        click = page_adapter.click_card(page, card)
        if not click.get("ok"):
            return {
                "ok": False,
                "sku": sku,
                "reason": "click_failed",
                "click": click,
            }

        modal: dict[str, Any] = {}
        for _ in range(settings.collection.wait_seconds):
            page.wait_for_timeout(settings.browser.modal_poll_ms)
            current_risk = page_adapter.risk(page)
            if current_risk:
                return {
                    "ok": False,
                    "sku": sku,
                    "reason": "risk_after_click",
                    "risk": current_risk,
                }
            modal = page_adapter.parse_modal(page)
            if modal.get("short_url"):
                break

        page_adapter.close_dialog(page)
        if not page_adapter.trusted_short_url(modal.get("short_url")):
            return {
                "ok": False,
                "sku": sku,
                "reason": "trusted_short_url_missing",
            }

        row = build_linked_row(
            settings,
            page_adapter,
            card,
            queue_row,
            tab,
            modal,
            click,
        )
        upsert_jsonl_by_sku(settings.contracts.linked_file, row)
        return {
            "ok": True,
            "sku": sku,
            "short_url": row["short_url"],
            "record_sha256": row["record_sha256"],
        }
    except Exception as exc:
        page_adapter.close_dialog(page)
        return {
            "ok": False,
            "sku": sku,
            "reason": "exception",
            "error": repr(exc),
        }
