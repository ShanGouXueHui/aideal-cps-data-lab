from __future__ import annotations

import tomllib
from pathlib import Path


CONFIG_FILE = Path("config/engineering-audit.toml")


def load_limits() -> dict[str, object]:
    with CONFIG_FILE.open("rb") as stream:
        return tomllib.load(stream)
