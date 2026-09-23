"""Storage invariants, shared by every instrument; kit-owned scratch only.

Contract: instrument-conventions.md, Storage primitives. Owner-authorized
dev-lane consolidation; independent test producer absent.
"""

from __future__ import annotations

import ast
import sqlite3
import sys
import unittest
from contextlib import closing

from test_instrument import TOOLS, load

from ops.testkit import World, run


class Storage(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="storage-")
        self.addCleanup(self.world.close)
        self.m = load()
        self.path = self.world.root / "state ?#%.db"

    def seed(self):
        conn = self.m.connect_store(self.path, mode="rwc", isolation_level=None)
        self.addCleanup(conn.close)
        conn.execute("CREATE TABLE value(n INTEGER)")
        conn.execute("INSERT INTO value VALUES (0)")
        return conn

    def test_access_modes_and_escaped_paths(self):
        self.seed()
        self.assertTrue(self.path.is_file(), "SQLite must open the literal path, including URI punctuation")
        for mode in ("ro", "rw", "rwc"):
            with self.subTest(mode=mode), closing(self.m.connect_store(self.path, mode=mode)) as conn:
                self.assertEqual(conn.execute("SELECT n FROM value").fetchone()[0], 0)
                if mode == "ro":
                    for sql in ("UPDATE value SET n=1", "CREATE TABLE extra(n)", "CREATE TEMP TABLE extra(n)"):
                        with self.subTest(sql=sql), self.assertRaises(sqlite3.OperationalError):
                            conn.execute(sql)
                else:
                    conn.execute("UPDATE value SET n=1")
                    conn.rollback()

    def test_only_create_mode_creates_directories_or_store(self):
        path = self.world.root / "absent" / "state.db"
        for mode in ("ro", "rw"):
            with self.subTest(mode=mode), self.assertRaises(sqlite3.OperationalError):
                self.m.connect_store(path, mode=mode)
            self.assertFalse(path.parent.exists())
        with closing(self.m.connect_store(path, mode="rwc")):
            self.assertTrue(path.is_file())
        with self.assertRaises(ValueError):
            self.m.connect_store(path, mode="invalid")

    def test_commit_and_every_exception_leave_no_partial_transaction(self):
        conn = self.seed()
        with self.m.transaction(conn):
            conn.execute("UPDATE value SET n=1")
        for failure in (ValueError("fault"), KeyboardInterrupt(), SystemExit(3)):
            with self.subTest(failure=type(failure).__name__):
                with self.assertRaises(type(failure)), self.m.transaction(conn):
                    conn.execute("UPDATE value SET n=2")
                    raise failure
                self.assertFalse(conn.in_transaction)
                self.assertEqual(conn.execute("SELECT n FROM value").fetchone()[0], 1)

    def test_commit_failure_rolls_back_and_releases_writer(self):
        conn = self.seed()
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE child(id REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED)")
        with self.assertRaises(sqlite3.IntegrityError), self.m.transaction(conn):
            conn.execute("INSERT INTO child VALUES (9)")
        self.assertFalse(conn.in_transaction)
        self.assertEqual(conn.execute("SELECT count(*) FROM child").fetchone()[0], 0)
        with self.m.transaction(conn):
            conn.execute("INSERT INTO parent VALUES (9)")

    def test_nested_transaction_does_not_commit_or_rollback_its_callers_work(self):
        conn = self.seed()
        with self.m.transaction(conn):
            conn.execute("UPDATE value SET n=1")
            with self.assertRaises(sqlite3.OperationalError), self.m.transaction(conn):
                self.fail("nested transaction must not start")
            self.assertTrue(conn.in_transaction)
        self.assertEqual(conn.execute("SELECT n FROM value").fetchone()[0], 1)

    def test_lock_is_acquired_before_reading_and_released_after_failure(self):
        first = self.seed()
        with closing(self.m.connect_store(self.path, mode="rw", timeout=0, isolation_level=None)) as second:
            with self.m.transaction(first):
                with self.assertRaises(sqlite3.OperationalError), self.m.transaction(second):
                    self.fail("a second writer must not reach its read")
                self.assertTrue(first.in_transaction)
            with self.m.transaction(second):
                second.execute("UPDATE value SET n=n+1")
            self.assertEqual(first.execute("SELECT n FROM value").fetchone()[0], 1)

    def test_read_adapters_share_the_same_permission_boundary(self):
        conf = self.world.plant_text("lane.conf", "LANE_NAME='storage-test'\n")
        # A fresh interpreter keeps file-loaded modules from other suites out
        # of this integration reading; every adapter uses the kit's state root.
        code = """
import sys
from contextlib import closing
import sqlite3
sys.path.insert(0, sys.argv[1])
import ci, coordination, decisions, handoff, ledger, machine, sessions
writers = [lambda: ci.connect(write=True), lambda: decisions.connect(write=True),
           handoff.writer, ledger.reservation_writer, sessions.writer]
for writer in writers:
    with closing(writer()):
        pass
readers = [lambda: ci.connect(write=False), lambda: decisions.connect(write=False),
           coordination.reader, handoff.reader, ledger.reservation_reader,
           lambda: machine.connect(create=False), sessions.reader,
           sessions.coordination_reader]
for reader in readers:
    with closing(reader()) as conn:
        assert conn.execute('SELECT 1').fetchone()[0] == 1
        try:
            conn.execute('CREATE TABLE forbidden_write(n INTEGER)')
        except sqlite3.OperationalError:
            continue
        raise AssertionError(f'{reader} gave a read caller write authority')
"""
        result = run([sys.executable, "-B", "-c", code, str(TOOLS)],
                     cwd=self.world.cwd, env=self.world.env({"LANE_CONF": str(conf)}), timeout=30)
        self.assertEqual(result.exit, 0, result.stdout + result.stderr)

    def test_storage_mechanisms_have_one_runtime_owner(self):
        copies = []
        for path in TOOLS.glob("*.py"):
            if path.name == "instrument.py":
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node, ast.Call):
                    continue
                # A synthetic empty register has no file authority.
                if (ast.unparse(node.func) == "sqlite3.connect"
                        and (not node.args or not isinstance(node.args[0], ast.Constant)
                             or node.args[0].value != ":memory:")):
                    copies.append(f"{path.name}:{node.lineno}: private file connection")
                if (isinstance(node.func, ast.Attribute) and node.func.attr == "execute"
                        and node.args and isinstance(node.args[0], ast.Constant)
                        and str(node.args[0].value).upper().startswith("BEGIN")):
                    copies.append(f"{path.name}:{node.lineno}: private transaction")
        self.assertEqual(copies, [], "use the shared storage primitives")
