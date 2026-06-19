from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class JingfenSettings:
    auth_probe_urls: tuple[str, ...]
    login_start_url: str
    public_probe_urls: tuple[str, ...]
    profile_path: Path
    storage_path: Path
    locale: str
    timezone_id: str
    viewport_width: int
    viewport_height: int


def load_jingfen_settings(root: Path | None = None) -> JingfenSettings:
    root = root or Path.cwd()
    path = root / "config/jingfen.toml"
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    return JingfenSettings(
        auth_probe_urls=tuple(str(value) for value in data["auth_probe_urls"]),
        login_start_url=str(data["login_start_url"]),
        public_probe_urls=tuple(str(value) for value in data["public_probe_urls"]),
        profile_path=root / str(data["profile_path"]),
        storage_path=root / str(data["storage_path"]),
        locale=str(data["locale"]),
        timezone_id=str(data["timezone_id"]),
        viewport_width=int(data["viewport_width"]),
        viewport_height=int(data["viewport_height"]),
    )
