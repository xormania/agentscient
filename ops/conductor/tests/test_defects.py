"""The defect ledger lever: next, add, show, list; one file per row; the wire.

Owner, 2026-09-13 ("fix issue #1 - PR and merge"): lane-defects.md conflicted
on three of five merge-forwards since 2026-09-11 because every session
appended its row at the same line of one table. From LD-36 a row is its own
file under ops/conductor/handoff/lane-defects/, so two sessions' rows merge
as two additions; only the same id minted twice conflicts, as add/add on one
file, loudly. One producer (Claude Fable 5.1) under hand grant 194; the
second producer absent, said in the commit.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from ops.testkit import World, run

ROOT = Path(__file__).resolve().parents[3]
LEVER = ROOT / "ops" / "conductor" / "tools" / "defects.py"
PAGE = Path("ops/conductor/handoff/lane-defects.md")
ROWS = Path("ops/conductor/handoff/lane-defects")

HEADER = ("# Lane defects\n\n| id | observed | where | defect | repair | tests |\n"
          "|---|---|---|---|---|---|\n")
ROW = "| LD-{n} | 2026-09-10 | `x.py` | a defect | a repair | a test |\n"


class TheDefectLever(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="defects-")
        self.addCleanup(self.world.close)
        self.world.require("git")
        self.repo = self.world.cwd
        self.world.git("init", "-q", "-b", "dev", cwd=self.repo)
        self.world.plant_text(
            self.repo / PAGE,
            HEADER + ROW.format(n=1) + ROW.format(n=35),
        )
        self.world.git("add", "-A", cwd=self.repo)
        self.world.git("commit", "-q", "-m", "seed", cwd=self.repo)

    def git(self, *args, cwd=None, expect=0):
        result = self.world.git(*args, cwd=cwd or self.repo, check=False)
        if expect is not None:
            self.assertEqual(result.exit, expect, result.stdout + result.stderr)
        return result

    def run_lever(self, *args, identity=True, cwd=None):
        extra = {}
        if identity:
            extra["WF_AGENT"] = "Owner <owner@example.test>"
        return run(
            [sys.executable, str(LEVER), *args],
            env=self.world.env(extra=extra),
            cwd=str(cwd or self.repo),
            timeout=60,
        )

    def add(self, n_where="`y.py`", **kw):
        return self.run_lever("add", "--where", n_where, "--defect", kw.get("defect", "the defect"),
                              "--repair", kw.get("repair", "the repair"), "--tests", kw.get("tests", "the test"),
                              cwd=kw.get("cwd"), identity=kw.get("identity", True))

    def assert_wire(self, proc, klass):
        self.assertEqual(proc.exit, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout, "", "a refusal prints nothing on stdout")
        lines = proc.stderr.strip().splitlines()
        self.assertEqual(len(lines), 1, proc.stderr)
        self.assertRegex(lines[0], rf"^{klass}: expected .+; found .+; needed .+$")

    def test_next_reads_the_table_then_the_rows_directory(self):
        proc = self.run_lever("next", identity=False)
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "LD-1", "the table ends at LD-35")
        (self.repo / ROWS).mkdir()
        self.world.plant_text(self.repo / ROWS / "LD-40.md", "# LD-40\n")
        proc = self.run_lever("next", identity=False)
        self.assertEqual(proc.stdout.strip(), "LD-41", "a row file outranks the table")

    def test_add_writes_one_file_per_row_and_prints_its_id_and_path(self):
        proc = self.add()
        self.assertEqual(proc.exit, 1, proc.stderr)
        self.assertEqual(proc.stdout.strip(), f"LD-36 {ROWS / 'LD-36.md'}")
        text = (self.repo / ROWS / "LD-36.md").read_text()
        self.assertTrue(text.startswith("# LD-36\n"), text)
        for field in ("observed", "where", "defect", "repair", "tests", "by"):
            self.assertRegex(text, rf"(?m)^\| {field} \| .+ \|$", f"field {field}")
        self.assertIn("| by | Owner <owner@example.test> |", text)
        self.assertRegex(text, r"\| observed \| \d{4}-\d{2}-\d{2} \|")
        self.assertIn("| where | `y.py` |", text)
        again = self.add(n_where="`z.py`")
        self.assertEqual(again.stdout.split()[0], "LD-37", "the next add mints the next id")
        self.assertEqual((self.repo / PAGE).read_text(), HEADER + ROW.format(n=1) + ROW.format(n=35),
                         "the page is never written by add")

    def test_add_needs_identity_and_every_field_on_the_wire(self):
        self.assert_wire(self.add(identity=False), "identity")
        proc = self.run_lever("add", "--where", "`y.py`", "--defect", "d", "--repair", "r")
        self.assert_wire(proc, "arguments")
        self.assertIn("--tests", proc.stderr)
        self.assert_wire(self.run_lever("add", "--where", "", "--defect", "d", "--repair", "r", "--tests", "t"),
                         "arguments")
        self.assertFalse((self.repo / ROWS).exists(), "a refused add writes nothing")

    def test_show_and_list_read_the_rows_without_identity(self):
        self.add()
        self.add(n_where="`z.py`", defect="second")
        shown = self.run_lever("show", "LD-37", identity=False)
        self.assertEqual(shown.exit, 1, shown.stderr)
        self.assertIn("| defect | second |", shown.stdout)
        self.assert_wire(self.run_lever("show", "LD-99", identity=False), "absent")
        listed = self.run_lever("list", identity=False)
        self.assertEqual(listed.exit, 0, listed.stderr)
        self.assertEqual([l.split()[0] for l in listed.stdout.strip().splitlines()], ["LD-36", "LD-37"])
        self.assertIn("`z.py`", listed.stdout.splitlines()[1])

    def test_two_sessions_rows_merge_as_two_additions(self):
        """The reason for the shape: rows from two branches never touch."""
        self.git("checkout", "-q", "-b", "lane/a")
        self.assertEqual(self.add(n_where="`a.py`").exit, 1)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "a: LD-36")
        self.git("checkout", "-q", "dev")
        self.git("checkout", "-q", "-b", "lane/b")
        # b mints while a's row sits on lane/a only: the same id, the one case that conflicts
        proc = self.add(n_where="`b.py`")
        self.assertEqual(proc.stdout.split()[0], "LD-36")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "b: LD-36")
        merge = self.git("merge", "--no-edit", "lane/a", expect=None)
        self.assertEqual(merge.exit, 0, "the same id twice is an add/add conflict, loudly")
        conflicted = self.git("diff", "--name-only", "--diff-filter=U").stdout.split()
        self.assertEqual(conflicted, [str(ROWS / "LD-36.md")], "only the row file, never the page")
        self.git("merge", "--abort")
        # b re-mints after taking a's row: distinct files, no conflict
        self.git("reset", "-q", "--hard", "dev")
        self.git("merge", "-q", "--no-edit", "lane/a")
        proc = self.add(n_where="`b.py`")
        self.assertEqual(proc.stdout.split()[0], "LD-37")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "b: LD-37")
        self.git("checkout", "-q", "dev")
        self.git("merge", "-q", "--no-edit", "lane/a")
        merge = self.git("merge", "--no-edit", "lane/b", expect=None)
        self.assertEqual(merge.exit, 0, merge.stdout + merge.stderr)
        self.assertEqual(sorted(p.name for p in (self.repo / ROWS).iterdir()), ["LD-36.md", "LD-37.md"])

    def test_outside_a_repository_refuses(self):
        outside = self.world.path("nowhere")
        outside.mkdir()
        self.assert_wire(self.run_lever("next", identity=False, cwd=outside), "repository")


if __name__ == "__main__":
    unittest.main()
