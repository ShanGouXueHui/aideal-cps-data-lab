from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .application import run_collection
from .repository import atomic_json
from .resume_authorization import authorize_collection
from .resume_gate import load_gate_config
from .settings import load_settings
from .terminal_state import load_terminal_state


def _guard_result(
    reason: str,
    *,
    authorized: bool,
    collection_started: bool,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "aideal-hz24-collection-guard/v1",
        "ok": authorized,
        "reason": reason,
        "authorized": authorized,
        "collection_started": collection_started,
        "details": details,
    }


def _write_guard(payload: dict[str, Any]) -> None:
    config = load_gate_config()
    atomic_json(Path(str(config["guard_report"])), payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _terminal_state_error(reason: str, error: ValueError) -> int:
    _write_guard(
        _guard_result(
            reason,
            authorized=False,
            collection_started=False,
            details={"error": str(error)},
        )
    )
    return 3


def run_guarded_collection() -> int:
    settings = load_settings()
    authorized, authorization = authorize_collection(
        settings,
        require_pending=True,
    )
    if not authorized:
        _write_guard(
            _guard_result(
                "resume_authorization_failed",
                authorized=False,
                collection_started=False,
                details={
                    "failures": authorization.get("failures") or [],
                    "counts": authorization.get("counts") or {},
                },
            )
        )
        return 4

    try:
        load_terminal_state(
            settings.contracts.linked_file,
            settings.contracts.unavailable_file,
        )
    except ValueError as error:
        return _terminal_state_error("terminal_state_conflict", error)

    result = run_collection()

    try:
        load_terminal_state(
            settings.contracts.linked_file,
            settings.contracts.unavailable_file,
        )
    except ValueError as error:
        _write_guard(
            _guard_result(
                "terminal_state_conflict_after_collection",
                authorized=False,
                collection_started=True,
                details={"error": str(error), "collection_rc": result},
            )
        )
        return 3

    post_authorized, post = authorize_collection(
        settings,
        require_pending=False,
    )
    if not post_authorized:
        _write_guard(
            _guard_result(
                "post_collection_authorization_failed",
                authorized=False,
                collection_started=True,
                details={
                    "collection_rc": result,
                    "failures": post.get("failures") or [],
                    "counts": post.get("counts") or {},
                },
            )
        )
        return 5

    _write_guard(
        _guard_result(
            "collection_completed_or_paused_safely",
            authorized=True,
            collection_started=True,
            details={
                "collection_rc": result,
                "counts": post.get("counts") or {},
            },
        )
    )
    return result
