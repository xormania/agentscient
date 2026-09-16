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


# -- what a core function returns --------------------------------------------

def participant_dict(row) -> dict:
    return {
        "participant": f"PT-{row['id']}", "id": row["id"], "roles": row["roles"],
        "agent": row["agent"], "session": row["session_id"],
        "harness": row["harness"], "endpoint": row["endpoint"],
        "bound_by": f"PT-{row['bound_by']}" if row["bound_by"] else None,
        "bound_for": f"A-{row['bound_for']}" if row["bound_for"] else None,
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


def no_store(**rest) -> dict:
    """Could not look, said as a marker: a read with no store behind it
    returns this and never an empty list dressed as an answer
    (docs/wire.md, absence discipline)."""
    return {"store": "absent", **rest}


# -- the core: one function per verb, keyed by the wire name in CORE ----------

def core_bind(conn, part, *, agent, session_id, roles, harness=None,
              endpoint=None, probe=None) -> dict:
    """This session's own participant. `part` is None here by construction:
    binding is how a session comes to have one."""
    named = roles_of(roles)
    key = (session_id or "").strip()
    if not key:
        refuse("session", "a session id in the environment", "unset",
               "run under a harness that sets CLAUDE_CODE_SESSION_ID")
    row = conn.execute(
        "SELECT id FROM participants WHERE session_id = ?", (key,)
    ).fetchone()
    if row is None:
        cursor = conn.execute(
            "INSERT INTO participants(session_id, agent, harness, roles, endpoint, "
            "probe, bound_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key, agent, harness, named, endpoint, probe, stamp()),
        )
        pid = cursor.lastrowid
    else:
        pid = row["id"]
        conn.execute(
            "UPDATE participants SET agent = ?, harness = ?, roles = ?, "
            "endpoint = ?, probe = ?, bound_at = ? WHERE id = ?",
            (agent, harness, named, endpoint, probe, stamp(), pid),
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
    require_role(part, ("dispatcher",))
    named = roles_of(roles)
    key = (session_id or "").strip()
    if not key:
        refuse("arguments", "a non-empty session id", repr(session_id),
               "the session id the launcher minted for the worker")
    _, aid = parse_id(assignment, "A")
    assignment_row(conn, aid)
    row = conn.execute(
        "SELECT id FROM participants WHERE session_id = ?", (key,)
    ).fetchone()
    if row is None:
        cursor = conn.execute(
            "INSERT INTO participants(session_id, agent, harness, roles, endpoint, "
            "probe, bound_at, bound_by, bound_for) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (key, agent, harness, named, endpoint, probe, stamp(), part["id"], aid),
        )
        pid = cursor.lastrowid
    else:
        pid = row["id"]
        conn.execute(
            "UPDATE participants SET roles = ?, harness = ?, endpoint = ?, "
            "probe = ?, bound_at = ?, bound_by = ?, bound_for = ? WHERE id = ?",
            (named, harness, endpoint, probe, stamp(), part["id"], aid, pid),
        )
    return participant_dict(participant_row(conn, pid))


def core_who(conn, part) -> dict:
    return participant_dict(part)


def core_participants(conn, part, *, role=None) -> dict:
    if conn is None:
        return no_store(participants=[])
    rows = conn.execute("SELECT * FROM participants ORDER BY id").fetchall()
    shown = [r for r in rows if not role or role in r["roles"].split(",")]
    return {"participants": [participant_dict(r) for r in shown]}


def core_draft(conn, part, *, agent, title, outcome, requirement=None, revision=None,
               depends=None, duty=None, scope=None, inputs=None) -> dict:
    require_role(part, ("lead", "coordinator"))
    sid = machine.create(conn, ASSIGNMENT, agent)
    conn.execute(
        "INSERT INTO assignments(id, title, outcome, requirement, scope, inputs, "
        "depends, revision, generation, duty, opened_by, opened_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
        (sid, title, outcome, requirement, scope, inputs, depends, revision,
         duty, part["id"], stamp()),
    )
    return assignment_dict(assignment_row(conn, sid))


def core_offer(conn, part, *, agent, assignment, to) -> dict:
    require_role(part, ("lead", "coordinator"))
    _, aid = parse_id(assignment, "A")
    assignment_row(conn, aid)
    recipient = recipient_of(conn, to)

    def gate(_subject):
        conn.execute("UPDATE assignments SET recipient = ? WHERE id = ?", (recipient, aid))

    machine.move(conn, ASSIGNMENT, aid, "offer", agent, note=recipient, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_claim(conn, part, *, agent, assignment, branch, generation, ttl=None) -> dict:
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

    machine.move(conn, ASSIGNMENT, aid, "claim", agent, note=branch,
                 ttl_s=ttl_s, gate=gate)
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
        require_holder(part, row)
        recipient = row["recipient"]

    def gate(_subject):
        live = assignment_row(conn, aid)
        require_generation(live, generation)
        conn.execute(
            "UPDATE assignments SET generation = generation + 1, holder = NULL, "
            "recipient = ? WHERE id = ?", (recipient, aid),
        )

    machine.move(conn, ASSIGNMENT, aid, transition, agent, evidence=why, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_release(conn, part, *, agent, assignment, why, generation) -> dict:
    return _hand_back(conn, part, agent=agent, assignment=assignment, why=why,
                      generation=generation, transition="release")


def core_reassign(conn, part, *, agent, assignment, to, why, generation) -> dict:
    return _hand_back(conn, part, agent=agent, assignment=assignment, why=why,
                      generation=generation, transition="reassign", to=to)


def core_submit(conn, part, *, agent, assignment, evidence, revision, generation) -> dict:
    _, aid = parse_id(assignment, "A")
    evidence = reading(evidence, "the candidate")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    require_holder(part, row)
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

    machine.move(conn, ASSIGNMENT, aid, "submit", agent, evidence=evidence, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_verify(conn, part, *, agent, assignment, evidence, generation) -> dict:
    _, aid = parse_id(assignment, "A")
    evidence = reading(evidence, "the verification")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    require_role(part, ("verifier", "lead"))
    not_the_producer(part, row, "verifies")
    if row["revision"] and evidence != row["revision"]:
        refuse("revision", f"a reading of the applicable revision {row['revision']} "
               f"of A-{aid}", evidence,
               "verify the candidate that was submitted, or reopen the assignment")

    def gate(_subject):
        live = assignment_row(conn, aid)
        require_generation(live, generation)
        conn.execute("UPDATE assignments SET verified_by = ? WHERE id = ?",
                     (part["id"], aid))

    machine.move(conn, ASSIGNMENT, aid, "verify", agent, evidence=evidence, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_return(conn, part, *, agent, assignment, findings, generation) -> dict:
    _, aid = parse_id(assignment, "A")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    require_role(part, ("verifier", "lead"))
    machine.move(conn, ASSIGNMENT, aid, "return", agent, evidence=findings)
    return assignment_dict(assignment_row(conn, aid))


def core_accept(conn, part, *, agent, assignment, evidence, generation) -> dict:
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

    machine.move(conn, ASSIGNMENT, aid, "accept", agent, evidence=evidence, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_reopen(conn, part, *, agent, assignment, revision, why, generation) -> dict:
    """A changed candidate: the observations go stale and keep their scope."""
    _, aid = parse_id(assignment, "A")
    row = assignment_row(conn, aid)
    require_generation(row, generation)
    require_role(part, ("lead", "coordinator"))

    def gate(_subject):
        live = assignment_row(conn, aid)
        require_generation(live, generation)
        conn.execute(
            "UPDATE assignments SET generation = generation + 1, revision = ?, "
            "verified_by = NULL WHERE id = ?", (revision, aid),
        )
        conn.execute(
            "UPDATE observations SET applicability = 'stale', stale_reason = ? "
            "WHERE assignment = ? AND applicability = 'current'",
            (f"the candidate moved to {revision}: {why}", aid),
        )

    machine.move(conn, ASSIGNMENT, aid, "reopen", agent, evidence=revision, gate=gate)
    return assignment_dict(assignment_row(conn, aid))


def core_supersede(conn, part, *, agent, assignment, by) -> dict:
    require_role(part, ("lead", "coordinator"))
    _, aid = parse_id(assignment, "A")
    _, newer = parse_id(by, "A")
    assignment_row(conn, aid)
    assignment_row(conn, newer)

    def gate(_subject):
        conn.execute("UPDATE assignments SET superseded_by = ? WHERE id = ?", (newer, aid))

    machine.move(conn, ASSIGNMENT, aid, "supersede", agent,
                 evidence=f"A-{newer}", gate=gate)
    shown = assignment_dict(assignment_row(conn, aid))
    shown["superseded_by"] = f"A-{newer}"
    return shown


def core_assignments(conn, part, *, state=None, to=None) -> dict:
    """`part` filters to what that participant holds; None shows every row."""
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
    if purpose not in PURPOSES:
        refuse("arguments", "a purpose of " + ", ".join(PURPOSES), purpose,
               "an inform carries no obligation; a request and a finding do")
    recipient = recipient_of(conn, to)
    aid = parse_id(assignment, "A")[1] if assignment else None
    did = parse_id(decision, "DC")[1] if decision else None
    reply = parse_id(reply_to, "M")[1] if reply_to else None
    if aid is not None:
        assignment_row(conn, aid)
    sid = machine.create(conn, MESSAGE, agent)
    conn.execute(
        "INSERT INTO messages(id, sender, recipient, purpose, body, artifact, "
        "assignment, decision, reply_to, queued_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sid, part["id"], recipient, purpose, body, artifact, aid, did, reply, stamp()),
    )
    return message_dict(message_row(conn, sid))


def core_deliver(conn, part, *, message, ref) -> dict:
    """The transport's own receipt. The core never sends; it records."""
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
    machine.move(conn, MESSAGE, mid, "resolve", agent, evidence=evidence)
    shown = message_dict(message_row(conn, mid))
    shown["evidence"] = evidence
    return shown


def core_withdraw(conn, part, *, agent, message, why) -> dict:
    _, mid = parse_id(message, "M")
    row = message_row(conn, mid)
    if row["sender"] != part["id"]:
        refuse("recipient", f"the sender PT-{row['sender']} of M-{mid}",
               f"PT-{part['id']}", "the sender withdraws its own message")
    machine.move(conn, MESSAGE, mid, "withdraw", agent, evidence=why)
    return message_dict(message_row(conn, mid))


def core_inbox(conn, part, *, unresolved=False) -> dict:
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
    if conn is None:
        return no_store(outstanding=[])
    rows = conn.execute(
        "SELECT m.*, s.place FROM messages m JOIN subjects s ON s.id = m.id "
        "WHERE s.place = 'open' ORDER BY m.id"
    ).fetchall()
    shown = [row for row in rows if row["purpose"] in OBLIGATIONS
             and (not to or row["recipient"] == to)]
    return {"outstanding": [message_dict(row) for row in shown]}


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
    _, aid = parse_id(assignment, "A")
    if not str(generation).isdigit():
        refuse("arguments", "--generation as a whole number", str(generation),
               "the generation printed by show")
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = assignment_row(conn, aid)
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
    if conn is None:
        return no_store(decisions=[])
    rows = conn.execute("SELECT * FROM decisions ORDER BY id").fetchall()
    shown = [row for row in rows if not undecided_only or row["decided_at"] is None]
    return {"decisions": [decision_dict(row) for row in shown]}


def core_reserve(conn, part, *, agent, name, assignment, ttl=None) -> dict:
    _, aid = parse_id(assignment, "A")
    ttl_s = int(ttl) * 60 if str(ttl or "").isdigit() else None
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
    return {"resource": f"R-{sid}", "id": sid, "name": name, "place": "held",
            "assignment": f"A-{aid}", "assignment_id": aid,
            "holder": f"PT-{part['id']}"}


def core_free(conn, part, *, agent, name, why) -> dict:
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

    machine.move(conn, RESOURCE, row["id"], "free", agent, evidence=why, gate=gate)
    return {"resource": f"R-{row['id']}", "id": row["id"], "name": name,
            "place": "free", "previous_holder": f"PT-{previous}",
            "reconciled": previous == part["id"]}


def core_resources(conn, part) -> dict:
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
    "bind": core_bind, "bind-for": core_bind_for, "who": core_who,
    "participants": core_participants,
    "draft": core_draft, "offer": core_offer, "claim": core_claim,
    "release": core_release, "reassign": core_reassign, "submit": core_submit,
    "verify": core_verify, "return": core_return, "accept": core_accept,
    "reopen": core_reopen, "supersede": core_supersede,
    "assignments": core_assignments,
    "show": core_show, "send": core_send, "deliver": core_deliver, "ack": core_ack,
    "resolve": core_resolve, "withdraw": core_withdraw, "inbox": core_inbox,
    "outstanding": core_outstanding, "observe": core_observe,
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
        shown = core_bind(conn, None, agent=agent, session_id=session(""),
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
        shown = core_bind_for(conn, bound_participant(conn), agent=agent,
                              session_id=opts["session"], roles=opts["roles"],
                              assignment=opts["for"], harness=opts.get("harness"),
                              endpoint=opts.get("endpoint"), probe=opts.get("probe"))
    print(f"participant {shown['participant']} bound for session {shown['session']} "
          f"by {shown['bound_by']} for {shown['bound_for']}")


def do_who(rest):
    parse(rest, 0)
    shown = core_who(None, bound_participant(reader()))
    print(f"participant {shown['participant']} {shown['roles']} "
          f"session {shown['session']}")


def do_participants(rest):
    _, opts = parse(rest, 0, optional=("role",))
    shown = core_participants(reader(), None, role=opts.get("role"))
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
        shown = core_draft(conn, bound_participant(conn), agent=agent, title=title,
                           outcome=opts["outcome"], requirement=opts.get("requirement"),
                           revision=opts.get("revision"), depends=opts.get("depends"),
                           duty=opts.get("duty"), scope=opts.get("scope"),
                           inputs=opts.get("inputs"))
    print(f"assignment {shown['assignment']}")


def do_offer(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("to",))
    with writer() as conn:
        shown = core_offer(conn, bound_participant(conn), agent=agent, assignment=raw,
                           to=opts["to"])
    print(f"offered {shown['assignment']} to {shown['recipient']}")


def do_claim(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("branch", "generation"), optional=("ttl",))
    with writer() as conn:
        shown = core_claim(conn, bound_participant(conn), agent=agent, assignment=raw,
                           branch=opts["branch"], generation=opts["generation"],
                           ttl=opts.get("ttl"))
    print(f"claimed {shown['assignment']} by {shown['holder']} on {shown['branch']}")


def do_release(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("why", "generation"))
    with writer() as conn:
        shown = core_release(conn, bound_participant(conn), agent=agent, assignment=raw,
                             why=opts["why"], generation=opts["generation"])
    print(f"released {shown['assignment']} to {shown['recipient']}; "
          f"generation {shown['generation']}")


def do_reassign(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("to", "why", "generation"))
    with writer() as conn:
        shown = core_reassign(conn, bound_participant(conn), agent=agent, assignment=raw,
                              to=opts["to"], why=opts["why"],
                              generation=opts["generation"])
    print(f"reassigned {shown['assignment']} to {shown['recipient']}; "
          f"generation {shown['generation']}")


def do_submit(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("evidence", "revision", "generation"))
    with writer() as conn:
        shown = core_submit(conn, bound_participant(conn), agent=agent, assignment=raw,
                            evidence=opts["evidence"], revision=opts["revision"],
                            generation=opts["generation"])
    print(f"submitted {shown['assignment']} at {shown['revision']}")


def do_verify(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("evidence", "generation"))
    with writer() as conn:
        shown = core_verify(conn, bound_participant(conn), agent=agent, assignment=raw,
                            evidence=opts["evidence"], generation=opts["generation"])
    print(f"verified {shown['assignment']} by {shown['verified_by']}")


def do_return(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("findings", "generation"))
    with writer() as conn:
        shown = core_return(conn, bound_participant(conn), agent=agent, assignment=raw,
                            findings=opts["findings"], generation=opts["generation"])
    print(f"returned {shown['assignment']} to {shown['holder']}")


def do_accept(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("evidence", "generation"))
    with writer() as conn:
        shown = core_accept(conn, bound_participant(conn), agent=agent, assignment=raw,
                            evidence=opts["evidence"], generation=opts["generation"])
    print(f"accepted {shown['assignment']} by {shown['accepted_by']}")


def do_reopen(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("revision", "why", "generation"))
    with writer() as conn:
        shown = core_reopen(conn, bound_participant(conn), agent=agent, assignment=raw,
                            revision=opts["revision"], why=opts["why"],
                            generation=opts["generation"])
    print(f"reopened {shown['assignment']} at {shown['revision']}; "
          f"generation {shown['generation']}")


def do_supersede(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("by",))
    with writer() as conn:
        shown = core_supersede(conn, bound_participant(conn), agent=agent, assignment=raw,
                               by=opts["by"])
    print(f"superseded {shown['assignment']} by {shown['superseded_by']}")


def assignment_line(row: dict) -> str:
    who = row["holder"] or row["recipient"] or "nobody"
    return (f"{row['assignment']} {row['title']} — {row['place']}, {who}, "
            f"generation {row['generation']}, revision {row['revision'] or 'none'}")


def do_assignments(rest):
    _, opts = parse(rest, 0, optional=("state", "to"), flags=("mine",))
    conn = reader()
    part = bound_participant(conn) if opts.get("mine") else None
    shown = core_assignments(conn, part, state=opts.get("state"), to=opts.get("to"))
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
        shown = core_send(conn, bound_participant(conn), agent=agent, to=opts["to"],
                          purpose=opts["purpose"], body=opts["body"],
                          assignment=opts.get("assignment"),
                          decision=opts.get("decision"),
                          reply_to=opts.get("reply-to"), artifact=opts.get("artifact"))
    print(f"message {shown['message']} queued")


def do_deliver(rest):
    identity()
    (raw,), opts = parse(rest, 1, required=("ref",))
    with writer() as conn:
        shown = core_deliver(conn, bound_participant(conn), message=raw, ref=opts["ref"])
    print(f"delivered {shown['message']} ref {shown['delivery_ref']}")


def do_ack(rest):
    identity()
    (raw,), _ = parse(rest, 1)
    with writer() as conn:
        shown = core_ack(conn, bound_participant(conn), message=raw)
    print(f"acknowledged {shown['message']} by {shown['acked_by']}; not resolved")


def do_resolve(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("evidence",))
    with writer() as conn:
        shown = core_resolve(conn, bound_participant(conn), agent=agent, message=raw,
                             evidence=opts["evidence"])
    print(f"resolved {shown['message']}: {shown['evidence']}")


def do_withdraw(rest):
    agent = identity()
    (raw,), opts = parse(rest, 1, required=("why",))
    with writer() as conn:
        shown = core_withdraw(conn, bound_participant(conn), agent=agent, message=raw,
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
    shown = core_inbox(conn, bound_participant(conn), unresolved=bool(opts.get("unresolved")))
    if not shown["messages"]:
        print("no messages")
        return EXIT_DONE
    for row in shown["messages"]:
        print(message_line(row))
    return EXIT_DONE


def do_outstanding(rest):
    _, opts = parse(rest, 0, optional=("to",))
    shown = core_outstanding(reader(), None, to=opts.get("to"))
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
        shown = core_observe(conn, bound_participant(conn), assignment=raw,
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
    shown = core_observations(reader(), None, assignment=raw,
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
        shown = core_ask(conn, bound_participant(conn), question=opts["question"],
                         alternatives=opts["alternatives"],
                         assignment=opts.get("assignment"))
    print(f"decision {shown['decision']}")


def do_answer(rest):
    identity()
    (raw,), opts = parse(rest, 1, optional=("counter", "unknowns", "consequence"))
    with writer() as conn:
        shown = core_answer(conn, bound_participant(conn), decision=raw,
                            counter=opts.get("counter"), unknowns=opts.get("unknowns"),
                            consequence=opts.get("consequence"))
    print(f"answered {shown['decision']}")


def do_decide(rest):
    identity()
    (raw,), opts = parse(rest, 1, required=("choice", "rationale"))
    with writer() as conn:
        shown = core_decide(conn, bound_participant(conn), decision=raw, choice=opts["choice"],
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
    shown = core_decision(reader(), None, decision=raw)
    if shown.get("store") == "absent":
        print("no store")
        return EXIT_DONE
    return print_decision(shown)


def do_decisions(rest):
    _, opts = parse(rest, 0, flags=("open",))
    shown = core_decisions(reader(), None, undecided_only=bool(opts.get("open")))
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
        shown = core_reserve(conn, bound_participant(conn), agent=agent, name=name,
                             assignment=opts["for"], ttl=opts.get("ttl"))
    print(f"reserved {shown['name']} for {shown['assignment']} by {shown['holder']}")


def do_free(rest):
    agent = identity()
    (name,), opts = parse(rest, 1, required=("why",))
    with writer() as conn:
        shown = core_free(conn, bound_participant(conn), agent=agent, name=name, why=opts["why"])
    note = ("" if shown["reconciled"]
            else f"; {shown['previous_holder']}'s run is not reconciled")
    print(f"freed {shown['name']}{note}")


def do_resources(rest):
    parse(rest, 0)
    shown = core_resources(reader(), None)
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
    shown = core_show(reader(), None, target=raw)
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
    shown = core_coverage(reader(), None, requirement=opts.get("requirement"))
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
    shown = core_brief(conn, bound_participant(conn))
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
