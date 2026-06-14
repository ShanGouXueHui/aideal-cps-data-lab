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

STAGE_COLUMNS = (
    "jd_sku_id",
    *BUSINESS_COLUMNS,
    "source_page_no",
    "source_round_id",
    "source_run_id",
    "source_payload_hash",
    "catalog_change_count",
    "first_seen_at",
    "last_checked_at",
    "last_seen_at",
)

CREATE_STAGE = """
CREATE TEMPORARY TABLE IF NOT EXISTS tmp_commission_products_stage (
  jd_sku_id VARCHAR(64) NOT NULL,
  title VARCHAR(512) NOT NULL,
  description TEXT NULL,
  item_url VARCHAR(500) NULL,
  promotion_url VARCHAR(500) NOT NULL,
  short_url VARCHAR(500) NULL,
  long_url TEXT NULL,
  qr_url TEXT NULL,
  jd_command TEXT NULL,
  image_url VARCHAR(1000) NOT NULL,
  category_name VARCHAR(128) NULL,
  shop_name VARCHAR(255) NULL,
  price DECIMAL(12,2) NOT NULL,
  coupon_price DECIMAL(12,2) NULL,
  commission_rate DECIMAL(8,4) NULL,
  estimated_commission DECIMAL(12,2) NULL,
  sales_volume BIGINT NULL,
  coupon_info VARCHAR(512) NULL,
  status VARCHAR(32) NOT NULL,
  link_created_at DATETIME(6) NULL,
  link_expire_at DATETIME(6) NULL,
  refresh_due_at DATETIME(6) NULL,
  source_page_no SMALLINT UNSIGNED NULL,
  source_round_id VARCHAR(64) NULL,
  source_run_id VARCHAR(64) NULL,
  source_payload_hash CHAR(64) NOT NULL,
  catalog_change_count INT UNSIGNED NOT NULL,
  first_seen_at DATETIME(6) NOT NULL,
  last_checked_at DATETIME(6) NOT NULL,
  last_seen_at DATETIME(6) NOT NULL,
  PRIMARY KEY (jd_sku_id)
) ENGINE=InnoDB
"""

TRUNCATE_STAGE = "TRUNCATE TABLE tmp_commission_products_stage"

INSERT_STAGE = f"""
INSERT INTO tmp_commission_products_stage ({', '.join(STAGE_COLUMNS)})
VALUES ({', '.join(['%s'] * len(STAGE_COLUMNS))})
"""

COUNT_DIFFS = """
SELECT
  COALESCE(SUM(CASE WHEN p.jd_sku_id IS NULL THEN 1 ELSE 0 END), 0) AS inserted_count,
  COALESCE(SUM(CASE WHEN p.jd_sku_id IS NOT NULL AND p.source_payload_hash <> s.source_payload_hash THEN 1 ELSE 0 END), 0) AS updated_count,
  COALESCE(SUM(CASE WHEN p.jd_sku_id IS NOT NULL AND p.source_payload_hash = s.source_payload_hash THEN 1 ELSE 0 END), 0) AS unchanged_count,
  COALESCE(SUM(CASE WHEN p.jd_sku_id IS NOT NULL AND p.is_published = 1 AND p.source_payload_hash <> s.source_payload_hash THEN 1 ELSE 0 END), 0) AS published_changed_count
FROM tmp_commission_products_stage s
LEFT JOIN commission_products p ON p.jd_sku_id = s.jd_sku_id
"""

SELECT_CHANGED_FOR_HISTORY = f"""
SELECT
  p.jd_sku_id,
  p.source_payload_hash AS before_hash,
  s.source_payload_hash AS after_hash,
  {', '.join(f'p.{column} AS before_{column}' for column in BUSINESS_COLUMNS)},
  {', '.join(f's.{column} AS after_{column}' for column in BUSINESS_COLUMNS)}
FROM commission_products p
JOIN tmp_commission_products_stage s ON s.jd_sku_id = p.jd_sku_id
WHERE p.is_published = 0
  AND p.source_payload_hash <> s.source_payload_hash
"""

