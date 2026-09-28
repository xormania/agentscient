#!/usr/bin/env python3
"""extract/exitcodes.py — the `exitcodes` observation (SPEC §5.7), from
``errors.py`` and ``wf.py`` by AST.  Neither module is imported.

Facts per §5.7: ``constants``, ``exit_literals``, ``all_codes``.

Two readings are recorded in EXTRACTION-NOTES and repeated here because they
change what the numbers mean:

* the name filter (§5.7 "names containing EXIT or CODE") is applied
  case-insensitively, so class attributes spelled ``exit_code`` are seen;
* a class attribute whose value is a bare name is resolved against the
  module-level integer constants of the same file, and reported with the
  resolution in provenance.  A value that does not resolve to an int is
  emitted as ``{"unresolved"}`` rather than dropped.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

NAME = "exitcodes"
TARGETS = ("errors.py", "wf.py")
NAME_RE = re.compile(r"exit|code", re.IGNORECASE)


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


def int_literal(node):
    """An ``int`` written literally.  ``True``/``False`` are ints in Python
    but are not exit codes, so they are refused here."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int) \
            and not isinstance(node.value, bool):
        return True, node.value
    return False, None


def module_ints(tree):
    """``NAME -> int`` for every module-level ``NAME = <int literal>``."""
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            ok, value = int_literal(node.value)
            if not ok:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = value
    return out


def exit_call_name(call):
    """The callee spelling when this call is an exit-like call, else None."""
    if not isinstance(call, ast.Call):
        return None
    if isinstance(call.func, ast.Name):
        rendered = call.func.id
    elif isinstance(call.func, ast.Attribute):
        rendered = ast.unparse(call.func)
    else:
        return None
    tail = rendered.rsplit(".", 1)[-1]
    if rendered in ("sys.exit", "SystemExit") or "exit" in tail.lower():
        return rendered
    return None


def extract(root=None) -> dict:
    root = app_dir(root)
    constants, constant_prov = [], []
    literals, literal_prov, call_sites = set(), [], []
    missing = []

    for rel in TARGETS:
        path = root / rel
        if not path.exists():
            missing.append(rel)
            continue
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source)
        ints = module_ints(tree)

        # -- module-level NAME = <int> ------------------------------------
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            ok, value = int_literal(node.value)
            if not ok:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and NAME_RE.search(target.id):
                    constants.append({"name": target.id, "value": value,
                                      "file": rel})
                    constant_prov.append(prov(
                        rel, node,
                        "§5.7 module-level NAME = <int>, name matching"
                        " /exit|code/i", lines, name=target.id, value=value))

        # -- class attributes ---------------------------------------------
        for klass in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            for node in klass.body:
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if not NAME_RE.search(target.id):
                        continue
                    dotted = f"{klass.name}.{target.id}"
                    ok, value = int_literal(node.value)
                    if ok:
                        resolution = "int literal"
                    elif isinstance(node.value, ast.Name) and \
                            node.value.id in ints:
                        value = ints[node.value.id]
                        resolution = (f"{node.value.id} = {value}, resolved"
                                      f" against {rel}'s module constants")
                    else:
                        constants.append({
                            "name": dotted,
                            "value": {"unresolved":
                                      "the value is not an int literal and does"
                                      " not resolve to a module-level int"
                                      f" constant: {ast.unparse(node.value)}"},
                            "file": rel})
                        constant_prov.append(prov(
                            rel, node, "§5.7 class attribute, name matching"
                            " /exit|code/i, value unresolved", lines,
                            name=dotted))
                        continue
                    constants.append({"name": dotted, "value": value,
                                      "file": rel})
                    constant_prov.append(prov(
                        rel, node,
                        "§5.7 class attribute, name matching /exit|code/i",
                        lines, name=dotted, value=value, resolution=resolution))

        # -- ints passed to exit-like calls --------------------------------
        for node in ast.walk(tree):
            callee = exit_call_name(node)
            if callee is None:
                continue
            arguments = []
            for arg in node.args:
                ok, value = int_literal(arg)
                if ok:
                    literals.add(value)
                    arguments.append(value)
                    literal_prov.append(prov(
                        rel, node, "§5.7 int literal passed to an exit-like"
                        f" call ({callee})", lines, value=value))
                else:
                    arguments.append(f"<not an int literal: {ast.unparse(arg)}>")
            call_sites.append(prov(
                rel, node, "§5.7 exit-like call site, scanned for int literal"
                " arguments", lines, callee=callee, arguments=arguments))

    provenance = {
        "targets": list(TARGETS),
        "constants": constant_prov,
        "exit_literals": literal_prov,
        "exit_call_sites": call_sites,
        "readings": [
            ("the §5.7 name filter is applied case-insensitively (ADAPTED):"
            " spelled EXIT/CODE only, the 'and class attributes' half of the"
            " rule matches nothing in this tree"),
            "True/False are not counted as int literals",
        ],
    }
    if missing:
        provenance["missing_targets"] = sorted(missing)

    facts = {}
    if missing:
        facts["constants"] = {"unresolved": "not every §5.7 source could be"
                                            f" read: {', '.join(sorted(missing))}"}
        facts["exit_literals"] = dict(facts["constants"])
        facts["all_codes"] = dict(facts["constants"])
        return {"facts": facts, "provenance": provenance}

    if not constants:
        facts["constants"] = {"unresolved": "no module-level int constant and"
                                            " no class attribute in errors.py or"
                                            " wf.py has a name matching"
                                            " /exit|code/i"}
    else:
        constants.sort(key=lambda c: (c["file"], c["name"],
                                      json.dumps(c["value"], sort_keys=True)))
        facts["constants"] = constants

    # An empty exit_literals list is a resolved answer, not a gap: every
    # exit-like call site found is quoted in provenance.exit_call_sites with
    # the argument that was not an int literal.
    facts["exit_literals"] = sorted(literals)

    values = sorted({c["value"] for c in constants
                     if isinstance(c["value"], int)} | literals)
    if not values:
        facts["all_codes"] = {"unresolved": "neither source yielded an integer"
                                            " exit code"}
    else:
        facts["all_codes"] = values
    return {"facts": facts, "provenance": provenance}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    print(json.dumps(extract(argv[0] if argv else None), sort_keys=True,
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
