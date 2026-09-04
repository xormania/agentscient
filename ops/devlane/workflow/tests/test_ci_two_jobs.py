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
DEV_BRANCHES = ["dev"]
SELF_HOSTED = ["self-hosted"]

# Distinctive fragments of the contracted step order, matched against
# each step's name and run text. Alternatives in a tuple are one step.
# Matching is positional and unique: a concatenated decoy name is not
# six steps, and equal indexes are not order.
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

MASTER_TRIGGER_WORKFLOW = """\
name: ci
"on":
  pull_request:
    branches: [master]
    types: [opened, synchronize, reopened]
  merge_group:
  push:
    branches: [master]
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


def trigger_branches(spec: object) -> list[str] | None:
    """Branch filter of one event. None means no branches: key, i.e. all."""
    if spec is None or spec is True:
        return None
    if isinstance(spec, str):
        return [spec]
    if isinstance(spec, list):
        return [str(item) for item in spec]
    if isinstance(spec, dict):
        if "branches" not in spec:
            return None
        raw = spec["branches"]
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, list):
            return [str(item) for item in raw]
        raise AssertionError(f"branches is not a name or list: {raw!r}")
    raise AssertionError(f"trigger spec is not a filter: {spec!r}")


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


def blob_hits(blob: str, needles: tuple[str, ...]) -> bool:
    lowered = blob.lower()
    return any(needle.lower() in lowered for needle in needles)


def step_order_indexes(
    blobs: list[str],
    groups: tuple[tuple[str, ...], ...],
) -> list[int]:
    """One distinct step per contracted group, in that order.

    Length must match. Each group must hit exactly one blob, and the
    hit indexes must be 0..n-1. A concatenated decoy that satisfies
    every substring at one index is therefore not order.
    """
    if len(blobs) != len(groups):
        raise AssertionError(
            f"step count {len(blobs)} != contracted {len(groups)}: {blobs!r}"
        )
    indexes: list[int] = []
    for needles in groups:
        hits = [i for i, blob in enumerate(blobs) if blob_hits(blob, needles)]
        if len(hits) != 1:
            raise AssertionError(
                f"step {needles!r} hits {hits} in {blobs!r}"
            )
        indexes.append(hits[0])
    expected = list(range(len(groups)))
    if indexes != expected:
        raise AssertionError(
            f"step order {indexes} is not contracted order {expected}"
        )
    return indexes


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
                self.assertEqual(
                    labels,
                    SELF_HOSTED,
                    f"{name} runs-on={labels!r}",
                )

    def test_not_self_hosted_is_not_the_self_hosted_label(self):
        self.assertEqual(runs_on({"runs-on": "self-hosted"}), SELF_HOSTED)
        self.assertNotEqual(
            runs_on({"runs-on": "not-self-hosted"}),
            SELF_HOSTED,
        )
        self.assertNotEqual(
            runs_on({"runs-on": ["not-self-hosted"]}),
            SELF_HOSTED,
        )
        self.assertIn("self-hosted", "not-self-hosted")

    def test_triggers_are_pull_request_merge_group_and_push(self):
        on = trigger_map(self.load())
        self.assertEqual(set(on), set(TRIGGERS), set(on))
        self.assertEqual(
            trigger_branches(on["pull_request"]),
            DEV_BRANCHES,
            on["pull_request"],
        )
        self.assertEqual(
            trigger_branches(on["push"]),
            DEV_BRANCHES,
            on["push"],
        )
        merge_branches = trigger_branches(on["merge_group"])
        if merge_branches is not None:
            self.assertEqual(merge_branches, DEV_BRANCHES, on["merge_group"])

    def test_triggers_targeting_master_are_not_the_dev_set(self):
        with tempfile.TemporaryDirectory(prefix="ci-two-jobs-master-") as raw:
            path = Path(raw) / "ci.yml"
            _plant_bytes(path, MASTER_TRIGGER_WORKFLOW.encode("utf-8"))
            landed = path.read_text(encoding="utf-8")
            self.assertEqual(landed, MASTER_TRIGGER_WORKFLOW)
            on = trigger_map(load_workflow(path))
            self.assertEqual(set(on), set(TRIGGERS), set(on))
            self.assertEqual(trigger_branches(on["pull_request"]), ["master"])
            self.assertEqual(trigger_branches(on["push"]), ["master"])
            self.assertNotEqual(trigger_branches(on["pull_request"]), DEV_BRANCHES)
            self.assertNotEqual(trigger_branches(on["push"]), DEV_BRANCHES)

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
        self.assertEqual(
            step_order_indexes(blobs, LANE_STEP_NEEDLES),
            list(range(len(LANE_STEP_NEEDLES))),
            blobs,
        )

    def test_app_steps_are_the_named_steps_in_order(self):
        jobs = self.jobs()
        self.assertIn("app", set(jobs))
        blobs = step_blobs(jobs["app"])
        self.assertEqual(
            step_order_indexes(blobs, APP_STEP_NEEDLES),
            list(range(len(APP_STEP_NEEDLES))),
            blobs,
        )

    def test_a_concatenated_decoy_name_is_not_the_lane_step_order(self):
        decoy = "GITHUB_PATH term_wall ruff suites.sh closure literals"
        job = {
            "steps": [{"name": decoy, "run": "true"}]
            + [{"run": "true"}] * (len(LANE_STEP_NEEDLES) - 1),
        }
        blobs = step_blobs(job)
        self.assertEqual(len(blobs), len(LANE_STEP_NEEDLES))
        self.assertTrue(blob_hits(blobs[0], LANE_STEP_NEEDLES[0]))
        with self.assertRaises(AssertionError):
            step_order_indexes(blobs, LANE_STEP_NEEDLES)

    def test_a_concatenated_decoy_name_is_not_the_app_step_order(self):
        decoy = (
            "host toolchain composer validate composer install "
            "php -l kernel phpunit mate"
        )
        job = {
            "steps": [{"name": decoy, "run": "true"}]
            + [{"run": "true"}] * (len(APP_STEP_NEEDLES) - 1),
        }
        blobs = step_blobs(job)
        self.assertEqual(len(blobs), len(APP_STEP_NEEDLES))
        self.assertTrue(blob_hits(blobs[0], APP_STEP_NEEDLES[0]))
        with self.assertRaises(AssertionError):
            step_order_indexes(blobs, APP_STEP_NEEDLES)

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
