#!/usr/bin/env python3
"""extract/cli.py — the `cli` observation (SPEC §5.6), from ``wf.py`` by AST.

Never imports and never runs ``wf.py``: the parser is reconstructed by
reading ``build_parser`` statement by statement.

Emits ``{"facts": {...}, "provenance": {...}}``.  Facts follow §5.6:

    global_arguments, commands (name/arguments/next_json_keys/helpers_applied),
    env_literals

Any rule that cannot be resolved emits ``{"unresolved": "<why>"}`` rather
than a shape that would read as a confident answer.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

NAME = "cli"
TARGET = "wf.py"
ENV_RE = re.compile(r"^WF_[A-Z_]+$")
MAX_DEPTH = 5


# --------------------------------------------------------------------------
# source access + provenance


def app_dir(explicit=None) -> Path:
    """`ops/devlane/workflow` — the parent of contracts/."""
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


# --------------------------------------------------------------------------
# literals


def literal(node):
    """(resolved, value) for the literal forms argparse calls actually use."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (str, int, float, bool)) or node.value is None:
            return True, node.value
        return False, None
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
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
            ok_k, k = literal(key) if key is not None else (False, None)
            ok_v, v = literal(value)
            if not (ok_k and ok_v) or not isinstance(k, str):
                return False, None
            out[k] = v
        return True, out
    return False, None


def kwarg(call, name):
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def kw_literal(call, name, unparsed_prefix):
    """A keyword's literal value, ``None`` when absent, ``{"unresolved"}``
    when present but not a literal — an absent flag and an unreadable one are
    different observations."""
    node = kwarg(call, name)
    if node is None:
        return None
    ok, value = literal(node)
    if ok:
        return value
    return {"unresolved": f"{unparsed_prefix}{name}= is not a literal:"
                          f" {ast.unparse(node)}"}


def env_from_default(call):
    """The env var a ``default=`` reads, when it reads one."""
    node = kwarg(call, "default")
    if node is None:
        return None
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            attr, args = sub.func.attr, sub.args
            base = ast.unparse(sub.func.value)
            if (attr == "get" and base in ("os.environ", "environ")) and args:
                ok, value = literal(args[0])
                if ok and isinstance(value, str):
                    return value
            if attr == "getenv" and args:
                ok, value = literal(args[0])
                if ok and isinstance(value, str):
                    return value
        if (isinstance(sub, ast.Subscript)
                and ast.unparse(sub.value) in ("os.environ", "environ")):
            ok, value = literal(sub.slice)
            if ok and isinstance(value, str):
                return value
    return None


# --------------------------------------------------------------------------
# add_argument -> a record in the §5.6 shape


def argument_record(call, *, is_global):
    """§5.6 argument shape.  Positionals carry ``positional``; options carry
    ``flags``."""
    names = []
    non_literal = []
    for arg in call.args:
        ok, value = literal(arg)
        if ok and isinstance(value, str):
            names.append(value)
        else:
            non_literal.append(ast.unparse(arg))
    flags = [n for n in names if n.startswith("-")]
    positionals = [n for n in names if not n.startswith("-")]

    record = {}
    if non_literal and not names:
        record["flags"] = {"unresolved": "add_argument name is not a string"
                                         f" literal: {', '.join(non_literal)}"}
    elif flags:
        record["flags"] = flags
    elif positionals:
        record["positional"] = positionals[0]
    else:
        record["flags"] = {"unresolved": "add_argument names no option string"
                                         " and no positional"}

    record["action"] = kw_literal(call, "action", "")
    record["nargs"] = kw_literal(call, "nargs", "")
    record["choices"] = kw_literal(call, "choices", "")
    if is_global:
        dest = kw_literal(call, "dest", "")
        record["dest"] = dest if dest is not None else None
        record["default_env"] = env_from_default(call)
    else:
        record["required"] = kw_literal(call, "required", "")
    return record


def sort_key(record):
    if "positional" in record:
        return (1, str(record["positional"]))
    flags = record.get("flags")
    if isinstance(flags, list) and flags:
        return (0, flags[0])
    return (2, json.dumps(flags, sort_keys=True))


# --------------------------------------------------------------------------
# payload-key resolution (next_json_keys)


