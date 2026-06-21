from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

EXPECTED_SHA = "509d5b09bc9843d2e083ecd29fa2cfc83569c4cf877ced7a13d37a1e820d457a"
EXPECTED_ROWS = 3304
SKIP_DIRS = {".git", ".venv", ".venv-browser", "node_modules", "__pycache__", "logs", "run"}
NAME_HINTS = ("candidate", "commercial", "20260615", "100135", "lkg", "last_known", "hz23")


def git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def count_rows(raw: bytes) -> tuple[int, int, int]:
    rows = 0
    invalid = 0
    skus: list[str] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        rows += 1
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if isinstance(value, dict):
            skus.append(str(value.get("sku") or value.get("jd_sku_id") or ""))
    return rows, invalid, len(set(skus))


def iter_jsonl(root: Path):
    for path in root.rglob("*.jsonl"):
        parts = set(path.parts)
        if parts & SKIP_DIRS:
            continue
        yield path


def inspect(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    rows, invalid, unique_skus = count_rows(raw)
    return {
        "path": str(path),
        "size_bytes": len(raw),
        "sha256": sha,
        "row_count": rows,
        "invalid_row_count": invalid,
        "unique_sku_count": unique_skus,
        "exact_sha_match": sha == EXPECTED_SHA,
        "row_count_match": rows == EXPECTED_ROWS,
        "name_hint_match": any(hint in path.name.lower() for hint in NAME_HINTS),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--output", default="reports/hz23_lkg_locator_latest.json")
    args = parser.parse_args()
    repo = Path.cwd()
    roots = [Path(value).expanduser().resolve() for value in args.root]
    if not roots:
        roots = [repo.resolve(), repo.parent.resolve(), Path.home().resolve() / "backups"]
    seen: set[Path] = set()
    matches: list[dict[str, object]] = []
    scanned = 0
    errors: list[dict[str, str]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in iter_jsonl(root):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                item = inspect(resolved)
            except Exception as exc:
                errors.append({"path": str(resolved), "error": type(exc).__name__})
                continue
            scanned += 1
            if item["exact_sha_match"] or item["row_count_match"] or item["name_hint_match"]:
                matches.append(item)
    exact = [item for item in matches if item["exact_sha_match"]]
    payload = {
        "schema_version": "hz23-lkg-locator/v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "git_head": git_head(repo),
        "read_only": True,
        "expected": {"sha256": EXPECTED_SHA, "row_count": EXPECTED_ROWS},
        "roots": [str(root) for root in roots],
        "scanned_jsonl_count": scanned,
        "match_count": len(matches),
        "exact_match_count": len(exact),
        "status": "FOUND_EXACT" if exact else "NOT_FOUND_EXACT",
        "matches": matches[:200],
        "error_count": len(errors),
        "errors": errors[:50],
    }
    output = repo / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("STATUS=" + payload["status"])
    print("SCANNED_JSONL_COUNT=" + str(scanned))
    print("MATCH_COUNT=" + str(len(matches)))
    print("EXACT_MATCH_COUNT=" + str(len(exact)))
    print("REPORT=" + str(output.relative_to(repo)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
