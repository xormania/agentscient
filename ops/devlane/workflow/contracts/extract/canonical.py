#!/usr/bin/env python3
"""extract/canonical.py — the `canonical` observation (SPEC §5.8), from
``canonical.py`` by AST.  The module is read, never imported.

Facts per §5.8: ``json_dumps_calls``, ``hashlib_algorithms``.

A keyword whose value is not a literal is recorded as the string
``"non-literal"``, exactly as §5.8 spells it.  Tuple and list literals are
rendered as JSON arrays — ``separators=(",", ":")`` becomes ``[",", ":"]`` —
because JSON has no tuple; the verbatim source is in provenance so the
distinction is not lost.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

NAME = "canonical"
TARGET = "canonical.py"
NON_LITERAL = "non-literal"


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


def literal(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (str, int, float, bool)) or node.value is None:
            return True, node.value
        return False, None
    if isinstance(node, (ast.Tuple, ast.List)):
        out = []
        for element in node.elts:
            ok, value = literal(element)
            if not ok:
                return False, None
            out.append(value)
        return True, out
    if isinstance(node, ast.Dict):
        out = {}
        for key, value in zip(node.keys, node.values, strict=False):
            if key is None:
                return False, None
            ok_k, k = literal(key)
            ok_v, v = literal(value)
            if not (ok_k and ok_v) or not isinstance(k, str):
                return False, None
            out[k] = v
        return True, out
    return False, None


def json_aliases(tree):
    """Names under which the stdlib ``json`` module and its ``dumps`` are
    reachable in this file."""
    module_names, dumps_names = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "json":
                    module_names.add(alias.asname or "json")
        if isinstance(node, ast.ImportFrom) and node.module == "json":
            for alias in node.names:
                if alias.name == "dumps":
                    dumps_names.add(alias.asname or "dumps")
    return module_names, dumps_names


def hashlib_aliases(tree):
    module_names, direct = set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "hashlib":
                    module_names.add(alias.asname or "hashlib")
        if isinstance(node, ast.ImportFrom) and node.module == "hashlib":
            for alias in node.names:
                direct[alias.asname or alias.name] = alias.name
    return module_names, direct


def extract(root=None) -> dict:
    root = app_dir(root)
    path = root / TARGET
    if not path.exists():
        return {"facts": {"json_dumps_calls": {"unresolved":
                                               f"{TARGET} is absent"},
                          "hashlib_algorithms": {"unresolved":
                                                 f"{TARGET} is absent"}},
                "provenance": {"target": TARGET}}

    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    modules, dumps_names = json_aliases(tree)
    hash_modules, hash_direct = hashlib_aliases(tree)

    calls, call_prov = [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        matched = None
        if isinstance(node.func, ast.Attribute) and node.func.attr == "dumps" \
                and isinstance(node.func.value, ast.Name) \
                and node.func.value.id in modules:
            matched = ast.unparse(node.func)
        elif isinstance(node.func, ast.Name) and node.func.id in dumps_names:
            matched = node.func.id
        if matched is None:
            continue
        keywords, rendered = {}, {}
        for keyword in node.keywords:
            key = keyword.arg if keyword.arg is not None else "**"
            ok, value = literal(keyword.value)
            keywords[key] = value if ok else NON_LITERAL
            rendered[key] = ast.unparse(keyword.value)
        record = {"line": node.lineno, "keywords": keywords}
        calls.append(record)
        call_prov.append(prov(
            TARGET, node, "§5.8 a call to json.dumps; keywords read as"
            " literals, non-literals recorded as \"non-literal\"", lines,
            callee=matched, keyword_source=rendered,
            positional=[ast.unparse(a) for a in node.args]))

    algorithms, algorithm_prov = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id in hash_modules:
            algorithms.add(node.attr)
            algorithm_prov.append(prov(
                TARGET, node, "§5.8 attribute name used on the hashlib module",
                lines, algorithm=node.attr))
    for local, original in sorted(hash_direct.items()):
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == local and \
                    isinstance(node.ctx, ast.Load):
                algorithms.add(original)
                algorithm_prov.append(prov(
                    TARGET, node, "§5.8 hashlib name imported directly and"
                    " used", lines, algorithm=original))
                break

    facts = {}
    if calls:
        calls.sort(key=lambda c: c["line"])
        facts["json_dumps_calls"] = calls
    else:
        facts["json_dumps_calls"] = {
            "unresolved": f"no call to json.dumps was found in {TARGET}"
                          f" (json imported as: {', '.join(sorted(modules)) or 'not at all'})"}
    if algorithms:
        facts["hashlib_algorithms"] = sorted(algorithms)
    else:
        facts["hashlib_algorithms"] = {
            "unresolved": f"hashlib is not used by name in {TARGET}"}

    provenance = {
        "target": TARGET,
        "json_dumps_calls": call_prov,
        "hashlib_algorithms": sorted(algorithm_prov,
                                     key=lambda p: (p["lines"], p["rule"])),
        "readings": [
            ("tuple/list keyword values are rendered as JSON arrays; the"
            " verbatim source is in text and keyword_source"),
            ("positional arguments are not part of the §5.8 shape and are"
            " carried in provenance only"),
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
