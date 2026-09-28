"""The plan job's prompt quotes the first-run walkthrough.

Written from the contract (in/contract-plan-prompt.md) at
0cea17ab4023f80c92c99591e4aaf825f9bac98a, before the catalogue was
edited. The prompt names each environment the first run will meet and
the refusal that stands at each improvisation point.
"""

from __future__ import annotations

import json
import unittest

import support

JOBS_PATH = support.APP / "jobs.json"

WALKTHROUGH = "walkthrough of the first run"
ISOLATED_HOME = "the snapshot's isolated home"
TOOLS_CANNOT_FIND = "what tools then cannot find"
NO_NETWORK = "no network"
READ_ONLY_GIT = "the read-only git directory"
JOB_PROMPT_DEMANDS = "each job prompt's demands"
RUNNER_WORKSPACE = "the self-hosted runner's workspace"
IMPROVISE = "a worker could improvise"
REFUSAL_BESIDE = (
    "the refusal that must stand there is written beside it"
)


def _squish(text):
    return " ".join(text.split())


class _PlanJob(unittest.TestCase):
    def plan_prompt(self):
        self.assertTrue(JOBS_PATH.is_file(), f"jobs.json missing: {JOBS_PATH}")
        jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(jobs, dict)
        self.assertIn("plan", jobs)
        spec = jobs["plan"]
        self.assertIsInstance(spec, dict)
        prompt = spec.get("prompt")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip(), "plan prompt is empty")
        return prompt

    def words(self):
        return _squish(self.plan_prompt())


class PlanPromptQuotesTheFirstRunWalkthrough(_PlanJob):
    """Every named environment, and the refusal beside each improvisation."""

    def test_the_prompt_asks_for_a_walkthrough_of_the_first_run(self):
        self.assertIn(WALKTHROUGH, self.words())

    def test_the_walkthrough_names_the_snapshots_isolated_home(self):
        self.assertIn(ISOLATED_HOME, self.words())

    def test_the_walkthrough_names_what_tools_then_cannot_find(self):
        self.assertIn(TOOLS_CANNOT_FIND, self.words())

    def test_the_walkthrough_names_no_network(self):
        self.assertIn(NO_NETWORK, self.words())

    def test_the_walkthrough_names_the_read_only_git_directory(self):
        self.assertIn(READ_ONLY_GIT, self.words())

    def test_the_walkthrough_names_each_job_prompts_demands(self):
        self.assertIn(JOB_PROMPT_DEMANDS, self.words())

    def test_the_walkthrough_names_the_self_hosted_runners_workspace(self):
        self.assertIn(RUNNER_WORKSPACE, self.words())

    def test_the_walkthrough_names_where_a_worker_could_improvise(self):
        self.assertIn(IMPROVISE, self.words())

    def test_each_improvisation_point_has_its_refusal_written_beside_it(self):
        self.assertIn(REFUSAL_BESIDE, self.words())

    def test_every_walkthrough_sentence_is_present_together(self):
        required = (
            WALKTHROUGH,
            ISOLATED_HOME,
            TOOLS_CANNOT_FIND,
            NO_NETWORK,
            READ_ONLY_GIT,
            JOB_PROMPT_DEMANDS,
            RUNNER_WORKSPACE,
            IMPROVISE,
            REFUSAL_BESIDE,
        )
        self.assertGreater(len(required), 0)
        words = self.words()
        missing = [sentence for sentence in required if sentence not in words]
        self.assertEqual(
            missing, [],
            "plan prompt must quote every first-run walkthrough sentence; "
            f"missing {missing!r}",
        )


if __name__ == "__main__":
    unittest.main()
