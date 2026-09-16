"""suites.sh runs ruff on the host as the CI lane job does.

Owner, 2026-09-13 (ruling 4): two CI reds the day before were lint on a
locally green tree, because ops/bin/suites.sh ran no ruff while the lane
job runs `ruff check .`. Written by hand under wall grant 211, one
producer, the second producer absent by the owner's word. The script is
copied into a scratch tree whose only suite directories are absent, so
the run is the lint block alone; red at the base because no `== ruff`
block exists and a lint fault exits 0.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from ops.testkit import World, run

REPO = Path(__file__).resolve().parents[4]
SUITES = REPO / "ops" / "bin" / "suites.sh"
RUFF_TOML = REPO / "ruff.toml"


class SuitesRunRuff(unittest.TestCase):
    def setUp(self):
        try:
            self.world = World(host_path=False, prefix="suites-ruff-")
        except TypeError:
            self.world = World(prefix="suites-ruff-")
        self.addCleanup(self.world.close)
        self.root = self.world.cwd
        self.world.plant_bytes("cwd/ops/bin/suites.sh", SUITES.read_bytes())
        self.world.plant_bytes("cwd/ruff.toml", RUFF_TOML.read_bytes())
        for name in ("bash", "python3", "mktemp", "cat", "rm", "dirname"):
            self.world.tools.wrap(name)

    def run_suites(self, path=None):
        extra = {"PATH": path if path is not None else str(self.world.bin)}
        return run(
            ["bash", str(self.root / "ops" / "bin" / "suites.sh")],
            cwd=self.root,
            env=self.world.env(extra),
            timeout=120,
        )

    def test_a_lint_fault_is_a_red_run_with_a_ruff_block(self):
        self.world.plant_text("cwd/bad.py", "import os\n")  # F401, unused import
        self.world.tools.plant(
            "ruff",
            responses=[
                {"match": ["--version"], "stdout": "ruff 0.8.0\n"},
                {
                    "match": ["check"],
                    "stdout": "bad.py:1:8: F401 [*] `os` imported but unused\n",
                    "exit": 1,
                },
            ],
        )
        proc = self.run_suites()
        self.assertEqual(proc.exit, 1, proc.stdout + proc.stderr)
        self.assertIn("== ruff", proc.stdout)
        self.assertIn("F401", proc.stdout)

    def test_a_clean_tree_is_green_and_names_the_ruff_version(self):
        self.world.plant_text("cwd/good.py", "X = 1\n")
        self.world.tools.plant(
            "ruff",
            responses=[
                {"match": ["--version"], "stdout": "ruff 0.8.0\n"},
                {"match": ["check"], "stdout": "", "exit": 0},
            ],
        )
        proc = self.run_suites()
        self.assertEqual(proc.exit, 0, proc.stdout + proc.stderr)
        self.assertIn("== ruff", proc.stdout)
        self.assertRegex(proc.stdout, r"ruff \d+\.\d+")

    def test_a_host_without_ruff_is_red_with_the_absence_declared(self):
        """Absence is declared, never inferred: a host that cannot lint
        does not read green on lint."""
        self.world.plant_text("cwd/bad.py", "import os\n")
        proc = self.run_suites(path=str(self.world.bin))
        self.assertEqual(proc.exit, 1, proc.stdout + proc.stderr)
        self.assertIn("== ruff", proc.stdout)
        self.assertIn("ABSENT", proc.stdout)


if __name__ == "__main__":
    unittest.main()
