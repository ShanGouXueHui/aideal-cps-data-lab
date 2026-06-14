from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.domain import CommissionProduct
from aideal_cps_data_lab.persistence.repository import UpsertOutcome

ConnectionFactory = Callable[[], Any]

SELECT_ONE = """
SELECT jd_sku_id, source_payload_hash, title, description, item_url,
       promotion_url, short_url, image_url, price, coupon_price,
       commission_rate, estimated_commission, sales_volume, coupon_info,
       status, link_created_at, link_expire_at, refresh_due_at
FROM commission_products
WHERE jd_sku_id = %s
FOR UPDATE
"""

INSERT_ONE = """
INSERT INTO commission_products (
  jd_sku_id, title, description, item_url, promotion_url, short_url,
  image_url, price, coupon_price, commission_rate, estimated_commission,
  sales_volume, coupon_info, status, is_published, missing_rounds,
  source_page_no, source_round_id, source_run_id, source_payload_hash,
  catalog_change_count, link_created_at, link_expire_at, refresh_due_at,
  first_seen_at, last_checked_at, last_seen_at
) VALUES (
  %s, %s, %s, %s, %s, %s,
  %s, %s, %s, %s, %s,
  %s, %s, %s, 0, 0,
  %s, %s, %s, %s,
  %s, %s, %s, %s,
  %s, %s, %s
)
"""

UPDATE_CHANGED = """
UPDATE commission_products
SET title=%s, description=%s, item_url=%s, promotion_url=%s,
    short_url=%s, image_url=%s, price=%s, coupon_price=%s,
    commission_rate=%s, estimated_commission=%s, sales_volume=%s,
    coupon_info=%s, status=%s, is_published=0,
    source_page_no=%s, source_round_id=%s, source_run_id=%s,
    source_payload_hash=%s, catalog_change_count=catalog_change_count+1,
    link_created_at=%s, link_expire_at=%s, refresh_due_at=%s,
    last_checked_at=%s, last_seen_at=%s
WHERE jd_sku_id=%s
"""

UPDATE_UNCHANGED = """
UPDATE commission_products
SET source_page_no=%s, source_round_id=%s, source_run_id=%s,
    last_checked_at=%s, last_seen_at=%s
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

                if existing is None:
                    cursor.execute(
                        INSERT_ONE,
                        self._insert_values(product, round_id, run_id, payload_hash, checked_at, seen_at),
                    )
                    inserted += 1
                elif existing.get("source_payload_hash") == payload_hash:
                    cursor.execute(
                        UPDATE_UNCHANGED,
                        (product.source_page_no, round_id, run_id, checked_at, seen_at, product.jd_sku_id),
                    )
                    unchanged += 1
                else:
                    cursor.execute(
                        UPDATE_CHANGED,
                        self._update_values(product, round_id, run_id, payload_hash, checked_at, seen_at),
                    )
                    cursor.execute(
                        INSERT_HISTORY,
                        (
                            product.jd_sku_id,
                            round_id,
                            "update",
                            json.dumps(existing, ensure_ascii=False, default=str, sort_keys=True),
                            json.dumps(product.business_payload(), ensure_ascii=False, default=str, sort_keys=True),
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
    def _insert_values(product: CommissionProduct, round_id: str, run_id: str, payload_hash: str, checked_at: Any, seen_at: Any) -> tuple[Any, ...]:
        return (
            product.jd_sku_id, product.title, product.description, product.item_url,
            product.promotion_url, product.short_url, product.image_url, product.price,
            product.coupon_price, product.commission_rate, product.estimated_commission,
            product.sales_volume, product.coupon_info, product.status,
            product.source_page_no, round_id, run_id, payload_hash,
            product.catalog_change_count, product.link_created_at, product.link_expire_at,
            product.refresh_due_at, product.first_seen_at or seen_at, checked_at, seen_at,
        )

    @staticmethod
    def _update_values(product: CommissionProduct, round_id: str, run_id: str, payload_hash: str, checked_at: Any, seen_at: Any) -> tuple[Any, ...]:
        return (
            product.title, product.description, product.item_url, product.promotion_url,
            product.short_url, product.image_url, product.price, product.coupon_price,
            product.commission_rate, product.estimated_commission, product.sales_volume,
            product.coupon_info, product.status, product.source_page_no, round_id, run_id,
            payload_hash, product.link_created_at, product.link_expire_at,
            product.refresh_due_at, checked_at, seen_at, product.jd_sku_id,
        )
