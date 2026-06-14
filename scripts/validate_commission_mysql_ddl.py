#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DEFAULT_DDL = Path("docs/architecture/commission_data_mysql_v1.sql")

REQUIRED_OBJECTS = [
    "commission_products",
    "commission_refresh_runs",
    "commission_product_history",
    "commission_publish_versions",
    "v_published_commission_products",
]

REQUIRED_FRAGMENTS = [
    "UNIQUE KEY uq_commission_products_sku (jd_sku_id)",
    "price DECIMAL(12,2)",
    "commission_rate DECIMAL(8,4)",
    "estimated_commission DECIMAL(12,2)",
    "source_payload_hash CHAR(64)",
    "missing_rounds INT UNSIGNED",
    "WHERE is_published = 1",
    "AND status = 'active'",
]

FORBIDDEN_PATTERNS = {
    "embedded_password": re.compile(r"(?i)identified\s+by\s+['\"][^'\"]+['\"]"),
    "global_grant": re.compile(r"(?i)grant\s+.+\s+on\s+\*\.\*"),
    "destructive_product_drop": re.compile(r"(?i)drop\s+table\s+(if\s+exists\s+)?commission_products"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the commission MySQL V1 DDL without connecting to MySQL.")
    parser.add_argument("path", nargs="?", default=str(DEFAULT_DDL))
    args = parser.parse_args()

    path = Path(args.path)
    result: dict[str, object] = {
        "path": str(path),
        "exists": path.exists(),
        "required_objects": {},
        "required_fragments": {},
        "forbidden_patterns": {},
        "ok": False,
    }

    if not path.exists():
        result["error"] = "ddl_missing"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    text = path.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    lowered = normalized.lower()

    objects: dict[str, bool] = {}
    for name in REQUIRED_OBJECTS:
        if name.startswith("v_"):
            objects[name] = f"create view {name}" in lowered
        else:
            objects[name] = f"create table if not exists {name}" in lowered
    result["required_objects"] = objects

    fragments = {fragment: fragment.lower() in lowered for fragment in REQUIRED_FRAGMENTS}
    result["required_fragments"] = fragments

    forbidden = {name: bool(pattern.search(text)) for name, pattern in FORBIDDEN_PATTERNS.items()}
    result["forbidden_patterns"] = forbidden

    result["statement_counts"] = {
        "create_table": len(re.findall(r"(?i)\bcreate\s+table\b", text)),
        "create_view": len(re.findall(r"(?i)\bcreate\s+view\b", text)),
        "drop_view": len(re.findall(r"(?i)\bdrop\s+view\b", text)),
    }

    result["ok"] = bool(
        all(objects.values())
        and all(fragments.values())
        and not any(forbidden.values())
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
