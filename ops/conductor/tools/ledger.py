#!/usr/bin/env python3
"""Every appended register as one file per row, so parallel sessions' rows never touch.

    ledger.py ledgers                         the ledgers this lever knows, one per line
    ledger.py next LEDGER                     reserve and print this owner's next id
    ledger.py check LEDGER                    findings: shared or unfiled numbers
    ledger.py add LEDGER --field VALUE ...    write the row file, print "ID path"
    ledger.py show LEDGER ID                  print the row
    ledger.py list LEDGER                     one line per row: id, observed, first field

Owner, 2026-09-13: the pitfalls page and anything similar, because agents
need to work in parallel. lane-defects.md conflicted on three of five
merge-forwards since 2026-09-11 and pitfalls-20260911.md on one, each
session appending its row at the same line of one table. A ledger here
is a page whose table stops at a row, a directory of one file per row
after it, an id shape and a field list. IDs are reserved transactionally
in the lane state store before their git row is written, while the row
files remain the record plane. PR264's reader counts every retained ref,
including historical additions (2026-09-16, CO ruling M-155).
defects.py is a shim over the defects ledger.

Follows instrument-conventions.md: the lever works on the repository of
its cwd and refuses `repository` outside one; writing verbs need an
identity, reads never do; refusals are one stderr line, exit 2, stdout empty.
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    import machine
    from instrument import (
        Refusal,
        conf,
        emit,
        git,
        identity,
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

# name -> page (table rows stop there), rows directory, id prefix, heading
# word, fields in order. The table's id column is matched as "| <prefix><n> |".
LEDGERS: dict[str, dict[str, object]] = {
    "defects": {
        "page": Path("ops/conductor/handoff/lane-defects.md"),
        "rows": Path("ops/conductor/handoff/lane-defects"),
        "prefix": "LD-",
        "heading": "",
        "fields": ("where", "defect", "repair", "tests"),
    },
    "pitfalls": {
        "page": Path("ops/conductor/handoff/pitfalls-20260911.md"),
        "rows": Path("ops/conductor/handoff/pitfalls"),
        "prefix": "",
        "heading": "pitfall ",
        "fields": ("what-bit", "do-instead"),
    },
    # LD-53: two sessions minted I-029 on two branches because there was
    # no reader to ask. An idea is prose in the owner's words in the
    # shape ops/conductor/ideas/README.md gives, never a field table, so
    # this register is handwritten: the lever mints its number and
    # reports the numbers already shared, and writes nothing.
    "ideas": {
        "page": None,
        "rows": Path("ops/conductor/ideas"),
        "prefix": "I-",
        "heading": "",
        "fields": (),
        # The record's file name carries a slug after its number, so the
        # entry pattern is the directory's own, not the default one row
        # per id.
        "entry": r"I-(\d+)-.+\.md",
        "width": 3,
        "handwritten": True,
    },
}
FIELD_LINE = re.compile(r"^\| ([\w-]+) \| (.*) \|$", re.MULTILINE)
RESERVATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_reservations(
    ledger TEXT NOT NULL,
    number INTEGER NOT NULL,
    owner TEXT NOT NULL,
    agent TEXT NOT NULL,
    reserved_at TEXT NOT NULL,
    filed_at TEXT,
    path TEXT,
    UNIQUE(ledger, number)
)
"""


def ledger(name: str) -> dict[str, object]:
    if name not in LEDGERS:
        refuse("ledger", "one of " + ", ".join(LEDGERS), name or "nothing", "name a ledger this lever knows")
    return LEDGERS[name]


def repo_root() -> Path:
    proc = git("rev-parse", "--show-toplevel")
    if proc.returncode != 0 or not proc.stdout.strip():
        refuse("repository", "a git repository at the working directory", os.getcwd(),
               "run the lever from inside the repository whose ledger it writes")
    return Path(proc.stdout.strip())


def trunk_ref(root: Path) -> str | None:
    """origin/<trunk> after a bounded fetch, or None when the repository
    has no such remote ref (a scratch repository, an offline host). The
    fetch is said on stderr, never on stdout, so a caller reading the id
    reads only the id. Owner, 2026-09-13 ("minimize parallel work
    conflicts"): a session minting from its own tree alone re-mints an id
    another session already pushed."""
    trunk = conf("TRUNK_BRANCH")
    ref = f"origin/{trunk}"
    if git("remote", "get-url", "origin", cwd=root).returncode != 0:
        return None
    fetched = git("fetch", "-q", "origin", trunk, cwd=root, timeout=20)
    if fetched.returncode == 0:
        print(f"fetched {ref}", file=sys.stderr)
    if git("rev-parse", "--verify", "-q", ref, cwd=root).returncode != 0:
        return None
    return ref


