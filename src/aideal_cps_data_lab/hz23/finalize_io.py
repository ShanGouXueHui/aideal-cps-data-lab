from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class FinalizePaths:
    summary: Path
    index: Path
    seen: Path
    observer_state: Path
    source_candidates: tuple[Path, ...]
    export: Path
    manifest: Path


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def choose_source(paths: tuple[Path, ...]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def observation_hours(state: dict[str, Any], generated_at: str) -> float:
    started = state.get("observation_started_at") or state.get("created_at")
    if not started:
        return 0.0
    try:
        start = datetime.fromisoformat(str(started))
        end = datetime.fromisoformat(generated_at)
    except Exception:
        return 0.0
    return max(0.0, (end - start).total_seconds() / 3600.0)


def update_catalog(
    index: dict[str, Any],
    seen: set[str],
    round_id: str,
    generated_at: str,
) -> dict[str, Any]:
    products = index.setdefault("products", {})
    for sku, row in products.items():
        if sku in seen:
            row["missing_rounds"] = 0
            row["active"] = True
        else:
            row["missing_rounds"] = int(row.get("missing_rounds") or 0) + 1
            if row["missing_rounds"] >= 2:
                row["active"] = False
    index["updated_at"] = generated_at
    index["last_completed_round_id"] = round_id
    return products


def json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
