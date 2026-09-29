"""Operator entry to a native, user-facing CO terminal with shared context."""

import codecs
import errno
import fcntl
import os
import pty
import select
import shutil
import signal
import sys
import termios
import time
import tty
import uuid

from .api import API, SERVER, TOOLS
from .compat import ClaudeChannelLog
from .launch import team_config
from .profiles import prepare, retain_login, toml
from .runtime import resolve
from .store import Store
from .telemetry import Trace, Transcript, context, requested


def command(directory, member, config, private, server):
    """Build native CLI arguments without accepting arbitrary command fragments."""
    instructions = API(directory, member).instructions()
    prompt = (
        "Call onboard; it supplies the shared and role instructions. Read only relevant skills not marked loaded. "
        "Recover current work and reports before asking the user what is next."
    )
    harness = config["harness"]
    argv, native_id = [config["binary"]], None
    if harness == "codex":
        options = {
            "mcp_servers": {SERVER: server},
            "developer_instructions": instructions,
            "sandbox_mode": "read-only",
            "approval_policy": "on-request",
        }
        for source, target in (
            ("model", "model"),
            ("reasoning", "model_reasoning_effort"),
            ("provider", "model_provider"),
        ):
            if config.get(source):
                options[target] = config[source]
        for key, value in options.items():
            argv += ["-c", key + "=" + toml(value)]
        argv += ["--", prompt]
    elif harness == "claude":
        native_id = str(uuid.uuid4())
        debug = private / "native-debug.log"
        debug.write_text("")
        debug.chmod(0o600)
        argv += [
            "--session-id",
            native_id,
            "--setting-sources",
            "",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--mcp-config",
            str(private / "mcp.json"),
            "--settings",
            str(private / "settings.json"),
            "--debug-file",
            str(debug),
            "--dangerously-load-development-channels",
            "server:" + SERVER,
            "--tools",
            "",
            "--allowedTools",
            ",".join("mcp__" + SERVER + "__" + row["name"] for row in TOOLS),
            "--append-system-prompt",
            instructions,
        ]
        for source, flag in (("model", "--model"), ("reasoning", "--effort")):
            if config.get(source):
                argv += [flag, config[source]]
        argv += ["--", prompt]
    else:
        native_id = str(uuid.uuid4())
        # Isolated HOME and cwd prevent project/user MCP and plugin discovery.
        compatibility = {
            name: {key: False for key in ("skills", "rules", "agents", "mcps", "hooks")}
            for name in ("claude", "cursor")
        }
        settings = {"mcp_servers": {SERVER: server}, "compat": compatibility}
        path = private / "config.toml"
        path.write_text("\n".join(key + " = " + toml(value) for key, value in settings.items()) + "\n")
        path.chmod(0o600)
        argv += [
            "--session-id",
            native_id,
            "--tools",
            "search_tool,use_tool",
            "--no-subagents",
            "--no-memory",
            "--disable-web-search",
            "--rules",
            instructions + "\n" + prompt,
        ]
        for source, flag in (("model", "--model"), ("reasoning", "--effort")):
            if config.get(source):
                argv += [flag, config[source]]
    return argv, native_id


