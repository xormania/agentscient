import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LADDER_PATH = ROOT / "ops" / "conductor" / "tools" / "ladder.py"


def load_ladder():
    module_name = "ladder_wall_from_job_cap_driver"
    spec = importlib.util.spec_from_file_location(module_name, LADDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load ladder driver from {LADDER_PATH}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


class LadderWallFromJobCapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ladder = load_ladder()

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.worktree = Path(self.temporary_directory.name)
        self.driver = object.__new__(self.ladder.Driver)
        self.driver.worktree = self.worktree

    def write_jobs(self, jobs):
        registry = self.worktree / "ops" / "devlane" / "task" / "jobs.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps(jobs), encoding="utf-8")
        return registry

    def test_record_copy_cap_wins_over_the_job_registry(self):
        self.write_jobs({"author-tests": {"caps": {"timeout": 91}}})

        wall = self.driver.stage_wall(
            "tests", {"caps": {"timeout": 17}}
        )

        self.assertEqual(17, wall)

    def test_tests_stage_uses_its_job_cap_when_record_has_no_cap(self):
        self.write_jobs({"author-tests": {"caps": {"timeout": 23}}})

        wall = self.driver.stage_wall("tests", {})

        self.assertEqual(23, wall)

    def test_review_stage_uses_its_job_cap_when_record_has_no_cap(self):
        self.write_jobs({"security-audit": {"caps": {"timeout": 29}}})

        wall = self.driver.stage_wall("security", {})

        self.assertEqual(29, wall)

    def test_stage_absent_from_dispatch_table_has_no_cap(self):
        stage = "not-a-dispatch-stage"
        self.assertNotIn(stage, self.ladder.DISPATCH_STAGES)
        self.write_jobs({"author-tests": {"caps": {"timeout": 31}}})

        wall = self.driver.stage_wall(stage, {})

        self.assertIsNone(wall)

    def test_missing_job_registry_has_no_cap(self):
        wall = self.driver.stage_wall("tests", {})

        self.assertIsNone(wall)

    def test_unparseable_job_registry_has_no_cap(self):
        registry = self.write_jobs({})
        registry.write_text("not json", encoding="utf-8")

        wall = self.driver.stage_wall("tests", {})

        self.assertIsNone(wall)

    def test_job_without_timeout_has_no_cap(self):
        self.write_jobs({"author-tests": {"caps": {"memory": 512}}})

        wall = self.driver.stage_wall("tests", {})

        self.assertIsNone(wall)


if __name__ == "__main__":
    unittest.main()
