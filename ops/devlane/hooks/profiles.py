"""Derived native hook profiles and guarded launch transport; no policy authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from functools import cache
from pathlib import Path

HARNESSES = ("claude", "codex", "grok", "agy")
EVENTS = ("PreToolUse", "PostToolUse", "Stop", "SessionStart")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_pins(source):
    source = Path(source).resolve(strict=True)
    hooks = source / "ops/devlane/hooks"
    files = list((hooks / "claude").glob("*.py"))
    files += [hooks / name for name in ("enforcement.py", "native.py", "profiles.py", "boundaries.json")]
    files += list((source / "ops/conductor/tools").rglob("*.py"))
    files += [source / "ops/lane.conf", source / "ops/devlane/harness/isolation.py"]
    local = source / "ops/lane.local.conf"
    if local.exists() or local.is_symlink():
        files.append(local)
    if not files or any(not p.is_file() or p.resolve() != p for p in files):
        raise ValueError("unavailable stable policy closure")
    return {str(path): digest(path) for path in sorted(set(files))}


def freeze_runtime(source, destination):
    """Publish a private byte copy of the trusted installation's policy closure.

    The caller supplies its installation, never the worker's candidate tree.
    Verify both sides of the copy so an overlapping edit cannot mint mixed pins.
    The native transport makes the whole published directory read-only.
    """
    source, destination = Path(source).resolve(strict=True), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("worker runtime already exists without its binding")
    pins = source_pins(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".runtime-", dir=destination.parent))
    try:
        expected = {}
        for name, sha in pins.items():
            target = staging / Path(name).relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(Path(name).read_bytes())
            expected[str(target)] = sha
        if source_pins(staging) != expected or source_pins(source) != pins:
            raise ValueError("trusted policy changed while freezing worker runtime")
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination


def verify_runtime(binding, source, *, previous=None):
    """Check retained bytes before importing any Python from an issued runtime."""
    source = Path(source).absolute()
    previous = Path(previous) if previous is not None else source
    if source.resolve(strict=True) != source or binding["source"] != str(previous):
        raise ValueError("worker runtime is not its issued directory")
    expected = {str(source / Path(name).relative_to(previous)): sha
                for name, sha in binding["pins"].items()}
    if source_pins(source) != expected:
        raise ValueError("issued worker runtime changed")


def fallback(harness, event):
    reason = "hook-unavailable: expected a complete pinned shared guard; found missing or changed helper; needed regenerate the reviewed profile and inspect co_doc.py"
    if harness == "agy":
        return {"decision": "continue" if event == "Stop" else "deny", "reason": reason}
    if event == "PreToolUse":
        return {"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny", "permissionDecisionReason": reason}}
    if event == "Stop":
        return {"continue": False, "stopReason": reason}
    return {"decision": "block", "reason": reason}


def helper_text(binding):
    """Reuse control.py's pinned-helper/fallback mechanism, not its action policy."""
    lines = ["#!/bin/sh", "set -u", 'event=${1:-PreToolUse}', 'case "$event" in']
    for event in EVENTS:
        lines.append(f"{event}) denial={shlex.quote(canonical(fallback(binding['harness'], event)))} ;;")
    lines += [f"*) denial={shlex.quote(canonical(fallback(binding['harness'], 'PreToolUse')))} ;;", "esac",
              'block() { printf "%s\\n" "$denial"; exit 0; }']
    for path, expected in sorted({**binding["pins"], **binding["config_pins"]}.items()):
        lines.append(f'[ "$(/usr/bin/sha256sum {shlex.quote(path)} 2>/dev/null)" = {shlex.quote(expected + "  " + path)} ] || block')
    # Only the evaluator receives authority-store context. The harness continues
    # to use its own isolated HOME/configuration and never inherits this HOME.
    for key, value in sorted(binding["authority_environment"].items()):
        lines.append("export " + key + "=" + shlex.quote(value))
    command = [binding["python"], "-I", "-B", str(Path(binding["source"]) / "ops/devlane/hooks/enforcement.py"),
               "--harness", binding["harness"], "--binding", binding["binding"]]
    lines += ['result=$(' + shlex.join(command) + ' --event "$event") || block',
              '[ -n "$result" ] || block', 'printf "%s\\n" "$result"', ""]
    return "\n".join(lines)


