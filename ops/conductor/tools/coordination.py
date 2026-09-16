#!/usr/bin/env python3
"""The coordination core: participants, assignments, messages, evidence.

Contract: ops/conductor/coordination-lever.md. Inherits
ops/conductor/instrument-conventions.md (the refusal wire, the four exit
classes, identity for writes) and runs on the state engine (machine.py):
every row lives in state.db, never in a file.

The defect this module exists to close: the engine's holder is the agent
string (machine.py compares row["holder"] == agent), and one host binds
one WF_AGENT for every session on it, so three sessions of the same
model satisfy each other's holder checks. Here the participant, keyed on
the harness session id, is the authority; the agent string is
attribution only. Authority is checked inside these functions, never in
a hook: the hook engine cannot see MCP tool calls, so a check that lived
there would not run when the MCP projection calls the same function.

    coordination.py bind --roles R[,R] [--harness H] [--endpoint E] [--probe TEXT]
    coordination.py bind-for --session ID --roles R[,R] --for A-n [--harness H]
    coordination.py grant PT-n --roles R[,R]
    coordination.py revoke PT-n --roles R[,R]
    coordination.py who | participants [--role R]
    coordination.py draft TITLE --outcome TEXT [--requirement REF] [--revision SHA]
                              [--depends A-n,..] [--duty TEXT] [--scope TEXT] [--inputs REF]
    coordination.py offer A-n --to WHO --generation N
    coordination.py claim A-n --branch B --generation N [--ttl MIN]
    coordination.py release A-n --why TEXT --generation N
    coordination.py reassign A-n --to WHO --why TEXT --generation N
    coordination.py submit A-n --evidence READING --revision SHA --generation N
    coordination.py verify A-n --candidate SHA --evidence READING --generation N
    coordination.py return A-n --findings REF --generation N
    coordination.py accept A-n --evidence READING --generation N
    coordination.py reopen A-n --revision SHA --why TEXT --generation N
    coordination.py supersede A-n --by A-m --generation N
    coordination.py assignments [--state S] [--to WHO] [--mine] | show A-n|M-n
    coordination.py send --to WHO --purpose P --body TEXT [--assignment A-n]
                         [--decision DC-n] [--reply-to M-n] [--artifact REF]
    coordination.py deliver M-n --ref REF | ack M-n | resolve M-n --evidence READING
    coordination.py withdraw M-n --why TEXT | inbox [--unresolved] | outstanding [--to WHO]
    coordination.py undelivered [--to WHO]
    coordination.py observe A-n --observation TEXT --revision SHA --generation N
                            [--stale] [--execution REC] [--artifact REF]
                            [--requirement REF] [--environment TEXT]
    coordination.py observations A-n [--all]
    coordination.py ask --question TEXT --alternatives TEXT [--assignment A-n]
    coordination.py answer DC-n [--counter TEXT] [--unknowns TEXT] [--consequence TEXT]
    coordination.py decide DC-n --choice TEXT --rationale TEXT
    coordination.py decision DC-n | decisions [--open]
    coordination.py reserve NAME --for A-n [--ttl MIN] | free NAME --why TEXT | resources
    coordination.py coverage [--requirement REF] | brief

Reads need no identity and no participant and never create the store.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys

# The shared instrument module sits beside this file; its directory goes
# on the path so the import resolves however this file was loaded: as
# the script, by path from another tool, or as a copy a test staged
# with its siblings.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    import machine
    from instrument import (
        EXIT_DONE,
        Refusal,
        emit,
        identity,
        refuse,
        session,
        stamp,
        state_dir,
    )
except ModuleNotFoundError:
    print(
        "tooling: expected instrument.py and machine.py beside this tool; found absent; "
        "needed restore ops/conductor/tools/instrument.py and machine.py beside it",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

LOCK = "deliverable.json"
ROLES = ("lead", "coordinator", "dispatcher", "worker", "verifier")
PURPOSES = ("inform", "request", "finding")
OBLIGATIONS = ("request", "finding")
ID = re.compile(r"^(PT|DC|A|M|E|R)-(\d+)$")
READING = re.compile(
    r"^(?:[0-9a-f]{7,40}|#\d+|\d{8}T\d{6}Z-[\w-]+|P-[\w-]+)$", re.IGNORECASE
)

T = machine.Transition
ASSIGNMENT = machine.Machine(
    name="assignment",
    version=1,
    initial="drafted",
    places=("drafted", "offered", "held", "submitted", "verified", "accepted", "superseded"),
    transitions=(
        T("offer", "drafted", "offered", "any", "none", "offered", "keep"),
        T("claim", "offered", "held", "any", "none", "taken", "take"),
        T("release", "held", "offered", "holder-or-lapsed", "required", "place", "clear"),
        T("reassign", "held", "offered", "any", "required", "place", "clear"),
        T("submit", "held", "submitted", "any", "required", "place", "keep"),
        T("verify", "submitted", "verified", "any", "required", "place", "keep"),
        T("return", "submitted", "held", "any", "required", "place", "keep"),
        T("accept", "verified", "accepted", "any", "required", "place", "keep"),
        T("reopen", "verified", "held", "any", "required", "place", "keep"),
        T("supersede", "offered", "superseded", "any", "required", "place", "keep"),
    ),
    ttl_s=8 * 3600,
)
MESSAGE = machine.Machine(
    name="message",
    version=1,
    initial="open",
    places=("open", "resolved", "withdrawn"),
    transitions=(
        T("resolve", "open", "resolved", "any", "required", "place", "keep"),
        T("withdraw", "open", "withdrawn", "any", "required", "place", "keep"),
    ),
    ttl_s=8 * 3600,
)
RESOURCE = machine.Machine(
    name="resource",
    version=1,
    initial="free",
    places=("free", "held"),
    transitions=(
        T("reserve", "free", "held", "any", "none", "taken", "take"),
        T("free", "held", "free", "holder-or-lapsed", "required", "place", "clear"),
    ),
    ttl_s=2 * 3600,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS participants(
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL UNIQUE,
    agent TEXT NOT NULL, harness TEXT, roles TEXT NOT NULL, endpoint TEXT,
    probe TEXT, bound_at TEXT NOT NULL, bound_by INTEGER, bound_for INTEGER,
    granted_by INTEGER, granted_at TEXT, revoked_by INTEGER, revoked_at TEXT);
CREATE TABLE IF NOT EXISTS assignments(
    id INTEGER PRIMARY KEY, title TEXT NOT NULL, outcome TEXT NOT NULL,
    requirement TEXT, scope TEXT, inputs TEXT, recipient TEXT, depends TEXT,
    revision TEXT, generation INTEGER NOT NULL, duty TEXT, thread INTEGER,
    branch TEXT, holder INTEGER, submitted_by INTEGER, verified_by INTEGER,
    accepted_by INTEGER, opened_by INTEGER NOT NULL, opened_at TEXT NOT NULL,
    superseded_by INTEGER);
CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY, sender INTEGER NOT NULL, recipient TEXT NOT NULL,
    purpose TEXT NOT NULL, body TEXT NOT NULL, artifact TEXT, assignment INTEGER,
    decision INTEGER, reply_to INTEGER, queued_at TEXT NOT NULL,
    delivered_at TEXT, delivery_ref TEXT, acked_at TEXT, acked_by INTEGER);
CREATE TABLE IF NOT EXISTS observations(
    id INTEGER PRIMARY KEY AUTOINCREMENT, assignment INTEGER NOT NULL,
    producer INTEGER NOT NULL, requirement TEXT, execution TEXT,
    revision TEXT NOT NULL, environment TEXT, observation TEXT NOT NULL,
    artifact TEXT, applicability TEXT NOT NULL, stale_reason TEXT,
    at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions(
    id INTEGER PRIMARY KEY AUTOINCREMENT, asked_by INTEGER NOT NULL,
    question TEXT NOT NULL, alternatives TEXT NOT NULL, assignment INTEGER,
    counter TEXT, unknowns TEXT, consequence TEXT, choice TEXT, rationale TEXT,
    decided_by INTEGER, decided_at TEXT, asked_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS resources(
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, assignment INTEGER,
    holder INTEGER, note TEXT);
"""


# -- arguments ---------------------------------------------------------------

def parse(rest, count, *, required=(), optional=(), flags=()):
    """Positionals and --options; anything else refuses `arguments`.

    The acting participant is never among them: it is resolved from the
    session, so a supplied one falls through to the unknown-option
    refusal and confers nothing (objective §7).
    """
    positionals, options = [], {}
    tokens = list(rest)
    while tokens:
        token = tokens.pop(0)
        if token.startswith("--"):
            name = token[2:]
            if name in flags:
                options[name] = True
                continue
            if name not in required and name not in optional:
                refuse("arguments", "a known option", token, usage())
            if not tokens:
                refuse("arguments", f"a value after --{name}", "end of arguments", usage())
            options[name] = tokens.pop(0)
        else:
            positionals.append(token)
    if len(positionals) != count:
        refuse("arguments", f"{count} positional argument(s)", str(len(positionals)), usage())
    for name in required:
        if name not in options:
            refuse("arguments", f"--{name}", "absent", usage())
    return positionals, options


def usage() -> str:
    return "see the verbs in the module doc of coordination.py"


def parse_id(text: str, kinds=("PT", "A", "M", "E", "DC", "R")) -> tuple[str, int]:
    match = ID.match(text)
    kinds = (kinds,) if isinstance(kinds, str) else tuple(kinds)
    if match is None or match.group(1) not in kinds:
        wanted = " or ".join(f"{k}-1" for k in kinds)
        refuse("id", f"an id like {wanted}", text, "an id printed by a listing verb")
    return match.group(1), int(match.group(2))


def reading(value: str, what: str) -> str:
    if READING.match(value) is None:
        refuse("evidence", f"{what} as a sha, #N, a dispatch record id or a P- row",
               value, "name the reading the move rests on")
    return value


