"""pr-overview tests are part of the one answer to 'is it green?'.

Adversarial finding 4: `.claude/skills/pr-overview/tests` is absent
from `ops/bin/suites.sh`, so the board-wide refusal pin never runs in
CI or `bash ops/bin/suites.sh`.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SUITES = REPO / "ops" / "bin" / "suites.sh"
OVERVIEW_TESTS = ".claude/skills/pr-overview/tests"


class SuitesIncludePrOverview(unittest.TestCase):
    def test_suites_sh_discovers_pr_overview_tests(self):
        self.assertTrue(SUITES.is_file(), f"missing {SUITES}")
        text = SUITES.read_text(encoding="utf-8")
        self.assertIn(
            OVERVIEW_TESTS,
            text,
            f"{SUITES} must discover {OVERVIEW_TESTS}",
        )
        self.assertRegex(
            text,
            r"python3 -m unittest discover",
            "suites.sh still discovers with unittest",
        )


if __name__ == "__main__":
    unittest.main()
