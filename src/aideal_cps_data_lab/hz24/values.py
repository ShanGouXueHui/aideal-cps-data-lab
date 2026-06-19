from __future__ import annotations

import tomllib
from pathlib import Path


CONFIG_DIRECTORY = Path("config")


def read_hz24_values() -> dict[str, object]:
    result: dict[str, object] = {}
    for name in ("hz24-domain.toml", "hz24-browser.toml", "hz24-collection.toml"):
        with (CONFIG_DIRECTORY / name).open("rb") as stream:
            result.update(tomllib.load(stream))
    return result
