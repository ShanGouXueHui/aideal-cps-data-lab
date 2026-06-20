from __future__ import annotations

import unittest

from aideal_cps_data_lab.config import DataLabSettings
from aideal_cps_data_lab.domain import CommissionProduct
from aideal_cps_data_lab.persistence.mysql_batch_repository import (
    COUNT_DIFFS,
    CREATE_STAGE,
    INSERT_NEW,
    INSERT_STAGE,
    STAGE_COLUMNS,
    UPDATE_CHANGED,
    BatchMySQLCommissionProductRepository,
)
from aideal_cps_data_lab.persistence.mysql_columns import stage_values
from aideal_cps_data_lab.testing import FIXTURES


class BatchRepositoryContractTest(unittest.TestCase):
    def product(self) -> CommissionProduct:
        return CommissionProduct.from_candidate_row(
            {
                "sku": FIXTURES.sku,
                "title": "测试商品",
                "item_url": FIXTURES.item_url,
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

    def test_stage_has_unique_sku_and_complete_placeholder_count(self) -> None:
        self.assertIn("PRIMARY KEY (jd_sku_id)", CREATE_STAGE)
        self.assertEqual(INSERT_STAGE.count("%s"), len(STAGE_COLUMNS))
        values = stage_values(
            self.product(),
            "round-1",
            "run-1",
        )
        self.assertEqual(len(values), len(STAGE_COLUMNS))
        self.assertEqual(values[0], FIXTURES.sku)

    def test_merge_sql_has_integrity_guards(self) -> None:
        self.assertIn("published_changed_count", COUNT_DIFFS)
        self.assertIn("p.is_published = 0", UPDATE_CHANGED)
        self.assertIn("WHERE p.jd_sku_id IS NULL", INSERT_NEW)

    def test_write_flag_blocks_before_connection(self) -> None:
        called = False

        def factory():
            nonlocal called
            called = True
            raise AssertionError("connection must not be created")

        repository = BatchMySQLCommissionProductRepository(factory, DataLabSettings())
        with self.assertRaisesRegex(RuntimeError, "DATA_LAB_DB_WRITE_ENABLED"):
            repository.upsert_many(
                [self.product()],
                round_id="round-1",
                run_id="run-1",
            )
        self.assertFalse(called)

    def test_batch_size_must_be_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "batch_size"):
            BatchMySQLCommissionProductRepository(
                lambda: None,
                DataLabSettings(),
                batch_size=0,
            )


if __name__ == "__main__":
    unittest.main()
