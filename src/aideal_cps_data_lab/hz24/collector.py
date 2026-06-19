from __future__ import annotations

import hashlib
import json
import random
import time
from typing import Any

from playwright.sync_api import sync_playwright

from .batch import BatchState
from .jd_page import JDPageAdapter
from .link_service import collect_link
from .records import save_unavailable, timestamp, unavailable_reason
from .repository import (
    atomic_json,
    load_json,
    read_jsonl,
    successful_skus,
    unavailable_skus,
)
from .settings import HZ24Settings, load_settings


def _log(event: str, **data: Any) -> None:
    print(
        json.dumps(
            {
                "ts": timestamp(),
                "worker": "hz24_increment",
                "event": event,
                **data,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )


def _load_queue(settings: HZ24Settings) -> tuple[dict[str, dict[str, Any]], str]:
    manifest = load_json(settings.contracts.queue_manifest_file)
    raw = settings.contracts.queue_file.read_bytes()
    rows = read_jsonl(settings.contracts.queue_file)
    digest = hashlib.sha256(raw).hexdigest()
    expected = str(manifest.get("data_sha256") or "")
    if not rows or digest != expected:
        raise ValueError("queue_integrity_failed")
    indexed = {
        str(row.get("sku") or ""): row
        for row in rows
        if str(row.get("sku") or "")
    }
    return indexed, digest


def _checkpoint(
    settings: HZ24Settings,
    queue_count: int,
    queue_sha: str,
    linked_count: int,
    unavailable_count: int,
    pending_count: int,
    tab: str | None,
    sku: str | None,
    stop_reason: str | None,
    complete: bool = False,
) -> None:
    state = load_json(settings.contracts.state_file)
    state.update(
        {
            "schema_version": settings.contracts.state_schema,
            "queue_sha256": queue_sha,
            "queue_count": queue_count,
            "started_at": state.get("started_at") or timestamp(),
            "updated_at": timestamp(),
            "last_tab": tab,
            "last_sku": sku,
            "linked_count": linked_count,
            "unavailable_count": unavailable_count,
            "pending_count": pending_count,
            "complete": complete,
            "stop_reason": stop_reason,
        }
    )
    atomic_json(settings.contracts.state_file, state)


def _process_card(
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


def _update_sets(
    outcome: str,
    sku: str,
    linked: set[str],
    unavailable: set[str],
    pending: set[str],
    batch: BatchState,
    result: dict[str, Any],
    tab: str,
    fuse: int,
) -> None:
    if outcome == "linked":
        linked.add(sku)
        pending.discard(sku)
        batch.register_success()
    elif outcome == "unavailable":
        unavailable.add(sku)
        pending.discard(sku)
        batch.register_unavailable()
    else:
        batch.register_failure({"tab": tab, **result}, fuse)


def _process_tab(
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
    ordered = [
        card
        for card in cards
        if str(card.get("sku") or "") in targets
    ]
    _log(
        "TAB_READY",
        tab=tab,
        target_count=len(targets),
        card_count=len(cards),
        matched_count=len(ordered),
    )

    for card in ordered:
        if batch.processed >= settings.collection.batch_limit or batch.stop_reason:
            break
        sku = str(card.get("sku") or "")
        outcome, result = _process_card(
            settings,
            adapter,
            page,
            card,
            queue[sku],
            tab,
        )
        _update_sets(
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
        _checkpoint(
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
        _log(
            "ITEM_RESULT",
            tab=tab,
            sku=sku,
            outcome=outcome,
            reason=result.get("reason"),
            pending_count=len(pending),
        )
        if batch.stop_reason:
            break
        time.sleep(
            random.uniform(
                settings.collection.item_sleep_min_seconds,
                settings.collection.item_sleep_max_seconds,
            )
        )


def _build_report(
    settings: HZ24Settings,
    queue: dict[str, dict[str, Any]],
    linked: set[str],
    unavailable: set[str],
    pending: set[str],
    batch: BatchState,
) -> dict[str, Any]:
    return {
        "schema_version": settings.contracts.collection_schema,
        "generated_at": timestamp(),
        "ok": batch.stop_reason is None,
        "complete": not pending,
        "queue_count": len(queue),
        "success_count": len(linked & set(queue)),
        "unavailable_count": len(unavailable & set(queue)),
        "accounted_count": len((linked | unavailable) & set(queue)),
        "pending_count": len(pending),
        "pending_samples": sorted(pending)[:30],
        "batch_processed": batch.processed,
        "batch_success": batch.linked,
        "batch_unavailable": batch.unavailable,
        "batch_fail": batch.failed,
        "failures": batch.failures[-30:],
        "stop_reason": batch.stop_reason,
        "risk": batch.stop_risk,
        "output_file": str(settings.contracts.linked_file),
        "unavailable_file": str(settings.contracts.unavailable_file),
    }


def run_collection(settings: HZ24Settings | None = None) -> int:
    settings = settings or load_settings()
    try:
        queue, queue_sha = _load_queue(settings)
    except Exception as exc:
        report = {
            "ok": False,
            "reason": "queue_integrity_failed",
            "error": repr(exc),
        }
        atomic_json(settings.contracts.collection_report_file, report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 2

    linked = successful_skus(settings.contracts.linked_file)
    unavailable = unavailable_skus(settings.contracts.unavailable_file)
    pending = set(queue) - linked - unavailable
    batch = BatchState()
    _checkpoint(
        settings,
        len(queue),
        queue_sha,
        len(linked),
        len(unavailable),
        len(pending),
        None,
        None,
        None,
    )

    adapter = JDPageAdapter(settings)
    with sync_playwright() as playwright:
        page = adapter.connect_page(playwright)
        if page is None:
            batch.stop_reason = "browser_page_missing"
        else:
            initial_risk = adapter.risk(page)
            if initial_risk:
                batch.stop_reason = "risk_initial"
                batch.stop_risk = initial_risk
            else:
                for index, tab in enumerate(settings.special_tabs):
                    if (
                        batch.processed >= settings.collection.batch_limit
                        or not pending
                        or batch.stop_reason
                    ):
                        break
                    _process_tab(
                        settings,
                        adapter,
                        page,
                        tab,
                        queue,
                        linked,
                        unavailable,
                        pending,
                        queue_sha,
                        batch,
                    )
                    if (
                        index < len(settings.special_tabs) - 1
                        and pending
                        and batch.processed < settings.collection.batch_limit
                        and not batch.stop_reason
                    ):
                        time.sleep(
                            random.uniform(
                                settings.collection.tab_sleep_min_seconds,
                                settings.collection.tab_sleep_max_seconds,
                            )
                        )

    linked = successful_skus(settings.contracts.linked_file)
    unavailable = unavailable_skus(settings.contracts.unavailable_file)
    pending = set(queue) - linked - unavailable
    report = _build_report(
        settings,
        queue,
        linked,
        unavailable,
        pending,
        batch,
    )
    _checkpoint(
        settings,
        len(queue),
        queue_sha,
        len(linked),
        len(unavailable),
        len(pending),
        None,
        None,
        batch.stop_reason,
        complete=not pending,
    )
    atomic_json(settings.contracts.collection_report_file, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if batch.stop_reason and batch.stop_reason.startswith("risk_"):
        return 88
    return 1 if batch.stop_reason else 0
