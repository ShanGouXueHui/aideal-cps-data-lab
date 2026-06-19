from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.application.backfill import build_backfill_plan
from aideal_cps_data_lab.application.candidate_validation import validate_candidate
from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.hz24.repository import atomic_json, load_json
from aideal_cps_data_lab.persistence.mysql_batch_repository_v2 import (
    TransactionSafeBatchMySQLCommissionProductRepository,
)
from aideal_cps_data_lab.persistence.mysql_factory import build_connection_factory

DEFAULT_MANIFEST = Path(
    "data/export/aideal_cps_products_commercial_candidate_manifest.json"
)
DEFAULT_STATUS = Path("reports/hz23_commercial_status_v2_latest.json")
DEFAULT_REPORT = Path("reports/commission_mysql_backfill_latest.json")


@dataclass(frozen=True, slots=True)
class BackfillRequest:
    input_path: Path
    manifest_path: Path
    status_path: Path
    round_id: str
    run_id: str
    batch_size: int
    execute: bool
    report_path: Path


def initial_payload(request: BackfillRequest) -> dict[str, Any]:
    return {
        "ok": False,
        "mode": "execute" if request.execute else "dry_run",
        "repository_mode": "temporary_stage_single_transaction_v2",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input": str(request.input_path),
        "manifest": str(request.manifest_path),
        "commercial_status": str(request.status_path),
        "batch_size": request.batch_size,
    }


def finish(request: BackfillRequest, payload: dict[str, Any], code: int) -> int:
    atomic_json(request.report_path, payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


def commercial_gate(
    status: dict[str, Any],
    manifest: dict[str, Any],
    candidate_validation: dict[str, Any],
    plan_summary: dict[str, Any],
) -> tuple[str, dict[str, bool]]:
    status_round = status.get("latest_round") or {}
    status_manifest = status.get("candidate_manifest") or {}
    round_id = str(manifest.get("round_id") or "")
    checks = {
        "status_file_present": bool(status),
        "service_active": ((status.get("service") or {}).get("state") == "active"),
        "observation_ready": status.get("observation_ready") is True,
        "mysql_initialization_allowed": (
            status.get("mysql_initialization_allowed") is True
        ),
        "candidate_validation_ok": candidate_validation.get("ok") is True,
        "backfill_plan_ready": plan_summary.get("ready_for_write") is True,
        "round_id_present": bool(round_id),
        "round_id_matches_status": bool(round_id)
        and round_id == str(status_round.get("round_id") or ""),
        "round_id_matches_status_manifest": bool(round_id)
        and round_id == str(status_manifest.get("round_id") or ""),
        "commercial_switch_still_off": manifest.get("commercial_enabled") is False,
    }
    return round_id, checks


def execute_backfill(
    request: BackfillRequest,
    products,
    effective_round_id: str,
) -> dict[str, int]:
    settings = DataLabSettings.from_env()
    settings.assert_write_allowed()
    repository = TransactionSafeBatchMySQLCommissionProductRepository(
        build_connection_factory(settings),
        settings,
        batch_size=request.batch_size,
    )
    outcome = repository.upsert_many(
        products,
        round_id=effective_round_id,
        run_id=request.run_id,
    )
    return {
        "inserted": outcome.inserted,
        "updated": outcome.updated,
        "unchanged": outcome.unchanged,
        "rejected": outcome.rejected,
        "database_unique_sku_count": repository.count_by_sku(),
        "database_duplicate_sku_count": repository.duplicate_sku_count(),
    }


def run_backfill(request: BackfillRequest) -> int:
    payload = initial_payload(request)
    if not request.input_path.exists():
        payload["error"] = "input_missing"
        return finish(request, payload, 2)
    if request.batch_size <= 0:
        payload["error"] = "invalid_batch_size"
        return finish(request, payload, 2)

    validation = validate_candidate(
        request.input_path,
        request.manifest_path,
    ).as_dict()
    plan = build_backfill_plan(request.input_path)
    plan_summary = plan.summary()
    payload["candidate_validation"] = validation
    payload.update(plan_summary)

    status = load_json(request.status_path)
    manifest = load_json(request.manifest_path)
    round_id, checks = commercial_gate(
        status,
        manifest,
        validation,
        plan_summary,
    )
    payload["commercial_gate"] = checks
    payload["gate_failures"] = [name for name, passed in checks.items() if not passed]
    payload["ready_for_execute"] = all(checks.values())

    if not request.execute:
        payload["ok"] = bool(
            validation.get("ok") and plan_summary.get("ready_for_write")
        )
        return finish(request, payload, 0 if payload["ok"] else 1)
    if not payload["ready_for_execute"]:
        payload["error"] = "commercial_backfill_gate_not_ready"
        return finish(request, payload, 1)
    if request.round_id and request.round_id != round_id:
        payload["error"] = "explicit_round_id_mismatch"
        return finish(request, payload, 2)
    if not request.run_id:
        payload["error"] = "run_id_required"
        return finish(request, payload, 2)

    metrics = execute_backfill(
        request,
        plan.unique_products,
        request.round_id or round_id,
    )
    payload.update(metrics)
    payload["ok"] = (
        metrics["database_duplicate_sku_count"] == 0
        and metrics["database_unique_sku_count"] >= plan.valid_unique_count
    )
    return finish(request, payload, 0 if payload["ok"] else 1)


def parse_request() -> BackfillRequest:
    parser = argparse.ArgumentParser(
        description="Plan or execute an idempotent commission MySQL backfill."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--commercial-status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--round-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return BackfillRequest(
        input_path=args.input,
        manifest_path=args.manifest,
        status_path=args.commercial_status,
        round_id=args.round_id,
        run_id=args.run_id,
        batch_size=args.batch_size,
        execute=args.execute,
        report_path=args.report,
    )


def main() -> int:
    return run_backfill(parse_request())
