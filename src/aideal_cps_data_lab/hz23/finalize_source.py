from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aideal_cps_data_lab.hz24.repository import read_jsonl
from aideal_cps_data_lab.hz24.settings import HZ24Settings

from .finalize_candidates import deduplicate_source


@dataclass(frozen=True, slots=True)
class SourceSelection:
    path: Path | None
    dedup: dict[str, dict]
    source_duplicates: int
    unsafe_count: int
    untrusted_count: int
    source_row_count: int
    evaluated: tuple[dict[str, object], ...]


EMPTY_SELECTION = SourceSelection(
    path=None,
    dedup={},
    source_duplicates=0,
    unsafe_count=0,
    untrusted_count=0,
    source_row_count=0,
    evaluated=(),
)


def select_source(
    paths: tuple[Path, ...],
    settings: HZ24Settings,
) -> SourceSelection:
    fallback: SourceSelection | None = None
    evaluated: list[dict[str, object]] = []
    for path in paths:
        if not path.exists():
            evaluated.append(
                {"path": str(path), "present": False, "row_count": 0, "trusted_sku_count": 0}
            )
            continue
        rows = read_jsonl(path)
        dedup, duplicates, unsafe_count, untrusted_count = deduplicate_source(
            rows,
            settings,
        )
        evaluated.append(
            {
                "path": str(path),
                "present": True,
                "row_count": len(rows),
                "trusted_sku_count": len(dedup),
            }
        )
        selection = SourceSelection(
            path=path,
            dedup=dedup,
            source_duplicates=duplicates,
            unsafe_count=unsafe_count,
            untrusted_count=untrusted_count,
            source_row_count=len(rows),
            evaluated=(),
        )
        if fallback is None:
            fallback = selection
        if dedup:
            return SourceSelection(
                path=selection.path,
                dedup=selection.dedup,
                source_duplicates=selection.source_duplicates,
                unsafe_count=selection.unsafe_count,
                untrusted_count=selection.untrusted_count,
                source_row_count=selection.source_row_count,
                evaluated=tuple(evaluated),
            )
    chosen = fallback or EMPTY_SELECTION
    return SourceSelection(
        path=chosen.path,
        dedup=chosen.dedup,
        source_duplicates=chosen.source_duplicates,
        unsafe_count=chosen.unsafe_count,
        untrusted_count=chosen.untrusted_count,
        source_row_count=chosen.source_row_count,
        evaluated=tuple(evaluated),
    )
