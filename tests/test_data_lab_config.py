from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from aideal_cps_data_lab.config import DataLabSettings


class DataLabSettingsTest(unittest.TestCase):
    def test_all_commercial_database_flags_default_false(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = DataLabSettings.from_env()
        self.assertEqual(settings.database_url, "")
        self.assertFalse(settings.db_write_enabled)
        self.assertFalse(settings.db_dual_write_enabled)
        self.assertFalse(settings.publish_enabled)

    def test_write_gate_requires_flag_and_database_url(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "DATA_LAB_DB_WRITE_ENABLED"):
            DataLabSettings().assert_write_allowed()
        with self.assertRaisesRegex(RuntimeError, "DATA_LAB_DATABASE_URL"):
            DataLabSettings(db_write_enabled=True).assert_write_allowed()

    def test_explicit_true_values_are_supported(self) -> None:
        env = {
            "DATA_LAB_DATABASE_URL": "mysql+pymysql://placeholder@127.0.0.1/aideal_cps_data_lab",
            "DATA_LAB_DB_WRITE_ENABLED": "true",
            "DATA_LAB_DB_DUAL_WRITE_ENABLED": "1",
            "DATA_LAB_PUBLISH_ENABLED": "yes",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = DataLabSettings.from_env()
        self.assertTrue(settings.db_write_enabled)
        self.assertTrue(settings.db_dual_write_enabled)
        self.assertTrue(settings.publish_enabled)
        settings.assert_write_allowed()
        settings.assert_publish_allowed()


if __name__ == "__main__":
    unittest.main()
