#!/usr/bin/env python3
from __future__ import annotations

import tomllib
from decimal import Decimal
from pathlib import Path

from aideal_cps_data_lab.io_utils import write_jsonl
from aideal_cps_data_lab.schema import ProductSnapshot


def main() -> int:
    with Path("config/sample-export.toml").open("rb") as stream:
        config = tomllib.load(stream)
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
            product_url=str(config["product_url"]),
            material_url=str(config["material_url"]),
        )
    ]
    output = Path(str(config["output"]))
    count = write_jsonl(output, rows)
    print(f"wrote={count}")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
