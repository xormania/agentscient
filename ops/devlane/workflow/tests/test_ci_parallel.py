"""Complete dev evidence across jobs; missing work can never aggregate green."""

from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone

from ops.devlane.workflow.checks import ci_parallel as parallel
from ops.testkit import Check, World


class ParallelEvidence(unittest.TestCase):
    def test_native_duration_includes_setup_and_refuses_four_minute_overrun(self):
        now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        for seconds, passes in ((239, True), (240, True), (241, False)):
            jobs = [{"started_at": (now - timedelta(seconds=seconds)).isoformat()}]
            if passes:
                self.assertEqual(parallel.elapsed_seconds(jobs, now), seconds)
            else:
                with self.assertRaisesRegex(ValueError, "four minutes"):
                    parallel.elapsed_seconds(jobs, now)
        with self.assertRaises(ValueError):
            parallel.elapsed_seconds([], now)

    def setUp(self):
        self.world = World()
        self.addCleanup(self.world.close)
        self.checks = [Check(f"case-{i}", ("true",), 30) for i in range(12)]
        self.parts = parallel.partition(self.checks, root=self.world.cwd)
        self.context = {"repository": "example/repo", "run_id": 7, "event_revision": "a" * 40,
                        "mode": "hosted", "attempt": 2}
        self.jobs = {name: {"result": "success"} for name in parallel.JOBS}
        self.receipts = []
        for name, checks in self.parts.items():
            self.receipts.append({"kind": name, "repository": "example/repo", "run_id": 7,
                                  "attempt": 1, "event_revision": "a" * 40, "exit": 0,
                                  "inputs": {"runner_environment": {"requested_mode": "hosted"}},
                                  "plan": sorted(c.name for c in checks),
                                  "results": [{"name": c.name, "exit": 0, "mode": "executed"} for c in checks]})

    def test_complete_disjoint_partition_keeps_new_checks(self):
        self.assertEqual(sorted(c.name for part in self.parts.values() for c in part),
                         sorted(c.name for c in self.checks))
        added = parallel.partition([*self.checks, Check("new", ("true",), 30)], root=self.world.cwd)
        self.assertEqual(sum(c.name == "new" for part in added.values() for c in part), 1)
        self.assertEqual(parallel.validate(self.parts, self.receipts, self.jobs, self.context), 12)

    def test_failed_missing_duplicate_wrong_candidate_and_wrong_mode_refuse(self):
        faults = {
            "missing-job": lambda r, j: j.pop(parallel.JOBS[0]),
            "failed-job": lambda r, j: j[parallel.JOBS[0]].update(result="failure"),
            "missing-receipt": lambda r, j: r.pop(),
            "missing-case": lambda r, j: r[0]["results"].pop(),
            "duplicate-case": lambda r, j: r[0]["results"].append(r[0]["results"][0]),
            "duplicate-receipt": lambda r, j: r.append(r[0]),
            "failed-case": lambda r, j: r[0]["results"][0].update(exit=1),
            "wrong-source": lambda r, j: r[0].update(event_revision="b" * 40),
            "wrong-run": lambda r, j: r[0].update(run_id=8),
            "wrong-mode": lambda r, j: r[0]["inputs"]["runner_environment"].update(requested_mode="local"),
            "future-attempt": lambda r, j: r[0].update(attempt=3),
        }
        for name, mutate in faults.items():
            with self.subTest(name=name):
                receipts, jobs = copy.deepcopy(self.receipts), copy.deepcopy(self.jobs)
                mutate(receipts, jobs)
                with self.assertRaises(ValueError):
                    parallel.validate(self.parts, receipts, jobs, self.context)
