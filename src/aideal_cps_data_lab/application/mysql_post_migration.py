from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.hz24.repository import atomic_json
from aideal_cps_data_lab.hz24.settings import load_settings
from aideal_cps_data_lab.persistence.mysql_factory import build_connection_factory

EXPECTED_TABLES = {
    "commission_products",
    "commission_refresh_runs",
    "commission_product_history",
    "commission_publish_versions",
}
EXPECTED_VIEW = "v_published_commission_products"
DEFAULT_REPORT = Path("reports/commission_mysql_post_migration_latest.json")


def query_scalar(cursor: Any, statement: str, parameters: tuple[Any, ...] = ()) -> int:
    cursor.execute(statement, parameters)
    return int((cursor.fetchone() or {}).get("value") or 0)


def inspect_structure(cursor: Any, database_name: str) -> dict[str, Any]:
    cursor.execute(
        "SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=%s",
        (database_name,),
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
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
        (database_name, "commission_products"),
    )
    indexes = list(cursor.fetchall())
    unique_sku = any(
        int(row.get("NON_UNIQUE") or 0) == 0
        and str(row.get("COLUMN_NAME")) == "jd_sku_id"
        for row in indexes
    )
    return {"tables": tables, "views": views, "unique_sku": unique_sku}


def collect_metrics(cursor: Any, trusted_pattern: str) -> dict[str, int]:
    return {
        "duplicate_sku_count": query_scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM ("
            "SELECT jd_sku_id FROM commission_products "
            "GROUP BY jd_sku_id HAVING COUNT(*)>1"
            ") AS duplicate_rows",
        ),
        "bad_link_count": query_scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM commission_products "
            "WHERE promotion_url NOT LIKE %s",
            (trusted_pattern,),
        ),
        "required_field_violation_count": query_scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM commission_products "
            "WHERE jd_sku_id='' OR title='' OR image_url='' "
            "OR promotion_url='' OR price IS NULL OR source_payload_hash IS NULL",
        ),
        "published_view_count": query_scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM v_published_commission_products",
        ),
        "expected_published_count": query_scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM commission_products "
            "WHERE is_published=1 AND status='active'",
        ),
        "product_count": query_scalar(
            cursor,
            "SELECT COUNT(*) AS value FROM commission_products",
        ),
    }


def build_result(
    database_name: str,
    structure: dict[str, Any],
    metrics: dict[str, int],
) -> dict[str, Any]:
    tables = structure["tables"]
    views = structure["views"]
    checks = {
        "all_tables_present": EXPECTED_TABLES.issubset(tables),
        "published_view_present": EXPECTED_VIEW in views,
        "unique_sku_index_present": structure["unique_sku"],
        "duplicate_sku_zero": metrics["duplicate_sku_count"] == 0,
        "bad_link_zero": metrics["bad_link_count"] == 0,
        "required_field_violation_zero": (
            metrics["required_field_violation_count"] == 0
        ),
        "published_view_count_matches": (
            metrics["published_view_count"] == metrics["expected_published_count"]
        ),
    }
    return {
        "ok": all(checks.values()),
        "database_name": database_name,
        "tables": sorted(tables),
        "views": sorted(views),
        "missing_tables": sorted(EXPECTED_TABLES - tables),
        **metrics,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
    }


def run_verification(report_path: Path = DEFAULT_REPORT) -> int:
    settings = DataLabSettings.from_env()
    if not settings.database_url and not settings.mysql_default_file:
        result = {"ok": False, "error": "mysql_connection_not_configured"}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2
    browser = load_settings().browser
    trusted_pattern = f"{browser.trusted_link_scheme}://{browser.trusted_link_host}/%"
    connection = build_connection_factory(settings)()
    cursor = connection.cursor()
    try:
        structure = inspect_structure(cursor, settings.mysql_database)
        metrics = collect_metrics(cursor, trusted_pattern)
        result = build_result(settings.mysql_database, structure, metrics)
    finally:
        cursor.close()
        connection.close()
    atomic_json(report_path, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1
