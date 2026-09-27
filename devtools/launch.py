"""Start and stop configured persistent sessions. There is no job dispatcher."""

import asyncio
import fcntl
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

from .store import Store, identifier

HARNESSES = {"codex", "claude", "grok", "external"}


def initialize(directory, workspace, members, co=None, project=None):
    from .profiles import write_json

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
    if co is not None and not any(row["name"] == co and row["harness"] == "external" for row in rows):
        raise ValueError("CO must name the external user-facing session.")
    Store(directory).initialize(rows)
    write_json(config, {"members": rows, **({"co": co} if co else {}), **({"project": project} if project else {})})
    return {"state": str(directory), "members": rows}


def team_config(directory):
    config = json.loads((Path(directory) / "team.json").read_text())
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
    if config.get("co") and not any(row["name"] == config["co"] and row["harness"] == "external" for row in rows):
        raise ValueError("CO must name the external user-facing session.")
    return config


def configuration(directory, member):
    store = Store(directory)
    rows = team_config(store.directory)["members"]
    store.initialize(rows)
    selected = next((row for row in rows if row["name"] == member), None)
    if selected is None:
        raise ValueError("Member is not configured in team.json")
    if selected["harness"] == "external":
        raise ValueError("External members connect their own MCP client; there is no managed process to start.")
    from .control import Control

    scope = Control(store, member).snapshot()
    if not scope:
        raise ValueError(
            "Bind this member's role and work through the operator member_bind capability before starting it."
        )
    selected = dict(selected)
    from .workspaces import Workspaces, project_config

    if scope["job"] and project_config(store):
        selected["workspace"] = Workspaces(store, member).ensure()["root"]
    binary = shutil.which(selected.get("binary", selected["harness"]))
    if not binary:
        raise ValueError(f"Install/login to {selected['harness']} and set its binary in team.json")
    selected["binary"] = str(Path(binary).resolve())
    return selected


def tmux_name(directory, member):
    digest = hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest()[:10]
    return f"agentscient-{digest}-{identifier(member)}"


def start(directory, member, *, binding_revision=None):
    store = Store(directory)
    locks = store.directory / "launch-locks"
    locks.mkdir(exist_ok=True, mode=0o700)
    with (locks / (identifier(member) + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if binding_revision is not None:
            from .control import Control

            scope = Control(store, member).snapshot()
            if not scope or scope["revision"] != binding_revision or scope["paused"] or not scope["launch_pending"]:
                return {"superseded": True}
            current = store.member(member)
            if current["pid"] and current["desired"] == "stopped":
                try:
                    os.kill(current["pid"], 0)
                except ProcessLookupError:
                    pass
                else:
                    return {"waiting_for_stop": True}
        result = _start(directory, member, binding_revision)
        if binding_revision is not None and result.get("already_running"):
            with store.connect() as db:
                db.execute(
                    "UPDATE member_bindings SET launch_pending=0 WHERE member=? AND revision=?",
                    (member, binding_revision),
                )
        return result


def _start(directory, member, binding_revision):
    from .profiles import ENTRY

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
    if binding_revision is not None:
        argv += ["--binding-revision", str(binding_revision)]
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
    if binding_revision is not None and current["generation"] == previous_generation:
        raise RuntimeError("Managed process did not establish a session; inspect monitor and retry with resume.")
    if current["generation"] != previous_generation and current["state"] == "failed":
        raise RuntimeError(current["detail"].get("error", "Native startup failed"))
    return {"member": member, "requested": "running", **detail, "session": current}


def agent(directory, member, binding_revision=None):
    from .control import REQUEST_BINDING, Control

    store = Store(directory)
    config = configuration(directory, member)
    control = Control(store, member)
    origin = control.snapshot()
    generation = store.begin_session(
        member,
        os.getpid(),
        binding_revision=binding_revision,
        settings={key: config.get(key) for key in ("harness", "model", "reasoning")},
    )

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
        if error and origin:
            token = REQUEST_BINDING.set((member, origin))
            try:
                with store.work_context(member, origin["work_order"], origin["job"]):
                    control.report("Native session failed: " + error[:600], kind="blocker")
            except ValueError:
                pass  # A revoked or changed reporting relationship cannot receive this report.
            finally:
                REQUEST_BINDING.reset(token)
