"""Workflow execution contract; JSON is the standard-library-readable YAML subset.

Reused: testkit.world. The gate behavior lives in test_lane_checks; these
cases prove GitHub calls that gate unconditionally and retains release checks.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from ops.devlane.workflow.checks.ci_contexts import (
    DerivationError,
    workflow_job_names,
)
from ops.devlane.workflow.checks.ci_runners import HOSTED, RUNS_ON
from ops.testkit import World

ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
UPLOAD = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
RECORD_REFS = "git for-each-ref --format='%(refname:strip=3)' refs/remotes/origin/records/ | while read -r b; do git branch -f \"$b\" \"origin/$b\"; done"
FULL_GATE = "python3 -m ops.devlane.workflow.checks.ci lane"


def conditional_keys(value):
    if isinstance(value, dict):
        return ({key for key in value if key in {"if", "paths", "paths-ignore", "continue-on-error"}}
                | set().union(*(conditional_keys(child) for child in value.values())))
    if isinstance(value, list):
        return set().union(*(conditional_keys(child) for child in value))
    return set()


class CiTwoJobs(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.addCleanup(self.world.close)
        self.workflow = self.world.stage(WORKFLOW, "ci.yml")
        self.doc = json.loads(self.workflow.read_text())

    def assert_contract(self, doc):
        inspected = copy.deepcopy(doc)
        for job in inspected["jobs"].values():
            for step in job["steps"]:
                if step.get("if") == HOSTED:
                    self.assertNotIn("id", step)
                    self.assertTrue("uses" in step or "pip --isolated install" in step.get("run", ""))
                    step.pop("if")
            artifact = job["steps"][-1]
            self.assertEqual(artifact.pop("if"), "${{ always() && steps.verify.outputs.receipt != '' }}")
        self.assertEqual(conditional_keys(inspected), set())
        self.assertEqual(doc["on"], {
            "pull_request": {"types": ["opened", "synchronize", "reopened"], "branches": ["dev"]},
            "merge_group": {"branches": ["dev"]}, "push": {"branches": ["dev"]},
        })
        self.assertEqual(doc["permissions"], {"contents": "read", "actions": "read"})
        self.assertEqual(doc["concurrency"], {
            "group": "ci-${{ github.event_name }}-${{ github.event.pull_request.number || github.ref }}",
            "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
        })
        self.assertEqual(set(doc["jobs"]), {"lane", "app"})
        for name, job in doc["jobs"].items():
            self.assertEqual(job["runs-on"], RUNS_ON)
            self.assertEqual(job["timeout-minutes"], 15 if name == "lane" else 5)
            steps = job["steps"]
            actions = [step["uses"] for step in steps if "uses" in step]
            expected_setup = ["actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
                              "cue-lang/setup-cue@a93fa358375740cd8b0078f76355512b9208acb1" if name == "lane"
                              else "shivammathur/setup-php@f3e473d116dcccaddc5834248c87452386958240"]
            self.assertEqual(actions, [CHECKOUT, *expected_setup, UPLOAD])
            for step in steps:
                if step.get("uses") in expected_setup:
                    self.assertEqual(step.get("if"), HOSTED)
            self.assertEqual(steps[0]["uses"], CHECKOUT)
            self.assertIs(steps[0]["with"]["persist-credentials"], False)
            self.assertNotIn("defaults", job)
            self.assertNotIn("env", job)
            for step in steps:
                self.assertNotIn("working-directory", step)
            commands = [step["run"] for step in steps if "run" in step and step.get("if") != HOSTED]
            expected = ([RECORD_REFS] if name == "lane" else []) + [f"python3 -m ops.devlane.workflow.checks.ci {name}"]
            self.assertEqual(commands, expected)
            self.assertEqual(steps[0]["with"]["fetch-depth"], 0)
            gate = next(step for step in steps if step.get("id") == "verify")
            self.assertEqual(gate["env"], {"TERM_WALL": "${{ vars.TERM_WALL }}", "GITHUB_TOKEN": "${{ github.token }}",
                                           "CI_RUNNER_MODE": "${{ vars.CI_RUNNER_MODE || 'hosted' }}",
                                           "CI_RUNNER_ENVIRONMENT": "${{ runner.environment }}"})
            self.assertEqual(steps[-1]["with"], {"name": "${{ steps.verify.outputs.artifact }}",
                                              "path": "${{ steps.verify.outputs.receipt }}",
                                              "if-no-files-found": "error", "retention-days": 30})
        self.assertNotIn("defaults", doc)
        self.assertNotIn("env", doc)

    def test_the_workflow_executes_the_full_gate_and_application_checks(self):
        self.assert_contract(self.doc)

    def test_step_names_have_no_effect_on_the_contract(self):
        for job in self.doc["jobs"].values():
            for step in job["steps"]:
                step["name"] = "arbitrary display label"
        self.assert_contract(self.doc)

    def test_pr_readiness_derives_current_jobs_and_refuses_broken_json(self):
        self.assertEqual(workflow_job_names(ROOT), ["app", "lane"])
        for payload in ('{"jobs": {}}', '{"jobs": []}', '{"jobs": {"app": null}}', '{broken'):
            with self.subTest(payload=payload):
                self.world.plant_text("cwd/.github/workflows/ci.yml", payload)
                with self.assertRaises(DerivationError):
                    workflow_job_names(self.world.cwd)

    def test_disabled_partial_hidden_and_duplicated_execution_is_detected(self):
        mutations = {
            "disabled": lambda d: d["jobs"]["lane"]["steps"][-2].update(run="echo skipped"),
            "masked-failure": lambda d: d["jobs"]["lane"]["steps"][-2].update(run=FULL_GATE + " || true"),
            "partial": lambda d: d["jobs"]["lane"]["steps"][-2].update(run=FULL_GATE + " --suite ops/testkit/tests"),
            "conditional": lambda d: d["jobs"]["lane"]["steps"][-2].update({"if": "false"}),
            "ignored-failure": lambda d: d["jobs"]["lane"]["steps"][-2].update({"continue-on-error": True}),
            "omitted": lambda d: d["jobs"]["lane"]["steps"].pop(),
            "duplicated": lambda d: d["jobs"]["lane"]["steps"].insert(-1, d["jobs"]["lane"]["steps"][-2]),
            "app-disabled": lambda d: d["jobs"]["app"]["steps"][-2].update(run="true"),
            "path-filter": lambda d: d["on"]["pull_request"].update(paths=["ops/**"]),
            "ignored-path": lambda d: d["on"]["push"].update({"paths-ignore": ["docs/**"]}),
            "job-skip": lambda d: d["jobs"]["app"].update({"if": "false"}),
            "wrong-branch": lambda d: d["on"]["push"].update(branches=["master"]),
            "cancel-push": lambda d: d["concurrency"].update({"cancel-in-progress": True}),
            "wrong-runner": lambda d: d["jobs"]["lane"].update({"runs-on": "not-self-hosted"}),
            "wrong-directory": lambda d: d["jobs"]["lane"]["steps"][-2].update({"working-directory": "elsewhere"}),
        }
        for origin, mutate in mutations.items():
            doc = copy.deepcopy(self.doc)
            mutate(doc)
            with self.subTest(origin=origin), self.assertRaises((AssertionError, KeyError)):
                self.assert_contract(doc)
