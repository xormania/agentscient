"""Derived native hook profiles and guarded launch transport; no policy authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import sys
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
    files += list((source / "ops/conductor/tools").glob("*.py"))
    files += [source / "ops/lane.conf"]
    if not files or any(not p.is_file() or p.is_symlink() for p in files):
        raise ValueError("unavailable stable policy closure")
    return {str(path): digest(path) for path in sorted(set(files))}


def fallback(harness, event):
    reason = "hook-unavailable: expected a complete pinned shared guard; found missing or changed helper; needed regenerate the reviewed profile and inspect co_doc.py"
    if harness == "agy":
        return {"decision": "continue" if event == "Stop" else "deny", "reason": reason}
    if event == "PreToolUse":
        return {"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny", "permissionDecisionReason": reason}}
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


def configuration(harness, native_home, helper, cwd):
    configs = {}
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
    elif harness == "claude":
        configs[helper.parent / "settings.json"] = canonical({"hooks": event_groups})
    elif harness == "codex":
        configs[native_home / "hooks.json"] = canonical({"hooks": event_groups})
        configs[native_home / "config.toml"] = ('[features]\nhooks = true\nunified_exec_tty = false\nshell_snapshot = false\nplugins = false\napps = false\nmulti_agent = false\n'
             '\n[projects.' + json.dumps(str(cwd)) + ']\ntrust_level = "trusted"\n')
    else:
        configs[native_home / "hooks/agentscient.json"] = canonical({"hooks": event_groups})
    return configs


def generate(harness, destination, *, source, cwd, mode, home=None, session=None,
             agent=None, servers=(), executable=None):
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
    configs = configuration(harness, native_home, helper, cwd)
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
               "servers": list(servers), "authority_environment": authority,
               "pins": source_pins(source), "config_pins": {str(p): digest(p) for p in configs},
               "executable": str(Path(executable).resolve(strict=True)) if executable else None,
               "executable_sha256": digest(executable) if executable else None}
    binding["helper_sha256"] = hashlib.sha256(helper_text(binding).encode()).hexdigest()
    Path(binding["binding"]).write_text(canonical(binding))
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
    if Path(binding["source"]).resolve() != Path(__file__).resolve().parents[3]:
        raise ValueError("policy source is not this trusted installation")
    if source_pins(binding["source"]) != binding["pins"]:
        raise ValueError("policy closure changed")
    registry = json.loads((Path(binding["source"]) / "ops/devlane/hooks/boundaries.json").read_text())
    if binding["harness"] == "agy" and any(row.get("engine") and row.get("event") in {"PostToolUse", "SessionStart"} for row in registry["rows"]):
        raise ValueError("agy lacks a verified immediate post-tool/start decision channel for these required rows")
    expected_configs = configuration(binding["harness"], Path(binding["home"]), Path(binding["helper"]), Path(binding["cwd"]))
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
    if source_pins(binding["source"]) != binding["pins"]:
        raise ValueError("relocated policy closure changed")
    def moved(path):
        p = Path(path)
        return str(new_root / p.relative_to(old_root)) if p.is_relative_to(old_root) else str(p)
    configs = configuration(binding["harness"], Path(binding["home"]), Path(binding["helper"]), Path(binding["cwd"]))
    expected = {str(p): hashlib.sha256(content.encode()).hexdigest() for p, content in configs.items()}
    if expected != binding["config_pins"]:
        raise ValueError("relocated configuration is not a shared projection")
    for path, sha in binding["config_pins"].items():
        if digest(moved(path)) != sha:
            raise ValueError("relocated native configuration changed")
    if Path(moved(binding["helper"])).read_text() != helper_text(binding):
        raise ValueError("relocated helper changed")
    revised = {**binding}
    for key in ("cwd", "home", "helper", "binding"):
        revised[key] = moved(binding[key])
    configs = configuration(revised["harness"], Path(revised["home"]), Path(revised["helper"]), Path(revised["cwd"]))
    revised["config_pins"] = {str(p): hashlib.sha256(content.encode()).hexdigest() for p, content in configs.items()}
    revised["helper_sha256"] = hashlib.sha256(helper_text(revised).encode()).hexdigest()
    for path, content in configs.items():
        path.write_text(content)
    Path(revised["helper"]).write_text(helper_text(revised))
    Path(revised["binding"]).write_text(canonical(revised))
    return validate(revised)


def native_launch(binding, argv, env):
    """Compile a protected launch from trusted launcher-owned argv, never user overlays."""
    validate(binding)
    if not binding["executable"] or str(Path(argv[0]).resolve()) != binding["executable"]:
        raise ValueError("launch executable was not pinned")
    harness = binding["harness"]
    # This function is called after normal launcher construction. These flags
    # are reserved transport, not an arbitrary forwarded-argv interface.
    tokens = list(argv[1:])
    if harness == "claude":
        for index in range(len(tokens) - 1, -1, -1):
            if tokens[index:index + 2] == ["--setting-sources", "project,local"]:
                del tokens[index:index + 2]
    denied = ("--settings", "--setting-sources", "--bare", "--safe-mode", "--agent", "--plugin-dir", "--dangerously-bypass-hook-trust", "--enable", "--disable")
    if any(t.split("=", 1)[0] in denied for t in tokens):
        raise ValueError("native argv changes the guarded profile")
    for value in tokens:
        if value.startswith(("--config=", "-cfeatures", "-chooks", "-cshell_environment_policy")):
            raise ValueError("joined native config override is not admitted")
    for index, value in enumerate(tokens):
        if value in {"-c", "--config"} and index + 1 < len(tokens):
            key = tokens[index + 1].split("=", 1)[0]
            if key.startswith(("hooks", "features.", "shell_environment_policy")):
                raise ValueError("native argv changes hook/continuation coverage")
    if binding["authority_environment"]["HOME"] != str(Path.home()):
        raise ValueError("authority HOME differs from the trusted launcher")
    out = dict(env)
    for key in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "GROK_SESSION_ID"):
        out.pop(key, None)
    if binding["mode"] == "worker":
        out["CLAUDE_SESSION_ID"] = binding["session"]
    for key in ("CLAUDE_CODE_SIMPLE", "CLAUDE_CODE_SAFE_MODE", "BOUNDARIES_PATH", "PYTHONPATH", "PYTHONSTARTUP"):
        out.pop(key, None)
    if harness == "claude":
        tokens = ["--setting-sources", "", "--settings", str(Path(binding["helper"]).parent / "settings.json"), *tokens]
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
                 str(Path(binding["source"]) / "ops/lane.conf"), binding["helper"], binding["binding"], *binding["config_pins"]}
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
    native_id = native_payload.get("conversationId") if binding["harness"] == "agy" else native_payload.get("session_id", native_payload.get("sessionId"))
    session = binding["session"] if binding["mode"] == "worker" else native_id
    if not isinstance(session, str) or not session.strip() or len(session) > 128:
        raise ValueError("native/issued session identity unavailable")
    os.environ.pop("AGENTSCIENT_HOOK_PROFILE", None)
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
        if participant["endpoint"] not in (None, endpoint):
            raise ValueError("native session already has a different endpoint")
        if participant["endpoint"] is None:
            with core.writer() as conn:
                core.core_bind(conn, participant, agent=instrument.identity(), roles=participant["roles"], harness=binding["harness"],
                               endpoint=endpoint, probe="native shared-hook interactive registration")
    return session


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare-interactive", "run-interactive", "check"))
    parser.add_argument("--binding")
    parser.add_argument("--harness", choices=HARNESSES)
    parser.add_argument("--destination")
    parser.add_argument("--cwd")
    parser.add_argument("--executable")
    parser.add_argument("--agent")
    parser.add_argument("native_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if args.operation == "run-interactive":
            binding = read_binding(args.binding)
            if binding.get("mode") != "interactive":
                raise ValueError("interactive launch requires an interactive projection")
            native_args = args.native_args[1:] if args.native_args[:1] == ["--"] else args.native_args
            command, env = native_launch(binding, [binding["executable"], *native_args], os.environ)
            os.execve(command[0], command, env)  # noqa: S606 - validated executable and token vector
        elif args.operation == "check":
            validate(read_binding(args.binding))
            print("shared hook profile: valid projection; native interception requires its measured witness")
        else:
            if not all((args.harness, args.destination, args.cwd, args.executable, args.agent)):
                raise ValueError("interactive preparation requires harness, destination, cwd, executable and agent")
            binding = generate(args.harness, args.destination, source=Path(__file__).resolve().parents[3],
                               cwd=args.cwd, mode="interactive", agent=args.agent, executable=args.executable)
            print(binding["binding"])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"hook-profile: expected a complete pinned native projection; found {exc}; needed inspect co_doc.py and regenerate the reviewed profile", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
