from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aideal_cps_data_lab.application import build_backfill_plan
from aideal_cps_data_lab.testing import FIXTURES


class BackfillPlanTest(unittest.TestCase):
    def candidate(self, sku: str, price: str = "99.90") -> dict[str, object]:
        return {
            "sku": sku,
            "title": f"商品-{sku}",
            "item_url": f"{FIXTURES.item_url_prefix}{sku}.html",
            "promotion_url": FIXTURES.promotion_url,
            "image_url": FIXTURES.image_url,
            "price": price,
            "commission_rate": "10%",
            "estimated_commission": "9.99",
            "status": "active",
        }

    def write_rows(self, rows: list[object]) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".jsonl",
            delete=False,
        )
        with tmp:
            for row in rows:
                if isinstance(row, str):
                    tmp.write(row + "\n")
                else:
                    tmp.write(json.dumps(row, ensure_ascii=False) + "\n")
        return Path(tmp.name)

    def test_valid_rows_are_sorted_by_sku(self) -> None:
        path = self.write_rows([self.candidate("200"), self.candidate("100")])
        self.addCleanup(path.unlink)
        plan = build_backfill_plan(path)
        self.assertEqual([x.jd_sku_id for x in plan.unique_products], ["100", "200"])
        self.assertEqual(plan.duplicate_sku_count, 0)
        self.assertTrue(plan.summary()["ready_for_write"])

    def test_duplicate_sku_blocks_write_readiness(self) -> None:
        path = self.write_rows([self.candidate("100"), self.candidate("100")])
        self.addCleanup(path.unlink)
        plan = build_backfill_plan(path)
        self.assertEqual(plan.valid_unique_count, 1)
        self.assertEqual(plan.duplicate_sku_count, 1)
        self.assertFalse(plan.summary()["ready_for_write"])

    def test_invalid_rows_are_counted_by_reason(self) -> None:
        invalid_url = self.candidate("101")
        invalid_url["promotion_url"] = FIXTURES.untrusted_url
        path = self.write_rows(["not-json", invalid_url])
        self.addCleanup(path.unlink)
        plan = build_backfill_plan(path)
        self.assertEqual(plan.rejected["invalid_json"], 1)
        self.assertEqual(plan.rejected["untrusted_promotion_url"], 1)
        self.assertEqual(plan.valid_unique_count, 0)


if __name__ == "__main__":
    unittest.main()
