"""Durable live-session messages and measured events. No task gates."""

from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", value):
        raise ValueError("Use a member name of 1–64 letters, digits, underscores or hyphens.")
    return value


SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
 name TEXT PRIMARY KEY, harness TEXT NOT NULL, workspace TEXT NOT NULL,
 native_id TEXT, state TEXT NOT NULL DEFAULT 'stopped', desired TEXT NOT NULL DEFAULT 'stopped',
 pid INTEGER, generation TEXT, updated TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS messages (
 id INTEGER PRIMARY KEY, sender TEXT NOT NULL REFERENCES members(name),
 recipient TEXT NOT NULL REFERENCES members(name), body TEXT NOT NULL,
 reply_to INTEGER REFERENCES messages(id), request_key TEXT, created TEXT NOT NULL,
 delivery TEXT NOT NULL DEFAULT 'queued', attempt TEXT, submitted TEXT, acknowledged TEXT,
 error TEXT, UNIQUE(sender, request_key));
CREATE INDEX IF NOT EXISTS message_inbox ON messages(recipient,id);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL,
 kind TEXT NOT NULL, data TEXT NOT NULL);
"""


class Store:
    def __init__(self, directory):
        self.directory = Path(directory).expanduser().resolve()
        self.path = self.directory / "live.sqlite3"

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self, members):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)
            for member in members:
                name = identifier(member["name"])
                root = Path(member["workspace"]).expanduser().resolve(strict=True)
                if self.directory == root or self.directory.is_relative_to(root):
                    raise ValueError("Keep live state outside the managed source worktree.")
                old = db.execute("SELECT * FROM members WHERE name=?", (name,)).fetchone()
                if old and (old["harness"] != member["harness"] or old["workspace"] != str(root)):
                    raise ValueError(f"Member {name} already has a different harness or worktree.")
                db.execute(
                    "INSERT OR IGNORE INTO members(name,harness,workspace,updated) VALUES (?,?,?,?)",
                    (name, member["harness"], str(root), stamp()),
                )
        self.path.chmod(0o600)

    @staticmethod
    def _event(db, actor, kind, data):
        return db.execute(
            "INSERT INTO events(at,actor,kind,data) VALUES (?,?,?,?)", (stamp(), actor, kind, canonical(data))
        ).lastrowid

    def event(self, actor, kind, **data):
        with self.connect() as db:
            return self._event(db, actor, kind, data)

    def member(self, name):
        with self.connect() as db:
            row = db.execute("SELECT * FROM members WHERE name=?", (name,)).fetchone()
        if not row:
            raise ValueError(f"Unknown member: {name}")
        result = dict(row)
        result["detail"] = json.loads(result["detail"])
        return result

    def members(self):
        with self.connect() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM members ORDER BY name")]
        for row in rows:
            row["detail"] = json.loads(row["detail"])
        return rows

    def session(self, name, *, generation=None, **fields):
        allowed = {"native_id", "state", "desired", "pid", "detail"}
        if not fields or set(fields) - allowed:
            raise ValueError("Unknown session update")
        if "detail" in fields:
            fields["detail"] = canonical(fields["detail"])
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT generation FROM members WHERE name=?", (name,)).fetchone()
            if not row:
                raise ValueError("Unknown member")
            if generation is not None and row["generation"] != generation:
                raise ValueError("This session generation has been superseded.")
            fields["updated"] = stamp()
            db.execute(
                "UPDATE members SET " + ",".join(k + "=?" for k in fields) + " WHERE name=?", (*fields.values(), name)
            )
            self._event(db, name, "session", {k: v for k, v in fields.items() if k != "updated"})

    def begin_session(self, name, pid):
        generation = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM members WHERE name=?", (name,)).fetchone()
            if not row:
                raise ValueError("Unknown member")
            if row["state"] in {"starting", "active", "idle"} and row["pid"]:
                try:
                    import os

                    os.kill(row["pid"], 0)
                except ProcessLookupError:
                    pass
                else:
                    raise ValueError("This member already has a running session.")
            db.execute(
                "UPDATE members SET generation=?,pid=?,state='starting',desired='running',updated=? WHERE name=?",
                (generation, pid, stamp(), name),
            )
            # A crashed transport may have delivered before recording success. Preserve uncertainty.
            db.execute(
                "UPDATE messages SET delivery='uncertain',error='Transport stopped before recording delivery' "
                "WHERE recipient=? AND delivery='delivering'",
                (name,),
            )
            self._event(db, name, "session_starting", {"generation": generation, "pid": pid})
        return generation

    def send(self, sender, recipient, body, *, key, reply_to=None):
        self.member(sender)
        self.member(recipient)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM messages WHERE sender=? AND request_key=?", (sender, key)).fetchone()
            values = (recipient, body, reply_to)
            if old:
                if tuple(old[k] for k in ("recipient", "body", "reply_to")) != values:
                    raise ValueError("That message key already identifies a different payload.")
                return dict(old)
            if (
                reply_to
                and not db.execute(
                    "SELECT 1 FROM messages WHERE id=? AND (sender=? OR recipient=?)", (reply_to, sender, sender)
                ).fetchone()
            ):
                raise ValueError("Reply to a message involving this member.")
            ident = db.execute(
                "INSERT INTO messages(sender,recipient,body,reply_to,request_key,created) VALUES (?,?,?,?,?,?)",
                (sender, *values, key, stamp()),
            ).lastrowid
            self._event(db, sender, "message_queued", {"message": ident, "recipient": recipient})
            return dict(db.execute("SELECT * FROM messages WHERE id=?", (ident,)).fetchone())

    def inbox(self, member, after=0, limit=20, unacknowledged=False):
        with self.connect() as db:
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM messages WHERE recipient=? AND id>?"
                    + (" AND acknowledged IS NULL" if unacknowledged else "")
                    + " ORDER BY id LIMIT ?",
                    (member, after, limit + 1),
                )
            ]
        more = len(rows) > limit
        rows = rows[:limit]
        return {"messages": rows, "next_after": rows[-1]["id"] if more else None}

    def acknowledge(self, member, message):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM messages WHERE id=? AND recipient=?", (message, member)).fetchone()
            if not row:
                raise ValueError("Only the recipient can acknowledge this message.")
            if not row["acknowledged"]:
                db.execute("UPDATE messages SET acknowledged=? WHERE id=?", (stamp(), message))
                self._event(db, member, "message_acknowledged", {"message": message})
        return {"message": message, "acknowledged": True}

    def take_delivery(self, member):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM messages WHERE recipient=? AND delivery='queued' AND acknowledged IS NULL "
                "ORDER BY id LIMIT 1",
                (member,),
            ).fetchone()
            if not row:
                return None
            attempt = uuid.uuid4().hex
            db.execute("UPDATE messages SET delivery='delivering',attempt=? WHERE id=?", (attempt, row["id"]))
            result = dict(row)
            result["attempt"] = attempt
            return result

    def delivered(self, member, message, attempt, *, error=None, transport=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE messages SET delivery=?,submitted=?,error=? "
                "WHERE id=? AND recipient=? AND attempt=? AND delivery='delivering'",
                (
                    "uncertain" if error else "submitted",
                    stamp() if not error else None,
                    error,
                    message,
                    member,
                    attempt,
                ),
            ).rowcount
            if not changed:
                raise ValueError("Delivery attempt no longer current.")
            self._event(
                db,
                member,
                "delivery_uncertain" if error else "message_submitted",
                {"message": message, "transport": transport, "error": error},
            )

    def retry(self, member, message):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM messages WHERE id=? AND sender=?", (message, member)).fetchone()
            if not row or row["acknowledged"] or row["delivery"] != "uncertain":
                raise ValueError("Only the sender can explicitly retry an uncertain, unacknowledged delivery.")
            db.execute("UPDATE messages SET delivery='queued',attempt=NULL,error=NULL WHERE id=?", (message,))
            self._event(db, member, "message_retry", {"message": message})
        return {"message": message, "delivery": "queued"}

    def events(self, after=0, limit=30, actor=None, kind=None):
        sql, args = "SELECT * FROM events WHERE id>?", [after]
        for key, value in (("actor", actor), ("kind", kind)):
            if value:
                sql += f" AND {key}=?"
                args.append(value)
        with self.connect() as db:
            rows = [dict(r) for r in db.execute(sql + " ORDER BY id LIMIT ?", (*args, limit + 1))]
        for row in rows:
            row["data"] = json.loads(row["data"])
        return {"events": rows[:limit], "next_after": rows[limit - 1]["id"] if len(rows) > limit else None}

    def wait(self, member, after=0, timeout=20):
        deadline = time.monotonic() + timeout
        while True:
            result = self.inbox(member, after)
            if result["messages"] or time.monotonic() >= deadline:
                return result
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
