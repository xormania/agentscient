#!/usr/bin/env python3
"""Every appended register as one file per row, so parallel sessions' rows never touch.

    ledger.py ledgers                         the ledgers this lever knows, one per line
    ledger.py next LEDGER                     print the next id
    ledger.py add LEDGER --field VALUE ...    write the row file, print "ID path"
    ledger.py show LEDGER ID                  print the row
    ledger.py list LEDGER                     one line per row: id, observed, first field

Owner, 2026-09-13: the pitfalls page and anything similar, because agents
need to work in parallel. lane-defects.md conflicted on three of five
merge-forwards since 2026-09-11 and pitfalls-20260911.md on one, each
session appending its row at the same line of one table. A ledger here
is a page whose table stops at a row, a directory of one file per row
after it, an id shape and a field list. The next id is one past the
highest in the table and the directory, so the only conflict left is the
same id minted by two sessions before either lands: an add/add on one
file that git names. defects.py is a shim over the defects ledger.

Follows instrument-conventions.md: the lever works on the repository of
its cwd and refuses `repository` outside one; writing verbs need an
identity, reads never do; refusals are one stderr line, exit 2, stdout empty.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from instrument import Refusal, conf, emit, git, identity, now, refuse
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
}
FIELD_LINE = re.compile(r"^\| ([\w-]+) \| (.*) \|$", re.MULTILINE)


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


def highest(root: Path, spec: dict[str, object]) -> int:
    """One past this is the next id: the highest over the page's table and
    the rows directory, in the working tree and on origin/<trunk>."""
    prefix = re.escape(str(spec["prefix"]))
    table = re.compile(rf"^\| {prefix}(\d+) \|", re.MULTILINE)
    entry = re.compile(rf"{prefix}(\d+)\.md$")
    top = 0
    page = root / spec["page"]
    if page.is_file():
        top = max([int(n) for n in table.findall(page.read_text(encoding="utf-8"))] + [top])
    rows = root / spec["rows"]
    if rows.is_dir():
        for name in os.listdir(rows):
            m = entry.fullmatch(name)
            if m:
                top = max(top, int(m.group(1)))
    ref = trunk_ref(root)
    if ref is not None:
        shown = git("show", f"{ref}:{spec['page'].as_posix()}", cwd=root)
        if shown.returncode == 0:
            top = max([int(n) for n in table.findall(shown.stdout)] + [top])
        listed = git("ls-tree", "--name-only", ref, f"{spec['rows'].as_posix()}/", cwd=root)
        if listed.returncode == 0:
            for line in listed.stdout.splitlines():
                m = entry.search(line.strip())
                if m:
                    top = max(top, int(m.group(1)))
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
    missing = [f for f in fields if not got.get(f, "").strip()]
    if missing:
        refuse("arguments", "every field non-empty: " + " ".join("--" + f for f in fields),
               "missing or empty: " + " ".join("--" + f for f in missing), "say each field's text")
    return got


def do_add(root: Path, name: str, args: list[str]) -> int:
    spec = ledger(name)
    by = identity()
    fields = parse_fields(spec, args)
    observed = fields.get("observed") or now().strftime("%Y-%m-%d")
    ident = f"{spec['prefix']}{highest(root, spec) + 1}"
    rows = root / spec["rows"]
    rows.mkdir(parents=True, exist_ok=True)
    path = rows / f"{ident}.md"
    lines = [f"# {spec['heading']}{ident}", "", "| field | value |", "|---|---|", f"| observed | {observed} |"]
    lines += [f"| {f} | {fields[f]} |" for f in spec["fields"]]
    lines += [f"| by | {by} |", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"{ident} {spec['rows'] / path.name}")
    return 0


def row_path(root: Path, name: str, ident: str) -> Path:
    spec = ledger(name)
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
        print(f"{name} {spec['rows']} " + " ".join("--" + f for f in spec["fields"]))
    return 0


USAGE = "ledgers | next LEDGER | add LEDGER --field TEXT ... | show LEDGER ID | list LEDGER"


def main(argv: list[str]) -> int:
    if argv == ["ledgers"]:
        return do_ledgers()
    if len(argv) == 2 and argv[0] == "next":
        return (print(f"{ledger(argv[1])['prefix']}{highest(repo_root(), ledger(argv[1])) + 1}") or 0)
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
