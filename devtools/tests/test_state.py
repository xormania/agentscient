"""Persistence invariants shared by runtime services and operator inspection."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from devtools.store import State


class StateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_inspection_preserves_existing_schema_and_observes_fresh_commits(self):
        view = State(self.root)
        with self.assertRaises(sqlite3.OperationalError), view.connect():
            pass
        self.assertEqual([], list(self.root.iterdir()))

        writer = State(self.root, read_only=False)
        with writer.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE retained (value INTEGER NOT NULL)")
            db.execute("INSERT INTO retained VALUES (1)")
            db.execute("PRAGMA user_version=1")

        with view.connect() as db:
            self.assertEqual(1, db.execute("PRAGMA user_version").fetchone()[0])
            self.assertEqual(["retained"], [row[0] for row in db.execute("SELECT name FROM sqlite_master")])
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("UPDATE retained SET value=0")

        with view.connect() as db:
            db.execute("BEGIN")
            self.assertEqual(1, db.execute("SELECT value FROM retained").fetchone()["value"])
            with writer.connect() as changed:
                changed.execute("UPDATE retained SET value=2")
            self.assertEqual(1, db.execute("SELECT value FROM retained").fetchone()["value"])

        with view.connect() as db:
            self.assertEqual(2, db.execute("SELECT value FROM retained").fetchone()["value"])

    def test_failed_transaction_rolls_back_and_always_closes_connection(self):
        state = State(self.root, read_only=False)
        with state.connect() as db:
            db.executescript("CREATE TABLE parent (id INTEGER PRIMARY KEY);"
                             "CREATE TABLE child (parent INTEGER REFERENCES parent(id));")
            db.execute("INSERT INTO parent VALUES (1)")
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute("SELECT 1")

        with self.assertRaises(sqlite3.IntegrityError), state.connect() as db:
            db.execute("INSERT INTO parent VALUES (2)")
            db.execute("INSERT INTO child VALUES (99)")
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute("SELECT 1")
        with State(self.root).connect() as db:
            self.assertEqual([1], [row[0] for row in db.execute("SELECT id FROM parent")])
            self.assertEqual([], list(db.execute("SELECT * FROM child")))


if __name__ == "__main__":
    unittest.main()
