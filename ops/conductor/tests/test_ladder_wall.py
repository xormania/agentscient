"""LD-17 (2026-09-11): the ladder's wait wall comes from the job cap, not
from a record copy that carries no cap yet.

Measured: ladder 20260911T040533Z-ladder-fd103b stopped its tests-fix
stage (record 3ab0c7, cap 1800 s) with reason ``wall`` after
WALL_DEFAULT plus grace (900 + 300 s), while the job was 22 minutes in
and closing. The launcher writes ``caps.timeout`` into the worktree
record copy only at close, so the driver's read at wait time found
nothing and fell to WALL_DEFAULT for every stage.

Contract: ``Driver.stage_wall(stage, launched)`` returns the record
copy's cap when present, else the stage's job cap from
``ops/devlane/task/jobs.json``, else None (the caller applies
WALL_DEFAULT).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LADDER = ROOT / "ops" / "conductor" / "tools" / "ladder.py"


def _load():
    spec = importlib.util.spec_from_file_location("ladder_wall_under_test", LADDER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Stub:
    def __init__(self, worktree):
        self.worktree = worktree
        self.conf = {"WALL_DEFAULT": "900", "LADDER_WAIT_GRACE": "300"}


class TheWallComesFromTheJobCap(unittest.TestCase):
    def setUp(self):
        self.ladder = _load()
        self.tmp = Path(tempfile.mkdtemp())
        jobs = self.tmp / "ops" / "devlane" / "task"
        jobs.mkdir(parents=True)
        (jobs / "jobs.json").write_text(json.dumps({
            "author-tests": {"caps": {"timeout": 1800}},
            "implement": {"caps": {"timeout": 3600}},
            "check-tests": {"caps": {"timeout": 1800}},
            "security-audit": {"caps": {"timeout": 1200}},
            "adversarial-review": {"caps": {"timeout": 1800}},
        }))
        self.stub = _Stub(self.tmp)

    def wall(self, stage, launched):
        return self.ladder.Driver.stage_wall(self.stub, stage, launched)

    def test_a_record_copy_without_caps_uses_the_job_cap(self):
        self.assertEqual(self.wall("tests-fix", {}), 1800)
        self.assertEqual(self.wall("code", {"caps": {"cap-out": 500000}}), 3600)
        self.assertEqual(self.wall("security-re", {}), 1200)

    def test_a_record_copy_with_a_cap_wins(self):
        self.assertEqual(self.wall("tests-fix", {"caps": {"timeout": 1500.0}}), 1500.0)

    def test_an_unknown_stage_or_missing_registry_yields_none(self):
        self.assertIsNone(self.wall("no-such-stage", {}))
        (self.tmp / "ops" / "devlane" / "task" / "jobs.json").unlink()
        self.assertIsNone(self.wall("tests-fix", {}))


if __name__ == "__main__":
    unittest.main()
