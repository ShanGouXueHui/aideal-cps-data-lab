#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from aideal_cps_data_lab.application.landed_validation import validate_landed_rows
from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.persistence.mysql_factory import build_connection_factory

MANIFEST = Path("data/export/aideal_cps_products_commercial_candidate_manifest.json")
REPORT = Path("reports/commission_mysql_payload_hash_validation_latest.json")

COLUMNS = (
    "jd_sku_id", "title", "description", "item_url", "promotion_url",
    "short_url", "long_url", "qr_url", "jd_command", "image_url",
    "category_name", "shop_name", "price", "coupon_price",
    "commission_rate", "estimated_commission", "sales_volume",
    "coupon_info", "status", "link_created_at", "link_expire_at",
    "refresh_due_at", "source_payload_hash", "source_round_id",
)


def main() -> int:
    settings = DataLabSettings.from_env()
    if not settings.database_url and not settings.mysql_default_file:
        result = {"ok": False, "error": "mysql_connection_not_configured"}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    manifest = {}
    if MANIFEST.exists():
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            manifest = value

    connection = build_connection_factory(settings)()
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"SELECT {', '.join(COLUMNS)} FROM commission_products ORDER BY jd_sku_id"
        )
        rows = list(cursor.fetchall())
    finally:
        cursor.close()
        connection.close()

    result = validate_landed_rows(rows, manifest)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(REPORT.suffix + ".tmp")
    tmp.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(REPORT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