def toml_value(value):
    if isinstance(value, dict):
        return "{" + ", ".join(json.dumps(k) + " = " + toml_value(v) for k, v in sorted(value.items())) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    if not isinstance(value, (str, bool, int, float)):
        raise ValueError("unsupported native configuration value")
    return json.dumps(value, allow_nan=False)


def normalized_settings(settings, helper):
    """Copy preserved settings without another participant's identity or secret."""
    settings = json.loads(json.dumps(settings or {}))
    servers = settings.get("mcp_servers", {})
    for server in servers.values():
        environment = server.setdefault("env", {})
        for key in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "GROK_SESSION_ID", "COORDINATION_CAPABILITY"):
            environment.pop(key, None)
        environment["AGENTSCIENT_HOOK_PROFILE"] = str(helper.parent / "binding.json")
    return settings


def configuration(harness, native_home, helper, cwd, settings=None):
    configs = {}
    settings = normalized_settings(settings, helper)
    servers = settings.get("mcp_servers", {})
    events = EVENTS if harness != "agy" else ("PreToolUse", "PostToolUse", "Stop", "PreInvocation")
    event_groups = {}
    for event in events:
        # PreInvocation initializes an interactive native identity only. It is
        # never presented as a dispatch job or a SessionStart interception proof.
        hook_event = "SessionStart" if event == "PreInvocation" else event
        action = {"type": "command", "command": shlex.join(["/bin/sh", str(helper), hook_event]), "timeout": 120}
        event_groups[event] = ([{"matcher": ".*", "hooks": [action]}]
                               if event in {"PreToolUse", "PostToolUse"} else [{"hooks": [action]}])
    if harness == "agy":
        for event in ("Stop", "PreInvocation"):
            event_groups[event] = event_groups[event][0]["hooks"]
        configs[native_home / ".gemini/config/hooks.json"] = canonical({"agentscient-shared": {"enabled": True, **event_groups}})
        if servers:
            configs[native_home / ".gemini/config/mcp_config.json"] = canonical({"mcpServers": servers})
    elif harness == "claude":
        configs[helper.parent / "settings.json"] = canonical({"hooks": event_groups})
        if servers:
            configs[helper.parent / "mcp.json"] = canonical({"mcpServers": servers})
    elif harness == "codex":
        configs[native_home / "hooks.json"] = canonical({"hooks": event_groups})
        prefix = "".join(json.dumps(key) + " = " + toml_value(value) + "\n" for key, value in sorted(settings.items()))
        configs[native_home / "config.toml"] = (prefix + '[features]\nhooks = true\nunified_exec_tty = false\nshell_snapshot = false\nplugins = false\napps = false\nmulti_agent = false\n'
             '\n[projects.' + json.dumps(str(cwd)) + ']\ntrust_level = "trusted"\n')
    else:
        configs[native_home / "hooks/agentscient.json"] = canonical({"hooks": event_groups})
        if servers:
            configs[native_home / "config.toml"] = 'mcp_servers = ' + toml_value(servers) + '\n'
    return configs


