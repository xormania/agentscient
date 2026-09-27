#!/usr/bin/env python3
"""Count the helpers the lane's tools each carry a private copy of.

    python3 ops/conductor/reports/duplication-census.py [ROOT]

ROOT defaults to `ops`. Tests, fixtures, the archive and vendored copies
are excluded. The reading is printed, never stored here; the record that
quotes it names the commit it was taken at. Stdlib only, no grep: the
lane's hooks route code search through Graft, and this census is a
measurement of definitions, which the parser answers exactly.

What it reports:

- top-level function names defined in three or more files;
- function bodies (three statements or more) identical across files;
- per file, lines that spell the refusal wire literally;
- shell files that define their own refuse, die or fail helper;
- the vendored isolation copy's distance from the harness module;
- the exit code the receipt engine gives a refusal, against the wire's 2.
"""

from __future__ import annotations

import ast
import collections
import difflib
import hashlib
import re
import sys
from pathlib import Path

SKIP = ("/tests/", "/fixtures/", "/archive/", "/vendor/")
WIRE = re.compile(r"expected .*; found .*; needed")
SHELL_HELPER = re.compile(r"^(refuse|die|fail|_refuse)\(\)", re.MULTILINE)
VENDORED = "devlane/dispatch/levers/codex/vendor/isolation.py"
CANONICAL = "devlane/harness/isolation.py"
RECEIPT_ERRORS = "devlane/harness/receipt/errors.py"


def sources(root: Path, suffix: str) -> list[Path]:
    me = Path(__file__).resolve()
    return sorted(
        p for p in root.rglob(f"*{suffix}")
        if not any(k in str(p) for k in SKIP) and p.resolve() != me
    )


def census(root: Path) -> None:
    names: dict[str, list[str]] = collections.defaultdict(list)
    bodies: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for path in sources(root, ".py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as error:
            print(f"UNREACHABLE {path}: {error}")
            continue
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            names[node.name].append(str(path))
            if len(node.body) >= 3:
                dump = ast.dump(ast.Module(body=node.body, type_ignores=[]))
                digest = hashlib.sha256(dump.encode()).hexdigest()[:10]
                bodies[digest].append((str(path), node.name))

    print("== top-level function names defined in 3+ files ==")
    for name, files in sorted(names.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(files) >= 3 and name != "main":
            print(f"{len(files):3d} {name:14s} " + " ".join(sorted(set(files))))

    print("\n== function bodies identical across files (3+ statements) ==")
    for digest, where in sorted(bodies.items()):
        if len({f for f, _ in where}) >= 2:
            print(digest, " | ".join(f"{f}:{n}" for f, n in where))

    print("\n== files spelling the refusal wire literally (count, file) ==")
    for path in sources(root, ".py") + sources(root, ".sh"):
        count = len(WIRE.findall(path.read_text(encoding="utf-8", errors="replace")))
        if count:
            print(f"{count:3d} {path}")

    print("\n== shell files defining their own refuse/die/fail helper ==")
    for path in sources(root, ".sh"):
        if SHELL_HELPER.search(path.read_text(encoding="utf-8", errors="replace")):
            print(f"    {path}")

    print("\n== the vendored isolation copy against the harness module ==")
    vendored, canonical = root / VENDORED, root / CANONICAL
    if vendored.is_file() and canonical.is_file():
        changed = [
            line
            for line in difflib.unified_diff(
                canonical.read_text().splitlines(),
                vendored.read_text().splitlines(),
                lineterm="", n=0,
            )
            if line[:1] in "+-" and not line.startswith(("+++", "---"))
        ]
        print(f"    lines added or removed: {len(changed)}")
    else:
        print(f"    UNREACHABLE: {vendored} or {canonical} absent")

    print("\n== the receipt engine's refusal exit code (the wire says 2) ==")
    errors = root / RECEIPT_ERRORS
    if errors.is_file():
        match = re.search(r"^EXIT_REFUSED = (\d+)", errors.read_text(), re.MULTILINE)
        print(f"    EXIT_REFUSED = {match.group(1) if match else 'not declared'}")
    else:
        print(f"    UNREACHABLE: {errors} absent")


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else "ops")
    if not root.is_dir():
        print(
            f"root: expected a directory to census; found {root}; "
            "needed run from the repository checkout",
            file=sys.stderr,
        )
        return 2
    census(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
