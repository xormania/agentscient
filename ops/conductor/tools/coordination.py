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
    coordination.py who | participants [--role R]
    coordination.py draft TITLE --outcome TEXT [--requirement REF] [--revision SHA]
                              [--depends A-n,..] [--duty TEXT] [--scope TEXT] [--inputs REF]
    coordination.py offer A-n --to WHO
    coordination.py claim A-n --branch B --generation N [--ttl MIN]
    coordination.py release A-n --why TEXT --generation N
    coordination.py reassign A-n --to WHO --why TEXT --generation N
    coordination.py submit A-n --evidence READING --revision SHA --generation N
    coordination.py verify A-n --evidence READING --generation N
    coordination.py return A-n --findings REF --generation N
    coordination.py accept A-n --evidence READING --generation N
    coordination.py reopen A-n --revision SHA --why TEXT --generation N
    coordination.py supersede A-n --by A-m
    coordination.py assignments [--state S] [--to WHO] [--mine] | show A-n|M-n
    coordination.py send --to WHO --purpose P --body TEXT [--assignment A-n]
                         [--decision DC-n] [--reply-to M-n] [--artifact REF]
    coordination.py deliver M-n --ref REF | ack M-n | resolve M-n --evidence READING
    coordination.py withdraw M-n --why TEXT | inbox [--unresolved] | outstanding [--to WHO]
    coordination.py observe A-n --observation TEXT --revision SHA [--execution REC]
                            [--artifact REF] [--requirement REF] [--environment TEXT]
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
    probe TEXT, bound_at TEXT NOT NULL, bound_by INTEGER, bound_for INTEGER);
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
    """A store written before the dispatched-worker binding existed gains
    its two columns here; ALTER ... ADD COLUMN is idempotent under the
    guard and costs one PRAGMA on every open."""
    have = {row["name"] for row in conn.execute("PRAGMA table_info(participants)")}
    for name in ("bound_by", "bound_for"):
        if name not in have:
            conn.execute(f"ALTER TABLE participants ADD COLUMN {name} INTEGER")


def writer():
    conn = machine.connect(create=True)
    conn.executescript(SCHEMA)
    ensure_columns(conn)
    for declared in (ASSIGNMENT, MESSAGE, RESOURCE):
        machine.declare(conn, declared)
    return conn


def reader():
    """The store for a read, or None when there is nothing to read."""
    if not machine.store_path().is_file():
        return None
    conn = machine.connect(create=False)
    conn.executescript(SCHEMA)
    ensure_columns(conn)
    return conn


# -- participants ------------------------------------------------------------

def resolve(conn):
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


# -- participants: verbs -----------------------------------------------------

def do_bind(rest):
    agent = identity()
    _, opts = parse(rest, 0, required=("roles",), optional=("harness", "endpoint", "probe"))
    roles = roles_of(opts["roles"])
    key = session("")
    if not key:
        refuse("session", "a session id in the environment", "unset",
               "run under a harness that sets CLAUDE_CODE_SESSION_ID")
    with writer() as conn:
        row = conn.execute(
            "SELECT id FROM participants WHERE session_id = ?", (key,)
        ).fetchone()
        if row is None:
            cursor = conn.execute(
                "INSERT INTO participants(session_id, agent, harness, roles, endpoint, "
                "probe, bound_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, agent, opts.get("harness"), roles, opts.get("endpoint"),
                 opts.get("probe"), stamp()),
            )
            pid = cursor.lastrowid
        else:
            pid = row["id"]
            conn.execute(
                "UPDATE participants SET agent = ?, harness = ?, roles = ?, "
                "endpoint = ?, probe = ?, bound_at = ? WHERE id = ?",
                (agent, opts.get("harness"), roles, opts.get("endpoint"),
                 opts.get("probe"), stamp(), pid),
            )
    print(f"participant PT-{pid} bound to session {key}")


