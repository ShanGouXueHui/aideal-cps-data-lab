from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path

EXPECTED_SHA = "509d5b09bc9843d2e083ecd29fa2cfc83569c4cf877ced7a13d37a1e820d457a"
EXPECTED_ROWS = 3304
SKIP_NAMES = {".git", ".venv", ".venv-browser", "node_modules", "__pycache__", "logs", "run"}
ARCHIVE_SUFFIXES = (".gz", ".zip", ".tar", ".tgz", ".tar.gz")


def blocked(path: Path) -> bool:
    return bool(set(path.parts) & SKIP_NAMES)


def row_count(raw: bytes) -> int:
    return sum(1 for line in raw.decode("utf-8", errors="replace").splitlines() if line.strip())


def record(source: str, member: str, raw: bytes) -> dict[str, object]:
    digest = hashlib.sha256(raw).hexdigest()
    rows = row_count(raw)
    return {
        "source": source,
        "member": member,
        "size_bytes": len(raw),
        "sha256": digest,
        "row_count": rows,
        "exact_sha_match": digest == EXPECTED_SHA,
        "row_count_match": rows == EXPECTED_ROWS,
    }


def inspect_archive(path: Path) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    name = path.name.lower()
    try:
        if name.endswith(".jsonl.gz") or name.endswith(".gz"):
            raw = gzip.decompress(path.read_bytes())
            out.append(record(str(path), path.name.removesuffix(".gz"), raw))
        elif name.endswith(".zip"):
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if info.filename.endswith(".jsonl"):
                        out.append(record(str(path), info.filename, archive.read(info)))
        elif name.endswith((".tar", ".tgz", ".tar.gz")):
            with tarfile.open(path) as archive:
                for member in archive.getmembers():
                    if member.isfile() and member.name.endswith(".jsonl"):
                        stream = archive.extractfile(member)
                        if stream:
                            out.append(record(str(path), member.name, stream.read()))
    except Exception as exc:
        out.append({"source": str(path), "member": "", "error": type(exc).__name__})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--output", default="reports/hz23_lkg_archive_locator_latest.json")
    args = parser.parse_args()
    repo = Path.cwd()
    roots = [Path(value).expanduser().resolve() for value in args.root] or [Path.home().resolve()]
    scanned = 0
    findings: list[dict[str, object]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or blocked(path):
                continue
            lower = path.name.lower()
            if not lower.endswith(ARCHIVE_SUFFIXES):
                continue
            scanned += 1
            for item in inspect_archive(path):
                if item.get("exact_sha_match") or item.get("row_count_match") or item.get("error"):
                    findings.append(item)
    exact = [item for item in findings if item.get("exact_sha_match")]
    payload = {
        "schema_version": "hz23-lkg-archive-locator/v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "read_only": True,
        "expected": {"sha256": EXPECTED_SHA, "row_count": EXPECTED_ROWS},
        "roots": [str(root) for root in roots],
        "scanned_archive_count": scanned,
        "match_count": len(findings),
        "exact_match_count": len(exact),
        "status": "FOUND_EXACT" if exact else "NOT_FOUND_EXACT",
        "matches": findings[:200],
    }
    output = repo / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("STATUS=" + payload["status"])
    print("SCANNED_ARCHIVE_COUNT=" + str(scanned))
    print("MATCH_COUNT=" + str(len(findings)))
    print("EXACT_MATCH_COUNT=" + str(len(exact)))
    print("REPORT=" + str(output.relative_to(repo)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
