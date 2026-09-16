"""dispatcher: only the session named as Dispatcher may send a dispatch.

Owner, 2026-09-12, settling one branch per session: "as long you account
for the fact that i'll have multiple sessions running soon". Several
sessions sending dispatches at once is how two of them launch the same
job, merge the trunk under each other and read a board that moved; the
lane's answer is one Dispatcher on the host, named in the state engine,
and `ops/bin/dispatch.sh` and `ops/bin/go.sh` refusing every other
session.

The row: class `dispatcher`, boundary `dispatch`, no escape — a grant
does not lift it, because the remedy is not a write the session may be
trusted with, it is sending the request to another session. The gate
reads `holder_note` of the one subject of the `dispatcher` machine in
`state.db` and compares it with the session the harness named for this
one. It never reads the working directory: two sessions in one worktree
are still two sessions, and one worktree per session is not a rule the
lane has.

Absence is declared, never inferred (docs/wire.md). Three readings are
kept apart: no Dispatcher named, which says `dispatcher.py set`; a
Dispatcher named that is somebody else, which names both ids; and a
store the gate could not read, which says so rather than reading as
nobody holding the role.

The fixture drives the real `ops/conductor/tools/dispatcher.py` rather
than writing rows into the store by hand, so the seam between the lever
and the wall is measured and not assumed. On the host the gate's
`~/.local/state` and the lever's `XDG_STATE_HOME` name one directory;
the fixture makes them name one directory too.

One producer (Claude Opus 5 (1M context)) under hand grant 264 wrote
these tests, the row and the gate; the second producer is absent by the
owner's word (AGENTS.md, dev-lane changes by hand).
"""

from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path

from ops.testkit import World, run

HOOK = Path(__file__).resolve().parents[1] / "claude" / "matrix.py"
TOOLS = Path(__file__).resolve().parents[4] / "ops" / "conductor" / "tools"
LEVER = TOOLS / "dispatcher.py"
MINE = "session-mine-0001"
THEIRS = "session-theirs-0002"
TIMEOUT = 60
AGENT = "Test Dispatcher <test@example.invalid>"


