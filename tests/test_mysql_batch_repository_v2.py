from __future__ import annotations

import unittest

from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.domain import CommissionProduct
from aideal_cps_data_lab.persistence.mysql_batch_repository import (
    COUNT_DIFFS,
    INSERT_NEW,
    SELECT_CHANGED_FOR_HISTORY,
    UPDATE_CHANGED,
    UPDATE_UNCHANGED,
)
from aideal_cps_data_lab.persistence.mysql_batch_repository_v2 import (
    CLEAR_STAGE,
    TransactionSafeBatchMySQLCommissionProductRepository,
)
from aideal_cps_data_lab.testing import FIXTURES


class FakeCursor:
    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts
        self.executed: list[str] = []
        self.batch_sizes: list[int] = []
        self.rowcount = 0
        self.mode = ""
        self.closed = False

    def execute(self, sql: str, params=None) -> None:
        self.executed.append(sql)
        self.rowcount = 0
        if sql == COUNT_DIFFS:
            self.mode = "counts"
        elif sql == SELECT_CHANGED_FOR_HISTORY:
            self.mode = "changed"
        elif sql == UPDATE_CHANGED:
            self.rowcount = int(self.counts.get("updated_count") or 0)
        elif sql == UPDATE_UNCHANGED:
            self.rowcount = int(self.counts.get("unchanged_count") or 0)
        elif sql == INSERT_NEW:
            self.rowcount = int(self.counts.get("inserted_count") or 0)

    def executemany(self, sql: str, params) -> None:
        values = list(params)
        self.batch_sizes.append(len(values))
        self.rowcount = len(values)

    def fetchone(self):
        if self.mode == "counts":
            self.mode = ""
            return dict(self.counts)
        return None

    def fetchall(self):
        if self.mode == "changed":
            self.mode = ""
            return []
        return []

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, counts: dict[str, int]) -> None:
        self.fake_cursor = FakeCursor(counts)
        self.began = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def begin(self) -> None:
        self.began = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class TransactionSafeBatchRepositoryTest(unittest.TestCase):
    def product(self, sku: str) -> CommissionProduct:
        return CommissionProduct.from_candidate_row(
            {
                "sku": sku,
                "title": f"商品-{sku}",
                "item_url": f"{FIXTURES.item_url_prefix}{sku}.html",
                "promotion_url": FIXTURES.promotion_url,
                "image_url": FIXTURES.image_url,
                "price": "99.90",
                "commission_rate": "12.5%",
                "estimated_commission": "12.49",
                "status": "active",
                "source_page_no": 1,
                "last_checked_at": FIXTURES.timestamp,
                "last_seen_at": FIXTURES.timestamp,
            }
        )

    def repository(self, connection: FakeConnection, batch_size: int = 500):
        settings = DataLabSettings(
            database_url="configured-outside-test",
            db_write_enabled=True,
        )
        return TransactionSafeBatchMySQLCommissionProductRepository(
            lambda: connection,
            settings,
            batch_size=batch_size,
        )

    def test_4000_rows_use_eight_batches_and_one_transaction(self) -> None:
        connection = FakeConnection(
            {
                "inserted_count": 4000,
                "updated_count": 0,
                "unchanged_count": 0,
                "published_changed_count": 0,
            }
        )
        products = [self.product(str(100000000000 + index)) for index in range(4000)]
        outcome = self.repository(connection).upsert_many(
            products,
            round_id="round-1",
            run_id="run-1",
        )
        self.assertEqual(outcome.inserted, 4000)
        self.assertEqual(connection.fake_cursor.batch_sizes, [500] * 8)
        self.assertIn(CLEAR_STAGE, connection.fake_cursor.executed)
        self.assertNotIn("TRUNCATE TABLE tmp_commission_products_stage", connection.fake_cursor.executed)
        self.assertTrue(connection.began)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.fake_cursor.closed)
        self.assertTrue(connection.closed)

    def test_published_change_rolls_back_before_merge(self) -> None:
        connection = FakeConnection(
            {
                "inserted_count": 0,
                "updated_count": 1,
                "unchanged_count": 0,
                "published_changed_count": 1,
            }
        )
        with self.assertRaisesRegex(RuntimeError, "published_product_change"):
            self.repository(connection).upsert_many(
                [self.product(FIXTURES.sku)],
                round_id="round-2",
                run_id="run-2",
            )
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_duplicate_input_is_rejected_before_connection(self) -> None:
        called = False

        def factory():
            nonlocal called
            called = True
            return FakeConnection({})

        settings = DataLabSettings(
            database_url="configured-outside-test",
            db_write_enabled=True,
        )
        repository = TransactionSafeBatchMySQLCommissionProductRepository(factory, settings)
        product = self.product(FIXTURES.sku)
        with self.assertRaisesRegex(ValueError, "duplicate SKU"):
            repository.upsert_many([product, product], round_id="r", run_id="x")
        self.assertFalse(called)


if __name__ == "__main__":
    unittest.main()
