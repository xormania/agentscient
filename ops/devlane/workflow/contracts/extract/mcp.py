#!/usr/bin/env python3
"""extract/mcp.py — the `mcp` observation (SPEC §5.11), from
``mcp_server.py`` and ``mcp_launch.py`` by AST.  Neither is imported.

Facts per §5.11: ``server_imports``, ``launch_imports``, ``verb_literals``,
``uri_literals``.

"Local" is §5.11's own test: a name is local iff ``<name>.py`` exists in the
app directory.  The name recorded is the *module's* name, not the alias it
is bound to (``import chain as chainmod`` → ``chain``); the alias is in
provenance.  Imports made inside a function body count — an import is an
import wherever it is written — and are flagged ``scope: "function"``.

An import list that comes back empty is a resolved answer here, not a gap:
provenance.all_imports quotes every import statement of the file, local or
not, so "imports nothing local" is evidenced rather than defaulted.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

NAME = "mcp"
SERVER = "mcp_server.py"
LAUNCH = "mcp_launch.py"
URI_RE = re.compile(r"^[a-z]+://")

# §5.11 fixes this list; it is not derived from the code under inspection.
VERBS = ("init", "open", "claim", "release", "red", "green", "check",
         "outcome", "marker", "advance", "next", "status", "log", "commit",
         "verify", "export")


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


def prov(rel, node, rule, lines, **extra) -> dict:
    out = {"file": rel, "lines": _lines(node), "text": _text(lines, node),
           "rule": rule}
    out.update(extra)
    return out


def parse(root: Path, rel: str):
    path = root / rel
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return ast.parse(text), text.splitlines()


def function_lines(tree):
    """Line numbers that fall inside a function body — used only to label an
    import's scope in provenance."""
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
    return spans


def imports(root: Path, rel: str, tree, lines):
    """(sorted local module names, provenance, every import statement)."""
    local, entries, everything = {}, [], []
    spans = function_lines(tree)

    def scope(node):
        return "function" if any(a <= node.lineno <= b for a, b in spans) \
            else "module"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                everything.append({"statement": ast.unparse(node),
                                   "module": alias.name, "line": node.lineno})
                if (root / f"{alias.name}.py").exists():
                    local.setdefault(alias.name, True)
                    entries.append(prov(
                        rel, node, "§5.11 local import — <name>.py exists"
                        " beside the module", lines, module=alias.name,
                        alias=alias.asname, scope=scope(node)))
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ""
            everything.append({"statement": ast.unparse(node), "module": name,
                               "line": node.lineno, "level": node.level})
            if node.level == 0 and name and (root / f"{name}.py").exists():
                local.setdefault(name, True)
                entries.append(prov(
                    rel, node, "§5.11 local import — <name>.py exists beside"
                    " the module", lines, module=name,
                    names=[a.name for a in node.names], scope=scope(node)))
    entries.sort(key=lambda e: (e["module"], int(e["lines"].split("-")[0])))
    everything.sort(key=lambda e: (e["line"], e["module"]))
    return sorted(local), entries, everything


def string_constants(tree, lines, rel):
    """Every string constant, f-string segments included and flagged."""
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
        anchor = owner if owner is not None else node
        out.append((node.value, {
            "file": rel, "lines": _lines(anchor), "text": _text(lines, anchor),
            "kind": "f-string-segment" if owner is not None else "constant",
        }))
    return out


def extract(root=None) -> dict:
    root = app_dir(root)
    facts, provenance = {}, {"targets": [LAUNCH, SERVER]}

    server = parse(root, SERVER)
    launch = parse(root, LAUNCH)

    if server is None:
        gone = {"unresolved": f"{SERVER} is absent"}
        facts["server_imports"] = dict(gone)
        facts["verb_literals"] = dict(gone)
        facts["uri_literals"] = dict(gone)
    else:
        tree, lines = server
        names, entries, everything = imports(root, SERVER, tree, lines)
        facts["server_imports"] = names
        provenance["server_imports"] = entries
        provenance["server_all_imports"] = everything

        pairs = string_constants(tree, lines, SERVER)
        verbs, verb_prov = {}, []
        uris, uri_prov = {}, []
        for value, entry in pairs:
            if value in VERBS:
                verbs.setdefault(value, True)
                record = dict(entry)
                record["rule"] = ("§5.11 string constant equal to a §4 verb"
                                  " name (fixed list, not derived from code)")
                record["value"] = value
                verb_prov.append(record)
            if URI_RE.match(value):
                uris.setdefault(value, True)
                record = dict(entry)
                record["rule"] = "§5.11 string constant matching /^[a-z]+:\\/\\//"
                record["value"] = value
                uri_prov.append(record)
        verb_prov.sort(key=lambda e: (e["value"], int(e["lines"].split("-")[0])))
        uri_prov.sort(key=lambda e: (e["value"], int(e["lines"].split("-")[0])))
        facts["verb_literals"] = sorted(verbs) if verbs else {
            "unresolved": f"no string constant of {SERVER} equals any of the"
                          f" §4 verbs: {' '.join(VERBS)}"}
        facts["uri_literals"] = sorted(uris) if uris else {
            "unresolved": f"no string constant of {SERVER} matches"
                          " /^[a-z]+:\\/\\//"}
        provenance["verb_literals"] = verb_prov
        provenance["uri_literals"] = uri_prov
        provenance["verbs_considered"] = list(VERBS)

    if launch is None:
        facts["launch_imports"] = {"unresolved": f"{LAUNCH} is absent"}
    else:
        tree, lines = launch
        names, entries, everything = imports(root, LAUNCH, tree, lines)
        facts["launch_imports"] = names
        provenance["launch_imports"] = entries
        provenance["launch_all_imports"] = everything

    provenance["readings"] = [
        ("the module name is recorded, not the alias: `import chain as"
        " chainmod` contributes \"chain\""),
        ("imports written inside a function body are counted and flagged"
        " scope: \"function\""),
        ("an empty import list is a resolved answer evidenced by"
        " all_imports, not a default"),
    ]
    return {"facts": facts, "provenance": provenance}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    print(json.dumps(extract(argv[0] if argv else None), sort_keys=True,
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
