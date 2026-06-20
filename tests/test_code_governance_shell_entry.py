from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


class CodeGovernanceShellEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.entry = cls.root / "scripts/ops/run_code_governance_ci_bridge.sh"
        cls.text = cls.entry.read_text(encoding="utf-8")

    def test_shell_syntax(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(self.entry)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode)

    def test_forbidden_shell_exit_patterns_are_absent(self) -> None:
        self.assertNotIn("set -e", self.text)
        self.assertNotIn("|| exit 1", self.text)

    def test_uses_isolated_offline_bridge(self) -> None:
        self.assertIn("git worktree add --detach", self.text)
        self.assertIn("AIDEAL_OFFLINE_TEST=1", self.text)
        self.assertIn("scripts/ops/ci_bridge_runner.py", self.text)
        self.assertIn('ACTION="${2:-validate}"', self.text)

    def test_branch_validation_cannot_publish(self) -> None:
        self.assertIn("PUBLISH_REQUIRES_MAIN", self.text)
        self.assertIn('[ "${TARGET_REF}" != "main" ]', self.text)


if __name__ == "__main__":
    unittest.main()
