from __future__ import annotations

import unittest
from unittest.mock import patch

from aideal_cps_data_lab.hz24.resume_gate import artifact_checks


class ArtifactGateTests(unittest.TestCase):
    @patch(
        "aideal_cps_data_lab.hz24.resume_gate.active_paths_unchanged_since",
        side_effect=lambda value: value in {"engineering-head", "offline-head"},
    )
    def test_current_audit_and_offline_heads_pass(self, _unchanged) -> None:
        checks = artifact_checks(
            {"expected_unavailable_count": 5},
            {
                "status": "PASS",
                "gate_blocker_count": 0,
                "git_head": "engineering-head",
            },
            {
                "status": "PASS",
                "git_head": "offline-head",
                "jd_live_called": False,
            },
            {
                "ok": True,
                "executed": True,
                "evidence_count": 5,
                "checks": {"linked_hash_unchanged": True},
            },
        )
        self.assertTrue(all(checks.values()))

    @patch(
        "aideal_cps_data_lab.hz24.resume_gate.active_paths_unchanged_since",
        return_value=False,
    )
    def test_stale_audit_head_blocks_resume(self, _unchanged) -> None:
        checks = artifact_checks(
            {"expected_unavailable_count": 5},
            {
                "status": "PASS",
                "gate_blocker_count": 0,
                "git_head": "stale-head",
            },
            {
                "status": "PASS",
                "git_head": "stale-head",
                "jd_live_called": False,
            },
            {
                "ok": True,
                "executed": True,
                "evidence_count": 5,
                "checks": {"linked_hash_unchanged": True},
            },
        )
        self.assertFalse(checks["engineering_report_active_paths_current"])
        self.assertFalse(checks["offline_quality_active_paths_current"])


if __name__ == "__main__":
    unittest.main()
