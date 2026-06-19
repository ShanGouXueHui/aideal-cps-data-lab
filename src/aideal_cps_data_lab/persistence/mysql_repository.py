from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.domain import CommissionProduct
from aideal_cps_data_lab.persistence.repository import UpsertOutcome

from .mysql_columns import BUSINESS_COLUMNS, business_values
from .mysql_metrics import count_duplicates, count_products

ConnectionFactory = Callable[[], Any]

SELECT_ONE = f"""
SELECT jd_sku_id, source_payload_hash, {', '.join(BUSINESS_COLUMNS)}
FROM commission_products
WHERE jd_sku_id = %s
FOR UPDATE
"""

INSERT_ONE = f"""
INSERT INTO commission_products (
  jd_sku_id, {', '.join(BUSINESS_COLUMNS)}, is_published, missing_rounds,
  source_page_no, source_round_id, source_run_id, source_payload_hash,
  catalog_change_count, first_seen_at, last_checked_at, last_seen_at
) VALUES (
  %s, {', '.join(['%s'] * len(BUSINESS_COLUMNS))}, 0, 0,
  %s, %s, %s, %s,
  %s, %s, %s, %s
)
"""

UPDATE_CHANGED = f"""
UPDATE commission_products
SET {', '.join(f'{column}=%s' for column in BUSINESS_COLUMNS)},
    source_page_no=%s,
    source_round_id=%s,
    source_run_id=%s,
    source_payload_hash=%s,
    catalog_change_count=catalog_change_count+1,
    last_checked_at=%s,
    last_seen_at=%s
WHERE jd_sku_id=%s
"""

UPDATE_UNCHANGED = """
UPDATE commission_products
SET source_page_no=%s,
    source_round_id=%s,
    source_run_id=%s,
    last_checked_at=%s,
    last_seen_at=%s
WHERE jd_sku_id=%s
"""

INSERT_HISTORY = """
INSERT INTO commission_product_history (
  jd_sku_id, round_id, change_type, before_payload, after_payload,
  before_hash, after_hash, changed_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""


class MySQLCommissionProductRepository:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        settings: DataLabSettings,
    ) -> None:
        self._connection_factory = connection_factory
        self._settings = settings

    def upsert_many(
        self,
        products: Iterable[CommissionProduct],
        *,
        round_id: str,
        run_id: str,
    ) -> UpsertOutcome:
        self._settings.assert_write_allowed()
        rows = list(products)
        self._require_unique(rows)
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            connection.begin()
            for product in rows:
                outcome = self._upsert_one(cursor, product, round_id, run_id)
                counts[outcome] += 1
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()
        return UpsertOutcome(**counts)

    def _upsert_one(
        self,
        cursor: Any,
        product: CommissionProduct,
        round_id: str,
        run_id: str,
    ) -> str:
        cursor.execute(SELECT_ONE, (product.jd_sku_id,))
        existing = cursor.fetchone()
        now = datetime.now()
        checked_at = product.last_checked_at or now
        seen_at = product.last_seen_at or checked_at
        payload_hash = product.source_payload_hash()
        values = business_values(product.business_payload())
        if existing is None:
            self._insert(
                cursor, product, values, round_id, run_id, payload_hash, checked_at, seen_at
            )
            return "inserted"
        if existing.get("source_payload_hash") == payload_hash:
            self._touch(cursor, product, round_id, run_id, checked_at, seen_at)
            return "unchanged"
        self._update_changed(
            cursor,
            existing,
            product,
            values,
            round_id,
            run_id,
            payload_hash,
            checked_at,
            seen_at,
            now,
        )
        return "updated"

    @staticmethod
    def _insert(
        cursor: Any,
        product: CommissionProduct,
        values: tuple[Any, ...],
        round_id: str,
        run_id: str,
        payload_hash: str,
        checked_at: datetime,
        seen_at: datetime,
    ) -> None:
        cursor.execute(
            INSERT_ONE,
            (
                product.jd_sku_id,
                *values,
                product.source_page_no,
                round_id,
                run_id,
                payload_hash,
                product.catalog_change_count,
                product.first_seen_at or seen_at,
                checked_at,
                seen_at,
            ),
        )

    @staticmethod
    def _touch(
        cursor: Any,
        product: CommissionProduct,
        round_id: str,
        run_id: str,
        checked_at: datetime,
        seen_at: datetime,
    ) -> None:
        cursor.execute(
            UPDATE_UNCHANGED,
            (
                product.source_page_no,
                round_id,
                run_id,
                checked_at,
                seen_at,
                product.jd_sku_id,
            ),
        )

    @staticmethod
    def _update_changed(
        cursor: Any,
        existing: dict[str, Any],
        product: CommissionProduct,
        values: tuple[Any, ...],
        round_id: str,
        run_id: str,
        payload_hash: str,
        checked_at: datetime,
        seen_at: datetime,
        changed_at: datetime,
    ) -> None:
        cursor.execute(
            UPDATE_CHANGED,
            (
                *values,
                product.source_page_no,
                round_id,
                run_id,
                payload_hash,
                checked_at,
                seen_at,
                product.jd_sku_id,
            ),
        )
        before = {column: existing.get(column) for column in BUSINESS_COLUMNS}
        cursor.execute(
            INSERT_HISTORY,
            (
                product.jd_sku_id,
                round_id,
                "update",
                json.dumps(before, ensure_ascii=False, default=str, sort_keys=True),
                json.dumps(
                    product.business_payload(),
                    ensure_ascii=False,
                    default=str,
                    sort_keys=True,
                ),
                existing.get("source_payload_hash"),
                payload_hash,
                changed_at,
            ),
        )

    def count_by_sku(self) -> int:
        return count_products(self._connection_factory)

    def duplicate_sku_count(self) -> int:
        return count_duplicates(self._connection_factory)

    @staticmethod
    def _require_unique(rows: list[CommissionProduct]) -> None:
        skus = [row.jd_sku_id for row in rows]
        if len(skus) != len(set(skus)):
            raise ValueError("duplicate SKU in upsert batch")