def entry_re(spec: dict[str, object]) -> re.Pattern:
    """A row file's name to its number. A register whose file names carry
    more than the id (the ideas directory's slug) declares its own."""
    named = spec.get("entry")
    if named:
        return re.compile(str(named))
    return re.compile(rf"{re.escape(str(spec['prefix']))}(\d+)\.md$")


def ident(spec: dict[str, object], number: int) -> str:
    """The id as the register spells it. The ideas directory writes its
    number three digits wide, so I-32 would be a second spelling of one
    id and the reader would have taught a session to mint it."""
    return f"{spec['prefix']}{number:0{int(spec.get('width') or 0)}d}"


def reservation_ledger(spec: dict[str, object]) -> str:
    """The stable register name stored beside a reserved number."""
    for name, candidate in LEDGERS.items():
        if candidate is spec or candidate == spec:
            return name
    refuse("ledger", "a declared ledger specification", spec, "reserve an id for a ledger this lever knows")


def reservation_owner(root: Path) -> str:
    """The harness session, or the worktree when no harness named one."""
    named = session()
    return named if named != "unknown" else str(root.resolve())


def reservation_agent() -> str:
    """Attribute a reservation, retaining the former identity-free `next`.

    `next` was a read before it became the reservation verb. Existing
    callers may therefore have no identity; new callers are attributed
    through the shared identity reader, while that one legacy absence is
    recorded explicitly rather than inferred from another environment key.
    """
    try:
        return identity()
    except Refusal as error:
        if error.kind == "identity" and error.found == "unset":
            return "unknown"
        raise


def reservation_writer() -> sqlite3.Connection:
    conn = machine.connect(create=True)
    conn.execute(RESERVATIONS_SCHEMA)
    return conn


def reservation_reader() -> sqlite3.Connection | None:
    """Open the register without creating either the store or its table."""
    if not machine.store_path().is_file():
        return None
    conn = machine.connect(create=False)
    present = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ledger_reservations'"
    ).fetchone()
    if present is None:
        conn.close()
        return None
    return conn


def _reserve_locked(
    conn: sqlite3.Connection,
    root: Path,
    spec: dict[str, object],
    owner: str,
    agent: str,
) -> int:
    name = reservation_ledger(spec)
    row = conn.execute(
        "SELECT MAX(number) AS number FROM ledger_reservations WHERE ledger = ?",
        (name,),
    ).fetchone()
    reserved = int(row["number"] or 0)
    number = max(highest(root, spec), reserved) + 1
    conn.execute(
        "INSERT INTO ledger_reservations"
        "(ledger, number, owner, agent, reserved_at) VALUES (?, ?, ?, ?, ?)",
        (name, number, owner, agent, stamp()),
    )
    return number


def reserve(
    conn: sqlite3.Connection,
    root: Path,
    spec: dict[str, object],
    owner: str,
    agent: str,
) -> int:
    """Reserve the next number in one immediate transaction.

    `BEGIN IMMEDIATE` serializes same-host minters. The unique key remains
    the second wall: if another SQLite client wins independently, re-read
    the register and retry once rather than returning a shared number.
    """
    winner = 0
    for attempt in range(2):
        try:
            conn.execute("BEGIN IMMEDIATE")
            number = _reserve_locked(conn, root, spec, owner, agent)
            conn.commit()
            return number
        except sqlite3.IntegrityError:
            conn.rollback()
            row = conn.execute(
                "SELECT MAX(number) AS number FROM ledger_reservations WHERE ledger = ?",
                (reservation_ledger(spec),),
            ).fetchone()
            winner = int(row["number"] or 0)
            if attempt == 0:
                continue
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
    refuse(
        "reservation",
        f"one unused number after {ident(spec, winner)}",
        "the same number won twice",
        "retry after the competing reservation commits",
    )


def own_reservation(
    conn: sqlite3.Connection,
    root: Path,
    spec: dict[str, object],
    owner: str,
    agent: str,
) -> int:
    """Return this owner's open reservation, or atomically make one."""
    name = reservation_ledger(spec)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT number FROM ledger_reservations "
            "WHERE ledger = ? AND owner = ? AND filed_at IS NULL "
            "ORDER BY number LIMIT 1",
            (name, owner),
        ).fetchone()
        if row is not None:
            conn.commit()
            return int(row["number"])
        number = _reserve_locked(conn, root, spec, owner, agent)
        conn.commit()
        return number
    except sqlite3.IntegrityError:
        if conn.in_transaction:
            conn.rollback()
        return reserve(conn, root, spec, owner, agent)
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise


