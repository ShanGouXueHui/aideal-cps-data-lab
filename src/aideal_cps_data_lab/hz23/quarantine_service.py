from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .safety import unsafe_source_reason

DEFAULT_SOURCE = Path("data/import/hz_jd_union_all_product_full_links_latest.jsonl")
FALLBACK_SOURCE = Path("data/import/hz_jd_union_product_all_full_links_latest.jsonl")
REPORT = Path("reports/hz23_hz20_quarantine_latest.json")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _write_report(payload: dict[str, Any]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix(REPORT.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(REPORT)


def _scan(
    original: bytes,
) -> tuple[list[bytes], list[dict[str, Any]], list[int], dict[str, int]]:
    safe_lines: list[bytes] = []
    unsafe_rows: list[dict[str, Any]] = []
    invalid_lines: list[int] = []
    reason_counts: dict[str, int] = {}
    for line_no, raw_line in enumerate(original.splitlines(keepends=True), start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line.decode("utf-8"))
        except Exception:
            invalid_lines.append(line_no)
            continue
        if not isinstance(row, dict):
            invalid_lines.append(line_no)
            continue
        reason = unsafe_source_reason(row)
        if not reason:
            safe_lines.append(
                raw_line if raw_line.endswith(b"\n") else raw_line + b"\n"
            )
            continue
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        unsafe_rows.append(
            {
                "line_no": line_no,
                "reason": reason,
                "sku": str(row.get("sku") or row.get("jd_sku_id") or ""),
                "worker_name": row.get("worker_name"),
                "menu_mode": row.get("menu_mode"),
                "promotion_mode": row.get("promotion_mode"),
                "row": row,
            }
        )
    return safe_lines, unsafe_rows, invalid_lines, reason_counts


def _paths(source: Path) -> tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(
        f"data/history/{source.name}.{timestamp}.before_hz20_quarantine.bak"
    )
    quarantine = Path(f"data/history/hz20_unsafe_quarantine_{timestamp}.jsonl")
    return backup, quarantine


def _payload(
    source: Path,
    original: bytes,
    cleaned: bytes,
    safe_lines: list[bytes],
    unsafe_rows: list[dict[str, Any]],
    invalid_lines: list[int],
    reason_counts: dict[str, int],
    execute: bool,
    backup: Path,
    quarantine: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "aideal-hz23-hz20-quarantine/v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "execute" if execute else "dry_run",
        "source": str(source),
        "source_sha256_before": _digest(original),
        "source_sha256_after": _digest(cleaned),
        "source_line_count_before": len(original.splitlines()),
        "safe_line_count": len(safe_lines),
        "unsafe_row_count": len(unsafe_rows),
        "invalid_line_count": len(invalid_lines),
        "invalid_lines": invalid_lines[:20],
        "reason_counts": reason_counts,
        "unsafe_sku_samples": [row["sku"] for row in unsafe_rows[:20]],
        "backup": str(backup),
        "quarantine": str(quarantine),
        "executed": False,
    }


def _execute(
    source: Path,
    original: bytes,
    cleaned: bytes,
    unsafe_rows: list[dict[str, Any]],
    payload: dict[str, Any],
    backup: Path,
    quarantine: Path,
) -> None:
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(original)
    quarantine.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in unsafe_rows
        ),
        encoding="utf-8",
    )
    _atomic_write(source, cleaned)
    payload["executed"] = True
    payload["backup_exists"] = backup.exists()
    payload["quarantine_exists"] = quarantine.exists()
    payload["source_sha256_verified"] = _digest(source.read_bytes()) == payload[
        "source_sha256_after"
    ]
    payload["ok"] = bool(
        payload["backup_exists"]
        and payload["quarantine_exists"]
        and payload["source_sha256_verified"]
    )


def run(source: Path, execute: bool) -> int:
    if not source.exists():
        result = {"ok": False, "error": "source_missing", "source": str(source)}
        _write_report(result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2
    original = source.read_bytes()
    safe_lines, unsafe_rows, invalid_lines, reason_counts = _scan(original)
    cleaned = b"".join(safe_lines)
    backup, quarantine = _paths(source)
    result = _payload(
        source,
        original,
        cleaned,
        safe_lines,
        unsafe_rows,
        invalid_lines,
        reason_counts,
        execute,
        backup,
        quarantine,
    )
    if invalid_lines:
        result.update(ok=False, error="invalid_source_jsonl")
    elif execute:
        _execute(
            source,
            original,
            cleaned,
            unsafe_rows,
            result,
            backup,
            quarantine,
        )
    else:
        result["ok"] = True
    _write_report(result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    source = args.source or (
        DEFAULT_SOURCE if DEFAULT_SOURCE.exists() else FALLBACK_SOURCE
    )
    return run(source, args.execute)