def roles_of(text: str) -> str:
    named = [part.strip() for part in text.split(",") if part.strip()]
    if not named:
        refuse("arguments", "at least one role", text or "empty", "one of " + ", ".join(ROLES))
    for role in named:
        if role not in ROLES:
            refuse("arguments", "a known role", role, "one of " + ", ".join(ROLES))
    return ",".join(named)


# -- the store ---------------------------------------------------------------

def ensure_columns(conn) -> None:
    """A store written before the dispatched-worker binding or the grant
    chain existed gains their columns here; ALTER ... ADD COLUMN is
    idempotent under the guard and costs one PRAGMA on every open."""
    have = {row["name"] for row in conn.execute("PRAGMA table_info(participants)")}
    for name, kind in (("bound_by", "INTEGER"), ("bound_for", "INTEGER"),
                       ("granted_by", "INTEGER"), ("granted_at", "TEXT"),
                       ("revoked_by", "INTEGER"), ("revoked_at", "TEXT")):
        if name not in have:
            conn.execute(f"ALTER TABLE participants ADD COLUMN {name} {kind}")


def writer():
    conn = machine.connect(create=True)
    conn.executescript(SCHEMA)
    ensure_columns(conn)
    for declared in (ASSIGNMENT, MESSAGE, RESOURCE):
        machine.declare(conn, declared)
    return conn


