"""Owned tmux sessions. No arbitrary terminal commands are exposed to agents."""

import hashlib
import shlex
import shutil
import subprocess
from pathlib import Path

from .store import identifier
from .telemetry import clean


def address(directory, member):
    digest = hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest()[:16]
    return "agentscient-" + digest, "agent-" + identifier(member)


def command(directory, *args, check=True):
    binary = shutil.which("tmux")
    if not binary:
        raise ValueError("Install tmux in WSL2/Linux before launching managed Claude, Codex or Grok sessions.")
    server, _ = address(directory, "server")
    result = subprocess.run(
        [binary, "-L", server, "-f", "/dev/null", *args], capture_output=True, text=True, timeout=10
    )
    if check and result.returncode:
        raise RuntimeError("tmux: " + clean(result.stderr.strip())[:1000])
    return result


def describe(directory, member):
    server, session = address(directory, member)
    return {
        "server": server,
        "terminal": session,
        "attach": shlex.join(["tmux", "-L", server, "attach-session", "-t", "=" + session]),
    }


def start(store, member, argv, workspace):
    detail = describe(store.directory, member)
    target = "=" + detail["terminal"]
    if command(store.directory, "has-session", "-t", target, check=False).returncode == 0:
        raise ValueError("This member already has an owned terminal; inspect it before restarting.")
    command(
        store.directory,
        "new-session",
        "-d",
        "-s",
        detail["terminal"],
        "-c",
        workspace,
        "--",
        "exec " + shlex.join(argv),
    )
    store.event(member, "terminal_created", **detail)
    return detail


def status(store, member):
    store.member(member)
    detail = describe(store.directory, member)
    exists = command(store.directory, "has-session", "-t", "=" + detail["terminal"], check=False).returncode == 0
    return {**detail, "exists": exists}


def read(store, member, lines=80):
    store.member(member)
    if type(lines) is not int or not 1 <= lines <= 500:
        raise ValueError("Read between 1 and 500 terminal lines")
    _, session = address(store.directory, member)
    result = command(store.directory, "capture-pane", "-p", "-t", "=" + session, "-S", str(-lines))
    return {"member": member, "text": clean(result.stdout), "source": "tmux/pane", "lines": lines}
