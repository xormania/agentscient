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
  catalog                   read-only JSON catalogue of active canonical skills
  read NAME                 inspect a whole canonical page, without telemetry
  use NAME [DETAIL]         record invocation and serve the canonical page

The skills table syncs from disk, which stays the source of truth for what
exists; events are observations (the non-authoritative-mirror rule).
Reading needs no identity; recording an event does: set WF_AGENT
('Name <address>'), the same contract wf enforces. Inherits
ops/conductor/instrument-conventions.md: a refusal is one line on
stderr, `class: expected ...; found ...; needed ...`, exit 2, stdout
empty (owner, 2026-09-13, ruling 1: exit 1 with a sentence read as the
Finding class). The store lives under the lane's state directory.
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from instrument import Refusal, emit, identity, refuse, session, stamp, state_dir
except ModuleNotFoundError:
    print(
        "tooling: expected instrument.py beside this tool; found absent; "
        "needed restore ops/conductor/tools/instrument.py beside it",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

REPO = Path(__file__).resolve().parents[3]

# A secret-shaped value never enters the store: the skill-use hook hands a
# Skill call's arguments here verbatim (security audit
# 20260913T104919Z-review-codex-9126d3, finding 4). The token shapes are
# those of ops/devlane/workflow/checks/secret_scan.py; the assignment form
# covers a password or token typed as a named value.
SECRET_SHAPES = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bxox[abpsr]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
)
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key)\b(\s*[=:]\s*)(\S+)")
REDACTED = "[redacted]"


def redact(text):
    """The text with every secret-shaped value replaced; None stays None."""
    if text is None:
        return None
    text = SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    for shape in SECRET_SHAPES:
        text = shape.sub(REDACTED, text)
    return text
SKILLS_DIR = REPO / ".claude" / "skills"
KINDS = ("project", "conductor", "process", "personal")
SKILL_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
MAX_SKILL_BYTES = 256 * 1024
MAX_EVENT_DETAIL_BYTES = 16 * 1024


def db_path():
    return state_dir() / "skills.db"


