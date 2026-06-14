from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.domain import CommissionProduct, ProductValidationError


@dataclass(frozen=True, slots=True)
class BackfillPlan:
    source_path: str
    source_sha256: str
    total_lines: int
    parsed_rows: int
    unique_products: tuple[CommissionProduct, ...]
    duplicate_sku_count: int
    rejected: dict[str, int] = field(default_factory=dict)

    @property
    def valid_unique_count(self) -> int:
        return len(self.unique_products)

    def summary(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "total_lines": self.total_lines,
            "parsed_rows": self.parsed_rows,
            "valid_unique_count": self.valid_unique_count,
            "duplicate_sku_count": self.duplicate_sku_count,
            "rejected": dict(sorted(self.rejected.items())),
            "ready_for_write": self.valid_unique_count > 0 and self.duplicate_sku_count == 0,
        }


def build_backfill_plan(path: Path) -> BackfillPlan:
    raw = path.read_bytes()
    source_sha256 = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()

    parsed_rows = 0
    duplicate_sku_count = 0
    rejected: dict[str, int] = {}
    products: dict[str, CommissionProduct] = {}

    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            rejected["invalid_json"] = rejected.get("invalid_json", 0) + 1
            continue
        if not isinstance(value, dict):
            rejected["not_object"] = rejected.get("not_object", 0) + 1
            continue

        parsed_rows += 1
        try:
            product = CommissionProduct.from_candidate_row(value)
        except ProductValidationError as exc:
            reason = str(exc) or "validation_error"
            rejected[reason] = rejected.get(reason, 0) + 1
            continue

        if product.jd_sku_id in products:
            duplicate_sku_count += 1
            continue
        products[product.jd_sku_id] = product

    ordered = tuple(products[sku] for sku in sorted(products))
    return BackfillPlan(
        source_path=str(path),
        source_sha256=source_sha256,
        total_lines=len(lines),
        parsed_rows=parsed_rows,
        unique_products=ordered,
        duplicate_sku_count=duplicate_sku_count,
        rejected=rejected,
    )