def generate(harness, destination, *, source, cwd, mode, home=None, session=None,
             agent=None, servers=(), executable=None, native_settings=None, credential_environment=None):
    if harness not in HARNESSES or mode not in {"interactive", "worker"}:
        raise ValueError("unknown harness or startup mode")
    if mode == "worker" and not session:
        raise ValueError("worker profile requires its issued assignment session")
    source, cwd, dest = Path(source).resolve(strict=True), Path(cwd).resolve(strict=True), Path(destination).absolute()
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise ValueError("profile destination must be new or empty")
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    native_home = Path(home).resolve(strict=True) if home else dest
    helper = dest / "guard.sh"
    native_settings = normalized_settings(native_settings, helper)
    configs = configuration(harness, native_home, helper, cwd, native_settings)
    for path, content in configs.items():
        if path.exists() or path.is_symlink():
            raise ValueError(f"refusing to replace existing native configuration: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    authority = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(Path.home()), "XDG_STATE_HOME": str(Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))).resolve()),
                 "LANE_CONF": str(source / "ops/lane.conf")}
    if agent:
        authority["WF_AGENT_OVERRIDE"] = agent
    binding = {"schema": "shared-hook-profile/1", "harness": harness, "mode": mode,
               "source": str(source), "cwd": str(cwd), "home": str(native_home),
               "helper": str(helper), "binding": str(dest / "binding.json"),
               "python": str(Path(sys.executable).resolve()), "session": session,
               "coordination_capability": secrets.token_hex(32),
               "servers": list(servers), "authority_environment": authority,
               "native_settings": native_settings,
               "credential_environment": credential_environment or {},
               "pins": source_pins(source), "config_pins": {str(p): digest(p) for p in configs},
               "executable": str(Path(executable).resolve(strict=True)) if executable else None,
               "executable_sha256": digest(executable) if executable else None}
    binding["helper_sha256"] = hashlib.sha256(helper_text(binding).encode()).hexdigest()
    with os.fdopen(os.open(binding["binding"], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as private:
        private.write(canonical(binding))
    helper.write_text(helper_text(binding))
    helper.chmod(0o700)
    return binding


def read_binding(path):
    raw = Path(path).read_text()
    value = json.loads(raw)
    if not isinstance(value, dict) or canonical(value) != raw:
        raise ValueError("malformed profile projection")
    return value


def validate(binding):
    if binding.get("schema") != "shared-hook-profile/1" or binding.get("harness") not in HARNESSES:
        raise ValueError("unknown profile projection")
    if binding.get("mode") not in {"worker", "interactive"} or (binding["mode"] == "worker" and not binding.get("session")):
        raise ValueError("invalid startup identity mode")
    capability = binding.get("coordination_capability")
    if not isinstance(capability, str) or not re.fullmatch(r"[0-9a-f]{64}", capability):
        raise ValueError("missing or malformed coordination capability")
    if Path(binding["source"]).resolve() != Path(__file__).resolve().parents[3]:
        raise ValueError("policy source is not this trusted installation")
    if source_pins(binding["source"]) != binding["pins"]:
        raise ValueError("policy closure changed")
    registry = json.loads((Path(binding["source"]) / "ops/devlane/hooks/boundaries.json").read_text())
    if binding["harness"] == "agy" and any(row.get("engine") and row.get("event") in {"PostToolUse", "SessionStart"} for row in registry["rows"]):
        raise ValueError("agy lacks a verified immediate post-tool/start decision channel for these required rows")
    expected_configs = configuration(binding["harness"], Path(binding["home"]), Path(binding["helper"]), Path(binding["cwd"]), binding.get("native_settings"))
    expected_pins = {str(path): hashlib.sha256(content.encode()).hexdigest() for path, content in expected_configs.items()}
    if expected_pins != binding["config_pins"]:
        raise ValueError("profile does not project the shared guard")
    for path, expected in binding["config_pins"].items():
        if Path(path).is_symlink() or digest(path) != expected:
            raise ValueError("native hook configuration changed")
    if digest(binding["helper"]) != binding["helper_sha256"] or Path(binding["helper"]).read_text() != helper_text(binding):
        raise ValueError("native helper changed")
    if read_binding(binding["binding"]) != binding:
        raise ValueError("binding changed")
    if binding["executable"] and digest(binding["executable"]) != binding["executable_sha256"]:
        raise ValueError("native executable changed")
    return binding



def relocate(binding, old_root, new_root):
    """Reproject an unchanged guard when the existing dispatcher relocates a job."""
    old_root, new_root = Path(old_root), Path(new_root)
    if binding["mode"] != "worker" or Path(binding["binding"]) != old_root / "enforcement/binding.json":
        raise ValueError("relocation is not the recorded worker profile")
    def moved(path):
        p = Path(path)
        return str(new_root / p.relative_to(old_root)) if p.is_relative_to(old_root) else str(p)
    pins = {moved(path): sha for path, sha in binding["pins"].items()}
    if source_pins(moved(binding["source"])) != pins:
        raise ValueError("relocated policy closure changed")
    configs = configuration(binding["harness"], Path(binding["home"]), Path(binding["helper"]), Path(binding["cwd"]), binding.get("native_settings"))
    expected = {str(p): hashlib.sha256(content.encode()).hexdigest() for p, content in configs.items()}
    if expected != binding["config_pins"]:
        raise ValueError("relocated configuration is not a shared projection")
    for path, sha in binding["config_pins"].items():
        if digest(moved(path)) != sha:
            raise ValueError("relocated native configuration changed")
    if Path(moved(binding["helper"])).read_text() != helper_text(binding):
        raise ValueError("relocated helper changed")
    revised = {**binding}
    for key in ("source", "cwd", "home", "helper", "binding"):
        revised[key] = moved(binding[key])
    revised["pins"] = pins
    revised["authority_environment"] = {**binding["authority_environment"],
                                        "LANE_CONF": moved(binding["authority_environment"]["LANE_CONF"])}
    configs = configuration(revised["harness"], Path(revised["home"]), Path(revised["helper"]), Path(revised["cwd"]), revised.get("native_settings"))
    revised["config_pins"] = {str(p): hashlib.sha256(content.encode()).hexdigest() for p, content in configs.items()}
    revised["helper_sha256"] = hashlib.sha256(helper_text(revised).encode()).hexdigest()
    for path, content in configs.items():
        path.write_text(content)
    Path(revised["helper"]).write_text(helper_text(revised))
    Path(revised["binding"]).write_text(canonical(revised))
    Path(revised["binding"]).chmod(0o600)
    return validate(revised)


def codex_config_args(tokens):
    """Normalize native spellings; admit only existing launcher config fields."""
    result = []
    pending = iter(tokens)
    for arg in pending:
        if arg == "--":
            return [*result, arg, *pending]
        if arg in {"-c", "--config"}:
            value = next(pending, "")
        elif arg.startswith("--config="):
            value = arg[len("--config="):]
        elif arg.startswith("-c") and not arg.startswith("--"):
            value = arg[2:].removeprefix("=")
        else:
            result.append(arg)
            continue
        key, separator, raw = value.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*", key):
            raise ValueError("malformed native configuration assignment")
        admitted = key in {"model_reasoning_effort", "sandbox_workspace_write.writable_roots"} or re.fullmatch(
            r"mcp_servers\.[A-Za-z0-9_-]+\.(?:command|args|env_vars|required|enabled_tools|tools\.[A-Za-z0-9_-]+\.approval_mode)", key)
        if not admitted:
            raise ValueError("native configuration field is not a launcher projection")
        parsed = tomllib.loads("value=" + raw)
        if set(parsed) != {"value"} or "\n" in raw or "\r" in raw:
            raise ValueError("native configuration requires one TOML value")
        result += ["-c", value]
    return result


# The harnesses a managed session runs as a member (sessions-lever.md, Slice 2).
MEMBER_HARNESSES = ("claude", "codex", "grok")
# The sessions bridge's protocol channel per harness (sessions-lever.md, Slice 2,
# "Required of the wall" (1)): admitted only whole, with nothing before or after it.
CHANNELS = {"codex": ("app-server", "--listen", "stdio://"), "grok": ("--no-auto-update", "agent", "stdio")}


def interactive_args(harness, tokens):
    """Admit session UI arguments, never alternate native authority/configuration."""
    if tuple(tokens) == CHANNELS.get(harness):
        return list(tokens)
    groups = {
        "codex": {"value": "--model -m", "flag": "--no-alt-screen --strict-config --help -h --version -V"},
        "claude": {"value": "--model --effort --output-format --input-format --max-budget-usd", "uuid": "--session-id",
                   "optional": "--resume -r", "flag": "--continue -c --print -p --verbose --include-partial-messages --include-hook-events --help -h --version -v"},
        "grok": {"value": "--model -m --reasoning-effort --effort --output-format --max-turns",
                 "prompt": "--single -p", "optional": "--resume -r",
                 "flag": "--continue -c --minimal --fullscreen --no-alt-screen --include-partial-messages --help -h --version -v"},
        "agy": {"value": "--model --effort --output-format --input-format --print-timeout --conversation",
                "prompt": "--print --prompt -p --prompt-interactive -i", "flag": "--continue -c --help -h"},
    }
    grammar = {name: kind for kind, names in groups[harness].items() for name in names.split()}
    result, index, resume, session = [], 0, False, False
    while index < len(tokens):
        arg = tokens[index]
        index += 1
        if arg == "--":
            if len(tokens[index:]) != 1:
                raise ValueError("native prompt requires one argument after --")
            return [*result, arg, *tokens[index:]]
        if not arg.startswith("-"):
            if harness == "codex" and arg == "resume" and not resume:
                resume = True
                grammar.update({name: "flag" for name in ("--last", "--all", "--include-non-interactive")})
            elif harness == "codex" and resume and not session and arg:
                session = True
            else:
                raise ValueError("unknown native command; supply prompt after --")
            result.append(arg)
            continue
        name, equals, value = arg.partition("=")
        if not arg.startswith("--") and len(arg) > 2:
            name, equals, value = arg[:2], "=", arg[2:].removeprefix("=")
        kind = grammar.get(name)
        if kind is None or (kind == "flag" and equals):
            raise ValueError("native interactive option is not admitted: " + name)
        if kind == "flag":
            result.append(name)
            continue
        if not equals:
            if kind == "optional" and (index == len(tokens) or tokens[index].startswith("-")):
                result.append(name)
                continue
            if index == len(tokens):
                raise ValueError("native option requires a value: " + name)
            value = tokens[index]
            index += 1
        if value.startswith("-") or (not value and kind != "prompt"):
            raise ValueError("native option has an ambiguous or missing value: " + name)
        if kind == "uuid" and not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value, re.IGNORECASE):
            raise ValueError("native option requires a UUID: " + name)
        result += [name, value]
    return result


def native_launch(binding, argv, env):
    """Keep interactive argument admission separate from issued worker startup."""
    validate(binding)
    if not isinstance(argv, (list, tuple)) or not argv or any(not isinstance(t, str) or "\0" in t for t in argv):
        raise ValueError("native argv must be a nonempty string vector")
    if not binding["executable"] or str(Path(argv[0]).resolve()) != binding["executable"]:
        raise ValueError("launch executable was not pinned")
    harness = binding["harness"]
    tokens = list(argv[1:])
    if binding["mode"] == "interactive":
        tokens = interactive_args(harness, tokens)
    if harness == "claude" and binding["mode"] == "worker":
        for index in range(len(tokens) - 1, -1, -1):
            if tokens[index:index + 2] == ["--setting-sources", "project,local"]:
                del tokens[index:index + 2]
    denied = ("--settings", "--setting-sources", "--bare", "--safe-mode", "--agent", "--plugin-dir", "--dangerously-bypass-hook-trust", "--enable", "--disable")
    if binding["mode"] == "worker" and any(t.split("=", 1)[0] in denied for t in tokens):
        raise ValueError("native argv changes the guarded profile")
    if harness == "codex":
        tokens = codex_config_args(tokens)
    if binding["authority_environment"]["HOME"] != str(Path.home()):
        raise ValueError("authority HOME differs from the trusted launcher")
    out = dict(env)
    out.pop("COORDINATION_CAPABILITY", None)
    out["COORDINATION_CAPABILITY"] = binding["coordination_capability"]
    if binding["authority_environment"].get("WF_AGENT_OVERRIDE"):
        out["WF_AGENT_OVERRIDE"] = binding["authority_environment"]["WF_AGENT_OVERRIDE"]
    for key in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "GROK_SESSION_ID"):
        out.pop(key, None)
    # The admitted launch id reaches the hook through the child environment, never
    # the binding, which one profile keeps across launches; initialize compares it.
    out.pop("AGENTSCIENT_LAUNCH_SESSION", None)
    options = tokens[:tokens.index("--")] if "--" in tokens else tokens
    if binding["mode"] == "interactive" and "--session-id" in options:
        out["AGENTSCIENT_LAUNCH_SESSION"] = options[options.index("--session-id") + 1]
    if binding["mode"] == "worker":
        out["CLAUDE_SESSION_ID"] = binding["session"]
    for key in ("CLAUDE_CODE_SIMPLE", "CLAUDE_CODE_SAFE_MODE", "BOUNDARIES_PATH", "PYTHONPATH", "PYTHONSTARTUP"):
        out.pop(key, None)
    if harness == "claude":
        tokens = ["--setting-sources", "", "--settings", str(Path(binding["helper"]).parent / "settings.json"), *tokens]
        if binding.get("native_settings", {}).get("mcp_servers"):
            if "--mcp-config" in tokens:
                raise ValueError("interactive MCP configuration is already projected")
            tokens = ["--strict-mcp-config", "--mcp-config", str(Path(binding["helper"]).parent / "mcp.json"), *tokens]
    elif harness == "codex":
        tokens = [x for x in tokens if x != "--ignore-user-config"]
        tokens.insert(1 if tokens and tokens[0] == "exec" else 0, "--dangerously-bypass-hook-trust")
        out["CODEX_HOME"] = binding["home"]
    elif harness == "grok":
        out.update(HOME=binding["home"], GROK_HOME=binding["home"])
    else:
        out["HOME"] = binding["home"]
    bubble = shutil.which("bwrap")
    if not bubble:
        raise ValueError("profile write protection unavailable: install bubblewrap")
    # Retain the existing harness sandbox/isolation. Add read-only bind mounts
    # only for trusted policy and derived configuration, not a second workspace
    # permission policy. In particular, do not hide dispatch output/session paths.
    command = [bubble, "--die-with-parent", "--unshare-user", "--bind", "/", "/", "--proc", "/proc", "--dev", "/dev"]
    protected = {str(Path(binding["source"]) / "ops/devlane/hooks"),
                 str(Path(binding["source"]) / "ops/conductor/tools"),
                 *binding["pins"], binding["helper"], binding["binding"], *binding["config_pins"]}
    if binding["mode"] == "worker" and Path(binding["source"]) == Path(binding["binding"]).parent.parent / "runtime":
        protected.add(binding["source"])
    for path in sorted(protected):
        command += ["--ro-bind", path, path]
    out["AGENTSCIENT_HOOK_PROFILE"] = binding["binding"]
    command += ["--chdir", binding["cwd"], "--", binding["executable"], *tokens]
    return command, out