class TheDispatcherRole(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="dispatch-role-")
        self.addCleanup(self.world.close)
        self.world.require("git")
        self.hook = self.world.stage(HOOK, siblings=("miss.py", "command_shape.py"))
        src = HOOK.parent.parent / "boundaries.json"
        self.world.plant_bytes(self.hook.parent.parent / "boundaries.json", src.read_bytes())
        self.repo = self.world.cwd
        self.state = self.world.home / ".local" / "state" / "agentscient"
        self.world.plant_text(self.repo / "ops" / "lane.conf",
                              "LANE_NAME='agentscient'\nTRUNK_BRANCH='dev'\n")
        self.world.plant_text(self.repo / "ops" / "bin" / "dispatch.sh", "#!/bin/sh\nexit 0\n")
        self.world.plant_text(self.repo / "ops" / "bin" / "go.sh", "#!/bin/sh\nexit 0\n")
        # `plan` is a session-owned read job, so a well-formed call of it
        # crosses every other row of this boundary and reaches ours.
        self.world.plant_text(self.repo / "s.md", "# the scope\n\nread the tree.\n")
        self.world.git("init", "-q", "-b", "dev")

    # -- the lever ---------------------------------------------------------

    def lever(self, *args, expect=0):
        """The real dispatcher.py, writing into this world's state store."""
        if not LEVER.is_file():
            self.fail(f"the lever is not in the tree yet: {LEVER}")
        env = self.world.env(extra={
            "XDG_STATE_HOME": str(self.world.home / ".local" / "state"),
            "WF_AGENT": AGENT,
            "LANE_CONF": str(self.repo / "ops" / "lane.conf"),
            "CLAUDE_CODE_SESSION_ID": MINE,
        })
        result = run([sys.executable, str(LEVER), *args], cwd=str(self.repo),
                     env=env, timeout=TIMEOUT)
        if expect is not None and result.exit != expect:
            self.fail(f"dispatcher.py {' '.join(args)} exit {result.exit}: "
                      f"{result.stderr or result.stdout}")
        return result

    def named(self):
        """What the store holds for the role, read the way the gate reads it."""
        db = self.state / "state.db"
        if not db.is_file():
            return None
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT place, holder_note FROM subjects WHERE machine = 'dispatcher'"
        ).fetchone()
        conn.close()
        return row

    # -- the call ----------------------------------------------------------

    def bash(self, command, *, session=MINE):
        env = self.world.env(extra={"CLAUDE_CODE_SESSION_ID": session} if session
                             else {"CLAUDE_CODE_SESSION_ID": ""})
        payload = json.dumps({"tool_name": "Bash",
                              "tool_input": {"command": command},
                              "cwd": str(self.repo),
                              "session_id": session or ""})
        return run([sys.executable, str(self.hook)], cwd=str(self.repo),
                   env=env, stdin=payload, timeout=TIMEOUT)

    DISPATCH = "ops/bin/dispatch.sh --job plan --scope-file s.md"

    def refusal(self, proc):
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertTrue(proc.stdout.strip(), "hook let the call through")
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        reason = out["permissionDecisionReason"]
        self.assertTrue(reason.startswith("[matrix:dispatcher] dispatcher: expected "), reason)
        self.assertIn("; found ", reason)
        self.assertIn("; needed ", reason)
        return reason

    def allowed(self, proc):
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "", proc.stdout)

    # -- the rows ----------------------------------------------------------

    def test_no_dispatcher_named_refuses_and_names_the_lever(self):
        reason = self.refusal(self.bash(self.DISPATCH))
        self.assertIn("expected a Dispatcher named", reason)
        self.assertIn("found none", reason)
        self.assertIn("dispatcher.py set", reason)

    def test_the_named_session_dispatches(self):
        self.lever("set", MINE, "--why", "the lane's dispatcher for today")
        row = self.named()
        self.assertIsNotNone(row, "the lever wrote no subject")
        self.assertEqual((row[0], row[1]), ("named", MINE))
        self.allowed(self.bash(self.DISPATCH, session=MINE))

    def test_another_session_refuses_and_both_ids_are_named(self):
        self.lever("set", MINE, "--why", "the lane's dispatcher for today")
        reason = self.refusal(self.bash(self.DISPATCH, session=THEIRS))
        self.assertIn(MINE, reason)
        self.assertIn(THEIRS, reason)
        self.assertIn("send the request to the Dispatcher", reason)

    def test_a_session_the_harness_did_not_name_refuses(self):
        self.lever("set", MINE, "--why", "the lane's dispatcher for today")
        reason = self.refusal(self.bash(self.DISPATCH, session=""))
        self.assertIn(MINE, reason)
        self.assertIn("the harness named no session", reason)

    def test_go_sh_carries_the_row_too(self):
        self.lever("set", MINE, "--why", "the lane's dispatcher for today")
        reason = self.refusal(self.bash("ops/bin/go.sh --job plan --scope-file s.md",
                                        session=THEIRS))
        self.assertIn(MINE, reason)

    def test_a_grant_is_no_escape(self):
        self.lever("set", MINE, "--why", "the lane's dispatcher for today")
        reason = self.refusal(self.bash(f"HAND_GRANT=264 {self.DISPATCH}", session=THEIRS))
        self.assertIn(MINE, reason)

    def test_clear_puts_it_back_to_none(self):
        self.lever("set", MINE, "--why", "the lane's dispatcher for today")
        self.lever("clear", "--why", "the session is closing")
        reason = self.refusal(self.bash(self.DISPATCH, session=MINE))
        self.assertIn("found none", reason)

    def test_a_store_that_cannot_be_read_is_not_none(self):
        self.lever("set", MINE, "--why", "the lane's dispatcher for today")
        self.world.plant_text(self.state / "state.db", "not a database\n")
        reason = self.refusal(self.bash(self.DISPATCH, session=MINE))
        self.assertIn("could not be read", reason)
        self.assertNotIn("found none", reason)

    def test_a_command_that_is_not_a_dispatch_is_untouched(self):
        self.allowed(self.bash("git status --short", session=THEIRS))

    def test_the_docstring_table_names_the_row(self):
        text = HOOK.read_text(encoding="utf-8")
        self.assertIn("\n    dispatcher ", text,
                      "the matrix docstring table does not name the row")


if __name__ == "__main__":
    unittest.main()
