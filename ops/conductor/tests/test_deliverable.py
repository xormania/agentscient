"""The deliverable lock lever: set, show, clear; identity for writes; the wire."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEVER = ROOT / "ops" / "conductor" / "tools" / "deliverable.py"


class TheLockLever(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="deliverable-"))
        self.xdg = self.tmp / "xdg"
        conf = self.tmp / "lane.conf"
        conf.write_text("LANE_NAME='testlane'\n")
        self.env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.tmp / "home"),
                    "XDG_STATE_HOME": str(self.xdg), "LANE_CONF": str(conf)}
        self.lock = self.xdg / "testlane" / "deliverable.json"

    def run_lever(self, *args, identity=True):
        env = dict(self.env)
        if identity:
            env["WF_AGENT"] = "Owner <owner@example.test>"
        return subprocess.run([sys.executable, str(LEVER), *args], env=env, capture_output=True, text=True, check=False)

    def test_set_writes_the_lock_and_show_reads_it(self):
        proc = self.run_lever("set", "lane/a", "lane/b", "--why", "the slices")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(self.lock.read_text())
        self.assertEqual(data["branches"], ["lane/a", "lane/b"])
        self.assertEqual(data["why"], "the slices")
        self.assertEqual(data["by"], "Owner <owner@example.test>")
        self.assertRegex(data["at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        shown = self.run_lever("show", identity=False)
        self.assertEqual(shown.returncode, 0)
        self.assertIn("lane/a", shown.stdout)

    def test_clear_removes_it_and_show_says_no_lock(self):
        self.run_lever("set", "lane/a", "--why", "x")
        proc = self.run_lever("clear")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.lock.exists())
        self.assertEqual(self.run_lever("show", identity=False).stdout.strip(), "no lock")

    def test_writes_need_identity_and_refuse_on_the_wire(self):
        for args in (("set", "lane/a", "--why", "x"), ("clear",)):
            with self.subTest(args=args):
                proc = self.run_lever(*args, identity=False)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")
                self.assertRegex(proc.stderr.strip(), r"^identity: expected .*; found .*; needed .*$")
                self.assertEqual(len(proc.stderr.strip().splitlines()), 1)

    def test_set_needs_branches_and_a_reason(self):
        for args in (("set",), ("set", "lane/a"), ("set", "--why", "x")):
            with self.subTest(args=args):
                proc = self.run_lever(*args)
                self.assertEqual(proc.returncode, 2)
                self.assertTrue(proc.stderr.startswith("arguments: expected"), proc.stderr)


if __name__ == "__main__":
    unittest.main()
