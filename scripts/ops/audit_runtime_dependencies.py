from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
OUTPUT = ROOT / "reports" / "runtime_dependency_audit_latest.json"
TEXT_EXTENSIONS = {".py", ".sh", ".toml", ".yaml", ".yml", ".json"}
SKIP_DIRS = {
    ".git",
    ".github",
    ".venv",
    ".venv-browser",
    "__pycache__",
    "backups",
    "data",
    "docs",
    "logs",
    "reports",
}
SCAN_ROOTS = ("scripts", "src", "tests", "config", "migrations")
RUN_REF_RE = re.compile(r"(?P<quote>['\"]?)(run/[A-Za-z0-9_./{}-]+)(?P=quote)")
SOURCE_SUFFIXES = {".py", ".sh"}
GENERATED_SUFFIXES = {".json", ".env", ".flag", ".lock", ".pid", ".log"}


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def is_scan_target(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if set(relative.parts) & SKIP_DIRS:
        return False
    return bool(relative.parts and relative.parts[0] in SCAN_ROOTS)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if not is_scan_target(path):
            continue
        if path.suffix in TEXT_EXTENSIONS:
            files.append(path)
    return sorted(files)


def is_generated_runtime_artifact(target: str) -> bool:
    path = Path(target)
    name = path.name
    suffix = path.suffix
    if name.startswith("."):
        return True
    if suffix in GENERATED_SUFFIXES:
        return True
    if suffix == "" and ("worktree" in name or name.startswith("v")):
        return True
    if "{" in target or "}" in target or target.endswith("_"):
        return True
    return False


def target_status(target: str) -> tuple[bool, str, bool]:
    if (ROOT / target).exists():
        return True, "present", False
    if is_generated_runtime_artifact(target):
        return True, "generated_runtime_artifact", False
    suffix = Path(target).suffix
    if suffix in SOURCE_SUFFIXES:
        return False, "missing_source_entrypoint", True
    return True, "non_source_runtime_reference", False


def main() -> int:
    references: list[dict[str, object]] = []
    for path in iter_files():
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for line_no, line in enumerate(lines, start=1):
            for match in RUN_REF_RE.finditer(line):
                target = match.group(2)
                exists, status, blocker = target_status(target)
                references.append(
                    {
                        "source": str(path.relative_to(ROOT)),
                        "line": line_no,
                        "target": target,
                        "target_exists": exists,
                        "target_status": status,
                        "blocker": blocker,
                        "text": line.strip()[:240],
                    }
                )
    missing = [item for item in references if item["blocker"] is True]
    payload = {
        "schema_version": "runtime-dependency-audit/v3",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_head": git_head(),
        "read_only": True,
        "scan_roots": list(SCAN_ROOTS),
        "reference_count": len(references),
        "missing_reference_count": len(missing),
        "status": "PASS" if not missing else "FAIL",
        "references": references,
        "missing_references": missing,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("STATUS=" + payload["status"])
    print("REFERENCE_COUNT=" + str(len(references)))
    print("MISSING_REFERENCE_COUNT=" + str(len(missing)))
    print("REPORT=" + str(OUTPUT.relative_to(ROOT)))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
