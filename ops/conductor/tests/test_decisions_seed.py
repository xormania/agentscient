"""The tracked decisions seed is the record; SQLite derives from it."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from ops.testkit import World, run

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "ops" / "conductor" / "tools" / "decisions.py"
SIBLINGS = ("instrument.py", "laneconf.py")
AGENT = "Test Owner <owner@example.invalid>"
SEED_ID = "D-SEED-1"


class DecisionsSeed(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="decisions-seed-")
        self.addCleanup(self.world.close)
        self.repo = self.world.path("repo")
        self.tools = self.repo / "ops" / "conductor" / "tools"
        staged = self.world.stage(TOOL, siblings=SIBLINGS)
        for source in staged.parent.iterdir():
            self.world.plant_bytes(self.tools / source.name, source.read_bytes())
        self.tool = self.tools / "decisions.py"
        self.seed = self.repo / "ops" / "conductor" / "decisions.seed.json"
        self.conf = self.world.plant_text("lane.conf", "LANE_NAME='agentscient'\n")
        self.env = self.world.env(extra={
            "LANE_CONF": str(self.conf),
            "WF_AGENT": AGENT,
        })

    def invoke(self, *args: str):
        return run(
            [sys.executable, str(self.tool), *args],
            cwd=self.repo,
            env=self.env,
            timeout=60,
        )

    def test_add_rewrites_the_seed_from_the_store(self):
        self.world.plant_text(self.seed, "[]\n")
        proc = self.invoke(
            "add", "D-ADD-1", "Should this row reach the seed",
            "--home", "ops/example.md",
        )
        self.assertEqual(proc.exit, 0, proc.stderr)
        rows = json.loads(self.seed.read_text(encoding="utf-8"))
        # Planted fault: an add that writes only SQLite leaves this list empty.
        self.assertEqual([row["id"] for row in rows], ["D-ADD-1"])

    def test_a_seed_only_id_loads_into_the_store_on_first_read(self):
        row = {
            "blocked_on": None,
            "created_at": "2026-01-02T03:04:05Z",
            "created_by": AGENT,
            "decided_at": None,
            "decided_by": None,
            "evidence": None,
            "home": "ops/seed.md",
            "id": SEED_ID,
            "question": "Should this seed row load",
            "recorded_by": AGENT,
            "standing": "proposed",
            "superseded_by": None,
            "supersedes": None,
        }
        self.world.plant_text(self.seed, json.dumps([row]) + "\n")
        first = self.invoke("show", SEED_ID)
        self.assertEqual(first.exit, 0, first.stderr)
        self.seed.unlink()
        second = self.invoke("show", SEED_ID)
        self.assertEqual(second.exit, 0, second.stderr)
        self.assertIn(SEED_ID, second.stdout)

    def test_export_write_accepts_the_tracked_or_an_explicit_path(self):
        self.world.plant_text(self.seed, "[]\n")
        added = self.invoke(
            "add", "D-ADD-1", "Should this row reach the seed",
            "--home", "ops/example.md",
        )
        self.assertEqual(added.exit, 0, added.stderr)
        explicit = self.world.path("export/decisions.json")
        written = self.invoke("export", "--write", str(explicit))
        self.assertEqual(written.exit, 0, written.stderr)
        self.assertEqual(explicit.read_bytes(), self.seed.read_bytes())
        self.world.plant_text(self.seed, "[]\n")
        default = self.invoke("export", "--write")
        self.assertEqual(default.exit, 0, default.stderr)
        self.assertEqual(
            [row["id"] for row in json.loads(self.seed.read_text())],
            ["D-ADD-1"],
        )


if __name__ == "__main__":
    unittest.main()
