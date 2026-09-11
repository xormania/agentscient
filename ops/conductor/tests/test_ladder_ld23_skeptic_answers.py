"""LD-23: the driver names the skeptic findings on the tests-fix dispatch.

Since the correction gate (PR 133) classifies a write job that follows a
check-tests record as a correction, the tests-fix stage needs one
``--answers`` key per skeptic finding, each disposed with a contract
citation, or the launcher refuses ``correction`` and the ladder stops with
record=none (ladder 20260911T213956Z-ladder-96e53f, 2026-09-11 21:59Z,
item 31 slice 1). The driver passed ``--answers`` for fix-tests and
fix-code only. ladder.py is the subject and is not read here; the fixture,
the cited stub and the stage_findings plant come from
test_ladder_lever_undisposed. One producer wrote the driver change and
this test (grant 144); the second-producer regression test is a dispatch
that follows.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from test_ladder_lever_undisposed import _finding, _UndisposedFixture  # noqa: E402

SKEPTIC_FINDINGS = (_finding("SKEP1"), _finding("SKEP2"))


class _SkepticFixture(_UndisposedFixture):
    """The skeptic says changes with two findings; the audits approve."""

    def plant_skeptic_changes(self, *, cited_all: bool = False) -> None:
        self.patch_plant(
            verdicts={"check-tests": "changes"},
            stage_findings={
                "check-tests": [dict(row) for row in SKEPTIC_FINDINGS],
            },
            cited_all=cited_all,
        )
        plant = self.load_plant()
        self.assertEqual(plant["verdicts"].get("check-tests"), "changes")
        planted = (plant.get("stage_findings") or {}).get("check-tests") or []
        self.assertEqual(len(planted), 2, planted)
        self.assertEqual(planted[0]["claim"], SKEPTIC_FINDINGS[0]["claim"])
        self.assertEqual(planted[1]["claim"], SKEPTIC_FINDINGS[1]["claim"])
        self.assertEqual(bool(plant.get("cited_all")), cited_all)

    def skeptic_keys(self) -> list[str]:
        self.assertIn("check-tests", self.dispatch_names())
        landed = self.closed_envelope("check-tests").get("findings") or []
        self.assertEqual(len(landed), 2, landed)
        keys = self.envelope_keys("check-tests")
        self.assertEqual(len(keys), 2, keys)
        return keys


class StopBeforeTestsFix(_SkepticFixture):
    """An undisposed skeptic finding stops the ladder before tests-fix."""

    def test_undisposed_skeptic_findings_stop_before_tests_fix(self):
        before_store = self.findings_store_snapshot()
        before_disp = self.dispositions_snapshot()
        self.plant_skeptic_changes()
        proc = self.run_ladder()
        keys = self.skeptic_keys()
        self.assert_stopped(
            proc, stage="tests-fix", record="none", reason="undisposed",
        )
        self.assert_output_names_keys(proc, keys)
        self.assertNotIn("tests-fix", self.dispatch_names())
        self.assert_driver_did_not_write_dispositions(before_store, before_disp)


class TestsFixNamesEveryKey(_SkepticFixture):
    """With every finding cited, tests-fix carries one --answers per key."""

    def test_tests_fix_argv_answers_every_skeptic_finding(self):
        self.plant_skeptic_changes(cited_all=True)
        proc = self.run_ladder()
        keys = self.skeptic_keys()
        self.assertIn("tests-fix", self.dispatch_names(), self.combined(proc))
        self.assert_answers_every_key("tests-fix", keys)
        self.assert_item1_shape("tests-fix")


if __name__ == "__main__":
    unittest.main()
