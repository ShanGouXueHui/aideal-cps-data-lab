from __future__ import annotations

import unittest
from decimal import Decimal

from aideal_cps_data_lab.domain import CommissionProduct, ProductValidationError


class CommissionProductDomainTest(unittest.TestCase):
    def base_row(self) -> dict[str, object]:
        return {
            "sku": "100012345678",
            "title": "测试商品",
            "item_url": "https://item.jd.com/100012345678.html",
            "promotion_url": "https://u.jd.com/example",
            "short_url": "https://u.jd.com/example",
            "image_url": "https://img.example.invalid/product.jpg",
            "price": "99.90",
            "commission_rate": "12.5%",
            "estimated_commission": "12.49",
            "status": "active",
            "source_page_no": 1,
            "source_round_id": "round-a",
            "last_checked_at": "2026-06-14T10:00:00",
            "last_seen_at": "2026-06-14T10:00:00",
        }

    def test_decimal_and_percent_normalization(self) -> None:
        product = CommissionProduct.from_candidate_row(self.base_row())
        self.assertEqual(product.price, Decimal("99.90"))
        self.assertEqual(product.commission_rate, Decimal("12.5"))
        self.assertEqual(product.estimated_commission, Decimal("12.49"))

    def test_hash_ignores_volatile_lineage_and_timestamps(self) -> None:
        row_a = self.base_row()
        row_b = self.base_row()
        row_b["source_round_id"] = "round-b"
        row_b["last_checked_at"] = "2026-06-15T10:00:00"
        row_b["last_seen_at"] = "2026-06-15T10:00:00"

        product_a = CommissionProduct.from_candidate_row(row_a)
        product_b = CommissionProduct.from_candidate_row(row_b)
        self.assertEqual(product_a.source_payload_hash(), product_b.source_payload_hash())

    def test_hash_changes_for_business_field(self) -> None:
        row_a = self.base_row()
        row_b = self.base_row()
        row_b["price"] = "89.90"

        product_a = CommissionProduct.from_candidate_row(row_a)
        product_b = CommissionProduct.from_candidate_row(row_b)
        self.assertNotEqual(product_a.source_payload_hash(), product_b.source_payload_hash())

    def test_rejects_untrusted_promotion_url(self) -> None:
        row = self.base_row()
        row["promotion_url"] = "https://example.com/not-jd"
        with self.assertRaisesRegex(ProductValidationError, "untrusted_promotion_url"):
            CommissionProduct.from_candidate_row(row)

    def test_rejects_non_numeric_sku(self) -> None:
        row = self.base_row()
        row["sku"] = "bad-sku"
        with self.assertRaisesRegex(ProductValidationError, "invalid_jd_sku_id"):
            CommissionProduct.from_candidate_row(row)


if __name__ == "__main__":
    unittest.main()
