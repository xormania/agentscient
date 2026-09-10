"""Frozen criteria and the draft-dev terminal path.

Written from FINDING-ADMISSION.md §Refusals, completion and independent
acceptance. ladder.sh finish WORK_ORDER is the manual terminal
entrypoint. GitHub/land stay mocked by the inherited ladder fixture.

Intended reds: finish is an unknown start form; missing declaration
does not refuse admission-criteria; a failed terminal still dispatches
another review.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from test_ladder_lever import BRANCH, _LadderFixture

DISPATCH_TESTS = Path(__file__).resolve().parents[2] / "devlane" / "dispatch" / "tests"
if str(DISPATCH_TESTS) not in sys.path:
    sys.path.insert(0, str(DISPATCH_TESTS))
import admission_enforcement_support as aes  # noqa: E402


class TerminalDeclarationShape(unittest.TestCase):
    """GREEN: terminal object is exactly draft-pr into dev."""

    def test_terminal_is_draft_pr_into_dev(self):
        self.assertEqual(aes.TERMINAL, {"action": "draft-pr", "base": "dev"})
        body = aes.work_order(
            ident="WO-term-aa41",
            branch="work",
            base_ref="a" * 40,
            scope={"path": "owner-scope.md", "sha256": "b" * 64},
            authority=[{"path": "addendum.md", "sha256": "c" * 64}],
            test_scope=["ops/conductor/tests/"],
            fixture=[aes.command_row("fx", "true", [])],
            acceptance=[aes.command_row("ac", "true", [])],
            final=[aes.command_row("fn", "ops/bin/suites.sh", [])],
            reviews=[{"slot": "check-tests", "job": "check-tests"}],
        )
        self.assertEqual(body["terminal"], aes.TERMINAL)
        self.assertEqual(body["final"][0]["inputs"], [])
        with self.assertRaises(ValueError):
            aes.work_order(
                ident="WO-term-aa41",
                branch="work",
                base_ref="a" * 40,
                scope={"path": "owner-scope.md", "sha256": "b" * 64},
                authority=[{"path": "addendum.md", "sha256": "c" * 64}],
                test_scope=["ops/conductor/tests/"],
                fixture=[aes.command_row("fx2", "true", [])],
                acceptance=[aes.command_row("ac2", "true", [])],
                final=[aes.command_row("fn2", "ops/bin/suites.sh", [])],
                reviews=[{"slot": "check-tests", "job": "check-tests"}],
                terminal={"action": "merge", "base": "dev"},
            )


class LadderFinishIsTheManualTerminal(_LadderFixture):
    def test_finish_without_a_work_order_is_admission_criteria(self):
        proc = self.invoke(["finish"])
        text = self.combined(proc)
        self.assertEqual((proc.stdout or "").strip(), "")
        self.assertEqual(proc.returncode, 2, text)
        self.assertIn("admission-criteria", (proc.stderr or "").lower())
        self.assertIn("expected", (proc.stderr or "").lower())
        self.assertIn("needed", (proc.stderr or "").lower())

    def test_finish_does_not_dispatch_another_review(self):
        wo = self.scratch / "work-order.json"
        body = aes.work_order(
            ident="WO-term-aa41",
            branch=BRANCH,
            base_ref=self.git("rev-parse", "HEAD", cwd=self.wt).stdout.strip(),
            scope={"path": "scope.md", "sha256": aes.sha256_file(self.scope_path)},
            authority=[{"path": "scope.md", "sha256": aes.sha256_file(self.scope_path)}],
            test_scope=["ops/conductor/tests/"],
            fixture=[aes.command_row("fx-term", "true", [])],
            acceptance=[aes.command_row("ac-term", "true", [])],
            final=[aes.command_row("fn-term", "ops/bin/suites.sh", [])],
            reviews=[{"slot": "check-tests", "job": "check-tests"}],
        )
        aes.write_json(wo, body)
        before = self.dispatch_count(job="check-tests", stage="check-tests")
        proc = self.invoke(["finish", "WO-term-aa41"])
        text = self.combined(proc)
        self.assertNotIn("unrecognized", text.lower(), text)
        after = self.dispatch_count(job="check-tests", stage="check-tests")
        self.assertEqual(after, before, text)
        if proc.returncode == 0:
            self.assertIn("pr=", (proc.stdout or ""))
            self.assertIn("/pull/", (proc.stdout or ""))
        else:
            self.assertIn("admission-", text.lower())
            self.assertIn("expected", text.lower())

    def test_a_failed_terminal_retry_adds_no_review(self):
        before = self.dispatch_names()
        first = self.invoke(["finish", "WO-term-aa41"])
        second = self.invoke(["finish", "WO-term-aa41"])
        self.assertEqual(self.dispatch_names(), before)
        for proc in (first, second):
            text = self.combined(proc)
            self.assertNotRegex(
                text.lower(),
                r"check-tests|security-audit|adversarial-review",
            )


if __name__ == "__main__":
    unittest.main()
