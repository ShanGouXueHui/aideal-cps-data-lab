#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from aideal_cps_data_lab.application import build_backfill_plan
from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.persistence.mysql_factory import build_secret_file_connection_factory
from aideal_cps_data_lab.persistence.mysql_repository import MySQLCommissionProductRepository


def write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or execute an idempotent commission JSONL to MySQL backfill."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--round-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/commission_mysql_backfill_latest.json"),
    )
    args = parser.parse_args()

    if not args.input.exists():
        payload = {"ok": False, "error": "input_missing", "input": str(args.input)}
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    plan = build_backfill_plan(args.input)
    payload: dict[str, object] = {
        "ok": True,
        "mode": "execute" if args.execute else "dry_run",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        **plan.summary(),
    }

    if not args.execute:
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if payload["ready_for_write"] else 1

    if not payload["ready_for_write"]:
        payload.update(ok=False, error="backfill_plan_not_ready")
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1

    settings = DataLabSettings.from_env()
    settings.assert_write_allowed()
    if not args.round_id or not args.run_id:
        payload.update(ok=False, error="round_id_and_run_id_required")
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    factory = build_secret_file_connection_factory(settings)
    repository = MySQLCommissionProductRepository(factory, settings)
    outcome = repository.upsert_many(
        plan.unique_products,
        round_id=args.round_id,
        run_id=args.run_id,
    )
    payload.update(
        inserted=outcome.inserted,
        updated=outcome.updated,
        unchanged=outcome.unchanged,
        rejected=outcome.rejected,
        database_unique_sku_count=repository.count_by_sku(),
        database_duplicate_sku_count=repository.duplicate_sku_count(),
    )
    payload["ok"] = payload["database_duplicate_sku_count"] == 0
    write_report(args.report, payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
