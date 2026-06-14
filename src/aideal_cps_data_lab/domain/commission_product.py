from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from aideal_cps_data_lab.contracts import canonical_business_payload, canonical_payload_hash


class ProductValidationError(ValueError):
    """Raised when a candidate row is not eligible for commercial persistence."""


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ProductValidationError(f"missing_{field}")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decimal(value: Any, field: str, *, required: bool = False) -> Decimal | None:
    if value in (None, ""):
        if required:
            raise ProductValidationError(f"missing_{field}")
        return None
    raw = str(value).strip()
    if raw.endswith("%"):
        raw = raw[:-1].strip()
    try:
        number = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ProductValidationError(f"invalid_{field}") from exc
    if number < 0:
        raise ProductValidationError(f"negative_{field}")
    return number


def _integer(value: Any, field: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ProductValidationError(f"invalid_{field}") from exc
    if number < 0:
        raise ProductValidationError(f"negative_{field}")
    return number


def _validate_promotion_url(value: Any) -> str:
    url = _required_text(value, "promotion_url")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "u.jd.com":
        raise ProductValidationError("untrusted_promotion_url")
    return url


@dataclass(frozen=True, slots=True)
class CommissionProduct:
    jd_sku_id: str
    title: str
    item_url: str
    promotion_url: str
    image_url: str
    price: Decimal
    coupon_price: Decimal | None = None
    commission_rate: Decimal | None = None
    estimated_commission: Decimal | None = None
    sales_volume: int | None = None
    description: str | None = None
    short_url: str | None = None
    long_url: str | None = None
    qr_url: str | None = None
    jd_command: str | None = None
    category_name: str | None = None
    shop_name: str | None = None
    coupon_info: str | None = None
    status: str = "active"
    source_page_no: int | None = None
    source_round_id: str | None = None
    source_run_id: str | None = None
    catalog_change_count: int = 0
    link_created_at: str | None = None
    link_expire_at: str | None = None
    refresh_due_at: str | None = None
    first_seen_at: str | None = None
    last_checked_at: str | None = None
    last_seen_at: str | None = None

    @classmethod
    def from_candidate_row(cls, row: dict[str, Any]) -> "CommissionProduct":
        sku = _required_text(row.get("jd_sku_id") or row.get("sku"), "jd_sku_id")
        if not sku.isdigit():
            raise ProductValidationError("invalid_jd_sku_id")

        status = str(row.get("status") or "active").strip().lower()
        if status not in {"active", "inactive", "quarantined"}:
            raise ProductValidationError("invalid_status")

        source_page_no = _integer(row.get("source_page_no") or row.get("page_no"), "source_page_no")
        if source_page_no is not None and not 1 <= source_page_no <= 67:
            raise ProductValidationError("invalid_source_page_no")

        change_count = _integer(row.get("catalog_change_count") or 0, "catalog_change_count") or 0

        return cls(
            jd_sku_id=sku,
            title=_required_text(row.get("title"), "title"),
            item_url=_required_text(row.get("item_url"), "item_url"),
            promotion_url=_validate_promotion_url(row.get("promotion_url") or row.get("short_url")),
            image_url=_required_text(row.get("image_url"), "image_url"),
            price=_decimal(row.get("price"), "price", required=True),
            coupon_price=_decimal(row.get("coupon_price"), "coupon_price"),
            commission_rate=_decimal(row.get("commission_rate"), "commission_rate"),
            estimated_commission=_decimal(
                row.get("estimated_commission") or row.get("estimated_income"),
                "estimated_commission",
            ),
            sales_volume=_integer(row.get("sales_volume"), "sales_volume"),
            description=_optional_text(row.get("description")),
            short_url=_optional_text(row.get("short_url")) or _optional_text(row.get("promotion_url")),
            long_url=_optional_text(row.get("long_url")),
            qr_url=_optional_text(row.get("qr_url")),
            jd_command=_optional_text(row.get("jd_command")),
            category_name=_optional_text(row.get("category_name")),
            shop_name=_optional_text(row.get("shop_name")),
            coupon_info=_optional_text(row.get("coupon_info")),
            status=status,
            source_page_no=source_page_no,
            source_round_id=_optional_text(row.get("source_round_id")),
            source_run_id=_optional_text(row.get("source_run_id") or row.get("run_id")),
            catalog_change_count=change_count,
            link_created_at=_optional_text(row.get("link_created_at")),
            link_expire_at=_optional_text(row.get("link_expire_at")),
            refresh_due_at=_optional_text(row.get("refresh_due_at")),
            first_seen_at=_optional_text(row.get("first_seen_at")),
            last_checked_at=_optional_text(row.get("last_checked_at")),
            last_seen_at=_optional_text(row.get("last_seen_at")),
        )

    def business_payload(self) -> dict[str, Any]:
        """Return the canonical fields whose change is a business change."""

        return canonical_business_payload(
            {
                "jd_sku_id": self.jd_sku_id,
                "title": self.title,
                "description": self.description,
                "item_url": self.item_url,
                "promotion_url": self.promotion_url,
                "short_url": self.short_url,
                "long_url": self.long_url,
                "qr_url": self.qr_url,
                "jd_command": self.jd_command,
                "image_url": self.image_url,
                "category_name": self.category_name,
                "shop_name": self.shop_name,
                "price": self.price,
                "coupon_price": self.coupon_price,
                "commission_rate": self.commission_rate,
                "estimated_commission": self.estimated_commission,
                "sales_volume": self.sales_volume,
                "coupon_info": self.coupon_info,
                "status": self.status,
                "link_created_at": self.link_created_at,
                "link_expire_at": self.link_expire_at,
                "refresh_due_at": self.refresh_due_at,
            }
        )

    def source_payload_hash(self) -> str:
        return canonical_payload_hash(self.business_payload())

    def persistence_payload(self) -> dict[str, Any]:
        return {
            **self.business_payload(),
            "source_page_no": self.source_page_no,
            "source_round_id": self.source_round_id,
            "source_run_id": self.source_run_id,
            "source_payload_hash": self.source_payload_hash(),
            "catalog_change_count": self.catalog_change_count,
            "first_seen_at": self.first_seen_at,
            "last_checked_at": self.last_checked_at,
            "last_seen_at": self.last_seen_at,
        }
