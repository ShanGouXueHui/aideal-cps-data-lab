from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
OUTPUT = ROOT / "reports" / "runtime_dependency_audit_latest.json"
TEXT_EXTENSIONS = {".py", ".sh", ".toml", ".yaml", ".yml", ".json", ".md"}
SKIP_DIRS = {".git", ".venv", ".venv-browser", "logs", "run", "data", "reports", "__pycache__"}
RUN_REF_RE = re.compile(r"(?P<quote>['\"]?)(run/[A-Za-z0-9_./-]+)(?P=quote)")


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if set(path.relative_to(ROOT).parts) & SKIP_DIRS:
            continue
        if path.suffix in TEXT_EXTENSIONS:
            files.append(path)
    return sorted(files)


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
                references.append(
                    {
                        "source": str(path.relative_to(ROOT)),
                        "line": line_no,
                        "target": target,
                        "target_exists": (ROOT / target).exists(),
                        "text": line.strip()[:240],
                    }
                )
    missing = [item for item in references if not item["target_exists"]]
    payload = {
        "schema_version": "runtime-dependency-audit/v1",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_head": git_head(),
        "read_only": True,
        "reference_count": len(references),
        "missing_reference_count": len(missing),
        "status": "PASS" if not missing else "FAIL",
        "references": references,
        "missing_references": missing,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("STATUS=" + payload["status"])
    print("REFERENCE_COUNT=" + str(len(references)))
    print("MISSING_REFERENCE_COUNT=" + str(len(missing)))
    print("REPORT=" + str(OUTPUT.relative_to(ROOT)))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
