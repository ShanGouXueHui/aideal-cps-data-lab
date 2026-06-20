from __future__ import annotations

from typing import Any

from .finalize_io import FinalizePaths
from .finalize_publish import persist_outcome
from .promotion_policy import is_promotion_ready


def persist_ready_outcome(
    paths: FinalizePaths,
    candidate_text: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    guarded = dict(manifest)
    if not is_promotion_ready(guarded):
        guarded["candidate_integrity_ready"] = False
    return persist_outcome(paths, candidate_text, guarded)
