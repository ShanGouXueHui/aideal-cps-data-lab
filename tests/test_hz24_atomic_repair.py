from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aideal_cps_data_lab.hz24.repair_preflight import RepairSnapshot
from aideal_cps_data_lab.hz24.repository import (
    read_jsonl,
    upsert_jsonl_rows_by_sku,
)
from aideal_cps_data_lab.hz24.sold_out_execution import (
    capture_file,
    post_checks,
    restore_file,
)


def snapshot(
    linked: set[str],
    unavailable: set[str],
    pending: set[str],
) -> RepairSnapshot:
    return RepairSnapshot(
        queue={sku: {} for sku in linked | unavailable | pending},
        linked={sku: {} for sku in linked},
        unavailable={sku: {} for sku in unavailable},
        pending=pending,
        checks={"valid": True},
        counts={
            "queue": len(linked | unavailable | pending),
            "linked": len(linked),
            "unavailable": len(unavailable),
            "pending": len(pending),
            "linked_duplicates": 0,
            "unavailable_duplicates": 0,
        },
        issues={"linked": {}, "unavailable": {}},
    )


class AtomicRepairTests(unittest.TestCase):
    def test_multi_upsert_is_atomic_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unavailable.jsonl"
            upsert_jsonl_rows_by_sku(
                path,
                [
                    {"sku": "200", "status": "unavailable"},
                    {"sku": "100", "status": "unavailable"},
                    {"sku": "200", "status": "unavailable", "value": 2},
                ],
            )
            rows = read_jsonl(path)
            self.assertEqual(["100", "200"], [row["sku"] for row in rows])
            self.assertEqual(2, rows[1]["value"])

    def test_restore_returns_exact_original_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unavailable.jsonl"
            path.write_bytes(b'{"sku":"old"}\n')
            original = capture_file(path)
            upsert_jsonl_rows_by_sku(path, [{"sku": "new"}])
            restore_file(path, original)
            self.assertEqual(original.data, path.read_bytes())

    def test_post_checks_require_exact_72_5_144_state(self) -> None:
        linked = {f"L{index}" for index in range(72)}
        evidence = {f"U{index}" for index in range(5)}
        pending_before = {f"P{index}" for index in range(149)}
        pending_after = {f"P{index}" for index in range(144)}
        before = snapshot(linked, set(), pending_before)
        after = snapshot(linked, evidence, pending_after)
        checks = post_checks(
            {
                "expected_unavailable_after": 5,
                "expected_pending_after": 144,
            },
            before,
            after,
            evidence,
            "linked-hash",
            "linked-hash",
        )
        self.assertTrue(all(checks.values()))

    def test_post_checks_reject_linked_hash_change(self) -> None:
        before = snapshot({"L"}, set(), {"P"})
        after = snapshot({"L"}, {"U"}, set())
        checks = post_checks(
            {
                "expected_unavailable_after": 1,
                "expected_pending_after": 0,
            },
            before,
            after,
            {"U"},
            "before",
            "after",
        )
        self.assertFalse(checks["linked_hash_unchanged"])


if __name__ == "__main__":
    unittest.main()
