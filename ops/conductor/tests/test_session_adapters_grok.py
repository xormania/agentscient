"""Grok adapter, sessions slice 2.

Contract: `ops/conductor/sessions-lever.md` "The adapter boundary, extended"
(`transport`, `channel`, `handshake`, `submit`, `observe`) and the grok
fake in "Tests". `session_adapters/grok.py` and `channel.py` are withheld.
A missing adapter fails the row's own reading, not an import.

`session/update` carrying the chunk text reads `output <text>`.
`_x.ai/session/prompt_complete` carrying the turn reads `done <turn>`.
A frame naming another sessionId reads `refused native`.
`session/request_permission` is answered `decline` and reads
`permission <title>`.

Declared gap: planted faults follow the implementation, which is absent,
so this module has no mutants file.

The one command that reads this file is
`python3 -m unittest discover -s ops/conductor/tests -p test_session_adapters_grok.py`.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from ops.testkit import RefusalCase, Result, World, refusal_wire, run

REPO = Path(__file__).resolve().parents[3]
ADAPTERS = REPO / "ops" / "conductor" / "tools" / "session_adapters"
GROK = ADAPTERS / "grok.py"
CHANNEL = ADAPTERS / "channel.py"
FAKES = Path(__file__).resolve().parent / "fakes"
FAKE_SRC = FAKES / "session_grok.py"
ORIGIN = "sessions-lever.md#slice-2 adapters"
SHORT_ROOT = "/tmp"
SOCKET_LIMIT = 108
SESSION_ID = "sess-grok-506"
OTHER_SESSION = "sess-other"
UPDATE_TEXT = "pane-line"
TURN = "turn-7"
PERMISSION_TITLE = "run the suite"
OPERATOR_TEXT = "operator line for gee"
CHANNEL_TAIL = ["--no-auto-update", "agent", "stdio"]
HANDSHAKE = ["initialize", "session/new"]
HANDSHAKE_AUTH = ["initialize", "authenticate", "session/new"]


def fake_text(path: Path) -> str:
    """The planted peer, its shebang this interpreter."""
    if not path.is_file():
        raise AssertionError(f"INVALID: planted program missing: {path}")
    text = path.read_text(encoding="utf-8")
    if text.startswith("#!"):
        text = text.split("\n", 1)[1]
    return f"#!{sys.executable}\n" + text


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def open_world(prefix: str) -> World:
    """A world rooted under /tmp so the peer's socket stays under 108 bytes."""
    saved = tempfile.tempdir
    tempfile.tempdir = SHORT_ROOT
    try:
        return World(prefix=prefix)
    finally:
        tempfile.tempdir = saved


