"""Compose existing policy owners; harness adapters contain no predicates."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[2]
TOOLS = SOURCE / "ops/conductor/tools"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Paths are chosen from this installed source, never from the caller's cwd.
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE / "claude"))
import instrument  # noqa: E402

native = load("shared_hook_native", HERE / "native.py")
matrix = load("shared_hook_matrix", HERE / "claude/matrix.py")
engine = load("shared_hook_engine", HERE / "claude/engine.py")
engine.matrix = matrix
unsafe = load("shared_hook_unsafe", HERE / "claude/unsafe-command.py")
no_subagents = load("shared_hook_delegation", HERE / "claude/no-subagents.py")
context = load("shared_hook_context", HERE / "claude/context-precheck.py")
hand = load("shared_hook_hand", TOOLS / "hand.py")
skills = load("shared_hook_skills", TOOLS / "skills.py")
skill_use = load("shared_hook_skill_use", HERE / "claude/skill-use.py")


def decision(outcome="allow", reason="", context="", *, klass=None):
    value = {"outcome": outcome, "reason": reason, "context": context}
    if klass:
        value["policy_class"] = klass
    return value


def refuse(found, needed="repair the shared guard binding; inspect co_doc.py"):
    return decision("deny", f"hook-input: expected complete verified enforcement; found {found}; needed {needed}")


def converted(value):
    if value is None:
        return decision()
    if not isinstance(value, dict):
        raise ValueError("malformed evaluator response")
    if value.get("decision") == "block":
        reason = native.text(value.get("reason"), "refusal reason")
        return decision("deny", reason, klass=policy_class(reason))
    spec = value.get("hookSpecificOutput")
    if not isinstance(spec, dict):
        raise ValueError("missing evaluator output")
    outcome = spec.get("permissionDecision")
    if outcome in {"deny", "ask"}:
        reason = native.text(spec.get("permissionDecisionReason"), "refusal reason")
        return decision(outcome, reason, klass=policy_class(reason))
    if "additionalContext" in spec:
        return decision(context=native.text(spec["additionalContext"], "context", empty=True))
    raise ValueError("unknown evaluator decision")


def policy_class(reason):
    """Read only existing policy owners' bracketed class tags, never tool input."""
    match = re.match(r"\[(?:(?:matrix|engine):)?([a-z][a-z0-9-]*)\] ", reason)
    return match[1] if match else None


def shared_miss(_cwd, klass, found, hook="engine"):
    """Adapt the engine's existing observation seam to the pinned skills owner."""
    return skill_use.record_miss(skills, klass, found)


@contextmanager
def working_directory(path):
    previous = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(previous)


def mcp_allowed(inp, servers):
    """Use existing catalogues/schemas; domain mutations still authorize themselves."""
    server, name, args = inp.get("server"), inp.get("name"), inp.get("arguments")
    if server not in servers or not isinstance(args, dict):
        return False
    if server == "coordination":
        owner = load("shared_coordination_surface", TOOLS / "coordination_mcp.py")
        tool = owner.BY_NAME.get(name)
        if tool is None:
            return False
        owner.check_arguments(tool, args)
        return True
    if server in {"agentscient-lane", "agentscient_lane"}:
        owner = load("shared_lane_surface", TOOLS / "lane_mcp.py")
        # Names/schema are derived from the existing owner, not duplicated here.
        rows = owner._schemas({"version": 3})
        return any(row["name"] == name and row.get("annotations", {}).get("readOnlyHint") is True for row in rows)
    return False


