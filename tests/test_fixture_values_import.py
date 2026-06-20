import unittest

from aideal_cps_data_lab.testing import FIXTURES


class FixtureValuesImportTest(unittest.TestCase):
    def test_sku_is_present(self) -> None:
        self.assertTrue(FIXTURES.sku)