def file_reservation(
    conn: sqlite3.Connection,
    spec: dict[str, object],
    number: int,
    owner: str,
    path: Path,
) -> None:
    changed = conn.execute(
        "UPDATE ledger_reservations SET filed_at = ?, path = ? "
        "WHERE ledger = ? AND number = ? AND owner = ? AND filed_at IS NULL",
        (stamp(), path.as_posix(), reservation_ledger(spec), number, owner),
    ).rowcount
    if changed != 1:
        refuse(
            "reservation",
            f"one open reservation for {owner} and {ident(spec, number)}",
            f"{changed} rows",
            "run next for this owner before filing the row",
        )


def unfiled_reservations(name: str) -> list[sqlite3.Row]:
    conn = reservation_reader()
    if conn is None:
        return []
    try:
        return conn.execute(
            "SELECT number, owner, reserved_at FROM ledger_reservations "
            "WHERE ledger = ? AND filed_at IS NULL ORDER BY number",
            (name,),
        ).fetchall()
    finally:
        conn.close()


def reservation_age(reserved_at: str) -> str:
    try:
        seconds = max(0, int((now() - parse_stamp(reserved_at)).total_seconds()))
    except (TypeError, ValueError):
        return "unknown"
    return f"{seconds}s"


def by_number(root: Path, spec: dict[str, object]) -> dict[int, list[str]]:
    """The rows directory read as number -> file names, in the working
    tree only: a file on the trunk and the same file here are one row,
    and counting both would report every row as shared with itself."""
    entry = entry_re(spec)
    found: dict[int, list[str]] = {}
    rows = root / spec["rows"]
    if rows.is_dir():
        for name in sorted(os.listdir(rows)):
            m = entry.fullmatch(name) or entry.search(name)
            if m:
                found.setdefault(int(m.group(1)), []).append(name)
    return found


def minted_anywhere(root: Path, spec: dict[str, object]) -> tuple[int, bool]:
    """The highest id any commit in this repository ever added, over every
    ref, in one spawn.

    `highest` read the working tree, the page's table and origin/<trunk>.
    A row minted on a branch that has not merged is in none of the three,
    so two sessions minting between merges are handed the same number.
    Measured on 2026-09-16 over 1,264 refs: ten ids carry two different
    rows, LD-81 four; at 19:25:34Z one session filed LD-81, LD-82 and
    LD-83 on ids `next` had just called free, and at 20:09:44Z renumbered
    all three by hand after the trunk moved 21 commits and landed a
    different LD-81 underneath it. Twelve ids existed off the trunk and
    were invisible here.

    `--all` is every ref under refs/, so a row that only ever lived in a
    dispatch snapshot counts too, and `--no-renames` keeps a row that was
    renumbered away counted under the number it vacated -- an id once
    used is never handed out a second time.

    Returns what it found and whether it could look. A git that cannot
    answer is not a zero: on `False` the caller refuses class `refs`
    rather than minting off a silence (docs/wire.md, absence discipline).
    An operator who sets LEDGER_REFS=local has declared that limit
    instead, and the answer is off this repository's refs alone.
    """
    entry = entry_re(spec)
    # `--all` reads only the refs this repository already holds, and trunk_ref
    # fetches origin/<trunk> by refspec, which leaves every other branch stale
    # or absent -- so a row another session pushed to its own branch would still
    # be invisible, which is the collision this reader exists to close. Fetch
    # every branch first, and say so on stderr, never on stdout.
    if os.environ.get("LEDGER_REFS") == "local":
        # The operator has declared the limit rather than inheriting it: the
        # answer is off this repository's refs alone and may be low.
        print("LEDGER_REFS=local: ids read off this repository's refs alone; "
              "a branch pushed since the last fetch is not among them",
              file=sys.stderr)
    elif git("remote", "get-url", "origin", cwd=root).returncode == 0:
        if git("fetch", "-q", "origin", cwd=root, timeout=60).returncode != 0:
            return 0, False
        print("fetched origin", file=sys.stderr)
    listed = git("log", "--all", "--no-renames", "--diff-filter=A", "--format=",
                 "--name-only", "--", f"{spec['rows'].as_posix()}/", cwd=root,
                 timeout=30)
    if listed.returncode != 0:
        return 0, False
    top = 0
    for line in listed.stdout.splitlines():
        m = entry.search(line.strip())
        if m:
            top = max(top, int(m.group(1)))
    return top, True