def initialize(binding, native_payload, *, instrument):
    """Bind interactive native identity; validate an issued worker independently.

    The existing coordination core owns participant/role authority. No dispatch
    job is synthesized for an interactive terminal and no parent id is inherited.
    """
    import importlib.util
    validate(binding)
    native_id = native_payload.get("conversationId") if binding["harness"] == "agy" else native_payload.get("session_id", native_payload.get("sessionId"))
    session = binding["session"] if binding["mode"] == "worker" else native_id
    if not isinstance(session, str) or not session.strip() or len(session) > 128:
        raise ValueError("native/issued session identity unavailable")
    launch = os.environ.get("AGENTSCIENT_LAUNCH_SESSION")
    if binding["mode"] == "interactive" and launch and launch != session:
        raise ValueError(f"native: expected the launch session id {launch}; found {session}; "
                         "needed the native session the launch named: relaunch the profile, never rebind it")
    os.environ.pop("AGENTSCIENT_HOOK_PROFILE", None)
    os.environ["COORDINATION_CAPABILITY"] = binding["coordination_capability"]
    for key in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "GROK_SESSION_ID"):
        os.environ.pop(key, None)
    # This is the instrument's existing generic issued-session carrier. Native
    # aliases are cleared first, so an inherited Claude identity cannot win.
    os.environ["CLAUDE_SESSION_ID"] = session
    if not instrument.state_db().is_file():
        raise ValueError("existing coordination store unavailable")
    path = Path(binding["source"]) / "ops/conductor/tools/coordination.py"
    spec = importlib.util.spec_from_file_location("hook_coordination", path)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    conn = core.reader()
    try:
        if binding["mode"] == "interactive" and conn.execute(
                "SELECT 1 FROM participants WHERE capability_digest = ? AND session_id != ?",
                (instrument.capability_digest(binding), session)).fetchone():
            raise ValueError("profile already belongs to another native terminal; resume it or prepare a new profile")
        participant = core.maybe_participant(conn)
        if participant is not None:
            core.require_role(participant, core.ROLES)
    finally:
        conn.close()
    if participant is None:
        if binding["mode"] != "interactive":
            raise ValueError("worker has no issued participant")
        with core.writer() as conn:
            core.core_bind(conn, None, agent=instrument.identity(), roles="worker", harness=binding["harness"],
                           endpoint="hook-profile:" + binding["binding"], probe="native shared-hook interactive registration")
    elif participant["harness"] not in (None, binding["harness"]):
        raise ValueError("participant harness differs from native binding")
    elif binding["mode"] == "interactive":
        endpoint = "hook-profile:" + binding["binding"]
        if participant["endpoint"] is None:
            with core.writer() as conn:
                core.core_bind(conn, participant, agent=instrument.identity(), roles=participant["roles"], harness=binding["harness"],
                               endpoint=endpoint, probe="native shared-hook interactive registration")
    return session


