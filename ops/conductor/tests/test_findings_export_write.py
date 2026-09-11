"""Triage 2026-09-11: `findings.py export --write [PATH]` regenerates the
export file; plain `export` still prints and writes nothing."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "ops" / "conductor" / "tools" / "findings.py"


class ExportWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = dict(os.environ, XDG_STATE_HOME=str(self.tmp / "state"),
                        WF_AGENT="Tester <t@x.y>")

    def _run(self, *argv):
        return subprocess.run([sys.executable, str(TOOL), "export", *argv], cwd=ROOT,
                              env=self.env, capture_output=True, text=True, check=False, timeout=60)

    def test_write_to_an_explicit_path(self):
        out = self.tmp / "out" / "findings.jsonl"
        proc = self._run("--write", str(out))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(out.is_file())
        self.assertIn(str(out), proc.stdout)
        self.assertIn("wrote 0 row(s)", proc.stdout)

    def test_plain_export_prints_and_writes_nothing(self):
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # the store directory under XDG_STATE_HOME is created on connect;
        # no export file appears anywhere under the temp root
        self.assertEqual([p.name for p in self.tmp.rglob("*.jsonl")], [])

    def test_write_with_two_paths_refuses_arguments(self):
        proc = self._run("--write", "a", "b")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("arguments:", proc.stderr)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
