"""Managed sessions slice 2: the codex adapter over a planted app-server.

Contract: `ops/conductor/sessions-lever.md` §The adapter boundary, extended.
The fake `fakes/session_codex.py` is planted through the kit and spawned
through `run`. `framing.Parser` is the real parser. A missing adapter
fails the row's own reading, not an import error.

The one command that reads this file is
`python3 -m unittest discover -s ops/conductor/tests -p test_session_adapters_codex.py`.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import unittest
from pathlib import Path

from ops.testkit import RefusalCase, Result, World, refusal_wire, run

REPO = Path(__file__).resolve().parents[3]
ADAPTERS = REPO / "ops" / "conductor" / "tools" / "session_adapters"
CODEX = ADAPTERS / "codex.py"
FRAMING = ADAPTERS / "framing.py"
FAKES = Path(__file__).resolve().parent / "fakes"
FAKE_SRC = FAKES / "session_codex.py"
ORIGIN = "sessions-lever.md#slice-2 adapters"
LANE_CONF = str(REPO / "ops" / "lane.conf")


def fake_text(path: Path) -> str:
    """A program under fakes/, its shebang this interpreter."""
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


def reading_of(exc: BaseException) -> str:
    return str(getattr(exc, "reading", None) or exc)


class TheCodexAdapter(unittest.TestCase):
    """The five protocol methods against the planted app-server.

    origin: sessions-lever.md#slice-2 adapters
    """

    def setUp(self):
        self.world = World(prefix="session-codex-", host_path=False)
        self.addCleanup(self.world.close)
        self._fake = None

    def adapter(self):
        if not CODEX.is_file():
            return None
        try:
            module = load_module(CODEX, "session_adapters_codex")
        except Exception:
            return None
        cls = getattr(module, "Adapter", None)
        if not isinstance(cls, type):
            return None
        try:
            return cls()
        except Exception:
            return None

    def fake(self):
        if self._fake is None:
            self._fake = load_module(FAKE_SRC, "session_codex_fake")
        return self._fake

    def parser(self):
        self.assertTrue(FRAMING.is_file(), f"RED: framing is absent: {FRAMING}")
        return load_module(FRAMING, "session_adapters_framing_codex")

    def as_frame(self, event: dict) -> dict:
        module = self.parser()
        return module.Parser().feed(json.dumps(event, separators=(",", ":")))

    def plant(self) -> Path:
        return self.world.tools.plant("app-server", script=fake_text(FAKE_SRC))

    def start(self, **overrides):
        name = self.world.root.name
        prefix = "session-codex-"
        token = name[len(prefix):] if name.startswith(prefix) else name
        root = self.world.root / "codex"
        inbox = root / "inbox"
        outbox = root / "outbox"
        inbox.mkdir(parents=True)
        outbox.mkdir(parents=True)
        spec = {
            "thread_id": f"thread-{token}",
            "turn_id": f"turn-{token}",
            "delta": f"delta-{token}",
            "error_method": None,
            "die_after": None,
            "inbox": str(inbox),
            "outbox": str(outbox),
            "log": str(root / "requests.jsonl"),
            "ready": str(root / "ready"),
            "stop": str(root / "stop"),
        }
        spec.update(overrides)
        spec_path = root / "spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        exe = self.plant()
        box: dict = {}

        def invoke() -> None:
            try:
                box["result"] = run(
                    [str(exe), "--listen", "stdio://", str(spec_path)],
                    cwd=self.world.cwd,
                    env=self.world.env(extra={"LANE_CONF": LANE_CONF}),
                    timeout=30,
                )
            except BaseException as exc:  # the row asserts the adapter, not the spawn
                box["error"] = exc

        thread = threading.Thread(target=invoke)
        thread.start()

        def stop() -> None:
            Path(spec["stop"]).write_text("stop\n", encoding="utf-8")
            thread.join(timeout=15)

        self.addCleanup(stop)
        rpc = self.fake().RPC(spec_path, box)
        rpc.wait_ready()
        return rpc, spec

    def log_text(self, spec: dict) -> str:
        path = Path(spec["log"])
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def call(self, fn):
        try:
            return fn()
        except Exception as exc:
            return reading_of(exc)

    def test_transport_reads_protocol(self):
        with self.subTest(id="transport-protocol", origin=ORIGIN):
            adapter = self.adapter()
            reading = ""
            if adapter is not None:
                reading = self.call(adapter.transport)
            self.assertEqual(reading, "protocol")

    def test_channel_argv_ends_with_app_server_listen_stdio(self):
        with self.subTest(id="channel-app-server", origin=ORIGIN):
            adapter = self.adapter()
            binding_path = self.world.root / "binding.json"
            self.world.plant_text(binding_path, "{}\n", recognisable="{")
            self.plant()
            binding = {
                "executable": str(self.world.bin / "app-server"),
                "binding": str(binding_path),
                "harness": "codex",
            }
            argv: list = []
            if adapter is not None:
                argv = self.call(
                    lambda: list(adapter.channel({"name": "co", "harness": "codex"}, binding))
                )
                if not isinstance(argv, list):
                    argv = []
            parts = [str(part) for part in argv]
            tail = [Path(parts[-3]).name, parts[-2], parts[-1]] if len(parts) >= 3 else parts
            self.assertEqual(tail, ["app-server", "--listen", "stdio://"])

    def test_handshake_returns_the_spec_thread_id(self):
        with self.subTest(id="handshake-thread-id", origin=ORIGIN):
            rpc, spec = self.start()
            adapter = self.adapter()
            reading = None
            if adapter is not None:
                reading = self.call(lambda: adapter.handshake(rpc))
            self.assertEqual(reading, spec["thread_id"])

    def test_handshake_dying_after_initialize_refuses_channel(self):
        row = RefusalCase(
            id="handshake-dies-after-initialize",
            argv=("app-server", "--listen", "stdio://"),
            cls="channel",
            named=("thread/start",),
            origin=ORIGIN,
        )
        with self.subTest(id=row.id, origin=row.origin):
            refusal_wire(row, self.handshake_refusal())

    def handshake_refusal(self) -> Result:
        rpc, _spec = self.start(die_after="initialize")
        adapter = self.adapter()
        cwd = str(self.world.cwd)
        argv = ("app-server", "--listen", "stdio://")
        if adapter is None:
            return Result(argv, 0, "", "", 0.0, cwd)
        try:
            value = adapter.handshake(rpc)
        except BaseException as exc:
            text = reading_of(exc).strip()
            if text.startswith("channel:"):
                return Result(argv, 2, "", text + "\n", 0.0, cwd)
            return Result(argv, 0, "", text + "\n", 0.0, cwd)
        text = str(value).strip()
        if text.startswith("channel:"):
            return Result(argv, 2, "", text + "\n", 0.0, cwd)
        return Result(argv, 0, text, "", 0.0, cwd)

    def test_submit_idle_reads_accepted_turn(self):
        with self.subTest(id="submit-idle-turn", origin=ORIGIN):
            rpc, spec = self.start()
            adapter = self.adapter()
            reading = None
            if adapter is not None:
                reading = self.call(lambda: adapter.submit(rpc, "hello", busy=False))
            self.assertEqual(reading, f"accepted turn {spec['turn_id']}")
            self.assertIn("turn/start", self.log_text(spec))

    def test_submit_busy_sends_tool_output_into_the_active_turn(self):
        with self.subTest(id="submit-busy-tool-output", origin=ORIGIN):
            rpc, spec = self.start()
            adapter = self.adapter()
            if adapter is not None:
                self.call(lambda: adapter.submit(rpc, "hello", busy=False))
                self.call(lambda: adapter.submit(rpc, "tool says 1", busy=True))
            line = next(
                (ln for ln in self.log_text(spec).splitlines() if "toolOutput" in ln),
                "",
            )
            self.assertIn("toolOutput", line)
            self.assertIn(spec["turn_id"], line)

    def test_submit_method_not_found_reads_unsupported_turn_start(self):
        with self.subTest(id="submit-unsupported-turn-start", origin=ORIGIN):
            rpc, _spec = self.start(error_method="turn/start")
            adapter = self.adapter()
            reading = None
            if adapter is not None:
                reading = self.call(lambda: adapter.submit(rpc, "hello", busy=False))
            self.assertEqual(reading, "unsupported turn/start")

    def test_observe_classifies_each_emitted_frame(self):
        rpc, spec = self.start()
        rpc.request("initialize", {})
        rpc.notify("initialized")
        rpc.request("thread/start", {})
        rpc.request("turn/start", {"input": "ping"})
        by_method = {frame["method"]: frame for frame in rpc.frames()}
        rows = (
            ("observe-native", "thread/started",
             lambda frame: f"native {frame['params']['threadId']}"),
            ("observe-activity", "turn/started", lambda frame: "activity active"),
            ("observe-output", "item/agentMessage/delta",
             lambda frame: f"output {frame['params']['delta']}"),
            ("observe-done", "turn/completed",
             lambda frame: f"done {frame['params']['turnId']}"),
        )
        adapter = self.adapter()
        for row_id, method, expect in rows:
            with self.subTest(id=row_id, origin=ORIGIN):
                frame = self.as_frame(by_method[method])
                reading = ""
                if adapter is not None:
                    reading = str(self.call(lambda: adapter.observe(rpc, frame)))
                self.assertEqual(reading, expect(frame))
                self.assertEqual(frame["params"]["threadId"], spec["thread_id"])

    def test_observe_other_thread_id_reads_refused_native(self):
        with self.subTest(id="observe-refused-native", origin=ORIGIN):
            rpc, spec = self.start()
            adapter = self.adapter()
            frame = self.as_frame({
                "method": "item/agentMessage/delta",
                "params": {"threadId": f"other-{spec['thread_id']}", "delta": "nope"},
            })
            reading = ""
            if adapter is not None:
                self.call(lambda: adapter.handshake(rpc))
                reading = str(self.call(lambda: adapter.observe(rpc, frame)))
            self.assertEqual(reading, "refused native")

    def test_observe_permission_is_declined(self):
        with self.subTest(id="observe-permission-decline", origin=ORIGIN):
            rpc, spec = self.start()
            adapter = self.adapter()
            title = f"permit-{spec['thread_id']}"
            frame = self.as_frame({
                "id": "perm-1",
                "method": "permission/request",
                "params": {"threadId": spec["thread_id"], "title": title},
            })
            reading = ""
            if adapter is not None:
                self.call(lambda: adapter.handshake(rpc))
                reading = str(self.call(lambda: adapter.observe(rpc, frame)))
            self.assertEqual(reading, f"permission {title}")
            self.assertIn("decline", self.log_text(spec))


if __name__ == "__main__":
    unittest.main()