def do_bind_for(rest):
    """A participant for a session that cannot bind itself.

    A dispatched Codex or Grok worker has no harness session id in its
    environment, so it could hold no participant and every mutation it
    made refused class `participant`. The launcher mints a session id per
    dispatch and sets it as CLAUDE_SESSION_ID, the older key
    instrument.session() already admits. Only a dispatcher may issue one,
    and the binding records who issued it and for which assignment, so a
    participant nobody dispatched is visible as such.
    """
    agent = identity()
    _, opts = parse(
        rest, 0, required=("session", "roles", "for"),
        optional=("harness", "endpoint", "probe"),
    )
    roles = roles_of(opts["roles"])
    key = opts["session"].strip()
    if not key:
        refuse("arguments", "a non-empty --session", repr(opts["session"]),
               "the session id the launcher minted for the worker")
    with writer() as conn:
        part = resolve(conn)
        require_role(part, ("dispatcher",))
        _, aid = parse_id(opts["for"], "A")
        assignment_row(conn, aid)
        row = conn.execute(
            "SELECT id FROM participants WHERE session_id = ?", (key,)
        ).fetchone()
        if row is None:
            cursor = conn.execute(
                "INSERT INTO participants(session_id, agent, harness, roles, endpoint, "
                "probe, bound_at, bound_by, bound_for) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (key, agent, opts.get("harness"), roles, opts.get("endpoint"),
                 opts.get("probe"), stamp(), part["id"], aid),
            )
            pid = cursor.lastrowid
        else:
            pid = row["id"]
            conn.execute(
                "UPDATE participants SET roles = ?, harness = ?, endpoint = ?, "
                "probe = ?, bound_at = ?, bound_by = ?, bound_for = ? WHERE id = ?",
                (roles, opts.get("harness"), opts.get("endpoint"), opts.get("probe"),
                 stamp(), part["id"], aid, pid),
            )
    print(f"participant PT-{pid} bound for session {key} by PT-{part['id']} for A-{aid}")


def do_who(rest):
    parse(rest, 0)
    part = resolve(reader())
    print(f"participant PT-{part['id']} {part['roles']} session {part['session_id']}")


