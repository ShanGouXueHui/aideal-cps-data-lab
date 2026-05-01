from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import json


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


@dataclass
class ProductSnapshot:
    source: str = "jd_portal"
    source_url: str | None = None
    collected_at: str | None = None

    jd_sku_id: str | None = None
    title: str = ""
    category_name: str | None = None
    shop_name: str | None = None
    brand_name: str | None = None

    price: Decimal | None = None
    basis_price: Decimal | None = None
    coupon_price: Decimal | None = None
    purchase_price: Decimal | None = None
    commission_rate: Decimal | None = None

    sales_volume: int | None = None
    comment_count: int | None = None
    good_comments_share: Decimal | None = None

    image_url: str | None = None
    product_url: str | None = None
    material_url: str | None = None
    short_url: str | None = None

    raw: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def now_utc_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def saved_amount(self) -> Decimal:
        basis = self.basis_price or self.price or Decimal("0")
        purchase = self.purchase_price or self.coupon_price or Decimal("0")
        if basis > 0 and purchase > 0 and basis > purchase:
            return basis - purchase
        return Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        out: dict[str, Any] = {}
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, Decimal):
                out[key] = str(value)
            else:
                out[key] = value
        return out

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductSnapshot":
        money_fields = {
            "price",
            "basis_price",
            "coupon_price",
            "purchase_price",
            "commission_rate",
            "good_comments_share",
        }
        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key in money_fields:
                kwargs[key] = _decimal_or_none(value)
            else:
                kwargs[key] = value
        return cls(**kwargs)
