import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from support import ENTRY, Client, initialize, until

from devtools.api import API
from devtools.profiles import permitted
from devtools.store import Store
from devtools.telemetry import Trace


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.directory = root / "state"
        initialize(self.directory, self.workspace, ["alpha:external", "beta:external"])
        self.store = Store(self.directory)

    def client(self, member, channel=False):
        client = Client(self.directory, member, channel, operator=True)
        self.addCleanup(client.close)
        return client

    def test_stdio_discovery_concurrent_delivery_ack_and_restart(self):
        alpha, beta = self.client("alpha"), self.client("beta")
        self.assertEqual(3, len(alpha.call("tools/list")["tools"]))
        names, offset = [], 0
        while offset is not None:
            page = alpha.tool("capability_search", {"offset": offset})
            names.extend(row["name"] for row in page["capabilities"])
            offset = page["next_offset"]
        self.assertIn("message_send", names)
        self.assertEqual(
            "object", alpha.tool("capability_describe", {"capability": "message_send"})["inputSchema"]["type"]
        )
        waiting = beta.begin(
            "tools/call",
            {"name": "capability_invoke", "arguments": {"capability": "message_wait", "arguments": {"timeout": 3}}},
        )
        self.assertEqual(2, len(beta.invoke("peers")["members"]))
        message = alpha.invoke("message_send", to="beta", body="Continue while we talk", key="one")
        self.assertEqual(
            message["id"], alpha.invoke("message_send", to="beta", body="Continue while we talk", key="one")["id"]
        )
        with self.assertRaises(ValueError):
            alpha.invoke("message_send", to="beta", body="different", key="one")
        held = json.loads(beta.finish(waiting)["content"][0]["text"])
        self.assertEqual(message["id"], held["messages"][0]["id"])
        with self.assertRaises(ValueError):
            alpha.invoke("message_ack", message=message["id"])
        beta.invoke("message_ack", message=message["id"])
        beta.close()
        restarted = self.client("beta")
        self.assertTrue(restarted.invoke("message_inbox")["messages"][0]["acknowledged"])
        events = alpha.invoke("telemetry_events", kind="message_acknowledged")["events"]
        self.assertEqual(1, len(events))
        self.assertFalse(alpha.invoke("telemetry_usage")["observed"])
        with self.assertRaises(ValueError):
            alpha.invoke("message_ack", message=True)
        with self.assertRaises(ValueError):
            alpha.invoke("peers", command="echo forbidden")

    def test_claude_notifications_wait_for_native_channel_registration(self):
        generation = self.store.begin_session("beta", os.getpid())
        alpha, beta = self.client("alpha"), self.client("beta", channel=True)
        message = alpha.invoke("message_send", to="beta", body="pending before ready", key="channel")
        time.sleep(0.2)
        self.assertFalse(beta.notifications)
        self.assertEqual("queued", self.store.inbox("beta")["messages"][0]["delivery"])
        self.store.session("beta", generation=generation, state="idle")
        packet = until(lambda: beta.notifications and beta.notifications[0])
        self.assertEqual("notifications/claude/channel", packet["method"])
        self.assertEqual(str(message["id"]), packet["params"]["meta"]["message_id"])
        delivered = until(
            lambda: row if (row := self.store.inbox("beta")["messages"][0])["delivery"] == "submitted" else None
        )
        self.assertIsNone(delivered["acknowledged"])
        beta.invoke("message_ack", message=message["id"])

    def test_transport_crash_is_uncertain_and_retry_is_explicit(self):
        message = self.store.send("alpha", "beta", "durable", key="crash")
        attempt = self.store.take_delivery("beta")
        self.store.begin_session("beta", os.getpid())
        self.assertEqual("uncertain", self.store.inbox("beta")["messages"][0]["delivery"])
        self.assertIsNone(self.store.take_delivery("beta"))
        with self.assertRaises(ValueError):
            self.store.delivered("beta", message["id"], attempt["attempt"])
        self.store.retry("alpha", message["id"])
        self.assertEqual(message["id"], self.store.take_delivery("beta")["id"])
        with self.assertRaises(ValueError):
            self.store.begin_session("beta", os.getpid())

    def test_native_tool_boundary_and_hook_fail_closed(self):
        for harness in ("codex", "claude", "grok"):
            for tool in ("Bash", "exec_command", "read_file", "apply_patch", "unknown", {}, None):
                self.assertFalse(permitted(harness, tool, {}))
        self.assertTrue(permitted("codex", "work_context", {}))
        self.assertTrue(permitted("claude", "mcp__agentscient_dev__work_context", {}))
        self.assertTrue(
            permitted("grok", "use_tool", {"tool_name": "agentscient_dev__work_context", "tool_input": {}})
        )
        self.assertFalse(permitted("grok", "use_tool", {"tool_name": {}, "tool_input": {}}))
        result = subprocess.run(
            [
                sys.executable,
                str(ENTRY),
                "hook",
                "--state",
                str(self.directory),
                "--member",
                "beta",
                "--harness",
                "claude",
            ],
            input="{bad",
            text=True,
            capture_output=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertEqual("deny", json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"])

    def test_usage_is_measured_and_trace_redacts_credentials(self):
        with patch.dict(os.environ, {"TEST_API_KEY": "private-value-for-test"}):
            trace = Trace(self.directory, "alpha")
            trace.record(
                "native",
                {
                    "authorization": "private-value-for-test",
                    "text": "Bearer abcdefghijkl",
                    "usage": {"inputTokens": 123, "outputTokens": 17},
                },
            )
            trace.close()
        content = trace.path.read_text()
        self.assertNotIn("private-value-for-test", content)
        self.assertNotIn("abcdefghijkl", content)
        self.assertEqual(123, json.loads(content)["data"]["usage"]["inputTokens"])
        self.store.event("alpha", "native_usage", observation={"inputTokens": 123})
        result = API(self.directory, "beta").invoke("telemetry_usage", {"actor": "alpha"})
        self.assertTrue(result["observed"])
        self.assertEqual(123, result["events"][0]["data"]["observation"]["inputTokens"])
