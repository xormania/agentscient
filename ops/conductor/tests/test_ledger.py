"""The generic ledger lever: every appended register as one file per row.

Owner, 2026-09-13: the pitfalls page and anything similar, because agents
need to work in parallel. ledger.py names each ledger in one table
(defects, pitfalls): the page whose rows stop, the rows directory, the id
shape, the fields. defects.py stays as a shim over it. One producer
(Claude Fable 5.1) under hand grant 196; the second producer absent, said
in the commit.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from ops.testkit import World, run

ROOT = Path(__file__).resolve().parents[3]
LEVER = ROOT / "ops" / "conductor" / "tools" / "ledger.py"
SHIM = ROOT / "ops" / "conductor" / "tools" / "defects.py"
DEFECTS_PAGE = Path("ops/conductor/handoff/lane-defects.md")
DEFECTS_ROWS = Path("ops/conductor/handoff/lane-defects")
PITFALLS_PAGE = Path("ops/conductor/handoff/pitfalls-20260911.md")
PITFALLS_ROWS = Path("ops/conductor/handoff/pitfalls")
IDEAS_ROWS = Path("ops/conductor/ideas")

DEFECTS_TABLE = ("# Lane defects\n\n| id | observed | where | defect | repair | tests |\n|---|---|---|---|---|---|\n"
                 "| LD-1 | 2026-09-10 | `x.py` | a defect | a repair | a test |\n"
                 "| LD-35 | 2026-09-13 | `x.py` | a defect | a repair | a test |\n")
PITFALLS_TABLE = ("# Running list\n\n| # | what bit | do instead |\n|---|---|---|\n"
                  "| 1 | a thing | the other thing |\n| 29 | a thing | the other thing |\n")


class TheLedgerLever(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="ledger-")
        self.addCleanup(self.world.close)
        self.tmp = self.world.root
        self.repo = self.world.cwd
        self.env = self.world.env()
        self.git("init", "-q", "-b", "dev")
        for page, text in ((DEFECTS_PAGE, DEFECTS_TABLE), (PITFALLS_PAGE, PITFALLS_TABLE)):
            self.world.plant_text(self.repo / page, text)

    def git(self, *args, cwd=None):
        proc = run(
            ["git", "-C", str(cwd or self.repo), *args],
            cwd=cwd or self.repo,
            env=self.env,
            timeout=60,
        )
        self.assertEqual(proc.exit, 0, proc.stdout + proc.stderr)
        return proc

    def run_lever(self, *args, lever=LEVER, identity=True):
        env = dict(self.env)
        if identity:
            env["WF_AGENT"] = "Owner <owner@example.test>"
        return run(
            [sys.executable, str(lever), *args],
            env=env,
            cwd=self.repo,
            timeout=60,
        )

    def assert_wire(self, proc, klass):
        self.assertEqual(proc.exit, 2, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout, "")
        lines = proc.stderr.strip().splitlines()
        self.assertEqual(len(lines), 1, proc.stderr)
        self.assertRegex(lines[0], rf"^{klass}: expected .+; found .+; needed .+$")

    def test_ledgers_lists_the_named_registers(self):
        """The charge is that the verb names every register this lever
        knows and refuses a name it does not. The pin read

            self.assertEqual(names, ["defects", "pitfalls"])

        until LD-53 put the ideas directory under the same next-id
        reader. A list pinned to its own length is the finding
        docs/tests.md rule 3 names, so the row asks for the registers it
        is about and for nothing it is not."""
        proc = self.run_lever("ledgers", identity=False)
        self.assertEqual(proc.exit, 0, proc.stderr)
        names = [l.split()[0] for l in proc.stdout.strip().splitlines()]
        for known in ("defects", "pitfalls", "ideas"):
            self.assertIn(known, names)
        self.assertEqual(len(names), len(set(names)), names)
        self.assert_wire(self.run_lever("next", "nowhere", identity=False), "ledger")

    def plant_ideas(self, *names):
        """Idea records, which are prose in the owner's words and never a
        field table, so the lever only ever reads them."""
        for name in names:
            self.world.plant_text(self.repo / IDEAS_ROWS / name,
                                  f"# {name[:-3]}\n\nrecorded by hand.\n")

    def test_ideas_next_is_one_past_the_highest_in_the_records_own_shape(self):
        """LD-53: two sessions minted I-029 on two branches because there
        was no reader to ask. The ideas directory is one now, read-only:
        the number is three digits wide, as every record in the directory
        spells it, and I-32 would be a fourth spelling of the same id."""
        self.plant_ideas("I-001-first.md", "I-002-second.md", "I-031-last.md")
        proc = self.run_lever("next", "ideas", identity=False)
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "I-032")

    def test_ideas_check_is_quiet_when_no_number_is_shared(self):
        """The clean neighbour. A directory where every record holds its
        own number is an answer, and the verb says so rather than saying
        nothing, because silence is not a declaration."""
        self.plant_ideas("I-001-first.md", "I-002-second.md")
        proc = self.run_lever("check", "ideas", identity=False)
        self.assertEqual(proc.exit, 0, proc.stdout + proc.stderr)
        self.assertIn("no shared numbers", proc.stdout)

    def test_ideas_check_finds_a_shared_number_and_names_every_file(self):
        self.plant_ideas("I-001-first.md", "I-002-second.md",
                         "I-002-minted-elsewhere.md")
        proc = self.run_lever("check", "ideas", identity=False)
        # A Finding, not a Rejection: the verb ran to completion and the
        # result carries findings (docs/wire.md).
        self.assertEqual(proc.exit, 1, proc.stdout + proc.stderr)
        self.assertIn("I-002", proc.stdout)
        self.assertIn("I-002-second.md", proc.stdout)
        self.assertIn("I-002-minted-elsewhere.md", proc.stdout)
        self.assertNotIn("I-001", proc.stdout)

    def test_ideas_next_still_answers_while_a_number_is_shared(self):
        """A collision already minted says nothing about the next number,
        and a reader that refused would leave a session with no way to
        mint at all. The two questions are separate verbs on purpose."""
        self.plant_ideas("I-001-first.md", "I-002-second.md",
                         "I-002-minted-elsewhere.md")
        proc = self.run_lever("next", "ideas", identity=False)
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "I-003")

    def test_ideas_refuses_the_verbs_that_write_or_read_a_field_table(self):
        """An idea is recorded by hand, in the owner's words, in the shape
        ops/conductor/ideas/README.md gives. The lever mints its number
        and reports collisions; it never writes one, and show and list
        would read a field table that is not there."""
        self.plant_ideas("I-001-first.md")
        for argv in (("add", "ideas", "--where", "x"),
                     ("show", "ideas", "I-001"),
                     ("list", "ideas")):
            self.assert_wire(self.run_lever(*argv), "ledger")

    def test_pitfalls_next_add_show_list(self):
        proc = self.run_lever("next", "pitfalls", identity=False)
        self.assertEqual(proc.stdout.strip(), "30", "the table ends at 29")
        proc = self.run_lever("add", "pitfalls", "--what-bit", "a grep with a head", "--do-instead", "count first")
        self.assertEqual(proc.exit, 0, proc.stderr)
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

    def test_add_refuses_a_rows_directory_that_resolves_outside_the_repository(self):
        """Security audit 20260913T104919Z-review-codex-9126d3 (Daybreak), finding 3:
        a symlink at the rows directory sent the new row file outside the
        repository, since the lever wrote through it with no containment check."""
        outside = self.tmp / "outside"
        outside.mkdir()
        (self.repo / PITFALLS_ROWS).symlink_to(outside, target_is_directory=True)
        proc = self.run_lever("add", "pitfalls", "--what-bit", "a", "--do-instead", "b")
        self.assert_wire(proc, "containment")
        self.assertEqual(list(outside.iterdir()), [], "nothing is written outside the repository")

    def test_add_refuses_a_field_value_that_spans_lines(self):
        """The same audit, finding 5: a line break inside a value wrote extra
        field lines into the row, and list read the forged observed and where."""
        for value in ("t\n| where | forged |", "t\r| observed | 2099-01-01 |"):
            with self.subTest(value=value):
                proc = self.run_lever("add", "defects", "--where", "real", "--defect", "d", "--repair", "r",
                                      "--tests", value)
                self.assert_wire(proc, "arguments")
                self.assertIn("--tests", proc.stderr)
        self.assertFalse((self.repo / DEFECTS_ROWS).exists(), "no row file for a refused add")

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
        self.git("init", "-q", "--bare", "-b", "dev", str(origin))
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "origin", "dev")
        self.git("checkout", "-q", "-b", "lane/b")
        # another session lands pitfall 30 on the trunk; this branch never merges it
        other = self.tmp / "other"
        self.git("clone", "-q", str(origin), str(other))
        for k, v in (("user.email", "fixture@example.invalid"), ("user.name", "Fixture"), ("commit.gpgsign", "false")):
            self.git("config", k, v, cwd=other)
        env = dict(self.env, WF_AGENT="Other <other@example.test>")
        proc = run(
            [sys.executable, str(LEVER), "add", "pitfalls", "--what-bit", "a", "--do-instead", "b"],
            env=env,
            cwd=other,
            timeout=60,
        )
        self.assertEqual(proc.stdout.split()[0], "30", proc.stderr)
        self.git("add", "-A", cwd=other)
        self.git("commit", "-q", "-m", "other: 30", cwd=other)
        self.git("push", "-q", "origin", "dev", cwd=other)
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

    def test_next_skips_an_id_taken_on_a_branch_the_trunk_has_not_merged(self):
        """The charge: an id another session pushed to its own branch is
        taken, and this lever must not hand it out a second time.

        Before this row the lever read the working tree, the page's table
        and origin/<trunk>, and nothing else, so a row minted on a branch
        between two merges was invisible. Measured on the lane's own
        repository on 2026-09-16 over 1,264 refs: ten ids carried two
        different rows, LD-81 four, and twelve ids existed off the trunk.
        At 19:25:34Z a session filed LD-81, LD-82 and LD-83 on ids `next`
        had just called free and renumbered all three by hand at
        20:09:44Z, after the trunk moved 21 commits underneath it.

        Three arms: the planted fault (taken on an unmerged branch), the
        vacated id (renumbered away, never re-issued), and the clean
        neighbour (a ledger nothing touched, whose next id must not move).
        """
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("config", "commit.gpgsign", "false")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "seed")
        origin = self.tmp / "origin.git"
        self.git("init", "-q", "--bare", "-b", "dev", str(origin))
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "origin", "dev")

        # another session mints pitfall 30 on its own branch and pushes the
        # branch, never the trunk
        other = self.tmp / "other"
        self.git("clone", "-q", str(origin), str(other))
        for k, v in (("user.email", "fixture@example.invalid"),
                     ("user.name", "Fixture"), ("commit.gpgsign", "false")):
            self.git("config", k, v, cwd=other)
        self.git("checkout", "-q", "-b", "lane/other", cwd=other)
        env = dict(self.env, WF_AGENT="Other <other@example.test>")
        minted = run([sys.executable, str(LEVER), "add", "pitfalls",
                      "--what-bit", "a", "--do-instead", "b"],
                     env=env, cwd=other, timeout=60)
        self.assertEqual(minted.stdout.split()[0], "30", minted.stderr)
        self.git("add", "-A", cwd=other)
        self.git("commit", "-q", "-m", "other: 30", cwd=other)
        self.git("push", "-q", "origin", "lane/other", cwd=other)

        # the planted fault: 30 is on no trunk, and was handed out anyway
        absent = run(["git", "-C", str(self.repo), "show",
                      f"origin/dev:{(PITFALLS_ROWS / '30.md').as_posix()}"],
                     cwd=self.repo, env=self.env, timeout=60)
        self.assertNotEqual(absent.exit, 0,
                            "the fixture is wrong if the trunk already carries 30")
        proc = self.run_lever("next", "pitfalls", identity=False)
        self.assertEqual(proc.stdout.strip(), "31",
                         "30 is taken on a branch the trunk has not merged")
        self.assertIn("fetched origin", proc.stderr,
                      "the branch is only visible after a fetch, and the fetch "
                      "is said on stderr")

        # the vacated id: renumbering 30 to 40 must not free 30 or hide 40
        self.git("mv", (PITFALLS_ROWS / "30.md").as_posix(),
                 (PITFALLS_ROWS / "40.md").as_posix(), cwd=other)
        self.git("commit", "-q", "-m", "other: 30 renumbered to 40", cwd=other)
        self.git("push", "-q", "origin", "lane/other", cwd=other)
        proc = self.run_lever("next", "pitfalls", identity=False)
        self.assertEqual(proc.stdout.strip(), "41",
                         "40 is taken and 30 was used; neither is handed out again")

        # the clean neighbour: a ledger nothing has touched does not move
        proc = self.run_lever("next", "defects", identity=False)
        self.assertEqual(proc.stdout.strip(), "LD-36",
                         "the reader must stay quiet on a ledger with no branch rows")

    def test_next_refuses_when_origin_cannot_be_reached_and_says_the_way_round(self):
        """The charge: minting reads every ref, which means it reads the
        network, and an id read off refs that could not be refreshed is
        low by an unknown amount. The caller reads stdout, so saying it on
        stderr would not reach them: the read refuses on the wire instead.

        Asked for by the XO on 2026-09-16 against this row, as the same
        shape as an empty answer that reads as a confident one -- the
        fault four sessions committed that day. Two arms: the planted
        fault, an origin that cannot be reached; and the named remedy,
        LEDGER_REFS=local, which is the operator declaring the limit
        rather than inheriting it in silence.
        """
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("config", "commit.gpgsign", "false")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "seed")
        self.git("remote", "add", "origin", str(self.tmp / "no-such-origin.git"))

        self.assert_wire(self.run_lever("next", "pitfalls", identity=False), "refs")
        self.assert_wire(
            self.run_lever("add", "pitfalls", "--what-bit", "a", "--do-instead", "b"),
            "refs")

        env = dict(self.env, LEDGER_REFS="local")
        proc = run([sys.executable, str(LEVER), "next", "pitfalls"],
                   env=env, cwd=self.repo, timeout=60)
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "30",
                         "the declared-local read still answers off this repository")
        self.assertIn("LEDGER_REFS=local", proc.stderr,
                      "the limit is said, and said on stderr so stdout carries only the id")


if __name__ == "__main__":
    unittest.main()
