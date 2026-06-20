import unittest

from aideal_cps_data_lab.application.landed_validation import validate_landed_rows
from aideal_cps_data_lab.contracts import canonical_payload_hash
from aideal_cps_data_lab.testing import FIXTURES


class LandedValidationTest(unittest.TestCase):
    def make_row(self, title="item", round_id="round-1"):
        row = {
            "jd_sku_id": FIXTURES.sku,
            "title": title,
            "item_url": FIXTURES.item_url,
            "promotion_url": FIXTURES.promotion_url,
            "short_url": FIXTURES.promotion_url,
            "image_url": FIXTURES.image_url,
            "price": "99.90",
            "commission_rate": "12.5000",
            "estimated_commission": "12.49",
            "status": "active",
            "source_round_id": round_id,
        }
        row["source_payload_hash"] = canonical_payload_hash(row)
        return row

    def test_valid(self):
        result = validate_landed_rows(
            [self.make_row()], {"row_count": 1, "round_id": "round-1"}
        )
        self.assertTrue(result["ok"])

    def test_hash_mismatch(self):
        row = self.make_row()
        row["title"] = "changed"
        result = validate_landed_rows(
            [row], {"row_count": 1, "round_id": "round-1"}
        )
        self.assertEqual(result["payload_hash_mismatch_count"], 1)

    def test_round_mismatch(self):
        result = validate_landed_rows(
            [self.make_row(round_id="round-2")],
            {"row_count": 1, "round_id": "round-1"},
        )
        self.assertIn("round_id_matches_manifest", result["failures"])


if __name__ == "__main__":
    unittest.main()