def highest(root: Path, spec: dict[str, object]) -> int:
    """One past this is the next id: the highest over the page's table and
    the rows directory, in the working tree, on origin/<trunk>, and on
    every other ref this repository holds (`minted_anywhere`).

    A register with no page (the ideas directory) is read from its rows
    alone; a number already held by two rows does not change what the
    next one is, so this answers whether or not `check` has findings.
    """
    prefix = re.escape(str(spec["prefix"]))
    table = re.compile(rf"^\| {prefix}(\d+) \|", re.MULTILINE)
    entry = entry_re(spec)
    top = 0
    page = root / spec["page"] if spec["page"] else None
    if page is not None and page.is_file():
        top = max([int(n) for n in table.findall(page.read_text(encoding="utf-8"))] + [top])
    for number in by_number(root, spec):
        top = max(top, number)
    ref = trunk_ref(root)
    if ref is not None:
        if spec["page"]:
            shown = git("show", f"{ref}:{spec['page'].as_posix()}", cwd=root)
            if shown.returncode == 0:
                top = max([int(n) for n in table.findall(shown.stdout)] + [top])
        listed = git("ls-tree", "--name-only", ref, f"{spec['rows'].as_posix()}/", cwd=root)
        if listed.returncode == 0:
            for line in listed.stdout.splitlines():
                m = entry.search(line.strip())
                if m:
                    top = max(top, int(m.group(1)))
    everywhere, looked = minted_anywhere(root, spec)
    if not looked:
        # Absence is declared, never inferred (docs/wire.md). An id minted off
        # refs that could not be refreshed is low by an unknown amount, and the
        # caller reads stdout, so stderr alone would not reach it.
        refuse("refs",
               "every id this repository's refs hold, after a fetch of origin",
               "origin could not be reached, so the refs may be stale and the "
               "next id low",
               "run it where origin answers, or set LEDGER_REFS=local to mint "
               "off this repository's refs alone and say so in the row")
    top = max(top, everywhere)
    return top


def parse_fields(spec: dict[str, object], args: list[str]) -> dict[str, str]:
    fields = tuple(spec["fields"])
    got: dict[str, str] = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and a[2:] in fields + ("observed",):
            if i + 1 >= len(args):
                refuse("arguments", f"a value after {a}", "none", f"give {a} its text")
            got[a[2:]] = args[i + 1]
            i += 2
            continue
        refuse("arguments", "add LEDGER " + " ".join(f"--{f} TEXT" for f in fields) + " [--observed DATE]",
               a, "name each field by its flag")
    # A line break in a value writes a field line of its own, which list then
    # reads as the row's (security audit 20260913T104919Z-review-codex-9126d3,
    # finding 5): every value stays on its one line.
    broken = [f for f, value in got.items() if "\n" in value or "\r" in value]
    if broken:
        refuse("arguments", "each field's text on one line", "a line break in " + " ".join("--" + f for f in broken),
               "join the text onto one line")
    missing = [f for f in fields if not got.get(f, "").strip()]
    if missing:
        refuse("arguments", "every field non-empty: " + " ".join("--" + f for f in fields),
               "missing or empty: " + " ".join("--" + f for f in missing), "say each field's text")
    return got


def contain(root: Path, target: Path, shown: Path) -> None:
    """Refuse a write whose target resolves outside the repository. A symlink
    at the rows directory sent a row file anywhere the link pointed (security
    audit 20260913T104919Z-review-codex-9126d3, finding 3)."""
    inside = root.resolve()
    resolved = target.resolve()
    if not resolved.is_relative_to(inside):
        refuse("containment", f"{shown} inside the repository {inside}", f"it resolves to {resolved}",
               f"replace the symlink at {shown} with a directory of the repository")


def handwritten(name: str, spec: dict[str, object], verb: str) -> None:
    """A register the lever reads and never writes refuses the verbs that
    would write one or read a field table out of prose."""
    if spec.get("handwritten"):
        refuse("ledger", f"a ledger this lever writes for {verb}", name,
               f"{name} is recorded by hand in the shape its README gives; "
               f"this lever answers next {name} and check {name}")


def do_check(root: Path, name: str) -> int:
    """Findings, not a refusal: the verb ran to completion and the result
    carries what it found (docs/wire.md). A number minted twice in the
    past says nothing about the next one, so `next` keeps answering and
    this is where the collision is reported.
    """
    spec = ledger(name)
    shared = {n: names for n, names in by_number(root, spec).items() if len(names) > 1}
    unfiled = unfiled_reservations(name)
    if not shared and not unfiled:
        print(f"{name}: no shared numbers")
        return 0
    for number in sorted(shared):
        print(f"{ident(spec, number)} shared by " + ", ".join(shared[number]))
    for row in unfiled:
        print(
            f"{ident(spec, int(row['number']))} reserved and unfiled by "
            f"{row['owner']} age={reservation_age(row['reserved_at'])}"
        )
    print(
        f"{name}: {len(shared)} shared number(s), "
        f"{len(unfiled)} reserved-and-unfiled number(s)"
    )
    return 1


