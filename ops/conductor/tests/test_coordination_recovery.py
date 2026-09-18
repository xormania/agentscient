"""Owner recovery uses an actual hand grant and keeps role history.

Dev-lane grant 309; one producer, independent test author absent.
"""

import json
import sqlite3
import sys
import unittest
from pathlib import Path

from ops.testkit import World, run

TOOLS = Path(__file__).resolve().parents[1] / "tools"
AGENT = "Recovery test model <noreply@example.test>"


class OwnerRecovery(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="coordination-recovery-")
        self.addCleanup(self.world.close)
        self.conf = self.world.plant_text("lane.conf", "LANE_NAME='testlane'\n")
        self.ok("old-lead", "bind", "--roles", "lead")
        self.ok("successor", "bind", "--roles", "worker")

    def invoke(self, session, *args, tool="coordination.py"):
        env = self.world.env(extra={"LANE_CONF": str(self.conf), "WF_AGENT": AGENT,
                                    "CODEX_THREAD_ID": session})
        return run([sys.executable, "-B", str(TOOLS / tool), *args],
                   cwd=self.world.cwd, env=env, timeout=20)

    def ok(self, session, *args):
        result = self.invoke(session, *args)
        self.assertEqual(result.exit, 0, result.stderr)
        return result.stdout

    def declare(self, session="successor", **changes):
        result = self.invoke(session, "declare", "Restore recovery coordination",
                             "Owner authorized recovery of the stopped lead", "other",
                             "--ttl", "30", tool="hand.py")
        self.assertEqual(result.exit, 0, result.stderr)
        ident = result.stdout.split()[1].rstrip(":")
        if changes:
            store = self.world.home / ".local/state/testlane/handwork.db"
            with sqlite3.connect(store) as conn:
                for key, value in changes.items():
                    conn.execute(f"UPDATE handwork SET {key}=? WHERE id=?", (value, ident))
        return ident

    def recover(self, grant, session="successor", roles="lead,coordinator,dispatcher"):
        return self.invoke(session, "recover-roles", "--grant", grant, "--roles", roles,
                           "--why", "Owner approved recovery after the old lead stopped")

    def test_recovery_and_identical_retry_preserve_history(self):
        grant = self.declare()
        for _ in range(2):
            result = self.recover(grant)
            self.assertEqual(result.exit, 0, result.stderr)
        with sqlite3.connect(self.world.xdg_state / "testlane/state.db") as conn:
            rows = conn.execute("SELECT session_id, roles FROM participants ORDER BY id").fetchall()
            receipts = conn.execute("SELECT previous_roles, grant_reading FROM owner_role_grants").fetchall()
        self.assertEqual(rows, [("old-lead", "lead"),
                                ("successor", "worker,lead,coordinator,dispatcher")])
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0][0], "worker")
        self.assertEqual(json.loads(receipts[0][1])["session"], "successor")
        denied = self.recover(grant, roles="verifier")
        self.assertEqual(denied.exit, 2, denied.stderr)
        self.assertIn("grant: expected", denied.stderr)

    def test_grant_must_belong_to_this_session_and_be_current(self):
        cases = ({"status": "settled"}, {"ts": "2000-01-01T00:00:00Z"},
                 {"agent": "Other model <noreply@example.test>"},
                 {"scope": "some/other/file"}, {"lever_class": "wall"})
        for changes in cases:
            with self.subTest(changes=changes):
                denied = self.recover(self.declare(**changes))
                self.assertEqual(denied.exit, 2, denied.stderr)
                self.assertIn("grant: expected", denied.stderr)
        denied = self.recover(self.declare(session="old-lead"))
        self.assertEqual(denied.exit, 2, denied.stderr)
        self.assertIn("grant: expected", denied.stderr)
        self.assertIn("worker", self.ok("successor", "who"))

    def test_missing_grant_and_ordinary_self_grant_stay_refused(self):
        denied = self.recover("9999")
        self.assertEqual(denied.exit, 2, denied.stderr)
        self.assertIn("grant: expected", denied.stderr)
        denied = self.invoke("successor", "grant", "PT-2", "--roles", "lead")
        self.assertEqual(denied.exit, 2, denied.stderr)
        self.assertIn("role: expected", denied.stderr)


if __name__ == "__main__":
    unittest.main()
