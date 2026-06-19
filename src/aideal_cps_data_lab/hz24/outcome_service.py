from __future__ import annotations

from typing import Any

from .batch import BatchState
from .jd_page import JDPageAdapter
from .link_service import collect_link
from .records import save_unavailable, unavailable_reason
from .settings import HZ24Settings


def resolve_outcome(
    settings: HZ24Settings,
    adapter: JDPageAdapter,
    page,
    card: dict[str, Any],
    queue_row: dict[str, Any],
    tab: str,
) -> tuple[str, dict[str, Any]]:
    reason = unavailable_reason(card)
    if reason:
        save_unavailable(settings, card, queue_row, tab, reason)
        return "unavailable", {
            "ok": False,
            "terminal": True,
            "reason": reason,
            "sku": str(card.get("sku") or ""),
        }
    result = collect_link(settings, adapter, page, card, queue_row, tab)
    if result.get("ok"):
        return "linked", result
    terminal = unavailable_reason(card, result)
    if terminal:
        save_unavailable(settings, card, queue_row, tab, terminal)
        return "unavailable", {
            "ok": False,
            "terminal": True,
            "reason": terminal,
            "sku": str(card.get("sku") or ""),
        }
    return "failed", result


def register_outcome(
    outcome: str,
    sku: str,
    linked: set[str],
    unavailable: set[str],
    pending: set[str],
    batch: BatchState,
    result: dict[str, Any],
    tab: str,
    failure_fuse: int,
) -> None:
    if outcome == "linked":
        linked.add(sku)
        pending.discard(sku)
        batch.register_success()
        return
    if outcome == "unavailable":
        unavailable.add(sku)
        pending.discard(sku)
        batch.register_unavailable()
        return
    batch.register_failure({"tab": tab, **result}, failure_fuse)
