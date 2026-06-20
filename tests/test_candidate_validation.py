from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from aideal_cps_data_lab.application import validate_candidate
from aideal_cps_data_lab.contracts import canonical_payload_hash
from aideal_cps_data_lab.testing import FIXTURES


class CandidateValidationTest(unittest.TestCase):
    def build_files(
        self,
        rows: list[dict[str, object]],
    ) -> tuple[Path, Path, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        candidate = root / "candidate.jsonl"
        text = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        )
        candidate.write_text(text, encoding="utf-8")
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "aideal-cps-product-feed-manifest/v1",
                    "feed_schema_version": "aideal-cps-product-feed/v1",
                    "feed_status": "candidate",
                    "round_id": "round-1",
                    "data_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "row_count": len(rows),
                    "eligible_sku_count": len(rows),
                    "duplicate_sku_count": 0,
                    "rejected": {"unsafe_hz20": 0, "untrusted_promotion_url": 0},
                    "commercial_enabled": False,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return candidate, manifest, tmp

    def row(self, sku: str, commission_rate: str = "12.5%") -> dict[str, object]:
        row: dict[str, object] = {
            "schema_version": "aideal-cps-product-feed/v1",
            "source": "jd_union_datalab",
            "sku": sku,
            "title": f"商品-{sku}",
            "item_url": f"{FIXTURES.item_url_prefix}{sku}.html",
            "promotion_url": FIXTURES.promotion_url,
            "short_url": FIXTURES.promotion_url,
            "image_url": FIXTURES.image_url,
            "price": "99.90",
            "commission_rate": commission_rate,
            "estimated_commission": "12.49",
            "status": "active",
            "source_round_id": "round-1",
            "source_page_no": 1,
            "catalog_change_count": 0,
        }
        row["source_payload_hash"] = canonical_payload_hash(row)
        return row

    def test_valid_candidate_passes(self) -> None:
        candidate, manifest, tmp = self.build_files([self.row("100"), self.row("200")])
        self.addCleanup(tmp.cleanup)
        report = validate_candidate(candidate, manifest)
        self.assertTrue(report.ok, report.as_dict())
        self.assertEqual(report.row_count, 2)
        self.assertEqual(report.unique_sku_count, 2)

    def test_product_lineage_round_may_precede_snapshot_round(self) -> None:
        row = self.row("100")
        row["source_round_id"] = "round-0"
        row["source_payload_hash"] = canonical_payload_hash(row)
        candidate, manifest, tmp = self.build_files([row])
        self.addCleanup(tmp.cleanup)
        report = validate_candidate(candidate, manifest)
        self.assertTrue(report.ok, report.as_dict())

    def test_missing_product_lineage_round_is_rejected(self) -> None:
        row = self.row("100")
        row["source_round_id"] = None
        row["source_payload_hash"] = canonical_payload_hash(row)
        candidate, manifest, tmp = self.build_files([row])
        self.addCleanup(tmp.cleanup)
        report = validate_candidate(candidate, manifest)
        self.assertFalse(report.ok)
        self.assertIn("source_round_id_missing", report.errors)

    def test_percent_and_decimal_rates_have_same_hash(self) -> None:
        percent = self.row("100", "12.5%")
        decimal = self.row("100", "12.5000")
        self.assertEqual(canonical_payload_hash(percent), canonical_payload_hash(decimal))

    def test_checksum_tamper_is_rejected(self) -> None:
        candidate, manifest, tmp = self.build_files([self.row("100")])
        self.addCleanup(tmp.cleanup)
        candidate.write_text(
            candidate.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
        report = validate_candidate(candidate, manifest)
        self.assertFalse(report.ok)
        self.assertIn("file_checksum_mismatch", report.errors)

    def test_payload_hash_mismatch_is_rejected(self) -> None:
        row = self.row("100")
        row["source_payload_hash"] = "0" * 64
        candidate, manifest, tmp = self.build_files([row])
        self.addCleanup(tmp.cleanup)
        report = validate_candidate(candidate, manifest)
        self.assertFalse(report.ok)
        self.assertEqual(report.payload_hash_mismatch_count, 1)

    def test_duplicate_and_unsorted_sku_are_rejected(self) -> None:
        candidate, manifest, tmp = self.build_files(
            [self.row("200"), self.row("100"), self.row("100")]
        )
        self.addCleanup(tmp.cleanup)
        report = validate_candidate(candidate, manifest)
        self.assertFalse(report.ok)
        self.assertIn("duplicate_sku", report.errors)
        self.assertIn("sku_order_invalid", report.errors)


if __name__ == "__main__":
    unittest.main()
