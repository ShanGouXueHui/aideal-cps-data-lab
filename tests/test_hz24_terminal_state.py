from __future__ import annotations

import unittest

from aideal_cps_data_lab.hz24.terminal_state import TerminalSkuState


class TerminalStateTests(unittest.TestCase):
    def test_disjoint_states_pass(self) -> None:
        state = TerminalSkuState(linked={"100"}, unavailable={"200"})
        state.require_disjoint()
        self.assertFalse(state.overlap)

    def test_overlap_is_rejected(self) -> None:
        state = TerminalSkuState(linked={"100"}, unavailable={"100"})
        with self.assertRaises(ValueError):
            state.require_disjoint()


if __name__ == "__main__":
    unittest.main()
