from __future__ import annotations

import tomllib
from dataclasses import dataclass

from .settings import HZ24Settings


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    linked_manifest_schema: str
    outcome_manifest_schema: str
    required_link_fields: tuple[str, ...]
    legacy_source_marker: str


def load_validation_config(
    settings: HZ24Settings,
) -> ValidationConfig:
    path = settings.root / "config/hz24-validation.toml"
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    return ValidationConfig(
        linked_manifest_schema=str(data["linked_manifest_schema"]),
        outcome_manifest_schema=str(data["outcome_manifest_schema"]),
        required_link_fields=tuple(
            str(value) for value in data["required_link_fields"]
        ),
        legacy_source_marker=str(data["legacy_source_marker"]),
    )
