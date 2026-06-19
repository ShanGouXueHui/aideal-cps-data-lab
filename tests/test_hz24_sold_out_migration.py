from __future__ import annotations

import unittest

from aideal_cps_data_lab.hz24.legacy_sold_out import (
    collect_evidence,
    evidence_from_failure,
    validate_evidence,
)


def sold_out_failure(sku: str = "100") -> dict:
    return {
        "sku": sku,
        "tab": "限量高佣",
        "click": {
            "hit": {"cls": "card-disabled"},
            "mark": {
                "matched": {
                    "itemUrl": f"https://item.invalid/{sku}",
                    "rootText": "商品名称 已抢光 一键领链",
                }
            },
        },
    }


class SoldOutMigrationTests(unittest.TestCase):
    def test_extracts_only_confirmed_sold_out(self) -> None:
        evidence = evidence_from_failure(sold_out_failure())
        self.assertIsNotNone(evidence)
        self.assertEqual("100", evidence.sku)

    def test_deduplicates_report_failures(self) -> None:
        evidence, duplicates = collect_evidence(
            {"failures": [sold_out_failure(), sold_out_failure()]}
        )
        self.assertEqual(1, len(evidence))
        self.assertEqual(1, duplicates)

    def test_rejects_already_linked_sku(self) -> None:
        evidence, _ = collect_evidence({"failures": [sold_out_failure()]})
        checks = validate_evidence(
            evidence,
            {"100": {"source_tabs": ["限量高佣"]}},
            {"100"},
            1,
            0,
        )
        self.assertFalse(checks["none_already_linked"])

    def test_accepts_matching_queue_evidence(self) -> None:
        evidence, _ = collect_evidence({"failures": [sold_out_failure()]})
        checks = validate_evidence(
            evidence,
            {"100": {"source_tabs": ["限量高佣"]}},
            set(),
            1,
            0,
        )
        self.assertTrue(all(checks.values()))


if __name__ == "__main__":
    unittest.main()
