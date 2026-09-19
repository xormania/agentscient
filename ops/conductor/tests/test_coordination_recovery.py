"""Owner recovery uses an actual hand grant and keeps role history.

Dev-lane grant 309; one producer, independent test author absent.
"""

import datetime
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
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
                                    "CODEX_THREAD_ID": session,
                                    "COORDINATION_CAPABILITY": hashlib.sha256(session.encode()).hexdigest()})
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

    def test_invalid_numeric_grants_refuse_on_the_wire(self):
        for grant in ("²", "9" * 100, "-1", "0"):
            with self.subTest(grant=grant):
                denied = self.recover(grant)
                self.assertEqual(denied.exit, 2, denied.stderr)
                self.assertTrue(denied.stderr.startswith("grant: expected"), denied.stderr)
                self.assertNotIn("Traceback", denied.stderr)

    def test_out_of_range_grant_duration_refuses_on_the_wire(self):
        made = self.invoke("successor", "declare", "Recover isolated role",
                           "Owner authorized isolated recovery test", "other",
                           "--ttl", "1000000000000000", tool="hand.py")
        self.assertEqual(made.exit, 0, made.stderr)
        denied = self.recover(made.stdout.split()[1].rstrip(":"))
        self.assertEqual(denied.exit, 2, denied.stderr)
        self.assertNotIn("Traceback", denied.stderr)

    def test_expiry_while_waiting_for_the_write_lock_refuses(self):
        # Independent review R1: a grant can expire while another caller
        # holds the coordination write lock. Exercise both actual stores.
        grant = self.declare()
        store = self.world.xdg_state / "testlane/state.db"
        hand_store = self.world.home / ".local/state/testlane/handwork.db"
        started = datetime.datetime.now(datetime.timezone.utc)
        with sqlite3.connect(hand_store) as hand:
            hand.execute("UPDATE handwork SET ts=?, ttl_s=2 WHERE id=?",
                         (started.isoformat(), grant))
        blocker = sqlite3.connect(store, isolation_level=None)
        self.addCleanup(blocker.close)
        blocker.execute("BEGIN IMMEDIATE")
        source = """
import sqlite3, sys
sys.path.insert(0, sys.argv[1])
import coordination as c
conn = sqlite3.connect(sys.argv[2], isolation_level=None, timeout=10)
conn.row_factory = sqlite3.Row
part = conn.execute("SELECT * FROM participants WHERE session_id='successor'").fetchone()
try:
    c.core_recover_roles(conn, dict(part), agent=c.identity(), grant=sys.argv[3],
                         roles='lead', why='Owner authorized isolated recovery test')
except c.Refusal as error:
    print(str(error), file=sys.stderr)
    raise SystemExit(2)
"""
        env = self.world.env(extra={"LANE_CONF": str(self.conf), "WF_AGENT": AGENT,
                                    "CODEX_THREAD_ID": "successor",
                                    "COORDINATION_CAPABILITY": hashlib.sha256(b"successor").hexdigest()})
        proc = subprocess.Popen([sys.executable, "-B", "-c", source, str(TOOLS),
                                 str(store), grant], cwd=self.world.cwd, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            saw_hand_lock = False
            until = time.monotonic() + 1.5
            while time.monotonic() < until:
                observer = sqlite3.connect(hand_store, isolation_level=None, timeout=0)
                try:
                    observer.execute("BEGIN IMMEDIATE")
                    observer.rollback()
                except sqlite3.OperationalError:
                    saw_hand_lock = True
                    break
                finally:
                    observer.close()
                time.sleep(0.01)
            self.assertTrue(saw_hand_lock, "authorization lock was not observed")
            while datetime.datetime.now(datetime.timezone.utc) <= started + datetime.timedelta(seconds=2.1):
                time.sleep(0.02)
            blocker.rollback()
            out, err = proc.communicate(timeout=15)
            self.assertEqual(proc.returncode, 2, out + err)
            self.assertTrue(err.startswith("grant: expected"), err)
            with sqlite3.connect(store) as conn:
                roles = conn.execute("SELECT roles FROM participants WHERE session_id='successor'").fetchone()[0]
                self.assertEqual(roles, "worker")
        finally:
            blocker.rollback()
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
