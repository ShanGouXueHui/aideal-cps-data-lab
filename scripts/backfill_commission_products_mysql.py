#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.application import build_backfill_plan, validate_candidate
from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.persistence.mysql_batch_repository_v2 import (
    TransactionSafeBatchMySQLCommissionProductRepository,
)
from aideal_cps_data_lab.persistence.mysql_factory import build_connection_factory

DEFAULT_MANIFEST = Path(
    "data/export/aideal_cps_products_commercial_candidate_manifest.json"
)
DEFAULT_STATUS = Path("reports/hz23_commercial_status_v2_latest.json")


def write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(path)


def load_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or execute an idempotent commercial commission JSONL to MySQL backfill."
        )
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--commercial-status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--round-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/commission_mysql_backfill_latest.json"),
    )
    args = parser.parse_args()

    payload: dict[str, object] = {
        "ok": False,
        "mode": "execute" if args.execute else "dry_run",
        "repository_mode": "temporary_stage_single_transaction_v2",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input": str(args.input),
        "manifest": str(args.manifest),
        "commercial_status": str(args.commercial_status),
        "batch_size": args.batch_size,
    }

    if not args.input.exists():
        payload["error"] = "input_missing"
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    if args.batch_size <= 0:
        payload["error"] = "invalid_batch_size"
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    candidate_validation = validate_candidate(args.input, args.manifest).as_dict()
    payload["candidate_validation"] = candidate_validation

    plan = build_backfill_plan(args.input)
    payload.update(plan.summary())

    commercial_status = load_object(args.commercial_status)
    status_round = commercial_status.get("latest_round") or {}
    status_manifest = commercial_status.get("candidate_manifest") or {}
    manifest = load_object(args.manifest)

    round_id = str(manifest.get("round_id") or "")
    commercial_gate = {
        "status_file_present": bool(commercial_status),
        "service_active": ((commercial_status.get("service") or {}).get("state") == "active"),
        "observation_ready": commercial_status.get("observation_ready") is True,
        "mysql_initialization_allowed": (
            commercial_status.get("mysql_initialization_allowed") is True
        ),
        "candidate_validation_ok": candidate_validation.get("ok") is True,
        "backfill_plan_ready": plan.summary().get("ready_for_write") is True,
        "round_id_present": bool(round_id),
        "round_id_matches_status": bool(round_id)
        and round_id == str(status_round.get("round_id") or ""),
        "round_id_matches_status_manifest": bool(round_id)
        and round_id == str(status_manifest.get("round_id") or ""),
        "commercial_switch_still_off": manifest.get("commercial_enabled") is False,
    }
    payload["commercial_gate"] = commercial_gate
    payload["gate_failures"] = [
        name for name, passed in commercial_gate.items() if not passed
    ]
    payload["ready_for_execute"] = all(commercial_gate.values())

    if not args.execute:
        payload["ok"] = bool(
            candidate_validation.get("ok")
            and plan.summary().get("ready_for_write")
        )
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if payload["ok"] else 1

    if not payload["ready_for_execute"]:
        payload["error"] = "commercial_backfill_gate_not_ready"
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1

    if args.round_id and args.round_id != round_id:
        payload["error"] = "explicit_round_id_mismatch"
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    effective_round_id = args.round_id or round_id
    if not args.run_id:
        payload["error"] = "run_id_required"
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    settings = DataLabSettings.from_env()
    settings.assert_write_allowed()
    factory = build_connection_factory(settings)
    repository = TransactionSafeBatchMySQLCommissionProductRepository(
        factory,
        settings,
        batch_size=args.batch_size,
    )
    outcome = repository.upsert_many(
        plan.unique_products,
        round_id=effective_round_id,
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
    payload["ok"] = (
        int(payload["database_duplicate_sku_count"]) == 0
        and int(payload["database_unique_sku_count"]) >= plan.valid_unique_count
    )
    write_report(args.report, payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