def do_participants(rest):
    _, opts = parse(rest, 0, optional=("role",))
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    with conn:
        rows = conn.execute("SELECT * FROM participants ORDER BY id").fetchall()
    shown = [r for r in rows if not opts.get("role") or opts["role"] in r["roles"].split(",")]
    if not shown:
        print("no participants")
        return EXIT_DONE
    for row in shown:
        issued = (f", bound by PT-{row['bound_by']} for A-{row['bound_for']}"
                  if row["bound_by"] else "")
        print(f"PT-{row['id']} {row['roles']} — {row['agent']} "
              f"session {row['session_id']} harness {row['harness'] or 'unrecorded'}"
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
        part = resolve(conn)
        require_role(part, ("lead", "coordinator"))
        sid = machine.create(conn, ASSIGNMENT, agent)
        conn.execute(
            "INSERT INTO assignments(id, title, outcome, requirement, scope, inputs, "
            "depends, revision, generation, duty, opened_by, opened_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
            (sid, title, opts["outcome"], opts.get("requirement"), opts.get("scope"),
             opts.get("inputs"), opts.get("depends"), opts.get("revision"),
             opts.get("duty"), part["id"], stamp()),
        )
    print(f"assignment A-{sid}")


def do_offer(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("to",))
    _, aid = parse_id(raw, "A")
    with writer() as conn:
        part = resolve(conn)
        require_role(part, ("lead", "coordinator"))
        assignment_row(conn, aid)
        to = recipient_of(conn, opts["to"])

        def gate(_row):
            conn.execute("UPDATE assignments SET recipient = ? WHERE id = ?", (to, aid))

        machine.move(conn, ASSIGNMENT, aid, "offer", agent, note=to, gate=gate)
    print(f"offered A-{aid} to {to}")


def do_claim(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("branch", "generation"), optional=("ttl",))
    _, aid = parse_id(raw, "A")
    branch = opts["branch"]
    ttl_s = int(opts["ttl"]) * 60 if str(opts.get("ttl", "")).isdigit() else None
    require_lock(branch)
    with writer() as conn:
        part = resolve(conn)
        row = assignment_row(conn, aid)
        require_generation(row, opts["generation"])

        def gate(_subject):
            live = assignment_row(conn, aid)
            require_generation(live, opts["generation"])
            if not addressed(part, live["recipient"] or ""):
                refuse("recipient", f"the named recipient {live['recipient'] or 'nobody'} "
                       f"of A-{aid}", f"PT-{part['id']} ({part['roles']})",
                       "the recipient claims it, or it is reassigned first")
            conn.execute(
                "UPDATE assignments SET holder = ?, branch = ? WHERE id = ?",
                (part["id"], branch, aid),
            )

        machine.move(conn, ASSIGNMENT, aid, "claim", agent, note=branch,
                     ttl_s=ttl_s, gate=gate)
    print(f"claimed A-{aid} by PT-{part['id']} on {branch}")


def _hand_back(rest, transition, *, role_gated):
    """release and reassign: the hold goes back and the generation bumps."""
    agent = identity()
    required = ("why", "generation") + (("to",) if role_gated else ())
    (raw,), opts = parse(rest, 1, required=required)
    _, aid = parse_id(raw, "A")
    with writer() as conn:
        part = resolve(conn)
        row = assignment_row(conn, aid)
        require_generation(row, opts["generation"])
        if role_gated:
            require_role(part, ("lead", "coordinator"))
            to = recipient_of(conn, opts["to"])
        else:
            require_holder(part, row)
            to = row["recipient"]

        def gate(_subject):
            live = assignment_row(conn, aid)
            require_generation(live, opts["generation"])
            conn.execute(
                "UPDATE assignments SET generation = generation + 1, holder = NULL, "
                "recipient = ? WHERE id = ?", (to, aid),
            )

        machine.move(conn, ASSIGNMENT, aid, transition, agent,
                     evidence=opts["why"], gate=gate)
    print(f"{transition}ed A-{aid} to {to}; generation {row['generation'] + 1}")


def do_release(rest):
    return _hand_back(rest, "release", role_gated=False)


def do_reassign(rest):
    return _hand_back(rest, "reassign", role_gated=True)


def do_submit(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("evidence", "revision", "generation"))
    _, aid = parse_id(raw, "A")
    evidence = reading(opts["evidence"], "the candidate")
    with writer() as conn:
        part = resolve(conn)
        row = assignment_row(conn, aid)
        require_generation(row, opts["generation"])
        require_holder(part, row)
        if row["revision"] and opts["revision"] != row["revision"]:
            refuse("revision", f"the applicable revision {row['revision']} of A-{aid}",
                   opts["revision"], "submit against the applicable revision, or reopen it")

        def gate(_subject):
            live = assignment_row(conn, aid)
            require_generation(live, opts["generation"])
            conn.execute(
                "UPDATE assignments SET submitted_by = ?, revision = ? WHERE id = ?",
                (part["id"], opts["revision"], aid),
            )

        machine.move(conn, ASSIGNMENT, aid, "submit", agent, evidence=evidence, gate=gate)
    print(f"submitted A-{aid} at {opts['revision']}")


def do_verify(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("evidence", "generation"))
    _, aid = parse_id(raw, "A")
    evidence = reading(opts["evidence"], "the verification")
    with writer() as conn:
        part = resolve(conn)
        row = assignment_row(conn, aid)
        require_generation(row, opts["generation"])
        require_role(part, ("verifier", "lead"))
        not_the_producer(part, row, "verifies")
        if row["revision"] and evidence != row["revision"]:
            refuse("revision", f"a reading of the applicable revision {row['revision']} "
                   f"of A-{aid}", evidence,
                   "verify the candidate that was submitted, or reopen the assignment")

        def gate(_subject):
            live = assignment_row(conn, aid)
            require_generation(live, opts["generation"])
            conn.execute("UPDATE assignments SET verified_by = ? WHERE id = ?",
                         (part["id"], aid))

        machine.move(conn, ASSIGNMENT, aid, "verify", agent, evidence=evidence, gate=gate)
    print(f"verified A-{aid} by PT-{part['id']}")


def do_return(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("findings", "generation"))
    _, aid = parse_id(raw, "A")
    with writer() as conn:
        part = resolve(conn)
        row = assignment_row(conn, aid)
        require_generation(row, opts["generation"])
        require_role(part, ("verifier", "lead"))
        machine.move(conn, ASSIGNMENT, aid, "return", agent, evidence=opts["findings"])
    print(f"returned A-{aid} to PT-{row['holder']}")


def do_accept(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("evidence", "generation"))
    _, aid = parse_id(raw, "A")
    evidence = reading(opts["evidence"], "the acceptance")
    with writer() as conn:
        part = resolve(conn)
        row = assignment_row(conn, aid)
        require_generation(row, opts["generation"])
        require_role(part, ("lead",))
        not_the_producer(part, row, "accepts")

        def gate(_subject):
            live = assignment_row(conn, aid)
            require_generation(live, opts["generation"])
            conn.execute("UPDATE assignments SET accepted_by = ? WHERE id = ?",
                         (part["id"], aid))

        machine.move(conn, ASSIGNMENT, aid, "accept", agent, evidence=evidence, gate=gate)
    print(f"accepted A-{aid} by PT-{part['id']}")


def do_reopen(rest):
    """A changed candidate: the observations go stale and keep their scope."""
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("revision", "why", "generation"))
    _, aid = parse_id(raw, "A")
    with writer() as conn:
        part = resolve(conn)
        row = assignment_row(conn, aid)
        require_generation(row, opts["generation"])
        require_role(part, ("lead", "coordinator"))

        def gate(_subject):
            live = assignment_row(conn, aid)
            require_generation(live, opts["generation"])
            conn.execute(
                "UPDATE assignments SET generation = generation + 1, revision = ?, "
                "verified_by = NULL WHERE id = ?", (opts["revision"], aid),
            )
            conn.execute(
                "UPDATE observations SET applicability = 'stale', stale_reason = ? "
                "WHERE assignment = ? AND applicability = 'current'",
                (f"the candidate moved to {opts['revision']}: {opts['why']}", aid),
            )

        machine.move(conn, ASSIGNMENT, aid, "reopen", agent,
                     evidence=opts["revision"], gate=gate)
    print(f"reopened A-{aid} at {opts['revision']}; generation {row['generation'] + 1}")