def _evaluate(payload, *, servers=(), mode=None, pins=None):
    """One complete decision. Guard failures cannot be confused with predicate None."""
    token = None
    try:
        if not isinstance(payload, dict):
            raise ValueError("native object absent")
        event = payload.get("hook_event_name")
        if event not in engine.EVENTS:
            raise ValueError("unsupported lifecycle coverage")
        cwd = native.text(payload.get("cwd"), "cwd")
        if not Path(cwd).is_absolute() or not Path(cwd).is_dir():
            raise ValueError("unavailable working directory")
        # Source config/registry are authority. Payload and environment cannot
        # replace them with a worker-controlled checkout's policy.
        conf = instrument._laneconf().parse_file(SOURCE / "ops/lane.conf")
        token = matrix.GUARD_CONTEXT.set({"conf": conf, "state": str(instrument.state_root()), "instrument": instrument, "grant_db": str(hand.database_path())})
        registry = native.loads((HERE / "boundaries.json").read_bytes())
        rows = registry.get("rows")
        if registry.get("schema") != "agentscient.boundaries/2" or not isinstance(rows, list) or not rows:
            raise ValueError("invalid installed registry")
        if event in {"PreToolUse", "PostToolUse"}:
            tool, inp = payload.get("tool_name"), payload.get("tool_input")
            if not isinstance(inp, dict):
                raise ValueError("invalid tool arguments")
            if tool == "Bash":
                native.text(inp.get("command"), "command")
                if inp.get("tty") or inp.get("RunPersistent") or inp.get("env"):
                    return refuse("unbound interactive shell or environment", "use a finite guarded command")
            elif tool in {"Write", "Edit", "MultiEdit"}:
                native.text(inp.get("file_path"), "edit path")
                if not any(isinstance(inp.get(key), str) for key in ("content", "new_string")):
                    raise ValueError("missing edit content")
            elif tool == "MCP":
                if not mcp_allowed(inp, servers):
                    return refuse("unbound MCP operation", "bind the existing server catalogue and effective core authority")
            elif tool == "Continuation":
                return refuse("unbound continuation input", "use a finite guarded command; input is not a fresh shell action")
            elif tool == "Skill":
                if payload.get("native_harness") != "claude":
                    return refuse("unverified native Skill transport", "use the common skills.py use command")
                if mode != "interactive":
                    return refuse("native operator skill outside an interactive profile", "follow the worker's assigned job instructions")
                name = native.skill_name(inp)
                skill_use.managed_page(skills, SOURCE, name, pins=pins)
                # The witnessed Claude payload is name-only. It cannot prove
                # which project/personal/plugin source the native tool loads.
                return decision("deny", "skill-source: expected a verified canonical native skill source; "
                                f"found name-only Skill invocation {name}; needed "
                                + skill_use.use_command(SOURCE, name), klass="skill-source")
            elif tool not in {"Read", "Cancel", "Agent", "Task", "Workflow"}:
                return refuse("unknown native tool", "declare and verify its translation in the shared guard")
            if event == "PostToolUse" and any(row.get("engine") and row.get("event") == event for row in rows) and "tool_response" not in payload:
                return refuse("unavailable post-tool result", "supply the verified native result reading")
        elif event == "Stop" and not isinstance(payload.get("last_assistant_message"), str):
            return refuse("unavailable final response", "supply a verified native transcript reading")
        with working_directory(cwd):
            if event == "PreToolUse":
                reason = no_subagents.decide(payload)
                if reason:
                    return decision("deny", reason, klass="no-subagents")
                if tool == "Bash":
                    out = converted(unsafe.decide(payload))
                    if out["outcome"] != "allow":
                        return out
                if tool in {"Bash", "Write", "Edit", "MultiEdit"}:
                    out = converted(matrix.decide(payload))
                    if out["outcome"] != "allow":
                        return out
            # Fresh-host skill events can consume operator source pages. Only
            # an interactive binding pins those pages; workers keep job state.
            def observer(*args, **kwargs):
                return mode == "interactive" and shared_miss(*args, **kwargs)
            out = converted(engine.decide(payload, rows=rows, miss_logger=observer)[0])
            if out["outcome"] != "allow":
                return out
            if event == "PreToolUse" and tool == "Bash":
                checked = converted(context.decide(payload, strict=True))
                if checked["outcome"] != "allow":
                    checked.setdefault("policy_class", "context-precheck")
                    return checked
            return out
    except Exception as exc:  # noqa: BLE001 - unavailable guard input is a blocking result
        return refuse(type(exc).__name__ + ": " + str(exc)[:240])
    finally:
        if token is not None:
            matrix.GUARD_CONTEXT.reset(token)


def evaluate(payload, *, servers=(), mode=None, pins=None):
    result = _evaluate(payload, servers=servers, mode=mode, pins=pins)
    return skill_use.recovery(result, skills, SOURCE, mode=mode)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=native.HARNESSES, required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--binding", required=True)
    args = parser.parse_args(argv)
    result = refuse("unavailable guard")
    try:
        profiles = load("shared_hook_profiles", HERE / "profiles.py")
        binding = profiles.read_binding(args.binding)
        profiles.validate(binding)
        if binding["harness"] != args.harness:
            raise ValueError("harness binding mismatch")
        raw = native.loads(sys.stdin.buffer.read(native.MAX_BYTES + 1))
        profiles.initialize(binding, raw, instrument=instrument)
        items = native.normalize(args.harness, raw, event=args.event, cwd=binding["cwd"], home=binding["home"])
        rewritten = None
        if args.harness == "codex" and args.event == "PreToolUse" and len(items) == 1 and items[0].get("tool_name") == "Bash":
            rewritten = native.bind_command(items[0]["tool_input"]["command"], binding["cwd"])
            items[0]["cwd"] = binding["cwd"]
        result = decision()
        for payload in items:
            result = evaluate(payload, servers=binding.get("servers", ()), mode=binding["mode"], pins=binding["pins"])
            if result["outcome"] != "allow":
                break
        if rewritten and result["outcome"] == "allow":
            result["updated_input"] = {"command": rewritten}
        if (binding["mode"] == "interactive" and result["outcome"] == "allow"
                and args.event in {"SessionStart", "PreInvocation"}):
            result["context"] = "\n".join(filter(None, (result["context"], skill_use.startup(skills, SOURCE, pins=binding["pins"]))))
    except Exception as exc:  # noqa: BLE001 - native hooks must answer even on a broken binding
        result = refuse(type(exc).__name__ + ": " + str(exc)[:240])
    print(json.dumps(native.respond(args.harness, result, args.event)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
