#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TABLES = [
    "commission_products",
    "commission_refresh_runs",
    "commission_product_history",
    "commission_publish_versions",
]
VIEW = "v_published_commission_products"


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the commission MySQL upgrade and rollback files without a database."
    )
    parser.add_argument(
        "--up",
        type=Path,
        default=Path("migrations/mysql/0001_commission_data_v1.up.sql"),
    )
    parser.add_argument(
        "--down",
        type=Path,
        default=Path("migrations/mysql/0001_commission_data_v1.down.sql"),
    )
    args = parser.parse_args()

    result: dict[str, object] = {
        "up": str(args.up),
        "down": str(args.down),
        "up_exists": args.up.exists(),
        "down_exists": args.down.exists(),
        "ok": False,
    }
    if not args.up.exists() or not args.down.exists():
        result["error"] = "migration_file_missing"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    up_text = args.up.read_text(encoding="utf-8")
    down_text = args.down.read_text(encoding="utf-8")
    up = normalize(up_text)
    down = normalize(down_text)

    creates = {table: f"create table if not exists {table}" in up for table in TABLES}
    drops = {table: f"drop table if exists {table}" in down for table in TABLES}
    view_create = f"create view {VIEW}" in up
    view_drop = f"drop view if exists {VIEW}" in down

    down_positions = [down.find(f"drop table if exists {table}") for table in reversed(TABLES)]
    rollback_order_ok = all(position >= 0 for position in down_positions) and down_positions == sorted(down_positions)

    forbidden = {
        "up_embedded_credentials": bool(re.search(r"(?i)identified\s+by", up_text)),
        "down_embedded_credentials": bool(re.search(r"(?i)identified\s+by", down_text)),
        "global_grant": bool(re.search(r"(?i)grant\s+.+\s+on\s+\*\.\*", up_text + down_text)),
        "drop_database": bool(re.search(r"(?i)drop\s+database", down_text)),
    }

    result.update(
        creates=creates,
        drops=drops,
        view_create=view_create,
        view_drop=view_drop,
        rollback_order_ok=rollback_order_ok,
        forbidden=forbidden,
        statement_counts={
            "up_create_table": len(re.findall(r"(?i)\bcreate\s+table\b", up_text)),
            "up_create_view": len(re.findall(r"(?i)\bcreate\s+view\b", up_text)),
            "down_drop_table": len(re.findall(r"(?i)\bdrop\s+table\b", down_text)),
            "down_drop_view": len(re.findall(r"(?i)\bdrop\s+view\b", down_text)),
        },
    )
    result["ok"] = bool(
        all(creates.values())
        and all(drops.values())
        and view_create
        and view_drop
        and rollback_order_ok
        and not any(forbidden.values())
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
