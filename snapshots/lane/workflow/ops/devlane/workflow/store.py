"""sqlite3 access and forward-only migrations.

The database is a cache with a rebuild command behind it (PLAN §8, D1): the
tracked export is the evidence, ``wf.db`` is gitignored and reconstructed by
``wf init --rebuild``.  Nothing here decides anything; it stores and reads.

Migration discipline (PLAN §6) is loopflow's, unchanged: numbered forward-only
SQL applied inside a transaction and recorded with the digest of the file that
was applied.  A file that changes after it has been applied is an integrity
failure, not a new migration — the record would otherwise describe a schema
nobody ever ran.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import canonical
from errors import Integrity, Refusal

MIGRATION_NAME = re.compile(r"^(\d{4})_([A-Za-z0-9_\-]+)\.sql$")


def sql_statements(script: str):
    """Split a migration into statements.

    ``executescript`` is not usable here: it implicitly commits any pending
    transaction before it runs, which would apply the DDL outside the
    transaction that records it — leaving a schema nobody has a row for if
    the insert then failed.  ``sqlite3.complete_statement`` is SQLite's own
    splitter and understands string literals and comments.
    """
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if buffer.strip() and sqlite3.complete_statement(buffer):
            yield buffer.strip()
            buffer = ""
    if buffer.strip():
        raise Refusal(
            "the migration ends with a complete statement",
            actual=buffer.strip()[:60],
            needed="a terminating semicolon",
        )


def migration_files(migrations_dir: Path):
    """Numbered migrations in apply order, refusing an ambiguous set."""
    found = {}
    for path in sorted(Path(migrations_dir).iterdir()):
        if path.name.startswith("."):
            continue
        match = MIGRATION_NAME.match(path.name)
        if not match:
            raise Refusal(
                "every file in migrations/ is a numbered migration",
                actual=path.name,
                needed="NNNN_name.sql",
            )
        version = int(match.group(1))
        if version in found:
            raise Refusal(
                "migration versions are unique",
                actual=f"{found[version].name} and {path.name}",
                needed="one file per version",
            )
        found[version] = path
    return [(version, found[version]) for version in sorted(found)]


class Store:
    """An open control-plane database."""

    def __init__(self, db_path: Path, read_only: bool = False):
        self.path = Path(db_path)
        self.read_only = read_only
        if read_only:
            # A reader must not be able to create the file it is reading.
            # sqlite3.connect() creates on open, so a missing cache became an
            # empty database and every query then failed on a missing table.
            # as_uri() percent-encodes. Interpolating the path made SQLite
            # parse a '?' or '#' inside it as URI syntax: a checkout under
            # `a?b/` opened `a` instead — creating a writable zero-byte file
            # and reporting the real database as schema-less, so the mode
            # added to stop a read creating state was creating it.
            self.conn = sqlite3.connect(
                f"{self.path.resolve().as_uri()}?mode=ro",
                uri=True, isolation_level=None)
            self.conn.row_factory = sqlite3.Row
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        # Contended claims mean concurrent writers; without this a second
        # process raises "database is locked" instead of waiting its turn,
        # which would surface as an internal error rather than a refusal.
        self.conn.execute("PRAGMA busy_timeout = 10000")

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # -- transactions ------------------------------------------------------

    def begin(self):
        self.conn.execute("BEGIN IMMEDIATE")

    def commit(self):
        self.conn.execute("COMMIT")

    def rollback(self):
        self.conn.execute("ROLLBACK")

    def q(self, sql, params=()):
        return self.conn.execute(sql, params)

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def all(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    # -- migrations --------------------------------------------------------

    def applied_migrations(self) -> dict:
        row = self.one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        )
        if row is None:
            return {}
        return {
            r["version"]: (r["name"], r["sha256"])
            for r in self.all("SELECT version, name, sha256 FROM schema_migrations")
        }

    def migrate(self, migrations_dir: Path, now: str) -> list:
        """Apply pending migrations. Idempotent: a second call applies none."""
        applied = self.applied_migrations()
        pending = []
        for version, path in migration_files(migrations_dir):
            body = path.read_bytes()
            sha = canonical.sha256_hex(body)
            if version in applied:
                recorded_name, recorded_sha = applied[version]
                if recorded_sha != sha:
                    raise Integrity(
                        "an applied migration file has changed since it was applied",
                        detail=f"{path.name}: recorded {recorded_sha[:12]}, file {sha[:12]}",
                    )
                if recorded_name != path.name:
                    raise Integrity(
                        "an applied migration has been renamed",
                        detail=f"recorded {recorded_name}, file {path.name}",
                    )
                continue
            pending.append((version, path, body.decode("utf-8"), sha))

        for version, path, sql, sha in pending:
            self.begin()
            try:
                for statement in sql_statements(sql):
                    self.conn.execute(statement)
                self.conn.execute(
                    "INSERT INTO schema_migrations (version, name, sha256, applied_at)"
                    " VALUES (?, ?, ?, ?)",
                    (version, path.name, sha, now),
                )
                self.commit()
            except Exception:
                self.rollback()
                raise
        return [path.name for _, path, _, _ in pending]

    # -- work orders -------------------------------------------------------

    def get_work_order(self, wo_id):
        return self.one("SELECT * FROM work_orders WHERE wo_id = ?", (wo_id,))

    def list_work_orders(self):
        return self.all("SELECT * FROM work_orders ORDER BY wo_id")

    def insert_work_order(self, wo_id, objective, kind, kind_version, spec_sha256, created_at):
        self.q(
            "INSERT INTO work_orders (wo_id, objective, kind, kind_version, spec_sha256,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (wo_id, objective, kind, kind_version, spec_sha256, created_at),
        )

    # -- events ------------------------------------------------------------

    def chain_tail(self, wo_id):
        return self.one(
            "SELECT * FROM events WHERE wo_id = ? ORDER BY seq DESC LIMIT 1", (wo_id,)
        )

    def list_events(self, wo_id):
        return self.all("SELECT * FROM events WHERE wo_id = ? ORDER BY seq", (wo_id,))

    def get_event(self, wo_id, seq):
        return self.one("SELECT * FROM events WHERE wo_id = ? AND seq = ?", (wo_id, seq))

    def insert_event(self, wo_id, seq, hash_, prev, time, payload, state_sha256):
        self.q(
            "INSERT INTO events (wo_id, seq, hash, prev, time, payload, state_sha256)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (wo_id, seq, hash_, prev, time, payload, state_sha256),
        )

    # -- projection --------------------------------------------------------

    def get_state(self, wo_id):
        return self.one("SELECT * FROM wo_state WHERE wo_id = ?", (wo_id,))

    def upsert_state(self, wo_id, state_json, state_sha256, last_seq, last_hash):
        self.q(
            "INSERT INTO wo_state (wo_id, state_json, state_sha256, last_seq, last_hash)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(wo_id) DO UPDATE SET state_json=excluded.state_json,"
            " state_sha256=excluded.state_sha256, last_seq=excluded.last_seq,"
            " last_hash=excluded.last_hash",
            (wo_id, state_json, state_sha256, last_seq, last_hash),
        )

    # -- gate kinds --------------------------------------------------------

    def get_gate_kind(self, kind, version):
        return self.one(
            "SELECT * FROM gate_kinds WHERE kind = ? AND version = ?", (kind, version)
        )

    def list_gate_kinds(self):
        return self.all("SELECT * FROM gate_kinds ORDER BY kind, version")

    def upsert_gate_kind(self, kind, version, spec_json, spec_sha256, synced_at):
        self.q(
            "INSERT INTO gate_kinds (kind, version, spec_json, spec_sha256, synced_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(kind, version) DO UPDATE SET spec_json=excluded.spec_json,"
            " spec_sha256=excluded.spec_sha256, synced_at=excluded.synced_at",
            (kind, version, spec_json, spec_sha256, synced_at),
        )

    # -- artifacts ---------------------------------------------------------

    def get_artifact(self, digest):
        return self.one("SELECT * FROM artifacts WHERE digest = ?", (digest,))

    def list_artifacts(self):
        return self.all("SELECT * FROM artifacts ORDER BY digest")

    def upsert_artifact(self, digest, size, media_type, class_, created_at):
        self.q(
            "INSERT INTO artifacts (digest, size, media_type, class, created_at)"
            " VALUES (?, ?, ?, ?, ?) ON CONFLICT(digest) DO NOTHING",
            (digest, size, media_type, class_, created_at),
        )

    # -- attempts ----------------------------------------------------------

    def count_attempts(self, wo_id) -> int:
        return self.one("SELECT COUNT(*) AS n FROM attempts WHERE wo_id = ?", (wo_id,))["n"]

    def list_attempts(self, wo_id):
        return self.all(
            "SELECT * FROM attempts WHERE wo_id = ? ORDER BY attempt_id", (wo_id,)
        )

    def insert_attempt(self, row: dict):
        columns = [
            "attempt_id", "wo_id", "verb", "agent", "argv", "attempted_at",
            "duration_ms", "exit_code", "record_kind", "exhaustiveness", "reason",
            "event_appended", "seq_before", "seq_after", "head_before", "head_after",
            "stage_before", "stage_after", "stdout_tail", "stderr_tail",
            "stdout_sha256", "stderr_sha256",
        ]
        placeholders = ", ".join("?" for _ in columns)
        self.q(
            f"INSERT INTO attempts ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(row.get(c, "" if c not in
                  ("duration_ms", "exit_code", "event_appended", "seq_before", "seq_after")
                  else 0) for c in columns),
        )
