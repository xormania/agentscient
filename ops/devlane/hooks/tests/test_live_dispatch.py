"""live-dispatch: a worktree a running dispatch was launched from is not moved
under it.

LD-119 (2026-09-22) and its recurrence LD-142 (2026-09-23): a dispatched
worker's guard pins the helper from the worktree it was launched from, and
a merge into that worktree while the worker runs voids the pin; the worker
finishes its review and is then refused coord_submit, so the assignment
stays held. The fix in force was a rule relayed by message and it recurred
(D-PATTERN-1), so this is the mechanism: `git merge`, `pull`, `checkout`,
`reset` and `rebase` in a worktree that a running dispatch record names as
its source refuse class `live-dispatch`, expected no running dispatch from
this worktree, found the record id, needed wait for its close or merge
after. No grant escape.

Running is onboard.py's reading: no exit file, record.json status
`launched`, state.json's pid alive. The source is the dispatch's
enforcement/binding.json `source`, the worktree whose helper the worker
pinned. A running dispatch whose source cannot be read refuses: could not
look is not a pass.

One producer (Claude Opus 5.5) under wall grant 363 wrote these rows and the
row; no second producer.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from ops.testkit import World, run

HOOK = Path(__file__).resolve().parents[1] / "claude" / "matrix.py"
RECORD = "20260923T040605Z-review-codex-6ed2cb"
OTHER = "20260923T040654Z-review-codex-8649a7"
TIMEOUT = 60
MOVES = ("git merge dev", "git pull", "git checkout other", "git reset --hard HEAD~1",
         "git rebase dev", "git merge --ff-only origin/dev", "git checkout -- ops/lane.conf")
READS = ("git status", "git log --oneline -3", "git diff dev", "git fetch origin",
         "git show HEAD", "git branch --show-current")


class LiveDispatch(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="live-dispatch-")
        self.addCleanup(self.world.close)
        self.world.require("git")
        self.sleep = self.world.require("sleep")
        self.hook = self._subject()
        self.repo = self.world.cwd
        self.world.git("init", "-q", "-b", "dev")
        self.world.plant_text(self.repo / "ops" / "lane.conf",
                              "LANE_NAME='agentscient'\nTRUNK_BRANCH='dev'\nSCOPE_CAP='1024'\n")
        self.world.git("add", "-A")
        self.world.git("commit", "-q", "-m", "fixture")
        self.world.git("checkout", "-q", "-b", "lane/fixture")
        self.elsewhere = self.world.root / "elsewhere"
        self.elsewhere.mkdir()
        self.world.git("init", "-q", "-b", "dev", cwd=self.elsewhere)
        self.env = self.world.env()
        # Where launch.py's _jobs_root writes: the world sets XDG_STATE_HOME
        # apart from HOME, so a gate reading HOME alone is caught (A-541 #1).
        self.store = Path(self.env["XDG_STATE_HOME"]) / "agentscient/dispatch"

    def _subject(self):
        staged = self.world.stage(HOOK, siblings=("miss.py", "command_shape.py"))
        src = HOOK.parent.parent / "boundaries.json"
        self.world.plant_bytes(staged.parent.parent / "boundaries.json", src.read_bytes())
        return staged

    def live_pid(self):
        child = self.world.own(subprocess.Popen([self.sleep, "120"]))  # a planted pid, reaped at close
        return child.pid

    def dispatch(self, rid, *, source, status="launched", pid=None, exited=False, binding=True):
        """Plant a dispatch directory as launch.py leaves it."""
        root = self.store / rid
        self.world.plant_text(root / "record.json", json.dumps({"id": rid, "status": status}))
        self.world.plant_text(root / "state.json", json.dumps({"pid": pid if pid is not None else self.live_pid()}))
        if binding:
            self.world.plant_text(root / "enforcement/binding.json",
                                  json.dumps({"source": str(source), "mode": "worker"}))
        if exited:
            self.world.plant_text(root / "exit", "0\n")
        return root

    def run_bash(self, command, cwd=None, env=None):
        cwd = cwd or self.repo
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)})
        return run([sys.executable, str(self.hook)], cwd=str(cwd), env=env or self.env, stdin=payload,
                   timeout=TIMEOUT)

    def refusal(self, proc, command):
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertTrue(proc.stdout.strip(), f"{command}: the hook let it through")
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny", command)
        reason = out["permissionDecisionReason"]
        self.assertTrue(reason.startswith("[matrix:live-dispatch] live-dispatch: expected "), reason)
        self.assertIn("; found ", reason)
        self.assertIn("; needed ", reason)
        return reason

    def allowed(self, proc, command):
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertNotIn("live-dispatch", proc.stdout, command)

    def test_moving_a_worktree_a_running_dispatch_came_from_is_refused_with_its_record(self):
        # origin: LD-142; the XO merged dev into the launching worktree at 04:14Z
        # while A-522 and A-525 ran from it.
        self.dispatch(RECORD, source=self.repo)
        for command in MOVES:
            with self.subTest(command=command):
                reason = self.refusal(self.run_bash(command), command)
                self.assertIn(RECORD, reason.split("; found ", 1)[1])
                self.assertIn("no running dispatch", reason.split("; found ", 1)[0])
                self.assertIn("close", reason.split("; needed ", 1)[1])

    def test_the_worktree_is_found_through_dash_C_and_from_a_subdirectory(self):
        self.dispatch(RECORD, source=self.repo)
        self.refusal(self.run_bash(f"git -C {self.repo} merge dev", cwd=self.elsewhere), "git -C")
        self.refusal(self.run_bash("git merge dev", cwd=self.repo / "ops"), "subdirectory")
        self.refusal(self.run_bash("git fetch -q origin && git merge origin/dev"), "a second statement")

    def test_the_store_is_the_one_the_launcher_resolves(self):
        # origin: 20260923T050106Z-review-codex-3e82cf#1. launch.py's _jobs_root:
        # DISPATCH_JOBS, then XDG_STATE_HOME, then HOME's .local/state.
        jobs = self.world.root / "jobs"
        home_store = self.world.home / ".local/state/agentscient/dispatch"
        without_xdg = {k: v for k, v in self.env.items() if k != "XDG_STATE_HOME"}
        cases = {
            "XDG_STATE_HOME": (self.store, self.env),
            "DISPATCH_JOBS": (jobs, {**self.env, "DISPATCH_JOBS": str(jobs)}),
            "HOME": (home_store, without_xdg),
        }
        for name, (store, env) in cases.items():
            with self.subTest(store=name):
                self.store = store
                root = self.dispatch(RECORD, source=self.repo)
                self.assertIn(RECORD, self.refusal(self.run_bash("git merge dev", env=env), name))
                shutil.rmtree(root)
        # Clean neighbour: a dispatch under HOME while XDG_STATE_HOME names
        # another store is not the launcher's store and is not read.
        self.store = home_store
        self.dispatch(RECORD, source=self.repo)
        self.allowed(self.run_bash("git merge dev"), "a store the launcher does not use")

    def test_a_cd_earlier_in_the_chain_is_the_directory_the_row_reads(self):
        # origin: 20260923T050106Z-review-codex-3e82cf#2. `cd <wt> && git merge dev`
        # is the ordinary shape; the row reads the directory the statement runs in.
        self.dispatch(RECORD, source=self.repo)
        for command in (f"cd {self.repo} && git merge dev", f"cd {self.repo}/ops && git rebase dev",
                        f"cd -- {self.repo}; git pull", f"cd {self.elsewhere} && cd {self.repo} && git merge dev"):
            with self.subTest(command=command):
                self.assertIn(RECORD, self.refusal(self.run_bash(command, cwd=self.elsewhere), command))
        # Clean neighbours: a chain that leaves the held worktree before it moves one.
        for command in (f"cd {self.elsewhere} && git merge dev", f"cd {self.repo} && cd {self.elsewhere} && git merge dev"):
            with self.subTest(command=command):
                self.allowed(self.run_bash(command), command)

    def test_a_grant_is_no_escape(self):
        self.dispatch(RECORD, source=self.repo)
        self.refusal(self.run_bash("HAND_GRANT=1 git merge dev"), "granted")

    def test_a_running_dispatch_whose_source_cannot_be_read_refuses(self):
        # Could not look is not a pass (matrix.py's header).
        self.dispatch(RECORD, source=self.repo, binding=False)
        reason = self.refusal(self.run_bash("git merge dev"), "no binding")
        self.assertIn(RECORD, reason)

    def test_reads_in_that_worktree_are_untouched(self):
        self.dispatch(RECORD, source=self.repo)
        for command in READS:
            with self.subTest(command=command):
                self.allowed(self.run_bash(command), command)

    def test_clean_neighbours_pass(self):
        # A dispatch that closed, one whose pid is gone, one not launched, and one
        # running from another worktree: none of them holds this worktree.
        gone = self.world.own(subprocess.Popen([self.sleep, "0"]))  # a pid that has exited
        self.world.reap(gone)
        cases = {
            "closed": {"exited": True},
            "pid-gone": {"pid": gone.pid},
            "not-launched": {"status": "closed"},
            "other-worktree": {"source": self.elsewhere},
        }
        for name, fields in cases.items():
            with self.subTest(case=name):
                root = self.dispatch(OTHER, **{"source": self.repo, **fields})
                self.allowed(self.run_bash("git merge dev"), name)
                self.allowed(self.run_bash("git rebase dev"), name)
                shutil.rmtree(root)
        self.allowed(self.run_bash("git merge dev"), "an empty store")
        os.rmdir(self.store)
        self.allowed(self.run_bash("git merge dev"), "no store")

    def test_the_docstring_table_names_the_row(self):
        text = self.hook.read_text(encoding="utf-8")
        self.assertIn("live-dispatch", text.split('"""', 2)[1])
        rows = json.loads((HOOK.parent.parent / "boundaries.json").read_text(encoding="utf-8"))["rows"]
        row = next((r for r in rows if r["class"] == "live-dispatch"), None)
        self.assertIsNotNone(row, "boundaries.json declares no live-dispatch row")
        self.assertEqual(row["escape"], "none")


if __name__ == "__main__":
    unittest.main()
