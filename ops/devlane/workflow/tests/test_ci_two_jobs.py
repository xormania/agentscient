"""CI as two always-on jobs, lane and app.

Contract: fix scope item 34. The workflow `.github/workflows/ci.yml` is
the subject. Tests load it as YAML and plant copies under a temporary
directory; they never write the live workflow or the conductor store.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"

TRIGGERS = ("pull_request", "merge_group", "push")
JOBS = ("lane", "app")

# Distinctive fragments of the contracted step order, matched against
# each step's name and run text. Alternatives in a tuple are one step.
LANE_STEP_NEEDLES = (
    ("GITHUB_PATH", ".local/bin", "user toolchain"),
    ("term_wall", "term wall"),
    ("ruff",),
    ("suites.sh",),
    ("closure",),
    ("literals",),
)
APP_STEP_NEEDLES = (
    ("host toolchain", "php -v", "composer --version"),
    ("composer validate",),
    ("composer install",),
    ("php -l", "php lint"),
    ("kernel",),
    ("phpunit",),
    ("mate",),
)

TWO_JOB_WORKFLOW = """\
name: ci
"on":
  pull_request:
    branches: [dev]
    types: [opened, synchronize, reopened]
  merge_group:
  push:
    branches: [dev]
jobs:
  lane:
    runs-on: self-hosted
    steps:
      - run: echo lane
  app:
    runs-on: self-hosted
    steps:
      - run: echo app
