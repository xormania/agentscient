"""The lint checker refuses rather than reporting a hollow clean.

Every case here is a way the check could have said "clean" without
having checked anything under the rules the repo actually enforces —
three of them were found by audit on 2026-08-22 and are pinned so
they cannot come back.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

CHECK = support.WF_DIR / "checks" / "lint.py"
REPO = support.WF_DIR.parent.parent.parent
CONTRACT = REPO / "ruff.toml"


class TheLintCheckRefusesHollowPasses(unittest.TestCase):
    def run_check(self, root, *paths):
        return subprocess.run(
            [sys.executable, str(CHECK), "--root", str(root), *paths],
            capture_output=True, text=True, check=False,
        )

    def sandbox(self, with_contract=True):
        raw = tempfile.mkdtemp(prefix="lint-check-")
        self.addCleanup(
            lambda: subprocess.run(["rm", "-rf", raw], check=False))
        root = Path(raw)
        if with_contract:
            self.assertTrue(CONTRACT.is_file(), CONTRACT)
            (root / "ruff.toml").write_bytes(CONTRACT.read_bytes())
        return root

    def test_a_clean_module_under_the_contract_passes(self):
        root = self.sandbox()
        (root / "m.py").write_text("def answer():\n    return 42\n")
        proc = self.run_check(root)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("clean", proc.stdout)

    def test_a_planted_finding_fails_and_is_counted_once(self):
        # The summary and fix-advice lines ruff prints are not
        # findings; counting them made one F401 read as three.
        root = self.sandbox()
        planted = "import os\n\n\ndef answer():\n    return 42\n"
        (root / "m.py").write_text(planted)
        self.assertIn("import os", (root / "m.py").read_text())

        proc = self.run_check(root)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("1 finding(s)", proc.stdout)
        self.assertIn("F401", proc.stdout)

    def test_a_tree_without_the_contract_is_refused(self):
        # Without ruff.toml, ruff falls back to its own defaults and
        # could report clean under rules nobody chose.
        root = self.sandbox(with_contract=False)
        (root / "m.py").write_text("def answer():\n    return 42\n")
        self.assertFalse((root / "ruff.toml").exists())

        proc = self.run_check(root)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("INVALID", proc.stdout)
        self.assertIn("ruff.toml", proc.stdout)

    def test_a_path_that_is_not_python_is_refused(self):
        # `--show-files` lists whatever the config reaches, including
        # ruff.toml itself, so a non-Python path once read as "one
        # file checked, clean".
        root = self.sandbox()
        (root / "m.py").write_text("def answer():\n    return 42\n")

        proc = self.run_check(root, "ruff.toml")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("zero Python files", proc.stdout)

    def test_a_missing_ruff_binary_is_refused_not_reported_clean(self):
        # The mode with the worst failure shape: a runner without ruff
        # must produce INVALID, never a clean pass over nothing.
        root = self.sandbox()
        (root / "m.py").write_text("def answer():\n    return 42\n")
        env = dict(os.environ, PATH="/nonexistent")
        proc = subprocess.run(
            [sys.executable, str(CHECK), "--root", str(root)],
            capture_output=True, text=True, check=False, env=env,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("INVALID", proc.stdout)

    def test_the_contract_and_not_ruffs_defaults_decides(self):
        # DTZ is selected by ruff.toml and is NOT in ruff's defaults,
        # so a checker that quietly ran isolated — or dropped the
        # config — would call this file clean.
        root = self.sandbox()
        (root / "m.py").write_text(
            "import datetime\n\n\ndef now():\n"
            "    return datetime.datetime.now()\n")
        proc = self.run_check(root)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("DTZ", proc.stdout)

    def test_the_repo_itself_passes_under_its_own_contract(self):
        proc = self.run_check(REPO)
        self.assertEqual(proc.returncode, 0, proc.stdout[-2000:])
        self.assertRegex(proc.stdout, r"clean — [1-9]\d* file")


if __name__ == "__main__":
    unittest.main()
