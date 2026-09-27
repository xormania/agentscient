"""Start and stop configured persistent sessions. There is no job dispatcher."""

import asyncio
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .profiles import ENTRY, write_json
from .store import Store, identifier

HARNESSES = {"codex", "claude", "grok", "external"}


def initialize(directory, workspace, members):
    directory = Path(directory).expanduser().resolve()
    config = directory / "team.json"
    if config.exists():
        raise ValueError("Team already exists; edit its team.json to change configuration.")
    rows = []
    for item in members:
        name, harness = item.split(":", 1)
        identifier(name)
        if harness not in HARNESSES or name in {row["name"] for row in rows}:
            raise ValueError("Use unique names and codex, claude, grok or external harnesses.")
        rows.append(
            {
                "name": name,
                "harness": harness,
                "binary": harness,
                "workspace": str(Path(workspace).expanduser().resolve(strict=True)),
            }
        )
    if not rows:
        raise ValueError("Configure at least one member.")
    Store(directory).initialize(rows)
    write_json(config, {"members": rows})
    return {"state": str(directory), "members": rows}


def configuration(directory, member):
    store = Store(directory)
    config = json.loads((store.directory / "team.json").read_text())
    rows = config.get("members")
    if not isinstance(rows, list) or not rows:
        raise ValueError("team.json needs a nonempty members array")
    names = set()
    for row in rows:
        identifier(row["name"])
        if row["name"] in names or row["harness"] not in HARNESSES:
            raise ValueError("Invalid or duplicate team member")
        names.add(row["name"])
        if set(row) - {"name", "harness", "workspace", "binary", "model", "reasoning"}:
            raise ValueError("Unknown team member option")
        for key in ("binary", "model", "reasoning"):
            if key in row and (not isinstance(row[key], str) or not row[key] or "\0" in row[key]):
                raise ValueError(f"{key} must be a nonempty string")
    store.initialize(rows)
    selected = next((row for row in rows if row["name"] == member), None)
    if selected is None:
        raise ValueError("Member is not configured in team.json")
    if selected["harness"] == "external":
        raise ValueError("External members connect their own MCP client; there is no managed process to start.")
    from .control import Control

    if not Control(store, member).snapshot():
        raise ValueError(
            "Bind this member's role and work through the operator member_bind capability before starting it."
        )
    selected = dict(selected)
    binary = shutil.which(selected.get("binary", selected["harness"]))
    if not binary:
        raise ValueError(f"Install/login to {selected['harness']} and set its binary in team.json")
    selected["binary"] = str(Path(binary).resolve())
    return selected


def tmux_name(directory, member):
    digest = hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest()[:10]
    return f"agentscient-{digest}-{identifier(member)}"


def start(directory, member):
    store = Store(directory)
    config = configuration(directory, member)
    current = store.member(member)
    previous_generation = current["generation"]
    if current["state"] in {"starting", "idle", "active"} and current["pid"]:
        try:
            os.kill(current["pid"], 0)
        except ProcessLookupError:
            pass
        else:
            return {"member": member, "already_running": True, "session": current}
    argv = [sys.executable, str(ENTRY), "agent", "--state", str(store.directory), "--member", member]
    if config["harness"] == "claude":
        if not shutil.which("tmux"):
            raise ValueError(
                "Claude's native TUI needs tmux for background launch, or run the agent command in a terminal."
            )
        name = tmux_name(directory, member)
        subprocess.run(["tmux", "new-session", "-d", "-s", name, "--", shlex.join(argv)], check=True, timeout=10)
        detail = {"terminal": name, "attach": f"tmux attach -t {name}"}
    else:
        logs = store.directory / "logs"
        logs.mkdir(exist_ok=True, mode=0o700)
        path = logs / (identifier(member) + ".log")
        with path.open("a") as stream:
            path.chmod(0o600)
            process = subprocess.Popen(
                argv, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True
            )
        threading.Thread(target=process.wait, daemon=True).start()
        detail = {"pid": process.pid, "log": str(path)}
    store.event(member, "launch_requested", **detail)
    # Return observed startup, not a fabricated ready acknowledgement.
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        current = store.member(member)
        if current["generation"] != previous_generation:
            break
        time.sleep(0.05)
    current = store.member(member)
    if current["generation"] != previous_generation and current["state"] == "failed":
        raise RuntimeError(current["detail"].get("error", "Native startup failed"))
    return {"member": member, "requested": "running", **detail, "session": current}


def agent(directory, member):
    store = Store(directory)
    config = configuration(directory, member)
    generation = store.begin_session(member, os.getpid())

    def stop(_signal, _frame):
        store.session(member, generation=generation, desired="stopped")

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    error = None
    try:
        from .native import Native, claude

        if config["harness"] == "claude":
            claude(directory, member, config, generation)
        else:
            asyncio.run(Native(directory, member, config, generation).run())
    except Exception as exc:
        error = str(exc)[:1000]
        store.event(member, "session_failed", error=error)
        raise
    finally:
        store.session(
            member,
            generation=generation,
            state="failed" if error else "stopped",
            desired="stopped",
            pid=None,
            detail={"error": error},
        )
