#!/usr/bin/env python3
"""engine.py -- the boundary engine: one hook, every lifecycle event, rows as data.

Owner, 2026-09-12: "build the engine - just make it a specific registry
of intentional conditions that can be added to any hook in the session
lifecycle"; "its about a registry that dictates the matrix of conditions
used in pre-tool - post-tool - whatever tool state". Law: docs/workflow.md,
a transition declares its actor class, its evidence duty, its failure
class and its gate.

The registry (ops/devlane/hooks/boundaries.json, or BOUNDARIES_PATH) is
the source. A row with ``engine: true`` is evaluated here: it binds to an
event (PreToolUse, PostToolUse, SessionStart, Stop) and optionally to
tools, and carries a ``when`` tree over the predicate vocabulary below
(``all`` / ``any`` / ``not`` / ``pred``). A refusing row emits the wire
line ``[engine:<class>] <class>: expected ...; found ...; needed ...``
through the event's channel: a deny on PreToolUse, a block on PostToolUse
and Stop. A row with ``context`` instead of ``refuse`` emits additional
context. The first refusing row wins; an event with no rows passes.

A predicate the engine does not know, a registry it cannot read, or an
exception in a predicate is could-not-look and refuses ``hook-error``: a
condition nobody can evaluate is never a pass. A row's ``escape``
``grant`` is lifted by an open hand grant leading the command; ``none``
is lifted by nothing.

``engine.py lint`` reports the registry: engine rows, the vocabulary,
unknown predicates, unknown events. Adding a condition is adding a row.
"""

import importlib.util
import json
import os
import re
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REGISTRY = os.path.join(HERE, "..", "boundaries.json")
EVENTS = ("PreToolUse", "PostToolUse", "SessionStart", "Stop")


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


matrix = _load("matrix", "matrix.py")
miss = _load("miss", "miss.py")


class CouldNotLook(Exception):
    pass