@cache
def isolation_owner(expected=None):
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "harness/isolation.py"
    source = path.read_bytes()
    if expected is not None and hashlib.sha256(source).hexdigest() != expected:
        raise ValueError("credential custody source changed before import")
    spec = importlib.util.spec_from_file_location("profile_isolation", path)
    module = importlib.util.module_from_spec(spec)
    # Execute exactly the checked bytes, never a writable adjacent .pyc. This
    # owner imports only stdlib dependencies, loaded before the native child.
    exec(compile(source, str(path), "exec"), module.__dict__)  # noqa: S102 - pinned source owner
    return module


def capture_custody(binding):
    """Retain this attempt's validated owner and credential directory identities."""
    validate(binding)
    owner = isolation_owner(binding["pins"][str(Path(binding["source"]) / "ops/devlane/harness/isolation.py")])
    admitted = canonical(binding)
    home = Path(binding["home"])
    directories = {home}
    for name in owner.HARNESSES[binding["harness"]]["auth_files"]:
        leaf = Path(name)
        if leaf.is_absolute() or ".." in leaf.parts or not leaf.name:
            raise ValueError("credential custody requires a declared relative leaf")
        directories.update(home / parent for parent in leaf.parents)

    def identity(path):
        current = path.lstat()
        if not stat.S_ISDIR(current.st_mode):
            raise ValueError(f"credential custody directory is not a real directory: {path}")
        return current.st_dev, current.st_ino

    retained = tuple((path, identity(path)) for path in sorted(directories))

    def carry_back(current_binding, env=None):
        validate(current_binding)
        if canonical(current_binding) != admitted:
            raise ValueError("credential custody binding differs from the pre-child capture")
        for path, before in retained:
            if identity(path) != before:
                raise ValueError(f"credential custody directory changed after launch: {path}")
        return owner.carry_back(current_binding["harness"], home, env=env)

    return carry_back


