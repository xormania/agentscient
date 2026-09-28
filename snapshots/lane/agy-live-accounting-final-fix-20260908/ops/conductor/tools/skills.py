#!/usr/bin/env python3
"""skills.py — CRUD and telemetry for the project's skills, SQLite-backed.

  sync                      derive rows from .claude/skills/ on disk (upsert;
                            a vanished dir marks its row missing, never deletes;
                            a wished skill whose dir appears becomes active)
  add NAME DESC [--kind=K] [--status=draft]      a planned skill row
  list [--status=S]         the registry view
  show NAME                 one skill, with its recent event history
  note NAME TEXT            update notes
  retire NAME REASON        soft-retire (reason required; nothing vanishes)
  log-use NAME [DETAIL]     an invocation happened
  log-fail NAME DETAIL      an invocation failed; DETAIL carries the error's words
  log-miss NAME DETAIL      a potential use that did not happen — work was done
                            another way; DETAIL says what was done instead
  wish NAME DETAIL          a skill that should exist and does not
  report                    per-skill use/fail/miss counts; wishes ranked

The skills table syncs from disk, which stays the source of truth for what
exists; events are observations (the non-authoritative-mirror rule).
Reading needs no identity; recording an event does: set WF_AGENT
('Name <address>'), the same contract wf enforces. Refusals name what was
expected, found, and needed.
"""
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

DB = os.path.expanduser("~/.local/state/agentscient/skills.db")
REPO = Path(__file__).resolve().parents[3]
SKILLS_DIR = REPO / ".claude" / "skills"
KINDS = ("project", "conductor", "process", "personal")
AGENT_FORM = re.compile(r".+ <[^<>@\s]+@[^<>\s]+>$")

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def agent_or_refuse():
    agent = os.environ.get("WF_AGENT", "")
    if not AGENT_FORM.match(agent):
        sys.exit("refusing: recording needs an identity; found "
                 f"WF_AGENT={agent!r}, expected 'Name <address>' — "
                 "export WF_AGENT='Your Model Name <noreply@vendor>'")
    return agent

