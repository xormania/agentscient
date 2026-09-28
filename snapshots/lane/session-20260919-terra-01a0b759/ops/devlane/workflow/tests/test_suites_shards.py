"""suites.sh discovers the conductor family as disjoint shards.

Owner, 2026-09-16, through the Lead: "CI is starting to take a lot of time
- can we get it faster? Delegate". Measured at d919c982, one `unittest
discover` per file over all 69 files of `ops/conductor/tests`: 1478 tests,
334s summed, and one file, `test_coordination.py`, is 60s of that. Run in
one process the family costs ~300s of a ~330s lane job while every other
suite finishes inside 100s, so the whole lever waits on it.

The family is discovered as disjoint slices that run concurrently, the way
the suites already run, so it costs its slowest slice rather than its sum.
The slices are cut by measured cost and not by count: `c` is 93s, `l` is
97s, `o` and `w` together 79s, everything else 65s. The last pattern is the
complement of the others, so a file added later always lands in a slice.

The danger a slice carries is that a file falling out of every slice is a
silently smaller suite, and that failure reads green. So the lever proves
the partition on every run and refuses on the wire when it does not hold.
These rows are that proof\'s fixture set: the real tree as the clean
neighbour, and two planted pattern faults the guard must catch.

Written by hand, one producer, under grant 265 for this file and grant 282
for the lever; the second producer is absent by the owner\'s word
(AGENTS.md, dev-lane changes by hand).
"""

from __future__ import annotations

import fnmatch
import re
import unittest
from pathlib import Path

from ops.testkit import World, run

REPO = Path(__file__).resolve().parents[4]
SUITES = REPO / "ops" / "bin" / "suites.sh"
FAMILY = REPO / "ops" / "conductor" / "tests"
DECLARED = re.compile(r"^conductor_shards=\((.*)\)\s*$", re.MULTILINE)
TIMEOUT = 120

A_CASE = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n"


def declared_shards(text):
    """The shard patterns as suites.sh declares them, in its own order."""
    found = DECLARED.search(text)
    if found is None:
        return []
    return re.findall(r"\'([^\']+)\'", found.group(1))


class ThePartitionOfTheFamily(unittest.TestCase):
    """The real tree against the real patterns, in process: no shard runs
    here, only the question of whether the slices cover it once each."""

    def setUp(self):
        self.shards = declared_shards(SUITES.read_text(encoding="utf-8"))

    def test_the_lever_declares_more_than_one_shard(self):
        self.assertGreater(len(self.shards), 1,
                           f"suites.sh declares {self.shards}")

    def test_every_file_of_the_family_lands_in_exactly_one_shard(self):
        """The union is the whole set and the slices are disjoint. A file in
        none is a suite that shrank in silence; a file in two is counted
        twice and runs twice."""
        names = sorted(p.name for p in FAMILY.glob("test_*.py"))
        self.assertGreater(len(names), 1, f"no family at {FAMILY}")
        wrong = {}
        for name in names:
            hits = [p for p in self.shards if fnmatch.fnmatch(name, p)]
            if len(hits) != 1:
                wrong[name] = hits
        self.assertEqual(wrong, {}, f"{len(names)} files, shards {self.shards}")

    def test_a_name_no_shard_would_take_is_impossible(self):
        """The clean neighbour of the row above, asked of names the family
        does not have yet: the last pattern is the complement of the others,
        so anything added later still lands somewhere."""
        for name in ("test_zzz_new.py", "test_coordination_2.py", "test_l.py",
                     "test_0_digit.py", "test_watchdog_extra.py"):
            with self.subTest(name=name):
                hits = [p for p in self.shards if fnmatch.fnmatch(name, p)]
                self.assertEqual(len(hits), 1, f"{name} matched {hits}")