def relay(argv, env, cwd, trace, poll):
    """Transparent PTY relay; capture output, never raw password/key input."""
    input_fd, output_fd = sys.stdin.fileno(), sys.stdout.fileno()
    original = termios.tcgetattr(input_fd) if os.isatty(input_fd) else None
    old_handlers = {}
    pid, master = pty.fork()
    if pid == 0:
        try:
            os.chdir(cwd)
            os.execvpe(argv[0], argv, env)
        except Exception as error:
            print(str(error), file=sys.stderr, flush=True)
            os._exit(127)

    def resize(*_):
        if original:
            size = fcntl.ioctl(input_fd, termios.TIOCGWINSZ, bytes(8))
            fcntl.ioctl(master, termios.TIOCSWINSZ, size)

    def terminate(*_):
        nonlocal stop_at
        if stop_at is None:
            stop_at = time.monotonic()
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    def write_all(fd, data):
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]

    # Keep incomplete lines together so ordinary credentials split across reads
    # are still filtered by Trace.clean. Very large output is bounded.
    decoder, pending = codecs.getincrementaldecoder("utf-8")("replace"), ""
    stop_at, status, input_open = None, None, True
    trace.record("process_started", {"argv": argv, "pid": pid, "transport": "interactive/pty"})
    try:
        for sig, handler in ((signal.SIGWINCH, resize), (signal.SIGTERM, terminate), (signal.SIGHUP, terminate)):
            old_handlers[sig] = signal.signal(sig, handler)
        resize()
        if original:
            tty.setraw(input_fd)
        while True:
            if not poll():
                terminate()
            if stop_at is not None and time.monotonic() - stop_at > 5:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            readable, _, _ = select.select([master, *([input_fd] if input_open else [])], [], [], 0.1)
            if input_fd in readable:
                data = os.read(input_fd, 65536)
                if data:
                    write_all(master, data)
                else:
                    input_open = False
            if master in readable:
                try:
                    data = os.read(master, 65536)
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    data = b""
                if not data:
                    break
                write_all(output_fd, data)
                pending += decoder.decode(data)
                while "\n" in pending or len(pending) > 65536:
                    end = pending.index("\n") + 1 if "\n" in pending else 65536
                    trace.record("terminal_output", {"text": pending[:end]})
                    pending = pending[end:]
            waited, value = os.waitpid(pid, os.WNOHANG)
            if waited:
                status = value
                # Drain any final PTY output before returning.
                input_open = False
                while select.select([master], [], [], 0)[0]:
                    try:
                        data = os.read(master, 65536)
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        break
                    if not data:
                        break
                    pending += decoder.decode(data)
                    write_all(output_fd, data)
                break
    finally:
        terminate()
        if status is None:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                waited, value = os.waitpid(pid, os.WNOHANG)
                if waited:
                    status = value
                    break
                time.sleep(0.02)
            if status is None:
                os.killpg(pid, signal.SIGKILL)
                _, status = os.waitpid(pid, 0)
        # Native subprocesses belong to this session even if the TUI exits first.
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        pending += decoder.decode(b"", final=True)
        if pending:
            trace.record("terminal_output", {"text": pending})
        os.close(master)
        if original:
            termios.tcsetattr(input_fd, termios.TCSADRAIN, original)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    return os.waitstatus_to_exitcode(status)


def run(directory, profile=None, model=None, reasoning=None):
    store = Store(directory)
    team = team_config(store.directory)
    member = team.get("co")
    if not member or not team.get("runtime"):
        raise ValueError("The CO launcher requires an appointed external CO and shared runtime policy (--runtime).")
    config = resolve(store.directory, "co", profile=profile)
    for key, value in (("model", model), ("reasoning", reasoning)):
        if value is not None:
            if not value or "\0" in value:
                raise ValueError(key + " must be nonempty text")
            config[key] = value
    config["binary"] = shutil.which(config["binary"])
    generation = store.begin_session(member, os.getpid(), settings=config)
    trace = Trace(directory, member, component="co-console", context=lambda: context(store, member))
    error, exit_code = None, None
    try:
        private, env, server = prepare(directory, member, config["harness"])
        workspace = private / "console"
        workspace.mkdir(mode=0o700, exist_ok=True)
        argv, native_id = command(directory, member, config, private, server)
        store.session(
            member,
            generation=generation,
            native_id=native_id,
            detail={"transport": "interactive/pty", "harness": config["harness"]},
        )
        store.event(
            member,
            "runtime_selected",
            **config["selection"],
            settings={key: config.get(key) for key in ("harness", "vendor", "model", "reasoning", "provider")},
        )
        requested(store, member, config, private)
        transcript = Transcript(store, member, trace)
        channel = ClaudeChannelLog(private / "native-debug.log") if config["harness"] == "claude" else None
        ready = False

        def poll():
            nonlocal ready
            current = store.member(member)
            if current["generation"] != generation or current["desired"] != "running":
                return False
            if not ready and (not channel or (observation := channel.poll())):
                ready = True
                store.session(member, generation=generation, state="idle")
                if channel:
                    store.event(member, "channel_ready", native_id=native_id, **observation)
            transcript.poll()
            return True

        exit_code = relay(argv, env, workspace, trace, poll)
        transcript.poll()
        if exit_code and store.member(member)["desired"] == "running":
            error = f"Native CO exited with status {exit_code}"
    except Exception as exc:
        error = str(exc)[:1000]
        raise
    finally:
        try:
            retain_login(directory, member, config["harness"], generation)
        except (OSError, ValueError):
            store.event(member, "login_cache_failed", harness=config["harness"])
        store.session(
            member,
            generation=generation,
            state="failed" if error else "stopped",
            desired="stopped",
            pid=None,
            detail={"error": error, "exit_code": exit_code, "harness": config["harness"]},
        )
        trace.record("console_closed", {"exit_code": exit_code, "error": error})
        trace.close()
    return (exit_code or 0) if error else 0
