# testkit: exempt fixture program planted as the codex app-server
"""The codex app-server the slice 2 adapter rows drive.

Speaks `app-server --listen stdio://`: one JSON line per request in the
spec's log. Answers `initialize`, `thread/start` with the spec's
`thread.id`, and `turn/start` with `turn.id`. Emits `thread/started`
(the frame whose `threadId` is the native id), then `turn/started`,
`item/agentMessage/delta` and `turn/completed`, each carrying that
`threadId`. A spec `error_method` is answered -32601. `die_after` exits
once that request has been answered.

With `inbox` in the spec, the process is spawned through `ops.testkit.run`
(its stdin is closed) and serves the inbox. Without `inbox`, the same
dispatch reads stdio. `RPC` is the pipes the adapter's `handshake`,
`submit` and `observe` drive against that process.

origin: sessions-lever.md#slice-2 adapters
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


class RPCError(Exception):
    """A JSON-RPC error result. `code` is the number, `method` the request."""

    def __init__(self, code: int, message: str, method: str):
        super().__init__(f"{method} {code} {message}")
        self.code = int(code)
        self.message = message
        self.method = method


class Closed(ConnectionError):
    """The server died before answering `method`."""

    def __init__(self, method: str):
        super().__init__(method)
        self.method = method


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def log_request(log_path: str, raw: str) -> None:
    line = raw.strip() + "\n"
    fd = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def dispatch(spec: dict, raw: str) -> tuple[dict | None, list, bool]:
    """One request. Returns the response object (or None for a
    notification or a client response), the events to emit, and whether
    the spec says to die after this method."""
    obj = json.loads(raw)
    method = obj.get("method")
    ident = obj.get("id")
    if method is None:
        return None, [], False
    die = spec.get("die_after") == method
    if spec.get("error_method") == method and ident is not None:
        error = {"id": ident, "error": {"code": -32601, "message": "Method not found"}}
        return error, [], die
    events: list = []
    if method == "initialize":
        result = {"userAgent": "session-codex-fake"}
    elif method == "initialized":
        return None, [], die
    elif method == "thread/start":
        result = {"thread": {"id": spec["thread_id"]}}
        events = [{"method": "thread/started", "params": {"threadId": spec["thread_id"]}}]
    elif method == "turn/start":
        result = {"turn": {"id": spec["turn_id"]}}
        thread_id = spec["thread_id"]
        turn_id = spec["turn_id"]
        events = [
            {"method": "turn/started", "params": {"threadId": thread_id, "turnId": turn_id}},
            {"method": "item/agentMessage/delta", "params": {
                "threadId": thread_id, "delta": spec["delta"]}},
            {"method": "turn/completed", "params": {"threadId": thread_id, "turnId": turn_id}},
        ]
    else:
        result = {}
    if ident is None:
        return None, events, die
    return {"id": ident, "result": result}, events, die


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class RPC:
    """The pipes `handshake`, `submit` and `observe` drive.

    `request(method, params)` returns the result object (`thread` / `turn`).
    A -32601 answer raises `RPCError`. A dead server raises `Closed`.
    `notify(method, params)` and `respond(ident, result)` are logged and
    return nothing. `frames()` is every notification emitted so far.
    """

    def __init__(self, spec_path: Path, box: dict | None = None):
        self.spec_path = Path(spec_path)
        self.spec = json.loads(self.spec_path.read_text(encoding="utf-8"))
        self.box = box if box is not None else {}
        self.inbox = Path(self.spec["inbox"])
        self.outbox = Path(self.spec["outbox"])
        self._n = 0
        self._frames: list = []

    def wait_ready(self, timeout: float = 5.0) -> None:
        ready = Path(self.spec["ready"])
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.box.get("error") is not None:
                raise AssertionError(f"INVALID: app-server did not start: {self.box['error']}")
            if ready.is_file() and ready.read_text(encoding="utf-8").strip().isdigit():
                return
            time.sleep(0.02)
        raise AssertionError(
            f"INVALID: app-server was not started through ops.testkit.run: {self.box!r}"
        )

    def frames(self) -> list:
        return list(self._frames)

    def request(self, method: str, params: dict | None = None) -> dict:
        ident = f"{self._n:04d}"
        self._n += 1
        payload = {"id": ident, "method": method, "params": params or {}}
        self._write(ident, payload)
        body = self._wait(ident, method)
        if "error" in body:
            error = body["error"]
            raise RPCError(int(error["code"]), str(error.get("message", "")), method)
        return body.get("result", {})

    def notify(self, method: str, params: dict | None = None) -> None:
        ident = f"{self._n:04d}"
        self._n += 1
        self._write(ident, {"method": method, "params": params or {}})
        self._wait_ack(ident)

    def respond(self, ident: str, result: dict) -> None:
        seq = f"{self._n:04d}"
        self._n += 1
        self._write(seq, {"id": ident, "result": result})
        self._wait_ack(seq)

    def _write(self, seq: str, payload: dict) -> None:
        atomic_write(self.inbox / f"{seq}.json", json.dumps(payload))

    def _wait(self, seq: str, method: str) -> dict:
        path = self.outbox / f"{seq}.json"
        events = self.outbox / f"{seq}.events.json"
        deadline = time.time() + 3
        while time.time() < deadline:
            if path.is_file():
                if events.is_file():
                    self._frames.extend(json.loads(events.read_text(encoding="utf-8")))
                return json.loads(path.read_text(encoding="utf-8"))
            if self._dead():
                break
            time.sleep(0.02)
        raise Closed(method)

    def _wait_ack(self, seq: str) -> None:
        path = self.outbox / f"{seq}.ack"
        deadline = time.time() + 0.4
        while time.time() < deadline:
            if path.is_file():
                return
            if self._dead():
                return
            time.sleep(0.02)

    def _dead(self) -> bool:
        ready = Path(self.spec["ready"])
        if not ready.is_file():
            return False
        text = ready.read_text(encoding="utf-8").strip()
        return text.isdigit() and not _alive(int(text))


def serve_inbox(spec: dict) -> int:
    inbox = Path(spec["inbox"])
    outbox = Path(spec["outbox"])
    inbox.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    atomic_write(Path(spec["ready"]), str(os.getpid()))
    seen: set[str] = set()
    while not Path(spec["stop"]).exists():
        pending = sorted(
            path for path in inbox.iterdir()
            if path.suffix == ".json" and path.name not in seen
        )
        for path in pending:
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                continue
            seen.add(path.name)
            response, events, die = dispatch(spec, raw)
            log_request(spec["log"], raw)
            stem = path.stem
            if response is not None:
                atomic_write(outbox / f"{stem}.json", json.dumps(response))
            else:
                atomic_write(outbox / f"{stem}.ack", "ok\n")
            if events:
                atomic_write(outbox / f"{stem}.events.json", json.dumps(events))
            if die:
                return 0
        time.sleep(0.02)
    return 0


def serve_stdio(spec: dict) -> int:
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        response, events, die = dispatch(spec, raw)
        log_request(spec["log"], raw)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
        for event in events:
            sys.stdout.write(json.dumps(event) + "\n")
        sys.stdout.flush()
        if die:
            return 0
    return 0


def main(argv: list[str]) -> int:
    if "--listen" not in argv or "stdio://" not in argv or argv[-1] == "stdio://":
        sys.stderr.write(
            "channel: expected app-server --listen stdio:// SPEC; "
            f"found {argv!r}; needed the stdio listener and a spec\n"
        )
        return 2
    spec = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
    if spec.get("inbox"):
        return serve_inbox(spec)
    return serve_stdio(spec)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
