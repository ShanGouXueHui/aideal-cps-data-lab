from __future__ import annotations

import unittest

from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.domain import CommissionProduct
from aideal_cps_data_lab.persistence.mysql_repository import (
    INSERT_HISTORY,
    INSERT_ONE,
    UPDATE_CHANGED,
    UPDATE_UNCHANGED,
    MySQLCommissionProductRepository,
)


class FakeCursor:
    def __init__(self, fetched: list[dict[str, object] | None]) -> None:
        self.fetched = list(fetched)
        self.executed: list[tuple[str, object | None]] = []
        self.closed = False

    def execute(self, sql: str, params: object | None = None) -> None:
        self.executed.append((sql, params))

    def fetchone(self) -> dict[str, object] | None:
        return self.fetched.pop(0) if self.fetched else None

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, fetched: list[dict[str, object] | None]) -> None:
        self.fake_cursor = FakeCursor(fetched)
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


class MySQLRepositoryTest(unittest.TestCase):
    def product(self, price: str = "99.90") -> CommissionProduct:
        return CommissionProduct.from_candidate_row(
            {
                "sku": "100012345678",
                "title": "测试商品",
                "item_url": "https://item.jd.com/100012345678.html",
                "promotion_url": "https://u.jd.com/example",
                "image_url": "https://img.example.invalid/product.jpg",
                "price": price,
                "commission_rate": "12.5%",
                "estimated_commission": "12.49",
                "status": "active",
                "source_page_no": 1,
                "last_checked_at": "2026-06-14T10:00:00",
                "last_seen_at": "2026-06-14T10:00:00",
            }
        )

    def repository(self, connection: FakeConnection) -> MySQLCommissionProductRepository:
        settings = DataLabSettings(
            database_url="configured-outside-repository",
            db_write_enabled=True,
        )
        return MySQLCommissionProductRepository(lambda: connection, settings)

    def test_insert_is_unpublished_and_committed(self) -> None:
        connection = FakeConnection([None])
        outcome = self.repository(connection).upsert_many(
            [self.product()], round_id="round-1", run_id="run-1"
        )
        self.assertEqual(outcome.inserted, 1)
        self.assertTrue(connection.began)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.fake_cursor.closed)
        self.assertTrue(connection.closed)
        self.assertTrue(any(sql == INSERT_ONE for sql, _ in connection.fake_cursor.executed))

    def test_unchanged_hash_updates_only_lineage(self) -> None:
        product = self.product()
        connection = FakeConnection([{"source_payload_hash": product.source_payload_hash()}])
        outcome = self.repository(connection).upsert_many(
            [product], round_id="round-2", run_id="run-2"
        )
        self.assertEqual(outcome.unchanged, 1)
        sqls = [sql for sql, _ in connection.fake_cursor.executed]
        self.assertIn(UPDATE_UNCHANGED, sqls)
        self.assertNotIn(INSERT_HISTORY, sqls)

    def test_changed_hash_updates_and_writes_history(self) -> None:
        connection = FakeConnection(
            [{"source_payload_hash": "old-hash", "title": "旧标题", "price": "109.90"}]
        )
        outcome = self.repository(connection).upsert_many(
            [self.product("89.90")], round_id="round-3", run_id="run-3"
        )
        self.assertEqual(outcome.updated, 1)
        sqls = [sql for sql, _ in connection.fake_cursor.executed]
        self.assertIn(UPDATE_CHANGED, sqls)
        self.assertIn(INSERT_HISTORY, sqls)

    def test_write_flag_blocks_connection_creation(self) -> None:
        called = False

        def connection_factory() -> FakeConnection:
            nonlocal called
            called = True
            return FakeConnection([])

        repository = MySQLCommissionProductRepository(connection_factory, DataLabSettings())
        with self.assertRaisesRegex(RuntimeError, "DATA_LAB_DB_WRITE_ENABLED"):
            repository.upsert_many([self.product()], round_id="round", run_id="run")
        self.assertFalse(called)

    def test_duplicate_batch_is_rejected_before_transaction(self) -> None:
        connection = FakeConnection([])
        product = self.product()
        with self.assertRaisesRegex(ValueError, "duplicate SKU"):
            self.repository(connection).upsert_many(
                [product, product], round_id="round", run_id="run"
            )
        self.assertFalse(connection.began)


if __name__ == "__main__":
    unittest.main()
