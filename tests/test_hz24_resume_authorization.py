from __future__ import annotations

import unittest
from unittest.mock import patch

from aideal_cps_data_lab.hz24.guarded_application import run_guarded_collection
from aideal_cps_data_lab.hz24.resume_authorization import _authorization_checks


def current_state(
    *,
    linked: set[str],
    unavailable: set[str],
    pending: set[str],
) -> dict:
    queue = linked | unavailable | pending
    return {
        "queue": queue,
        "queue_sha256": "queue-hash",
        "linked": linked,
        "unavailable": unavailable,
        "pending": pending,
        "linked_invalid": 0,
        "unavailable_invalid": 0,
        "linked_duplicates": 0,
        "unavailable_duplicates": 0,
        "linked_issues": {"invalid": []},
        "unavailable_issues": {"invalid": []},
    }


def resume_report() -> dict:
    return {
        "resume_allowed": True,
        "git_head": "tested-head",
        "counts": {"linked": 2, "unavailable": 1, "pending": 2},
        "details": {
            "queue_sha256": "queue-hash",
            "baseline_linked_skus": ["L1", "L2"],
            "baseline_unavailable_skus": ["U1"],
        },
    }


class ResumeAuthorizationTests(unittest.TestCase):
    @patch(
        "aideal_cps_data_lab.hz24.resume_authorization.active_paths_unchanged_since",
        return_value=True,
    )
    def test_monotonic_progress_is_authorized(self, _unchanged) -> None:
        checks = _authorization_checks(
            resume_report(),
            current_state(
                linked={"L1", "L2", "L3"},
                unavailable={"U1"},
                pending={"P1"},
            ),
            require_pending=True,
        )
        self.assertTrue(all(checks.values()))

    @patch(
        "aideal_cps_data_lab.hz24.resume_authorization.active_paths_unchanged_since",
        return_value=True,
    )
    def test_missing_baseline_linked_sku_is_blocked(self, _unchanged) -> None:
        checks = _authorization_checks(
            resume_report(),
            current_state(
                linked={"L1", "L3"},
                unavailable={"U1"},
                pending={"L2", "P1"},
            ),
            require_pending=True,
        )
        self.assertFalse(checks["baseline_linked_present"])

    @patch(
        "aideal_cps_data_lab.hz24.resume_authorization.active_paths_unchanged_since",
        return_value=True,
    )
    def test_completed_queue_passes_post_check(self, _unchanged) -> None:
        checks = _authorization_checks(
            resume_report(),
            current_state(
                linked={"L1", "L2", "L3", "P1"},
                unavailable={"U1", "P2"},
                pending=set(),
            ),
            require_pending=False,
        )
        self.assertTrue(all(checks.values()))

    @patch("aideal_cps_data_lab.hz24.guarded_application.load_settings")
    @patch("aideal_cps_data_lab.hz24.guarded_application._write_guard")
    @patch("aideal_cps_data_lab.hz24.guarded_application.run_collection")
    @patch(
        "aideal_cps_data_lab.hz24.guarded_application.authorize_collection",
        return_value=(False, {"failures": ["gate"], "counts": {}}),
    )
    def test_unauthorized_guard_never_starts_collection(
        self,
        _authorize,
        run_collection,
        write_guard,
        _settings,
    ) -> None:
        self.assertEqual(4, run_guarded_collection())
        run_collection.assert_not_called()
        payload = write_guard.call_args.args[0]
        self.assertFalse(payload["collection_started"])
        self.assertEqual("resume_authorization_failed", payload["reason"])


if __name__ == "__main__":
    unittest.main()