def do_supersede(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("by",))
    _, aid = parse_id(raw, "A")
    _, newer = parse_id(opts["by"], "A")
    with writer() as conn:
        part = resolve(conn)
        require_role(part, ("lead", "coordinator"))
        assignment_row(conn, aid)
        assignment_row(conn, newer)

        def gate(_subject):
            conn.execute("UPDATE assignments SET superseded_by = ? WHERE id = ?", (newer, aid))

        machine.move(conn, ASSIGNMENT, aid, "supersede", agent,
                     evidence=f"A-{newer}", gate=gate)
    print(f"superseded A-{aid} by A-{newer}")


def assignment_line(row) -> str:
    who = f"PT-{row['holder']}" if row["holder"] else (row["recipient"] or "nobody")
    return (f"A-{row['id']} {row['title']} — {row['place']}, {who}, "
            f"generation {row['generation']}, revision {row['revision'] or 'none'}")


def do_assignments(rest):
    _, opts = parse(rest, 0, optional=("state", "to"), flags=("mine",))
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    with conn:
        rows = conn.execute(
            "SELECT a.*, s.place FROM assignments a JOIN subjects s ON s.id = a.id "
            "ORDER BY a.id"
        ).fetchall()
        mine = resolve(conn)["id"] if opts.get("mine") else None
    shown = [
        row for row in rows
        if (not opts.get("state") or row["place"] == opts["state"])
        and (not opts.get("to") or row["recipient"] == opts["to"])
        and (mine is None or row["holder"] == mine)
    ]
    if not shown:
        print("no assignments")
        return EXIT_DONE
    for row in shown:
        print(assignment_line(row))
    return EXIT_DONE


# -- messages: verbs ---------------------------------------------------------

def do_send(rest):
    agent = identity()
    _, opts = parse(
        rest, 0, required=("to", "purpose", "body"),
        optional=("assignment", "decision", "reply-to", "artifact"),
    )
    if opts["purpose"] not in PURPOSES:
        refuse("arguments", "a purpose of " + ", ".join(PURPOSES), opts["purpose"],
               "an inform carries no obligation; a request and a finding do")
    with writer() as conn:
        part = resolve(conn)
        to = recipient_of(conn, opts["to"])
        aid = parse_id(opts["assignment"], "A")[1] if opts.get("assignment") else None
        did = parse_id(opts["decision"], "DC")[1] if opts.get("decision") else None
        reply = parse_id(opts["reply-to"], "M")[1] if opts.get("reply-to") else None
        if aid is not None:
            assignment_row(conn, aid)
        sid = machine.create(conn, MESSAGE, agent)
        conn.execute(
            "INSERT INTO messages(id, sender, recipient, purpose, body, artifact, "
            "assignment, decision, reply_to, queued_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, part["id"], to, opts["purpose"], opts["body"], opts.get("artifact"),
             aid, did, reply, stamp()),
        )
    print(f"message M-{sid} queued")