STORE_TABLES = tuple(sorted(set(
    re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", SCHEMA)
    + re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", machine.SCHEMA))))


def reader():
    """The store for a read, or None when there is nothing to read.

    Read-only by the connection itself, and migrating nothing. It used to
    connect read-write, run `executescript(SCHEMA)` and then
    `ensure_columns`, so every read of this instrument created tables and
    added columns on the way past — an unidentified writer of exactly the
    reach of a read, because reads need no identity (codex-beb7b6#3,
    grok-7bbe10#2). A store this module cannot read is a refusal, class
    `state`, and never a store built to order: "could not look" is a
    marker, not an empty answer (docs/wire.md, absence discipline).
    """
    path = machine.store_path()
    if not path.is_file():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True,
                           timeout=machine.BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {machine.BUSY_TIMEOUT_MS}")
    # `sqlite_schema` is the name SQLite 3.33 gave the table it has always
    # had; the older name carries a word the lane's literals verb forbids
    # in code, and this is the same table under the name that does not.
    held = {row["name"] for row in
            conn.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")}
    missing = [name for name in STORE_TABLES if name not in held]
    if missing:
        conn.close()
        refuse("state", f"the coordination schema in the store at {path}",
               "a store with no tables at all" if not held
               else f"a store without {', '.join(missing)}",
               "a writing verb creates the schema and migrates it; "
               "a read does neither")
    return conn


# -- participants ------------------------------------------------------------

def bound_participant(conn):
    """The participant acting on this command, from the session id alone."""
    key = session("")
    if not key:
        refuse("session", "a session id in the environment", "unset",
               "run under a harness that sets CLAUDE_CODE_SESSION_ID, then bind")
    row = None
    if conn is not None:
        row = conn.execute(
            "SELECT * FROM participants WHERE session_id = ?", (key,)
        ).fetchone()
    if row is None:
        refuse("participant", "a participant bound to this session", key,
               "bind --roles ROLE[,ROLE] first")
    return row


def same_session(conn, part):
    """The row a caller passes is an id, and everything else is read.

    The first repair compared the passed mapping's own `session_id`
    against the environment and read nothing else, which moved the
    boundary rather than closing it: a mapping carrying this session's id
    beside another participant's id and roles passed, and the function
    then acted on the roles it had been handed (Codex 834580#2, Daybreak
    1833de#3 against b1d868b0). So the id is all a caller supplies. The
    row is loaded from `participants` by that id, its `session_id` must
    be this process's, and the row this returns — never the argument — is
    what the function reads from there on.

    The argument shape stays, because passing the resolved row is what
    keeps the CLI and the MCP server thin. What it carries is a claim
    about which participant is acting, and the store answers it.

    `None` is the two declared cases and not a caller's choice: bind has
    no row yet, and a read with no store has nothing to resolve from.
    """
    if part is None:
        return None
    key = session("")
    row = None
    if conn is not None:
        row = conn.execute(
            "SELECT * FROM participants WHERE id = ?", (part["id"],)
        ).fetchone()
    if row is None or row["session_id"] != key:
        stood = (f"PT-{part['id']}, bound to session {row['session_id']}"
                 if row is not None else
                 f"PT-{part['id']}, which the store does not hold")
        refuse("participant", f"the participant bound to session {key or 'unset'}",
               stood,
               "act as the participant this process is bound to; "
               "the caller does not choose it")
    return row


def actor(part) -> str:
    """What the engine is told the mover is.

    `subjects.holder` is an opaque string the engine compares for
    equality and nothing else, so what it carries is each machine's own
    decision (`machine.py:253-264`, idea I-034). These machines carry
    the participant: the agent string is one value per host, so a holder
    that changed it was refused and a stranger that shared it was not
    (Grok #4 against 05b8aebe). The marking's attribution column takes
    the same value; the agent string behind it is on the participant's
    own row, recorded at bind.
    """
    return f"PT-{part['id']}"


def require_role(part, roles) -> None:
    held = {role for role in part["roles"].split(",") if role}
    if held & set(roles):
        return
    refuse("role", "a participant holding " + " or ".join(roles),
           f"PT-{part['id']} holding {part['roles']}",
           "bind that role, or hand the verb to a participant that holds it")


def participant_row(conn, pid: int):
    row = conn.execute("SELECT * FROM participants WHERE id = ?", (pid,)).fetchone()
    if row is None:
        refuse("participant", "a participant id in the store", f"PT-{pid}",
               "an id printed by participants")
    return row


def recipient_of(conn, text: str) -> str:
    """A participant id or a role name; anything else refuses."""
    if text in ROLES:
        return text
    _, number = parse_id(text, "PT")
    participant_row(conn, number)
    return f"PT-{number}"


def addressed(part, recipient: str) -> bool:
    if recipient == f"PT-{part['id']}":
        return True
    return recipient in {role for role in part["roles"].split(",") if role}


# -- rows --------------------------------------------------------------------

def assignment_row(conn, aid: int):
    row = None
    if conn is not None:
        row = conn.execute(
            "SELECT a.*, s.place, s.holder AS agent_holder, s.held_since, s.ttl_s "
            "FROM assignments a JOIN subjects s ON s.id = a.id WHERE a.id = ?", (aid,)
        ).fetchone()
    if row is None:
        refuse("unknown", "an assignment id in the store", f"A-{aid}",
               "an id printed by assignments")
    return row


def message_row(conn, mid: int):
    row = None
    if conn is not None:
        row = conn.execute(
            "SELECT m.*, s.place FROM messages m JOIN subjects s ON s.id = m.id "
            "WHERE m.id = ?", (mid,)
        ).fetchone()
    if row is None:
        refuse("unknown", "a message id in the store", f"M-{mid}",
               "an id printed by inbox")
    return row


def decision_row(conn, did: int):
    row = None
    if conn is not None:
        row = conn.execute("SELECT * FROM decisions WHERE id = ?", (did,)).fetchone()
    if row is None:
        refuse("unknown", "a decision id in the store", f"DC-{did}",
               "an id printed by decisions")
    return row


def advance(conn, aid: int, transition: str, part, *, evidence=None, note=None,
            ttl_s=None, gate=None):
    """Every move on an assignment bumps its generation, inside the move.

    The generation is what refuses a caller acting on a view the
    assignment has moved past, and it only does that if every move moves
    it. Grok reproduced the hole against b1d868b0: `return` and `submit`
    both left it where it was, so a verifier that began a return against
    one submission had it land on the next one. The Daybreak audit found
    the same shape in `supersede`, which stated no generation at all.
    Ruled by the Lead, 2026-09-16: one bump a move, so a delayed verb
    refuses on the gate it already has.

    The bump runs last inside the caller's own gate, so it is in the
    engine's `BEGIN IMMEDIATE` with the rest of the move and a refusal
    from the gate rolls it back with everything else.
    """

    def bump(subject):
        if gate is not None:
            gate(subject)
        conn.execute(
            "UPDATE assignments SET generation = generation + 1 WHERE id = ?", (aid,)
        )

    return machine.move(conn, ASSIGNMENT, aid, transition, actor(part),
                        evidence=evidence, note=note, ttl_s=ttl_s, gate=bump)


def require_generation(row, stated: str) -> int:
    """The stated generation against the row's, before the engine sees the
    place: a reassignment returns the subject to a place it held before,
    so the place alone cannot refuse a stale holder (AC-03)."""
    if not stated.isdigit():
        refuse("arguments", "--generation as a whole number", stated,
               "the generation printed by show")
    if int(stated) != row["generation"]:
        refuse("generation", f"generation {row['generation']} for A-{row['id']}",
               f"generation {stated}", "read show for the current generation; "
               "the assignment moved on without this holder")
    return int(stated)


def require_holder(part, row) -> None:
    if row["holder"] != part["id"]:
        refuse("holder", f"the holder PT-{row['holder']} of A-{row['id']}",
               f"PT-{part['id']}", "the holder moves it, or it is reassigned first")


def not_the_producer(part, row, what: str) -> None:
    """AC-11: an independent pass is not a role label away."""
    if row["submitted_by"] is not None and row["submitted_by"] == part["id"]:
        refuse("producer", f"a participant other than the producer PT-{row['submitted_by']}",
               f"PT-{part['id']}, which submitted A-{row['id']}",
               f"another participant {what} this candidate")


def lock_branches():
    path = state_dir() / LOCK
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    branches = data.get("branches") if isinstance(data, dict) else None
    return [str(b) for b in branches] if isinstance(branches, list) else None


def require_lock(branch: str) -> None:
    """A claim nobody can find on the board is not a claim
    (handoff-lever.md, the same rule the thread take carries)."""
    named = lock_branches()
    if named is None:
        refuse("deliverable", "the deliverable lock naming the branch", "no lock on this host",
               f"deliverable.py add {branch} --why '<the words>'")
    if branch not in named:
        refuse("deliverable", "a branch the deliverable lock names", branch,
               f"deliverable.py add {branch} --why '<the words>'; the lock holds "
               + ", ".join(named or ["nothing"]))


# -- what a core function returns --------------------------------------------

def participant_dict(row) -> dict:
    return {
        "participant": f"PT-{row['id']}", "id": row["id"], "roles": row["roles"],
        "agent": row["agent"], "session": row["session_id"],
        "harness": row["harness"], "endpoint": row["endpoint"],
        "bound_by": f"PT-{row['bound_by']}" if row["bound_by"] else None,
        "bound_for": f"A-{row['bound_for']}" if row["bound_for"] else None,
        "granted_by": f"PT-{row['granted_by']}" if row["granted_by"] else None,
    }


def assignment_dict(row) -> dict:
    return {
        "assignment": f"A-{row['id']}", "id": row["id"], "title": row["title"],
        "outcome": row["outcome"], "place": row["place"],
        "generation": row["generation"], "revision": row["revision"],
        "recipient": row["recipient"], "requirement": row["requirement"],
        "depends": row["depends"], "branch": row["branch"],
        "holder": f"PT-{row['holder']}" if row["holder"] else None,
        "submitted_by": f"PT-{row['submitted_by']}" if row["submitted_by"] else None,
        "verified_by": f"PT-{row['verified_by']}" if row["verified_by"] else None,
        "accepted_by": f"PT-{row['accepted_by']}" if row["accepted_by"] else None,
    }


def message_dict(row) -> dict:
    return {
        "message": f"M-{row['id']}", "id": row["id"], "purpose": row["purpose"],
        "sender": f"PT-{row['sender']}", "recipient": row["recipient"],
        "body": row["body"], "artifact": row["artifact"], "place": row["place"],
        "assignment": f"A-{row['assignment']}" if row["assignment"] else None,
        "queued_at": row["queued_at"], "delivered_at": row["delivered_at"],
        "delivery_ref": row["delivery_ref"], "acked_at": row["acked_at"],
        "acked_by": f"PT-{row['acked_by']}" if row["acked_by"] else None,
    }


def observation_dict(row) -> dict:
    return {
        "observation": f"E-{row['id']}", "id": row["id"],
        "assignment": f"A-{row['assignment']}", "producer": f"PT-{row['producer']}",
        "revision": row["revision"], "execution": row["execution"],
        "requirement": row["requirement"], "environment": row["environment"],
        "text": row["observation"], "artifact": row["artifact"],
        "applicability": row["applicability"], "stale_reason": row["stale_reason"],
    }


def decision_dict(row) -> dict:
    return {
        "decision": f"DC-{row['id']}", "id": row["id"], "question": row["question"],
        "alternatives": row["alternatives"], "counter": row["counter"],
        "unknowns": row["unknowns"], "consequence": row["consequence"],
        "choice": row["choice"], "rationale": row["rationale"],
        "decided_by": f"PT-{row['decided_by']}" if row["decided_by"] else None,
        "decided_at": row["decided_at"],
        "assignment": f"A-{row['assignment']}" if row["assignment"] else None,
    }


def named_revision(value, where: str) -> str:
    """A revision is the identity of the candidate the work is against,
    and the empty string is not an identity.

    Every revision gate reads `if row["revision"] and ...`, so a falsy
    column lifts all of them at once: Grok and Codex both submitted
    `--revision ''` against b1d868b0 and then verified a candidate the
    submission had never named. Leaving a revision out and naming an
    empty one are different acts and the second says so.
    """
    text = (value or "").strip()
    if not text:
        refuse("revision", f"the revision {where} is against",
               "an empty string" if value == "" else repr(value),
               "name it; leaving it out where it is optional is a "
               "different thing and reads as one")
    return text


def no_store(**rest) -> dict:
    """Could not look, said as a marker: a read with no store behind it
    returns this and never an empty list dressed as an answer
    (docs/wire.md, absence discipline)."""
    return {"store": "absent", **rest}


# -- the core: one function per verb, keyed by the wire name in CORE ----------

def core_bind(conn, part, *, agent, roles, harness=None,
              endpoint=None, probe=None) -> dict:
    """This session's own participant, and no other session's.

    `part` is None here by construction: binding is how a session comes
    to have one. The session id is read here and is not an argument —
    taking it as one let a worker process mint participants for sessions
    that do not exist and rewrite a bound lead's agent, endpoint and
    probe (Grok bcfee6#2 against b1d868b0).
    """
    part = same_session(conn, part)
    named = roles_of(roles)
    key = session("").strip()
    if not key:
        refuse("session", "a session id in the environment", "unset",
               "run under a harness that sets CLAUDE_CODE_SESSION_ID")
    # The read that decides and the write that acts take the lock
    # together. `writer()` is autocommit, so between the count and the
    # insert two first callers both read zero and both took roles above
    # worker: all three reviewers of round two reproduced two roots in
    # that window against b1d868b0.
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT * FROM participants WHERE session_id = ?", (key,)
        ).fetchone()
        if row is not None:
            # A re-bind is how a session refreshes where it can be reached
            # and what its last probe said. It is not how it changes what
            # it may do: Codex reproduced a bound worker re-binding itself
            # as a lead and drafting its own work against 05b8aebe.
            if set(named.split(",")) != set(row["roles"].split(",")):
                refuse("role", f"the roles PT-{row['id']} holds, {row['roles']}", named,
                       "a re-bind refreshes the endpoint and the probe; "
                       "a lead grants roles with grant")
            conn.execute(
                "UPDATE participants SET agent = ?, harness = ?, endpoint = ?, "
                "probe = ?, bound_at = ? WHERE id = ?",
                (agent, harness, endpoint, probe, stamp(), row["id"]),
            )
            pid = row["id"]
        else:
            bootstrap = conn.execute(
                "SELECT COUNT(*) AS n FROM participants"
            ).fetchone()["n"] == 0
            if not bootstrap and named != "worker":
                # Authority is a chain and the store's first participant is
                # its root. Announcing yourself is worth worker and nothing
                # else; everything above it is somebody's grant.
                refuse("role", "worker for a self-bind after the first participant",
                       named,
                       "bind --roles worker, then a lead grants the rest with "
                       "grant PT-n --roles R")
            pid = conn.execute(
                "INSERT INTO participants(session_id, agent, harness, roles, endpoint, "
                "probe, bound_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, agent, harness, named, endpoint, probe, stamp()),
            ).lastrowid
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return participant_dict(participant_row(conn, pid))


def core_grant(conn, part, *, agent, participant, roles) -> dict:
    """Roles above worker come from a lead, and the row says whose.

    The bootstrap aside, this is the only way a participant comes to hold
    anything but worker, which is what makes authority a chain that can
    be read back rather than a label a caller wrote about itself
    (objective sections 6 and 7; ruled by the Lead, 2026-09-16).
    """
    part = same_session(conn, part)
    require_role(part, ("lead",))
    named = roles_of(roles)
    _, pid = parse_id(participant, "PT")
    row = participant_row(conn, pid)
    held = dict.fromkeys(role for role in row["roles"].split(",") if role)
    held.update(dict.fromkeys(named.split(",")))
    conn.execute(
        "UPDATE participants SET roles = ?, granted_by = ?, granted_at = ? WHERE id = ?",
        (",".join(held), part["id"], stamp(), pid),
    )
    return participant_dict(participant_row(conn, pid))


def core_revoke(conn, part, *, agent, participant, roles) -> dict:
    """A role that can be given can be taken back, by a lead, on the record.

    `grant` is additive and nothing in the table subtracted, so a store
    accumulated authority and never shed it: the trial store stands at
    two leads because the roles were granted for a trial and could not be
    put down afterwards. Found in the live run, not in a review.

    One thing it will not do. A store with no lead in it has nobody who
    can ever grant one again — the chain's root is gone and no verb here
    can restore it — so the count is of the leads that would be left
    after the subtraction, whoever the subject is, the caller included. A
    last lead taking its own lead role down is the same store either way.

    What is left is never nothing: announcing yourself is worth worker,
    so a participant stripped of everything stands where a fresh
    self-bind would stand.
    """
    part = same_session(conn, part)
    require_role(part, ("lead",))
    named = roles_of(roles)
    _, pid = parse_id(participant, "PT")
    row = participant_row(conn, pid)
    held = [role for role in row["roles"].split(",") if role]
    taking = named.split(",")
    absent = [role for role in taking if role not in held]
    if absent:
        # Taking back what was never given is a refusal, not a silent
        # no-op that reads back as success (docs/wire.md, absence
        # discipline).
        refuse("role", f"roles PT-{pid} holds, {row['roles']}", ", ".join(absent),
               "name a role the participant holds; nothing was taken")
    left = [role for role in held if role not in taking] or ["worker"]
    standing = conn.execute("SELECT id, roles FROM participants").fetchall()
    leads = [other["id"] for other in standing
             if "lead" in (left if other["id"] == pid
                           else [role for role in (other["roles"] or "").split(",")
                                 if role])]
    if not leads:
        refuse("role", "a store left holding at least one lead",
               f"no lead at all once PT-{pid} stands at {','.join(left)}",
               "grant lead to another participant first; a store with no "
               "lead has nobody who can ever grant one")
    conn.execute(
        "UPDATE participants SET roles = ?, revoked_by = ?, revoked_at = ? WHERE id = ?",
        (",".join(left), part["id"], stamp(), pid),
    )
    return participant_dict(participant_row(conn, pid))


def core_bind_for(conn, part, *, agent, session_id, roles, assignment,
                  harness=None, endpoint=None, probe=None) -> dict:
    """A participant for a session that cannot bind itself.

    A dispatched Codex or Grok worker has no harness session id in its
    environment, so it could hold no participant and every mutation it
    made refused class `participant`. The launcher mints a session id per
    dispatch and sets it as CLAUDE_SESSION_ID, the older key
    instrument.session() already admits. Only a dispatcher may issue one,
    and the binding records who issued it and for which assignment, so a
    participant nobody dispatched is visible as such.
    """
    part = same_session(conn, part)
    require_role(part, ("dispatcher",))
    named = roles_of(roles)
    key = (session_id or "").strip()
    if not key:
        refuse("arguments", "a non-empty session id", repr(session_id),
               "the session id the launcher minted for the worker")
    if set(named.split(",")) - {"worker"}:
        # Minting a worker is a dispatcher's. Minting anything above one
        # is a grant, and a grant is a lead's.
        require_role(part, ("lead",))
    _, aid = parse_id(assignment, "A")
    # The same lock as a self-bind, for the same reason: the conflict
    # check reads and the mint writes, and two dispatchers minting for
    # one session id would otherwise both read nothing there.
    conn.execute("BEGIN IMMEDIATE")
    try:
        assignment_row(conn, aid)
        row = conn.execute(
            "SELECT id FROM participants WHERE session_id = ?", (key,)
        ).fetchone()
        if row is not None:
            # It never overwrites: Grok reproduced a bind-for rewriting a
            # bound lead's own row as a worker against 05b8aebe.
            refuse("conflict", f"no participant for session {key}",
                   f"PT-{row['id']}, bound already",
                   "that session is bound; a lead grants roles with grant PT-n --roles R")
        # Roles above worker are a grant, and a grant says who made it
        # and when, the way `grant` does. `bound_by` is not that record:
        # it says who ran the verb, not that anything was conferred. The
        # audit minted a verifier through this verb against b1d868b0 and
        # the store carried no grant at all (codex-1833de#5).
        granted = part["id"] if set(named.split(",")) - {"worker"} else None
        pid = conn.execute(
            "INSERT INTO participants(session_id, agent, harness, roles, endpoint, "
            "probe, bound_at, bound_by, bound_for, granted_by, granted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (key, agent, harness, named, endpoint, probe, stamp(), part["id"], aid,
             granted, stamp() if granted else None),
        ).lastrowid
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return participant_dict(participant_row(conn, pid))


def core_who(conn, part) -> dict:
    """A read: with no store it could not look, and says so rather than
    refusing class participant, which would read as having looked."""
    part = same_session(conn, part)
    if conn is None or part is None:
        return no_store(participant=None)
    return participant_dict(part)


def core_participants(conn, part, *, role=None) -> dict:
    part = same_session(conn, part)
    if conn is None:
        return no_store(participants=[])
    rows = conn.execute("SELECT * FROM participants ORDER BY id").fetchall()
    shown = [r for r in rows if not role or role in r["roles"].split(",")]
    return {"participants": [participant_dict(r) for r in shown]}


def core_draft(conn, part, *, agent, title, outcome, requirement=None, revision=None,
               depends=None, duty=None, scope=None, inputs=None) -> dict:
    part = same_session(conn, part)
    require_role(part, ("lead", "coordinator"))
    if revision is not None:
        revision = named_revision(revision, "the draft")
    sid = machine.create(conn, ASSIGNMENT, actor(part))
    conn.execute(
        "INSERT INTO assignments(id, title, outcome, requirement, scope, inputs, "
        "depends, revision, generation, duty, opened_by, opened_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
        (sid, title, outcome, requirement, scope, inputs, depends, revision,
         duty, part["id"], stamp()),
    )
    return assignment_dict(assignment_row(conn, sid))


def core_offer(conn, part, *, agent, assignment, to, generation) -> dict:
    part = same_session(conn, part)
    require_role(part, ("lead", "coordinator"))
    _, aid = parse_id(assignment, "A")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    recipient = recipient_of(conn, to)

    def gate(_subject):
        require_generation(assignment_row(conn, aid), generation)
        conn.execute("UPDATE assignments SET recipient = ? WHERE id = ?", (recipient, aid))

    advance(conn, aid, "offer", part, note=recipient, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_claim(conn, part, *, agent, assignment, branch, generation, ttl=None) -> dict:
    part = same_session(conn, part)
    _, aid = parse_id(assignment, "A")
    ttl_s = int(ttl) * 60 if str(ttl or "").isdigit() else None
    require_lock(branch)
    row = assignment_row(conn, aid)
    require_generation(row, generation)

    def gate(_subject):
        live = assignment_row(conn, aid)
        require_generation(live, generation)
        if not addressed(part, live["recipient"] or ""):
            refuse("recipient", f"the named recipient {live['recipient'] or 'nobody'} "
                   f"of A-{aid}", f"PT-{part['id']} ({part['roles']})",
                   "the recipient claims it, or it is reassigned first")
        conn.execute(
            "UPDATE assignments SET holder = ?, branch = ? WHERE id = ?",
            (part["id"], branch, aid),
        )

    advance(conn, aid, "claim", part, note=branch, ttl_s=ttl_s, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def _hand_back(conn, part, *, agent, assignment, why, generation, transition, to=None) -> dict:
    """release and reassign: the hold goes back and the generation bumps."""
    _, aid = parse_id(assignment, "A")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    if transition == "reassign":
        require_role(part, ("lead", "coordinator"))
        recipient = recipient_of(conn, to)
    else:
        held = machine.subject(conn, ASSIGNMENT, aid)
        if row["holder"] != part["id"] and not machine.lapsed(held):
            refuse("holder", f"the holder PT-{row['holder']} of A-{aid}",
                   f"PT-{part['id']}",
                   "the holder releases it, anyone once the lease lapses, "
                   "or a lead reassigns it")
        recipient = row["recipient"]

    def gate(_subject):
        live = assignment_row(conn, aid)
        require_generation(live, generation)
        conn.execute(
            "UPDATE assignments SET holder = NULL, recipient = ? WHERE id = ?",
            (recipient, aid),
        )

    advance(conn, aid, transition, part, evidence=why, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_release(conn, part, *, agent, assignment, why, generation) -> dict:
    part = same_session(conn, part)
    return _hand_back(conn, part, agent=agent, assignment=assignment, why=why,
                      generation=generation, transition="release")


def core_reassign(conn, part, *, agent, assignment, to, why, generation) -> dict:
    part = same_session(conn, part)
    return _hand_back(conn, part, agent=agent, assignment=assignment, why=why,
                      generation=generation, transition="reassign", to=to)


def core_submit(conn, part, *, agent, assignment, evidence, revision, generation) -> dict:
    part = same_session(conn, part)
    _, aid = parse_id(assignment, "A")
    evidence = reading(evidence, "the candidate")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    require_holder(part, row)
    revision = named_revision(revision, "the submission")
    if row["revision"] and revision != row["revision"]:
        refuse("revision", f"the applicable revision {row['revision']} of A-{aid}",
               revision, "submit against the applicable revision, or reopen it")

    def gate(_subject):
        live = assignment_row(conn, aid)
        require_generation(live, generation)
        conn.execute(
            "UPDATE assignments SET submitted_by = ?, revision = ? WHERE id = ?",
            (part["id"], revision, aid),
        )
        # Defence in depth: with observe gated on a named candidate no
        # verb can produce a current row of another revision, but a store
        # written before that gate can hold one. The row is marked, never
        # deleted, and keeps its text and its scope (objective §11).
        conn.execute(
            "UPDATE observations SET applicability = 'stale', stale_reason = ? "
            "WHERE assignment = ? AND applicability = 'current' AND revision != ?",
            (f"the candidate submitted is {revision}, not the revision observed",
             aid, revision),
        )

    advance(conn, aid, "submit", part, evidence=evidence, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_verify(conn, part, *, agent, assignment, candidate, evidence,
                generation) -> dict:
    """Two readings, and they are not the same reading.

    `candidate` is the revision's identity and must be the one the
    assignment stands at; `evidence` is a reading of the verification run
    itself. One option carried both before, so a candidate submitted with
    a P- corpus row or a dispatch record id as its reading could never be
    verified at all (Grok #8 against 05b8aebe). Both go through the
    contract's pinned evidence shapes.
    """
    part = same_session(conn, part)
    _, aid = parse_id(assignment, "A")
    candidate = reading(candidate, "the candidate")
    evidence = reading(evidence, "the verification")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    require_role(part, ("verifier", "lead"))
    not_the_producer(part, row, "verifies")
    candidate = named_revision(candidate, "the verification")
    if not row["revision"]:
        # Defence in depth, and the half the check on submit cannot
        # reach: a store written before that check can hold such a row,
        # and comparing a candidate against nothing verified anything.
        refuse("revision", f"a candidate named on A-{aid}", "none",
               "submit names the revision the work is against; an "
               "assignment standing at none cannot be verified")
    if candidate != row["revision"]:
        refuse("revision", f"the applicable revision {row['revision']} of A-{aid}",
               candidate,
               "verify the candidate that was submitted, or reopen the assignment")

    def gate(_subject):
        live = assignment_row(conn, aid)
        require_generation(live, generation)
        conn.execute("UPDATE assignments SET verified_by = ? WHERE id = ?",
                     (part["id"], aid))

    advance(conn, aid, "verify", part, evidence=evidence, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_return(conn, part, *, agent, assignment, findings, generation) -> dict:
    """The candidate goes back to its holder with what was found.

    The generation is checked twice, as every other generation-bearing
    transition checks it: once here so a stale caller reads class
    generation and not class place, and once inside the gate under the
    write lock, so a candidate that moved between the two is not moved
    on (docs/workflow.md: every transition names its gate).
    """
    part = same_session(conn, part)
    _, aid = parse_id(assignment, "A")
    findings = reading(findings, "the findings")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    require_role(part, ("verifier", "lead"))

    def gate(_subject):
        require_generation(assignment_row(conn, aid), generation)

    advance(conn, aid, "return", part, evidence=findings, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_accept(conn, part, *, agent, assignment, evidence, generation) -> dict:
    part = same_session(conn, part)
    _, aid = parse_id(assignment, "A")
    evidence = reading(evidence, "the acceptance")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    require_role(part, ("lead",))
    not_the_producer(part, row, "accepts")

    def gate(_subject):
        live = assignment_row(conn, aid)
        require_generation(live, generation)
        conn.execute("UPDATE assignments SET accepted_by = ? WHERE id = ?",
                     (part["id"], aid))

    advance(conn, aid, "accept", part, evidence=evidence, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_reopen(conn, part, *, agent, assignment, revision, why, generation) -> dict:
    """A changed candidate: the observations go stale and keep their scope."""
    part = same_session(conn, part)
    revision = named_revision(revision, "the reopen")
    _, aid = parse_id(assignment, "A")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    require_role(part, ("lead", "coordinator"))

    def gate(_subject):
        live = assignment_row(conn, aid)
        require_generation(live, generation)
        conn.execute(
            "UPDATE assignments SET revision = ?, verified_by = NULL WHERE id = ?",
            (revision, aid),
        )
        conn.execute(
            "UPDATE observations SET applicability = 'stale', stale_reason = ? "
            "WHERE assignment = ? AND applicability = 'current'",
            (f"the candidate moved to {revision}: {why}", aid),
        )

    advance(conn, aid, "reopen", part, evidence=revision, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_supersede(conn, part, *, agent, assignment, by, generation) -> dict:
    """Superseding is a writing verb on an assignment like any other.

    It moves an `offered` assignment, and `offered` is exactly the place
    a `release` or a `reassign` returns one to, so the place alone cannot
    tell the assignment that stands there now from the one the caller
    read. The Daybreak audit reproduced that ABA against b1d868b0.
    """
    part = same_session(conn, part)
    require_role(part, ("lead", "coordinator"))
    _, aid = parse_id(assignment, "A")
    _, newer = parse_id(by, "A")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    assignment_row(conn, newer)

    def gate(_subject):
        require_generation(assignment_row(conn, aid), generation)
        conn.execute("UPDATE assignments SET superseded_by = ? WHERE id = ?", (newer, aid))

    advance(conn, aid, "supersede", part, evidence=f"A-{newer}", gate=gate)
    shown = assignment_dict(assignment_row(conn, aid))
    shown["superseded_by"] = f"A-{newer}"
    return shown


def core_assignments(conn, part, *, state=None, to=None) -> dict:
    """`part` filters to what that participant holds; None shows every row."""
    part = same_session(conn, part)
    if conn is None:
        return no_store(assignments=[])
    rows = conn.execute(
        "SELECT a.*, s.place FROM assignments a JOIN subjects s ON s.id = a.id "
        "ORDER BY a.id"
    ).fetchall()
    holder = part["id"] if part is not None else None
    shown = [
        row for row in rows
        if (not state or row["place"] == state)
        and (not to or row["recipient"] == to)
        and (holder is None or row["holder"] == holder)
    ]
    return {"assignments": [assignment_dict(row) for row in shown]}


def core_send(conn, part, *, agent, to, purpose, body, assignment=None, decision=None,
              reply_to=None, artifact=None) -> dict:
    part = same_session(conn, part)
    if purpose not in PURPOSES:
        refuse("arguments", "a purpose of " + ", ".join(PURPOSES), purpose,
               "an inform carries no obligation; a request and a finding do")
    recipient = recipient_of(conn, to)
    aid = parse_id(assignment, "A")[1] if assignment else None
    did = parse_id(decision, "DC")[1] if decision else None
    reply = parse_id(reply_to, "M")[1] if reply_to else None
    if aid is not None:
        assignment_row(conn, aid)
    sid = machine.create(conn, MESSAGE, actor(part))
    conn.execute(
        "INSERT INTO messages(id, sender, recipient, purpose, body, artifact, "
        "assignment, decision, reply_to, queued_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sid, part["id"], recipient, purpose, body, artifact, aid, did, reply, stamp()),
    )
    return message_dict(message_row(conn, sid))


def core_deliver(conn, part, *, message, ref) -> dict:
    """The transport's own receipt. The core never sends; it records."""
    part = same_session(conn, part)
    _, mid = parse_id(message, "M")
    row = message_row(conn, mid)
    if row["sender"] != part["id"] and not addressed(part, row["recipient"]):
        refuse("recipient", f"the sender PT-{row['sender']} or the recipient "
               f"{row['recipient']} of M-{mid}", f"PT-{part['id']}",
               "the route that carried it records its receipt")
    conn.execute("UPDATE messages SET delivered_at = ?, delivery_ref = ? WHERE id = ?",
                 (stamp(), ref, mid))
    return message_dict(message_row(conn, mid))


def core_ack(conn, part, *, message) -> dict:
    part = same_session(conn, part)
    _, mid = parse_id(message, "M")
    row = message_row(conn, mid)
    if not addressed(part, row["recipient"]):
        refuse("recipient", f"the recipient {row['recipient']} of M-{mid}",
               f"PT-{part['id']} ({part['roles']})",
               "the recipient acknowledges its own message")
    conn.execute("UPDATE messages SET acked_at = ?, acked_by = ? WHERE id = ?",
                 (stamp(), part["id"], mid))
    return message_dict(message_row(conn, mid))


def core_resolve(conn, part, *, agent, message, evidence) -> dict:
    """Resolution is a place, moved by the obligation's holder, never by
    the acknowledgment (AC-04)."""
    part = same_session(conn, part)
    _, mid = parse_id(message, "M")
    evidence = reading(evidence, "the resolution")
    row = message_row(conn, mid)
    allowed = addressed(part, row["recipient"])
    if not allowed and row["assignment"] is not None:
        allowed = assignment_row(conn, row["assignment"])["holder"] == part["id"]
    if not allowed:
        refuse("recipient", f"the recipient {row['recipient']} of M-{mid}, "
               "or the holder of its assignment", f"PT-{part['id']} ({part['roles']})",
               "the participant that owes the answer resolves it")
    machine.move(conn, MESSAGE, mid, "resolve", actor(part), evidence=evidence)
    shown = message_dict(message_row(conn, mid))
    shown["evidence"] = evidence
    return shown


def core_withdraw(conn, part, *, agent, message, why) -> dict:
    part = same_session(conn, part)
    _, mid = parse_id(message, "M")
    row = message_row(conn, mid)
    if row["sender"] != part["id"]:
        refuse("recipient", f"the sender PT-{row['sender']} of M-{mid}",
               f"PT-{part['id']}", "the sender withdraws its own message")
    machine.move(conn, MESSAGE, mid, "withdraw", actor(part), evidence=why)
    return message_dict(message_row(conn, mid))


def core_inbox(conn, part, *, unresolved=False) -> dict:
    part = same_session(conn, part)
    if conn is None:
        return no_store(messages=[])
    rows = conn.execute(
        "SELECT m.*, s.place FROM messages m JOIN subjects s ON s.id = m.id ORDER BY m.id"
    ).fetchall()
    shown = [row for row in rows if addressed(part, row["recipient"])
             and (not unresolved or row["place"] == "open")]
    return {"messages": [message_dict(row) for row in shown]}


def core_outstanding(conn, part, *, to=None) -> dict:
    """An obligation stays here until it is resolved; an ack does not lift it."""
    part = same_session(conn, part)
    if conn is None:
        return no_store(outstanding=[])
    rows = conn.execute(
        "SELECT m.*, s.place FROM messages m JOIN subjects s ON s.id = m.id "
        "WHERE s.place = 'open' ORDER BY m.id"
    ).fetchall()
    shown = [row for row in rows if row["purpose"] in OBLIGATIONS
             and (not to or row["recipient"] == to)]
    return {"outstanding": [message_dict(row) for row in shown]}


def core_undelivered(conn, part, *, to=None) -> dict:
    """The messages queued to the calling participant that have not left
    the store yet — what a deliverer asks before it carries anything.

    `outstanding` is not this read and cannot stand in for it: an
    obligation stays outstanding long after it was delivered, and an
    inform is never outstanding at all yet still has to be carried. A
    withdrawn message is not carried, so only the open ones are here.
    Addressing is the inbox's rule: a participant by id, or a role its
    holder answers to.
    """
    part = same_session(conn, part)
    if conn is None:
        return no_store(undelivered=[])
    rows = conn.execute(
        "SELECT m.*, s.place FROM messages m JOIN subjects s ON s.id = m.id "
        "WHERE m.delivered_at IS NULL AND s.place = 'open' ORDER BY m.id"
    ).fetchall()
    shown = [row for row in rows if addressed(part, row["recipient"])
             and (not to or row["recipient"] == to)]
    return {"undelivered": [message_dict(row) for row in shown]}


def core_observe(conn, part, *, assignment, observation, revision, generation,
                 stale=False, execution=None, artifact=None, requirement=None,
                 environment=None) -> dict:
    """An observation names the candidate it was made against.

    Raised by the Codex review of package C and ruled by the Lead session
    on 2026-09-16: without these two checks a participant that had not
    seen a reopen could append an observation of the old revision and it
    read as current evidence of the new one. The checks and the insert
    take the write lock together, the way the engine's own move does, so
    a reopen committing between the read and the insert cannot slip
    between them.

    Filing the row as stale is the declared escape and it is not a pass:
    the row lands marked, carrying the revision it was made against, so
    it is readable as history and never as evidence of what replaced it.
    Both checks lift for it, because a reopen moves the generation and
    the revision together and an old observation could otherwise never be
    filed at all.
    """
    part = same_session(conn, part)
    _, aid = parse_id(assignment, "A")
    if not str(generation).isdigit():
        refuse("arguments", "--generation as a whole number", str(generation),
               "the generation printed by show")
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = assignment_row(conn, aid)
        if not row["revision"]:
            refuse("revision", f"a candidate named on A-{aid}", "no revision",
                   "draft it with --revision, or submit one, before observing it")
        reason = None
        if stale:
            reason = (f"filed as stale by PT-{part['id']}: observed at {revision}, "
                      f"the assignment stands at {row['revision'] or 'no revision'} "
                      f"at generation {row['generation']}")
        else:
            require_generation(row, generation)
            if row["revision"] and revision != row["revision"]:
                refuse("revision", f"the current revision {row['revision']} of A-{aid}",
                       revision,
                       "observe the candidate that stands, or file it with --stale")
        cursor = conn.execute(
            "INSERT INTO observations(assignment, producer, requirement, execution, "
            "revision, environment, observation, artifact, applicability, "
            "stale_reason, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (aid, part["id"], requirement, execution, revision, environment,
             observation, artifact, "stale" if stale else "current", reason, stamp()),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    row = conn.execute(
        "SELECT * FROM observations WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return observation_dict(row)


def core_observations(conn, part, *, assignment, include_stale=False) -> dict:
    part = same_session(conn, part)
    _, aid = parse_id(assignment, "A")
    if conn is None:
        return no_store(observations=[])
    assignment_row(conn, aid)
    rows = conn.execute(
        "SELECT * FROM observations WHERE assignment = ? ORDER BY id", (aid,)
    ).fetchall()
    shown = [row for row in rows
             if include_stale or row["applicability"] == "current"]
    return {"observations": [observation_dict(row) for row in shown]}


def core_ask(conn, part, *, question, alternatives, assignment=None) -> dict:
    part = same_session(conn, part)
    aid = parse_id(assignment, "A")[1] if assignment else None
    if aid is not None:
        assignment_row(conn, aid)
    cursor = conn.execute(
        "INSERT INTO decisions(asked_by, question, alternatives, assignment, asked_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (part["id"], question, alternatives, aid, stamp()),
    )
    return decision_dict(decision_row(conn, cursor.lastrowid))


def core_answer(conn, part, *, decision, counter=None, unknowns=None,
                consequence=None) -> dict:
    part = same_session(conn, part)
    if counter is None and unknowns is None and consequence is None:
        refuse("arguments", "at least one of --counter, --unknowns, --consequence",
               "none", "say what the brief is missing")
    _, did = parse_id(decision, "DC")
    decision_row(conn, did)
    for value, sql in (
        (counter, "UPDATE decisions SET counter = ? WHERE id = ?"),
        (unknowns, "UPDATE decisions SET unknowns = ? WHERE id = ?"),
        (consequence, "UPDATE decisions SET consequence = ? WHERE id = ?"),
    ):
        if value:
            conn.execute(sql, (value, did))
    return decision_dict(decision_row(conn, did))


def core_decide(conn, part, *, decision, choice, rationale) -> dict:
    part = same_session(conn, part)
    _, did = parse_id(decision, "DC")
    require_role(part, ("lead",))
    decision_row(conn, did)
    conn.execute(
        "UPDATE decisions SET choice = ?, rationale = ?, decided_by = ?, "
        "decided_at = ? WHERE id = ?", (choice, rationale, part["id"], stamp(), did),
    )
    return decision_dict(decision_row(conn, did))


def core_decision(conn, part, *, decision) -> dict:
    """The bounded brief: what is missing is named, never passed over."""
    part = same_session(conn, part)
    _, did = parse_id(decision, "DC")
    if conn is None:
        return no_store(decision=None)
    row = decision_row(conn, did)
    observations = conn.execute(
        "SELECT * FROM observations WHERE assignment IS ? AND applicability = 'current' "
        "ORDER BY id", (row["assignment"],)
    ).fetchall() if row["assignment"] else []
    brief = decision_dict(row)
    brief["gaps"] = [name for name in ("counter", "unknowns", "consequence")
                     if not row[name]]
    brief["observations"] = [observation_dict(entry) for entry in observations]
    return brief


def core_decisions(conn, part, *, undecided_only=False) -> dict:
    part = same_session(conn, part)
    if conn is None:
        return no_store(decisions=[])
    rows = conn.execute("SELECT * FROM decisions ORDER BY id").fetchall()
    shown = [row for row in rows if not undecided_only or row["decided_at"] is None]
    return {"decisions": [decision_dict(row) for row in shown]}


def core_reserve(conn, part, *, agent, name, assignment, ttl=None) -> dict:
    part = same_session(conn, part)
    _, aid = parse_id(assignment, "A")
    ttl_s = int(ttl) * 60 if str(ttl or "").isdigit() else None
    assignment_row(conn, aid)
    row = conn.execute("SELECT * FROM resources WHERE name = ?", (name,)).fetchone()
    if row is None:
        sid = machine.create(conn, RESOURCE, actor(part))
        conn.execute("INSERT INTO resources(id, name, assignment) VALUES (?, ?, ?)",
                     (sid, name, aid))
    else:
        sid = row["id"]

    def gate(_subject):
        conn.execute("UPDATE resources SET assignment = ?, holder = ? WHERE id = ?",
                     (aid, part["id"], sid))

    machine.move(conn, RESOURCE, sid, "reserve", actor(part), note=f"A-{aid}",
                 ttl_s=ttl_s, gate=gate)
    return {"resource": f"R-{sid}", "id": sid, "name": name, "place": "held",
            "assignment": f"A-{aid}", "assignment_id": aid,
            "holder": f"PT-{part['id']}"}


def core_free(conn, part, *, agent, name, why) -> dict:
    part = same_session(conn, part)
    row = conn.execute("SELECT * FROM resources WHERE name = ?", (name,)).fetchone()
    if row is None:
        refuse("unknown", "a reserved resource", name, "a name printed by resources")
    previous = row["holder"]

    def gate(subject):
        """A lapsed lease is evidence a reservation ran out, never proof
        the previous process stopped: the reconciliation is reported."""
        if previous != part["id"] and not machine.lapsed(subject):
            refuse("holder", f"the holder PT-{previous} of {name}",
                   f"PT-{part['id']}",
                   "the holder frees it, or anyone once the lease lapses")
        conn.execute("UPDATE resources SET holder = NULL WHERE id = ?", (row["id"],))

    machine.move(conn, RESOURCE, row["id"], "free", actor(part), evidence=why, gate=gate)
    return {"resource": f"R-{row['id']}", "id": row["id"], "name": name,
            "place": "free", "previous_holder": f"PT-{previous}",
            "reconciled": previous == part["id"]}


def core_resources(conn, part) -> dict:
    part = same_session(conn, part)
    if conn is None:
        return no_store(resources=[])
    rows = conn.execute(
        "SELECT r.*, s.place, s.held_since, s.ttl_s FROM resources r "
        "JOIN subjects s ON s.id = r.id ORDER BY r.id"
    ).fetchall()
    return {"resources": [{
        "resource": f"R-{row['id']}", "id": row["id"], "name": row["name"],
        "place": row["place"], "held_since": row["held_since"], "ttl_s": row["ttl_s"],
        "holder": f"PT-{row['holder']}" if row["holder"] else None,
        "assignment": f"A-{row['assignment']}" if row["assignment"] else None,
        "assignment_id": row["assignment"],
    } for row in rows]}


def core_show(conn, part, *, target) -> dict:
    part = same_session(conn, part)
    kind, number = parse_id(target, ("A", "M", "DC"))
    if kind == "DC":
        return core_decision(conn, part, decision=target)
    if conn is None:
        return no_store(target=target)
    if kind == "M":
        return message_dict(message_row(conn, number))
    shown = assignment_dict(assignment_row(conn, number))
    counts = conn.execute(
        "SELECT applicability, COUNT(*) AS n FROM observations WHERE assignment = ? "
        "GROUP BY applicability", (number,)
    ).fetchall()
    tally = {r["applicability"]: r["n"] for r in counts}
    shown["observations"] = {"current": tally.get("current", 0),
                             "stale": tally.get("stale", 0)}
    shown["marking"] = [machine.history_line(entry)
                        for entry in machine.history(conn, ASSIGNMENT, number)]
    return shown


def core_coverage(conn, part, *, requirement=None) -> dict:
    """requirement -> assignment -> candidate -> observation -> verification
    -> acceptance or the gap, named."""
    part = same_session(conn, part)
    if conn is None:
        return no_store(coverage=[])
    rows = conn.execute(
        "SELECT a.*, s.place FROM assignments a JOIN subjects s ON s.id = a.id "
        "ORDER BY a.id"
    ).fetchall()
    shown = [r for r in rows if not requirement or r["requirement"] == requirement]
    coverage = []
    for row in shown:
        current = conn.execute(
            "SELECT COUNT(*) AS n FROM observations WHERE assignment = ? "
            "AND applicability = 'current'", (row["id"],)
        ).fetchone()["n"]
        if row["place"] == "accepted":
            closure, gap = f"accepted by PT-{row['accepted_by']}", None
        elif row["verified_by"]:
            closure = f"verified by PT-{row['verified_by']}, acceptance gap"
            gap = "acceptance"
        else:
            closure, gap = "verification gap", "verification"
        entry = assignment_dict(row)
        entry.update({"observations": current, "closure": closure, "gap": gap})
        coverage.append(entry)
    return {"coverage": coverage}


def core_brief(conn, part) -> dict:
    """What a restarted or compacted participant reads to recover its
    obligations (AC-12): held work, unresolved inbox, open decisions."""
    part = same_session(conn, part)
    if conn is None:
        return no_store(brief=None)
    held = conn.execute(
        "SELECT a.*, s.place FROM assignments a JOIN subjects s ON s.id = a.id "
        "WHERE a.holder = ? ORDER BY a.id", (part["id"],)
    ).fetchall()
    messages = conn.execute(
        "SELECT m.*, s.place FROM messages m JOIN subjects s ON s.id = m.id "
        "WHERE s.place = 'open' ORDER BY m.id"
    ).fetchall()
    decisions = conn.execute(
        "SELECT * FROM decisions WHERE decided_at IS NULL ORDER BY id"
    ).fetchall()
    stale = conn.execute(
        "SELECT COUNT(*) AS n FROM observations WHERE producer = ? "
        "AND applicability = 'stale'", (part["id"],)
    ).fetchone()["n"]
    return {
        "participant": participant_dict(part),
        "held": [assignment_dict(row) for row in held],
        "unresolved": [message_dict(row) for row in messages
                       if addressed(part, row["recipient"])],
        "decisions_open": len(decisions),
        "observations_stale": stale,
    }


CORE = {
    "bind": core_bind, "bind-for": core_bind_for, "grant": core_grant,
    "revoke": core_revoke,
    "who": core_who,
    "participants": core_participants,
    "draft": core_draft, "offer": core_offer, "claim": core_claim,
    "release": core_release, "reassign": core_reassign, "submit": core_submit,
    "verify": core_verify, "return": core_return, "accept": core_accept,
    "reopen": core_reopen, "supersede": core_supersede,
    "assignments": core_assignments,
    "show": core_show, "send": core_send, "deliver": core_deliver, "ack": core_ack,
    "resolve": core_resolve, "withdraw": core_withdraw, "inbox": core_inbox,
    "outstanding": core_outstanding, "undelivered": core_undelivered,
    "observe": core_observe,
    "observations": core_observations, "ask": core_ask, "answer": core_answer,
    "decide": core_decide, "decision": core_decision, "decisions": core_decisions,
    "reserve": core_reserve, "free": core_free, "resources": core_resources,
    "coverage": core_coverage, "brief": core_brief,
}


# -- the CLI projection: parse argv, call the function, print -----------------

def do_bind(rest):
    agent = identity()
    _, opts = parse(rest, 0, required=("roles",), optional=("harness", "endpoint", "probe"))
    with writer() as conn:
        shown = CORE["bind"](conn, None, agent=agent,
                             roles=opts["roles"], harness=opts.get("harness"),
                             endpoint=opts.get("endpoint"), probe=opts.get("probe"))
    print(f"participant {shown['participant']} bound to session {shown['session']}")


def do_bind_for(rest):
    agent = identity()
    _, opts = parse(
        rest, 0, required=("session", "roles", "for"),
        optional=("harness", "endpoint", "probe"),
    )
    with writer() as conn:
        shown = CORE["bind-for"](conn, bound_participant(conn), agent=agent,
                                 session_id=opts["session"], roles=opts["roles"],
                                 assignment=opts["for"], harness=opts.get("harness"),
                                 endpoint=opts.get("endpoint"), probe=opts.get("probe"))
    print(f"participant {shown['participant']} bound for session {shown['session']} "
          f"by {shown['bound_by']} for {shown['bound_for']}")


def do_grant(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("roles",))
    with writer() as conn:
        shown = CORE["grant"](conn, bound_participant(conn), agent=agent,
                              participant=raw, roles=opts["roles"])
    print(f"granted {shown['roles']} to {shown['participant']} "
          f"by {shown['granted_by']}")


def do_revoke(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("roles",))
    with writer() as conn:
        shown = CORE["revoke"](conn, bound_participant(conn), agent=agent,
                               participant=raw, roles=opts["roles"])
    print(f"revoked {opts['roles']} from {shown['participant']}; "
          f"{shown['roles']} left")


def do_who(rest):
    parse(rest, 0)
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    shown = CORE["who"](conn, bound_participant(conn))
    print(f"participant {shown['participant']} {shown['roles']} "
          f"session {shown['session']}")
    return EXIT_DONE


def do_participants(rest):
    _, opts = parse(rest, 0, optional=("role",))
    shown = CORE["participants"](reader(), None, role=opts.get("role"))
    if shown.get("store") == "absent":
        print("no store")
        return EXIT_DONE
    if not shown["participants"]:
        print("no participants")
        return EXIT_DONE
    for row in shown["participants"]:
        issued = (f", bound by {row['bound_by']} for {row['bound_for']}"
                  if row["bound_by"] else "")
        print(f"{row['participant']} {row['roles']} — {row['agent']} "
              f"session {row['session']} harness {row['harness'] or 'unrecorded'}"
              f"{issued}")
    return EXIT_DONE


# -- assignments: verbs ------------------------------------------------------

def do_draft(rest):
    agent = identity()
    (title,), opts = parse(
        rest, 1, required=("outcome",),
        optional=("requirement", "revision", "depends", "duty", "scope", "inputs"),
    )
    with writer() as conn:
        shown = CORE["draft"](conn, bound_participant(conn), agent=agent, title=title,
                              outcome=opts["outcome"], requirement=opts.get("requirement"),
                              revision=opts.get("revision"), depends=opts.get("depends"),
                              duty=opts.get("duty"), scope=opts.get("scope"),
                              inputs=opts.get("inputs"))
    print(f"assignment {shown['assignment']}")


def do_offer(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("to", "generation"))
    with writer() as conn:
        shown = CORE["offer"](conn, bound_participant(conn), agent=agent, assignment=raw,
                              to=opts["to"], generation=opts["generation"])
    print(f"offered {shown['assignment']} to {shown['recipient']}")


def do_claim(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("branch", "generation"), optional=("ttl",))
    with writer() as conn:
        shown = CORE["claim"](conn, bound_participant(conn), agent=agent, assignment=raw,
                              branch=opts["branch"], generation=opts["generation"],
                              ttl=opts.get("ttl"))
    print(f"claimed {shown['assignment']} by {shown['holder']} on {shown['branch']}")


def do_release(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("why", "generation"))
    with writer() as conn:
        shown = CORE["release"](conn, bound_participant(conn), agent=agent, assignment=raw,
                                why=opts["why"], generation=opts["generation"])
    print(f"released {shown['assignment']} to {shown['recipient']}; "
          f"generation {shown['generation']}")


def do_reassign(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("to", "why", "generation"))
    with writer() as conn:
        shown = CORE["reassign"](conn, bound_participant(conn), agent=agent, assignment=raw,
                                 to=opts["to"], why=opts["why"],
                                 generation=opts["generation"])
    print(f"reassigned {shown['assignment']} to {shown['recipient']}; "
          f"generation {shown['generation']}")


def do_submit(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("evidence", "revision", "generation"))
    with writer() as conn:
        shown = CORE["submit"](conn, bound_participant(conn), agent=agent, assignment=raw,
                               evidence=opts["evidence"], revision=opts["revision"],
                               generation=opts["generation"])
    print(f"submitted {shown['assignment']} at {shown['revision']}")


def do_verify(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("candidate", "evidence", "generation"))
    with writer() as conn:
        shown = CORE["verify"](conn, bound_participant(conn), agent=agent, assignment=raw,
                               candidate=opts["candidate"], evidence=opts["evidence"],
                               generation=opts["generation"])
    print(f"verified {shown['assignment']} by {shown['verified_by']}")


def do_return(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("findings", "generation"))
    with writer() as conn:
        shown = CORE["return"](conn, bound_participant(conn), agent=agent, assignment=raw,
                               findings=opts["findings"], generation=opts["generation"])
    print(f"returned {shown['assignment']} to {shown['holder']}")


def do_accept(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("evidence", "generation"))
    with writer() as conn:
        shown = CORE["accept"](conn, bound_participant(conn), agent=agent, assignment=raw,
                               evidence=opts["evidence"], generation=opts["generation"])
    print(f"accepted {shown['assignment']} by {shown['accepted_by']}")


def do_reopen(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("revision", "why", "generation"))
    with writer() as conn:
        shown = CORE["reopen"](conn, bound_participant(conn), agent=agent, assignment=raw,
                               revision=opts["revision"], why=opts["why"],
                               generation=opts["generation"])
    print(f"reopened {shown['assignment']} at {shown['revision']}; "
          f"generation {shown['generation']}")


def do_supersede(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("by", "generation"))
    with writer() as conn:
        shown = CORE["supersede"](conn, bound_participant(conn), agent=agent, assignment=raw,
                                  by=opts["by"], generation=opts["generation"])
    print(f"superseded {shown['assignment']} by {shown['superseded_by']}")


def assignment_line(row: dict) -> str:
    who = row["holder"] or row["recipient"] or "nobody"
    return (f"{row['assignment']} {row['title']} — {row['place']}, {who}, "
            f"generation {row['generation']}, revision {row['revision'] or 'none'}")


def do_assignments(rest):
    _, opts = parse(rest, 0, optional=("state", "to"), flags=("mine",))
    conn = reader()
    part = bound_participant(conn) if opts.get("mine") else None
    shown = CORE["assignments"](conn, part, state=opts.get("state"), to=opts.get("to"))
    if shown.get("store") == "absent":
        print("no store")
        return EXIT_DONE
    if not shown["assignments"]:
        print("no assignments")
        return EXIT_DONE
    for row in shown["assignments"]:
        print(assignment_line(row))
    return EXIT_DONE


# -- messages: verbs ---------------------------------------------------------

def do_send(rest):
    agent = identity()
    _, opts = parse(
        rest, 0, required=("to", "purpose", "body"),
        optional=("assignment", "decision", "reply-to", "artifact"),
    )
    with writer() as conn:
        shown = CORE["send"](conn, bound_participant(conn), agent=agent, to=opts["to"],
                             purpose=opts["purpose"], body=opts["body"],
                             assignment=opts.get("assignment"),
                             decision=opts.get("decision"),
                             reply_to=opts.get("reply-to"), artifact=opts.get("artifact"))
    print(f"message {shown['message']} queued")


def do_deliver(rest):
    identity()
    (raw,), opts = parse(rest, 1, required=("ref",))
    with writer() as conn:
        shown = CORE["deliver"](conn, bound_participant(conn), message=raw, ref=opts["ref"])
    print(f"delivered {shown['message']} ref {shown['delivery_ref']}")


def do_ack(rest):
    identity()
    (raw,), _ = parse(rest, 1)
    with writer() as conn:
        shown = CORE["ack"](conn, bound_participant(conn), message=raw)
    print(f"acknowledged {shown['message']} by {shown['acked_by']}; not resolved")


def do_resolve(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("evidence",))
    with writer() as conn:
        shown = CORE["resolve"](conn, bound_participant(conn), agent=agent, message=raw,
                                evidence=opts["evidence"])
    print(f"resolved {shown['message']}: {shown['evidence']}")


def do_withdraw(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("why",))
    with writer() as conn:
        shown = CORE["withdraw"](conn, bound_participant(conn), agent=agent, message=raw,
                                 why=opts["why"])
    print(f"withdrew {shown['message']}")


def message_line(row: dict) -> str:
    tail = f" — {row['place']}" if row["place"] != "open" else ""
    return (f"{row['message']} {row['purpose']} from {row['sender']} to "
            f"{row['recipient']}: {row['body']}{tail}")


def do_inbox(rest):
    _, opts = parse(rest, 0, flags=("unresolved",))
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    shown = CORE["inbox"](conn, bound_participant(conn), unresolved=bool(opts.get("unresolved")))
    if not shown["messages"]:
        print("no messages")
        return EXIT_DONE
    for row in shown["messages"]:
        print(message_line(row))
    return EXIT_DONE


def do_undelivered(rest):
    _, opts = parse(rest, 0, optional=("to",))
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    shown = CORE["undelivered"](conn, bound_participant(conn), to=opts.get("to"))
    if not shown["undelivered"]:
        print("none undelivered")
        return EXIT_DONE
    for row in shown["undelivered"]:
        print(message_line(row) + f", queued {row['queued_at']}")
    return EXIT_DONE


def do_outstanding(rest):
    _, opts = parse(rest, 0, optional=("to",))
    shown = CORE["outstanding"](reader(), None, to=opts.get("to"))
    if shown.get("store") == "absent":
        print("no store")
        return EXIT_DONE
    if not shown["outstanding"]:
        print("none outstanding")
        return EXIT_DONE
    for row in shown["outstanding"]:
        seen = f", acknowledged {row['acked_at']}" if row["acked_at"] else ", not acknowledged"
        print(message_line(row) + seen)
    return EXIT_DONE


# -- observations, decisions, resources --------------------------------------

def do_observe(rest):
    identity()
    (raw,), opts = parse(
        rest, 1, required=("observation", "revision", "generation"),
        optional=("execution", "artifact", "requirement", "environment"),
        flags=("stale",),
    )
    with writer() as conn:
        shown = CORE["observe"](conn, bound_participant(conn), assignment=raw,
                                observation=opts["observation"], revision=opts["revision"],
                                generation=opts["generation"],
                                stale=bool(opts.get("stale")),
                                execution=opts.get("execution"),
                                artifact=opts.get("artifact"),
                                requirement=opts.get("requirement"),
                                environment=opts.get("environment"))
    print(f"observation {shown['observation']}")


def do_observations(rest):
    (raw,), opts = parse(rest, 1, flags=("all",))
    shown = CORE["observations"](reader(), None, assignment=raw,
                                 include_stale=bool(opts.get("all")))
    if shown.get("store") == "absent":
        print("no store")
        return EXIT_DONE
    if not shown["observations"]:
        print("no observations")
        return EXIT_DONE
    for row in shown["observations"]:
        mark = "" if row["applicability"] == "current" else f" [stale: {row['stale_reason']}]"
        where = f" ({row['execution']})" if row["execution"] else ""
        print(f"{row['observation']} {row['producer']} {row['revision']} — "
              f"{row['text']}{where}{mark}")
    return EXIT_DONE


def do_ask(rest):
    identity()
    _, opts = parse(rest, 0, required=("question", "alternatives"), optional=("assignment",))
    with writer() as conn:
        shown = CORE["ask"](conn, bound_participant(conn), question=opts["question"],
                            alternatives=opts["alternatives"],
                            assignment=opts.get("assignment"))
    print(f"decision {shown['decision']}")


def do_answer(rest):
    identity()
    (raw,), opts = parse(rest, 1, optional=("counter", "unknowns", "consequence"))
    with writer() as conn:
        shown = CORE["answer"](conn, bound_participant(conn), decision=raw,
                               counter=opts.get("counter"), unknowns=opts.get("unknowns"),
                               consequence=opts.get("consequence"))
    print(f"answered {shown['decision']}")


def do_decide(rest):
    identity()
    (raw,), opts = parse(rest, 1, required=("choice", "rationale"))
    with writer() as conn:
        shown = CORE["decide"](conn, bound_participant(conn), decision=raw, choice=opts["choice"],
                               rationale=opts["rationale"])
    print(f"decided {shown['decision']}: {shown['choice']}")


def print_decision(brief: dict) -> int:
    print(f"{brief['decision']} {brief['question']}")
    print(f"alternatives: {brief['alternatives']}")
    for label, key in (("counterevidence", "counter"), ("unknowns", "unknowns"),
                       ("consequence", "consequence")):
        print(f"{label}: {brief[key] or 'a declared gap, not a pass'}")
    print(f"observations: {len(brief['observations'])} current")
    if brief["decided_at"]:
        print(f"decided by {brief['decided_by']} at {brief['decided_at']}: "
              f"{brief['choice']} — {brief['rationale']}")
    else:
        print("undecided")
    return EXIT_DONE


def do_decision(rest):
    (raw,), _ = parse(rest, 1)
    shown = CORE["decision"](reader(), None, decision=raw)
    if shown.get("store") == "absent":
        print("no store")
        return EXIT_DONE
    return print_decision(shown)


def do_decisions(rest):
    _, opts = parse(rest, 0, flags=("open",))
    shown = CORE["decisions"](reader(), None, undecided_only=bool(opts.get("open")))
    if shown.get("store") == "absent":
        print("no store")
        return EXIT_DONE
    if not shown["decisions"]:
        print("no decisions")
        return EXIT_DONE
    for row in shown["decisions"]:
        state = row["choice"] if row["decided_at"] else "undecided"
        print(f"{row['decision']} {row['question']} — {state}")
    return EXIT_DONE


def do_reserve(rest):
    agent = identity()
    (name,), opts = parse(rest, 1, required=("for",), optional=("ttl",))
    with writer() as conn:
        shown = CORE["reserve"](conn, bound_participant(conn), agent=agent, name=name,
                                assignment=opts["for"], ttl=opts.get("ttl"))
    print(f"reserved {shown['name']} for {shown['assignment']} by {shown['holder']}")


def do_free(rest):
    agent = identity()
    (name,), opts = parse(rest, 1, required=("why",))
    with writer() as conn:
        shown = CORE["free"](conn, bound_participant(conn), agent=agent, name=name, why=opts["why"])
    note = ("" if shown["reconciled"]
            else f"; {shown['previous_holder']}'s run is not reconciled")
    print(f"freed {shown['name']}{note}")


def do_resources(rest):
    parse(rest, 0)
    shown = CORE["resources"](reader(), None)
    if shown.get("store") == "absent":
        print("no store")
        return EXIT_DONE
    if not shown["resources"]:
        print("no resources")
        return EXIT_DONE
    for row in shown["resources"]:
        print(f"{row['resource']} {row['name']} — {row['place']}, "
              f"{row['holder'] or 'free'}, A-{row['assignment_id'] or 0}")
    return EXIT_DONE


# -- the joined views --------------------------------------------------------

def do_show(rest):
    (raw,), _ = parse(rest, 1)
    shown = CORE["show"](reader(), None, target=raw)
    if shown.get("store") == "absent":
        print("no store")
        return EXIT_DONE
    if raw.startswith("DC-"):
        return print_decision(shown)
    if raw.startswith("M-"):
        print(message_line(shown))
        print(f"queued {shown['queued_at']}")
        if shown["delivered_at"]:
            print(f"delivered {shown['delivered_at']} ref {shown['delivery_ref']}")
        if shown["acked_at"]:
            print(f"acknowledged {shown['acked_at']} by {shown['acked_by']}")
        return EXIT_DONE
    print(assignment_line(shown))
    print(f"outcome: {shown['outcome']}")
    print(f"requirement: {shown['requirement'] or 'none'}; "
          f"branch: {shown['branch'] or 'none'}; depends: {shown['depends'] or 'none'}")
    print(f"observations: {shown['observations']['current']} current, "
          f"{shown['observations']['stale']} stale")
    print("marking:")
    for line in shown["marking"]:
        print(f"  {line}")
    return EXIT_DONE


def do_coverage(rest):
    _, opts = parse(rest, 0, optional=("requirement",))
    shown = CORE["coverage"](reader(), None, requirement=opts.get("requirement"))
    if shown.get("store") == "absent":
        print("no store")
        return EXIT_DONE
    if not shown["coverage"]:
        print("no assignments")
        return EXIT_DONE
    for row in shown["coverage"]:
        print(f"{row['requirement'] or 'requirement unstated'} → {row['assignment']} "
              f"{row['title']} → candidate {row['revision'] or 'none'} → "
              f"{row['observations']} observation(s) → {row['closure']}")
    return EXIT_DONE


def do_brief(rest):
    parse(rest, 0)
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    shown = CORE["brief"](conn, bound_participant(conn))
    who = shown["participant"]
    print(f"brief for {who['participant']} {who['roles']}")
    print("assignments held:")
    for row in shown["held"]:
        print(f"  {assignment_line(row)}")
    if not shown["held"]:
        print("  none")
    print("inbox unresolved:")
    for row in shown["unresolved"]:
        print(f"  {message_line(row)}")
    if not shown["unresolved"]:
        print("  none")
    print(f"decisions open: {shown['decisions_open']}")
    print(f"observations of mine gone stale: {shown['observations_stale']}")
    return EXIT_DONE


VERBS = {
    "bind": do_bind, "bind-for": do_bind_for, "grant": do_grant,
    "revoke": do_revoke,
    "who": do_who,
    "participants": do_participants,
    "draft": do_draft, "offer": do_offer, "claim": do_claim,
    "release": do_release, "reassign": do_reassign, "submit": do_submit,
    "verify": do_verify, "return": do_return, "accept": do_accept,
    "reopen": do_reopen, "supersede": do_supersede, "assignments": do_assignments,
    "show": do_show, "send": do_send, "deliver": do_deliver, "ack": do_ack,
    "resolve": do_resolve, "withdraw": do_withdraw, "inbox": do_inbox,
    "outstanding": do_outstanding, "undelivered": do_undelivered,
    "observe": do_observe,
    "observations": do_observations, "ask": do_ask, "answer": do_answer,
    "decide": do_decide, "decision": do_decision, "decisions": do_decisions,
    "reserve": do_reserve, "free": do_free, "resources": do_resources,
    "coverage": do_coverage, "brief": do_brief,
}


def main(argv: list[str]) -> int:
    verb = argv[1] if len(argv) > 1 else ""
    try:
        if verb not in VERBS:
            refuse("arguments", "one of " + ", ".join(sorted(VERBS)), verb or "no verb",
                   "name one verb; the module doc has the arguments")
        return VERBS[verb](argv[2:]) or EXIT_DONE
    except Refusal as refusal:
        return emit(refusal)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
