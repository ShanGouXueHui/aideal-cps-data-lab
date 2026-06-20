from __future__ import annotations

import unittest

from aideal_cps_data_lab.hz23.promotion_policy import is_promotion_ready


class FinalizePromotionGuardTest(unittest.TestCase):
    def test_observation_is_required(self) -> None:
        manifest = {
            "round_complete": True,
            "candidate_integrity_ready": True,
            "observation_ready": False,
        }
        self.assertFalse(is_promotion_ready(manifest))


if __name__ == "__main__":
    unittest.main()