def do_add(root: Path, name: str, args: list[str]) -> int:
    spec = ledger(name)
    handwritten(name, spec, "add")
    by = identity()
    fields = parse_fields(spec, args)
    observed = fields.get("observed") or now().strftime("%Y-%m-%d")
    rows = root / spec["rows"]
    contain(root, rows, spec["rows"])
    # Keep the bounded trunk refresh on every add, including when this
    # owner already holds the number that add will consume.
    trunk_ref(root)
    owner = reservation_owner(root)
    conn = reservation_writer()
    try:
        number = own_reservation(conn, root, spec, owner, by)
    finally:
        conn.close()
    row_id = ident(spec, number)
    rows.mkdir(parents=True, exist_ok=True)
    path = rows / f"{row_id}.md"
    contain(root, path, spec["rows"] / path.name)
    lines = [f"# {spec['heading']}{row_id}", "", "| field | value |", "|---|---|", f"| observed | {observed} |"]
    lines += [f"| {f} | {fields[f]} |" for f in spec["fields"]]
    lines += [f"| by | {by} |", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    relative = spec["rows"] / path.name
    conn = reservation_writer()
    try:
        file_reservation(conn, spec, number, owner, relative)
    finally:
        conn.close()
    print(f"{row_id} {relative}")
    return 0


def row_path(root: Path, name: str, row_id: str) -> Path:
    spec = ledger(name)
    handwritten(name, spec, "show")
    ident = row_id
    if not re.fullmatch(rf"{re.escape(str(spec['prefix']))}\d+", ident):
        refuse("arguments", f"an id of the form {spec['prefix']}NN", ident, "name the row by its id")
    path = root / spec["rows"] / f"{ident}.md"
    if not path.is_file():
        refuse("absent", f"a row file {spec['rows'] / (ident + '.md')}", "no such file",
               f"list the rows with ledger.py list {name}; earlier rows sit in the page's table")
    return path


def do_show(root: Path, name: str, ident: str) -> int:
    sys.stdout.write(row_path(root, name, ident).read_text(encoding="utf-8"))
    return 0


def do_list(root: Path, name: str) -> int:
    spec = ledger(name)
    handwritten(name, spec, "list")
    rows = root / spec["rows"]
    prefix = re.escape(str(spec["prefix"]))
    entries = []
    if rows.is_dir():
        for entry in os.listdir(rows):
            m = re.fullmatch(rf"{prefix}(\d+)\.md", entry)
            if m:
                entries.append((int(m.group(1)), entry))
    first = spec["fields"][0]
    for _, entry in sorted(entries):
        field = dict(FIELD_LINE.findall((rows / entry).read_text(encoding="utf-8")))
        print(f"{entry[:-3]} {field.get('observed', '?')} {field.get(first, '?')}")
    return 0


def do_ledgers() -> int:
    for name, spec in LEDGERS.items():
        line = f"{name} {spec['rows']} "
        line += ("(handwritten: next, check)" if spec.get("handwritten")
                 else " ".join("--" + f for f in spec["fields"]))
        print(line)
    return 0


USAGE = "ledgers | next LEDGER | check LEDGER | add LEDGER --field TEXT ... | show LEDGER ID | list LEDGER"


def main(argv: list[str]) -> int:
    if argv == ["ledgers"]:
        return do_ledgers()
    if len(argv) == 2 and argv[0] == "next":
        root = repo_root()
        spec = ledger(argv[1])
        conn = reservation_writer()
        try:
            number = own_reservation(
                conn,
                root,
                spec,
                reservation_owner(root),
                reservation_agent(),
            )
        finally:
            conn.close()
        return print(ident(spec, number)) or 0
    if len(argv) == 2 and argv[0] == "check":
        return do_check(repo_root(), argv[1])
    if len(argv) >= 2 and argv[0] == "add":
        return do_add(repo_root(), argv[1], argv[2:])
    if len(argv) == 3 and argv[0] == "show":
        return do_show(repo_root(), argv[1], argv[2])
    if len(argv) == 2 and argv[0] == "list":
        return do_list(repo_root(), argv[1])
    refuse("arguments", USAGE, " ".join(argv) or "nothing", "choose one verb with exactly its arguments")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Refusal as refusal:
        sys.exit(emit(refusal))
