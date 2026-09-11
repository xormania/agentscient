"""LD-19 (2026-09-11): a recorded extra attempt after a driver-caused cap.

Ladder fd103b's code stage reached its two-attempt cap because the
driver's own derived command failed (a discover over a support module),
not the worker. ``resume LADDER_ID --retry STAGE --because TEXT`` grants
that stage one further attempt; the grant is written on the stage row
(``retry``: because, at, by, from_attempt) and is spent once.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LADDER = ROOT / "ops" / "conductor" / "tools" / "ladder.py"


def _load():
    spec = importlib.util.spec_from_file_location("ladder_retry_under_test", LADDER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Stub:
    def __init__(self, retry, attempt=2):
        self.retry = retry
        self.agent = "Owner <owner@example.test>"
        self.rows = {"code": {"name": "code", "attempt": attempt, "outcome": "stopped"}}

    def row(self, name):
        return self.rows[name]


class TheRetryIsGrantedOnceAndRecorded(unittest.TestCase):
    def setUp(self):
        self.mod = _load()

    def test_no_retry_named_stays_capped(self):
        stub = _Stub(None)
        self.assertFalse(self.mod.Driver.retry_granted(stub, "code"))
        self.assertNotIn("retry", stub.rows["code"])

    def test_a_retry_for_another_stage_does_not_apply(self):
        stub = _Stub(("tests", "why"))
        self.assertFalse(self.mod.Driver.retry_granted(stub, "code"))

    def test_the_named_stage_gets_one_recorded_attempt(self):
        stub = _Stub(("code", "LD-19: the derived command, not the worker"))
        self.assertTrue(self.mod.Driver.retry_granted(stub, "code"))
        grant = stub.rows["code"]["retry"]
        self.assertEqual(grant["because"], "LD-19: the derived command, not the worker")
        self.assertEqual(grant["by"], "Owner <owner@example.test>")
        self.assertEqual(grant["from_attempt"], 2)
        self.assertRegex(grant["at"], r"^\d{8}T\d{6}Z$")  # the ladder's own utc_stamp shape
        self.assertFalse(self.mod.Driver.retry_granted(stub, "code"), "spent once")


class TheResumeArgumentsAreParsed(unittest.TestCase):
    def setUp(self):
        self.mod = _load()

    def test_plain_and_rescope(self):
        self.assertEqual(self.mod.resume_options(["resume", "id"]), (False, None))
        self.assertEqual(self.mod.resume_options(["resume", "id", "--rescope"]), (True, None))

    def test_retry_needs_a_stage_and_a_reason(self):
        self.assertEqual(
            self.mod.resume_options(["resume", "id", "--retry", "code", "--because", "LD-19"]),
            (False, ("code", "LD-19")),
        )
        for bad in (["resume", "id", "--retry", "code"],
                    ["resume", "id", "--retry", "nowhere", "--because", "x"],
                    ["resume", "id", "--because", "x"],
                    ["resume", "id", "--retry", "code", "--because", ""]):
            with self.subTest(args=bad), self.assertRaises(self.mod.Refused):
                self.mod.resume_options(bad)


if __name__ == "__main__":
    unittest.main()
