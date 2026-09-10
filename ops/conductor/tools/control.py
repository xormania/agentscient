#!/usr/bin/env python3
"""Execute frozen, one-use actions under conductor-control.md."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import os
import re
import selectors
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
HOOK = HERE.parents[2] / "devlane/hooks/conductor-control.py"
LIMIT = 8 * 1024 * 1024
KINDS = {"tests", "fixture", "red", "test-review", "code", "green", "review", "check"}
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
HEX = re.compile(r"[a-f0-9]{64}")
WORKER_CONTEXT = ("HOME", "CODEX_HOME", "CLAUDE_CONFIG_DIR", "GROK_HOME",
                  "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")


class Refusal(Exception):
    def __init__(self, kind, expected, found, needed):
        def clean(value):
            return " ".join(str(value).split()) or "empty"
        super().__init__(f"{kind}: expected {clean(expected)}; found {clean(found)}; needed {clean(needed)}")


def need(condition, kind, expected, found, needed):
    if not condition:
        raise Refusal(kind, expected, found, needed)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, "plan", "unique keys", key, "remove the duplicate")
        result[key] = value
    return result


def decode(data):
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_size <= LIMIT, "binding",
             "a bounded regular file", path, "restore the declared file")
        data = stream.read(LIMIT + 1)
    need(len(data) <= LIMIT, "binding", "bounded file", path, "restore the declared file")
    return data


def atomic(path, value):
    fd, temporary = tempfile.mkstemp(prefix=".control-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def git(repo, *args):
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
    for key in tuple(env):
        if key.startswith("GIT_") and key not in {"GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL"}:
            env.pop(key)
    executable = shutil.which("git")
    need(executable is not None, "binding", "Git executable", "unavailable", "restore the host Git installation")
    result = subprocess.run([executable, "--no-optional-locks", "-C", str(repo), *args],  # noqa: S603 -- internal read-only argv, no shell
                            capture_output=True, timeout=5, env=env, check=False)
    need(result.returncode == 0, "binding", "the declared Git worktree", "Git lookup failed",
         "restore the bound worktree and branch")
    return result.stdout.decode().strip()


def relative(value):
    return (isinstance(value, str) and bool(value) and "\x00" not in value
            and not Path(value).is_absolute() and "\\" not in value
            and all(part not in {"", ".", ".."} for part in value.split("/")))


def timestamp(value):
    need(isinstance(value, str), "plan", "UTC expiry", value, "supply a UTC timestamp")
    parsed = datetime.fromisoformat(value)
    need(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0,
         "plan", "UTC expiry", value, "supply a UTC timestamp")
    return parsed.timestamp()


def validate(plan):
    keys = {"version", "repo", "branch", "scope", "scope_sha256", "expires_at", "max_seconds", "actions"}
    need(isinstance(plan, dict) and set(plan) == keys and type(plan["version"]) is int
         and plan["version"] == 1, "plan", "closed version-1 plan", "wrong shape", "use the declared plan")
    need(isinstance(plan["repo"], str) and Path(plan["repo"]).is_absolute()
         and Path(plan["repo"]).is_dir(), "plan", "absolute worktree", plan["repo"], "name the worktree")
    need(isinstance(plan["branch"], str) and bool(plan["branch"]), "plan", "named branch",
         plan["branch"], "name the bound branch")
    need(relative(plan["scope"]) and isinstance(plan["scope_sha256"], str)
         and HEX.fullmatch(plan["scope_sha256"]), "plan", "scope path and SHA-256", "invalid scope",
         "bind the immutable task declaration")
    timestamp(plan["expires_at"])
    need(type(plan["max_seconds"]) is int and plan["max_seconds"] > 0, "plan",
         "positive time limit", plan["max_seconds"], "set the finite budget")
    need(isinstance(plan["actions"], list) and bool(plan["actions"]), "plan",
         "nonempty action array", "missing actions", "declare exact actions")
    preceding = set()
    for action in plan["actions"]:
        need(isinstance(action, dict) and set(action) == {"id", "kind", "argv", "timeout", "requires", "tests", "producer"},
             "plan", "closed action object", "wrong shape", "declare every action field")
        ident = action["id"]
        need(isinstance(ident, str) and TOKEN.fullmatch(ident) and ident not in preceding,
             "plan", "unique safe action ID", ident, "use a unique ID")
        need(isinstance(action["kind"], str) and action["kind"] in KINDS, "plan",
             "declared action kind", action["kind"], "use a declared kind")
        need(isinstance(action["argv"], list) and bool(action["argv"])
             and all(isinstance(x, str) and x and "\x00" not in x for x in action["argv"]),
             "plan", "nonempty literal argv", ident, "freeze the command arguments")
        need(type(action["timeout"]) is int and 0 < action["timeout"] <= plan["max_seconds"],
             "plan", "timeout within cumulative budget", ident, "bound the action timeout")
        for field in ("requires", "tests"):
            values = action[field]
            need(isinstance(values, list) and all(isinstance(x, str) for x in values)
                 and len(set(values)) == len(values), "plan", f"unique {field} array", ident, "fix the declaration")
        need(set(action["requires"]) <= preceding, "plan", "preceding prerequisites", ident, "order the actions")
        need(all(relative(x) for x in action["tests"]), "plan", "normalized test file paths", ident,
             "enumerate test files, helpers and fixtures")
        need(isinstance(action["producer"], str) and bool(action["producer"].strip()),
             "plan", "specific producer identity", ident, "name the harness and model")
        if action["kind"] in {"red", "green"}:
            need(action["argv"][:2] == ["unittest", "discover"], "plan",
                 "unittest discover argv", ident, "use the controller unittest runner")
        preceding.add(ident)
    return plan


def files(repo, paths):
    root = Path(repo).resolve()
    result = []
    for name in sorted(paths):
        path = root / name
        need(relative(name) and path.resolve().is_relative_to(root)
             and not any(p.is_symlink() for p in (path, *path.parents) if p != root and p.is_relative_to(root)),
             "binding", "regular in-worktree test file", name, "restore the sealed test files")
        git(root, "ls-files", "--error-unmatch", "--", name)
        result.append({"path": name, "sha256": sha(read(path))})
    return result, sha(canonical(result))


def bindings(state, directory):
    raw = read(directory / "plan.json")
    need(sha(raw) == state["plan_sha256"], "binding", "unchanged plan bytes", "plan changed", "restore the owner plan")
    plan = validate(decode(raw))
    need(plan == state["plan"], "binding", "frozen plan", "state mismatch", "restore the control state")
    repo = Path(plan["repo"]).resolve()
    need(git(repo, "rev-parse", "--show-toplevel") == str(repo)
         and git(repo, "branch", "--show-current") == plan["branch"],
         "binding", "declared worktree and branch", "binding changed", "restore the owner worktree")
    scope = repo / plan["scope"]
    need(scope.resolve().is_relative_to(repo) and sha(read(scope)) == plan["scope_sha256"],
         "binding", "unchanged task declaration", "scope changed", "restore the owner scope")
    for path in (HERE, HOOK):
        need(sha(read(path)) == state["instruments"][str(path)], "binding", "unchanged control and hook",
             path, "use the owner-pinned instruments")
    return plan


def load(directory, verify=True):
    need(directory.is_dir() and not directory.is_symlink(), "control", "existing control directory",
         directory, "initialize an owner plan outside the conductor")
    state = decode(read(directory / "state.json"))
    if verify:
        bindings(state, directory)
    return state


@contextmanager
def locked(directory):
    fd = os.open(directory / "lock", os.O_RDWR | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refusal("control", "exclusive action reservation", "another action is active", "wait for its outcome") from None
        yield
    finally:
        os.close(fd)


def remaining(state):
    plan = state["plan"]
    return min(plan["max_seconds"] - state["cumulative_time"], timestamp(plan["expires_at"]) - time.time())


def prerequisites(state, action):
    by_id = {x["id"]: x for x in state["plan"]["actions"]}
    result = {}
    pending = list(action["requires"])
    while pending:
        ident = pending.pop()
        if ident in result:
            continue
        record = state["actions_state"].get(ident, {})
        need(record.get("status") == "completed", "admission", "successful prerequisites", ident,
             "complete the declared prerequisite path")
        result[ident] = by_id[ident]
        pending.extend(by_id[ident]["requires"])
    return result


def admission(state, action):
    prior = prerequisites(state, action)
    selected = {kind: [x for x in prior.values() if x["kind"] == kind
                      and sorted(x["tests"]) == sorted(action["tests"])] for kind in KINDS}
    kind = action["kind"]
    if action["tests"] and kind != "tests":
        need(bool(selected["tests"]), "admission", "successful producer of this test set", "none",
             "produce and seal the declared tests first")
        rows, digest = files(state["plan"]["repo"], action["tests"])
        need(all(state["actions_state"][a["id"]].get("tests_sha256") == digest for a in selected["tests"]),
             "binding", "sealed test bytes", "tests changed", "start a new independent cycle")
    else:
        rows, digest = [], None
    required = {"fixture", "red", "tests"} if kind == "test-review" else {"fixture", "red", "tests", "test-review"}
    if kind in {"test-review", "code", "green"}:
        need(bool(action["tests"]) and all(selected[x] for x in required), "admission",
             "tests, fixture, valid RED and independent acceptance", "missing evidence", "complete the frozen TDD path")
        authors = {a["producer"].strip().casefold() for a in selected["tests"]}
        reviewers = {a["producer"].strip().casefold() for a in selected["test-review"]}
        current = action["producer"].strip().casefold()
        need(not authors & reviewers and (kind != "test-review" or current not in authors)
             and (kind != "code" or current not in authors | reviewers), "admission",
             "independent author, test reviewer and coder", "producer overlap", "use distinct declared producers")
        for choices in selected.values():
            for previous in choices:
                need(state["actions_state"][previous["id"]].get("tests_sha256") == digest,
                     "binding", "the same tested bytes throughout TDD", previous["id"], "restore the sealed test set")
    if kind == "green":
        need(any(a["argv"] == action["argv"] for a in selected["red"]), "admission",
             "the same discovery command as RED", action["id"], "freeze identical discovery arguments")
    return rows, digest, selected


def process_identity(pid):
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
        return text[text.rfind(")") + 2:].split()[19]
    except (OSError, IndexError):
        return None


def signal_owned(record, sig):
    pid = record.get("pid")
    if (isinstance(pid, int) and record.get("process_start") is not None
            and process_identity(pid) == record["process_start"]):
        try:
            if os.getpgid(pid) == pid:
                os.killpg(pid, sig)
        except ProcessLookupError:
            pass


def supervise(argv, repo, directory, record, duration, save, child_env=None):
    outputs = {"stdout": bytearray(), "stderr": bytearray()}
    interrupted = []
    old = {sig: signal.signal(sig, lambda signum, _frame: interrupted.append(signum))
           for sig in (signal.SIGTERM, signal.SIGINT)}
    started = time.monotonic()
    process = None
    reason = None
    try:
        env = dict(os.environ if child_env is None else child_env,
                   CONTROL_STATE=str(directory), PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.Popen(argv, cwd=repo, env=env, stdin=subprocess.DEVNULL,  # noqa: S603 -- literal argv frozen by the owner
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        record.update(pid=process.pid, process_start=process_identity(process.pid))
        save()
        with selectors.DefaultSelector() as selector:
            for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            exited_at = None
            while True:
                elapsed = time.monotonic() - started
                if interrupted or elapsed >= duration:
                    reason = "interrupted" if interrupted else "deadline"
                    break
                exited = process.poll() is not None
                if exited and exited_at is None:
                    exited_at = time.monotonic()
                    # The group was created by this invocation; remove descendants
                    # even if its leader exited while they retained output pipes.
                    with suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGTERM)
                if exited and (not selector.get_map() or time.monotonic() - exited_at >= .25):
                    break
                for key, _ in selector.select(min(.05, max(0, duration - elapsed))):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    available = LIMIT - sum(len(value) for value in outputs.values())
                    outputs[key.data].extend(chunk[:available])
                    if len(chunk) > available:
                        reason = "output limit"
                        break
                if reason:
                    break
        if reason:
            signal_owned(record, signal.SIGTERM)
        try:
            process.wait(timeout=.5)
        except subprocess.TimeoutExpired:
            signal_owned(record, signal.SIGKILL)
            process.wait(timeout=2)
        # No member of this freshly owned group is permitted to outlive its action.
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        return process.returncode, reason, time.monotonic() - started, outputs
    except OSError as error:
        outputs["stderr"].extend(f"spawn failed: {type(error).__name__}\n".encode())
        return 127, None, time.monotonic() - started, outputs
    finally:
        if process is not None:
            if process.poll() is None:
                signal_owned(record, signal.SIGKILL)
                process.wait(timeout=2)
            for stream in (process.stdout, process.stderr):
                stream.close()
        for sig, handler in old.items():
            signal.signal(sig, handler)


def logs(directory, name, record, outputs):
    for channel, data in outputs.items():
        path = directory / f"{name}.{channel}"
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        record[f"{channel}_path"] = str(path)
        record[f"{channel}_sha256"] = sha(data)


def initialize(path, directory, caller):
    raw = read(path)
    plan = validate(decode(raw))
    repo = Path(plan["repo"]).resolve()
    need(not directory.is_relative_to(repo), "control", "state outside worker worktree", directory,
         "use a private external state directory")
    state = {"plan": plan, "plan_sha256": sha(raw), "actions_state": {}, "cumulative_time": 0,
             "initialized_by": caller, "instruments": {str(p): sha(read(p)) for p in (HERE, HOOK)},
             "worker_context": {key: os.environ.get(key) for key in WORKER_CONTEXT}}
    need(timestamp(plan["expires_at"]) > time.time(), "plan", "unexpired plan", "expired",
         "issue a new bounded plan")
    need(not directory.exists(), "control", "new control directory", directory, "use the existing status or a new owner plan")
    # Validate bindings before creating any state.
    need(git(repo, "rev-parse", "--show-toplevel") == str(repo)
         and git(repo, "branch", "--show-current") == plan["branch"],
         "binding", "declared worktree and branch", "mismatch", "correct the owner plan")
    scope = repo / plan["scope"]
    need(scope.resolve().is_relative_to(repo) and sha(read(scope)) == plan["scope_sha256"],
         "binding", "matching scope hash", "scope mismatch", "freeze the task declaration")
    directory.mkdir(mode=0o700, parents=False)
    with (directory / "plan.json").open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    (directory / "lock").touch(mode=0o600, exist_ok=False)
    atomic(directory / "state.json", state)
    return 0


def runnable(state, ident):
    action = next((a for a in state["plan"]["actions"] if a["id"] == ident), None)
    need(action is not None, "control", "declared action ID", ident, "choose an owner-declared action")
    need(ident not in state["actions_state"], "control", "unused action", ident,
         "read the durable result; retries require a new owner plan")
    need(state.get("seat", {}).get("status", "running") == "running", "control",
         "active conductor seat", "seat already ended", "read status outside the conductor")
    need(remaining(state) > 0, "control", "remaining time and lifetime", "exhausted",
         "stop and return the retained outcome")
    admission(state, action)
    return action


def execute(directory, ident, caller):
    with locked(directory):
        state = load(directory)
        action = runnable(state, ident)
        need(not any(row.get("status") == "running" for row in state["actions_state"].values()),
             "control", "no unfinished action reservation", "an action is running", "inspect the retained action before starting another")
        rows, digest, selected = admission(state, action)
        record = {"status": "running", "exit_code": None, "by": caller, "tests": rows,
                  "tests_sha256": digest, "started_at": datetime.now(timezone.utc).isoformat(),
                  "stdout_path": None, "stdout_sha256": None, "stderr_path": None, "stderr_sha256": None}
        state["actions_state"][ident] = record
        atomic(directory / "state.json", state)  # Durable reservation precedes spawning.

    def save():
        with locked(directory):
            current = load(directory, verify=False)
            current["actions_state"][ident] = record
            current["cumulative_time"] = state["cumulative_time"]
            atomic(directory / "state.json", current)
    argv = action["argv"]
    if action["kind"] in {"red", "green"}:
        argv = [sys.executable, "-B", str(HERE), "_unittest", *argv[2:]]
    # Native conductor homes must never become worker configuration or job stores.
    # Restore the initialization context before the normal dispatch isolation runs.
    child_env = dict(os.environ)
    for key in WORKER_CONTEXT:
        value = state["worker_context"][key]
        if value is None:
            child_env.pop(key, None)
        else:
            child_env[key] = value
    code, reason, elapsed, output = supervise(argv, state["plan"]["repo"], directory, record,
                                            min(action["timeout"], remaining(state)), save, child_env)
    state["cumulative_time"] += elapsed
    logs(directory, ident, record, output)
    record.update(exit_code=code, elapsed_seconds=elapsed)
    success = code == 0 and reason is None
    try:
        bindings(state, directory)
        if action["tests"]:
            actual, actual_digest = files(state["plan"]["repo"], action["tests"])
            if action["kind"] != "tests":
                need(actual_digest == digest, "binding", "unchanged tests after action", ident,
                     "retain the aborted result and start an independent cycle")
            record.update(tests=actual, tests_sha256=actual_digest)
    except (Refusal, OSError, ValueError) as error:
        reason = f"binding changed: {error}"
    if action["kind"] in {"red", "green"} and reason is None:
        try:
            result = decode(output["stdout"])
            counts = ("testsRun", "failures", "errors", "unexpectedSuccesses", "skipped")
            valid = all(type(result.get(x)) is int and result[x] >= 0 for x in counts)
            valid = valid and result["testsRun"] > 0 and result["errors"] == result["unexpectedSuccesses"] == result["skipped"] == 0
            success = valid and ((code == 1 and result["failures"] > 0) if action["kind"] == "red"
                                 else (code == 0 and result["failures"] == 0))
        except (ValueError, TypeError, KeyError, AttributeError, Refusal):
            success = False
    if action["kind"] == "test-review" and success:
        try:
            verdict = decode(output["stdout"])
            success = (isinstance(verdict, dict) and set(verdict) == {"verdict", "tests_sha256", "red_sha256"}
                       and verdict["verdict"] == "approve" and verdict["tests_sha256"] == digest
                       and any(verdict["red_sha256"] == state["actions_state"][a["id"]]["stdout_sha256"]
                               for a in selected["red"]))
        except (ValueError, TypeError, Refusal):
            success = False
    record["status"] = "aborted" if reason else ("completed" if success else "failed")
    record["reason"] = reason
    save()
    return 3 if reason else (0 if success else 1)


def toml_value(value):
    if isinstance(value, dict):
        return "{" + ", ".join(json.dumps(key) + " = " + toml_value(item) for key, item in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    need(type(value) in (str, bool, int, float), "control", "provider configuration values",
         type(value).__name__, "use native provider strings, numbers and tables")
    return json.dumps(value)


def native_command(directory, host, model, prompt):
    """Owner-only launch wiring; each host gets a fresh home and mandatory gate."""
    state = load(directory)
    need("seat" not in state and remaining(state) > 0, "control", "unused seat and remaining time",
         "seat used or exhausted", "read the retained outcome")
    executable = shutil.which(host)
    need(executable is not None, "control", "installed native host", host, "install the verified host")
    need(bool(model) and prompt is not None, "control", "explicit model and prompt file",
         "missing launch input", "name the host model and owner prompt")
    message = read(prompt).decode()
    home = directory / "native-home"
    need(not home.exists(), "control", "fresh native home", "launch already prepared",
         "inspect the existing outcome; do not repeat a seat")
    home.mkdir(mode=0o700)
    env = dict(os.environ)
    variable = {"codex": "CODEX_HOME", "claude": "CLAUDE_CONFIG_DIR", "grok": "GROK_HOME"}[host]
    source = Path(env.get(variable) or str(Path.home() / f".{host}"))
    provider_config = ""
    if host in {"codex", "grok"} and (source / "config.toml").is_file():
        settings = tomllib.loads(read(source / "config.toml").decode())
        keys = ("model_provider", "model_providers") if host == "codex" else ("model",)
        provider_config = "".join(key + " = " + toml_value(settings[key]) + "\n" for key in keys if key in settings)
    credential = ".credentials.json" if host == "claude" else "auth.json"
    if (source / credential).is_file():
        (home / credential).symlink_to((source / credential).resolve())
    env[variable] = str(home)
    env["HOME"] = str(home)
    for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        env[key] = str(home / key.lower())
    command = shlex.join([sys.executable, str(HOOK), "--state", str(directory)])
    hooks = {"hooks": {"PreToolUse": [{"matcher": ".*", "hooks": [
        {"type": "command", "command": command, "timeout": 5}]}]}}
    if host == "codex":
        # Invocation-scoped hook trust is safe here only because this home is new
        # and the owner-selected repository contributes no additional Codex config.
        repo = Path(state["plan"]["repo"])
        need(not any((parent / ".codex" / name).exists() for parent in (repo, *repo.parents)
                     for name in ("config.toml", "hooks.json")),
             "control", "no extra project Codex configuration", "project config present",
             "review and remove the additional config from this conductor worktree")
        atomic(home / "hooks.json", hooks)
        (home / "config.toml").write_text(provider_config + "[features]\nhooks = true\ncode_mode = false\n")
        argv = [executable, "exec", "--ephemeral", "--dangerously-bypass-hook-trust",
                "--sandbox", "workspace-write", "--add-dir", str(directory),
                "--model", model, "--json", message]
    elif host == "claude":
        for key in ("CLAUDE_CODE_SIMPLE", "CLAUDE_CODE_SAFE_MODE"):
            env.pop(key, None)
        argv = [executable, "--print", "--model", model, "--setting-sources", "",
                "--strict-mcp-config", "--disable-slash-commands", "--settings", json.dumps(hooks),
                "--permission-mode", "dontAsk", "--allowedTools", "Bash,Read,Glob,Grep",
                "--output-format", "stream-json", "--verbose", message]
    else:
        (home / "hooks").mkdir()
        atomic(home / "hooks/control.json", hooks)
        (home / "config.toml").write_text(provider_config + "[cli]\nauto_update = false\n[features]\ntelemetry = false\n")
        argv = [executable, "--single", message, "--model", model, "--no-plan", "--no-subagents",
                "--always-approve", "--max-turns", "64", "--output-format", "streaming-json"]
    return argv, env


def seat(directory, argv, caller, child_env=None):
    need(bool(argv), "control", "conductor argv", "empty command", "supply the owner conductor command")
    with locked(directory):
        state = load(directory)
        need("seat" not in state and remaining(state) > 0, "control", "unused seat and remaining time",
             "seat used or budget exhausted", "read the retained outcome")
        record = {"status": "running", "by": caller, "exit_code": None}
        state["seat"] = record
        atomic(directory / "state.json", state)
        duration = min(state["plan"]["max_seconds"], timestamp(state["plan"]["expires_at"]) - time.time())

    def save_seat():
        with locked(directory):
            current = load(directory, verify=False)
            current["seat"] = record
            atomic(directory / "state.json", current)

    code, reason, elapsed, output = supervise(argv, state["plan"]["repo"], directory, record, duration, save_seat, child_env)
    # The seat owns the entire conductor lifetime, including separate action groups.
    current = load(directory, verify=False)
    active = [a for a in current["actions_state"].values() if a.get("status") == "running"]
    for entry in active:
        signal_owned(entry, signal.SIGTERM)
    if active:
        time.sleep(.25)
        for entry in active:
            signal_owned(entry, signal.SIGKILL)
    logs(directory, "seat", record, output)
    record.update(status="aborted" if reason else ("completed" if code == 0 else "failed"),
                  exit_code=code, reason=reason, elapsed_seconds=elapsed)
    deadline = time.monotonic() + 3
    while True:
        try:
            save_seat()
            break
        except Refusal:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.05)
    return 3 if reason else (0 if code == 0 else 1)


def unittest_result(arguments):
    stream = io.StringIO()
    # Program performs discovery itself. Tests cannot provide a replacement JSON receipt.
    program = unittest.TestProgram(module=None, argv=["unittest", "discover", *arguments],
                                   testRunner=unittest.TextTestRunner(stream=stream), exit=False)
    result = program.result
    print(json.dumps({"testsRun": result.testsRun, "failures": len(result.failures),
                      "errors": len(result.errors), "unexpectedSuccesses": len(result.unexpectedSuccesses),
                      "skipped": len(result.skipped),
                      "failed_tests": [{"id": test.id(), "traceback": trace} for test, trace in result.failures],
                      "errored_tests": [{"id": test.id(), "traceback": trace} for test, trace in result.errors],
                      "runner_output": stream.getvalue()}, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Refusal("control", "declared command arguments", message, "use control.py --help")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_unittest":
        return unittest_result(argv[1:])
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest="verb", required=True, parser_class=Parser)
    for verb in ("init", "run", "status", "seat"):
        child = commands.add_parser(verb)
        child.add_argument("--state", required=True, type=Path)
        if verb in {"init", "run"}:
            child.add_argument("target")
        if verb == "seat":
            child.add_argument("--host", choices=("codex", "claude", "grok"))
            child.add_argument("--model")
            child.add_argument("--prompt", type=Path)
    command = []
    if "--" in argv:
        index = argv.index("--")
        argv, command = argv[:index], argv[index + 1:]
    try:
        args = parser.parse_args(argv)
        need(not command or args.verb == "seat", "control", "seat-only trailing argv", args.verb,
             "use the declared command syntax")
        directory = args.state.absolute()
        if args.verb == "status":
            print(json.dumps(load(directory, verify=False), sort_keys=True))
            return 0
        caller = os.environ.get("WF_AGENT", "")
        need(re.fullmatch(r"[^<>\n]+ <[^<>\s]+@[^<>\s]+>", caller) is not None,
             "identity", "WF_AGENT Name <address>", "missing or malformed identity", "supply the invocation identity")
        if args.verb == "init":
            return initialize(Path(args.target), directory, caller)
        if args.verb == "run":
            return execute(directory, args.target, caller)
        if args.host:
            need(not command, "control", "native host options without raw argv", "mixed launch forms",
                 "use --host with --model and --prompt")
            command, child_env = native_command(directory, args.host, args.model, args.prompt)
            return seat(directory, command, caller, child_env)
        need(args.model is None and args.prompt is None, "control", "native host for model and prompt",
             "missing host", "supply --host or an explicit owner command")
        return seat(directory, command, caller)
    except Refusal as error:
        print(error, file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, subprocess.SubprocessError) as error:
        print(Refusal("control", "readable valid bound state", type(error).__name__,
                      "inspect the retained state and restore the declared inputs"), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
