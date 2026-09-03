# test-guard: allow — the no-op and clobber below are the fixtures under test.
"""The harness, tested with the harness's own historical bugs.

A ``plant()`` that cannot detect a no-op is worth nothing, so it is fed a
no-op and a clobber here and must reject both.  Without this, every planted
fault in the suite rests on a helper whose name is the only evidence it
works — and a name is not a check.
"""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import support
from support import PlantFailed, plant_bytes, plant_sql

FIXTURE = b'{"seq":1,"hash":"aa"}\n{"seq":2,"hash":"bb"}\n'


def _substitute(raw, old, new):
    """A bare substitution — deliberately unguarded, because the guard being
    tested is ``plant_bytes`` itself."""
    return raw.replace(old, new)


class PlantBytesGuard(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="wf-plant-"))
        self.path = self.dir / "chain.jsonl"
        self.path.write_bytes(FIXTURE)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_rejects_a_no_op_substitution(self):
        # The historical bug: an in-place substitution whose anchor had moved.
        # Same bytes, exit 0, nothing said.
        with self.assertRaises(PlantFailed) as caught:
            plant_bytes(self.path, lambda raw: _substitute(raw, b"absent-anchor", b"z"))
        self.assertIn("changed nothing", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), FIXTURE, "fixture must be untouched")

    def test_rejects_a_clobber_to_empty(self):
        # The historical bug: a write that truncates before the read runs.
        with self.assertRaises(PlantFailed) as caught:
            plant_bytes(self.path, lambda raw: b"")
        self.assertIn("emptied", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), FIXTURE)

    def test_rejects_a_size_change_that_contradicts_the_claim(self):
        with self.assertRaises(PlantFailed) as caught:
            plant_bytes(self.path, lambda raw: raw + b'{"seq":3}\n', expect="edit")
        self.assertIn("in-place edit", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), FIXTURE)

    def test_rejects_an_unrecognisable_result(self):
        with self.assertRaises(PlantFailed) as caught:
            plant_bytes(
                self.path,
                lambda raw: raw.split(b"\n")[0] + b"\n",
                expect="shrink",
                recognisable=lambda raw: support.jsonl_lines(raw) == 2,
            )
        self.assertIn("unrecognisable", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), FIXTURE)

    def test_rejects_an_empty_fixture(self):
        self.path.write_bytes(b"")
        with self.assertRaises(PlantFailed) as caught:
            plant_bytes(self.path, lambda raw: b"x")
        self.assertIn("already empty", str(caught.exception))

    def test_accepts_a_real_in_place_edit_and_returns_the_clean_bytes(self):
        before = plant_bytes(self.path, lambda raw: _substitute(raw, b'"aa"', b'"zz"'))
        self.assertEqual(before, FIXTURE)
        landed = self.path.read_bytes()
        self.assertNotEqual(landed, FIXTURE)
        self.assertEqual(len(landed), len(FIXTURE))
        self.assertEqual(support.jsonl_lines(landed), 2)

    def test_accepts_a_declared_shrink(self):
        plant_bytes(
            self.path,
            lambda raw: raw.split(b"\n")[0] + b"\n",
            expect="shrink",
            recognisable=lambda raw: support.jsonl_lines(raw) == 1,
        )
        self.assertEqual(support.jsonl_lines(self.path.read_bytes()), 1)


class PlantSqlGuard(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="wf-plantsql-"))
        self.db = self.dir / "t.db"
        conn = sqlite3.connect(str(self.db))
        conn.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, payload TEXT)")
        conn.executemany("INSERT INTO events VALUES (?, ?)", [(1, "a"), (2, "b"), (3, "c")])
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _rows(self):
        conn = sqlite3.connect(str(self.db))
        try:
            return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        finally:
            conn.close()

    def test_rejects_an_update_that_matched_nothing(self):
        with self.assertRaises(PlantFailed) as caught:
            plant_sql(self.db, "UPDATE events SET payload='x' WHERE seq=99")
        self.assertIn("touched 0 rows", str(caught.exception))
        self.assertEqual(self._rows(), 3)

    def _payloads(self):
        conn = sqlite3.connect(str(self.db))
        try:
            return conn.execute("SELECT payload FROM events ORDER BY seq").fetchall()
        finally:
            conn.close()

    def test_rejects_an_update_that_matched_too_much_and_rolls_it_back(self):
        before = self._payloads()
        with self.assertRaises(PlantFailed) as caught:
            plant_sql(self.db, "UPDATE events SET payload='x'", expect_rows=1)
        self.assertIn("touched 3 rows", str(caught.exception))
        self.assertEqual(self._payloads(), before,
                         "a rejected plant must leave the fixture untouched")

    def test_rejects_an_update_that_changed_no_content(self):
        # rowcount counts rows the WHERE *matched*, not rows that changed:
        # SQLite reports a match for an assignment of the value already
        # stored. Only comparing content catches this no-op.
        before = self._payloads()
        with self.assertRaises(PlantFailed) as caught:
            plant_sql(self.db, "UPDATE events SET payload='b' WHERE seq=2")
        self.assertIn("changed no content", str(caught.exception))
        self.assertEqual(self._payloads(), before)

    def test_rejects_a_result_the_check_does_not_recognise_and_rolls_it_back(self):
        before = self._payloads()
        with self.assertRaises(PlantFailed) as caught:
            plant_sql(
                self.db,
                "DELETE FROM events WHERE seq=2",
                check=lambda c: c.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 3,
            )
        self.assertIn("unrecognisable", str(caught.exception))
        self.assertEqual(self._payloads(), before)

    def test_refuses_a_statement_whose_table_it_cannot_identify(self):
        with self.assertRaises(PlantFailed) as caught:
            plant_sql(self.db, "PRAGMA user_version = 3")
        self.assertIn("cannot tell which table", str(caught.exception))

    def test_accepts_a_landing_update(self):
        plant_sql(
            self.db,
            "UPDATE events SET payload='x' WHERE seq=2",
            check=lambda c: c.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 3,
        )
        conn = sqlite3.connect(str(self.db))
        try:
            self.assertEqual(
                conn.execute("SELECT payload FROM events WHERE seq=2").fetchone()[0], "x"
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
