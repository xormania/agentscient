"""The generic ledger lever: every appended register as one file per row.

Owner, 2026-09-13: the pitfalls page and anything similar, because agents
need to work in parallel. ledger.py names each ledger in one table
(defects, pitfalls): the page whose rows stop, the rows directory, the id
shape, the fields. defects.py stays as a shim over it. One producer
(Claude Fable 5.1) under hand grant 196; the second producer absent, said
in the commit.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEVER = ROOT / "ops" / "conductor" / "tools" / "ledger.py"
SHIM = ROOT / "ops" / "conductor" / "tools" / "defects.py"
DEFECTS_PAGE = Path("ops/conductor/handoff/lane-defects.md")
DEFECTS_ROWS = Path("ops/conductor/handoff/lane-defects")
PITFALLS_PAGE = Path("ops/conductor/handoff/pitfalls-20260911.md")
PITFALLS_ROWS = Path("ops/conductor/handoff/pitfalls")

DEFECTS_TABLE = ("# Lane defects\n\n| id | observed | where | defect | repair | tests |\n|---|---|---|---|---|---|\n"
                 "| LD-1 | 2026-09-10 | `x.py` | a defect | a repair | a test |\n"
                 "| LD-35 | 2026-09-13 | `x.py` | a defect | a repair | a test |\n")
PITFALLS_TABLE = ("# Running list\n\n| # | what bit | do instead |\n|---|---|---|\n"
                  "| 1 | a thing | the other thing |\n| 29 | a thing | the other thing |\n")


class TheLedgerLever(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ledger-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.tmp / "home"),
                    "XDG_STATE_HOME": str(self.tmp / "xdg"),
                    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
        self.git("init", "-q", "-b", "dev")
        for page, text in ((DEFECTS_PAGE, DEFECTS_TABLE), (PITFALLS_PAGE, PITFALLS_TABLE)):
            (self.repo / page).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / page).write_text(text)

    def git(self, *args):
        proc = subprocess.run(["git", "-C", str(self.repo), *args], env=self.env,
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc

    def run_lever(self, *args, lever=LEVER, identity=True):
        env = dict(self.env)
        if identity:
            env["WF_AGENT"] = "Owner <owner@example.test>"
        return subprocess.run([sys.executable, str(lever), *args], env=env, cwd=str(self.repo),
                              capture_output=True, text=True, check=False)

    def assert_wire(self, proc, klass):
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout, "")
        lines = proc.stderr.strip().splitlines()
        self.assertEqual(len(lines), 1, proc.stderr)
        self.assertRegex(lines[0], rf"^{klass}: expected .+; found .+; needed .+$")

    def test_ledgers_lists_the_named_registers(self):
        proc = self.run_lever("ledgers", identity=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        names = [l.split()[0] for l in proc.stdout.strip().splitlines()]
        self.assertEqual(names, ["defects", "pitfalls"])
        self.assert_wire(self.run_lever("next", "nowhere", identity=False), "ledger")

    def test_pitfalls_next_add_show_list(self):
        proc = self.run_lever("next", "pitfalls", identity=False)
        self.assertEqual(proc.stdout.strip(), "30", "the table ends at 29")
        proc = self.run_lever("add", "pitfalls", "--what-bit", "a grep with a head", "--do-instead", "count first")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), f"30 {PITFALLS_ROWS / '30.md'}")
        text = (self.repo / PITFALLS_ROWS / "30.md").read_text()
        self.assertTrue(text.startswith("# pitfall 30\n"), text)
        self.assertIn("| what-bit | a grep with a head |", text)
        self.assertIn("| do-instead | count first |", text)
        self.assertIn("| by | Owner <owner@example.test> |", text)
        self.assertRegex(text, r"\| observed \| \d{4}-\d{2}-\d{2} \|")
        self.assertEqual(self.run_lever("next", "pitfalls", identity=False).stdout.strip(), "31")
        shown = self.run_lever("show", "pitfalls", "30", identity=False)
        self.assertIn("| what-bit |", shown.stdout)
        listed = self.run_lever("list", "pitfalls", identity=False)
        self.assertEqual(listed.stdout.strip().split()[0], "30")
        self.assertEqual((self.repo / PITFALLS_PAGE).read_text(), PITFALLS_TABLE, "the page is never written")

    def test_add_refuses_a_missing_field_by_its_flag_and_needs_identity(self):
        proc = self.run_lever("add", "pitfalls", "--what-bit", "x")
        self.assert_wire(proc, "arguments")
        self.assertIn("--do-instead", proc.stderr)
        self.assert_wire(self.run_lever("add", "pitfalls", "--what-bit", "x", "--do-instead", "y", identity=False),
                         "identity")
        self.assertFalse((self.repo / PITFALLS_ROWS).exists())

    def test_defects_through_the_lever_and_through_the_shim_agree(self):
        proc = self.run_lever("add", "defects", "--where", "`y.py`", "--defect", "d", "--repair", "r", "--tests", "t")
        self.assertEqual(proc.stdout.strip(), f"LD-36 {DEFECTS_ROWS / 'LD-36.md'}", proc.stderr)
        proc = self.run_lever("add", "--where", "`z.py`", "--defect", "d", "--repair", "r", "--tests", "t", lever=SHIM)
        self.assertEqual(proc.stdout.strip(), f"LD-37 {DEFECTS_ROWS / 'LD-37.md'}", proc.stderr)
        self.assertEqual(self.run_lever("next", lever=SHIM, identity=False).stdout.strip(), "LD-38")
        listed = self.run_lever("list", "defects", identity=False)
        self.assertEqual([l.split()[0] for l in listed.stdout.strip().splitlines()], ["LD-36", "LD-37"])
        self.assert_wire(self.run_lever("show", "defects", "LD-99", identity=False), "absent")

    def test_next_counts_the_trunk_rows_a_branch_has_not_merged(self):
        """Owner, 2026-09-13 ("minimize parallel work conflicts"): a session
        that mints from its own tree alone re-mints an id another session
        already pushed to the trunk; the lever also reads origin/<trunk>."""
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("config", "commit.gpgsign", "false")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "seed")
        origin = self.tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "dev", str(origin)], env=self.env, check=True)
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "origin", "dev")
        self.git("checkout", "-q", "-b", "lane/b")
        # another session lands pitfall 30 on the trunk; this branch never merges it
        other = self.tmp / "other"
        subprocess.run(["git", "clone", "-q", str(origin), str(other)], env=self.env, check=True)
        for k, v in (("user.email", "fixture@example.invalid"), ("user.name", "Fixture"), ("commit.gpgsign", "false")):
            subprocess.run(["git", "-C", str(other), "config", k, v], env=self.env, check=True)
        env = dict(self.env, WF_AGENT="Other <other@example.test>")
        proc = subprocess.run([sys.executable, str(LEVER), "add", "pitfalls", "--what-bit", "a", "--do-instead", "b"],
                              env=env, cwd=str(other), capture_output=True, text=True, check=False)
        self.assertEqual(proc.stdout.split()[0], "30", proc.stderr)
        subprocess.run(["git", "-C", str(other), "add", "-A"], env=self.env, check=True)
        subprocess.run(["git", "-C", str(other), "commit", "-q", "-m", "other: 30"], env=self.env, check=True)
        subprocess.run(["git", "-C", str(other), "push", "-q", "origin", "dev"], env=self.env, check=True)
        # this branch, unmerged, mints past what the trunk holds
        proc = self.run_lever("next", "pitfalls", identity=False)
        self.assertEqual(proc.stdout.strip(), "31", "the trunk's row 30 counts even though this tree lacks it")
        proc = self.run_lever("add", "pitfalls", "--what-bit", "c", "--do-instead", "d")
        self.assertEqual(proc.stdout.split()[0], "31", proc.stderr)
        self.assertIn("fetched origin/dev", proc.stderr, "the fetch is said on stderr, never on stdout")

    def test_two_sessions_pitfall_rows_merge_as_two_additions(self):
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("config", "commit.gpgsign", "false")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "seed")
        self.git("checkout", "-q", "-b", "lane/a")
        self.run_lever("add", "pitfalls", "--what-bit", "a", "--do-instead", "b")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "a: 30")
        self.git("checkout", "-q", "dev")
        self.git("merge", "-q", "--no-edit", "lane/a")
        self.git("checkout", "-q", "-b", "lane/b")
        self.assertEqual(self.run_lever("add", "pitfalls", "--what-bit", "c", "--do-instead", "d").stdout.split()[0], "31")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "b: 31")
        self.git("checkout", "-q", "dev")
        self.git("merge", "--no-edit", "lane/b")
        self.assertEqual(sorted(p.name for p in (self.repo / PITFALLS_ROWS).iterdir()), ["30.md", "31.md"])


if __name__ == "__main__":
    unittest.main()
