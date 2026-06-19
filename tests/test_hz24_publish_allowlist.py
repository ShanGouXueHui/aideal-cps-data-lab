from __future__ import annotations

import unittest
from pathlib import Path


class PublishAllowlistTests(unittest.TestCase):
    def test_evidence_script_never_mentions_runtime_jsonl(self) -> None:
        text = Path("scripts/hz24_publish_terminal_repair_evidence.sh").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("data/import/", text)
        self.assertNotIn(".jsonl", text)


if __name__ == "__main__":
    unittest.main()