UPDATE_CHANGED = f"""
UPDATE commission_products p
JOIN tmp_commission_products_stage s ON s.jd_sku_id = p.jd_sku_id
SET
  {', '.join(f'p.{column} = s.{column}' for column in BUSINESS_COLUMNS)},
  p.source_page_no = s.source_page_no,
  p.source_round_id = s.source_round_id,
  p.source_run_id = s.source_run_id,
  p.source_payload_hash = s.source_payload_hash,
  p.catalog_change_count = GREATEST(p.catalog_change_count + 1, s.catalog_change_count),
  p.missing_rounds = 0,
  p.last_checked_at = s.last_checked_at,
  p.last_seen_at = s.last_seen_at
WHERE p.is_published = 0
  AND p.source_payload_hash <> s.source_payload_hash
"""

UPDATE_UNCHANGED = """
UPDATE commission_products p
JOIN tmp_commission_products_stage s ON s.jd_sku_id = p.jd_sku_id
SET
  p.source_page_no = s.source_page_no,
  p.source_round_id = s.source_round_id,
  p.source_run_id = s.source_run_id,
  p.missing_rounds = 0,
  p.last_checked_at = s.last_checked_at,
  p.last_seen_at = s.last_seen_at
WHERE p.source_payload_hash = s.source_payload_hash
"""

INSERT_NEW = f"""
INSERT INTO commission_products (
  {', '.join(STAGE_COLUMNS)},
  is_published,
  missing_rounds
)
SELECT
  {', '.join(f's.{column}' for column in STAGE_COLUMNS)},
  0,
  0
FROM tmp_commission_products_stage s
LEFT JOIN commission_products p ON p.jd_sku_id = s.jd_sku_id
WHERE p.jd_sku_id IS NULL
"""

INSERT_HISTORY = """
INSERT INTO commission_product_history (
  jd_sku_id,
  round_id,
  change_type,
  before_payload,
  after_payload,
  before_hash,
  after_hash,
  changed_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""


class BatchMySQLCommissionProductRepository:
    """Batch repository optimized for 2k-4k product refreshes.

    Rows are loaded into a temporary staging table with executemany, compared in SQL,
    and merged in one transaction. A changed row that is already published is rejected
    until an explicit versioned publish workflow is implemented, preventing silent live
    data mutation.
    """

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        settings: DataLabSettings,
        *,
        batch_size: int = 500,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self._connection_factory = connection_factory
        self._settings = settings
        self._batch_size = batch_size

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
            cursor.execute(TRUNCATE_STAGE)

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
                history_values = [
                    self._history_values(row, round_id) for row in changed_rows
                ]
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
    def _stage_values(
        product: CommissionProduct,
        round_id: str,
        run_id: str,
    ) -> tuple[Any, ...]:
        now = datetime.now()
        checked_at = product.last_checked_at or now
        seen_at = product.last_seen_at or checked_at
        first_seen_at = product.first_seen_at or seen_at
        business = product.business_payload()
        return (
            product.jd_sku_id,
            *(business.get(column) for column in BUSINESS_COLUMNS),
            product.source_page_no,
            round_id,
            run_id,
            product.source_payload_hash(),
            product.catalog_change_count,
            first_seen_at,
            checked_at,
            seen_at,
        )

    @staticmethod
    def _history_values(row: dict[str, Any], round_id: str) -> tuple[Any, ...]:
        before = {
            column: row.get(f"before_{column}") for column in BUSINESS_COLUMNS
        }
        after = {
            column: row.get(f"after_{column}") for column in BUSINESS_COLUMNS
        }
        return (
            row.get("jd_sku_id"),
            round_id,
            "update",
            json.dumps(before, ensure_ascii=False, default=str, sort_keys=True),
            json.dumps(after, ensure_ascii=False, default=str, sort_keys=True),
            row.get("before_hash"),
            row.get("after_hash"),
            datetime.now(),
        )
