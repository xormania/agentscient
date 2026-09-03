#!/usr/bin/env python3
"""extract/commitmsg.py — the `commitmsg` observation (SPEC §5.10), from
``gitio.py`` by AST.  The module is read, never imported.

Facts per §5.10: ``trailer_keys``, ``subject_literals``, ``literals``.

ADAPTED, and it matters: the string-constant population includes the literal
segments of f-strings.  Every trailer in this module is written as an
f-string (``f"WO: {wo_id}"``), so the unadapted reading — top-level
``ast.Constant`` nodes only — would report a single trailer key and read as
a confident answer that the others do not exist.  Each literal's provenance
says whether it came from a plain constant or an f-string segment, and for
f-strings the reconstructed template (``wf({wo_id}/{stage}): {summary}``) is
carried in provenance so the adjudicator sees the whole message line.  The
templates are *not* mixed into the fact lists: those hold string constants
only, as §5.10 specifies.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

NAME = "commitmsg"
TARGET = "gitio.py"
TRAILER_RE = re.compile(r"^([A-Z][A-Za-z-]*):")
SUBJECT_MARK = "wf("


def app_dir(explicit=None) -> Path:
    if explicit is not None:
        return Path(explicit)
    return Path(__file__).resolve().parents[2]


def _span(node):
    end = getattr(node, "end_lineno", None) or node.lineno
    return node.lineno, end


def _lines(node) -> str:
    a, b = _span(node)
    return f"{a}-{b}"


def _text(lines, node) -> str:
    a, b = _span(node)
    return "\n".join(lines[a - 1:b])


def template(node: ast.JoinedStr) -> str:
    """An f-string rendered with ``{expr}`` in place of its interpolations."""
    out = []
    for part in node.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            out.append(part.value)
        elif isinstance(part, ast.FormattedValue):
            out.append("{" + ast.unparse(part.value) + "}")
        else:
            out.append("{…}")
    return "".join(out)


def constants(tree, lines, rel):
    """Every string constant of the file, each with where it came from.

    Yields ``(value, provenance)``.  Constants nested in an f-string are
    reported at the f-string's line range with the template beside them.
    """
    joined = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    joined[id(part)] = node
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        owner = joined.get(id(node))
        if owner is None:
            out.append((node.value, {
                "file": rel, "lines": _lines(node), "text": _text(lines, node),
                "rule": "§5.10 string constant of gitio.py", "kind": "constant",
            }))
        else:
            out.append((node.value, {
                "file": rel, "lines": _lines(owner), "text": _text(lines, owner),
                "rule": "§5.10 string constant of gitio.py, ADAPTED: an"
                        " f-string literal segment",
                "kind": "f-string-segment", "fstring_template": template(owner),
            }))
    return out


def collect(pairs, predicate, transform=None):
    """Sorted unique values matching ``predicate``, with one provenance entry
    per (value, site)."""
    values, entries = {}, []
    for value, entry in pairs:
        if not predicate(value):
            continue
        emitted = transform(value) if transform else value
        record = dict(entry)
        record["source_literal"] = value
        record["value"] = emitted
        values.setdefault(emitted, True)
        entries.append(record)
    entries.sort(key=lambda e: (e["value"], e["file"],
                                int(e["lines"].split("-")[0])))
    return sorted(values), entries


def extract(root=None) -> dict:
    root = app_dir(root)
    path = root / TARGET
    if not path.exists():
        gone = {"unresolved": f"{TARGET} is absent"}
        return {"facts": {"trailer_keys": dict(gone),
                          "subject_literals": dict(gone),
                          "literals": dict(gone)},
                "provenance": {"target": TARGET}}

    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    pairs = constants(tree, lines, TARGET)

    trailers, trailer_prov = collect(
        pairs, lambda v: TRAILER_RE.match(v) is not None,
        lambda v: TRAILER_RE.match(v).group(1))
    subjects, subject_prov = collect(pairs, lambda v: SUBJECT_MARK in v)
    every, literal_prov = collect(pairs, lambda v: ":" in v)

    facts = {}
    facts["trailer_keys"] = trailers or {
        "unresolved": "no string constant of gitio.py matches"
                      " /^[A-Z][A-Za-z-]*:/"}
    facts["subject_literals"] = subjects or {
        "unresolved": f"no string constant of gitio.py contains {SUBJECT_MARK!r}"}
    facts["literals"] = every or {
        "unresolved": "no string constant of gitio.py contains ':'"}

    provenance = {
        "target": TARGET,
        "trailer_keys": trailer_prov,
        "subject_literals": subject_prov,
        "literals": literal_prov,
        "readings": [
            ("f-string literal segments are part of the string-constant"
            " population (ADAPTED); every trailer in gitio.py is written as"
            " an f-string, so the unadapted reading would report only"
            " \"Source\""),
            "docstrings are string constants and are scanned like any other",
            ("reconstructed f-string templates are in provenance"
            " (fstring_template) and deliberately not in the fact lists"),
        ],
    }
    return {"facts": facts, "provenance": provenance}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    print(json.dumps(extract(argv[0] if argv else None), sort_keys=True,
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
