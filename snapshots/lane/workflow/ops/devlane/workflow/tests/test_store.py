"""store.py — the nine tables of PLAN §3.2 and migration discipline (§6)."""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import support
from support import plant_bytes
import canonical
import store
from errors import Integrity, Refusal

# PLAN §3.2 says nine tables and names them.  The assertion is the plan.
EXPECTED_TABLES = {
    "work_orders", "events", "wo_state", "gate_kinds", "artifacts",
    "claims", "sessions", "attempts", "schema_migrations",
}

REAL_MIGRATIONS = support.WF_DIR / "migrations"


class Fresh(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="wf-store-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.migrations = self.dir / "migrations"
        self.migrations.mkdir()
        for src in REAL_MIGRATIONS.glob("*.sql"):
            shutil.copy(src, self.migrations / src.name)

    def open(self, name="t.db"):
        st = store.Store(self.dir / name)
        self.addCleanup(st.close)
        return st

    def tables(self, st):
        return {
            r["name"]
            for r in st.all("SELECT name FROM sqlite_master WHERE type='table'")
            if not r["name"].startswith("sqlite_")
        }


class Migrations(Fresh):
    def test_creates_exactly_the_nine_tables_the_plan_names(self):
        st = self.open()
        st.migrate(self.migrations, canonical.now())
        self.assertEqual(self.tables(st), EXPECTED_TABLES)

    def test_is_idempotent(self):
        st = self.open()
        first = st.migrate(self.migrations, canonical.now())
        second = st.migrate(self.migrations, canonical.now())
        self.assertEqual(first, ["0001_foundation.sql"])
        self.assertEqual(second, [])
        self.assertEqual(self.tables(st), EXPECTED_TABLES)

    def test_records_the_digest_of_the_file_it_applied(self):
        st = self.open()
        st.migrate(self.migrations, canonical.now())
        row = st.one("SELECT * FROM schema_migrations WHERE version = 1")
        on_disk = canonical.sha256_hex(
            (self.migrations / "0001_foundation.sql").read_bytes()
        )
        self.assertEqual(row["sha256"], on_disk)
        self.assertEqual(row["name"], "0001_foundation.sql")

    # -- planted faults ----------------------------------------------------

    def test_detects_an_applied_migration_that_changed_afterwards(self):
        st = self.open()
        st.migrate(self.migrations, canonical.now())
        target = self.migrations / "0001_foundation.sql"
        plant_bytes(
            target,
            lambda raw: raw.replace(b"CREATE INDEX events_by_hash", b"CREATE INDEX events_by_hasH"),
            expect="edit",
            recognisable=lambda raw: b"CREATE TABLE events" in raw,
        )
        with self.assertRaises(Integrity) as caught:
            st.migrate(self.migrations, canonical.now())
        self.assertIn("has changed since it was applied", str(caught.exception))

    def test_detects_an_applied_migration_that_was_renamed(self):
        st = self.open()
        st.migrate(self.migrations, canonical.now())
        src = self.migrations / "0001_foundation.sql"
        body = src.read_bytes()
        dst = self.migrations / "0001_renamed.sql"
        src.rename(dst)
        self.assertFalse(src.exists(), "plant: the original name must be gone")
        self.assertEqual(dst.read_bytes(), body, "plant: content must be unchanged")
        with self.assertRaises(Integrity) as caught:
            st.migrate(self.migrations, canonical.now())
        self.assertIn("renamed", str(caught.exception))

    def test_refuses_an_unnumbered_file_in_the_migrations_directory(self):
        (self.migrations / "notes.txt").write_text("stray\n")
        st = self.open()
        with self.assertRaises(Refusal) as caught:
            st.migrate(self.migrations, canonical.now())
        self.assertIn("numbered migration", str(caught.exception))

    def test_refuses_two_files_claiming_the_same_version(self):
        shutil.copy(
            self.migrations / "0001_foundation.sql", self.migrations / "0001_other.sql"
        )
        st = self.open()
        with self.assertRaises(Refusal) as caught:
            st.migrate(self.migrations, canonical.now())
        self.assertIn("unique", str(caught.exception))


class Atomicity(Fresh):
    def test_a_failing_migration_leaves_neither_schema_nor_bookkeeping(self):
        # executescript() implicitly commits before it runs, which would apply
        # the DDL outside the transaction that records it.  This is the test
        # that catches a regression back to it.
        (self.migrations / "0002_broken.sql").write_text(
            "CREATE TABLE half_applied (a TEXT);\n"
            "CREATE TABLE half_applied (a TEXT);\n"  # duplicate: fails
        )
        st = self.open()
        with self.assertRaises(sqlite3.OperationalError):
            st.migrate(self.migrations, canonical.now())
        self.assertNotIn("half_applied", self.tables(st))
        self.assertIsNone(st.one("SELECT * FROM schema_migrations WHERE version = 2"))
        # …and the good migration before it stayed applied.
        self.assertIsNotNone(st.one("SELECT * FROM schema_migrations WHERE version = 1"))


class Statements(unittest.TestCase):
    def test_splits_on_statement_boundaries(self):
        script = "CREATE TABLE a (x TEXT);\nCREATE TABLE b (y TEXT);\n"
        self.assertEqual(
            list(store.sql_statements(script)),
            ["CREATE TABLE a (x TEXT);", "CREATE TABLE b (y TEXT);"],
        )

    def test_a_semicolon_inside_a_string_literal_is_not_a_boundary(self):
        script = "INSERT INTO a VALUES ('one; two');\n"
        self.assertEqual(list(store.sql_statements(script)), [script.strip()])

    def test_a_semicolon_inside_a_comment_is_not_a_boundary(self):
        script = "-- a comment; with a semicolon\nCREATE TABLE a (x TEXT);\n"
        self.assertEqual(list(store.sql_statements(script)), [script.strip()])

    def test_refuses_an_unterminated_trailing_statement(self):
        with self.assertRaises(Refusal) as caught:
            list(store.sql_statements("CREATE TABLE a (x TEXT)\n"))
        self.assertIn("terminating semicolon", str(caught.exception))


class RowHelpers(Fresh):
    def setUp(self):
        super().setUp()
        self.st = self.open()
        self.st.migrate(self.migrations, canonical.now())

    def test_work_order_round_trips(self):
        self.st.insert_work_order("WO-001", "objective", "tdd", 1, "a" * 64, canonical.now())
        row = self.st.get_work_order("WO-001")
        self.assertEqual(row["kind"], "tdd")
        self.assertEqual(row["kind_version"], 1)
        self.assertEqual(len(self.st.list_work_orders()), 1)

    def test_events_are_keyed_by_work_order_and_seq(self):
        self.st.insert_work_order("WO-001", "o", "tdd", 1, "a" * 64, canonical.now())
        self.st.insert_event("WO-001", 1, "h1", canonical.ZERO_DIGEST, canonical.now(), "{}", "s1")
        self.assertEqual(self.st.chain_tail("WO-001")["seq"], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.st.insert_event("WO-001", 1, "h2", "h1", canonical.now(), "{}", "s2")

    def test_an_event_for_an_unknown_work_order_is_refused_by_the_schema(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.st.insert_event(
                "WO-404", 1, "h1", canonical.ZERO_DIGEST, canonical.now(), "{}", "s1"
            )

    def test_attempts_insert_with_partial_rows(self):
        self.st.insert_work_order("WO-001", "o", "tdd", 1, "a" * 64, canonical.now())
        self.st.insert_attempt(
            {
                "attempt_id": "WO-001#0001", "wo_id": "WO-001", "verb": "red",
                "agent": "test", "argv": '["x"]', "attempted_at": canonical.now(),
                "duration_ms": 3, "exit_code": 1, "record_kind": "refusal",
                "exhaustiveness": "first-failure", "reason": "nope",
                "event_appended": 0, "seq_before": 0, "seq_after": 0,
            }
        )
        rows = self.st.list_attempts("WO-001")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_kind"], "refusal")
        self.assertEqual(rows[0]["stderr_sha256"], "")
        self.assertEqual(self.st.count_attempts("WO-001"), 1)


if __name__ == "__main__":
    unittest.main()
