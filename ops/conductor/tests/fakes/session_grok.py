# testkit: exempt fixture program planted as the grok ACP agent
"""Fake Grok ACP agent for sessions slice 2.

Planted through Tools.plant(..., script=...). The registry spec beside
this executable says which native id to answer (``native_id``; empty
means ``session-<pid>``), which method answers -32601 (``reject_method``),
and which request to die after (``die_after``, after the response).
One JSON line per request goes to the registry call log. Speaks
JSON-lines: ``initialize`` (protocolVersion 1) advertises authenticate,
``authenticate``, ``session/new`` → ``sessionId``; ``session/prompt`` and
``_x.ai/interject`` → a written result, then ``session/update`` and
``_x.ai/session/prompt_complete``. A session update names the
``coordination`` tool. The repository root is substituted once at plant.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO = "@@REPO@@"


def spec_path() -> Path | None:
    exe = Path(sys.argv[0]).resolve()
    own = exe.parent.parent / "fakes" / f"{exe.name}.spec.json"
    named = os.environ.get("TESTKIT_FAKE_SPEC", "")
    if named:
        path = Path(named)
        if path.is_file() and path.name.startswith(exe.name + "."):
            return path
    return own if own.is_file() else None


def load_spec() -> dict:
    path = spec_path()
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def log_request(raw: str, method: str, req_id, params, native: str) -> None:
    path = spec_path()
    if path is None:
        return
    log = path.with_name(path.name.replace(".spec.json", ".calls.jsonl"))
    line = json.dumps({
        "pid": os.getpid(),
        "method": method,
        "id": req_id,
        "params": params,
        "native_id": native,
        "raw": raw,
    }) + "\n"
    fd = os.open(str(log), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def result(req_id, value: dict) -> None:
    emit({"jsonrpc": "2.0", "id": req_id, "result": value})


def method_not_found(req_id) -> None:
    emit({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": "Method not found"},
    })


def texts(node) -> list[str]:
    found: list[str] = []
    if isinstance(node, str):
        found.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            found.extend(texts(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(texts(value))
    return found


def ancestor_pids() -> set[int]:
    found: set[int] = set()
    pid = os.getpid()
    for _ in range(8):
        status = Path(f"/proc/{pid}/status")
        if not status.is_file():
            break
        ppid = None
        for line in status.read_text(encoding="utf-8").splitlines():
            if line.startswith("PPid:"):
                ppid = int(line.split()[1])
                break
        if not ppid or ppid in found or ppid <= 1:
            break
        found.add(ppid)
        pid = ppid
    return found


def credentials() -> tuple[str, str] | None:
    spec = load_spec()
    session = spec.get("session")
    capability = spec.get("capability")
    if isinstance(session, str) and session and isinstance(capability, str) and capability:
        return session, capability
    root = Path(os.environ.get("XDG_STATE_HOME", ""))
    if not root.is_dir() or REPO.startswith("@@"):
        return None
    ancestors = ancestor_pids()
    matched = []
    only = []
    for launch_path in root.glob("*/sessions/*/*/launch.json"):
        try:
            launch = json.loads(launch_path.read_text(encoding="utf-8"))
            binding = json.loads(
                (launch_path.parent / "profile" / "binding.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue
        cap = binding.get("coordination_capability") if isinstance(binding, dict) else None
        launch_id = launch.get("launch_id") if isinstance(launch, dict) else None
        if not isinstance(cap, str) or not cap or not isinstance(launch_id, str) or not launch_id:
            continue
        pair = (launch_id, cap)
        only.append(pair)
        pid = launch.get("pid") if isinstance(launch, dict) else None
        if isinstance(pid, str) and pid.isdigit():
            pid = int(pid)
        if isinstance(pid, int) and pid in ancestors:
            matched.append(pair)
    if len(matched) == 1:
        return matched[0]
    if len(only) == 1:
        return only[0]
    return None


def core(*argv: str) -> None:
    creds = credentials()
    if creds is None:
        return
    session, capability = creds
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from ops.testkit import run
    env = os.environ.copy()
    env["CLAUDE_CODE_SESSION_ID"] = session
    env["COORDINATION_CAPABILITY"] = capability
    tool = str(Path(REPO) / "ops" / "conductor" / "tools" / "coordination.py")
    try:
        run([sys.executable, tool, *argv], cwd=os.getcwd(), env=env, timeout=30)
    except Exception:
        return


def inbox() -> str:
    creds = credentials()
    if creds is None:
        return ""
    session, capability = creds
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from ops.testkit import run
    env = os.environ.copy()
    env["CLAUDE_CODE_SESSION_ID"] = session
    env["COORDINATION_CAPABILITY"] = capability
    tool = str(Path(REPO) / "ops" / "conductor" / "tools" / "coordination.py")
    try:
        shown = run([sys.executable, tool, "inbox"], cwd=os.getcwd(), env=env, timeout=30)
    except Exception:
        return ""
    if shown.exit != 0:
        return ""
    return shown.stdout


def ack_lines(predicate) -> None:
    for line in inbox().splitlines():
        if not predicate(line):
            continue
        for token in line.split():
            if re.fullmatch(r"M-\d+", token):
                core("ack", token)


def native_id(spec: dict) -> str:
    named = spec.get("native_id")
    if isinstance(named, str) and named:
        return named
    return f"session-{os.getpid()}"


def on_submit(params, native: str) -> None:
    spec = load_spec()
    blob = "\n".join(texts(params))
    reply = spec.get("reply") if isinstance(spec.get("reply"), str) else "grok-reply-a503"
    if "readiness probe" in blob:
        if spec.get("ack_probe"):
            ack_lines(lambda line: "readiness probe" in line)
    else:
        emit({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": native,
                "update": {"sessionUpdate": "agent_message_chunk", "text": reply},
            },
        })
        if spec.get("send_reply") and blob.strip():
            for line in inbox().splitlines():
                if not any(part and part in line for part in texts(params)):
                    continue
                sender = re.search(r"\bfrom (PT-\d+)\b", line)
                if sender:
                    core("send", "--to", sender.group(1), "--purpose", "inform", "--body", reply)
                    break
        if spec.get("ack"):
            ack_lines(lambda line: True)
    emit({
        "jsonrpc": "2.0",
        "method": "_x.ai/session/prompt_complete",
        "params": {"sessionId": native},
    })


def handle(raw: str, msg: dict) -> bool:
    method = msg.get("method")
    if not isinstance(method, str):
        return False
    req_id = msg.get("id", None)
    params = msg.get("params")
    if not isinstance(params, dict):
        params = {}
    spec = load_spec()
    native = native_id(spec)
    log_request(raw, method, req_id, params, native)
    die = spec.get("die_after") == method
    if spec.get("reject_method") == method:
        if req_id is not None:
            method_not_found(req_id)
        return die
    if method == "initialize" and req_id is not None:
        body = {"protocolVersion": 1}
        if spec.get("advertise_auth", True):
            body["authMethods"] = [{"id": "agent", "name": "agent"}]
        result(req_id, body)
    elif method == "authenticate" and req_id is not None:
        result(req_id, {})
    elif method == "session/new" and req_id is not None:
        result(req_id, {"sessionId": native})
        emit({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": native,
                "update": {"sessionUpdate": "tool_call", "name": "coordination"},
            },
        })
    elif method in {"session/prompt", "_x.ai/interject"} and req_id is not None:
        result(req_id, {})
        on_submit(params, native)
    return die


def main() -> int:
    if sys.argv[1:2] == ["--version"]:
        sys.stdout.write("session-grok 0.0.0-fake\n")
        return 0
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if not isinstance(msg, dict):
            continue
        if handle(line, msg):
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
