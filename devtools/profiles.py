"""Private native settings. The only policy here is the requested MCP-only tool surface."""

import json
import os
import shlex
import shutil
import sys
import tomllib
from pathlib import Path

from .api import SERVER, TOOLS, validate
from .serena_provider import SERVER as SERENA_SERVER
from .serena_provider import TOOL as SERENA_TOOL
from .serena_provider import enabled as serena_enabled
from .serena_provider import server_config as serena_config

ENTRY = Path(__file__).resolve().parent / "run.py"
CODEX_FEATURES = {
    "hooks": True,
    "shell_tool": False,
    "unified_exec": False,
    "apply_patch_freeform": False,
    "js_repl": False,
    "code_mode": False,
    "plugins": False,
    "apps": False,
    "multi_agent": False,
}


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(data, indent=2) + "\n")
    path.chmod(0o600)


def toml(value):
    if isinstance(value, dict):
        return "{ " + ", ".join(json.dumps(key) + " = " + toml(item) for key, item in value.items()) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(map(toml, value)) + "]"
    return json.dumps(value)


def permitted(harness, tool, arguments):
    if not isinstance(tool, str) or not isinstance(arguments, dict):
        return False
    if tool in {
        "codex": {"update_plan", "request_user_input"},
        "claude": {"EndConversation", "StructuredOutput"},
        "grok": {"search_tool"},
    }.get(harness, set()):
        return True
    if harness == "grok" and tool == "use_tool":
        if set(arguments) != {"tool_name", "tool_input"}:
            return False
        tool, arguments = arguments["tool_name"], arguments["tool_input"]
        if not isinstance(tool, str) or not isinstance(arguments, dict):
            return False
    for provider, row in [(SERVER, row) for row in TOOLS] + [(SERENA_SERVER, SERENA_TOOL)]:
        names = {f"mcp__{provider}__{row['name']}", f"{provider}__{row['name']}"}
        if harness == "codex":
            names.add(row["name"])
        if tool in names:
            try:
                validate(arguments, row["inputSchema"])
                return True
            except ValueError:
                return False
    return False


def prepare(directory, member, harness):
    """Keep global settings untouched; reuse only the selected native login files."""
    directory = Path(directory).resolve()
    private = directory / "profiles" / member
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = os.environ.copy()
    # Grok gets a private HOME below; the server still uses the operator's GitHub OAuth session.
    env.setdefault("GH_CONFIG_DIR", str(Path(env.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "gh"))
    for key in (
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "CLAUDE_CODE_SIMPLE",
        "CLAUDE_CODE_SAFE_MODE",
        "CLAUDE_CODE_SESSION_ID",
        "CODEX_THREAD_ID",
        "GROK_SESSION_ID",
    ):
        env.pop(key, None)
    hook = shlex.join(
        [sys.executable, str(ENTRY), "hook", "--state", str(directory), "--member", member, "--harness", harness]
    )
    groups = {
        name: [
            {
                **({"matcher": ".*"} if name.endswith("ToolUse") else {}),
                "hooks": [{"type": "command", "command": hook, "timeout": 10}],
            }
        ]
        for name in ("PreToolUse", "PostToolUse", "SessionStart", "Stop")
    }
    server = {"command": sys.executable, "args": [str(ENTRY), "mcp", "--state", str(directory), "--member", member]}
    if harness == "claude":
        from .control import Control
        from .store import Store

        server["args"].append("--channel")
        write_json(private / "settings.json", {"hooks": groups})
        servers = {SERVER: server}
        store = Store(directory)
        if serena_enabled(store, Control(store, member).snapshot()):
            servers[SERENA_SERVER] = serena_config(directory, member)
        write_json(private / "mcp.json", {"mcpServers": servers})
    elif harness == "codex":
        original = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        for name in ("auth.json",):
            if (original / name).is_file() and not (private / name).exists():
                shutil.copyfile(original / name, private / name)
                (private / name).chmod(0o600)
        settings = {}
        config = original / "config.toml"
        if config.is_file():
            previous = tomllib.loads(config.read_text())
            for key in ("model", "model_provider", "model_providers", "model_reasoning_effort", "service_tier"):
                if key in previous:
                    settings[key] = previous[key]
        settings.update(features=CODEX_FEATURES, mcp_servers={}, web_search="disabled")
        (private / "config.toml").write_text(
            "\n".join(f"{key} = {toml(value)}" for key, value in settings.items()) + "\n"
        )
        write_json(private / "hooks.json", {"hooks": groups})
        env["CODEX_HOME"] = str(private)
    elif harness == "grok":
        original = Path(os.environ.get("GROK_HOME", str(Path.home() / ".grok")))
        if (original / "auth.json").is_file() and not (private / "auth.json").exists():
            shutil.copyfile(original / "auth.json", private / "auth.json")
            (private / "auth.json").chmod(0o600)
        write_json(private / "hooks" / "agentscient-live.json", {"hooks": groups})
        (private / "config.toml").write_text("mcp_servers = {}\n")
        env.update(HOME=str(private), GROK_HOME=str(private), GROK_CONFIG_DIR=str(private))
    else:
        raise ValueError("Supported harnesses: codex, claude, grok")
    return private, env, server


def hook(directory, member, harness, payload):
    from .store import Store
    from .telemetry import Trace, context, observed

    store = Store(directory)
    trace = Trace(directory, member, component="hook", context=lambda: context(store, member))
    try:
        trace.record("native_hook", {"harness": harness, "payload": payload})
    finally:
        trace.close()
    observed(store, member, harness + "/hook", payload)
    if harness == "claude" and payload.get("transcript_path"):
        path = Path(payload["transcript_path"]).expanduser().resolve()
        root = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).resolve() / "projects"
        native_id = payload.get("session_id")
        if path.is_relative_to(root) and path.name == str(native_id) + ".jsonl":
            store.event(member, "native_transcript", path=str(path), native_id=native_id)
        else:
            store.event(member, "transcript_rejected", reason="Path outside the native session transcript directory")
    event = payload.get("hook_event_name", payload.get("hookEventName", "PreToolUse"))
    event = {
        "pre_tool_use": "PreToolUse",
        "post_tool_use": "PostToolUse",
        "session_start": "SessionStart",
        "stop": "Stop",
    }.get(event, event)
    tool = payload.get("tool_name", payload.get("toolName"))
    arguments = payload.get("tool_input", payload.get("toolInput", {}))
    if event == "PreToolUse":
        allowed = permitted(harness, tool, arguments)
        if harness == "claude":
            current = store.member(member)
            if current["desired"] == "running" and current["state"] == "idle":
                store.session(member, generation=current["generation"], state="active")
        store.event(member, "native_tool_allowed" if allowed else "native_tool_denied", tool=tool, harness=harness)
        if harness == "grok":
            return {"decision": "allow" if allowed else "deny", "reason": "Use this team's MCP tools."}
        return {
            "hookSpecificOutput": {
                "hookEventName": event,
                "permissionDecision": "allow" if allowed else "deny",
                "permissionDecisionReason": "Use this team's MCP tools; native shell and filesystem tools are disabled.",
            }
        }
    store.event(member, "native_hook", event=event, native_id=payload.get("session_id"), tool=tool)
    if harness == "claude" and event == "Stop":
        current = store.member(member)
        if current["desired"] == "running" and current["state"] == "active":
            store.session(member, generation=current["generation"], state="idle")
    return {}
