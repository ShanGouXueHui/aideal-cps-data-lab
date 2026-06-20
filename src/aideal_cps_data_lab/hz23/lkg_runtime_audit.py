from __future__ import annotations

from pathlib import Path

from .lkg_settings import LastKnownGoodSettings


SCAN_SUFFIXES = (".py", ".sh", ".service", ".yml", ".yaml")


def canonical_writer_references(
    root: Path,
    settings: LastKnownGoodSettings,
) -> list[str]:
    needles = (
        str(settings.canonical_candidate),
        str(settings.canonical_manifest),
    )
    found: set[str] = set()
    for base_name in ("src", "scripts", "run", "config", ".github"):
        base = root / base_name
        if not base.exists():
            continue
        paths = [base] if base.is_file() else base.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(needle in text for needle in needles):
                found.add(str(path.relative_to(root)))
    return sorted(found)
