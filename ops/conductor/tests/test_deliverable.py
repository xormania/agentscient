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

    def test_remove_lifts_one_session_branch_and_leaves_the_others(self):
        """Owner, 2026-09-13 ("minimize parallel work conflicts"; LD-28): a
        session that lands removes its own branch; the lock kept naming
        every landed branch because clear was the only exit and clear wipes
        every session's entry at once."""
        self.run_lever("set", "lane/session-a", "--why", "session a")
        self.run_lever("add", "lane/session-b", "--why", "session b")
        proc = self.run_lever("remove", "lane/session-a")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "removed lane/session-a; locked lane/session-b")
        data = json.loads(self.lock.read_text())
        self.assertEqual(data["branches"], ["lane/session-b"])
        self.assertIn("session b", data["why"])
        again = self.run_lever("remove", "lane/session-a")
        self.assertEqual(again.returncode, 2, again.stdout)
        self.assertRegex(again.stderr.strip(), r"^absent: expected .+; found .+; needed .+$")
        last = self.run_lever("remove", "lane/session-b")
        self.assertEqual(last.returncode, 0, last.stderr)
        self.assertEqual(last.stdout.strip(), "removed lane/session-b; no lock")
        self.assertFalse(self.lock.exists(), "the last branch removed lifts the lock")
        self.assertEqual(self.run_lever("show", identity=False).stdout.strip(), "no lock")
        no_identity = self.run_lever("remove", "lane/session-b", identity=False)
        self.assertEqual(no_identity.returncode, 2)
        self.assertRegex(no_identity.stderr.strip(), r"^identity: ")

    def test_add_names_another_session_branch_beside_the_first(self):
        """Owner, 2026-09-12: "as long you account for the fact that i'll
        have multiple sessions running soon". Two sessions on one host share
        this lock; the second adds its branch, it does not replace the
        first's."""
        self.run_lever("set", "lane/session-a", "--why", "session a")
        proc = self.run_lever("add", "lane/session-b", "--why", "session b")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(self.lock.read_text())
        self.assertEqual(data["branches"], ["lane/session-a", "lane/session-b"])
        self.assertIn("session a", data["why"])
        self.assertIn("session b", data["why"])
        again = self.run_lever("add", "lane/session-b", "--why", "session b")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(self.lock.read_text())["branches"],
                         ["lane/session-a", "lane/session-b"], "add is idempotent")
        fresh = self.run_lever("clear")
        self.assertEqual(fresh.returncode, 0)
        proc = self.run_lever("add", "lane/session-c", "--why", "session c")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(self.lock.read_text())["branches"], ["lane/session-c"],
                         "add on no lock sets it")
        self.assertEqual(self.run_lever("add", "--why", "x").returncode, 2)
        self.assertEqual(self.run_lever("add", "lane/d").returncode, 2)

    def test_clear_removes_it_and_show_says_no_lock(self):
        self.run_lever("set", "lane/a", "--why", "x")
        proc = self.run_lever("clear")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.lock.exists())
        self.assertEqual(self.run_lever("show", identity=False).stdout.strip(), "no lock")

    def test_writes_need_identity_and_refuse_on_the_wire(self):
        for args in (("set", "lane/a", "--why", "x"), ("add", "lane/a", "--why", "x"), ("clear",)):
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