class Context:
    def __init__(self, payload):
        self.payload = payload
        self.event = payload.get("hook_event_name") or (
            "PostToolUse" if "tool_response" in payload
            else "PreToolUse" if payload.get("tool_name")
            else "SessionStart" if "source" in payload else "Stop")
        self.tool = payload.get("tool_name") or ""
        self.input = payload.get("tool_input") or {}
        self.response = payload.get("tool_response")
        self.cwd = payload.get("cwd") or os.getcwd()
        self.root = matrix.repo_root(self.cwd) or self.cwd
        self.conf = matrix.lane_conf(self.root)
        self.lane = self.conf.get("LANE_NAME")
        self.text = self.input.get("command", "") if self.tool == "Bash" else ""
        self.statements = [matrix.tokens_of(s) for s in matrix.commands(self.text)] if self.text else []
        self.statements = [s for s in self.statements if s]

    def response_text(self):
        if self.response is None:
            return ""
        if isinstance(self.response, str):
            return self.response
        try:
            return json.dumps(self.response, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(self.response)


# ---- the predicate vocabulary: each returns the found text, or None

def p_always(ctx):
    return "always"


def p_tool_in(ctx, names):
    return ctx.tool if ctx.tool in list(names) else None


def p_command_matches(ctx, pattern):
    """The whole command text first (a pipeline is one intention), then
    each statement the shape splitter yields."""
    rx = re.compile(pattern)
    for line in ctx.text.splitlines():
        if rx.search(line):
            return line.strip()[:200]
    for statement in matrix.commands(ctx.text):
        if rx.search(statement):
            return statement.strip()[:200]
    return None


def p_response_matches(ctx, pattern):
    rx = re.compile(pattern)
    for line in ctx.response_text().splitlines():
        if rx.search(line):
            return line.strip()[:200]
    return None


def p_file_written_under(ctx, prefix):
    candidates = []
    for key in ("file_path", "relative_path", "path"):
        if ctx.input.get(key):
            candidates.append(ctx.input[key])
    for toks in ctx.statements:
        candidates.extend(matrix.redirect_targets(toks) + matrix.written_paths(toks))
    for path in candidates:
        if path == ".":
            continue
        _, rel = matrix.relative(path, ctx.cwd)
        if (rel or path).startswith(prefix):
            return path
    return None


def _protected(ctx):
    return {b for b in (ctx.conf.get("TRUNK_BRANCH"), ctx.conf.get("RELEASE_BRANCH")) if b}


SEGMENT_SPLIT = re.compile(r"\|\||&&|;|\||\n")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _statements_with_dirs(ctx):
    """(toks, directory) per git statement, read from the raw command so
    that a `cd <dir>` earlier in the chain and a `git -C <dir>` on the
    statement itself both move the directory the row reads. The shape
    normaliser strips `-C`, so this predicate does not go through it
    (2026-09-12: the code form of this row refused `cd <worktree> && git
    commit` and `git -C <worktree> commit` on a session branch, reading
    the session's directory both times)."""
    directory = ctx.cwd
    for segment in SEGMENT_SPLIT.split(ctx.text or ""):
        try:
            toks = shlex.split(segment, posix=True)
        except ValueError:
            continue
        while toks and ASSIGNMENT.match(toks[0]):
            toks = toks[1:]
        while toks and toks[0] in ("sudo", "env", "command", "exec", "nice", "timeout"):
            toks = toks[1:]
            if toks and toks[0].startswith("-") and toks[0] != "-C":
                toks = toks[1:]
        if not toks:
            continue
        if matrix.base(toks[0]) == "cd":
            target = toks[1] if len(toks) > 1 else os.path.expanduser("~")
            directory = os.path.normpath(os.path.join(directory, os.path.expanduser(target)))
            continue
        if matrix.base(toks[0]) != "git":
            continue
        yield toks, directory


def p_git_write_on_protected(ctx):
    protected = _protected(ctx)
    for toks, cwd in _statements_with_dirs(ctx):
        sub, _rest, directory = matrix._git_subcommand(toks, cwd)
        if sub in matrix.TRUNK_WRITES:
            branch = matrix.branch_of(directory)
            if branch in protected:
                return f"git {sub} on {branch} in {directory}"
    return None


def p_git_push_to_protected(ctx):
    protected = _protected(ctx)
    for toks, cwd in _statements_with_dirs(ctx):
        sub, rest, _ = matrix._git_subcommand(toks, cwd)
        if sub != "push":
            continue
        operands = [t for t in rest if not t.startswith("-")]
        for spec in operands[1:]:
            dst = spec.split(":", 1)[1] if ":" in spec else spec
            dst = dst.lstrip("+").removeprefix("refs/heads/")
            if dst in protected:
                return f"git push to {dst}"
    return None


def p_claim_without_reading(ctx):
    for target, body in matrix.heredoc_records(ctx.text, ctx.cwd):
        line = matrix.unmeasured_claim(body)
        if line:
            return f'in the record {target}: "{line[:140]}"'
    for toks in ctx.statements:
        for surface, body in matrix.published_texts(toks, ctx.text, ctx.cwd):
            line = matrix.unmeasured_claim(body)
            if line:
                return f'in the {surface}: "{line[:140]}"'
    return None


def p_prune_target(ctx):
    for toks in ctx.statements:
        for target in matrix.prune_targets(toks, ctx.cwd, ctx.conf):
            return f"rm -r {target}"
    return None


def p_unittest_path_form(ctx):
    for toks in ctx.statements:
        found = matrix.path_form_unittest(toks)
        if found:
            return f"a path-form unittest argument {found}"
    return None


PREDICATES = {
    "always": p_always,
    "tool_in": p_tool_in,
    "command_matches": p_command_matches,
    "response_matches": p_response_matches,
    "file_written_under": p_file_written_under,
    "git_write_on_protected": p_git_write_on_protected,
    "git_push_to_protected": p_git_push_to_protected,
    "claim_without_reading": p_claim_without_reading,
    "prune_target": p_prune_target,
    "unittest_path_form": p_unittest_path_form,
}


def evaluate(node, ctx):
    """The found text when the tree holds, else None; CouldNotLook on a
    node the engine cannot evaluate."""
    if not isinstance(node, dict) or len(node) == 0:
        raise CouldNotLook(f"malformed when node {node!r}")
    if "all" in node:
        founds = []
        for child in node["all"]:
            found = evaluate(child, ctx)
            if found is None:
                return None
            founds.append(found)
        return "; ".join(founds) or "all"
    if "any" in node:
        for child in node["any"]:
            found = evaluate(child, ctx)
            if found is not None:
                return found
        return None
    if "not" in node:
        return None if evaluate(node["not"], ctx) is not None else "not (" + _describe(node["not"]) + ")"
    if "pred" in node:
        name = node["pred"]
        if name not in PREDICATES:
            raise CouldNotLook(f"unknown predicate {name}")
        return PREDICATES[name](ctx, **(node.get("args") or {}))
    raise CouldNotLook(f"malformed when node {node!r}")


def _describe(node):
    if isinstance(node, dict) and "pred" in node:
        return node["pred"]
    return json.dumps(node)[:60]


def registry_path():
    return os.environ.get("BOUNDARIES_PATH") or DEFAULT_REGISTRY


def load_registry():
    try:
        with open(registry_path(), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as error:
        raise CouldNotLook(f"registry unreadable at {registry_path()}: {error}") from error
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise CouldNotLook("registry carries no rows list")
    return rows


def predicate_names(node, out):
    if isinstance(node, dict):
        if "pred" in node:
            out.add(node["pred"])
        for value in node.values():
            predicate_names(value, out)
    elif isinstance(node, list):
        for value in node:
            predicate_names(value, out)
    return out


def lint():
    rows = load_registry()
    engine_rows = [r for r in rows if r.get("engine")]
    unknown_preds, unknown_events = [], []
    for row in engine_rows:
        for name in sorted(predicate_names(row.get("when"), set())):
            if name not in PREDICATES:
                unknown_preds.append(f"{row.get('class')}: {name}")
        if row.get("event") not in EVENTS:
            unknown_events.append(f"{row.get('class')}: {row.get('event')}")
    report = {"engine_rows": len(engine_rows), "code_rows": len(rows) - len(engine_rows),
              "predicates": sorted(PREDICATES), "unknown_predicates": unknown_preds,
              "unknown_events": unknown_events}
    print(json.dumps(report, indent=1))
    return 0 if not unknown_preds and not unknown_events else 1


def wire_line(klass, expected, found, needed):
    return f"[engine:{klass}] {klass}: expected {expected}; found {found}; needed {needed}"


def emit_refusal(event, line, decision="deny"):
    """deny, or ask when the row's escape is `ask`: the harness then puts
    the action in front of the owner, the one click no agent can make
    (owner, 2026-09-12)."""
    if event == "PreToolUse":
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                       "permissionDecisionReason": line}}
    if event in ("PostToolUse", "Stop"):
        return {"decision": "block", "reason": line}
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": line}}


