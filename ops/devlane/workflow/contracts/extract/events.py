#!/usr/bin/env python3
"""extract/events.py — the `events` observation (SPEC §5.9), from every
non-test ``.py`` of the app by AST.  Nothing is imported.

Facts per §5.9: ``types``, ``shapes``.

"Non-test" is resolved mechanically as: every ``*.py`` under
`ops/devlane/workflow`, minus anything under ``tests/``, ``contracts/`` or
``__pycache__/``, minus files whose basename starts with ``test_``.  The
resulting file list is in provenance so the population is auditable.

§5.9's shapes rule is ADAPTED in two places, both recorded per shape in
provenance.

1. RESOLUTION (widening).  A dict literal's ``"type"`` value is accepted when
   it is a string constant **or** when it is a name/attribute that resolves to
   a module-level string constant of this file or of a sibling module imported
   by it (``chainmod.WO_OPENED`` → ``chain.py``'s ``WO_OPENED = "wo.opened"``).
   The unadapted rule would see almost none of this app's event dicts.  A
   ``"type"`` that resolves to neither is emitted as ``{"unresolved"}``, not
   dropped: the receipt dict is the shape that matters most and it is the one
   whose type is a function parameter.

2. NOT-AN-EVENT (narrowing).  §5.9's rule keys on a dict literal carrying a
   key spelled ``"type"``, which is also how JSON Schema spells a type
   descriptor and how a read view spells the field it copied.  A site is
   dropped from ``shapes`` **only** when the extractor can positively prove it
   cannot be an event, by one of two tests:

     E1  the ``"type"`` value can never be a ``str`` — a dict/list/set/tuple
         display, a comprehension, a lambda, or a non-string constant.
         ``Chain.append`` (chain.py:192) refuses any event whose ``type`` is
         not a non-empty ``str``, so no runtime makes such a dict an event.
     E2  the dict is a pure projection of one other object: every value in it
         is a constant-key read (``B["k"]`` or ``B.get("k")``) of the same
         base ``B``, and the ``"type"`` value is that object's own ``"type"``.
         It re-describes an event it was handed; it does not name a type.

   Both tests are proofs of non-eventhood.  Failing to *prove* a dict IS an
   event is never a reason to drop it — "we could not look" must not be
   mistaken for "there is nothing there".  Every dropped site is quoted in
   ``provenance.excluded`` with the test that dropped it, so the narrowing is
   auditable and reversible.

Constructor evidence (``provenance.shapes[*].constructor_evidence``) records
when a dict demonstrably reaches ``chain.append`` — directly, through a local
name, or as the return value of a helper whose same-file callers append it.
It is EVIDENCE ONLY: it never includes and never excludes.  A dict with no
such evidence is still a shape.

Unresolvable-but-real types are never guessed.  Where a ``"type"`` is a
parameter or a branch-assigned local, provenance names the argument
expressions or branch values the population supplies, but the fact stays
``{"unresolved"}`` — those sites have more than one value, and §5.9's `type`
is one string.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

NAME = "events"
TYPE_RE = re.compile(r"^[a-z]+\.[a-z_]+$")
SKIP_DIRS = ("tests", "contracts", "__pycache__")

#: Node classes whose value can never be a ``str``.  See E1.
NEVER_A_STRING = (ast.Dict, ast.List, ast.Set, ast.Tuple, ast.DictComp,
                  ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.Lambda)


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


def sources(root: Path):
    """Every non-test .py of the app, as sorted posix paths relative to it."""
    out = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if rel.name.startswith("test_"):
            continue
        out.append(rel.as_posix())
    return sorted(out)


class Tree:
    """One parsed file: its lines, its module-level string constants, its
    sibling-module aliases, and a child→parent map."""

    def __init__(self, root: Path, rel: str):
        self.rel = rel
        text = (root / rel).read_text(encoding="utf-8")
        self.lines = text.splitlines()
        self.tree = ast.parse(text)
        self.parents = {}
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                self.parents[child] = node
        self.strings = {}
        for node in self.tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.strings[target.id] = (node.value.value, node)
        self.aliases = {}
        here = (root / rel).parent
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if (here / f"{alias.name}.py").exists():
                        target = (here / f"{alias.name}.py").relative_to(root)
                        self.aliases[alias.asname or alias.name] = target.as_posix()

    def enclosing_function(self, node):
        current = self.parents.get(node)
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current
            current = self.parents.get(current)
        return None


def resolve_type(trees, tree: Tree, node):
    """(value, how) for a dict's ``"type"`` value, or (None, why-not)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, "string constant"
    if isinstance(node, ast.Name) and node.id in tree.strings:
        value, origin = tree.strings[node.id]
        return value, (f"{node.id} = {value!r} at {tree.rel}:{origin.lineno}")
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        rel = tree.aliases.get(node.value.id)
        other = trees.get(rel) if rel else None
        if other is not None and node.attr in other.strings:
            value, origin = other.strings[node.attr]
            return value, (f"{node.value.id}.{node.attr} = {value!r} at"
                           f" {rel}:{origin.lineno}")
        if rel is None:
            return None, (f"{ast.unparse(node)} — {node.value.id} is not a"
                          " sibling module imported here")
        return None, (f"{ast.unparse(node)} — {rel} has no module-level"
                      f" string constant {node.attr}")
    return None, f"{ast.unparse(node)} is not a string constant or a name for one"