def do_deliver(rest):
    """The transport's own receipt. The core never sends; it records."""
    identity()
    (raw,), opts = parse(rest, 1, required=("ref",))
    _, mid = parse_id(raw, "M")
    with writer() as conn:
        part = resolve(conn)
        row = message_row(conn, mid)
        if row["sender"] != part["id"] and not addressed(part, row["recipient"]):
            refuse("recipient", f"the sender PT-{row['sender']} or the recipient "
                   f"{row['recipient']} of M-{mid}", f"PT-{part['id']}",
                   "the route that carried it records its receipt")
        conn.execute("UPDATE messages SET delivered_at = ?, delivery_ref = ? WHERE id = ?",
                     (stamp(), opts["ref"], mid))
    print(f"delivered M-{mid} ref {opts['ref']}")


def do_ack(rest):
    identity()
    (raw,), _ = parse(rest, 1)
    _, mid = parse_id(raw, "M")
    with writer() as conn:
        part = resolve(conn)
        row = message_row(conn, mid)
        if not addressed(part, row["recipient"]):
            refuse("recipient", f"the recipient {row['recipient']} of M-{mid}",
                   f"PT-{part['id']} ({part['roles']})",
                   "the recipient acknowledges its own message")
        conn.execute("UPDATE messages SET acked_at = ?, acked_by = ? WHERE id = ?",
                     (stamp(), part["id"], mid))
    print(f"acknowledged M-{mid} by PT-{part['id']}; not resolved")


def do_resolve(rest):
    """Resolution is a place, moved by the obligation's holder, never by
    the acknowledgment (AC-04)."""
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("evidence",))
    _, mid = parse_id(raw, "M")
    evidence = reading(opts["evidence"], "the resolution")
    with writer() as conn:
        part = resolve(conn)
        row = message_row(conn, mid)
        allowed = addressed(part, row["recipient"])
        if not allowed and row["assignment"] is not None:
            allowed = assignment_row(conn, row["assignment"])["holder"] == part["id"]
        if not allowed:
            refuse("recipient", f"the recipient {row['recipient']} of M-{mid}, "
                   "or the holder of its assignment", f"PT-{part['id']} ({part['roles']})",
                   "the participant that owes the answer resolves it")
        machine.move(conn, MESSAGE, mid, "resolve", agent, evidence=evidence)
    print(f"resolved M-{mid}: {evidence}")


def do_withdraw(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("why",))
    _, mid = parse_id(raw, "M")
    with writer() as conn:
        part = resolve(conn)
        row = message_row(conn, mid)
        if row["sender"] != part["id"]:
            refuse("recipient", f"the sender PT-{row['sender']} of M-{mid}",
                   f"PT-{part['id']}", "the sender withdraws its own message")
        machine.move(conn, MESSAGE, mid, "withdraw", agent, evidence=opts["why"])
    print(f"withdrew M-{mid}")


def message_line(row) -> str:
    tail = f" — {row['place']}" if row["place"] != "open" else ""
    return (f"M-{row['id']} {row['purpose']} from PT-{row['sender']} to "
            f"{row['recipient']}: {row['body']}{tail}")


def do_inbox(rest):
    _, opts = parse(rest, 0, flags=("unresolved",))
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    with conn:
        part = resolve(conn)
        rows = conn.execute(
            "SELECT m.*, s.place FROM messages m JOIN subjects s ON s.id = m.id "
            "ORDER BY m.id"
        ).fetchall()
    shown = [row for row in rows if addressed(part, row["recipient"])
             and (not opts.get("unresolved") or row["place"] == "open")]
    if not shown:
        print("no messages")
        return EXIT_DONE
    for row in shown:
        print(message_line(row))
    return EXIT_DONE