def con_():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE IF NOT EXISTS skills(
        name TEXT PRIMARY KEY, kind TEXT NOT NULL, path TEXT,
        description TEXT, status TEXT NOT NULL DEFAULT 'active',
        created_ts TEXT NOT NULL, updated_ts TEXT NOT NULL,
        retire_reason TEXT, notes TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS skill_events(
        id INTEGER PRIMARY KEY, ts TEXT NOT NULL, session TEXT NOT NULL,
        agent TEXT NOT NULL, skill TEXT NOT NULL, event TEXT NOT NULL,
        detail TEXT, source_path TEXT, source_sha256 TEXT)""")
    columns = {row[1] for row in con.execute("PRAGMA table_info(skill_events)")}
    if "source_path" not in columns:
        con.execute("ALTER TABLE skill_events ADD COLUMN source_path TEXT")
    if "source_sha256" not in columns:
        con.execute("ALTER TABLE skill_events ADD COLUMN source_sha256 TEXT")
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
    return _metadata(text)


def _metadata(text):
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


def _statuses():
    """Read lifecycle state without creating or repairing a registry."""
    path = db_path()
    try:
        try:
            path.lstat()
        except FileNotFoundError:
            return {}
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as con:
            return dict(con.execute("SELECT name,status FROM skills"))
    except (OSError, sqlite3.Error) as error:
        refuse("registry", "a readable skills registry", type(error).__name__,
               "repair the registry and run skills.py sync")


def _read_canonical_page(page, root):
    """Read one page from a held descriptor, then verify its actual target.

    Resolving a path and opening it later leaves a substitution interval.  The
    descriptor is the source we hash and serve; the /proc target check rejects
    a symlink that crossed the repository boundary before that descriptor was
    acquired.  Internal links remain supported.
    """
    fd = os.open(page, os.O_RDONLY)
    try:
        target = Path(os.readlink(f"/proc/self/fd/{fd}")).resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError("skill page is not a repository file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(MAX_SKILL_BYTES + 1)
        return target, raw
    finally:
        os.close(fd)


def _managed_pages():
    statuses = _statuses()
    try:
        root = REPO.resolve(strict=True)
        if not SKILLS_DIR.resolve(strict=True).is_relative_to(root):
            raise ValueError("skill root escapes repository")
        pages = []
        seen = set()
        for directory in sorted(SKILLS_DIR.iterdir()):
            if not directory.is_dir():
                continue
            page = directory / "SKILL.md"
            if not page.exists() and not page.is_symlink():
                continue
            canonical, raw = _read_canonical_page(page, root)
            if len(raw) > MAX_SKILL_BYTES:
                raise ValueError("skill page exceeds 256 KiB")
            content = raw.decode("utf-8")
            name, description = _metadata(content)
            if (not isinstance(name, str) or not SKILL_NAME.fullmatch(name)
                    or not description or name != directory.name or name in seen):
                raise ValueError("invalid metadata or duplicate skill name")
            seen.add(name)
            if statuses.get(name, "active") == "active":
                pages.append({"name": name, "description": description,
                              "path": str(canonical),
                              "sha256": hashlib.sha256(raw).hexdigest(),
                              "status": "active", "content": content})
        return sorted(pages, key=lambda row: row["name"])
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        refuse("skill-source", "unique readable canonical skills confined to this repository",
               str(error), "repair .claude/skills sources and run skills.py sync")


def managed_catalog():
    return [{key: value for key, value in page.items() if key != "content"}
            for page in _managed_pages()]


def load_skill(name):
    if not isinstance(name, str) or not SKILL_NAME.fullmatch(name):
        refuse("skill", "an unqualified local skill name", repr(name),
               "select an exact name from skills.py catalog")
    for page in _managed_pages():
        if page["name"] == name:
            return page
    refuse("skill", "an active canonical skill present in this checkout", name,
           "inspect skills.py catalog; sync new sources without reviving retired skills")


def catalog(argv):
    if argv:
        refuse("arguments", "catalog without arguments", repr(argv), "run skills.py catalog")
    print(json.dumps(managed_catalog(), sort_keys=True))


def read_skill(argv):
    if len(argv) != 1:
        refuse("arguments", "read NAME", repr(argv), "name one canonical skill")
    print(load_skill(argv[0])["content"], end="")


def use_skill(argv):
    if not 1 <= len(argv) <= 2:
        refuse("arguments", "use NAME [DETAIL]", repr(argv), "name one canonical skill")
    page = load_skill(argv[0])
    _record_event("invoked", page["name"],
                  argv[1] if len(argv) == 2 else "managed invocation", managed_page=page)
    print(f"invoked: {page['name']} (invocation recorded, not proof of completion)")
    print(f"source: {page['path']}; sha256: {page['sha256']}")
    print("Read the whole page below; resolve ./ and ../ from its source directory,"
          " and repository-relative paths from this checkout.")
    print("Do not repeat this page's manual log-use for this invocation; it is already recorded.\n")
    print(page["content"], end="")

def sync(_):
    if not SKILLS_DIR.is_dir():
        refuse("scan", f"a skills directory at {SKILLS_DIR}", "not a directory",
               "restore .claude/skills/; an unperformed scan is not an empty result")
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
                        (name, "project", str(d), desc, "active", stamp(), stamp()))
            print(f"new: {name}")
        else:
            if row[0] == "wished":
                print(f"wish fulfilled: {name}")
            con.execute("UPDATE skills SET path=?, description=?, updated_ts=?,"
                        " status=CASE WHEN status IN ('missing','wished')"
                        " THEN 'active' ELSE status END WHERE name=?",
                        (str(d), desc, stamp(), name))
    gone = [r[0] for r in con.execute(
        "SELECT name FROM skills WHERE path IS NOT NULL"
        " AND status NOT IN ('missing','retired','wished')") if r[0] not in seen]
    for name in gone:
        con.execute("UPDATE skills SET status='missing', updated_ts=?"
                    " WHERE name=?", (stamp(), name))
        print(f"MISSING (dir gone, row kept): {name}")
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    print(f"synced: {len(seen)} on disk, {n} rows total")

def add(argv):
    if len(argv) < 2:
        refuse("arguments", "add NAME DESCRIPTION", " ".join(argv) or "nothing",
               "name the skill and describe it")
    name, desc = argv[0], argv[1]
    kind = next((a.split("=", 1)[1] for a in argv if a.startswith("--kind=")),
                "project")
    status = next((a.split("=", 1)[1] for a in argv
                   if a.startswith("--status=")), "draft")
    if kind not in KINDS:
        refuse("kind", f"a kind in {KINDS}", repr(kind), "name one of them with --kind=")
    con = con_()
    if con.execute("SELECT 1 FROM skills WHERE name=?", (name,)).fetchone():
        refuse("exists", "a name with no row", f"{name!r} already has one",
               "`note` or `sync` updates it")
    con.execute("INSERT INTO skills(name, kind, description, status,"
                " created_ts, updated_ts) VALUES (?,?,?,?,?,?)",
                (name, kind, desc, status, stamp(), stamp()))
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
        refuse("arguments", "show NAME", "no name", "name the skill")
    con = con_()
    row = con.execute("SELECT name, kind, path, description, status,"
                      " created_ts, updated_ts, retire_reason, notes"
                      " FROM skills WHERE name=?", (argv[0],)).fetchone()
    if row is None:
        refuse("skill", "a registered skill", f"no row for {argv[0]!r}",
               "`list` shows rows; `add` or `wish` create them")
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
        refuse("arguments", "note NAME TEXT", " ".join(argv) or "nothing",
               "name the skill and the note")
    con = con_()
    if con.execute("UPDATE skills SET notes=?, updated_ts=? WHERE name=?",
                   (argv[1], stamp(), argv[0])).rowcount == 0:
        refuse("skill", "a registered skill", f"no row for {argv[0]!r}", "`list` shows rows")
    con.commit()
    print("noted")

def retire(argv):
    if len(argv) < 2:
        refuse("arguments", "retire NAME REASON", " ".join(argv) or "nothing",
               "give the reason; nothing leaves without one")
    con = con_()
    if con.execute("UPDATE skills SET status='retired', retire_reason=?,"
                   " updated_ts=? WHERE name=?",
                   (argv[1], stamp(), argv[0])).rowcount == 0:
        refuse("skill", "a registered skill", f"no row for {argv[0]!r}", "`list` shows rows")
    con.commit()
    print(f"retired {argv[0]} (row kept, reason recorded)")


def record_event(kind, name, detail=None):
    """Record one event for native adapters without producing stdout."""
    _record_event(kind, name, detail)


def _event_detail(detail):
    """Redact and bound telemetry before the SQLite write boundary."""
    detail = redact(detail)
    try:
        size = len(detail.encode("utf-8")) if detail is not None else 0
    except UnicodeEncodeError:
        refuse("detail", "UTF-8 event detail", "unencodable text",
               "supply a valid UTF-8 detail")
    if size > MAX_EVENT_DETAIL_BYTES:
        refuse("detail", f"event detail at most {MAX_EVENT_DETAIL_BYTES} UTF-8 bytes",
               f"{size} bytes", "shorten the event detail before recording it")
    return detail


def _record_event(kind, name, detail=None, *, managed_page=None):
    if kind not in {"invoked", "failed", "miss", "wish"} or not isinstance(name, str) or not name:
        refuse("arguments", "a declared skill event and name", repr((kind, name)),
               "use invoked, failed, miss or wish with a skill name")
    if (detail is not None and not isinstance(detail, str)) or (kind != "invoked" and not detail):
        refuse("arguments", "the event's detail text", repr(detail), "give the event its story")
    # Identity remains the shared instrument observation: ordinary CLI calls
    # use its established precedence, while a validated hook profile is
    # resolved by instrument.session().  This tool adds no identity authority.
    agent = identity()
    event_session = session("unrecorded")
    detail = _event_detail(detail)
    if kind == "invoked" and managed_page is None:
        # The legacy CLI can honestly record use of a planned registry row
        # that has no canonical page.  For a fresh or active disk skill,
        # capture the source receipt; do not fabricate one for a plan.
        known_status = _statuses().get(name)
        if known_status in (None, "active"):
            managed_page = load_skill(name)
    try:
        con = con_()
        with con:
            con.execute("BEGIN IMMEDIATE")
            known = con.execute("SELECT status FROM skills WHERE name=?", (name,)).fetchone()
            if kind == "invoked" and managed_page is not None and known and known[0] != "active":
                refuse("skill", "an active managed skill", f"{name}: {known[0]}",
                       "inspect skills.py catalog; invocation never revives inactive skills")
            if not known and kind != "wish":
                page = managed_page if managed_page is not None else load_skill(name)
                con.execute("INSERT INTO skills(name, kind, path, description, status,"
                            " created_ts, updated_ts) VALUES (?,?,?,?,?,?,?)",
                            (name, "project", str(Path(page["path"]).parent),
                             page["description"], "active", stamp(), stamp()))
            if known and kind == "wish" and known[0] != "wished":
                refuse("exists", "a wish for an absent skill", f"{name!r} already exists",
                       "log-miss if it existed and was not used")
            if not known and kind == "wish":
                con.execute("INSERT INTO skills(name, kind, description, status,"
                            " created_ts, updated_ts) VALUES (?,?,?,?,?,?)",
                            (name, "project", detail, "wished", stamp(), stamp()))
            source_path = managed_page["path"] if managed_page is not None else None
            source_sha256 = managed_page["sha256"] if managed_page is not None else None
            con.execute("INSERT INTO skill_events(ts, session, agent, skill, event, detail,"
                        " source_path, source_sha256) VALUES (?,?,?,?,?,?,?,?)",
                        (stamp(), event_session, agent, name, kind, detail,
                         source_path, source_sha256))
    except (OSError, sqlite3.Error) as error:
        refuse("registry", "writable skill telemetry", type(error).__name__,
               "repair the registry before recording skill use")
    finally:
        if "con" in locals():
            con.close()


def _event(kind):
    def go(argv):
        if not argv or (kind != "invoked" and len(argv) < 2):
            need = "NAME [DETAIL]" if kind == "invoked" else "NAME DETAIL"
            refuse("arguments", need, " ".join(argv) or "nothing",
                   "give the event its story; a count without one wears a claim's clothes")
        name = argv[0]
        record_event(kind, name, argv[1] if len(argv) > 1 else None)
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
            "wish": _event("wish"), "report": report,
            "catalog": catalog, "read": read_skill, "use": use_skill}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        refuse("arguments", "one of " + "|".join(cmds), " ".join(sys.argv[1:]) or "no verb",
               "name a verb; the module doc has details")
    cmds[sys.argv[1]](sys.argv[2:])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Refusal as refusal:
        raise SystemExit(emit(refusal)) from None