class Modules:
    """Parses sibling modules on demand.  Reads them; never imports them."""

    def __init__(self, root: Path):
        self.root = root
        self._cache = {}

    def get(self, rel):
        if rel not in self._cache:
            path = self.root / rel
            if not path.exists():
                self._cache[rel] = None
            else:
                text = path.read_text(encoding="utf-8")
                self._cache[rel] = (ast.parse(text), text.splitlines())
        return self._cache[rel]

    def aliases(self, rel):
        """``alias -> <module>.py`` for modules that live beside wf.py."""
        parsed = self.get(rel)
        out = {}
        if parsed is None:
            return out
        for node in ast.walk(parsed[0]):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if (self.root / f"{alias.name}.py").exists():
                        out[alias.asname or alias.name] = f"{alias.name}.py"
        return out

    def function(self, rel, name):
        parsed = self.get(rel)
        if parsed is None:
            return None
        for node in parsed[0].body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name == name:
                return node
        return None


def payload_keys(mods: Modules, expr, rel, func, depth=0, seen=None):
    """Keys of the object ``expr`` denotes, following dict literals, the name
    it was built under, and one call hop at a time into sibling modules.

    Returns ``(keys, notes)`` — notes record every hop that could not be
    followed, so a partial answer is never silently presented as complete.
    """
    keys, notes = set(), []
    seen = set() if seen is None else seen
    if depth > MAX_DEPTH:
        notes.append(f"{rel}: depth limit at {ast.unparse(expr)[:60]}")
        return keys, notes

    if isinstance(expr, ast.Dict):
        for key, value in zip(expr.keys, expr.values, strict=False):
            if key is None:                      # {**other}
                sub_keys, sub_notes = payload_keys(mods, value, rel, func,
                                                   depth + 1, seen)
                keys |= sub_keys
                notes += sub_notes
                continue
            ok, name = literal(key)
            if ok and isinstance(name, str):
                keys.add(name)
            else:
                notes.append(f"{rel}:{key.lineno}: non-literal dict key"
                             f" {ast.unparse(key)}")
        return keys, notes

    if isinstance(expr, ast.Name) and func is not None:
        target = expr.id
        marker = (rel, getattr(func, "name", "?"), target)
        if marker in seen:
            return keys, notes
        seen = seen | {marker}
        found = False
        for node in ast.walk(func):
            if isinstance(node, ast.Assign):
                for dest in node.targets:
                    if isinstance(dest, ast.Name) and dest.id == target:
                        found = True
                        sub_keys, sub_notes = payload_keys(
                            mods, node.value, rel, func, depth + 1, seen)
                        keys |= sub_keys
                        notes += sub_notes
                    if isinstance(dest, ast.Subscript) and \
                            isinstance(dest.value, ast.Name) and \
                            dest.value.id == target:
                        ok, name = literal(dest.slice)
                        if ok and isinstance(name, str):
                            keys.add(name)
                            found = True
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "update" \
                    and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == target and node.args:
                found = True
                sub_keys, sub_notes = payload_keys(mods, node.args[0], rel, func,
                                                   depth + 1, seen)
                keys |= sub_keys
                notes += sub_notes
        if not found:
            notes.append(f"{rel}: no assignment to {target} found in"
                         f" {getattr(func, 'name', '?')}")
        return keys, notes

    if isinstance(expr, ast.Call):
        callee_rel, callee_name = None, None
        if isinstance(expr.func, ast.Name):
            callee_rel, callee_name = rel, expr.func.id
        elif isinstance(expr.func, ast.Attribute) and \
                isinstance(expr.func.value, ast.Name):
            callee_rel = mods.aliases(rel).get(expr.func.value.id)
            callee_name = expr.func.attr
        if callee_rel is None or callee_name is None:
            notes.append(f"{rel}:{expr.lineno}: cannot follow"
                         f" {ast.unparse(expr.func)}")
            return keys, notes
        marker = (callee_rel, callee_name)
        if marker in seen:
            return keys, notes
        seen = seen | {marker}
        target = mods.function(callee_rel, callee_name)
        if target is None:
            notes.append(f"{rel}:{expr.lineno}: {callee_rel}:{callee_name} is"
                         " not a module-level function here")
            return keys, notes
        returns = [n for n in ast.walk(target)
                   if isinstance(n, ast.Return) and n.value is not None]
        if not returns:
            notes.append(f"{callee_rel}:{callee_name} returns nothing literal")
        for node in returns:
            sub_keys, sub_notes = payload_keys(mods, node.value, callee_rel,
                                               target, depth + 1, seen)
            keys |= sub_keys
            notes += sub_notes
        return keys, notes

    notes.append(f"{rel}:{getattr(expr, 'lineno', 0)}: unhandled expression"
                 f" {type(expr).__name__}")
    return keys, notes


