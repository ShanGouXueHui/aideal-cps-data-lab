#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.contracts import canonical_payload_hash
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

    mismatch_count = 0
    invalid_format_count = 0
    mismatch_samples: list[str] = []
    round_ids: set[str] = set()
    for row in rows:
        actual = str(row.get("source_payload_hash") or "")
        expected = canonical_payload_hash(row)
        if not re.fullmatch(r"[0-9a-f]{64}", actual):
            invalid_format_count += 1
        if actual != expected:
            mismatch_count += 1
            if len(mismatch_samples) < 20:
                mismatch_samples.append(str(row.get("jd_sku_id") or ""))
        if row.get("source_round_id"):
            round_ids.add(str(row.get("source_round_id")))

    manifest_rows = int(manifest.get("row_count") or 0) if manifest else None
    manifest_round = str(manifest.get("round_id") or "") if manifest else ""
    checks = {
        "manifest_present": bool(manifest),
        "row_count_matches_manifest": manifest_rows is not None and len(rows) == manifest_rows,
        "round_id_matches_manifest": bool(manifest_round and round_ids == {manifest_round}),
        "hash_format_valid": invalid_format_count == 0,
        "payload_hashes_match": mismatch_count == 0,
    }
    result = {
        "ok": all(checks.values()),
        "database_row_count": len(rows),
        "manifest_row_count": manifest_rows,
        "database_round_ids": sorted(round_ids),
        "manifest_round_id": manifest_round or None,
        "invalid_hash_format_count": invalid_format_count,
        "payload_hash_mismatch_count": mismatch_count,
        "payload_hash_mismatch_samples": mismatch_samples,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(REPORT.suffix + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(REPORT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
