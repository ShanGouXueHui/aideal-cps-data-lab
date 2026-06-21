from __future__ import annotations

import tomli
from pathlib import Path


CONFIG_FILE = Path("config/engineering-audit.toml")


def load_limits() -> dict[str, object]:
    with CONFIG_FILE.open("rb") as stream:
        return tomli.load(stream)