def emit_payloads(mods: Modules, rel, func):
    """Every ``ctx.emit(<payload>, …)`` in ``func``, resolved."""
    keys, notes, sites = set(), [], []
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "emit" and node.args:
            sites.append(node)
            sub_keys, sub_notes = payload_keys(mods, node.args[0], rel, func)
            keys |= sub_keys
            notes += sub_notes
    return keys, notes, sites


# --------------------------------------------------------------------------
# the parser walk


def parser_classes(tree):
    """Classes in wf.py that are argparse.ArgumentParser subclasses."""
    out = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if ast.unparse(base) in ("argparse.ArgumentParser",
                                         "ArgumentParser"):
                    out.add(node.name)
    return out


def is_parser_call(node, classes):
    if not isinstance(node, ast.Call):
        return False
    name = ast.unparse(node.func)
    return name in ("argparse.ArgumentParser", "ArgumentParser") or name in classes


def helper_arguments(tree, helper_name):
    """``add_argument`` calls a module-level helper makes on its first
    parameter — one level, statically, per §5.6."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == helper_name:
            params = node.args.posonlyargs + node.args.args
            if not params:
                return node, []
            first = params[0].arg
            calls = [c for c in ast.walk(node)
                     if isinstance(c, ast.Call)
                     and isinstance(c.func, ast.Attribute)
                     and c.func.attr == "add_argument"
                     and isinstance(c.func.value, ast.Name)
                     and c.func.value.id == first]
            calls.sort(key=lambda c: c.lineno)
            return node, calls
    return None, None


def extract(root=None) -> dict:
    root = app_dir(root)
    path = root / TARGET
    if not path.exists():
        gone = {"unresolved": f"{TARGET} is absent"}
        return {"facts": {"global_arguments": dict(gone),
                          "commands": dict(gone),
                          "env_literals": dict(gone)},
                "provenance": {"target": TARGET}}
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    mods = Modules(root)

    facts, provenance = {}, {"target": TARGET, "notes": []}

    # -- env literals ------------------------------------------------------
    env, env_prov = {}, []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and ENV_RE.match(node.value):
            env.setdefault(node.value, node)
    for value in sorted(env):
        env_prov.append(prov(TARGET, env[value], "§5.6 env_literals:"
                             " /^WF_[A-Z_]+$/ string constant", lines,
                             value=value))
    facts["env_literals"] = sorted(env)
    provenance["env_literals"] = env_prov
    if not env:
        facts["env_literals"] = {
            "unresolved": "no string constant in wf.py matches /^WF_[A-Z_]+$/"}

    # -- build_parser ------------------------------------------------------
    builder = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "build_parser":
            builder = node
    if builder is None:
        facts["global_arguments"] = {"unresolved": "no build_parser() in wf.py"}
        facts["commands"] = {"unresolved": "no build_parser() in wf.py"}
        return {"facts": facts, "provenance": provenance}

    classes = parser_classes(tree)
    parsers = {}          # var -> {"args": [...], "helpers": set(), "prov": []}
    commands = []         # creation order
    bound = {}            # var -> command record under construction
    root_var = None
    subparser_vars = {}   # var -> owning parser var

    def parser_slot(var):
        return parsers.setdefault(var, {"args": [], "helpers": set(), "prov": []})

    def apply_helper(helper, parser_var, call_node):
        node, calls = helper_arguments(tree, helper)
        slot = parser_slot(parser_var)
        if node is None or calls is None:
            provenance["notes"].append(
                f"{TARGET}:{call_node.lineno}: {helper}() is not a"
                " module-level function; its arguments are unresolved")
            slot["helpers"].add(helper)
            slot["args"].append(("unresolved", helper, call_node))
            return
        slot["helpers"].add(helper)
        for one in calls:
            slot["args"].append(("call", helper, one))

    for stmt in builder.body:
        # var = <parser constructor> | subparsers | add_parser
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name) \
                and isinstance(stmt.value, ast.Call):
            var, call = stmt.targets[0].id, stmt.value
            if is_parser_call(call, classes):
                parser_slot(var)
                continue
            if isinstance(call.func, ast.Attribute) and \
                    call.func.attr == "add_subparsers" and \
                    isinstance(call.func.value, ast.Name):
                subparser_vars[var] = call.func.value.id
                root_var = call.func.value.id
                continue
            if isinstance(call.func, ast.Attribute) and \
                    call.func.attr == "add_parser":
                ok, name = literal(call.args[0]) if call.args else (False, None)
                record = {
                    "name": name if ok and isinstance(name, str) else
                            {"unresolved": "add_parser name is not a string"
                                           " literal"},
                    "direct": [], "parents": [], "helpers": set(),
                    "dispatch": None, "node": call,
                }
                parent_node = kwarg(call, "parents")
                if parent_node is not None:
                    if isinstance(parent_node, (ast.List, ast.Tuple)):
                        for element in parent_node.elts:
                            if isinstance(element, ast.Name):
                                record["parents"].append(element.id)
                            else:
                                provenance["notes"].append(
                                    f"{TARGET}:{call.lineno}: parents= holds a"
                                    f" non-name {ast.unparse(element)}")
                    else:
                        provenance["notes"].append(
                            f"{TARGET}:{call.lineno}: parents= is not a list"
                            f" literal: {ast.unparse(parent_node)}")
                commands.append(record)
                bound[var] = record
                continue

        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            # p.add_argument(...) / parser.add_argument(...)
            if isinstance(call.func, ast.Attribute) and \
                    isinstance(call.func.value, ast.Name):
                var, attr = call.func.value.id, call.func.attr
                if attr == "add_argument":
                    if var in bound:
                        bound[var]["direct"].append(call)
                    else:
                        parser_slot(var)["args"].append(("call", None, call))
                    continue
                if attr == "set_defaults" and var in bound:
                    func_node = kwarg(call, "func")
                    bound[var]["dispatch"] = (
                        ast.unparse(func_node) if func_node is not None else None)
                    continue
            # helper(parser, ...)
            if isinstance(call.func, ast.Name) and call.args and \
                    isinstance(call.args[0], ast.Name):
                apply_helper(call.func.id, call.args[0].id, call)
                continue

        if isinstance(stmt, (ast.Assign, ast.Expr)):
            rendered = ast.unparse(stmt)
            if "add_argument" in rendered or "add_parser" in rendered:
                provenance["notes"].append(
                    f"{TARGET}:{stmt.lineno}: unhandled statement mentioning"
                    f" argparse: {rendered[:120]}")

    # -- global arguments --------------------------------------------------
    if root_var is None or root_var not in parsers:
        facts["global_arguments"] = {
            "unresolved": "the root parser could not be identified — no"
                          " <var>.add_subparsers(...) in build_parser()"}
        provenance["global_arguments"] = []
    else:
        slot = parsers[root_var]
        records, entries, unresolved = [], [], []
        for kind, helper, node in slot["args"]:
            if kind == "unresolved":
                unresolved.append(helper)
                continue
            record = argument_record(node, is_global=True)
            records.append(record)
            entries.append(prov(
                TARGET, node,
                "§5.6 add_argument on the root parser"
                + (f" via helper {helper}()" if helper else " directly"),
                lines, argument=record, helper=helper, parser_var=root_var))
        if unresolved:
            facts["global_arguments"] = {
                "unresolved": "arguments are added by helper(s) whose body"
                              f" could not be read: {', '.join(sorted(unresolved))}"}
        elif not records:
            facts["global_arguments"] = {
                "unresolved": "no add_argument reaches the root parser — either"
                              " there are none or the walk missed them"}
        else:
            records.sort(key=sort_key)
            facts["global_arguments"] = records
        provenance["global_arguments"] = entries
        provenance["root_parser_helpers"] = sorted(slot["helpers"])

    # -- commands ----------------------------------------------------------
    next_dispatch = None
    out_commands, command_prov = [], {}
    for record in commands:
        arguments, entries, helpers, unresolved = [], [], set(record["helpers"]), []
        for parent in record["parents"]:
            slot = parsers.get(parent)
            if slot is None:
                unresolved.append(f"parents=[{parent}] names an unknown parser")
                continue
            helpers |= slot["helpers"]
            for kind, helper, node in slot["args"]:
                if kind == "unresolved":
                    unresolved.append(f"helper {helper}() could not be read")
                    continue
                argument = argument_record(node, is_global=False)
                arguments.append(argument)
                entries.append(prov(
                    TARGET, node,
                    f"§5.6 inherited via parents=[{parent}]"
                    + (f", added by helper {helper}()" if helper else ""),
                    lines, argument=argument, helper=helper, via=parent))
        for node in record["direct"]:
            argument = argument_record(node, is_global=False)
            arguments.append(argument)
            entries.append(prov(TARGET, node,
                                "§5.6 add_argument on the sub-parser", lines,
                                argument=argument))

        name = record["name"]
        item = {"name": name}
        if unresolved:
            item["arguments"] = {"unresolved": "; ".join(sorted(set(unresolved)))}
        elif not arguments:
            item["arguments"] = []
        else:
            arguments.sort(key=sort_key)
            item["arguments"] = arguments
        item["helpers_applied"] = sorted(helpers)
        item["next_json_keys"] = "n/a"
        out_commands.append(item)
        key = name if isinstance(name, str) else f"<unresolved@{record['node'].lineno}>"
        command_prov[key] = {
            "add_parser": prov(TARGET, record["node"],
                               "§5.6 subparsers.add_parser(\"<name>\") →"
                               " command", lines,
                               parents=record["parents"],
                               dispatch=record["dispatch"]),
            "arguments": entries,
        }
        if name == "next":
            next_dispatch = record["dispatch"]

    # -- next_json_keys ----------------------------------------------------
    target = None
    if next_dispatch:
        target = mods.function(TARGET, next_dispatch)
    if next_dispatch is None:
        value = {"unresolved": "the next sub-parser records no"
                               " set_defaults(func=…) dispatch target"}
        provenance["next_json_keys"] = {"dispatch": None}
    elif target is None:
        value = {"unresolved": f"the next command dispatches to {next_dispatch},"
                               f" which is not a module-level function of {TARGET}"}
        provenance["next_json_keys"] = {"dispatch": next_dispatch}
    else:
        keys, notes, sites = emit_payloads(mods, TARGET, target)
        provenance["next_json_keys"] = {
            "dispatch": next_dispatch,
            "rule": "§5.6 next_json_keys, ADAPTED: keys of every payload"
                    " reaching ctx.emit(<payload>, …) inside the dispatch"
                    " target — dict literals, the name the payload is built"
                    " under, .update() calls and subscript assignment, one"
                    " call hop at a time into sibling modules",
            "emit_sites": [prov(TARGET, node, "ctx.emit payload", lines)
                           for node in sites],
            "unfollowed": sorted(set(notes)),
        }
        if not keys:
            value = {"unresolved": "no ctx.emit payload keys could be resolved"
                                   f" in {next_dispatch}: "
                                   + "; ".join(sorted(set(notes))[:4])}
        else:
            value = sorted(keys)
    for item in out_commands:
        if item["name"] == "next":
            item["next_json_keys"] = value

    out_commands.sort(key=lambda c: c["name"] if isinstance(c["name"], str)
                      else "￿")
    facts["commands"] = out_commands or {
        "unresolved": "no subparsers.add_parser(...) call found in build_parser()"}
    provenance["commands"] = command_prov
    # The signature line only: the whole body is already quoted, statement by
    # statement, in the per-argument provenance above.
    provenance["build_parser"] = {
        "file": TARGET, "lines": _lines(builder),
        "text": lines[builder.lineno - 1],
        "rule": "§5.6 the parser is read from this function only",
    }
    return {"facts": facts, "provenance": provenance}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = argv[0] if argv else None
    print(json.dumps(extract(root), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