# -- the constructor / non-constructor test --------------------------------

def key_read(node):
    """``(base, key)`` when ``node`` reads one constant string key out of some
    other object — ``B["k"]``, ``B.get("k")``, ``B.get("k", default)`` — else
    ``(None, None)``."""
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
            and isinstance(node.slice.value, str):
        return node.value, node.slice.value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == "get" and not node.keywords \
            and 1 <= len(node.args) <= 2 \
            and isinstance(node.args[0], ast.Constant) \
            and isinstance(node.args[0].value, str):
        return node.func.value, node.args[0].value
    return None, None


def not_an_event(node: ast.Dict, type_node):
    """``(test, why)`` when this dict is PROVED not to be an event
    constructor, else ``None``.  Nothing else drops a site."""
    # E1 — the "type" value can never be a str, so Chain.append would refuse
    # it (chain.py:192: `if not isinstance(event.get("type"), str) ...`).
    if isinstance(type_node, NEVER_A_STRING):
        kind = type(type_node).__name__
        return "E1", (f'its "type" value is a {kind} node'
                      f" ({ast.unparse(type_node)[:60]}...), which can never be"
                      " a str; chain.py:192 refuses any event whose type is not"
                      " a non-empty str, so no runtime makes this dict an"
                      " event — it is a JSON Schema type descriptor, a key"
                      ' literally named "type"')
    if isinstance(type_node, ast.Constant) and not isinstance(type_node.value, str):
        return "E1", (f'its "type" value is the non-string constant'
                      f" {type_node.value!r}; chain.py:192 refuses any event"
                      " whose type is not a non-empty str")
    # E2 — a pure projection of one other object, type included.
    base, key = key_read(type_node)
    if base is None or key != "type":
        return None
    base_src = ast.unparse(base)
    for entry, value in zip(node.keys, node.values, strict=False):
        if entry is None:
            return None                      # {**expansion}: not a projection
        other_base, _other_key = key_read(value)
        if other_base is None or ast.unparse(other_base) != base_src:
            return None                      # originates a value of its own
    fields = ", ".join(
        f"{ast.unparse(k)}: {ast.unparse(v)}" for k, v in
        zip(node.keys, node.values, strict=False))
    return "E2", (f"every value in this dict is a constant-key read of the same"
                  f" object {base_src} ({fields}), the \"type\" among them: it"
                  f" re-describes an event it was handed rather than naming a"
                  f" type, so it reads an event rather than constructing one")


