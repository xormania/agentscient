# testkit: exempt fixture program planted as the grok agent stdio peer
"""ACP peer for the grok session adapter.

Planted through Tools. The registry spec names the session id, whether
`initialize` advertises `authenticate`, a method answered -32601, a
method after which the process exits, and the permission title it may
ask. One JSON line per request goes to the requests log. The case
spawns this through ops.testkit.run; `run` keeps the pipes, so the
peer listens on the spec's unix socket and the case hands those pipes
to channel.RPC.

Emissions for `session/prompt` are written before the result, so a
reader thread can demux them and the request still completes: a
`session/update` agent_message_chunk, then `_x.ai/session/prompt_complete`,
then `session/request_permission` when the spec names a title.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path


def spec_path() -> Path | None:
    named = os.environ.get("TESTKIT_FAKE_SPEC", "")
    if named:
        path = Path(named)
        if path.is_file():
            return path
    exe = Path(sys.argv[0]).resolve()
    candidate = exe.parent.parent / "fakes" / f"{exe.name}.spec.json"
    return candidate if candidate.is_file() else None


def load_spec() -> dict:
    path = spec_path()
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def append(path: str, packet: dict) -> None:
    line = json.dumps(packet, separators=(",", ":")) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def send(conn: socket.socket, packet: dict) -> None:
    data = (json.dumps(packet, separators=(",", ":")) + "\n").encode("utf-8")
    conn.setblocking(True)
    conn.sendall(data)
    conn.setblocking(False)


def result_packet(ident, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def error_packet(ident, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": message}}


def packets(conn: socket.socket, stop: Path):
    conn.setblocking(False)
    buf = b""
    while not stop.exists():
        try:
            chunk = conn.recv(65536)
        except BlockingIOError:
            time.sleep(0.02)
            continue
        if chunk == b"":
            return
        buf += chunk
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            text = raw.decode("utf-8").strip()
            if not text:
                continue
            try:
                packet = json.loads(text)
            except ValueError:
                continue
            if isinstance(packet, dict):
                yield packet


def initialize_result(spec: dict) -> dict:
    result: dict = {"protocolVersion": 1}
    if spec.get("advertise_authenticate"):
        result["authMethods"] = [{"id": "token", "name": "token"}]
    return result


def emit_prompt(conn: socket.socket, spec: dict) -> bool:
    sid = spec["session_id"]
    frames = [
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": sid,
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": spec.get("update_text", "")},
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "method": "_x.ai/session/prompt_complete",
            "params": {"sessionId": sid, "turn": spec.get("turn", "")},
        },
    ]
    title = spec.get("permission_title")
    if title:
        frames.append({
            "jsonrpc": "2.0",
            "id": "perm-1",
            "method": "session/request_permission",
            "params": {
                "sessionId": sid,
                "title": title,
                "toolCall": {"toolCallId": "call-1", "title": title},
            },
        })
    for frame in frames:
        append(spec["emitted"], frame)
        send(conn, frame)
    return bool(title)


def converse(conn: socket.socket, spec: dict, stop: Path) -> None:
    waiting = False
    for packet in packets(conn, stop):
        method = packet.get("method")
        if waiting and not method:
            append(spec["answers"], packet)
            if packet.get("id") == "perm-1" or "decline" in json.dumps(packet):
                waiting = False
            continue
        if not method:
            append(spec["answers"], packet)
            continue
        append(spec["requests"], {
            "method": method,
            "id": packet.get("id"),
            "params": packet.get("params") or {},
        })
        ident = packet.get("id")
        if spec.get("die_after") == method:
            if method == "initialize":
                send(conn, result_packet(ident, initialize_result(spec)))
            return
        if spec.get("reject_method") == method:
            send(conn, error_packet(ident, -32601, "Method not found"))
            continue
        if method == "initialize":
            send(conn, result_packet(ident, initialize_result(spec)))
        elif method == "authenticate":
            send(conn, result_packet(ident, {}))
        elif method == "session/new":
            send(conn, result_packet(ident, {"sessionId": spec["session_id"]}))
        elif method == "session/prompt":
            waiting = emit_prompt(conn, spec)
            send(conn, result_packet(ident, {}))
        elif method == "_x.ai/interject":
            send(conn, result_packet(ident, {}))
        else:
            send(conn, error_packet(ident, -32601, "Method not found"))


def serve(spec: dict) -> int:
    sock_path = Path(spec["socket"])
    if sock_path.exists():
        sock_path.unlink()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(sock_path))
        server.listen(1)
        server.settimeout(0.2)
        Path(spec["ready"]).write_text(str(os.getpid()), encoding="utf-8")
        stop = Path(spec["stop"])
        conn = None
        while conn is None:
            if stop.exists():
                return 0
            try:
                conn, _addr = server.accept()
            except socket.timeout:
                continue
        try:
            converse(conn, spec, stop)
        finally:
            conn.close()
    finally:
        server.close()
    return 0


def main(argv: list[str]) -> int:
    spec = load_spec()
    required = ("socket", "ready", "stop", "requests", "emitted", "answers", "session_id")
    missing = [key for key in required if not spec.get(key)]
    if missing or argv:
        found = f"argv {argv!r}, missing {missing!r}"
        sys.stderr.write(
            "arguments: expected the registry spec and no argv; "
            f"found {found}; needed the planted grok spec\n"
        )
        return 2
    try:
        return serve(spec)
    except OSError as exc:
        sys.stderr.write(
            f"channel: expected a unix socket; found {exc}; needed a path the peer can bind\n"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
