from __future__ import annotations

import unittest
from unittest.mock import patch

from aideal_cps_data_lab.hz24.resume_gate import artifact_checks


def engineering_report(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "status": "PASS",
        "blocker_count": 0,
        "gate_blocker_count": 0,
        "full_gate_blocker_count": 0,
        "git_head": "engineering-head",
    }
    report.update(overrides)
    return report


def offline_report(git_head: str = "offline-head") -> dict[str, object]:
    return {
        "status": "PASS",
        "git_head": git_head,
        "jd_live_called": False,
    }


def migration_report() -> dict[str, object]:
    return {
        "ok": True,
        "executed": True,
        "evidence_count": 5,
        "checks": {"linked_hash_unchanged": True},
    }


class ArtifactGateTests(unittest.TestCase):
    @patch(
        "aideal_cps_data_lab.hz24.resume_gate.active_paths_unchanged_since",
        side_effect=lambda value: value in {"engineering-head", "offline-head"},
    )
    def test_current_audit_and_offline_heads_pass(self, _unchanged) -> None:
        checks = artifact_checks(
            {"expected_unavailable_count": 5},
            engineering_report(),
            offline_report(),
            migration_report(),
        )
        self.assertTrue(all(checks.values()))

    @patch(
        "aideal_cps_data_lab.hz24.resume_gate.active_paths_unchanged_since",
        return_value=True,
    )
    def test_global_blocker_blocks_resume(self, _unchanged) -> None:
        checks = artifact_checks(
            {"expected_unavailable_count": 5},
            engineering_report(blocker_count=1, status="FAIL"),
            offline_report(),
            migration_report(),
        )
        self.assertFalse(checks["engineering_gate_passed"])

    @patch(
        "aideal_cps_data_lab.hz24.resume_gate.active_paths_unchanged_since",
        return_value=True,
    )
    def test_missing_full_gate_field_blocks_resume(self, _unchanged) -> None:
        engineering = engineering_report()
        engineering.pop("full_gate_blocker_count")
        checks = artifact_checks(
            {"expected_unavailable_count": 5},
            engineering,
            offline_report(),
            migration_report(),
        )
        self.assertFalse(checks["engineering_gate_passed"])

    @patch(
        "aideal_cps_data_lab.hz24.resume_gate.active_paths_unchanged_since",
        return_value=False,
    )
    def test_stale_audit_head_blocks_resume(self, _unchanged) -> None:
        checks = artifact_checks(
            {"expected_unavailable_count": 5},
            engineering_report(git_head="stale-head"),
            offline_report("stale-head"),
            migration_report(),
        )
        self.assertFalse(checks["engineering_report_active_paths_current"])
        self.assertFalse(checks["offline_quality_active_paths_current"])


if __name__ == "__main__":
    unittest.main()
