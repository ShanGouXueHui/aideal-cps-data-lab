from __future__ import annotations

import unittest

from aideal_cps_data_lab.hz24.jd_page import JDPageAdapter
from aideal_cps_data_lab.hz24.settings import load_settings


class CanonicalAdapterTests(unittest.TestCase):
    def test_hz21_adapter_contract_removed(self) -> None:
        settings = load_settings()
        self.assertFalse(hasattr(settings.contracts, "hz21_adapter"))

    def test_image_normalization_uses_config(self) -> None:
        adapter = JDPageAdapter(load_settings())
        value = adapter.normalize_image("jfs/example.jpg")
        self.assertTrue(value.startswith("https://"))
        self.assertIn("jfs/example.jpg", value)

    def test_link_dates_are_ordered(self) -> None:
        created, expires, refresh = JDPageAdapter(load_settings()).link_dates()
        self.assertLess(created, refresh)
        self.assertLess(refresh, expires)


if __name__ == "__main__":
    unittest.main()
