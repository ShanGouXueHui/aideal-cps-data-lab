from __future__ import annotations

import os
import tomllib
from pathlib import Path

from .settings_models import HZ24Settings
from .settings_sections import browser_settings, collection_settings, contract_settings


def _read(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def load_settings() -> HZ24Settings:
    root = Path(__file__).resolve().parents[3]
    default_config = root / "config"
    config_dir = Path(os.environ.get("AIDEAL_HZ24_CONFIG_DIR", str(default_config)))
    domain = _read(config_dir / "hz24-domain.toml")
    browser_data = _read(config_dir / "hz24-browser.toml")
    collection_data = _read(config_dir / "hz24-collection.toml")
    contracts_data = _read(config_dir / "hz24-contracts.toml")
    return HZ24Settings(
        root=root,
        special_tabs=tuple(str(value) for value in domain["special_tabs"]),
        allowed_unavailable_reasons=frozenset(
            str(value) for value in domain["allowed_unavailable_reasons"]
        ),
        browser=browser_settings(browser_data),
        collection=collection_settings(collection_data),
        contracts=contract_settings(root, contracts_data),
    )
