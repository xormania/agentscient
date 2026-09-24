"""The one required gate cannot be skipped, moved or made advisory."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from ops.devlane.workflow.checks.ci_runners import HOSTED, RUNS_ON

ROOT = Path(__file__).resolve().parents[4]


class WorkflowGate(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((ROOT / ".github/workflows/ci.yml").read_text())

    def assert_contract(self, doc):
        self.assertEqual(set(doc["jobs"]), {"lane"})
        self.assertEqual(doc["on"], {
            "pull_request": {"types": ["opened", "synchronize", "reopened"], "branches": ["dev"]},
            "merge_group": {"branches": ["dev"]}, "push": {"branches": ["dev"]},
        })
        job = doc["jobs"]["lane"]
        self.assertEqual(job["runs-on"], RUNS_ON)
        self.assertEqual(job["timeout-minutes"], 4)
        for value in (doc, job):
            for key in ("defaults", "env", "if", "continue-on-error"):
                self.assertNotIn(key, value)
        steps = job["steps"]
        checkout = steps[0]
        self.assertEqual(checkout["uses"], "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1")
        self.assertEqual(checkout["with"], {"fetch-depth": 0, "persist-credentials": False})
        gates = [s for s in steps if s.get("id") == "verify"]
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0]["run"], "python3 -m ops.devlane.workflow.checks.ci lane")
        self.assertEqual(gates[0]["env"], {
            "TERM_WALL": "${{ vars.TERM_WALL }}", "GITHUB_TOKEN": "${{ github.token }}",
            "CI_RUNNER_MODE": "${{ vars.CI_RUNNER_MODE || 'hosted' }}",
            "CI_RUNNER_ENVIRONMENT": "${{ runner.environment }}",
        })
        for step in steps:
            for key in ("working-directory", "continue-on-error"):
                self.assertNotIn(key, step)
            if "if" in step:
                self.assertNotEqual(step.get("id"), "verify")
                self.assertIn(step["if"], (HOSTED, "${{ always() && steps.verify.outputs.receipt != '' }}"))
        self.assertEqual(steps[-1]["with"]["if-no-files-found"], "error")
        text = json.dumps(doc)
        for unnecessary in ("tmux", "bwrap", "bubblewrap", "setup-php", "ci_parallel"):
            self.assertNotIn(unnecessary, text)

    def test_required_gate_and_separate_manual_application_checks(self):
        self.assert_contract(self.doc)
        app = json.loads((ROOT / ".github/workflows/ci-app-manual.yml").read_text())
        self.assertEqual(app["on"], {"workflow_dispatch": {}})

    def test_execution_bypasses_are_detected(self):
        for mutation in (
            lambda d: d["jobs"]["lane"].update({"if": "false"}),
            lambda d: d["jobs"]["lane"].update({"continue-on-error": True}),
            lambda d: d["jobs"]["lane"]["steps"][-2].update({"run": "true"}),
            lambda d: d["jobs"]["lane"]["steps"][-2].update({"working-directory": "elsewhere"}),
            lambda d: d["jobs"]["lane"]["steps"][-2].update({"if": HOSTED}),
        ):
            doc = copy.deepcopy(self.doc)
            mutation(doc)
            with self.assertRaises(AssertionError):
                self.assert_contract(doc)