def coordination_server(harness, source):
    """The acting coordination server a member's profile registers (sessions-lever.md,
    Slice 2, "Required of the wall" (3)), replacing any operator copy of that name. It
    resolves its caller through AGENTSCIENT_HOOK_PROFILE, which normalized_settings
    adds. The codex bridge declines every approval its app-server asks, so codex
    approves this server's tools; the core's role gate still runs inside every verb."""
    server = {"command": str(Path(sys.executable).resolve()),
              "args": ["-B", str(Path(source) / "ops/conductor/tools/coordination_mcp.py"), "serve"]}
    if harness == "codex":
        server["default_tools_approval_mode"] = "approve"
    return server


def prepare_interactive(harness, destination, *, source, cwd, agent, executable):
    """Reuse credential custody and project existing registered MCP definitions."""
    isolation = isolation_owner()
    dest = Path(destination).absolute()
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise ValueError("interactive destination must be new or empty")
    env = dict(os.environ)
    settings = {}
    if harness in {"codex", "grok"}:
        config = isolation._real_home(harness, env) / "config.toml"
        if config.is_file():
            existing = tomllib.loads(config.read_text())
            keys = ("mcp_servers", "model", "model_provider", "model_providers", "model_reasoning_effort", "service_tier") if harness == "codex" else ("mcp_servers",)
            settings = {key: existing[key] for key in keys if key in existing}
    else:
        files = ([Path(env["HOME"]) / ".claude.json", Path(cwd) / ".mcp.json"] if harness == "claude"
                 else [Path(env["HOME"]) / ".gemini/config/mcp_config.json"])
        servers = {}
        for config in files:
            if config.is_file():
                existing = json.loads(config.read_text())
                servers.update(existing.get("mcpServers", {}))
                if harness == "claude":
                    servers.update(existing.get("projects", {}).get(str(Path(cwd).resolve()), {}).get("mcpServers", {}))
        if servers:
            settings["mcp_servers"] = servers
    if harness in MEMBER_HARNESSES:
        settings["mcp_servers"] = {**settings.get("mcp_servers", {}), "coordination": coordination_server(harness, source)}
    # Use exactly the existing credential leaves and renewal-custody mechanism.
    home = isolation.build_home(harness, dest / "home", env=env)
    return generate(harness, dest / "profile", source=source, cwd=cwd, mode="interactive", home=home,
                    agent=agent, executable=executable, servers=tuple(settings.get("mcp_servers", {})), native_settings=settings,
                    credential_environment={key: env[key] for key in ("HOME", "CODEX_HOME", "GROK_HOME") if key in env})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare-interactive", "run-interactive", "check"))
    parser.add_argument("--binding")
    parser.add_argument("--harness", choices=HARNESSES)
    parser.add_argument("--destination")
    parser.add_argument("--cwd")
    parser.add_argument("--executable")
    parser.add_argument("--agent")
    tokens = list(sys.argv[1:] if argv is None else argv)
    split = tokens.index("--") if "--" in tokens else len(tokens)
    native_args = tokens[split + 1:]
    args = parser.parse_args(tokens[:split])
    try:
        if args.operation == "run-interactive":
            binding = read_binding(args.binding)
            if binding.get("mode") != "interactive":
                raise ValueError("interactive launch requires an interactive projection")
            command, env = native_launch(binding, [binding["executable"], *native_args], os.environ)
            custody = capture_custody(binding)
            try:
                return subprocess.call(command, env=env)  # noqa: S603 - interactive lifetime; inherited terminal streams
            finally:
                custody(binding, env=binding["credential_environment"])
        elif args.operation == "check":
            validate(read_binding(args.binding))
            print("shared hook profile: valid projection; native interception requires its measured witness")
        else:
            if not all((args.harness, args.destination, args.cwd, args.executable, args.agent)):
                raise ValueError("interactive preparation requires harness, destination, cwd, executable and agent")
            binding = prepare_interactive(args.harness, args.destination, source=Path(__file__).resolve().parents[3],
                                          cwd=args.cwd, agent=args.agent, executable=args.executable)
            print(binding["binding"])
    except Exception as exc:  # noqa: BLE001 - refusal must not import an unvalidated custody owner
        print(f"hook-profile: expected a complete pinned native projection; found {exc}; needed inspect co_doc.py and regenerate the reviewed profile", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
