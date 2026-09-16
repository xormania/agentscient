"""The deliverable lock lever: set, show, clear; identity for writes; the wire."""

from __future__ import annotations

import contextlib
import fcntl
import json
import subprocess
import sys
import unittest
from pathlib import Path

from ops.testkit import World, run

ROOT = Path(__file__).resolve().parents[3]
LEVER = ROOT / "ops" / "conductor" / "tools" / "deliverable.py"
OWNER = "Owner <owner@example.test>"


class _LockFixture(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="deliverable-")
        self.addCleanup(self.world.close)
        self._measures = 0
        conf = self.world.plant_text(
            self.world.path("lane.conf"), "LANE_NAME='testlane'\n",
        )
        self.conf = conf
        self.lock = self.world.xdg_state / "testlane" / "deliverable.json"

    def _env(self, identity=True, agent=OWNER, extra=None):
        payload = {"LANE_CONF": str(self.conf), **(extra or {})}
        if identity:
            payload["WF_AGENT"] = agent
        return self.world.env(extra=payload)

    def run_lever(self, *args, identity=True, agent=OWNER, extra=None):
        return run(
            [sys.executable, str(LEVER), *args],
            cwd=self.world.cwd,
            env=self._env(identity=identity, agent=agent, extra=extra),
            timeout=60,
        )

    def measure_tool(self, text: str, *, delay: float = 0.0) -> str:
        """A measure argv as JSON: prints ``text`` and exits 0."""
        self._measures += 1
        path = self.world.tools.plant(
            f"measure-{self._measures}", stdout=text, exit=0, delay=delay,
        )
        return json.dumps([sys.executable, str(path)])


