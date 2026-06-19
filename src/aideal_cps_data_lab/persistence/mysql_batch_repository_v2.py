from __future__ import annotations

from typing import Any

from aideal_cps_data_lab.domain import CommissionProduct
from aideal_cps_data_lab.persistence.mysql_batch_repository import (
    CREATE_STAGE,
    INSERT_STAGE,
    BatchMySQLCommissionProductRepository,
)
from aideal_cps_data_lab.persistence.mysql_columns import stage_values

CLEAR_STAGE = "DELETE FROM tmp_commission_products_stage"


class TransactionSafeBatchMySQLCommissionProductRepository(
    BatchMySQLCommissionProductRepository
):
    """Staging repository that clears rows without implicit transaction commit."""

    def _load_stage(
        self,
        cursor: Any,
        rows: list[CommissionProduct],
        round_id: str,
        run_id: str,
    ) -> None:
        cursor.execute(CREATE_STAGE)
        cursor.execute(CLEAR_STAGE)
        values = [stage_values(product, round_id, run_id) for product in rows]
        self._executemany(cursor, INSERT_STAGE, values)