class TheGrokAdapter(unittest.TestCase):
    """Slice 2's five grok methods against the planted ACP peer.

    Rows are addressed by id. origin: sessions-lever.md#slice-2 adapters.
    """

    def setUp(self):
        self.world = open_world("session-grok-")
        self.addCleanup(self.world.close)
        self.requests_path = self.world.root / "fakes" / "grok.requests.jsonl"
        self.emitted_path = self.world.root / "fakes" / "grok.emitted.jsonl"
        self.answers_path = self.world.root / "fakes" / "grok.answers.jsonl"
        self.planted = self.world.tools.plant("grok", script=fake_text(FAKE_SRC))
        self.binding_path = self.world.plant_text("binding.json", "{}\n", recognisable="{")

    def adapter(self):
        if not GROK.is_file():
            return None
        try:
            module = load_module(GROK, "session_adapters_grok")
        except Exception:
            return None
        cls = getattr(module, "Adapter", None)
        if not isinstance(cls, type):
            return None
        try:
            return cls()
        except Exception:
            return None

    def open_rpc(self, reader, writer):
        """channel.RPC wraps the pipes this case spawned: reader, then writer."""
        if not CHANNEL.is_file():
            return None
        try:
            module = load_module(CHANNEL, "session_adapters_channel")
        except Exception:
            return None
        rpc_cls = getattr(module, "RPC", None)
        if not isinstance(rpc_cls, type):
            return None
        try:
            return rpc_cls(reader, writer)
        except Exception:
            return None

    def member(self) -> dict:
        return {"name": "gee", "harness": "grok"}

    def binding(self) -> dict:
        return {
            "executable": str(self.planted),
            "binding": str(self.binding_path),
            "harness": "grok",
        }

    def lines(self, path: Path) -> list[dict] | None:
        if not path.is_file():
            return None
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def methods(self) -> list[str] | None:
        rows = self.lines(self.requests_path)
        if rows is None:
            return None
        return [row.get("method") for row in rows]

    def spawn(self, **overrides):
        """The planted peer, started through ops.testkit.run with a timeout."""
        ready = self.world.tmp / "grok.ready"
        stop = self.world.tmp / "grok.stop"
        sock = self.world.tmp / "g.sock"
        for path in (ready, stop):
            if path.exists():
                path.unlink()
        if sock.exists():
            sock.unlink()
        if len(os.fsencode(str(sock))) >= SOCKET_LIMIT:
            raise AssertionError(f"INVALID: agent socket must be under {SOCKET_LIMIT} bytes: {sock}")
        spec_path = self.world.tools.spec_path("grok")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        fields = {
            "session_id": SESSION_ID,
            "advertise_authenticate": False,
            "reject_method": None,
            "die_after": None,
            "permission_title": None,
            "update_text": UPDATE_TEXT,
            "turn": TURN,
            "requests": str(self.requests_path),
            "emitted": str(self.emitted_path),
            "answers": str(self.answers_path),
            "ready": str(ready),
            "stop": str(stop),
            "socket": str(sock),
        }
        fields.update(overrides)
        spec.update(fields)
        spec_path.write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
        landed = json.loads(spec_path.read_text(encoding="utf-8"))
        if landed.get("session_id") != fields["session_id"]:
            raise AssertionError("INVALID: grok spec did not land intact")
        for log in (self.requests_path, self.emitted_path, self.answers_path):
            if log.exists():
                log.unlink()
        box: dict = {}

        def invoke() -> None:
            try:
                box["result"] = run(
                    [str(self.planted)],
                    cwd=self.world.cwd,
                    env=self.world.env(extra={"TESTKIT_FAKE_SPEC": str(spec_path)}),
                    timeout=30,
                )
            except BaseException as exc:  # the row asserts the adapter
                box["error"] = exc

        thread = threading.Thread(target=invoke)
        thread.start()
        client_box: dict = {}

        def release() -> None:
            client = client_box.get("client")
            if client is not None:
                with contextlib.suppress(OSError):
                    client.close()
            if not stop.exists():
                stop.write_text("stop\n", encoding="utf-8")
            thread.join(timeout=15)

        self.addCleanup(release)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not ready.is_file():
            if "error" in box:
                break
            time.sleep(0.02)
        if not ready.is_file():
            raise AssertionError(f"INVALID: grok fake was not started through ops.testkit.run: {box!r}")
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_box["client"] = client
        client.connect(str(sock))
        reader = client.makefile("r", encoding="utf-8", newline="\n", buffering=1)
        writer = client.makefile("w", encoding="utf-8", newline="\n", buffering=1)
        return self.open_rpc(reader, writer)

    def wait_decline(self) -> bool:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            text = self.answers_path.read_text(encoding="utf-8") if self.answers_path.is_file() else ""
            if "decline" in text:
                return True
            time.sleep(0.02)
        text = self.answers_path.read_text(encoding="utf-8") if self.answers_path.is_file() else ""
        return "decline" in text

    def test_transport_reads_protocol(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        with self.subTest(id="grok-transport-protocol", origin=ORIGIN):
            adapter = self.adapter()
            reading = None
            error = None
            if adapter is not None:
                try:
                    reading = adapter.transport()
                except Exception as exc:
                    error = exc
            self.assertIsNone(error, error)
            self.assertEqual(reading, "protocol")

    def test_channel_argv_ends_with_agent_stdio(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        with self.subTest(id="grok-channel-agent-stdio", origin=ORIGIN):
            adapter = self.adapter()
            parts = None
            error = None
            if adapter is not None:
                try:
                    parts = [str(item) for item in adapter.channel(self.member(), self.binding())]
                except Exception as exc:
                    error = exc
            self.assertIsNone(error, error)
            tail = None if parts is None else parts[-3:]
            self.assertEqual(tail, CHANNEL_TAIL)

    def test_handshake_returns_the_spec_session_id(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        with self.subTest(id="grok-handshake-session-id", origin=ORIGIN):
            adapter = self.adapter()
            native = None
            version = None
            error = None
            if adapter is not None:
                rpc = self.spawn()
                try:
                    native = adapter.handshake(rpc)
                except Exception as exc:
                    error = exc
                for row in self.lines(self.requests_path) or []:
                    if row.get("method") == "initialize":
                        version = (row.get("params") or {}).get("protocolVersion")
            self.assertIsNone(error, error)
            self.assertEqual((native, version), (SESSION_ID, 1))

    def test_handshake_calls_authenticate_only_when_advertised(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        with self.subTest(id="grok-handshake-authenticate", origin=ORIGIN):
            adapter = self.adapter()
            native = None
            methods = None
            error = None
            if adapter is not None:
                rpc = self.spawn(advertise_authenticate=True)
                try:
                    native = adapter.handshake(rpc)
                except Exception as exc:
                    error = exc
                methods = self.methods()
            self.assertIsNone(error, error)
            self.assertEqual((methods, native), (HANDSHAKE_AUTH, SESSION_ID))

    def test_handshake_skips_authenticate_when_it_is_not_advertised(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        with self.subTest(id="grok-handshake-no-authenticate", origin=ORIGIN):
            adapter = self.adapter()
            native = None
            methods = None
            error = None
            if adapter is not None:
                rpc = self.spawn(advertise_authenticate=False)
                try:
                    native = adapter.handshake(rpc)
                except Exception as exc:
                    error = exc
                methods = self.methods()
            self.assertIsNone(error, error)
            self.assertEqual((methods, native), (HANDSHAKE, SESSION_ID))

    def test_handshake_dying_after_initialize_refuses_channel_naming_session_new(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        case = RefusalCase(
            id="grok-handshake-dies-after-initialize",
            argv=("handshake",),
            cls="channel",
            named=("session/new",),
            origin=ORIGIN,
        )
        with self.subTest(id=case.id, origin=case.origin):
            refusal_wire(case, self.channel_refusal())

    def channel_refusal(self) -> Result:
        adapter = self.adapter()
        cwd = str(self.world.cwd)
        if adapter is None:
            return Result(("handshake",), 0, "", "", 0.0, cwd)
        rpc = self.spawn(die_after="initialize")
        try:
            adapter.handshake(rpc)
        except Exception as exc:
            line = exc.line() if callable(getattr(exc, "line", None)) else str(exc)
            stderr = line if line.endswith("\n") else line + "\n"
            return Result(("handshake",), 2, "", stderr, 0.0, cwd)
        return Result(("handshake",), 0, "handshake returned\n", "", 0.0, cwd)

    def test_submit_idle_sends_session_prompt_and_reads_written(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        with self.subTest(id="grok-submit-idle", origin=ORIGIN):
            reading, sent, carried, error = self.submitted(busy=False)
            self.assertIsNone(error, error)
            self.assertEqual((reading, sent, carried), ("written", True, True))

    def test_submit_busy_sends_interject(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        with self.subTest(id="grok-submit-busy", origin=ORIGIN):
            reading, sent, carried, error = self.submitted(busy=True)
            self.assertIsNone(error, error)
            self.assertEqual((reading, sent, carried), ("written", True, True))

    def submitted(self, *, busy: bool):
        adapter = self.adapter()
        if adapter is None:
            return None, None, None, None
        method = "_x.ai/interject" if busy else "session/prompt"
        other = "session/prompt" if busy else "_x.ai/interject"
        rpc = self.spawn()
        error = None
        reading = None
        try:
            adapter.handshake(rpc)
            reading = adapter.submit(rpc, OPERATOR_TEXT, busy=busy)
        except Exception as exc:
            error = exc
        rows = self.lines(self.requests_path) or []
        methods = [row.get("method") for row in rows]
        sent = method in methods and other not in methods
        carried = any(
            row.get("method") == method and OPERATOR_TEXT in json.dumps(row)
            for row in rows
        )
        return reading, sent, carried, error

    def test_submit_method_not_found_reads_unsupported_session_prompt(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        with self.subTest(id="grok-submit-unsupported", origin=ORIGIN):
            adapter = self.adapter()
            reading = None
            saw = None
            error = None
            if adapter is not None:
                rpc = self.spawn(reject_method="session/prompt")
                try:
                    adapter.handshake(rpc)
                    reading = adapter.submit(rpc, OPERATOR_TEXT, busy=False)
                except Exception as exc:
                    error = exc
                saw = "session/prompt" in (self.methods() or [])
            self.assertIsNone(error, error)
            self.assertEqual((reading, saw), ("unsupported session/prompt", True))

    def test_observe_classifies_each_emitted_frame(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        with self.subTest(id="grok-observe-emitted", origin=ORIGIN):
            adapter = self.adapter()
            readings = None
            error = None
            if adapter is not None:
                rpc = self.spawn()
                try:
                    adapter.handshake(rpc)
                    adapter.submit(rpc, OPERATOR_TEXT, busy=False)
                    readings = [adapter.observe(rpc, frame) for frame in self.lines(self.emitted_path) or []]
                except Exception as exc:
                    error = exc
            self.assertIsNone(error, error)
            self.assertEqual(readings, [f"output {UPDATE_TEXT}", f"done {TURN}"])

    def test_observe_a_frame_naming_another_session_reads_refused_native(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        with self.subTest(id="grok-observe-other-session", origin=ORIGIN):
            adapter = self.adapter()
            reading = None
            error = None
            if adapter is not None:
                rpc = self.spawn()
                frame = {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": OTHER_SESSION,
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"type": "text", "text": "nope"},
                        },
                    },
                }
                try:
                    adapter.handshake(rpc)
                    reading = adapter.observe(rpc, frame)
                except Exception as exc:
                    error = exc
            self.assertIsNone(error, error)
            self.assertEqual(reading, "refused native")

    def test_observe_permission_is_declined_and_reads_the_title(self):
        """origin: sessions-lever.md#slice-2 adapters"""
        with self.subTest(id="grok-observe-permission", origin=ORIGIN):
            adapter = self.adapter()
            reading = None
            declined = None
            printed = None
            error = None
            if adapter is not None:
                rpc = self.spawn(permission_title=PERMISSION_TITLE)
                try:
                    adapter.handshake(rpc)
                    adapter.submit(rpc, OPERATOR_TEXT, busy=False)
                    frame = next(
                        item for item in (self.lines(self.emitted_path) or [])
                        if item.get("method") == "session/request_permission"
                    )
                    buffer = io.StringIO()
                    with contextlib.redirect_stdout(buffer):
                        reading = adapter.observe(rpc, frame)
                    printed = PERMISSION_TITLE in buffer.getvalue()
                    declined = self.wait_decline()
                except Exception as exc:
                    error = exc
            self.assertIsNone(error, error)
            self.assertEqual(
                (reading, declined, printed),
                (f"permission {PERMISSION_TITLE}", True, True),
            )


if __name__ == "__main__":
    unittest.main()
