#!/usr/bin/env python3
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from aideal_cps_data_lab.io_utils import write_jsonl
from aideal_cps_data_lab.schema import ProductSnapshot


def main() -> int:
    rows = [
        ProductSnapshot(
            source="sample",
            collected_at=ProductSnapshot.now_utc_iso(),
            jd_sku_id="sample-sku-001",
            title="Sample product for JSONL export validation only",
            category_name="sample category",
            shop_name="sample shop",
            price=Decimal("99.00"),
            basis_price=Decimal("99.00"),
            coupon_price=Decimal("79.00"),
            purchase_price=Decimal("79.00"),
            product_url="https://example.invalid/product",
            material_url="https://example.invalid/material",
        )
    ]
    out = Path("data/import/sample_product_snapshots.jsonl")
    count = write_jsonl(out, rows)
    print(f"wrote={count}")
    print(f"output={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
