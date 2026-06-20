from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


URL_RE = re.compile(r"https?://[^\s'\"<>]+")
IP_RE = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:home|etc|opt|srv|var|usr|root)/[^\s'\"]+")
SHELL_FUNCTION_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{")
SHELL_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def name_has_fragment(name: str, fragments: tuple[str, ...]) -> bool:
    tokens = tuple(part for part in name.lower().split("_") if part)
    return any(fragment in tokens for fragment in fragments)


def iter_engineering_files(root: Path, settings: dict[str, object]) -> Iterable[Path]:
    extensions = set(str(value) for value in settings["scan_extensions"])
    excluded = set(str(value) for value in settings["excluded_directories"])
    config_directories = set(
        str(value) for value in settings["configuration_directories"]
    )
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts):
            continue
        is_config = bool(set(relative.parts) & config_directories)
        if path.suffix not in extensions and not is_config:
            continue
        yield relative


def is_configuration_file(path: Path, settings: dict[str, object]) -> bool:
    directories = set(str(value) for value in settings["configuration_directories"])
    extensions = set(
        str(value)
        for value in settings.get(
            "configuration_extensions",
            [".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"],
        )
    )
    return bool(set(path.parts) & directories) or path.suffix.lower() in extensions
