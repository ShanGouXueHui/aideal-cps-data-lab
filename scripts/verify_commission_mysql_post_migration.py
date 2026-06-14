#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.persistence.mysql_factory import build_connection_factory

EXPECTED_TABLES = {
    "commission_products",
    "commission_refresh_runs",
    "commission_product_history",
    "commission_publish_versions",
}
EXPECTED_VIEW = "v_published_commission_products"
REPORT = Path("reports/commission_mysql_post_migration_latest.json")


def scalar(cursor, sql: str) -> int:
    cursor.execute(sql)
    return int((cursor.fetchone() or {}).get("value") or 0)


def main() -> int:
    settings = DataLabSettings.from_env()
    if not settings.database_url and not settings.mysql_default_file:
        result = {"ok": False, "error": "mysql_connection_not_configured"}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    connection = build_connection_factory(settings)()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s",
            (settings.mysql_database,),
        )
        rows = list(cursor.fetchall())
        tables = {
            str(row.get("TABLE_NAME"))
            for row in rows
            if str(row.get("TABLE_TYPE")) == "BASE TABLE"
        }
        views = {
            str(row.get("TABLE_NAME"))
            for row in rows
            if str(row.get("TABLE_TYPE")) == "VIEW"
        }

        cursor.execute(
            "SELECT INDEX_NAME, NON_UNIQUE, COLUMN_NAME "
            "FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='commission_products'",
            (settings.mysql_database,),
        )
        indexes = list(cursor.fetchall())
        unique_sku = any(
            int(row.get("NON_UNIQUE") or 0) == 0
            and str(row.get("COLUMN_NAME")) == "jd_sku_id"
            for row in indexes
        )

        duplicate_sku_count = scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM ("
            "SELECT jd_sku_id FROM commission_products "
            "GROUP BY jd_sku_id HAVING COUNT(*)>1"
            ") AS duplicate_rows",
        )
        bad_link_count = scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM commission_products "
            "WHERE promotion_url NOT LIKE 'https://u.jd.com/%'",
        )
        required_field_violation_count = scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM commission_products "
            "WHERE jd_sku_id='' OR title='' OR image_url='' "
            "OR promotion_url='' OR price IS NULL OR source_payload_hash IS NULL",
        )
        published_view_count = scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM v_published_commission_products",
        )
        expected_published_count = scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM commission_products "
            "WHERE is_published=1 AND status='active'",
        )
        product_count = scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM commission_products",
        )

        checks = {
            "all_tables_present": EXPECTED_TABLES.issubset(tables),
            "published_view_present": EXPECTED_VIEW in views,
            "unique_sku_index_present": unique_sku,
            "duplicate_sku_zero": duplicate_sku_count == 0,
            "bad_link_zero": bad_link_count == 0,
            "required_field_violation_zero": required_field_violation_count == 0,
            "published_view_count_matches": published_view_count == expected_published_count,
        }
        result = {
            "ok": all(checks.values()),
            "database_name": settings.mysql_database,
            "tables": sorted(tables),
            "views": sorted(views),
            "missing_tables": sorted(EXPECTED_TABLES - tables),
            "product_count": product_count,
            "duplicate_sku_count": duplicate_sku_count,
            "bad_link_count": bad_link_count,
            "required_field_violation_count": required_field_violation_count,
            "published_view_count": published_view_count,
            "expected_published_count": expected_published_count,
            "checks": checks,
            "failures": [name for name, passed in checks.items() if not passed],
        }
    finally:
        cursor.close()
        connection.close()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(REPORT.suffix + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(REPORT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
