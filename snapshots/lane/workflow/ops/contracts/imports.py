#!/usr/bin/env python3
"""The cross-app import graph, as a registered check.

The dev-lane apps are standalone scripts, not packages, so "does app A
depend on app B" cannot be read off a manifest -- it is spread across
`import` statements that only resolve after a sys.path insert, and
across path literals like `parent.parent / "telemetry" / "breaker.py"`.
Nothing in the tree states the graph, so nothing notices when it
changes.

This exists because a contract hole hid a real finding once already:
PLAN.md section 9 says the MCP server "imports the query layer, not the
append layer", `mcp_server.py` imports `chain` anyway, and the `mcp`
contract placed no constraint on server imports at all -- so the
observation had nothing to conflict with and the pipeline reported
neither. A declared graph turns that class of question into a
comparison.

Refusals, not silences. The check is INVALID -- exit 1, never 0 --
when the declaration is missing or unparseable, when the app root does
not exist, or when no Python file was found to inspect. "Nobody
looked" must never render as "we checked and it was fine".

    imports.py [--root DIR] [--declaration FILE] [--json] [--print-graph]

Exit 0 clean, 1 on a violation or an INVALID run.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

#: A literal repo path into another app: `ops/devlane/<name>`.
LITERAL_APP_PATH = re.compile(r"\ops/devlane/([A-Za-z_][A-Za-z0-9_]*)")

#: Calls that turn a path into a module. A COMPLETE path string handed to
#: one of these is an edge even though it never touches `/` as an
#: operator -- `spec_from_file_location("b", "ops/devlane/beta/b.py")` is a
#: normal form for these standalone scripts, and the path-expression rule
#: alone reported it clean (Codex, PR #50 P1).
LOADER_CALLS = frozenset({
    # turn a path into a module
    "spec_from_file_location", "SourceFileLoader", "exec_module",
    "module_from_spec", "run_path", "load_module",
    # turn a path into bytes -- an app consumed by reading its file is
    # still a dependency (Codex, PR #50 round two)
    "Path", "PurePath", "open", "read_text", "read_bytes",
})

#: Calls that take a MODULE name rather than a path. `import_module("beta.bmod")`
#: is an import in every sense that matters and was invisible while only
#: path-shaped calls were inspected.
IMPORT_CALLS = frozenset({"import_module", "find_spec", "__import__"})


class Invalid(Exception):
    """The check could not run. Never reported as a pass."""


def discover_apps(app_root: Path) -> dict[str, set[str]]:
    """{app name: {module basenames it owns}} for every app dir with python."""
    apps = {}
    for child in sorted(app_root.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "__")):
            continue
        modules = {
            p.stem for p in child.rglob("*.py")
            if "__pycache__" not in p.parts
        }
        if modules:
            apps[child.name] = modules
    return apps


def owner_of(module: str, apps: dict[str, set[str]], mine: str) -> str | None:
    """Which app owns `module`? None when it is stdlib, third-party, or mine.

    An app DIRECTORY counts, not only a module file. With `.dev/app` on
    sys.path, `from telemetry import breaker` resolves the telemetry app
    as a namespace package with no __init__.py anywhere -- searching only
    file stems missed it entirely (Codex, PR #50 P2).
    """
    if module == mine or module in apps.get(mine, set()):
        return None
    if module in apps:
        return module
    owners = sorted(name for name, mods in apps.items() if module in mods)
    if len(owners) == 1:
        return owners[0]
    if len(owners) > 1:
        # Two apps own a module of this name, so which one is referenced
        # depends on sys.path order at run time and cannot be read off the
        # source. Returning None here treated it exactly like a stdlib
        # import and printed clean -- discarding the very edge the check
        # exists to find (Codex, PR #50 round two). The run refuses
        # instead: a graph that cannot be determined is not a clean graph.
        raise Invalid(
            f"{mine}: `{module}` is owned by more than one app "
            f"({', '.join(owners)}), so which is imported depends on "
            f"sys.path at run time — rename it or declare it explicitly")
    return None


def path_join_constants(tree: ast.AST):
    """Every string constant that participates in a `/` path expression.

    The precision hinge, and it is structural rather than textual. These
    apps load each other by path -- `HARNESS / "isolation.py"`, or
    `parent.parent / "telemetry" / "breaker.py"` -- so a real edge is a
    string used as a path SEGMENT. A string sitting in a list, a dict
    value, or a comment is a path the file talks ABOUT.

    Measured on dev: the textual version reported three edges, all false
    (two comments, and `"given": ["ops/devlane/workflow/PLAN.md"]` inside a
    control fixture). This rule reports none of them, because none is an
    operand of `/`, and still catches task/run.py's breaker load.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
            continue
        for side in (node.left, node.right):
            if isinstance(side, ast.Constant) and isinstance(side.value, str):
                yield side.value, node.lineno


def loader_argument_constants(tree: ast.AST):
    """Every string literal handed as an argument to a module loader.

    Narrow on purpose: a string is inspected only where it is about to
    BECOME a module. That keeps the fix from sliding back into the
    indiscriminate text search this checker started as, whose false
    positives are recorded in path_join_constants.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name not in LOADER_CALLS and name not in IMPORT_CALLS:
            continue
        dotted = name in IMPORT_CALLS
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    yield sub.value, node.lineno, dotted


def edges_in_file(path: Path, app: str, apps: dict[str, set[str]]):
    """Every cross-app reference this file makes, as (dst, why) pairs."""
    text = path.read_text(encoding="utf-8", errors="replace")
    found = set()

    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        raise Invalid(f"{path} does not parse: {exc}") from exc

    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module.split(".")[0]]
        for name in names:
            dst = owner_of(name, apps, app)
            if dst:
                found.add((dst, f"import {name}"))

    for value, lineno in path_join_constants(tree):
        if value in apps and value != app:
            found.add((value, f'path segment "{value}" (line {lineno})'))
        for match in LITERAL_APP_PATH.finditer(value):
            dst = match.group(1)
            if dst in apps and dst != app:
                found.add((dst, f"path ops/devlane/{dst} (line {lineno})"))

    for value, lineno, dotted in loader_argument_constants(tree):
        # A dotted module name resolves through the same ownership rules
        # as a static import; a path resolves by segment.
        parts = value.split(".") if dotted else value.split("/")
        for segment in parts:
            if segment in apps and segment != app:
                found.add((segment, f"loaded from {value!r} (line {lineno})"))
        if dotted:
            dst = owner_of(value.split(".")[0], apps, app)
            if dst:
                found.add((dst, f"import_module({value!r}) (line {lineno})"))

    return found


def build_graph(app_root: Path, include_tests: bool):
    apps = discover_apps(app_root)
    if not apps:
        raise Invalid(f"no app directory under {app_root} contains python")

    graph, inspected = {name: {} for name in apps}, 0
    for app in apps:
        for path in sorted((app_root / app).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if not include_tests and "tests" in path.parts:
                continue
            inspected += 1
            for dst, why in edges_in_file(path, app, apps):
                rel = path.relative_to(app_root.parent.parent)
                graph[app].setdefault(dst, []).append(f"{rel}: {why}")

    if inspected == 0:
        raise Invalid(f"no python file was inspected under {app_root}")
    return graph, inspected


def load_declaration(path: Path) -> dict[str, set[str]]:
    if not path.exists():
        raise Invalid(f"the declaration {path} is absent")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Invalid(f"the declaration {path} is unreadable: {exc}") from exc
    apps = data.get("apps")
    if not isinstance(apps, dict) or not apps:
        raise Invalid(f"{path} declares no apps")
    out = {}
    for name, entry in apps.items():
        allowed = (entry or {}).get("may_import", [])
        if not isinstance(allowed, list):
            raise Invalid(f"{path}: {name}.may_import is not a list")
        out[name] = set(allowed)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", help="repo root")
    ap.add_argument("--declaration", default=None)
    ap.add_argument("--include-tests", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--print-graph", action="store_true",
                    help="emit the observed graph and exit 0; seeds the declaration")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    app_root = root / "ops" / "devlane"
    decl_path = Path(args.declaration) if args.declaration else root / "ops" / "contracts" / "imports.json"

    try:
        if not app_root.is_dir():
            raise Invalid(f"{app_root} is not a directory")
        graph, inspected = build_graph(app_root, args.include_tests)

        if args.print_graph:
            observed = {a: {"may_import": sorted(d)} for a, d in sorted(graph.items())}
            print(json.dumps({"apps": observed}, indent=2, sort_keys=True))
            return 0

        declared = load_declaration(decl_path)
    except Invalid as exc:
        print(f"imports: INVALID — {exc}", file=sys.stderr)
        return 1

    violations, undeclared_apps = [], []
    for app, deps in sorted(graph.items()):
        if app not in declared:
            undeclared_apps.append(app)
        # An app missing from the declaration is checked as if it declared
        # nothing, rather than skipped. Skipping it would hide the edges of
        # exactly the app most worth looking at -- a new one, whose coupling
        # nobody has reviewed yet.
        allowed = declared.get(app, set())
        for dst, why in sorted(deps.items()):
            if dst not in allowed:
                violations.append({"from": app, "to": dst, "evidence": sorted(why)})

    for app in declared:
        if app not in graph:
            undeclared_apps.append(f"{app} (declared, but no such app)")

    if args.json:
        print(json.dumps({"inspected": inspected, "violations": violations,
                          "undeclared": undeclared_apps}, indent=2, sort_keys=True))
    else:
        print(f"imports: inspected {inspected} python file(s)")
        for app in undeclared_apps:
            print(f"  UNDECLARED APP: {app}")
        for v in violations:
            print(f"  VIOLATION: {v['from']} -> {v['to']}")
            for line in v["evidence"]:
                print(f"      {line}")
        if not violations and not undeclared_apps:
            print("  clean — every cross-app reference is declared")

    return 1 if (violations or undeclared_apps) else 0


if __name__ == "__main__":
    sys.exit(main())
