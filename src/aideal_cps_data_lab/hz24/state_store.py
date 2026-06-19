from __future__ import annotations

import hashlib
from typing import Any

from .batch import BatchState
from .records import timestamp
from .repository import atomic_json, load_json, read_jsonl
from .settings import HZ24Settings


def load_queue(
    settings: HZ24Settings,
) -> tuple[dict[str, dict[str, Any]], str]:
    manifest = load_json(settings.contracts.queue_manifest_file)
    raw = settings.contracts.queue_file.read_bytes()
    rows = read_jsonl(settings.contracts.queue_file)
    digest = hashlib.sha256(raw).hexdigest()
    expected = str(manifest.get("data_sha256") or "")
    if not rows or digest != expected:
        raise ValueError("queue_integrity_failed")
    indexed = {
        str(row.get("sku") or ""): row
        for row in rows
        if str(row.get("sku") or "")
    }
    return indexed, digest


def checkpoint(
    settings: HZ24Settings,
    queue_count: int,
    queue_sha: str,
    linked_count: int,
    unavailable_count: int,
    pending_count: int,
    tab: str | None,
    sku: str | None,
    stop_reason: str | None,
    complete: bool = False,
) -> None:
    state = load_json(settings.contracts.state_file)
    state.update(
        {
            "schema_version": settings.contracts.state_schema,
            "queue_sha256": queue_sha,
            "queue_count": queue_count,
            "started_at": state.get("started_at") or timestamp(),
            "updated_at": timestamp(),
            "last_tab": tab,
            "last_sku": sku,
            "linked_count": linked_count,
            "unavailable_count": unavailable_count,
            "pending_count": pending_count,
            "complete": complete,
            "stop_reason": stop_reason,
        }
    )
    atomic_json(settings.contracts.state_file, state)


def build_report(
    settings: HZ24Settings,
    queue: dict[str, dict[str, Any]],
    linked: set[str],
    unavailable: set[str],
    pending: set[str],
    batch: BatchState,
) -> dict[str, Any]:
    queue_skus = set(queue)
    return {
        "schema_version": settings.contracts.collection_schema,
        "generated_at": timestamp(),
        "ok": batch.stop_reason is None,
        "complete": not pending,
        "queue_count": len(queue),
        "success_count": len(linked & queue_skus),
        "unavailable_count": len(unavailable & queue_skus),
        "accounted_count": len((linked | unavailable) & queue_skus),
        "pending_count": len(pending),
        "pending_samples": sorted(pending)[:30],
        "batch_processed": batch.processed,
        "batch_success": batch.linked,
        "batch_unavailable": batch.unavailable,
        "batch_fail": batch.failed,
        "failures": batch.failures[-30:],
        "stop_reason": batch.stop_reason,
        "risk": batch.stop_risk,
        "output_file": str(settings.contracts.linked_file),
        "unavailable_file": str(settings.contracts.unavailable_file),
    }
