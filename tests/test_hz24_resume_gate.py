from __future__ import annotations

import unittest

from aideal_cps_data_lab.hz24.resume_gate import dataset_checks


class ResumeGateTests(unittest.TestCase):
    def test_partial_queue_accounting_passes(self) -> None:
        config = {
            "expected_queue_count": 3,
            "expected_linked_count": 1,
            "expected_unavailable_count": 1,
            "expected_pending_count": 1,
        }
        queue = {
            "100": {"source_tabs": ["A"]},
            "200": {"source_tabs": ["A"]},
            "300": {"source_tabs": ["A"]},
        }
        linked = [{"sku": "100", "status": "ok"}]
        unavailable = [
            {"sku": "200", "status": "unavailable", "reason": "sold_out"}
        ]
        checks, counts = dataset_checks(
            config,
            queue,
            linked,
            unavailable,
            0,
            0,
            {"invalid": []},
            {"invalid": []},
        )
        self.assertTrue(all(checks.values()))
        self.assertEqual(1, counts["pending"])

    def test_overlap_is_blocked(self) -> None:
        config = {
            "expected_queue_count": 1,
            "expected_linked_count": 1,
            "expected_unavailable_count": 1,
            "expected_pending_count": 0,
        }
        queue = {"100": {"source_tabs": ["A"]}}
        linked = [{"sku": "100", "status": "ok"}]
        unavailable = [
            {"sku": "100", "status": "unavailable", "reason": "sold_out"}
        ]
        checks, _ = dataset_checks(
            config,
            queue,
            linked,
            unavailable,
            0,
            0,
            {"invalid": []},
            {"invalid": []},
        )
        self.assertFalse(checks["terminal_overlap_zero"])


if __name__ == "__main__":
    unittest.main()
