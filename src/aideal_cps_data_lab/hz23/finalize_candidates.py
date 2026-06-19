from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from aideal_cps_data_lab.application.candidate_validation import expected_feed_schema
from aideal_cps_data_lab.contracts import canonical_payload_hash
from aideal_cps_data_lab.hz23.safety import unsafe_source_reason
from aideal_cps_data_lab.hz24.settings import HZ24Settings


def trusted_url(value: Any, settings: HZ24Settings) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except Exception:
        return False
    return (
        parsed.scheme == settings.browser.trusted_link_scheme
        and parsed.hostname == settings.browser.trusted_link_host
    )


def deduplicate_source(
    rows: list[dict[str, Any]],
    settings: HZ24Settings,
) -> tuple[dict[str, dict[str, Any]], int, int, int]:
    dedup: dict[str, dict[str, Any]] = {}
    occurrences: dict[str, int] = {}
    unsafe_count = 0
    untrusted_count = 0
    for row in rows:
        sku = str(row.get("sku") or "").strip()
        if not sku.isdigit() or row.get("status") != "ok" or not row.get("short_url"):
            continue
        occurrences[sku] = occurrences.get(sku, 0) + 1
        if unsafe_source_reason(row):
            unsafe_count += 1
            continue
        if not trusted_url(row.get("short_url"), settings):
            untrusted_count += 1
            continue
        dedup[sku] = row
    duplicates = sum(max(0, count - 1) for count in occurrences.values())
    return dedup, duplicates, unsafe_count, untrusted_count


def normalize_feed_row(
    sku: str,
    base: dict[str, Any],
    catalog: dict[str, Any],
    round_id: str,
    generated_at: str,
    settings: HZ24Settings,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": expected_feed_schema,
        "source": "jd_union_datalab",
        "sku": sku,
        "title": catalog.get("title") or base.get("title"),
        "description": base.get("description"),
        "item_url": catalog.get("item_url")
        or base.get("item_url")
        or f"{settings.browser.item_scheme}://{settings.browser.item_host}/{sku}.html",
        "promotion_url": base.get("short_url"),
        "short_url": base.get("short_url"),
        "long_url": base.get("long_url"),
        "qr_url": base.get("qr_url"),
        "jd_command": base.get("jd_command"),
        "image_url": catalog.get("image_url") or base.get("image_url"),
        "category_name": base.get("category_name"),
        "shop_name": base.get("shop_name"),
        "price": catalog.get("price") or base.get("price"),
        "coupon_price": base.get("coupon_price"),
        "commission_rate": catalog.get("commission_rate")
        or base.get("commission_rate"),
        "estimated_commission": catalog.get("estimated_income")
        or base.get("estimated_income"),
        "sales_volume": base.get("sales_volume"),
        "coupon_info": base.get("coupon_info"),
        "status": "active",
        "link_created_at": base.get("link_created_at"),
        "link_expire_at": base.get("link_expire_at"),
        "refresh_due_at": base.get("refresh_due_at"),
        "last_checked_at": catalog.get("last_checked_at"),
        "last_seen_at": catalog.get("last_seen_at"),
        "source_round_id": catalog.get("last_round_id") or round_id,
        "source_run_id": base.get("run_id"),
        "source_page_no": base.get("page_no"),
        "source_updated_at": catalog.get("last_checked_at")
        or base.get("ts")
        or generated_at,
        "catalog_change_count": int(catalog.get("change_count") or 0),
    }
    row["source_payload_hash"] = canonical_payload_hash(row)
    return row


def build_candidates(
    dedup: dict[str, dict[str, Any]],
    products: dict[str, Any],
    round_id: str,
    generated_at: str,
    settings: HZ24Settings,
    unsafe_count: int,
    untrusted_count: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rejected = {
        "inactive": 0,
        "missing_title": 0,
        "missing_item_url": 0,
        "missing_image_url": 0,
        "missing_price": 0,
        "missing_promotion_url": 0,
        "unsafe_hz20": unsafe_count,
        "untrusted_promotion_url": untrusted_count,
    }
    eligible: list[dict[str, Any]] = []
    for sku, base in dedup.items():
        catalog = products.get(sku) or {}
        if catalog and catalog.get("active") is False:
            rejected["inactive"] += 1
            continue
        row = normalize_feed_row(
            sku, base, catalog, round_id, generated_at, settings
        )
        missing = [
            field
            for field in ("title", "item_url", "image_url", "price", "promotion_url")
            if not row.get(field)
        ]
        for field in missing:
            rejected[f"missing_{field}"] += 1
        if missing:
            continue
        if not trusted_url(row.get("promotion_url"), settings):
            rejected["untrusted_promotion_url"] += 1
            continue
        eligible.append(row)
    eligible.sort(key=lambda row: str(row.get("sku") or ""))
    return eligible, rejected
