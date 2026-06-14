import unittest

from aideal_cps_data_lab.application.mysql_initialization_gate import (
    build_mysql_initialization_gate,
)


class MysqlInitializationGateTest(unittest.TestCase):
    def status(self):
        return {
            "service": {"state": "active"},
            "observation_ready": True,
            "mysql_initialization_allowed": True,
            "checks": {
                "full_round_complete": True,
                "candidate_integrity_ready": True,
            },
            "latest_round": {"round_id": "round-1"},
        }

    def manifest(self):
        return {
            "round_id": "round-1",
            "row_count": 2385,
            "data_sha256": "a" * 64,
            "commercial_enabled": False,
        }

    def validation(self):
        return {
            "ok": True,
            "row_count": 2385,
            "file_sha256": "a" * 64,
            "payload_hash_mismatch_count": 0,
            "duplicate_sku_count": 0,
            "invalid_row_count": 0,
        }

    def test_all_verified_inputs_are_ready(self):
        gate = build_mysql_initialization_gate(
            self.status(),
            self.manifest(),
            self.validation(),
            candidate_present=True,
            upgrade_present=True,
            rollback_present=True,
        )
        self.assertTrue(gate["ready"])

    def test_candidate_validation_failure_blocks_initialization(self):
        validation = self.validation()
        validation["payload_hash_mismatch_count"] = 1
        validation["ok"] = False
        gate = build_mysql_initialization_gate(
            self.status(),
            self.manifest(),
            validation,
            candidate_present=True,
            upgrade_present=True,
            rollback_present=True,
        )
        self.assertFalse(gate["ready"])
        self.assertIn("candidate_validation_ok", gate["failures"])
        self.assertIn("candidate_hash_mismatch_zero", gate["failures"])

    def test_round_id_mismatch_blocks_initialization(self):
        manifest = self.manifest()
        manifest["round_id"] = "round-2"
        gate = build_mysql_initialization_gate(
            self.status(),
            manifest,
            self.validation(),
            candidate_present=True,
            upgrade_present=True,
            rollback_present=True,
        )
        self.assertFalse(gate["ready"])
        self.assertIn("round_id_consistent", gate["failures"])


if __name__ == "__main__":
    unittest.main()
