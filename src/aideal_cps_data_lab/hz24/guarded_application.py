from __future__ import annotations

import json

from .application import run_collection
from .repository import atomic_json
from .settings import load_settings
from .terminal_state import load_terminal_state


def run_guarded_collection() -> int:
    settings = load_settings()
    try:
        load_terminal_state(
            settings.contracts.linked_file,
            settings.contracts.unavailable_file,
        )
    except ValueError as error:
        report = {
            "ok": False,
            "complete": False,
            "reason": "terminal_state_conflict",
            "error": str(error),
        }
        atomic_json(settings.contracts.collection_report_file, report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 3

    result = run_collection()

    try:
        load_terminal_state(
            settings.contracts.linked_file,
            settings.contracts.unavailable_file,
        )
    except ValueError as error:
        report = {
            "ok": False,
            "complete": False,
            "reason": "terminal_state_conflict_after_collection",
            "error": str(error),
        }
        atomic_json(settings.contracts.collection_report_file, report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 3
    return result
