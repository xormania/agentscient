"""Triage 2026-09-11: `dispatch.sh --help` answers with its usage, exit 0,
instead of refusing `--help` as an unknown flag (it did, twice today)."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WRAPPER = ROOT / "ops" / "conductor" / "tools" / "dispatch.sh"


class DispatchWrapperAnswersHelp(unittest.TestCase):
    def _run(self, flag):
        return subprocess.run(["bash", str(WRAPPER), flag], cwd=ROOT,
                              capture_output=True, text=True, check=False, timeout=30)

    def test_help_prints_usage_and_exits_0(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                proc = self._run(flag)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("usage: dispatch.sh", proc.stdout)
                self.assertIn("--scope-file", proc.stdout)
                self.assertEqual(proc.stderr.strip(), "")

    def test_an_unknown_flag_still_refuses(self):
        proc = self._run("--status")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unknown flag", proc.stderr)


if __name__ == "__main__":
    unittest.main()
