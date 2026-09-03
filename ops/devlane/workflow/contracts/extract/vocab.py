#!/usr/bin/env python3
"""extract/vocab.py — the `vocab` observation (SPEC §5.12), from
``checks/vocabulary_wall.py`` by AST.  The module is read, never imported.

Facts per §5.12: ``literals`` (every string constant, sorted unique,
f-string literal segments included and flagged in provenance) and
``joined`` (``"\\n".join(literals)``).

The contract's test — each reserved term is a substring of some literal —
runs against ``joined``, so note what "literal" includes here: docstrings
are string constants and are in; f-string segments are in and are flagged;
the reconstructed f-string template is in provenance only, because it is not
a constant.  If a term is spelled as a regex fragment rather than as plain
text, it will not be a substring of anything and the vet fails — which is
§5.12's stated GUESS working as intended, not a defect in this extractor.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

NAME = "vocab"
TARGET = "checks/vocabulary_wall.py"


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
    out = []
    for part in node.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            out.append(part.value)
        elif isinstance(part, ast.FormattedValue):
            out.append("{" + ast.unparse(part.value) + "}")
        else:
            out.append("{…}")
    return "".join(out)


def extract(root=None) -> dict:
    root = app_dir(root)
    path = root / TARGET
    if not path.exists():
        gone = {"unresolved": f"{TARGET} is absent"}
        return {"facts": {"literals": dict(gone), "joined": dict(gone)},
                "provenance": {"target": TARGET}}

    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)

    joined_owner = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    joined_owner[id(part)] = node

    values, entries = {}, []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        owner = joined_owner.get(id(node))
        anchor = owner if owner is not None else node
        record = {
            "file": TARGET, "lines": _lines(anchor),
            "text": _text(lines, anchor),
            "rule": "§5.12 string constant of the vocabulary wall"
                    + (", ADAPTED: an f-string literal segment"
                       if owner is not None else ""),
            "kind": "f-string-segment" if owner is not None else "constant",
            "value": node.value,
        }
        if owner is not None:
            record["fstring_template"] = template(owner)
        values.setdefault(node.value, True)
        entries.append(record)

    entries.sort(key=lambda e: (e["value"], int(e["lines"].split("-")[0])))
    literals = sorted(values)

    facts = {}
    if not literals:
        facts["literals"] = {"unresolved": f"{TARGET} holds no string constant"}
        facts["joined"] = {"unresolved": f"{TARGET} holds no string constant"}
    else:
        facts["literals"] = literals
        facts["joined"] = "\n".join(literals)

    provenance = {
        "target": TARGET,
        "literals": entries,
        "readings": [
            "docstrings are string constants and are included",
            ("f-string literal segments are included and flagged"
            " kind: \"f-string-segment\"; their reconstructed template is in"
            " fstring_template and is not itself a literal"),
            ("joined is \"\\n\".join(literals) over the sorted unique list, so"
            " a term spanning two literals is not a substring of it"),
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
