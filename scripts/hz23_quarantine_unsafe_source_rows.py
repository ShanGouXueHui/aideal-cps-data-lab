#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_SOURCE = Path("data/import/hz_jd_union_all_product_full_links_latest.jsonl")
FALLBACK_SOURCE = Path("data/import/hz_jd_union_product_all_full_links_latest.jsonl")
REPORT = Path("reports/hz23_hz20_quarantine_latest.json")


def unsafe_reason(row: dict[str, Any]) -> str | None:
    worker = str(row.get("worker_name") or "").lower()
    menu_mode = str(row.get("menu_mode") or "").lower()
    promotion_mode = str(row.get("promotion_mode") or "").lower()
    if worker == "hz20_mouse_click":
        return "worker_name_hz20_mouse_click"
    if "hz20" in menu_mode:
        return "menu_mode_contains_hz20"
    if "hz20" in promotion_mode:
        return "promotion_mode_contains_hz20"
    return None


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def save_report(payload: dict[str, Any]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(REPORT.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(REPORT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    source = args.source or (DEFAULT_SOURCE if DEFAULT_SOURCE.exists() else FALLBACK_SOURCE)
    if not source.exists():
        payload = {"ok": False, "error": "source_missing", "source": str(source)}
        save_report(payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    original = source.read_bytes()
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
        reason = unsafe_reason(row)
        if reason:
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
        else:
            safe_lines.append(raw_line if raw_line.endswith(b"\n") else raw_line + b"\n")

    cleaned = b"".join(safe_lines)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(f"data/history/{source.name}.{timestamp}.before_hz20_quarantine.bak")
    quarantine = Path(f"data/history/hz20_unsafe_quarantine_{timestamp}.jsonl")

    payload: dict[str, Any] = {
        "schema_version": "aideal-hz23-hz20-quarantine/v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "execute" if args.execute else "dry_run",
        "source": str(source),
        "source_sha256_before": digest(original),
        "source_sha256_after": digest(cleaned),
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

    if invalid_lines:
        payload.update(ok=False, error="invalid_source_jsonl")
        save_report(payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1

    if args.execute:
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(original)
        quarantine.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in unsafe_rows),
            encoding="utf-8",
        )
        atomic_write(source, cleaned)
        after = source.read_bytes()
        payload["executed"] = True
        payload["backup_exists"] = backup.exists()
        payload["quarantine_exists"] = quarantine.exists()
        payload["source_sha256_verified"] = digest(after) == payload["source_sha256_after"]
        payload["ok"] = bool(
            payload["backup_exists"]
            and payload["quarantine_exists"]
            and payload["source_sha256_verified"]
        )
    else:
        payload["ok"] = True

    save_report(payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