"""


def _plant_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    landed = path.read_bytes()
    if landed != data:
        raise AssertionError(f"plant did not land intact: {path}")
    if len(landed) != len(data):
        raise AssertionError(f"plant length drifted: {path}")


def load_workflow(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise AssertionError(f"workflow is not a mapping: {path}")
    return doc


def trigger_map(doc: dict) -> dict:
    if "on" in doc:
        on = doc["on"]
    elif True in doc:
        # PyYAML 1.1 treats the unquoted key `on` as the boolean True.
        on = doc[True]
    else:
        raise AssertionError("workflow has no on: triggers")
    if isinstance(on, dict):
        return on
    if isinstance(on, list):
        return {name: {} for name in on}
    if isinstance(on, str):
        return {on: {}}
    raise AssertionError(f"workflow on: is not a trigger map: {on!r}")


def paths_locations(obj, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}" if path else str(key)
            if key == "paths":
                found.append(here)
            found.extend(paths_locations(value, here))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            found.extend(paths_locations(value, f"{path}[{index}]"))
    return found


def job_ifs(jobs: dict) -> list[str]:
    found: list[str] = []
    for name, job in jobs.items():
        if isinstance(job, dict) and "if" in job:
            found.append(str(name))
    return found


def runs_on(job: dict) -> list[str]:
    raw = job.get("runs-on")
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def step_blob(step: object) -> str:
    if not isinstance(step, dict):
        return str(step)
    parts = []
    for key in ("name", "run", "uses"):
        value = step.get(key)
        if value:
            parts.append(str(value))
    return "\n".join(parts)


def step_blobs(job: dict) -> list[str]:
    steps = job.get("steps") or []
    if not isinstance(steps, list):
        raise AssertionError(f"job steps is not a list: {steps!r}")
    return [step_blob(step) for step in steps]


def first_match_index(blobs: list[str], needles: tuple[str, ...]) -> int:
    lowered = [blob.lower() for blob in blobs]
    want = tuple(n.lower() for n in needles)
    for index, blob in enumerate(lowered):
        if any(needle in blob for needle in want):
            return index
    return -1


class CiTwoJobs(unittest.TestCase):
    def load(self) -> dict:
        self.assertTrue(WORKFLOW.is_file(), f"RED: workflow is absent: {WORKFLOW}")
        return load_workflow(WORKFLOW)

    def jobs(self) -> dict:
        jobs = self.load().get("jobs")
        self.assertIsInstance(jobs, dict, f"jobs is not a mapping: {jobs!r}")
        self.assertTrue(jobs, "workflow declares no jobs")
        return jobs

    def test_jobs_are_exactly_lane_and_app(self):
        names = set(self.jobs())
        self.assertEqual(names, set(JOBS), names)
        self.assertEqual(len(names), 2, names)

    def test_both_jobs_run_on_self_hosted_runners(self):
        jobs = self.jobs()
        names = set(jobs)
        for name in JOBS:
            with self.subTest(job=name):
                self.assertIn(name, names)
                labels = runs_on(jobs[name])
                self.assertTrue(
                    any("self-hosted" in label for label in labels),
                    f"{name} runs-on={labels!r}",
                )

    def test_triggers_are_pull_request_merge_group_and_push(self):
        on = trigger_map(self.load())
        self.assertEqual(set(on), set(TRIGGERS), set(on))

    def test_workflow_has_no_paths_filter(self):
        doc = self.load()
        found = paths_locations(doc)
        self.assertEqual(found, [], f"paths: filter present at {found}")

    def test_neither_job_has_a_job_level_if(self):
        found = job_ifs(self.jobs())
        self.assertEqual(found, [], f"job-level if: on {found}")

    def test_lane_steps_are_the_named_steps_in_order(self):
        jobs = self.jobs()
        self.assertIn("lane", set(jobs))
        blobs = step_blobs(jobs["lane"])
        self.assertGreaterEqual(
            len(blobs),
            len(LANE_STEP_NEEDLES),
            f"lane has too few steps: {blobs!r}",
        )
        indexes = []
        for needles in LANE_STEP_NEEDLES:
            index = first_match_index(blobs, needles)
            self.assertGreaterEqual(
                index,
                0,
                f"lane missing step {needles!r} in {blobs!r}",
            )
            indexes.append(index)
        self.assertEqual(indexes, sorted(indexes), indexes)

    def test_app_steps_are_the_named_steps_in_order(self):
        jobs = self.jobs()
        self.assertIn("app", set(jobs))
        blobs = step_blobs(jobs["app"])
        self.assertGreaterEqual(
            len(blobs),
            len(APP_STEP_NEEDLES),
            f"app has too few steps: {blobs!r}",
        )
        indexes = []
        for needles in APP_STEP_NEEDLES:
            index = first_match_index(blobs, needles)
            self.assertGreaterEqual(
                index,
                0,
                f"app missing step {needles!r} in {blobs!r}",
            )
            indexes.append(index)
        self.assertEqual(indexes, sorted(indexes), indexes)

    def test_planted_paths_filter_is_detected(self):
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-paths-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, TWO_JOB_WORKFLOW.encode("utf-8"))
            landed = path.read_text(encoding="utf-8")
            self.assertEqual(landed, TWO_JOB_WORKFLOW)
            doc = load_workflow(path)
            self.assertEqual(paths_locations(doc), [])
            on = trigger_map(doc)
            self.assertIsInstance(on["pull_request"], dict)
            on["pull_request"]["paths"] = ["ops/**"]
            self.assertIn("paths", on["pull_request"])
            self.assertEqual(
                paths_locations({"on": on}),
                ["on.pull_request.paths"],
            )

    def test_planted_job_level_if_is_detected(self):
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-if-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, TWO_JOB_WORKFLOW.encode("utf-8"))
            landed = path.read_text(encoding="utf-8")
            self.assertEqual(landed, TWO_JOB_WORKFLOW)
            doc = load_workflow(path)
            jobs = doc["jobs"]
            self.assertEqual(job_ifs(jobs), [])
            jobs["lane"]["if"] = "github.event_name == 'push'"
            self.assertIn("if", jobs["lane"])
            self.assertEqual(job_ifs(jobs), ["lane"])
            self.assertNotIn("if", jobs["app"])


if __name__ == "__main__":
    unittest.main()
