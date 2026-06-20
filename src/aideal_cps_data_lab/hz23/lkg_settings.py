from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LastKnownGoodSettings:
    schema_version: str
    expected_round_id: str
    expected_row_count: int
    expected_data_sha256: str
    canonical_candidate: Path
    canonical_manifest: Path
    service_name: str
    search_roots: tuple[Path, ...]
    candidate_name_fragments: tuple[str, ...]


def load_last_known_good_settings(path: Path) -> LastKnownGoodSettings:
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    return LastKnownGoodSettings(
        schema_version=str(data["schema_version"]),
        expected_round_id=str(data["expected_round_id"]),
        expected_row_count=int(data["expected_row_count"]),
        expected_data_sha256=str(data["expected_data_sha256"]),
        canonical_candidate=Path(str(data["canonical_candidate"])),
        canonical_manifest=Path(str(data["canonical_manifest"])),
        service_name=str(data["service_name"]),
        search_roots=tuple(Path(str(value)) for value in data["search_roots"]),
        candidate_name_fragments=tuple(
            str(value).lower() for value in data["candidate_name_fragments"]
        ),
    )
