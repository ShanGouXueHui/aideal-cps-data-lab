from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.contracts import canonical_payload_hash
from aideal_cps_data_lab.domain import CommissionProduct, ProductValidationError

EXPECTED_FEED_SCHEMA = "aideal-cps-product-feed/v1"
EXPECTED_MANIFEST_SCHEMA = "aideal-cps-product-feed-manifest/v1"


@dataclass(frozen=True, slots=True)
class CandidateValidationReport:
    candidate_path: str
    manifest_path: str
    file_sha256: str
    row_count: int
    unique_sku_count: int
    duplicate_sku_count: int
    invalid_row_count: int
    payload_hash_mismatch_count: int
    errors: dict[str, int] = field(default_factory=dict)
    samples: tuple[dict[str, Any], ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "candidate_path": self.candidate_path,
            "manifest_path": self.manifest_path,
            "file_sha256": self.file_sha256,
            "row_count": self.row_count,
            "unique_sku_count": self.unique_sku_count,
            "duplicate_sku_count": self.duplicate_sku_count,
            "invalid_row_count": self.invalid_row_count,
            "payload_hash_mismatch_count": self.payload_hash_mismatch_count,
            "errors": dict(sorted(self.errors.items())),
            "samples": list(self.samples),
        }


def _add_error(errors: dict[str, int], reason: str, count: int = 1) -> None:
    errors[reason] = errors.get(reason, 0) + count


def validate_candidate(
    candidate_path: Path,
    manifest_path: Path,
    *,
    max_samples: int = 20,
) -> CandidateValidationReport:
    errors: dict[str, int] = {}
    samples: list[dict[str, Any]] = []

    if not candidate_path.exists():
        _add_error(errors, "candidate_missing")
        return CandidateValidationReport(
            str(candidate_path), str(manifest_path), "", 0, 0, 0, 0, 0, errors, tuple(samples)
        )
    if not manifest_path.exists():
        _add_error(errors, "manifest_missing")
        return CandidateValidationReport(
            str(candidate_path), str(manifest_path), "", 0, 0, 0, 0, 0, errors, tuple(samples)
        )

    raw = candidate_path.read_bytes()
    file_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        manifest = {}
        _add_error(errors, "manifest_invalid_json")
    if not isinstance(manifest, dict):
        manifest = {}
        _add_error(errors, "manifest_not_object")

    if manifest.get("schema_version") != EXPECTED_MANIFEST_SCHEMA:
        _add_error(errors, "manifest_schema_mismatch")
    if manifest.get("feed_schema_version") != EXPECTED_FEED_SCHEMA:
        _add_error(errors, "manifest_feed_schema_mismatch")
    if manifest.get("feed_status") != "candidate":
        _add_error(errors, "manifest_feed_status_invalid")
    if manifest.get("commercial_enabled") is not False:
        _add_error(errors, "commercial_switch_not_false")
    if manifest.get("data_sha256") != file_sha256:
        _add_error(errors, "file_checksum_mismatch")
    if not str(manifest.get("round_id") or "").strip():
        _add_error(errors, "manifest_round_id_missing")

    rows: list[dict[str, Any]] = []
    invalid_row_count = 0
    payload_hash_mismatch_count = 0
    for line_no, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            _add_error(errors, "blank_line")
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            invalid_row_count += 1
            _add_error(errors, "row_invalid_json")
            if len(samples) < max_samples:
                samples.append({"line": line_no, "reason": "row_invalid_json"})
            continue
        if not isinstance(value, dict):
            invalid_row_count += 1
            _add_error(errors, "row_not_object")
            if len(samples) < max_samples:
                samples.append({"line": line_no, "reason": "row_not_object"})
            continue

        sku = str(value.get("sku") or value.get("jd_sku_id") or "")
        if value.get("schema_version") != EXPECTED_FEED_SCHEMA:
            invalid_row_count += 1
            _add_error(errors, "row_schema_mismatch")
            if len(samples) < max_samples:
                samples.append({"line": line_no, "sku": sku, "reason": "row_schema_mismatch"})

        try:
            product = CommissionProduct.from_candidate_row(value)
        except ProductValidationError as exc:
            invalid_row_count += 1
            reason = f"row_{str(exc) or 'validation_error'}"
            _add_error(errors, reason)
            if len(samples) < max_samples:
                samples.append({"line": line_no, "sku": sku, "reason": reason})
            continue

        expected_hash = canonical_payload_hash(value)
        if value.get("source_payload_hash") != expected_hash:
            payload_hash_mismatch_count += 1
            _add_error(errors, "payload_hash_mismatch")
            if len(samples) < max_samples:
                samples.append(
                    {
                        "line": line_no,
                        "sku": product.jd_sku_id,
                        "reason": "payload_hash_mismatch",
                    }
                )
        if product.source_payload_hash() != expected_hash:
            _add_error(errors, "domain_hash_contract_mismatch")
        if not str(value.get("source_round_id") or "").strip():
            _add_error(errors, "source_round_id_missing")
            if len(samples) < max_samples:
                samples.append(
                    {
                        "line": line_no,
                        "sku": product.jd_sku_id,
                        "reason": "source_round_id_missing",
                    }
                )
        if value.get("status") != "active":
            _add_error(errors, "row_status_not_active")
        rows.append(value)

    skus = [str(row.get("sku") or row.get("jd_sku_id") or "") for row in rows]
    unique_sku_count = len(set(skus))
    duplicate_sku_count = len(skus) - unique_sku_count
    if duplicate_sku_count:
        _add_error(errors, "duplicate_sku", duplicate_sku_count)
    if skus != sorted(skus):
        _add_error(errors, "sku_order_invalid")

    row_count = len(rows)
    expected_counts = {
        "row_count": row_count,
        "eligible_sku_count": row_count,
        "duplicate_sku_count": duplicate_sku_count,
    }
    for field_name, expected in expected_counts.items():
        try:
            actual = int(manifest.get(field_name))
        except (TypeError, ValueError):
            actual = -1
        if actual != expected:
            _add_error(errors, f"manifest_{field_name}_mismatch")

    rejected = manifest.get("rejected") or {}
    if int(rejected.get("unsafe_hz20") or 0) != 0:
        _add_error(errors, "manifest_unsafe_hz20_nonzero")
    if int(rejected.get("untrusted_promotion_url") or 0) != 0:
        _add_error(errors, "manifest_untrusted_promotion_url_nonzero")

    return CandidateValidationReport(
        candidate_path=str(candidate_path),
        manifest_path=str(manifest_path),
        file_sha256=file_sha256,
        row_count=row_count,
        unique_sku_count=unique_sku_count,
        duplicate_sku_count=duplicate_sku_count,
        invalid_row_count=invalid_row_count,
        payload_hash_mismatch_count=payload_hash_mismatch_count,
        errors=errors,
        samples=tuple(samples),
    )
