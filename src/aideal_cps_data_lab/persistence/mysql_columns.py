from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from aideal_cps_data_lab.domain import CommissionProduct

BUSINESS_COLUMNS = (
    "title",
    "description",
    "item_url",
    "promotion_url",
    "short_url",
    "long_url",
    "qr_url",
    "jd_command",
    "image_url",
    "category_name",
    "shop_name",
    "price",
    "coupon_price",
    "commission_rate",
    "estimated_commission",
    "sales_volume",
    "coupon_info",
    "status",
    "link_created_at",
    "link_expire_at",
    "refresh_due_at",
)


def business_values(payload: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(payload.get(column) for column in BUSINESS_COLUMNS)


def stage_values(
    product: CommissionProduct,
    round_id: str,
    run_id: str,
) -> tuple[Any, ...]:
    now = datetime.now()
    checked_at = product.last_checked_at or now
    seen_at = product.last_seen_at or checked_at
    first_seen_at = product.first_seen_at or seen_at
    return (
        product.jd_sku_id,
        *business_values(product.business_payload()),
        product.source_page_no,
        round_id,
        run_id,
        product.source_payload_hash(),
        product.catalog_change_count,
        first_seen_at,
        checked_at,
        seen_at,
    )


def history_values(row: dict[str, Any], round_id: str) -> tuple[Any, ...]:
    before = {
        column: row.get(f"before_{column}") for column in BUSINESS_COLUMNS
    }
    after = {
        column: row.get(f"after_{column}") for column in BUSINESS_COLUMNS
    }
    return (
        row.get("jd_sku_id"),
        round_id,
        "update",
        json.dumps(before, ensure_ascii=False, default=str, sort_keys=True),
        json.dumps(after, ensure_ascii=False, default=str, sort_keys=True),
        row.get("before_hash"),
        row.get("after_hash"),
        datetime.now(),
    )
