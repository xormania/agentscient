#!/usr/bin/env python3
"""Native PreToolUse boundary for the owner-frozen conductor control."""
from __future__ import annotations

import importlib.util
import json
import shlex
import sys
from pathlib import Path

CONTROL = Path(__file__).resolve().parents[2] / "conductor/tools/control.py"
READS = {"Read", "read_file", "Glob", "glob", "Grep", "grep", "list_dir",
         "list_mcp_resources", "read_mcp_resource", "list_mcp_resource_templates"}
SHELL = {"Bash", "exec_command", "shell_command", "run_terminal_command"}
GIT_READS = {"status", "diff", "show", "log", "rev-parse", "ls-files", "ls-tree"}


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate native field")
        result[key] = value
    return result


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "permissionDecision": "deny", "permissionDecisionReason":
        f"tool: expected safe read or frozen controller action; found {' '.join(str(reason).split())}; "
        "needed use the owner-declared action or read diagnostics"}}))
    return 0


def shell_words(command):
    if not isinstance(command, str) or not command.strip():
        return None
    # Reject shell composition before tokenization, including quoted substitutions.
    if any(char in command for char in "\n\r\x00;&|<>`$"):
        return None
    try:
        words = shlex.split(command, posix=True)
    except ValueError:
        return None
    if not words or any("=" in word for word in words[:1]):
        return None
    return words


def safe_shell(words):
    if not words:
        return False
    command, *args = words
    if command == "pwd":
        return not args or args in (["-P"], ["-L"])
    if command == "cat":
        return bool(args) and all(arg != "-" and not arg.startswith("--output") for arg in args)
    if command == "rg":
        # Configuration/preprocessor/search-zip options can spawn arbitrary commands.
        return bool(args) and not any(arg == "-" or (arg.startswith("-") and not arg.startswith("--") and "z" in arg)
                                     or arg.startswith(("--pre", "--search-zip", "--hostname-bin"))
                                     for arg in args)
    if command == "git" and args and args[0] in GIT_READS:
        # Git accepts abbreviated long options, so a denylist misses --out=FILE.
        options = {"--", "--short", "--branch", "--porcelain", "--porcelain=v1", "--porcelain=v2",
                   "--stat", "--name-only", "--name-status", "--cached", "--staged", "--oneline",
                   "--decorate", "--no-decorate", "--show-toplevel", "--show-current", "--verify",
                   "--quiet", "--is-inside-work-tree", "--abbrev-ref", "--error-unmatch", "--full-name",
                   "--full-tree", "--check", "--no-ext-diff", "--no-textconv", "-r", "-z", "-n"}
        return all(not arg.startswith("-") or arg in options or arg[1:].isdigit() for arg in args[1:])
    return False


def main():
    try:
        raw = sys.stdin.buffer.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            return deny("oversized native payload")
        payload = json.loads(raw, object_pairs_hook=pairs)
        if not isinstance(payload, dict):
            return deny("malformed native payload")
        if "toolName" in payload:
            if (("tool_name" in payload and payload["tool_name"] != payload["toolName"])
                    or ("tool_input" in payload and payload["tool_input"] != payload.get("toolInput"))
                    or payload.get("toolInputTruncated")):
                return deny("ambiguous or truncated native payload")
            payload["tool_name"] = payload["toolName"]
            payload["tool_input"] = payload.get("toolInput")
        tool, params, cwd = payload.get("tool_name"), payload.get("tool_input"), payload.get("cwd")
        if not isinstance(tool, str) or not isinstance(params, dict) or not isinstance(cwd, str):
            return deny("missing or malformed native fields")
        tool = tool.removeprefix("functions.")
        if tool in READS:
            return 0
        if tool == "write_stdin":
            return 0 if params.get("chars", "") == "" else deny("interactive input")
        if tool not in SHELL:
            return deny(f"unrecognized or writing tool {tool}")
        if (params.get("tty") or params.get("stdin") or params.get("input") or params.get("env")
                or params.get("shell") not in (None, "/bin/bash", "/usr/bin/bash")):
            return deny("interactive input, environment override or alternate shell")
        words = shell_words(params.get("command", params.get("cmd")))
        if safe_shell(words):
            return 0
        if sys.argv[1:2] != ["--state"] or len(sys.argv) != 3:
            return deny("missing frozen state argument")
        state_path = Path(sys.argv[2]).absolute()
        if words == [sys.executable, str(CONTROL), "status", "--state", str(state_path)]:
            return 0
        expected = [str(CONTROL), "run"]
        if (not words or len(words) != 6 or not Path(words[0]).is_absolute()
                or Path(words[0]).resolve() != Path(sys.executable).resolve()
                or words[1:3] != expected or words[4] != "--state"
                or words[5] != str(state_path)):
            return deny("command outside the frozen controller interface")
        spec = importlib.util.spec_from_file_location("owner_conductor_control", CONTROL)
        control = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(control)
        state = control.load(state_path)
        actual_cwd = params.get("workdir", params.get("cwd", cwd))
        if Path(actual_cwd).resolve() != Path(state["plan"]["repo"]).resolve():
            return deny("worktree differs from the frozen action")
        # Admission, reservations and expiry belong to the invoked controller.
        # The native gate permits its exact declared interface, including a call
        # which will return a useful refusal after a seat has stopped.
        if not any(action["id"] == words[3] for action in state["plan"]["actions"]):
            return deny("undeclared action ID")
        return 0
    except Exception as error:  # noqa: BLE001 -- every native helper failure must deny, never fall through
        return deny(f"unavailable or invalid control input ({type(error).__name__})")


if __name__ == "__main__":
    raise SystemExit(main())
