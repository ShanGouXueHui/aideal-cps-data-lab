from __future__ import annotations

from pathlib import Path


REQUIRED_MARKERS = (
    "quality-reports:reports/project_engineering_audit_latest.json",
    "quality-reports:reports/offline_quality_latest.json",
    "audit report ref=quality-reports",
    "offline report ref=quality-reports",
)


def validate_authority_document(root: Path) -> list[str]:
    path = root / "docs/DOCUMENT_AUTHORITY.md"
    text = path.read_text(encoding="utf-8")
    return [marker for marker in REQUIRED_MARKERS if marker not in text]


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    missing = validate_authority_document(root)
    for marker in missing:
        print(f"MISSING_AUTHORITY_MARKER={marker}")
    print(f"AUTHORITY_MARKER_FAILURES={len(missing)}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
