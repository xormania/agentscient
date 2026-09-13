"""The skills registry on the refusal wire.

Contract: ops/conductor/instrument-conventions.md, inherited by
ops/conductor/tools/skills.py. Written by hand under grant 210 (owner,
2026-09-13: "#1- #4 hand grant ok'd get them done in one PR"), one
producer, the second producer absent by the owner's word. Red at the
base: every refusal exits 1 with a sentence, and the store ignores
XDG_STATE_HOME. Green with the same command once the tool imports
instrument.py. The tool is run as a subprocess under a scratch HOME and
XDG_STATE_HOME; `sync` reads the repository's own .claude/skills/.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "skills.py"
AGENT = "Test Author <author@example.invalid>"


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.state = Path(self.tmp.name) / "state"
        self.home.mkdir()
        self.state.mkdir()

    def run_tool(self, *argv, agent=AGENT):
        env = {k: v for k, v in os.environ.items()
               if k not in ("WF_AGENT", "HOME", "XDG_STATE_HOME")}
        env["HOME"] = str(self.home)
        env["XDG_STATE_HOME"] = str(self.state)
        if agent is not None:
            env["WF_AGENT"] = agent
        return subprocess.run([sys.executable, str(TOOL), *argv], cwd=REPO,
                              env=env, capture_output=True, text=True, timeout=60)

    def assert_refusal(self, proc, klass):
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout, "")
        lines = proc.stderr.splitlines()
        self.assertEqual(len(lines), 1, proc.stderr)
        line = lines[0]
        self.assertTrue(line.startswith(f"{klass}: expected "), line)
        self.assertIn("; found ", line)
        self.assertIn("; needed ", line)
        return line


class Refusals(_Fixture):
    def test_unknown_verb_refuses_arguments(self):
        self.assert_refusal(self.run_tool("bogus"), "arguments")
        self.assert_refusal(self.run_tool(), "arguments")

    def test_a_writing_verb_without_identity_refuses_identity(self):
        self.assert_refusal(self.run_tool("log-use", "close", "x", agent=None), "identity")
        self.assert_refusal(self.run_tool("wish", "nothing", "x", agent="bare name"), "identity")

    def test_verbs_missing_their_arguments_refuse_arguments(self):
        for argv in (("add", "only-name"), ("show",), ("note", "x"),
                     ("retire", "x"), ("log-use",), ("log-fail", "x"), ("wish", "x")):
            with self.subTest(argv=argv):
                self.assert_refusal(self.run_tool(*argv), "arguments")

    def test_an_unknown_skill_refuses_skill(self):
        for argv in (("show", "nosuch"), ("note", "nosuch", "t"),
                     ("retire", "nosuch", "r"), ("log-use", "nosuch", "d"),
                     ("log-miss", "nosuch", "d")):
            with self.subTest(argv=argv):
                line = self.assert_refusal(self.run_tool(*argv), "skill")
                self.assertIn("nosuch", line)

    def test_a_bad_kind_refuses_kind(self):
        self.assert_refusal(self.run_tool("add", "x", "desc", "--kind=nope"), "kind")

    def test_a_second_add_or_a_wish_for_an_existing_row_refuses_exists(self):
        proc = self.run_tool("add", "planned", "a planned skill")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assert_refusal(self.run_tool("add", "planned", "again"), "exists")
        self.assert_refusal(self.run_tool("wish", "planned", "again"), "exists")


class TheStore(_Fixture):
    def test_the_store_lives_under_xdg_state_home(self):
        proc = self.run_tool("add", "planned", "a planned skill")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.state / "agentscient" / "skills.db").is_file(),
                        "store not under XDG_STATE_HOME")
        self.assertFalse((self.home / ".local").exists(), "store leaked under HOME")

    def test_add_list_show_and_events_round_trip(self):
        self.assertEqual(self.run_tool("add", "planned", "a planned skill").returncode, 0)
        listed = self.run_tool("list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("planned", listed.stdout)
        self.assertEqual(self.run_tool("log-use", "planned", "used once").returncode, 0)
        self.assertEqual(self.run_tool("wish", "absent", "should exist").returncode, 0)
        shown = self.run_tool("show", "planned")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn("events: 1", shown.stdout)
        report = self.run_tool("report")
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("absent", report.stdout)

    def test_sync_reads_the_skills_on_disk(self):
        proc = self.run_tool("sync")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("synced:", proc.stdout)


class TheDetail(_Fixture):
    """Security audit 20260913T104919Z-review-codex-9126d3 (Daybreak), finding 4:
    the skill-use hook hands every Skill call's arguments to `log-use`, and
    the lever stored them verbatim, so a secret typed into a skill's
    arguments entered a durable log. The lever is the one place a detail
    enters the store, for the hook and the hand command alike."""

    def stored(self, sql):
        with sqlite3.connect(self.state / "agentscient" / "skills.db") as con:
            return [row[0] or "" for row in con.execute(sql)]

    def test_secret_shaped_values_never_reach_the_store(self):
        self.assertEqual(self.run_tool("add", "planned", "a planned skill").returncode, 0)
        token = "ghp_" + "A" * 36
        detail = f"password=hunter2 token: {token} api_key=abc123 keep this"
        proc = self.run_tool("log-use", "planned", detail)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = self.run_tool("wish", "absent", f"needs secret={token}")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stored = " ".join(self.stored("SELECT detail FROM skill_events")
                          + self.stored("SELECT description FROM skills WHERE name='absent'"))
        for secret in ("hunter2", token, "abc123"):
            self.assertNotIn(secret, stored)
        self.assertIn("keep this", stored)
        self.assertIn("[redacted]", stored)


if __name__ == "__main__":
    unittest.main()
