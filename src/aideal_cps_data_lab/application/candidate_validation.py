from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.contracts import canonical_payload_hash
from aideal_cps_data_lab.domain import CommissionProduct, ProductValidationError

expected_feed_schema = "aideal-cps-product-feed/v1"
expected_manifest_schema = "aideal-cps-product-feed-manifest/v1"


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


def _empty_report(
    candidate_path: Path,
    manifest_path: Path,
    errors: dict[str, int],
) -> CandidateValidationReport:
    return CandidateValidationReport(
        str(candidate_path), str(manifest_path), "", 0, 0, 0, 0, 0, errors, ()
    )


def _read_manifest(path: Path, errors: dict[str, int]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _add_error(errors, "manifest_invalid_json")
        return {}
    if not isinstance(value, dict):
        _add_error(errors, "manifest_not_object")
        return {}
    return value


def _validate_manifest(
    manifest: dict[str, Any],
    file_sha256: str,
    errors: dict[str, int],
) -> None:
    checks = {
        "manifest_schema_mismatch": (
            manifest.get("schema_version") == expected_manifest_schema
        ),
        "manifest_feed_schema_mismatch": (
            manifest.get("feed_schema_version") == expected_feed_schema
        ),
        "manifest_feed_status_invalid": manifest.get("feed_status") == "candidate",
        "commercial_switch_not_false": manifest.get("commercial_enabled") is False,
        "file_checksum_mismatch": manifest.get("data_sha256") == file_sha256,
        "manifest_round_id_missing": bool(
            str(manifest.get("round_id") or "").strip()
        ),
    }
    for reason, passed in checks.items():
        if not passed:
            _add_error(errors, reason)


def _sample(
    samples: list[dict[str, Any]],
    max_samples: int,
    line_no: int,
    reason: str,
    sku: str = "",
) -> None:
    if len(samples) >= max_samples:
        return
    value: dict[str, Any] = {"line": line_no, "reason": reason}
    if sku:
        value["sku"] = sku
    samples.append(value)


def _validate_domain_row(
    value: dict[str, Any],
    line_no: int,
    errors: dict[str, int],
    samples: list[dict[str, Any]],
    max_samples: int,
) -> tuple[CommissionProduct | None, int, int]:
    sku = str(value.get("sku") or value.get("jd_sku_id") or "")
    invalid_increment = 0
    if value.get("schema_version") != expected_feed_schema:
        invalid_increment += 1
        _add_error(errors, "row_schema_mismatch")
        _sample(samples, max_samples, line_no, "row_schema_mismatch", sku)
    try:
        product = CommissionProduct.from_candidate_row(value)
    except ProductValidationError as error:
        reason = f"row_{str(error) or 'validation_error'}"
        _add_error(errors, reason)
        _sample(samples, max_samples, line_no, reason, sku)
        return None, invalid_increment + 1, 0
    hash_mismatch = _validate_hashes(value, product, line_no, errors, samples, max_samples)
    _validate_lineage(value, product, line_no, errors, samples, max_samples)
    return product, invalid_increment, hash_mismatch


def _validate_hashes(
    value: dict[str, Any],
    product: CommissionProduct,
    line_no: int,
    errors: dict[str, int],
    samples: list[dict[str, Any]],
    max_samples: int,
) -> int:
    expected_hash = canonical_payload_hash(value)
    mismatch = int(value.get("source_payload_hash") != expected_hash)
    if mismatch:
        _add_error(errors, "payload_hash_mismatch")
        _sample(
            samples,
            max_samples,
            line_no,
            "payload_hash_mismatch",
            product.jd_sku_id,
        )
    if product.source_payload_hash() != expected_hash:
        _add_error(errors, "domain_hash_contract_mismatch")
    return mismatch


def _validate_lineage(
    value: dict[str, Any],
    product: CommissionProduct,
    line_no: int,
    errors: dict[str, int],
    samples: list[dict[str, Any]],
    max_samples: int,
) -> None:
    if not str(value.get("source_round_id") or "").strip():
        _add_error(errors, "source_round_id_missing")
        _sample(
            samples,
            max_samples,
            line_no,
            "source_round_id_missing",
            product.jd_sku_id,
        )
    if value.get("status") != "active":
        _add_error(errors, "row_status_not_active")


def _validate_rows(
    raw: bytes,
    errors: dict[str, int],
    samples: list[dict[str, Any]],
    max_samples: int,
) -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    invalid_count = 0
    hash_mismatch_count = 0
    for line_no, line in enumerate(
        raw.decode("utf-8", errors="replace").splitlines(), start=1
    ):
        if not line.strip():
            _add_error(errors, "blank_line")
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            invalid_count += 1
            _add_error(errors, "row_invalid_json")
            _sample(samples, max_samples, line_no, "row_invalid_json")
            continue
        if not isinstance(value, dict):
            invalid_count += 1
            _add_error(errors, "row_not_object")
            _sample(samples, max_samples, line_no, "row_not_object")
            continue
        product, invalid_increment, hash_mismatch = _validate_domain_row(
            value, line_no, errors, samples, max_samples
        )
        invalid_count += invalid_increment
        hash_mismatch_count += hash_mismatch
        if product is not None:
            rows.append(value)
    return rows, invalid_count, hash_mismatch_count


def _validate_counts(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    errors: dict[str, int],
) -> tuple[int, int]:
    skus = [str(row.get("sku") or row.get("jd_sku_id") or "") for row in rows]
    unique_count = len(set(skus))
    duplicate_count = len(skus) - unique_count
    if duplicate_count:
        _add_error(errors, "duplicate_sku", duplicate_count)
    if skus != sorted(skus):
        _add_error(errors, "sku_order_invalid")
    expected = {
        "row_count": len(rows),
        "eligible_sku_count": len(rows),
        "duplicate_sku_count": duplicate_count,
    }
    for field_name, expected_value in expected.items():
        try:
            actual = int(manifest.get(field_name))
        except (TypeError, ValueError):
            actual = -1
        if actual != expected_value:
            _add_error(errors, f"manifest_{field_name}_mismatch")
    return unique_count, duplicate_count


def _validate_rejected(manifest: dict[str, Any], errors: dict[str, int]) -> None:
    rejected = manifest.get("rejected") or {}
    if int(rejected.get("unsafe_hz20") or 0) != 0:
        _add_error(errors, "manifest_unsafe_hz20_nonzero")
    if int(rejected.get("untrusted_promotion_url") or 0) != 0:
        _add_error(errors, "manifest_untrusted_promotion_url_nonzero")


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
        return _empty_report(candidate_path, manifest_path, errors)
    if not manifest_path.exists():
        _add_error(errors, "manifest_missing")
        return _empty_report(candidate_path, manifest_path, errors)
    raw = candidate_path.read_bytes()
    file_sha256 = hashlib.sha256(raw).hexdigest()
    manifest = _read_manifest(manifest_path, errors)
    _validate_manifest(manifest, file_sha256, errors)
    rows, invalid_count, mismatch_count = _validate_rows(
        raw, errors, samples, max_samples
    )
    unique_count, duplicate_count = _validate_counts(rows, manifest, errors)
    _validate_rejected(manifest, errors)
    return CandidateValidationReport(
        candidate_path=str(candidate_path),
        manifest_path=str(manifest_path),
        file_sha256=file_sha256,
        row_count=len(rows),
        unique_sku_count=unique_count,
        duplicate_sku_count=duplicate_count,
        invalid_row_count=invalid_count,
        payload_hash_mismatch_count=mismatch_count,
        errors=errors,
        samples=tuple(samples),
    )
