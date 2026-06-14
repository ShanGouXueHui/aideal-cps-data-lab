from __future__ import annotations

import re
from typing import Any, Iterable

from aideal_cps_data_lab.contracts import canonical_payload_hash


def validate_landed_rows(
    rows: Iterable[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    landed = list(rows)
    mismatch_count = 0
    invalid_format_count = 0
    mismatch_samples: list[str] = []
    round_ids: set[str] = set()

    for row in landed:
        actual = str(row.get("source_payload_hash") or "")
        expected = canonical_payload_hash(row)
        if not re.fullmatch(r"[0-9a-f]{64}", actual):
            invalid_format_count += 1
        if actual != expected:
            mismatch_count += 1
            if len(mismatch_samples) < 20:
                mismatch_samples.append(str(row.get("jd_sku_id") or ""))
        if row.get("source_round_id"):
            round_ids.add(str(row.get("source_round_id")))

    manifest_rows = int(manifest.get("row_count") or 0) if manifest else None
    manifest_round = str(manifest.get("round_id") or "") if manifest else ""
    checks = {
        "manifest_present": bool(manifest),
        "row_count_matches_manifest": (
            manifest_rows is not None and len(landed) == manifest_rows
        ),
        "round_id_matches_manifest": bool(
            manifest_round and round_ids == {manifest_round}
        ),
        "hash_format_valid": invalid_format_count == 0,
        "payload_hashes_match": mismatch_count == 0,
    }
    return {
        "ok": all(checks.values()),
        "database_row_count": len(landed),
        "manifest_row_count": manifest_rows,
        "database_round_ids": sorted(round_ids),
        "manifest_round_id": manifest_round or None,
        "invalid_hash_format_count": invalid_format_count,
        "payload_hash_mismatch_count": mismatch_count,
        "payload_hash_mismatch_samples": mismatch_samples,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
    }