def do_outstanding(rest):
    """An obligation stays here until it is resolved; an ack does not lift it."""
    _, opts = parse(rest, 0, optional=("to",))
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    with conn:
        rows = conn.execute(
            "SELECT m.*, s.place FROM messages m JOIN subjects s ON s.id = m.id "
            "WHERE s.place = 'open' ORDER BY m.id"
        ).fetchall()
    shown = [row for row in rows if row["purpose"] in OBLIGATIONS
             and (not opts.get("to") or row["recipient"] == opts["to"])]
    if not shown:
        print("none outstanding")
        return EXIT_DONE
    for row in shown:
        seen = f", acknowledged {row['acked_at']}" if row["acked_at"] else ", not acknowledged"
        print(message_line(row) + seen)
    return EXIT_DONE


# -- observations, decisions, resources --------------------------------------

def do_observe(rest):
    identity()
    (raw,), opts = parse(
        rest, 1, required=("observation", "revision"),
        optional=("execution", "artifact", "requirement", "environment"),
    )
    _, aid = parse_id(raw, "A")
    with writer() as conn:
        part = resolve(conn)
        assignment_row(conn, aid)
        cursor = conn.execute(
            "INSERT INTO observations(assignment, producer, requirement, execution, "
            "revision, environment, observation, artifact, applicability, at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'current', ?)",
            (aid, part["id"], opts.get("requirement"), opts.get("execution"),
             opts["revision"], opts.get("environment"), opts["observation"],
             opts.get("artifact"), stamp()),
        )
    print(f"observation E-{cursor.lastrowid}")


def do_observations(rest):
    (raw,), opts = parse(rest, 1, flags=("all",))
    _, aid = parse_id(raw, "A")
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    with conn:
        assignment_row(conn, aid)
        rows = conn.execute(
            "SELECT * FROM observations WHERE assignment = ? ORDER BY id", (aid,)
        ).fetchall()
    shown = [row for row in rows if opts.get("all") or row["applicability"] == "current"]
    if not shown:
        print("no observations")
        return EXIT_DONE
    for row in shown:
        mark = "" if row["applicability"] == "current" else f" [stale: {row['stale_reason']}]"
        where = f" ({row['execution']})" if row["execution"] else ""
        print(f"E-{row['id']} PT-{row['producer']} {row['revision']} — "
              f"{row['observation']}{where}{mark}")
    return EXIT_DONE


def do_ask(rest):
    identity()
    _, opts = parse(rest, 0, required=("question", "alternatives"), optional=("assignment",))
    with writer() as conn:
        part = resolve(conn)
        aid = parse_id(opts["assignment"], "A")[1] if opts.get("assignment") else None
        if aid is not None:
            assignment_row(conn, aid)
        cursor = conn.execute(
            "INSERT INTO decisions(asked_by, question, alternatives, assignment, asked_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (part["id"], opts["question"], opts["alternatives"], aid, stamp()),
        )
    print(f"decision DC-{cursor.lastrowid}")


def do_answer(rest):
    identity()
    (raw,), opts = parse(rest, 1, optional=("counter", "unknowns", "consequence"))
    _, did = parse_id(raw, "DC")
    if not opts:
        refuse("arguments", "at least one of --counter, --unknowns, --consequence",
               "none", "say what the brief is missing")
    with writer() as conn:
        resolve(conn)
        decision_row(conn, did)
        for key, sql in (
            ("counter", "UPDATE decisions SET counter = ? WHERE id = ?"),
            ("unknowns", "UPDATE decisions SET unknowns = ? WHERE id = ?"),
            ("consequence", "UPDATE decisions SET consequence = ? WHERE id = ?"),
        ):
            if opts.get(key):
                conn.execute(sql, (opts[key], did))
    print(f"answered DC-{did}")


def do_decide(rest):
    identity()
    (raw,), opts = parse(rest, 1, required=("choice", "rationale"))
    _, did = parse_id(raw, "DC")
    with writer() as conn:
        part = resolve(conn)
        require_role(part, ("lead",))
        decision_row(conn, did)
        conn.execute(
            "UPDATE decisions SET choice = ?, rationale = ?, decided_by = ?, "
            "decided_at = ? WHERE id = ?",
            (opts["choice"], opts["rationale"], part["id"], stamp(), did),
        )
    print(f"decided DC-{did}: {opts['choice']}")