def is_chain_append(node) -> bool:
    """A call to ``<something>.chain.append(...)`` / ``chain.append(...)``."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "append"
            and ast.unparse(node.func).endswith("chain.append"))


def returns_node(function, node, name) -> bool:
    """The function hands this dict back to its caller."""
    for sub in ast.walk(function):
        if not isinstance(sub, ast.Return) or sub.value is None:
            continue
        if sub.value is node:
            return True
        if name is not None and isinstance(sub.value, ast.Name) \
                and sub.value.id == name:
            return True
    return False


def constructor_evidence(tree: Tree, node: ast.Dict, name, function):
    """Where this dict demonstrably reaches ``chain.append``.  EVIDENCE ONLY —
    it never includes a site and never excludes one."""
    found = set()
    parent = tree.parents.get(node)
    if is_chain_append(parent) and any(arg is node for arg in parent.args):
        found.add(f"{tree.rel}:{parent.lineno} appends this dict literal to"
                  " the chain")
    if function is not None:
        if name is not None:
            for sub in ast.walk(function):
                if is_chain_append(sub) and any(
                        isinstance(arg, ast.Name) and arg.id == name
                        for arg in sub.args):
                    found.add(f"{tree.rel}:{sub.lineno} appends {name} to the"
                              " chain")
        if returns_node(function, node, name):
            for sub in ast.walk(tree.tree):
                if not is_chain_append(sub):
                    continue
                for arg in sub.args:
                    if isinstance(arg, ast.Call) and \
                            isinstance(arg.func, ast.Name) and \
                            arg.func.id == function.name:
                        found.add(f"{tree.rel}:{sub.lineno} appends"
                                  f" {function.name}(...) to the chain")
    return sorted(found)


def parameter_arguments(trees, tree: Tree, function, param: str):
    """Every distinct expression this file's callers pass for ``param``, with
    its resolution when it has one.  NOT a resolution of the shape: it is the
    set of values the population supplies, which is more than one."""
    if function is None:
        return None
    positional = [a.arg for a in
                  getattr(function.args, "posonlyargs", []) + function.args.args]
    if param not in positional:
        return None
    index = positional.index(param)
    out = set()
    for sub in ast.walk(tree.tree):
        if not isinstance(sub, ast.Call) or not isinstance(sub.func, ast.Name) \
                or sub.func.id != function.name:
            continue
        supplied = None
        if len(sub.args) > index:
            supplied = sub.args[index]
        else:
            for keyword in sub.keywords:
                if keyword.arg == param:
                    supplied = keyword.value
        if supplied is None:
            continue
        value, _how = resolve_type(trees, tree, supplied)
        text = ast.unparse(supplied)
        out.add(text if value is None else f"{text} = {value!r}")
    return sorted(out) or None


def local_assignments(trees, tree: Tree, function, name: str):
    """Every value assigned to a local ``name`` inside ``function``, with its
    resolution when it has one.  Also not a resolution: branches disagree."""
    if function is None:
        return None
    out = set()
    for sub in ast.walk(function):
        if not isinstance(sub, ast.Assign):
            continue
        for target in sub.targets:
            if isinstance(target, ast.Name) and target.id == name:
                value, _how = resolve_type(trees, tree, sub.value)
                text = f"{ast.unparse(sub.value)} at {tree.rel}:{sub.lineno}"
                out.add(text if value is None else
                        f"{ast.unparse(sub.value)} = {value!r} at"
                        f" {tree.rel}:{sub.lineno}")
    return sorted(out) or None


def dict_keys(tree: Tree, node: ast.Dict):
    """Literal string keys, plus notes for anything not literal."""
    keys, notes = [], []
    for key, value in zip(node.keys, node.values, strict=False):
        if key is None:
            notes.append(f"{{**{ast.unparse(value)}}} — keys not statically known")
            continue
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.append(key.value)
        else:
            notes.append(f"non-literal key {ast.unparse(key)}")
    return keys, notes


def bound_name(tree: Tree, node: ast.Dict):
    """The name this dict literal is assigned to, if any."""
    parent = tree.parents.get(node)
    if isinstance(parent, ast.Assign) and len(parent.targets) == 1 \
            and isinstance(parent.targets[0], ast.Name):
        return parent.targets[0].id
    return None


def extract(root=None) -> dict:
    root = app_dir(root)
    files = sources(root)
    if not files:
        return {"facts": {"types": {"unresolved": "no non-test .py found"},
                          "shapes": {"unresolved": "no non-test .py found"}},
                "provenance": {"files": []}}

    trees = {rel: Tree(root, rel) for rel in files}

    # -- types -------------------------------------------------------------
    seen = {}
    type_prov = []
    for rel in files:
        tree = trees[rel]
        for node in ast.walk(tree.tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and TYPE_RE.match(node.value):
                bucket = seen.setdefault(node.value, set())
                if rel not in bucket:
                    bucket.add(rel)
                    type_prov.append(prov(
                        rel, node, "§5.9 types: string constant matching"
                        " /^[a-z]+\\.[a-z_]+$/", tree.lines, value=node.value))
    types = [{"value": value, "files": sorted(files_)}
             for value, files_ in sorted(seen.items())]

    # -- shapes ------------------------------------------------------------
    shapes, shape_prov, excluded = [], [], []
    for rel in files:
        tree = trees[rel]
        for node in ast.walk(tree.tree):
            if not isinstance(node, ast.Dict):
                continue
            type_node = None
            for key, value in zip(node.keys, node.values, strict=False):
                if isinstance(key, ast.Constant) and key.value == "type":
                    type_node = value
            if type_node is None:
                continue
            keys, notes = dict_keys(tree, node)
            function = tree.enclosing_function(node)
            name = bound_name(tree, node)

            proof = not_an_event(node, type_node)
            if proof is not None:
                test, why = proof
                excluded.append(prov(
                    rel, node,
                    f"§5.9 shapes, NOT AN EVENT ({test}): a dict literal"
                    ' carrying a "type" key is a shape unless it is proved not'
                    " to be an event constructor",
                    tree.lines,
                    type_value=ast.unparse(type_node),
                    literal_keys=sorted(keys),
                    enclosing_function=getattr(function, "name", None),
                    test=test, why=why))
                continue

            value, how = resolve_type(trees, tree, type_node)
            subscripts, updates = [], []
            if name is not None and function is not None:
                for sub in ast.walk(function):
                    if isinstance(sub, ast.Assign):
                        for target in sub.targets:
                            if isinstance(target, ast.Subscript) and \
                                    isinstance(target.value, ast.Name) and \
                                    target.value.id == name and \
                                    isinstance(target.slice, ast.Constant) and \
                                    isinstance(target.slice.value, str):
                                subscripts.append(target.slice.value)
                    if isinstance(sub, ast.Call) and \
                            isinstance(sub.func, ast.Attribute) and \
                            sub.func.attr == "update" and \
                            isinstance(sub.func.value, ast.Name) and \
                            sub.func.value.id == name:
                        updates.append(ast.unparse(sub))
            merged = sorted(set(keys) | set(subscripts))
            evidence = constructor_evidence(tree, node, name, function)

            unresolved = None
            if value is None:
                unresolved = f'the "type" value does not resolve to a string: {how}'
                if isinstance(type_node, ast.Name):
                    supplied = parameter_arguments(trees, tree, function,
                                                   type_node.id)
                    if supplied is not None:
                        unresolved += (
                            f"; {type_node.id} is a parameter of"
                            f" {function.name}, and this file's callers supply"
                            f" {len(supplied)} different values"
                            f" ({'; '.join(supplied)}), so there is no one"
                            " string to report")
                    else:
                        assigned = local_assignments(trees, tree, function,
                                                     type_node.id)
                        if assigned is not None:
                            unresolved += (
                                f"; {type_node.id} is a local of"
                                f" {function.name} assigned"
                                f" {len(assigned)} different values"
                                f" ({'; '.join(assigned)}), so there is no one"
                                " string to report")
                if evidence:
                    unresolved += ("; the site stays because it IS an event"
                                   " constructor — " + "; ".join(evidence))
                else:
                    unresolved += ("; the site stays because nothing proves it"
                                   " is not an event constructor")

            record = {
                "type": value if value is not None else {"unresolved": unresolved},
                "keys": merged,
                "file": rel,
                "line": node.lineno,
            }
            shapes.append(record)
            entry = prov(rel, node,
                         "§5.9 shapes: dict literal carrying a \"type\" key,"
                         " not proved to be a non-event",
                         tree.lines, type_resolution=how,
                         literal_keys=sorted(keys),
                         subscript_keys=sorted(set(subscripts)),
                         bound_to=name,
                         enclosing_function=getattr(function, "name", None))
            if evidence:
                entry["constructor_evidence"] = evidence
            if notes:
                entry["open_keys"] = sorted(set(notes))
            if updates:
                entry["updates"] = sorted(set(updates))
            shape_prov.append(entry)

    shapes.sort(key=lambda s: (s["type"] if isinstance(s["type"], str)
                               else "￿", s["file"], s["line"]))
    shape_prov.sort(key=lambda p: (p["file"], int(p["lines"].split("-")[0])))
    excluded.sort(key=lambda p: (p["file"], int(p["lines"].split("-")[0])))
    type_prov.sort(key=lambda p: (p["file"], int(p["lines"].split("-")[0]),
                                  p["value"]))

    facts = {}
    facts["types"] = types or {
        "unresolved": "no string constant in any non-test .py matches"
                      " /^[a-z]+\\.[a-z_]+$/"}
    facts["shapes"] = shapes or {
        "unresolved": "no dict literal with a \"type\" key survived the"
                      " not-an-event tests"}
    provenance = {
        "files": files,
        "types": type_prov,
        "shapes": shape_prov,
        "excluded": excluded,
        "readings": [
            ("§5.9's own warning holds: the /^[a-z]+\\.[a-z_]+$/ regex also"
            " matches filenames and any other dotted lowercase literal;"
            " every hit is quoted so the contract's documented ⊆ observed"
            " test can be read against its source"),
            ("a type value that is a name or attribute is resolved against"
            " module-level string constants of this file or of a sibling"
            " module imported by it (ADAPTED — see the module docstring)"),
            ("keys are sorted; open_keys records {**expansion} and updates"
            " records .update(...) on the bound name, both of which mean the"
            " key list is a lower bound for that shape"),
            ("a site leaves shapes only on proof that it is not an event"
            " constructor (NARROWED — E1: the \"type\" value can never be a"
            " str, which chain.py:192 refuses; E2: every value in the dict is"
            " a constant-key read of one same other object, the \"type\""
            " included, so the dict re-describes an event rather than naming"
            " one). Every dropped site is quoted in provenance.excluded"),
            ("inability to prove a dict IS an event is NOT one of those tests."
            " constructor_evidence records reaching chain.append when it can"
            " be shown, but a shape with no such evidence still stands: \"we"
            " could not look\" must not read as \"there is nothing there\""),
            ("shapes therefore stays deliberately over-inclusive. It still"
            " holds JSON Schema fragments whose \"type\" is a plain string"
            " (mcp_server.py's \"object\"/\"string\"/\"array\"/\"integer\"/"
            "\"boolean\") and MCP content blocks (\"text\"). Separating those"
            " from a real bare-word event type such as chain.py's OUTCOME ="
            " \"outcome\" would need the known-type vocabulary, and PLAN §6"
            " requires a new event type to cost zero engine changes — a"
            " vocabulary filter would silently drop exactly the new type it"
            " is most important to see. Over-inclusion is auditable from the"
            " quoted text; a wrong exclusion is not"),
            ("a \"type\" that is a parameter or a branch-assigned local stays"
            " {\"unresolved\"}. Provenance names the values the population"
            " supplies, because that is evidence the site is a constructor,"
            " but it is not a resolution: those sites have more than one"
            " value and §5.9's shape type is one string"),
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
