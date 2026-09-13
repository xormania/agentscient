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

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SUITES = REPO / "ops" / "bin" / "suites.sh"
RUFF_TOML = REPO / "ruff.toml"


class SuitesRunRuff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "tree"
        (self.root / "ops" / "bin").mkdir(parents=True)
        shutil.copy(SUITES, self.root / "ops" / "bin" / "suites.sh")
        shutil.copy(RUFF_TOML, self.root / "ruff.toml")

    def run_suites(self, path=None):
        env = dict(os.environ)
        if path is not None:
            env["PATH"] = path
        return subprocess.run(["bash", str(self.root / "ops" / "bin" / "suites.sh")],
                              cwd=self.root, env=env, capture_output=True, text=True,
                              timeout=120)

    def test_a_lint_fault_is_a_red_run_with_a_ruff_block(self):
        (self.root / "bad.py").write_text("import os\n")  # F401, unused import
        proc = self.run_suites()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("== ruff", proc.stdout)
        self.assertIn("F401", proc.stdout)

    def test_a_clean_tree_is_green_and_names_the_ruff_version(self):
        (self.root / "good.py").write_text("X = 1\n")
        proc = self.run_suites()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("== ruff", proc.stdout)
        self.assertRegex(proc.stdout, r"ruff \d+\.\d+")

    def test_a_host_without_ruff_is_red_with_the_absence_declared(self):
        """Absence is declared, never inferred: a host that cannot lint
        does not read green on lint."""
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        for name in ("bash", "python3", "mktemp", "cat", "rm", "dirname"):
            found = shutil.which(name)
            self.assertIsNotNone(found, f"{name} on PATH for the fixture")
            (bin_dir / name).symlink_to(found)
        (self.root / "bad.py").write_text("import os\n")
        proc = self.run_suites(path=str(bin_dir))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("== ruff", proc.stdout)
        self.assertIn("ABSENT", proc.stdout)


if __name__ == "__main__":
    unittest.main()