def do_decision(rest):
    """The bounded brief: what is missing is named, never passed over."""
    (raw,), _ = parse(rest, 1)
    _, did = parse_id(raw, "DC")
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    with conn:
        row = decision_row(conn, did)
        observations = conn.execute(
            "SELECT * FROM observations WHERE assignment IS ? AND applicability = 'current' "
            "ORDER BY id", (row["assignment"],)
        ).fetchall() if row["assignment"] else []
    print(f"DC-{did} {row['question']}")
    print(f"alternatives: {row['alternatives']}")
    for label, key in (("counterevidence", "counter"), ("unknowns", "unknowns"),
                       ("consequence", "consequence")):
        print(f"{label}: {row[key] or 'a declared gap, not a pass'}")
    print(f"observations: {len(observations)} current")
    if row["decided_at"]:
        print(f"decided by PT-{row['decided_by']} at {row['decided_at']}: "
              f"{row['choice']} — {row['rationale']}")
    else:
        print("undecided")
    return EXIT_DONE


def do_decisions(rest):
    _, opts = parse(rest, 0, flags=("open",))
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    with conn:
        rows = conn.execute("SELECT * FROM decisions ORDER BY id").fetchall()
    shown = [row for row in rows if not opts.get("open") or row["decided_at"] is None]
    if not shown:
        print("no decisions")
        return EXIT_DONE
    for row in shown:
        state = f"{row['choice']}" if row["decided_at"] else "undecided"
        print(f"DC-{row['id']} {row['question']} — {state}")
    return EXIT_DONE


def do_reserve(rest):
    agent = identity()
    (name,), opts = parse(rest, 1, required=("for",), optional=("ttl",))
    _, aid = parse_id(opts["for"], "A")
    ttl_s = int(opts["ttl"]) * 60 if str(opts.get("ttl", "")).isdigit() else None
    with writer() as conn:
        part = resolve(conn)
        assignment_row(conn, aid)
        row = conn.execute("SELECT * FROM resources WHERE name = ?", (name,)).fetchone()
        if row is None:
            sid = machine.create(conn, RESOURCE, agent)
            conn.execute("INSERT INTO resources(id, name, assignment) VALUES (?, ?, ?)",
                         (sid, name, aid))
        else:
            sid = row["id"]

        def gate(_subject):
            conn.execute("UPDATE resources SET assignment = ?, holder = ? WHERE id = ?",
                         (aid, part["id"], sid))

        machine.move(conn, RESOURCE, sid, "reserve", agent, note=f"A-{aid}",
                     ttl_s=ttl_s, gate=gate)
    print(f"reserved {name} for A-{aid} by PT-{part['id']}")


def do_free(rest):
    agent = identity()
    (name,), opts = parse(rest, 1, required=("why",))
    with writer() as conn:
        part = resolve(conn)
        row = conn.execute("SELECT * FROM resources WHERE name = ?", (name,)).fetchone()
        if row is None:
            refuse("unknown", "a reserved resource", name, "a name printed by resources")
        previous = row["holder"]

        def gate(subject):
            """A lapsed lease is evidence a reservation ran out, never proof
            the previous process stopped: the reconciliation is printed."""
            if previous != part["id"] and not machine.lapsed(subject):
                refuse("holder", f"the holder PT-{previous} of {name}",
                       f"PT-{part['id']}",
                       "the holder frees it, or anyone once the lease lapses")
            conn.execute("UPDATE resources SET holder = NULL WHERE id = ?", (row["id"],))

        machine.move(conn, RESOURCE, row["id"], "free", agent,
                     evidence=opts["why"], gate=gate)
    note = "" if previous == part["id"] else f"; PT-{previous}'s run is not reconciled"
    print(f"freed {name}{note}")


def do_resources(rest):
    parse(rest, 0)
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    with conn:
        rows = conn.execute(
            "SELECT r.*, s.place, s.held_since, s.ttl_s FROM resources r "
            "JOIN subjects s ON s.id = r.id ORDER BY r.id"
        ).fetchall()
    if not rows:
        print("no resources")
        return EXIT_DONE
    for row in rows:
        who = f"PT-{row['holder']}" if row["holder"] else "free"
        print(f"R-{row['id']} {row['name']} — {row['place']}, {who}, "
              f"A-{row['assignment'] or 0}")
    return EXIT_DONE


