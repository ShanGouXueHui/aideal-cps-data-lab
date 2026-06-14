from __future__ import annotations

from collections.abc import Iterable

from aideal_cps_data_lab.domain import CommissionProduct
from aideal_cps_data_lab.persistence.mysql_batch_repository import (
    COUNT_DIFFS,
    CREATE_STAGE,
    INSERT_HISTORY,
    INSERT_NEW,
    INSERT_STAGE,
    SELECT_CHANGED_FOR_HISTORY,
    UPDATE_CHANGED,
    UPDATE_UNCHANGED,
    BatchMySQLCommissionProductRepository,
)
from aideal_cps_data_lab.persistence.repository import UpsertOutcome

CLEAR_STAGE = "DELETE FROM tmp_commission_products_stage"


class TransactionSafeBatchMySQLCommissionProductRepository(
    BatchMySQLCommissionProductRepository
):
    """Staging-table repository that keeps the clear operation inside the transaction."""

    def upsert_many(
        self,
        products: Iterable[CommissionProduct],
        *,
        round_id: str,
        run_id: str,
    ) -> UpsertOutcome:
        self._settings.assert_write_allowed()
        rows = list(products)
        if not rows:
            return UpsertOutcome()

        skus = [row.jd_sku_id for row in rows]
        if len(skus) != len(set(skus)):
            raise ValueError("duplicate SKU in upsert batch")

        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            connection.begin()
            cursor.execute(CREATE_STAGE)
            cursor.execute(CLEAR_STAGE)

            stage_values = [self._stage_values(product, round_id, run_id) for product in rows]
            for offset in range(0, len(stage_values), self._batch_size):
                cursor.executemany(
                    INSERT_STAGE,
                    stage_values[offset : offset + self._batch_size],
                )

            cursor.execute(COUNT_DIFFS)
            counts = cursor.fetchone() or {}
            inserted = int(counts.get("inserted_count") or 0)
            updated = int(counts.get("updated_count") or 0)
            unchanged = int(counts.get("unchanged_count") or 0)
            published_changed = int(counts.get("published_changed_count") or 0)

            if inserted + updated + unchanged != len(rows):
                raise RuntimeError("staging comparison count mismatch")
            if published_changed:
                raise RuntimeError(
                    f"published_product_change_requires_publish_workflow:{published_changed}"
                )

            cursor.execute(SELECT_CHANGED_FOR_HISTORY)
            changed_rows = list(cursor.fetchall())
            if len(changed_rows) != updated:
                raise RuntimeError("changed history count mismatch")
            if changed_rows:
                history_values = [self._history_values(row, round_id) for row in changed_rows]
                for offset in range(0, len(history_values), self._batch_size):
                    cursor.executemany(
                        INSERT_HISTORY,
                        history_values[offset : offset + self._batch_size],
                    )

            cursor.execute(UPDATE_CHANGED)
            if int(cursor.rowcount or 0) != updated:
                raise RuntimeError("changed update rowcount mismatch")

            cursor.execute(UPDATE_UNCHANGED)
            if int(cursor.rowcount or 0) > unchanged:
                raise RuntimeError("unchanged update rowcount exceeds expected count")

            cursor.execute(INSERT_NEW)
            if int(cursor.rowcount or 0) != inserted:
                raise RuntimeError("new insert rowcount mismatch")

            connection.commit()
            return UpsertOutcome(
                inserted=inserted,
                updated=updated,
                unchanged=unchanged,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()
