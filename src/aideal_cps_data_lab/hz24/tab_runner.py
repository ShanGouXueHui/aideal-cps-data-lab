from __future__ import annotations

import random
import time
from typing import Any

from .batch import BatchState
from .jd_page import JDPageAdapter
from .outcome_service import register_outcome, resolve_outcome
from .settings import HZ24Settings
from .state_store import checkpoint


def run_tab(
    settings: HZ24Settings,
    adapter: JDPageAdapter,
    page,
    tab: str,
    queue: dict[str, dict[str, Any]],
    linked: set[str],
    unavailable: set[str],
    pending: set[str],
    queue_sha: str,
    batch: BatchState,
) -> None:
    targets = {
        sku
        for sku in pending
        if tab in (queue[sku].get("source_tabs") or [])
    }
    if not targets:
        return
    if not adapter.click_tab(page, tab):
        batch.stop_reason = f"tab_not_found:{tab}"
        return
    found_risk = adapter.risk(page)
    if found_risk:
        batch.stop_reason = "risk_after_tab"
        batch.stop_risk = found_risk
        return
    cards = adapter.collect_cards(page)
    for card in cards:
        sku = str(card.get("sku") or "")
        if sku not in targets:
            continue
        if batch.processed >= settings.collection.batch_limit:
            break
        outcome, result = resolve_outcome(
            settings,
            adapter,
            page,
            card,
            queue[sku],
            tab,
        )
        register_outcome(
            outcome,
            sku,
            linked,
            unavailable,
            pending,
            batch,
            result,
            tab,
            settings.collection.failure_fuse,
        )
        checkpoint(
            settings,
            len(queue),
            queue_sha,
            len(linked),
            len(unavailable),
            len(pending),
            tab,
            sku,
            batch.stop_reason,
        )
        if batch.stop_reason:
            break
        time.sleep(
            random.uniform(
                settings.collection.item_sleep_min_seconds,
                settings.collection.item_sleep_max_seconds,
            )
        )