def decide(payload):
    ctx = Context(payload)
    rows = load_registry()
    bound = [r for r in rows if r.get("engine") and r.get("event") == ctx.event
             and (not r.get("tools") or ctx.tool in r.get("tools"))]
    grant = matrix.open_grant(ctx.text, ctx.lane) if ctx.text else None
    contexts = []
    for row in bound:
        if row.get("escape") == "grant" and grant is not None:
            continue
        try:
            found = evaluate(row.get("when"), ctx)
        except CouldNotLook:
            raise
        except Exception as error:  # a predicate that dies is could-not-look, never a pass
            raise CouldNotLook(f"{row.get('class')}: {type(error).__name__}: {error}") from error
        if found is None:
            continue
        if "context" in row:
            contexts.append(str(row["context"]).replace("{rows}", str(len(rows))))
            continue
        refuse = row.get("refuse") or {}
        line = wire_line(row.get("class", "unnamed"), refuse.get("expected", "the row's expectation"),
                         found, refuse.get("needed", "the row's needed half"))
        decision = "ask" if row.get("escape") == "ask" else "deny"
        return emit_refusal(ctx.event, line, decision), row.get("class")
    if contexts:
        return {"hookSpecificOutput": {"hookEventName": ctx.event, "additionalContext": "\n".join(contexts)}}, None
    return None, None


def main(argv):
    if argv[1:] == ["lint"]:
        try:
            return lint()
        except CouldNotLook as error:
            print(f"hook-error: expected a readable registry; found {error}; needed fix the registry", file=sys.stderr)
            return 2
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    event = payload.get("hook_event_name") or ("PostToolUse" if "tool_response" in payload else "PreToolUse")
    try:
        output, klass = decide(payload)
    except CouldNotLook as error:
        line = wire_line("hook-error", "a registry the engine can evaluate", str(error),
                         "fix the registry row; could not look is not a pass")
        print(json.dumps(emit_refusal(event, line)))
        return 0
    except Exception as error:  # noqa: BLE001 - a hook that dies takes the session with it
        line = wire_line("hook-error", "a decision", f"{type(error).__name__}: {error}", "the engine fixed through the lane")
        print(json.dumps(emit_refusal(event, line)))
        return 0
    if output:
        print(json.dumps(output))
        if klass:
            reason = json.dumps(output)
            miss.log_miss(payload.get("cwd"), klass, reason, hook="engine")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
