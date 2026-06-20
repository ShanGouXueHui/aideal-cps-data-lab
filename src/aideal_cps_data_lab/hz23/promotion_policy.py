from __future__ import annotations

from typing import Any


def is_promotion_ready(manifest: dict[str, Any]) -> bool:
    return all(
        manifest.get(field) is True
        for field in (
            "round_complete",
            "candidate_integrity_ready",
            "observation_ready",
        )
    )
