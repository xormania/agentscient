#!/usr/bin/env python3
"""Declare and settle temporary permission for work done by hand."""

import argparse
import os
import re
import sqlite3
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

# The shared instrument module sits beside this file; its directory goes
# on the path so the import resolves however this file was loaded: as
# the script, by path from another tool, or as a copy a test staged
# with its siblings.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    import instrument
    from instrument import (
        Refusal,
        authority_home,
        emit,
        identity,
        lane_name,
        now,
        parse_stamp,
        refuse,
        session,
        stamp,
    )
except ModuleNotFoundError:
    print(
        "tooling: expected instrument.py beside this tool; found absent; "
        "needed restore ops/conductor/tools/instrument.py beside it",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

SCHEMA = """CREATE TABLE IF NOT EXISTS handwork(
    id INTEGER PRIMARY KEY, ts TEXT NOT NULL, session TEXT NOT NULL,
    agent TEXT NOT NULL, action TEXT NOT NULL, why_by_hand TEXT NOT NULL,
    missing_lever TEXT, evidence TEXT, lever_class TEXT, scope TEXT,
    ttl_s INTEGER, status TEXT DEFAULT 'settled', settled_ts TEXT,
    verified INTEGER, late INTEGER DEFAULT 0, settle_note TEXT)"""

LEVERS = {
    "dispatch": "ops/devlane/dispatch/launch.py",
    "collect": "ops/devlane/dispatch/launch.py",
    "gate-run": "ops/conductor/tools/gate.sh",
    "land": "ops/conductor/tools/land.py",
    "verify-record": None,
    "pr-open": None,
    "bulk-push": None,
    "amend": None,
    "worktree": None,
    "log-tooling": None,
    "wall": None,  # CI and test machinery work, in its own session (owner, 2026-09-12)
    "other": None,
}
HEX_OBJECT = re.compile(r"[0-9a-fA-F]{7,40}")
REMINDER = "declare-before-do is the temporary permission; settle it with evidence"
RECURRENCE = "a recurring absence is a lever demanding to be built."


def database_path():
    return (
        authority_home()
        / ".local/state"
        / lane_name()
        / "handwork.db"
    )


def connect():
    path = database_path()
    connection = instrument.connect_store(path, mode="rwc")
    connection.row_factory = sqlite3.Row
    connection.execute(SCHEMA)
    connection.commit()
    return connection


def validate_class(lever_class):
    if lever_class not in LEVERS:
        refuse(
            "class",
            "a known lever class",
            lever_class,
            "choose one of " + ", ".join(LEVERS),
        )


def declare(args):
    agent = identity()
    words = args.why.split()
    if len(words) < 4:
        refuse(
            "why-short",
            "WHY of at least four words",
            f"{len(words)} words",
            "state why this work cannot wait for a lever",
        )
    validate_class(args.lever_class)
    probe = LEVERS[args.lever_class]
    if probe is not None and Path(probe).exists():
        refuse(
            "lever-exists",
            "a missing lever",
            f"built probe {probe}",
            f"use the {args.lever_class} lever",
        )

    with connect() as connection:
        cursor = connection.execute(
            """INSERT INTO handwork
               (ts, session, agent, action, why_by_hand, missing_lever,
                lever_class, scope, ttl_s, status, late)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', 0)""",
            (
                stamp(now()),
                session(),
                agent,
                args.action,
                args.why,
                args.lever_class,
                args.lever_class,
                args.scope,
                args.ttl * 60,
            ),
        )
        grant_id = cursor.lastrowid
        count = connection.execute(
            """SELECT count(*) FROM handwork
               WHERE lever_class = ? AND status IN ('open', 'settled')""",
            (args.lever_class,),
        ).fetchone()[0]
    print(f"grant {grant_id}: {REMINDER}")
    if probe is None and count >= 3:
        print(RECURRENCE)


def verify_evidence(evidence):
    if HEX_OBJECT.fullmatch(evidence):
        result = subprocess.run(  # noqa: S603
            ["git", "cat-file", "-e", evidence],  # noqa: S607
            cwd=Path.cwd(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0, "git object"

    path = Path(evidence).expanduser()
    dispatch = Path.home() / ".local/state/agentscient/dispatch"
    if path.is_dir():
        try:
            path.resolve().relative_to(dispatch.resolve())
        except ValueError:
            pass
        else:
            return True, "dispatch record"
    if path.is_file():
        return True, "file"
    return False, "claimed evidence"


def settle(args):
    identity()
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM handwork WHERE id = ?", (args.id,)
        ).fetchone()
        if row is None:
            refuse(
                "unknown",
                "an id in the store",
                str(args.id),
                "choose an id shown by open",
            )
        if row["status"] != "open":
            refuse(
                "resettle",
                "an open grant",
                f"status {row['status']}",
                "settle each grant only once",
            )
        verified, shape = verify_evidence(args.evidence)
        settled = now()
        deadline = parse_stamp(row["ts"]) + timedelta(seconds=row["ttl_s"])
        late = settled > deadline
        connection.execute(
            """UPDATE handwork SET evidence = ?, status = 'settled',
               settled_ts = ?, verified = ?, late = ?, settle_note = ?
               WHERE id = ?""",
            (
                args.evidence,
                stamp(settled),
                int(verified),
                int(late),
                args.note,
                args.id,
            ),
        )
    state = "verified" if verified else "claimed; unverified"
    timing = "; late" if late else ""
    print(f"settled {args.id}: {state} ({shape}){timing}")


def open_grants(_args):
    current = now()
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM handwork WHERE status = 'open' ORDER BY ts, id"
        ).fetchall()
    if not rows:
        print("no open grants")
        return
    for row in rows:
        age = max(0, int((current - parse_stamp(row["ts"])).total_seconds()))
        state = "late" if age > row["ttl_s"] else "within ttl"
        print(
            f"{row['id']} {row['lever_class']} {row['action']} "
            f"age={age}s ttl={row['ttl_s']}s {state}"
        )


def report(_args):
    with connect() as connection:
        statuses = connection.execute(
            "SELECT status, count(*) AS n FROM handwork GROUP BY status ORDER BY status"
        ).fetchall()
        open_rows = connection.execute(
            "SELECT * FROM handwork WHERE status = 'open' ORDER BY ts, id"
        ).fetchall()
        classes = connection.execute(
            """SELECT lever_class, count(*) AS n FROM handwork
               GROUP BY lever_class ORDER BY lever_class"""
        ).fetchall()
        levers = connection.execute(
            """SELECT missing_lever, count(*) AS n FROM handwork
               GROUP BY missing_lever ORDER BY missing_lever"""
        ).fetchall()
        debt = connection.execute(
            """SELECT
               sum(CASE WHEN status = 'open' THEN 1 ELSE 0 END),
               sum(CASE WHEN status = 'settled' AND coalesce(verified, 0) = 0
                        THEN 1 ELSE 0 END),
               sum(CASE WHEN status = 'settled' AND late = 1 THEN 1 ELSE 0 END)
               FROM handwork"""
        ).fetchone()
    print("status: " + ", ".join(f"{row['status']}={row['n']}" for row in statuses))
    print("open grants:")
    for row in open_rows:
        print(f"  {row['id']} {row['lever_class']} {row['action']}")
    print("recurrence by class:")
    for row in classes:
        print(f"  {row['lever_class'] or 'unclassified'}={row['n']}")
    print("recurrence by missing lever:")
    for row in levers:
        print(f"  {row['missing_lever'] or 'unnamed'}={row['n']}")
    print(
        f"debt: open={debt[0] or 0}, settled-unverified={debt[1] or 0}, "
        f"settled-late={debt[2] or 0}"
    )


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="verb", required=True)

    declare_parser = commands.add_parser("declare")
    declare_parser.add_argument("action")
    declare_parser.add_argument("why")
    declare_parser.add_argument("lever_class")
    declare_parser.add_argument("--scope")
    declare_parser.add_argument("--ttl", type=int, default=30, metavar="MIN")
    declare_parser.set_defaults(run=declare)

    settle_parser = commands.add_parser("settle")
    settle_parser.add_argument("id", type=int)
    settle_parser.add_argument("--evidence", required=True)
    settle_parser.add_argument("--note")
    settle_parser.set_defaults(run=settle)

    open_parser = commands.add_parser("open")
    open_parser.set_defaults(run=open_grants)
    report_parser = commands.add_parser("report")
    report_parser.set_defaults(run=report)
    return result


def main():
    args = parser().parse_args()
    try:
        args.run(args)
    except Refusal as error:
        return emit(error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
