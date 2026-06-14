from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable

from aideal_cps_data_lab.domain import CommissionProduct


@dataclass(frozen=True, slots=True)
class UpsertOutcome:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0

    @property
    def accepted(self) -> int:
        return self.inserted + self.updated + self.unchanged


@runtime_checkable
class CommissionProductRepository(Protocol):
    """Persistence boundary shared by JSONL and MySQL implementations."""

    def upsert_many(
        self,
        products: Iterable[CommissionProduct],
        *,
        round_id: str,
        run_id: str,
    ) -> UpsertOutcome:
        """Atomically upsert one validated batch and return deterministic counters."""

    def count_by_sku(self) -> int:
        """Return the number of unique persisted SKU rows."""

    def duplicate_sku_count(self) -> int:
        """Return zero when the unique business-key invariant holds."""
