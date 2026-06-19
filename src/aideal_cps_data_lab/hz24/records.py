from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from .browser_contract import (
    DELISTED_TEXT,
    DISABLED_CARD_CLASS,
    NOT_PROMOTABLE_TEXTS,
    SOLD_OUT_TEXT,
)
from .jd_page import JDPageAdapter
from .repository import upsert_jsonl_by_sku
from .settings import HZ24Settings


LINK_HASH_FIELDS = (
    "sku",
    "title",
    "item_url",
    "image_url",
    "price",
    "commission_rate",
    "estimated_income",
    "short_url",
    "long_url",
    "source_tab",
    "source_tabs",
)


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def stable_hash(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    payload = {field: row.get(field) for field in fields}
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def unavailable_reason(
    card: dict[str, Any],
    result: dict[str, Any] | None = None,
) -> str | None:
    raw = str(card.get("raw_text") or "")
    if SOLD_OUT_TEXT in raw:
        return "sold_out"
    if DELISTED_TEXT in raw:
        return "delisted"
    if any(text in raw for text in NOT_PROMOTABLE_TEXTS):
        return "not_promotable"
    if result:
        click = result.get("click") or {}
        hit = click.get("hit") or {}
        matched = ((click.get("mark") or {}).get("matched") or {})
        root_text = str(matched.get("rootText") or "")
        if hit.get("cls") == DISABLED_CARD_CLASS and SOLD_OUT_TEXT in root_text:
            return "sold_out"
    return None


def save_unavailable(
    settings: HZ24Settings,
    card: dict[str, Any],
    queue_row: dict[str, Any],
    tab: str,
    reason: str,
) -> None:
    sku = str(card.get("sku") or "")
    row = {
        "schema_version": settings.contracts.unavailable_schema,
        "status": "unavailable",
        "reason": reason,
        "observed_at": timestamp(),
        "worker_name": settings.contracts.worker_name,
        "sku": sku,
        "title": card.get("title"),
        "item_url": card.get("itemUrl")
        or f"https://{settings.browser.item_host}/{sku}.html",
        "source_tab": tab,
        "source_tabs": queue_row.get("source_tabs") or [tab],
        "structure_sha256": queue_row.get("structure_sha256"),
    }
    row["record_sha256"] = stable_hash(
        row,
        tuple(key for key in row if key != "record_sha256"),
    )
    upsert_jsonl_by_sku(settings.contracts.unavailable_file, row)


def build_linked_row(
    settings: HZ24Settings,
    page_adapter: JDPageAdapter,
    card: dict[str, Any],
    queue_row: dict[str, Any],
    tab: str,
    modal: dict[str, Any],
    click: dict[str, Any],
) -> dict[str, Any]:
    sku = str(card.get("sku") or "")
    created, expire, refresh = page_adapter.link_dates()
    row: dict[str, Any] = {
        "schema_version": settings.contracts.linked_schema,
        "status": "ok",
        "ts": timestamp(),
        "worker_name": settings.contracts.worker_name,
        "source_menu": f"商品推广/{tab}",
        "source_tab": tab,
        "source_tabs": queue_row.get("source_tabs") or [tab],
        "menu_mode": settings.contracts.menu_mode,
        "promotion_mode": settings.contracts.promotion_mode,
        "sku": sku,
        "title": card.get("title"),
        "item_url": card.get("itemUrl")
        or f"https://{settings.browser.item_host}/{sku}.html",
        "image_url": page_adapter.normalize_image(card.get("imageUrl")),
        "price": card.get("price"),
        "commission_rate": card.get("rate"),
        "estimated_income": card.get("income"),
        "short_url": modal.get("short_url"),
        "long_url": modal.get("long_url"),
        "qr_url": modal.get("qr_url"),
        "jd_command": modal.get("jd_command"),
        "link_created_at": created,
        "link_expire_at": expire,
        "link_expire_days": settings.collection.link_expire_days,
        "refresh_due_at": refresh,
        "refresh_after_days": settings.collection.refresh_after_days,
        "refresh_before_expiry_days": (
            settings.collection.refresh_before_expiry_days
        ),
        "structure_sha256": queue_row.get("structure_sha256"),
        "click_result": click,
    }
    row["record_sha256"] = stable_hash(row, LINK_HASH_FIELDS)
    return row