class TheShardsRun(unittest.TestCase):
    """The lever itself, on a planted family small enough to run."""

    def setUp(self):
        self.world = World(prefix="suites-shards-")
        self.addCleanup(self.world.close)
        self.root = self.world.cwd
        self.world.plant_bytes("cwd/ops/bin/suites.sh", SUITES.read_bytes())
        self.world.plant_bytes("cwd/ruff.toml",
                               (REPO / "ruff.toml").read_bytes())
        # one file per slice, named so each lands in a different one
        self.planted = ("test_coordination_fixture.py", "test_ladder_fixture.py",
                        "test_watch_fixture.py", "test_zebra_fixture.py")
        for name in self.planted:
            self.world.plant_text(f"cwd/ops/conductor/tests/{name}", A_CASE)

    def lever(self, path=None):
        extra = {"PATH": path} if path is not None else None
        return run(["bash", str(self.root / "ops" / "bin" / "suites.sh")],
                   cwd=self.root, env=self.world.env(extra), timeout=TIMEOUT)

    def plant_shards(self, *patterns):
        """The lever with its shard list replaced: the planted fault."""
        text = SUITES.read_text(encoding="utf-8")
        line = "conductor_shards=(" + " ".join(f"\'{p}\'" for p in patterns) + ")"
        replaced = DECLARED.sub(line, text)
        self.assertTrue(DECLARED.search(text),
                        "INVALID: suites.sh declares no conductor_shards line "
                        "for this row to plant a fault on")
        self.world.plant_text("cwd/ops/bin/suites.sh", replaced)

    def counted(self, proc):
        return sum(int(n) for n in re.findall(r"^Ran (\d+) tests?", proc.stdout, re.MULTILINE))

    def test_the_family_is_named_once_per_shard_in_the_output(self):
        proc = self.lever()
        blocks = re.findall(r"^== conductor.*$", proc.stdout, re.MULTILINE)
        self.assertEqual(len(blocks), len(declared_shards(SUITES.read_text(encoding="utf-8"))),
                         proc.stdout)
        self.assertEqual(len(set(blocks)), len(blocks),
                         f"two shards share a label: {blocks}")

    def test_the_shards_together_run_every_test_the_family_has(self):
        """The count after sharding equals the count before it. Four planted
        files, one test each, and the sum over the shards is four."""
        proc = self.lever()
        whole = run(["python3", "-m", "unittest", "discover", "-s",
                     "ops/conductor/tests", "-p", "test_*.py"],
                    cwd=self.root, env=self.world.env(), timeout=TIMEOUT)
        before = int(re.search(r"Ran (\d+) tests?", whole.stderr + whole.stdout).group(1))
        self.assertEqual(before, len(self.planted), whole.stderr)
        self.assertEqual(self.counted(proc), before, proc.stdout)

    def test_a_file_in_no_shard_is_refused_on_the_wire(self):
        """The planted fault the guard exists for: a pattern set that leaves
        a file out. The lever refuses before it runs anything."""
        self.plant_shards("test_[c]*.py", "test_[l]*.py")
        proc = self.lever()
        self.assertEqual(proc.exit, 2, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout.strip(), "", proc.stdout)
        self.assertIn("test_watch_fixture.py", proc.stderr)
        for half in ("shard: expected ", "; found ", "; needed "):
            self.assertIn(half, proc.stderr)

    def test_a_file_in_two_shards_is_refused_on_the_wire(self):
        """The other half of the same guard: a file counted twice runs
        twice, and the count after sharding stops meaning anything."""
        self.plant_shards("test_[c-z]*.py", "test_[a-l]*.py", "test_[!a-z]*.py")
        proc = self.lever()
        self.assertEqual(proc.exit, 2, proc.stdout + proc.stderr)
        self.assertIn("test_coordination_fixture.py", proc.stderr)

    def test_a_tree_without_the_family_is_still_green(self):
        """The clean neighbour: nothing to partition is not a fault. The
        directory goes, not just its files — an empty tests directory is a
        run of no tests, which unittest reads as red on its own account and
        is a different question from this one."""
        import shutil
        shutil.rmtree(self.root / "ops" / "conductor" / "tests")
        proc = self.lever()
        self.assertEqual(proc.exit, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
