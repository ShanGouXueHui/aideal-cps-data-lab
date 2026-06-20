from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.hz24.repository import load_json

from .finalize_io import FinalizePaths, atomic_text, json_text

attempt_report_path = Path("reports/hz23_finalize_attempt_latest.json")


def serialize_candidates(rows: list[dict[str, Any]]) -> tuple[str, str]:
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        for row in rows
    )
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def should_promote(manifest: dict[str, Any]) -> bool:
    return bool(
        manifest.get("round_complete") is True
        and manifest.get("candidate_integrity_ready") is True
    )


def previous_manifest_summary(path: Path) -> dict[str, Any]:
    previous = load_json(path)
    return {
        "present": bool(previous),
        "round_id": previous.get("round_id"),
        "row_count": previous.get("row_count"),
        "data_sha256": previous.get("data_sha256"),
        "candidate_integrity_ready": previous.get("candidate_integrity_ready"),
        "observation_ready": previous.get("observation_ready"),
    }


def persist_outcome(
    paths: FinalizePaths,
    candidate_text: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    previous = previous_manifest_summary(paths.manifest)
    promoted = should_promote(manifest)
    outcome = dict(manifest)
    outcome["promoted"] = promoted
    outcome["promotion_status"] = "promoted" if promoted else "rejected"
    outcome["canonical_candidate_preserved"] = not promoted and paths.export.exists()
    outcome["canonical_manifest_preserved"] = not promoted and previous["present"]
    outcome["previous_manifest"] = previous

    if promoted:
        atomic_text(paths.export, candidate_text)
        atomic_text(paths.manifest, json_text(outcome))
    else:
        outcome["candidate_file"] = None
        outcome["data_file"] = None

    atomic_text(attempt_report_path, json_text(outcome))
    return outcome