# -- the joined views --------------------------------------------------------

def do_show(rest):
    (raw,), _ = parse(rest, 1)
    kind, number = parse_id(raw, ("A", "M", "DC"))
    if kind == "DC":
        return do_decision([raw])
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    if kind == "M":
        with conn:
            row = message_row(conn, number)
        print(message_line(row))
        print(f"queued {row['queued_at']}")
        if row["delivered_at"]:
            print(f"delivered {row['delivered_at']} ref {row['delivery_ref']}")
        if row["acked_at"]:
            print(f"acknowledged {row['acked_at']} by PT-{row['acked_by']}")
        return EXIT_DONE
    with conn:
        row = assignment_row(conn, number)
        marking = machine.history(conn, ASSIGNMENT, number)
        counts = conn.execute(
            "SELECT applicability, COUNT(*) AS n FROM observations WHERE assignment = ? "
            "GROUP BY applicability", (number,)
        ).fetchall()
    print(assignment_line(row))
    print(f"outcome: {row['outcome']}")
    print(f"requirement: {row['requirement'] or 'none'}; branch: {row['branch'] or 'none'}; "
          f"depends: {row['depends'] or 'none'}")
    tally = {r["applicability"]: r["n"] for r in counts}
    print(f"observations: {tally.get('current', 0)} current, {tally.get('stale', 0)} stale")
    print("marking:")
    for entry in marking:
        print(f"  {machine.history_line(entry)}")
    return EXIT_DONE


def do_coverage(rest):
    """requirement -> assignment -> candidate -> observation -> verification
    -> acceptance or the gap, named."""
    _, opts = parse(rest, 0, optional=("requirement",))
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    with conn:
        rows = conn.execute(
            "SELECT a.*, s.place FROM assignments a JOIN subjects s ON s.id = a.id "
            "ORDER BY a.id"
        ).fetchall()
        tallies = {
            row["id"]: conn.execute(
                "SELECT COUNT(*) AS n FROM observations WHERE assignment = ? "
                "AND applicability = 'current'", (row["id"],)
            ).fetchone()["n"] for row in rows
        }
    shown = [r for r in rows
             if not opts.get("requirement") or r["requirement"] == opts["requirement"]]
    if not shown:
        print("no assignments")
        return EXIT_DONE
    for row in shown:
        if row["place"] == "accepted":
            close = f"accepted by PT-{row['accepted_by']}"
        elif row["verified_by"]:
            close = f"verified by PT-{row['verified_by']}, acceptance gap"
        else:
            close = "verification gap"
        print(f"{row['requirement'] or 'requirement unstated'} → A-{row['id']} "
              f"{row['title']} → candidate {row['revision'] or 'none'} → "
              f"{tallies[row['id']]} observation(s) → {close}")
    return EXIT_DONE


def do_brief(rest):
    """What a restarted or compacted participant reads to recover its
    obligations (AC-12): held work, unresolved inbox, open decisions."""
    parse(rest, 0)
    conn = reader()
    if conn is None:
        print("no store")
        return EXIT_DONE
    with conn:
        part = resolve(conn)
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
    print(f"brief for PT-{part['id']} {part['roles']}")
    print("assignments held:")
    for row in held:
        print(f"  {assignment_line(row)}")
    if not held:
        print("  none")
    print("inbox unresolved:")
    mine = [row for row in messages if addressed(part, row["recipient"])]
    for row in mine:
        print(f"  {message_line(row)}")
    if not mine:
        print("  none")
    print(f"decisions open: {len(decisions)}")
    print(f"observations of mine gone stale: {stale}")
    return EXIT_DONE


VERBS = {
    "bind": do_bind, "bind-for": do_bind_for, "who": do_who,
    "participants": do_participants,
    "draft": do_draft, "offer": do_offer, "claim": do_claim,
    "release": do_release, "reassign": do_reassign, "submit": do_submit,
    "verify": do_verify, "return": do_return, "accept": do_accept,
    "reopen": do_reopen, "supersede": do_supersede, "assignments": do_assignments,
    "show": do_show, "send": do_send, "deliver": do_deliver, "ack": do_ack,
    "resolve": do_resolve, "withdraw": do_withdraw, "inbox": do_inbox,
    "outstanding": do_outstanding, "observe": do_observe,
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
