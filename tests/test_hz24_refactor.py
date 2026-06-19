from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aideal_cps_data_lab.hz24.batch import BatchState
from aideal_cps_data_lab.hz24.records import unavailable_reason
from aideal_cps_data_lab.hz24.repository import (
    read_jsonl,
    unavailable_skus,
    upsert_jsonl_by_sku,
)
from aideal_cps_data_lab.hz24.validation_io import index_by_sku


class HZ24RepositoryTests(unittest.TestCase):
    def test_upsert_jsonl_keeps_one_row_per_sku(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            upsert_jsonl_by_sku(path, {"sku": "100", "status": "ok", "value": 1})
            upsert_jsonl_by_sku(path, {"sku": "100", "status": "ok", "value": 2})
            rows = read_jsonl(path)
            self.assertEqual(1, len(rows))
            self.assertEqual(2, rows[0]["value"])

    def test_unavailable_skus_only_returns_terminal_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unavailable.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"sku": "100", "status": "unavailable"}),
                        json.dumps({"sku": "200", "status": "pending"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual({"100"}, unavailable_skus(path))


class HZ24OutcomeTests(unittest.TestCase):
    def test_sold_out_is_terminal_unavailable(self) -> None:
        card = {"raw_text": "商品名称 已抢光 一键领链"}
        self.assertEqual("sold_out", unavailable_reason(card))

    def test_not_promotable_is_terminal_unavailable(self) -> None:
        card = {"raw_text": "商品名称 暂不支持推广"}
        self.assertEqual("not_promotable", unavailable_reason(card))

    def test_failure_fuse_does_not_count_success(self) -> None:
        state = BatchState()
        state.register_failure({"reason": "click_failed"}, fuse=2)
        self.assertIsNone(state.stop_reason)
        state.register_success()
        state.register_failure({"reason": "click_failed"}, fuse=2)
        self.assertIsNone(state.stop_reason)


class HZ24ValidationTests(unittest.TestCase):
    def test_index_by_sku_reports_duplicate_rows(self) -> None:
        indexed, duplicates = index_by_sku(
            [
                {"sku": "100", "value": 1},
                {"sku": "100", "value": 2},
                {"sku": "200", "value": 3},
            ]
        )
        self.assertEqual(1, duplicates)
        self.assertEqual({"100", "200"}, set(indexed))
        self.assertEqual(2, indexed["100"]["value"])


if __name__ == "__main__":
    unittest.main()
