from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .schema import ProductSnapshot


def write_jsonl(path: str | Path, rows: Iterable[ProductSnapshot]) -> int:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with target.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(row.to_json())
            f.write("\n")
            count += 1
    return count


def read_jsonl(path: str | Path) -> list[dict]:
    source = Path(path)
    rows: list[dict] = []
    with source.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            rows.append(json.loads(s))
    return rows
