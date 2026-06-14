from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decimal_text(value: Any, *, percent: bool = False) -> str | None:
    if value in (None, ""):
        return None
    raw = str(value).strip()
    if percent and raw.endswith("%"):
        raw = raw[:-1].strip()
    try:
        number = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid_decimal:{value}") from exc
    return format(number, "f")


def _integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid_integer:{value}") from exc


def canonical_business_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Return the stable business fields used for change detection.

    Observation timestamps, page lineage, round identifiers, and import metadata are
    intentionally excluded. Numeric values are normalized so equivalent strings such as
    ``12.5%`` and ``12.5000`` produce the same hash.
    """

    promotion_url = _text(row.get("promotion_url") or row.get("short_url"))
    short_url = _text(row.get("short_url")) or promotion_url
    return {
        "jd_sku_id": _text(row.get("jd_sku_id") or row.get("sku")),
        "title": _text(row.get("title")),
        "description": _text(row.get("description")),
        "item_url": _text(row.get("item_url")),
        "promotion_url": promotion_url,
        "short_url": short_url,
        "long_url": _text(row.get("long_url")),
        "qr_url": _text(row.get("qr_url")),
        "jd_command": _text(row.get("jd_command")),
        "image_url": _text(row.get("image_url")),
        "category_name": _text(row.get("category_name")),
        "shop_name": _text(row.get("shop_name")),
        "price": _decimal_text(row.get("price")),
        "coupon_price": _decimal_text(row.get("coupon_price")),
        "commission_rate": _decimal_text(row.get("commission_rate"), percent=True),
        "estimated_commission": _decimal_text(
            row.get("estimated_commission")
            if row.get("estimated_commission") not in (None, "")
            else row.get("estimated_income")
        ),
        "sales_volume": _integer(row.get("sales_volume")),
        "coupon_info": _text(row.get("coupon_info")),
        "status": str(row.get("status") or "active").strip().lower(),
        "link_created_at": _text(row.get("link_created_at")),
        "link_expire_at": _text(row.get("link_expire_at")),
        "refresh_due_at": _text(row.get("refresh_due_at")),
    }


def canonical_payload_hash(row: dict[str, Any]) -> str:
    encoded = json.dumps(
        canonical_business_payload(row),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
