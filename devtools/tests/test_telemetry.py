import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import Client, until

from devtools.launch import initialize
from devtools.profiles import hook, prepare
from devtools.store import Store
from devtools.telemetry import Trace, Transcript, context, observed, requested


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        workspace = self.root / "workspace"
        workspace.mkdir()
        initialize(self.state, workspace, ["owner:external", "worker:claude"])
        self.store = Store(self.state)

    def test_mcp_wire_capture_correlates_live_channel_and_acknowledgement(self):
        generation = self.store.begin_session("worker", os.getpid())
        self.store.session("worker", generation=generation, state="idle", native_id="native-1")
        client = Client(self.state, "worker", channel=True, operator=True)
        try:
            message = self.store.send("owner", "worker", "Live direction", key="live")
            until(lambda: client.notifications)
            client.invoke("message_ack", message=message["id"])
        finally:
            client.close()
        records = [json.loads(line) for line in (self.state / "telemetry/worker.jsonl").read_text().splitlines()]
        channel = next(r for r in records if r["data"].get("method") == "notifications/claude/channel")
        self.assertIn("Live direction", channel["data"]["params"]["content"])
        self.assertEqual(generation, channel["context"]["generation"])
        self.assertEqual("native-1", channel["context"]["native_id"])
        self.assertTrue(any(r["kind"] == "mcp_in" and r["data"].get("method") == "tools/call" for r in records))
        events = self.store.events(actor="worker", limit=100)["events"]
        delivering = next(r for r in events if r["kind"] == "message_delivering")
        submitted = next(r for r in events if r["kind"] == "message_submitted")
        self.assertEqual(delivering["data"]["attempt"], submitted["data"]["attempt"])
        self.assertTrue(any(r["kind"] == "message_acknowledged" for r in events))

    def test_requested_inherited_and_observed_runtime_are_distinct(self):
        home = self.root / "codex"
        home.mkdir()
        (home / "config.toml").write_text('model="inherited-model"\nmodel_reasoning_effort="high"\n')
        with patch.dict(os.environ, {"CODEX_HOME": str(home)}):
            private, _, _ = prepare(self.state, "owner", "codex")
            requested(self.store, "owner", {"harness": "codex", "model": "requested-model"}, private)
        self.assertEqual({}, observed(self.store, "owner", "empty", {"thread": {"id": "one"}}))
        observed(self.store, "owner", "thread/start", {"model": "actual-model", "reasoningEffort": "medium"})
        events = self.store.events(actor="owner")["events"]
        configured = next(r["data"] for r in events if r["kind"] == "runtime_requested")
        actual = next(r["data"] for r in events if r["kind"] == "runtime_observed")
        self.assertEqual("requested-model", configured["settings"]["model"])
        self.assertEqual("inherited", configured["sources"]["reasoning"])
        self.assertEqual("high", configured["settings"]["reasoning"])
        self.assertIsNone(configured["settings"]["vendor"])
        self.assertEqual("actual-model", actual["settings"]["model"])
        self.assertNotIn("vendor", actual["settings"])

    def test_claude_transcript_tail_handles_partial_writes_and_redacts_nested_content(self):
        self.store.begin_session("worker", os.getpid())
        native = self.root / ".claude"
        transcript = native / "projects/project/session-one.jsonl"
        transcript.parent.mkdir(parents=True)
        trace = Trace(self.state, "worker", context=lambda: context(self.store, "worker"))
        self.addCleanup(trace.close)
        reader = Transcript(self.store, "worker", trace)
        with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(native), "TEST_API_KEY": "test-secret-value"}):
            hook(
                self.state,
                "worker",
                "claude",
                {
                    "hook_event_name": "SessionStart",
                    "session_id": "session-one",
                    "model": "reported-model",
                    "transcript_path": str(transcript),
                },
            )
            entry = {
                "message": {
                    "model": "reported-model",
                    "id": "msg-1",
                    "usage": {"input_tokens": 17},
                    "content": [{"text": "Tool result: test-secret-value"}, {"text": '{"password":"must-disappear"}'}],
                }
            }
            encoded = json.dumps(entry)
            transcript.write_text(encoded[:20])
            reader.poll()
            self.assertFalse(self.store.events(kind="native_usage")["events"])
            with transcript.open("a") as stream:
                stream.write(encoded[20:] + "\n")
            reader.poll()
            reader.poll()
            self.store.event("worker", "error", authorization="must-disappear", text="test-secret-value")
        usage = self.store.events(kind="native_usage")["events"]
        self.assertEqual(1, len(usage))
        self.assertEqual(17, usage[0]["data"]["observation"]["input_tokens"])
        retained = trace.path.read_text() + json.dumps(self.store.events(limit=100))
        self.assertNotIn("test-secret-value", retained)
        self.assertNotIn("must-disappear", retained)
        self.assertIn("reported-model", retained)
        outside = self.root / "session-one.jsonl"
        outside.write_text('{"message":{"content":"unrelated-private-file"}}\n')
        hook(
            self.state,
            "worker",
            "claude",
            {"hook_event_name": "Stop", "session_id": "session-one", "transcript_path": str(outside)},
        )
        reader.poll()
        self.assertNotIn("unrelated-private-file", trace.path.read_text())
        self.assertTrue(self.store.events(kind="transcript_rejected")["events"])
