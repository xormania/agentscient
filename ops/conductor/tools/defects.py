#!/usr/bin/env python3
"""The lane defect ledger: one file per row, so two sessions' rows never touch.

    defects.py next                                          print the next id, LD-NN
    defects.py add --where W --defect D --repair R --tests T   write the row file, print "LD-NN path"
    defects.py show LD-NN                                    print the row
    defects.py list                                          one line per row: id, observed, where

Owner, 2026-09-13 ("fix issue #1 - PR and merge"): lane-defects.md conflicted
on three of five merge-forwards since 2026-09-11 because every session
appended its row at the same line of one table. From LD-36 a row is its own
file under ops/conductor/handoff/lane-defects/; the page keeps its table
frozen at LD-35. The next id is one past the highest in the table and the
directory, so the only conflict left is the same id minted by two sessions
before either lands: an add/add on one file, which git names.

Follows instrument-conventions.md: the lever works on the repository of
its cwd and refuses `repository` outside one; writing verbs need an
identity, reads never do; refusals are one stderr line, exit 2, stdout empty.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from instrument import GIT, Refusal, emit, identity, now, refuse
except ModuleNotFoundError:
    print(
        "tooling: expected instrument.py beside this tool; found absent; "
        "needed restore ops/conductor/tools/instrument.py beside it",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

PAGE = Path("ops/conductor/handoff/lane-defects.md")
ROWS = Path("ops/conductor/handoff/lane-defects")
FIELDS = ("where", "defect", "repair", "tests")
ID = re.compile(r"^LD-(\d+)$")
TABLE_ID = re.compile(r"^\| LD-(\d+) \|", re.MULTILINE)
FILE_ID = re.compile(r"^LD-(\d+)\.md$")


def repo_root() -> Path:
    proc = subprocess.run([GIT, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        refuse("repository", "a git repository at the working directory", os.getcwd(),
               "run the lever from inside the repository whose ledger it writes")
    return Path(proc.stdout.strip())


def highest(root: Path) -> int:
    top = 0
    page = root / PAGE
    if page.is_file():
        top = max([int(m) for m in TABLE_ID.findall(page.read_text(encoding="utf-8"))] + [top])
    rows = root / ROWS
    if rows.is_dir():
        for entry in os.listdir(rows):
            m = FILE_ID.match(entry)
            if m:
                top = max(top, int(m.group(1)))
    return top


def do_next(root: Path) -> int:
    print(f"LD-{highest(root) + 1}")
    return 0


def parse_fields(args: list[str]) -> dict[str, str]:
    got: dict[str, str] = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and a[2:] in FIELDS + ("observed",):
            if i + 1 >= len(args):
                refuse("arguments", f"a value after {a}", "none", f"give {a} its text")
            got[a[2:]] = args[i + 1]
            i += 2
            continue
        refuse("arguments", "add --where W --defect D --repair R --tests T [--observed DATE]",
               a, "name each field by its flag")
    missing = [f for f in FIELDS if not got.get(f, "").strip()]
    if missing:
        refuse("arguments", "every field non-empty: " + " ".join("--" + f for f in FIELDS),
               "missing or empty: " + " ".join("--" + f for f in missing), "say what was observed, where, the repair and the tests")
    return got


def do_add(root: Path, args: list[str]) -> int:
    by = identity()
    fields = parse_fields(args)
    observed = fields.get("observed") or now().strftime("%Y-%m-%d")
    ident = f"LD-{highest(root) + 1}"
    rows = root / ROWS
    rows.mkdir(parents=True, exist_ok=True)
    path = rows / f"{ident}.md"
    lines = [f"# {ident}", "", "| field | value |", "|---|---|", f"| observed | {observed} |"]
    lines += [f"| {f} | {fields[f]} |" for f in FIELDS]
    lines += [f"| by | {by} |", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"{ident} {ROWS / path.name}")
    return 0


def row_path(root: Path, ident: str) -> Path:
    if not ID.match(ident):
        refuse("arguments", "an id of the form LD-NN", ident, "name the row by its id")
    path = root / ROWS / f"{ident}.md"
    if not path.is_file():
        refuse("absent", f"a row file {ROWS / (ident + '.md')}", "no such file",
               "list the rows with defects.py list; rows before LD-36 sit in the page's table")
    return path


def do_show(root: Path, ident: str) -> int:
    sys.stdout.write(row_path(root, ident).read_text(encoding="utf-8"))
    return 0


def do_list(root: Path) -> int:
    rows = root / ROWS
    entries = []
    if rows.is_dir():
        for entry in os.listdir(rows):
            m = FILE_ID.match(entry)
            if m:
                entries.append((int(m.group(1)), entry))
    for _, entry in sorted(entries):
        text = (rows / entry).read_text(encoding="utf-8")
        field = dict(re.findall(r"^\| (\w+) \| (.*) \|$", text, re.MULTILINE))
        print(f"{entry[:-3]} {field.get('observed', '?')} {field.get('where', '?')}")
    return 0


def main(argv: list[str]) -> int:
    if argv == ["next"]:
        return do_next(repo_root())
    if argv[:1] == ["add"]:
        root = repo_root()
        return do_add(root, argv[1:])
    if len(argv) == 2 and argv[0] == "show":
        return do_show(repo_root(), argv[1])
    if argv == ["list"]:
        return do_list(repo_root())
    refuse("arguments", "next | add --where W --defect D --repair R --tests T | show LD-NN | list",
           " ".join(argv) or "nothing", "choose one verb with exactly its arguments")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Refusal as refusal:
        sys.exit(emit(refusal))