class TheLockLever(_LockFixture):
    def test_set_writes_the_lock_and_show_reads_it(self):
        proc = self.run_lever("set", "lane/a", "lane/b", "--why", "the slices")
        self.assertEqual(proc.exit, 0, proc.stderr)
        data = json.loads(self.lock.read_text())
        self.assertEqual(data["branches"], ["lane/a", "lane/b"])
        self.assertEqual(data["why"], "the slices")
        self.assertEqual(data["by"], "Owner <owner@example.test>")
        self.assertRegex(data["at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        shown = self.run_lever("show", identity=False)
        self.assertEqual(shown.exit, 0)
        self.assertIn("lane/a", shown.stdout)

    def test_remove_lifts_one_session_branch_and_leaves_the_others(self):
        """Owner, 2026-09-13 ("minimize parallel work conflicts"; LD-28): a
        session that lands removes its own branch; the lock kept naming
        every landed branch because clear was the only exit and clear wipes
        every session's entry at once."""
        self.run_lever("set", "lane/session-a", "--why", "session a")
        self.run_lever("add", "lane/session-b", "--why", "session b")
        proc = self.run_lever("remove", "lane/session-a")
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "removed lane/session-a; locked lane/session-b")
        data = json.loads(self.lock.read_text())
        self.assertEqual(data["branches"], ["lane/session-b"])
        self.assertIn("session b", data["why"])
        again = self.run_lever("remove", "lane/session-a")
        self.assertEqual(again.exit, 2, again.stdout)
        self.assertRegex(again.stderr.strip(), r"^absent: expected .+; found .+; needed .+$")
        last = self.run_lever("remove", "lane/session-b")
        self.assertEqual(last.exit, 0, last.stderr)
        self.assertEqual(last.stdout.strip(), "removed lane/session-b; no lock")
        self.assertFalse(self.lock.exists(), "the last branch removed lifts the lock")
        self.assertEqual(self.run_lever("show", identity=False).stdout.strip(), "no lock")
        no_identity = self.run_lever("remove", "lane/session-b", identity=False)
        self.assertEqual(no_identity.exit, 2)
        self.assertRegex(no_identity.stderr.strip(), r"^identity: ")

    def test_add_names_another_session_branch_beside_the_first(self):
        """Owner, 2026-09-12: "as long you account for the fact that i'll
        have multiple sessions running soon". Two sessions on one host share
        this lock; the second adds its branch, it does not replace the
        first's."""
        self.run_lever("set", "lane/session-a", "--why", "session a")
        proc = self.run_lever("add", "lane/session-b", "--why", "session b")
        self.assertEqual(proc.exit, 0, proc.stderr)
        data = json.loads(self.lock.read_text())
        self.assertEqual(data["branches"], ["lane/session-a", "lane/session-b"])
        self.assertIn("session a", data["why"])
        self.assertIn("session b", data["why"])
        again = self.run_lever("add", "lane/session-b", "--why", "session b")
        self.assertEqual(again.exit, 0, again.stderr)
        self.assertEqual(json.loads(self.lock.read_text())["branches"],
                         ["lane/session-a", "lane/session-b"], "add is idempotent")
        fresh = self.run_lever("clear")
        self.assertEqual(fresh.exit, 0)
        proc = self.run_lever("add", "lane/session-c", "--why", "session c")
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(json.loads(self.lock.read_text())["branches"], ["lane/session-c"],
                         "add on no lock sets it")
        self.assertEqual(self.run_lever("add", "--why", "x").exit, 2)
        self.assertEqual(self.run_lever("add", "lane/d").exit, 2)

    def test_writers_wait_for_the_lock_file_so_parallel_sessions_lose_no_entry(self):
        """Code review 20260913T105222Z-review-grok-00b782 (Grok), finding 2 on
        PR #197: set, add, remove and clear read, change and write one
        host-wide file with no lock, and a concurrent remove and add lost
        lane/b in 3 of 60 trials at bdf8cf0c. Every writer holds an exclusive
        flock on deliverable.json.lock beside the lock while it reads and
        writes, so a writer that starts while another holds it waits."""
        self.run_lever("set", "lane/a", "--why", "a")
        before = self.lock.read_text()
        guard = self.lock.with_name("deliverable.json.lock")
        env = self._env(identity=True)
        for args in (("add", "lane/b", "--why", "b"), ("remove", "lane/a")):
            with self.subTest(args=args):
                held = open(guard, "a+")  # noqa: SIM115 - held across the child's start
                fcntl.flock(held, fcntl.LOCK_EX)
                child = subprocess.Popen(
                    [sys.executable, str(LEVER), *args],
                    env=env,
                    cwd=str(self.world.cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.world.own(child)
                try:
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        child.wait(timeout=1.0)
                    waited = child.poll() is None
                    unchanged = self.lock.read_text() == before
                finally:
                    held.close()
                    _out, err = child.communicate(timeout=30)
                self.assertTrue(waited, "the writer went ahead while another process held the lock")
                self.assertTrue(unchanged, "the lock changed while another process held it")
                self.assertEqual(child.returncode, 0, err)
                before = self.lock.read_text()
        self.assertEqual(json.loads(self.lock.read_text())["branches"], ["lane/b"])

    def test_a_target_is_stored_and_show_prints_the_live_reading_beside_it(self):
        """Owner, 2026-09-15, on a session that reported a plan's slices all
        done with 210 of 226 test modules still off the kit: "whatever it
        says - is the problem we to solve - right fucking now". The
        session named "done" was measured against the named work, never
        against the owner's target. A target on the lock is a measure
        command and the reading it must contain; show runs it and prints
        met or short beside the target, so the number sits next to the
        word every time the lock is read."""
        measure = self.measure_tool("on_kit=16/226\n")
        proc = self.run_lever("add", "lane/x", "--why", "every family onto the kit",
                              "--measure", measure, "--until", "on_kit=226/226")
        self.assertEqual(proc.exit, 0, proc.stderr)
        data = json.loads(self.lock.read_text())
        stored = data["targets"]["lane/x"]
        self.assertEqual(stored["measure"], json.loads(measure))
        self.assertEqual(stored["until"], "on_kit=226/226")
        shown = self.run_lever("show", "lane/x", identity=False)
        self.assertEqual(shown.exit, 0, shown.stderr)
        self.assertIn("target lane/x: until on_kit=226/226; reading on_kit=16/226; short", shown.stdout)
        met = self.measure_tool("on_kit=226/226 at abc1234\n")
        proc = self.run_lever("set", "lane/x", "--why", "every family onto the kit",
                              "--measure", met, "--until", "on_kit=226/226")
        self.assertEqual(proc.exit, 0, proc.stderr)
        shown = self.run_lever("show", "lane/x", identity=False)
        self.assertIn("target lane/x: until on_kit=226/226; reading on_kit=226/226 at abc1234; met", shown.stdout)
        # This line once read `assertNotIn("lane/x", ...), "set replaces"`.
        # T-71 retired that pin: set re-targets a branch the lock already
        # names and leaves the rest of the lock alone, so the branch it
        # named is still there afterwards.
        self.assertIn("lane/x", json.loads(self.lock.read_text())["branches"])

    def test_measure_without_until_or_until_without_measure_refuses_arguments(self):
        for extra in (("--measure", "true"), ("--until", "x")):
            with self.subTest(extra=extra):
                proc = self.run_lever("add", "lane/x", "--why", "w", *extra)
                self.assertEqual(proc.exit, 2, proc.stdout)
                self.assertRegex(proc.stderr.strip(), r"^arguments: expected .+; found .+; needed .+$")

    def test_done_refuses_target_while_the_reading_is_short_and_prints_it_when_met(self):
        measure = self.measure_tool("on_kit=16/226\n")
        self.run_lever("add", "lane/x", "--why", "w", "--measure", measure, "--until", "on_kit=226/226")
        proc = self.run_lever("done", "lane/x")
        self.assertEqual(proc.exit, 2, proc.stdout)
        self.assertEqual(proc.stdout, "")
        line = proc.stderr.strip()
        self.assertRegex(line, r"^target: expected .+; found .+; needed .+$")
        self.assertIn("on_kit=226/226", line)
        self.assertIn("on_kit=16/226", line)
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1)
        met = self.measure_tool("modules on_kit=226/226\nsecond line\n")
        self.run_lever("add", "lane/x", "--why", "w", "--measure", met, "--until", "on_kit=226/226")
        proc = self.run_lever("done", "lane/x")
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "done lane/x: modules on_kit=226/226")

    def test_done_on_a_branch_with_no_target_refuses_target_naming_the_flags(self):
        self.run_lever("add", "lane/x", "--why", "the slices")
        proc = self.run_lever("done", "lane/x")
        self.assertEqual(proc.exit, 2, proc.stdout)
        line = proc.stderr.strip()
        self.assertRegex(line, r"^target: expected .+; found .+; needed .+$")
        self.assertIn("--measure", line)
        self.assertIn("--until", line)
        absent = self.run_lever("done", "lane/nobody")
        self.assertEqual(absent.exit, 2)
        self.assertRegex(absent.stderr.strip(), r"^absent: ")

    def test_a_measure_that_cannot_run_is_unreachable_never_met(self):
        missing = json.dumps([sys.executable, str(self.world.tmp / "missing.py")])
        self.run_lever("add", "lane/x", "--why", "w", "--measure", missing,
                       "--until", "on_kit=226/226")
        shown = self.run_lever("show", "lane/x", identity=False)
        self.assertEqual(shown.exit, 0, shown.stderr)
        self.assertIn("target lane/x: until on_kit=226/226; reading unreachable", shown.stdout)
        proc = self.run_lever("done", "lane/x")
        self.assertEqual(proc.exit, 2, proc.stdout)
        self.assertIn("unreachable", proc.stderr)

    def test_remove_refuses_a_short_target_unless_a_reason_is_given(self):
        measure = self.measure_tool("on_kit=16/226\n")
        self.run_lever("add", "lane/x", "--why", "w", "--measure", measure, "--until", "on_kit=226/226")
        proc = self.run_lever("remove", "lane/x")
        self.assertEqual(proc.exit, 2, proc.stdout)
        self.assertRegex(proc.stderr.strip(), r"^target: expected .+; found .+; needed .+$")
        self.assertTrue(self.lock.exists())
        proc = self.run_lever("remove", "lane/x", "--unmet", "owner 2026-09-15: stop here")
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "removed lane/x unmet (owner 2026-09-15: stop here); no lock")
        met = self.measure_tool("on_kit=226/226\n")
        self.run_lever("add", "lane/y", "--why", "w", "--measure", met, "--until", "on_kit=226/226")
        proc = self.run_lever("remove", "lane/y")
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "removed lane/y; no lock")

    def test_clear_removes_it_and_show_says_no_lock(self):
        self.run_lever("set", "lane/a", "--why", "x")
        proc = self.run_lever("clear")
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertFalse(self.lock.exists())
        self.assertEqual(self.run_lever("show", identity=False).stdout.strip(), "no lock")

    def test_writes_need_identity_and_refuse_on_the_wire(self):
        for args in (("set", "lane/a", "--why", "x"), ("add", "lane/a", "--why", "x"), ("clear",)):
            with self.subTest(args=args):
                proc = self.run_lever(*args, identity=False)
                self.assertEqual(proc.exit, 2)
                self.assertEqual(proc.stdout, "")
                self.assertRegex(proc.stderr.strip(), r"^identity: expected .*; found .*; needed .*$")
                self.assertEqual(len(proc.stderr.strip().splitlines()), 1)

    def test_set_needs_branches_and_a_reason(self):
        for args in (("set",), ("set", "lane/a"), ("set", "--why", "x")):
            with self.subTest(args=args):
                proc = self.run_lever(*args)
                self.assertEqual(proc.exit, 2)
                self.assertTrue(proc.stderr.startswith("arguments: expected"), proc.stderr)

    def test_set_retargets_only_the_branch_it_names_and_refuses_a_stranger(self):
        """Origin T-71: a lead session ran `set` for its closing AAR and the
        lock then read one measure against all three branches, so two other
        sessions read short against a target that was never theirs. set
        re-targets what the lock already names; add introduces a branch."""
        first = self.measure_tool("a=1\n")
        second = self.measure_tool("b=1\n")
        self.run_lever("set", "lane/session-a", "--why", "session a",
                       "--measure", first, "--until", "a=1")
        self.run_lever("add", "lane/session-b", "--why", "session b",
                       "--measure", second, "--until", "b=1")

        third = self.measure_tool("a=2\n")
        proc = self.run_lever("set", "lane/session-a", "--why", "session a",
                              "--measure", third, "--until", "a=2")
        self.assertEqual(proc.exit, 0, proc.stderr)
        data = json.loads(self.lock.read_text())
        self.assertEqual(data["branches"],
                         ["lane/session-a", "lane/session-b"],
                         "set dropped a branch it was not asked about")
        self.assertEqual(data["targets"]["lane/session-a"]["until"], "a=2")
        self.assertEqual(data["targets"]["lane/session-b"]["until"], "b=1",
                         "set re-targeted another session's branch")
        self.assertEqual(data["targets"]["lane/session-b"]["measure"], json.loads(second))

        stranger = self.run_lever("set", "lane/session-z", "--why", "z")
        self.assertEqual(stranger.exit, 2)
        self.assertEqual(stranger.stdout, "")
        self.assertEqual(len(stranger.stderr.strip().splitlines()), 1)
        self.assertRegex(stranger.stderr.strip(),
                         r"^absent: expected .*; found .*; needed .*$")
        self.assertIn("lane/session-z", stranger.stderr)
        self.assertIn("add", stranger.stderr)
        self.assertEqual(json.loads(self.lock.read_text())["branches"],
                         ["lane/session-a", "lane/session-b"],
                         "a refused set still wrote the lock")

    def test_each_target_records_who_added_it_and_when(self):
        """Origin LD-49 (filed at 6fd0ba3b), beside T-71: a lock that stamps
        one `by` at the top cannot say which session added which branch, and
        add overwrote it, so the last writer owned them all. Each target
        carries its own by and at, and add leaves the lock-level by where it
        found it."""
        other = "Claude Opus 5 (1M context) <noreply@anthropic.com>"
        mine = self.measure_tool("a=1\n")
        theirs = self.measure_tool("b=1\n")
        self.run_lever("set", "lane/session-a", "--why", "session a",
                       "--measure", mine, "--until", "a=1")
        proc = self.run_lever("add", "lane/session-b", "--why", "session b",
                              "--measure", theirs, "--until", "b=1",
                              agent=other)
        self.assertEqual(proc.exit, 0, proc.stderr)

        data = json.loads(self.lock.read_text())
        self.assertEqual(data["targets"]["lane/session-a"]["by"], OWNER)
        self.assertEqual(data["targets"]["lane/session-b"]["by"], other)
        for branch in ("lane/session-a", "lane/session-b"):
            self.assertRegex(data["targets"][branch]["at"],
                             r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(data["by"], OWNER, "add overwrote the lock-level by")

        shown = self.run_lever("show", "lane/session-b", identity=False)
        self.assertIn("target lane/session-b: until b=1", shown.stdout)
        self.assertIn(f"(by {other})", shown.stdout)


class MeasureAsArgv(_LockFixture):
    """S3: --measure is a JSON list run as argv; a string refuses;
    a stored string reads as legacy-string; bare show runs no measure.

    Origin: issue 3 of the 2026-09-16 issues report; onboard's LD-48 retry.
    Planted faults: ops/conductor/tests/deliverable_faults.py.
    """

    def test_measure_is_argv(self):
        """id: measure-is-argv origin: issue 3"""
        self.world.require("sh")
        planted = "planted-x-value"
        measure = json.dumps(["sh", "-c", 'printf "%s" "$X"'])
        proc = self.run_lever(
            "add", "lane/x", "--why", "w",
            "--measure", measure, "--until", planted,
            extra={"X": planted},
        )
        self.assertEqual(proc.exit, 0, proc.stderr)
        first = self.run_lever("show", "lane/x", identity=False, extra={"X": planted})
        second = self.run_lever("show", "lane/x", identity=False, extra={"X": planted})
        self.assertEqual(first.exit, 0, first.stderr)
        self.assertEqual(second.exit, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        line = first.stdout.strip()
        self.assertIn(planted, line)
        self.assertIn("met", line)
        self.assertNotIn("legacy-string", line)
        self.assertEqual(json.loads(self.lock.read_text())["targets"]["lane/x"]["measure"],
                         json.loads(measure))

    def test_string_refuses(self):
        """id: string-refuses origin: issue 3"""
        proc = self.run_lever(
            "add", "lane/x", "--why", "w",
            "--measure", 'sh -c "echo hi"', "--until", "hi",
        )
        self.assertEqual(proc.exit, 2, proc.stdout)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1)
        refusal = proc.refusal()
        self.assertEqual(refusal.cls, "arguments")
        self.assertIn("JSON", proc.stderr)
        self.assertIn("list", proc.stderr)

    def test_legacy_string_reads(self):
        """id: legacy-string-reads origin: issue 3"""
        path = self.world.tools.plant("legacy-measure", stdout="hello from legacy\n", exit=0)
        data = {
            "branches": ["lane/x"],
            "why": "legacy",
            "targets": {
                "lane/x": {
                    "measure": f"{sys.executable} {path}",
                    "until": "hello from legacy",
                }
            },
        }
        self.world.plant_text(self.lock, json.dumps(data) + "\n")
        shown = self.run_lever("show", "lane/x", identity=False)
        self.assertEqual(shown.exit, 0, shown.stderr)
        self.assertIn("hello from legacy", shown.stdout)
        self.assertIn("legacy-string", shown.stdout)
        self.assertIn("met", shown.stdout)
        done = self.run_lever("done", "lane/x")
        self.assertEqual(done.exit, 0, done.stderr)
        self.assertIn("hello from legacy", done.stdout)

    def test_show_runs_nothing(self):
        """id: show-runs-nothing origin: issue 3"""
        measure = self.measure_tool("zzz\n", delay=20)
        proc = self.run_lever("add", "lane/x", "--why", "w",
                              "--measure", measure, "--until", "never")
        self.assertEqual(proc.exit, 0, proc.stderr)
        shown = self.run_lever("show", identity=False)
        self.assertEqual(shown.exit, 0, shown.stderr)
        self.assertLess(shown.duration, 2, shown.stderr)
        self.assertIn("reading not run", shown.stdout)
        self.assertIn("show lane/x reads it", shown.stdout)

    def test_show_branch_reads(self):
        """id: show-branch-reads origin: issue 3"""
        sleepy = self.measure_tool("zzz\n", delay=20)
        quick = self.measure_tool("y-reading\n")
        self.run_lever("add", "lane/x", "--why", "w",
                       "--measure", sleepy, "--until", "never")
        self.run_lever("add", "lane/y", "--why", "w",
                       "--measure", quick, "--until", "y-reading")
        shown = self.run_lever("show", "lane/y", identity=False)
        self.assertEqual(shown.exit, 0, shown.stderr)
        self.assertLess(shown.duration, 2, shown.stderr)
        self.assertIn("y-reading", shown.stdout)
        self.assertIn("met", shown.stdout)
        self.assertNotIn("reading not run", shown.stdout)

    def test_done_runs_one(self):
        """id: done-runs-one origin: issue 3"""
        sleepy = self.measure_tool("zzz\n", delay=20)
        quick = self.measure_tool("y-reading\n")
        self.run_lever("add", "lane/x", "--why", "w",
                       "--measure", sleepy, "--until", "never")
        self.run_lever("add", "lane/y", "--why", "w",
                       "--measure", quick, "--until", "y-reading")
        proc = self.run_lever("done", "lane/y")
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertLess(proc.duration, 2, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "done lane/y: y-reading")


if __name__ == "__main__":
    unittest.main()
