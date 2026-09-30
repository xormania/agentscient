"""Private native settings. The only policy here is the requested MCP-only tool surface."""

import hashlib
import json
import os
import shlex
import shutil
import sys
import tomllib
from pathlib import Path

from .api import API, SERVER, TOOLS, validate
from .role_packages import HOOK_EVENTS, descriptor
from .role_packages import role as role_package
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


def restore_login(private, original, harness):
    """Carry refreshed private credentials forward; a changed operator login wins."""
    source = original / "auth.json"
    digest = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
    cache = private.parent / (harness + "-login.json")
    previous = json.loads(cache.read_text()) if cache.is_file() else {}
    destination = private / "auth.json"
    if previous.get("source_sha256") == digest and "auth" in previous:
        destination.write_text(previous["auth"])
    elif source.is_file():
        shutil.copyfile(source, destination)
    if destination.exists():
        destination.chmod(0o600)
    write_json(private / "login-origin.json", {"source_sha256": digest, "harness": harness})


def retain_login(directory, member, harness, generation):
    if harness not in {"codex", "grok"}:
        return
    private = Path(directory) / "profiles" / member / generation
    if (private / "auth.json").is_file() and (private / "login-origin.json").is_file():
        origin = json.loads((private / "login-origin.json").read_text())
        write_json(private.parent / (harness + "-login.json"),
                   {"source_sha256": origin["source_sha256"], "auth": (private / "auth.json").read_text()})


def permitted(harness, tool, arguments, *, catalogue=None):
    if (not isinstance(harness, str) or harness not in {"codex", "claude", "grok"}
            or not isinstance(tool, str) or not isinstance(arguments, dict)):
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
    catalogue = {SERVER: TOOLS, SERENA_SERVER: [SERENA_TOOL]} if catalogue is None else catalogue
    for provider, row in [(provider, row) for provider, rows in catalogue.items() for row in rows]:
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


def tool_catalogue(directory, member):
    """Read the live trusted binding; the native launch catalog is not authority."""
    api = API(directory, member)
    scope = api.control.snapshot()
    result = {SERVER: api._tools(scope)}
    if serena_enabled(api.store, scope):
        result[SERENA_SERVER] = [SERENA_TOOL]
    return result


def prepare(directory, member, harness):
    """Keep global settings untouched; reuse only the selected native login files."""
    directory = Path(directory).resolve()
    from .store import Store

    store = Store(directory)
    api = API(directory, member)
    scope = api.control.snapshot()
    package = role_package(scope["role"]) if scope else None
    if package and harness not in package["runtime"]["harnesses"]:
        raise ValueError("This role package does not permit the selected harness")
    generation = store.member(member)["generation"]
    private = directory / "profiles" / member
    if generation:
        private /= generation
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    if package:
        write_json(private / "role-package.json", {**descriptor(scope["role"]), "binding_revision": scope["revision"]})
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
    lease_args = ["--generation", generation] if generation else []
    hook = shlex.join(
        [sys.executable, str(ENTRY), "hook", "--state", str(directory), "--member", member, "--harness", harness,
         *lease_args]
    )
    groups = {
        name: [
            {
                **({"matcher": ".*"} if name.endswith("ToolUse") else {}),
                "hooks": [{"type": "command", "command": hook, "timeout": 10}],
            }
        ]
        for name in (package["hooks"]["events"] if package else HOOK_EVENTS)
    }
    server = {"command": sys.executable,
              "args": [str(ENTRY), "mcp", "--state", str(directory), "--member", member, *lease_args]}
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
        restore_login(private, original, harness)
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
        restore_login(private, original, harness)
        write_json(private / "hooks" / "agentscient-live.json", {"hooks": groups})
        # Native child sessions and workflows bypass the command service's
        # role/job bindings. Disable them in the private configuration and
        # override inherited feature switches before the ACP process starts.
        settings = {"mcp_servers": {}, "subagents": {"enabled": False},
                    "workflows": {"enabled": False}, "goal": {"enabled": False}}
        (private / "config.toml").write_text(
            "\n".join(f"{key} = {toml(value)}" for key, value in settings.items()) + "\n"
        )
        env.update(HOME=str(private), GROK_HOME=str(private), GROK_CONFIG_DIR=str(private),
                   GROK_SUBAGENTS="0", GROK_WORKFLOWS="0", GROK_GOAL="0")
    else:
        raise ValueError("Supported harnesses: codex, claude, grok")
    return private, env, server


def hook(directory, member, harness, payload, generation=None):
    from .sessions import Lease
    from .store import Store

    with Lease(Store(directory), member, generation).hold():
        return _hook(directory, member, harness, payload)


def _hook(directory, member, harness, payload):
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
    if event == "SessionStart" and isinstance(payload.get("session_id"), str):
        current = store.member(member)
        if current["native_id"] is None and current["generation"] is not None:
            store.session(member, generation=current["generation"], native_id=payload["session_id"])
    tool = payload.get("tool_name", payload.get("toolName"))
    arguments = payload.get("tool_input", payload.get("toolInput", {}))
    if event == "PreToolUse":
        allowed = permitted(harness, tool, arguments, catalogue=tool_catalogue(directory, member))
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
