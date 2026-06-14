from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.domain import CommissionProduct
from aideal_cps_data_lab.persistence.repository import UpsertOutcome

ConnectionFactory = Callable[[], Any]

BUSINESS_COLUMNS = (
    "title",
    "description",
    "item_url",
    "promotion_url",
    "short_url",
    "long_url",
    "qr_url",
    "jd_command",
    "image_url",
    "category_name",
    "shop_name",
    "price",
    "coupon_price",
    "commission_rate",
    "estimated_commission",
    "sales_volume",
    "coupon_info",
    "status",
    "link_created_at",
    "link_expire_at",
    "refresh_due_at",
)

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
    def __init__(self, connection_factory: ConnectionFactory, settings: DataLabSettings) -> None:
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
        skus = [row.jd_sku_id for row in rows]
        if len(skus) != len(set(skus)):
            raise ValueError("duplicate SKU in upsert batch")

        inserted = updated = unchanged = 0
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            connection.begin()
            for product in rows:
                cursor.execute(SELECT_ONE, (product.jd_sku_id,))
                existing = cursor.fetchone()
                now = datetime.now()
                checked_at = product.last_checked_at or now
                seen_at = product.last_seen_at or checked_at
                payload_hash = product.source_payload_hash()
                business_values = self._business_values(product)

                if existing is None:
                    cursor.execute(
                        INSERT_ONE,
                        (
                            product.jd_sku_id,
                            *business_values,
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
                    inserted += 1
                    continue

                if existing.get("source_payload_hash") == payload_hash:
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
                    unchanged += 1
                    continue

                cursor.execute(
                    UPDATE_CHANGED,
                    (
                        *business_values,
                        product.source_page_no,
                        round_id,
                        run_id,
                        payload_hash,
                        checked_at,
                        seen_at,
                        product.jd_sku_id,
                    ),
                )
                cursor.execute(
                    INSERT_HISTORY,
                    (
                        product.jd_sku_id,
                        round_id,
                        "update",
                        json.dumps(
                            self._existing_business_payload(existing),
                            ensure_ascii=False,
                            default=str,
                            sort_keys=True,
                        ),
                        json.dumps(
                            product.business_payload(),
                            ensure_ascii=False,
                            default=str,
                            sort_keys=True,
                        ),
                        existing.get("source_payload_hash"),
                        payload_hash,
                        now,
                    ),
                )
                updated += 1

            connection.commit()
            return UpsertOutcome(inserted=inserted, updated=updated, unchanged=unchanged)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def count_by_sku(self) -> int:
        return self._scalar("SELECT COUNT(*) AS value FROM commission_products")

    def duplicate_sku_count(self) -> int:
        return self._scalar(
            "SELECT COUNT(*) AS value FROM ("
            "SELECT jd_sku_id FROM commission_products GROUP BY jd_sku_id HAVING COUNT(*) > 1"
            ") AS duplicate_rows"
        )

    def _scalar(self, sql: str) -> int:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            row = cursor.fetchone() or {}
            return int(row.get("value") or 0)
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def _business_values(product: CommissionProduct) -> tuple[Any, ...]:
        payload = product.business_payload()
        return tuple(payload.get(column) for column in BUSINESS_COLUMNS)

    @staticmethod
    def _existing_business_payload(existing: dict[str, Any]) -> dict[str, Any]:
        return {column: existing.get(column) for column in BUSINESS_COLUMNS}
