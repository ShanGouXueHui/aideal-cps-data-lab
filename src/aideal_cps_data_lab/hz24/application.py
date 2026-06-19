from __future__ import annotations

import json

from .batch import BatchState
from .repository import atomic_json, successful_skus, unavailable_skus
from .session import run_session
from .settings import load_settings
from .state_store import build_report, checkpoint, load_queue


def run_collection() -> int:
    settings = load_settings()
    try:
        queue, queue_sha = load_queue(settings)
    except Exception as error:
        report = {
            "ok": False,
            "reason": "queue_integrity_failed",
            "error": repr(error),
        }
        atomic_json(settings.contracts.collection_report_file, report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 2

    linked = successful_skus(settings.contracts.linked_file)
    unavailable = unavailable_skus(settings.contracts.unavailable_file)
    pending = set(queue) - linked - unavailable
    batch = BatchState()
    checkpoint(
        settings,
        len(queue),
        queue_sha,
        len(linked),
        len(unavailable),
        len(pending),
        None,
        None,
        None,
    )
    run_session(
        settings,
        queue,
        queue_sha,
        linked,
        unavailable,
        pending,
        batch,
    )

    linked = successful_skus(settings.contracts.linked_file)
    unavailable = unavailable_skus(settings.contracts.unavailable_file)
    pending = set(queue) - linked - unavailable
    report = build_report(
        settings,
        queue,
        linked,
        unavailable,
        pending,
        batch,
    )
    atomic_json(settings.contracts.collection_report_file, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if batch.stop_reason and batch.stop_reason.startswith("risk_"):
        return 88
    return 1 if batch.stop_reason else 0