def con_():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS skills(
        name TEXT PRIMARY KEY, kind TEXT NOT NULL, path TEXT,
        description TEXT, status TEXT NOT NULL DEFAULT 'active',
        created_ts TEXT NOT NULL, updated_ts TEXT NOT NULL,
        retire_reason TEXT, notes TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS skill_events(
        id INTEGER PRIMARY KEY, ts TEXT NOT NULL, session TEXT NOT NULL,
        agent TEXT NOT NULL, skill TEXT NOT NULL, event TEXT NOT NULL,
        detail TEXT)""")
    return con

def frontmatter(path):
    """(name, description) from SKILL.md frontmatter; None where absent —
    absence is not emptiness, and the caller falls back explicitly.
    A file that cannot be read at all returns None (no tuple): an
    unperformed read is not an empty frontmatter."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    m = re.match(r"\A---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None, None
    name = desc = None
    for line in m.group(1).splitlines():
        if line.startswith("name:") and name is None:
            name = line.split(":", 1)[1].strip() or None
        if line.startswith("description:") and desc is None:
            desc = line.split(":", 1)[1].strip() or None
    return name, desc

def sync(_):
    if not SKILLS_DIR.is_dir():
        sys.exit(f"refusing: {SKILLS_DIR} is not a directory — cannot scan; "
                 "an unperformed scan is not an empty result")
    con = con_()
    seen = set()
    for d in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        meta = frontmatter(d / "SKILL.md")
        if meta is None:
            print(f"UNRESOLVED (no readable SKILL.md, not registered): {d.name}")
            continue
        name, desc = meta
        name = name or d.name
        seen.add(name)
        row = con.execute("SELECT status FROM skills WHERE name=?",
                          (name,)).fetchone()
        if row is None:
            con.execute("INSERT INTO skills(name, kind, path, description,"
                        " status, created_ts, updated_ts) VALUES (?,?,?,?,?,?,?)",
                        (name, "project", str(d), desc, "active", now(), now()))
            print(f"new: {name}")
        else:
            if row[0] == "wished":
                print(f"wish fulfilled: {name}")
            con.execute("UPDATE skills SET path=?, description=?, updated_ts=?,"
                        " status=CASE WHEN status IN ('missing','wished')"
                        " THEN 'active' ELSE status END WHERE name=?",
                        (str(d), desc, now(), name))
    gone = [r[0] for r in con.execute(
        "SELECT name FROM skills WHERE path IS NOT NULL"
        " AND status NOT IN ('missing','retired','wished')") if r[0] not in seen]
    for name in gone:
        con.execute("UPDATE skills SET status='missing', updated_ts=?"
                    " WHERE name=?", (now(), name))
        print(f"MISSING (dir gone, row kept): {name}")
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    print(f"synced: {len(seen)} on disk, {n} rows total")

def add(argv):
    if len(argv) < 2:
        sys.exit("refusing: add needs NAME DESCRIPTION")
    name, desc = argv[0], argv[1]
    kind = next((a.split("=", 1)[1] for a in argv if a.startswith("--kind=")),
                "project")
    status = next((a.split("=", 1)[1] for a in argv
                   if a.startswith("--status=")), "draft")
    if kind not in KINDS:
        sys.exit(f"refusing: kind {kind!r}; expected one of {KINDS}")
    con = con_()
    if con.execute("SELECT 1 FROM skills WHERE name=?", (name,)).fetchone():
        sys.exit(f"refusing: {name!r} exists; `note` or `sync` updates it")
    con.execute("INSERT INTO skills(name, kind, description, status,"
                " created_ts, updated_ts) VALUES (?,?,?,?,?,?)",
                (name, kind, desc, status, now(), now()))
    con.commit()
    print(f"added {name} [{kind}/{status}]")

def list_(argv):
    status = next((a.split("=", 1)[1] for a in argv
                   if a.startswith("--status=")), None)
    con = con_()
    q = ("SELECT name, kind, status, COALESCE(description,'(no description)')"
         " FROM skills")
    rows = con.execute(q + (" WHERE status=?" if status else "")
                       + " ORDER BY kind, name",
                       (status,) if status else ()).fetchall()
    if not rows:
        print("no rows" + (f" with status={status}" if status else "")
              + " — run `sync` first if the table should not be empty")
        return
    for name, kind, st, desc in rows:
        print(f"{name:<18} {kind:<10} {st:<8} {desc[:70]}")

def show(argv):
    if not argv:
        sys.exit("refusing: show needs NAME")
    con = con_()
    row = con.execute("SELECT name, kind, path, description, status,"
                      " created_ts, updated_ts, retire_reason, notes"
                      " FROM skills WHERE name=?", (argv[0],)).fetchone()
    if row is None:
        sys.exit(f"refusing: no skill {argv[0]!r}; `list` shows rows,"
                 " `add`/`wish` create them")
    for k, v in zip(("name", "kind", "path", "description", "status",
                     "created", "updated", "retire_reason", "notes"), row,
                    strict=True):
        if v is not None:
            print(f"{k}: {v}")
    ev = con.execute("SELECT ts, event, COALESCE(detail,'') FROM skill_events"
                     " WHERE skill=? ORDER BY ts", (argv[0],)).fetchall()
    print(f"events: {len(ev)}")
    for ts, event, detail in ev[-10:]:
        print(f"  {ts} {event:<8} {detail[:60]}")

def note(argv):
    if len(argv) < 2:
        sys.exit("refusing: note needs NAME TEXT")
    con = con_()
    if con.execute("UPDATE skills SET notes=?, updated_ts=? WHERE name=?",
                   (argv[1], now(), argv[0])).rowcount == 0:
        sys.exit(f"refusing: no skill {argv[0]!r}")
    con.commit()
    print("noted")

def retire(argv):
    if len(argv) < 2:
        sys.exit("refusing: retire needs NAME REASON — nothing leaves"
                 " without one")
    con = con_()
    if con.execute("UPDATE skills SET status='retired', retire_reason=?,"
                   " updated_ts=? WHERE name=?",
                   (argv[1], now(), argv[0])).rowcount == 0:
        sys.exit(f"refusing: no skill {argv[0]!r}")
    con.commit()
    print(f"retired {argv[0]} (row kept, reason recorded)")

def _event(kind):
    def go(argv):
        if not argv or (kind != "invoked" and len(argv) < 2):
            need = "NAME [DETAIL]" if kind == "invoked" else "NAME DETAIL"
            sys.exit(f"refusing: needs {need} — an event without its story"
                     " is a count wearing a claim's clothes")
        agent = agent_or_refuse()
        name = argv[0]
        detail = argv[1] if len(argv) > 1 else None
        con = con_()
        known = con.execute("SELECT status FROM skills WHERE name=?",
                            (name,)).fetchone()
        if not known and kind != "wish":
            sys.exit(f"refusing: no skill {name!r} — for a skill that should"
                     " exist, use `wish`; for one on disk, run `sync` first")
        # A row whose status is still 'wished' is accumulated demand, not an
        # existing skill: wishing it again ranks it higher.
        if known and kind == "wish" and known[0] != "wished":
            sys.exit(f"refusing: {name!r} already exists — a wish is for the"
                     " absent; use log-miss if it existed and was not used")
        if not known:
            con.execute("INSERT INTO skills(name, kind, description, status,"
                        " created_ts, updated_ts) VALUES (?,?,?,?,?,?)",
                        (name, "project", detail, "wished", now(), now()))
        con.execute("INSERT INTO skill_events(ts, session, agent, skill,"
                    " event, detail) VALUES (?,?,?,?,?,?)",
                    (now(), os.environ.get("CLAUDE_SESSION_ID", "unrecorded"),
                     agent, name, kind, detail))
        con.commit()
        print(f"{kind}: {name}")
    return go

def report(_):
    con = con_()
    print(f"{'skill':<18} {'status':<8} {'uses':>4} {'fails':>5} {'misses':>6}")
    for name, st, u, f, m in con.execute("""
        SELECT s.name, s.status,
          SUM(CASE WHEN e.event='invoked' THEN 1 ELSE 0 END),
          SUM(CASE WHEN e.event='failed' THEN 1 ELSE 0 END),
          SUM(CASE WHEN e.event='miss' THEN 1 ELSE 0 END)
        FROM skills s LEFT JOIN skill_events e ON e.skill=s.name
        WHERE s.status != 'wished' GROUP BY s.name ORDER BY s.name"""):
        print(f"{name:<18} {st:<8} {u or 0:>4} {f or 0:>5} {m or 0:>6}")
    wishes = con.execute("""SELECT s.name, COUNT(e.id),
          COALESCE(MAX(e.detail),'') FROM skills s
        LEFT JOIN skill_events e ON e.skill=s.name AND e.event='wish'
        WHERE s.status='wished' GROUP BY s.name ORDER BY 2 DESC""").fetchall()
    if wishes:
        print("wished (demand, ranked):")
        for name, n, detail in wishes:
            print(f"  {n:>3}x {name:<18} {detail[:55]}")
    misses = con.execute("SELECT COUNT(*) FROM skill_events"
                         " WHERE event='miss'").fetchone()[0]
    if misses == 0:
        print("misses: 0 logged — a declared zero says looked-and-found-none"
              " only while sessions actually declare them")

def main():
    cmds = {"sync": sync, "add": add, "list": list_, "show": show,
            "note": note, "retire": retire, "log-use": _event("invoked"),
            "log-fail": _event("failed"), "log-miss": _event("miss"),
            "wish": _event("wish"), "report": report}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(f"usage: skills.py {{{'|'.join(cmds)}}} ...;"
                 " the module doc has details")
    cmds[sys.argv[1]](sys.argv[2:])

if __name__ == "__main__":
    main()
