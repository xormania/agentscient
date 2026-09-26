import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from support import Client, until

from devtools.launch import initialize
from devtools.store import Store


class NativeProtocolTests(unittest.TestCase):
    def test_live_messages_during_unfinished_work_keep_native_identity(self):
        for harness in ("codex", "grok"):
            with self.subTest(harness=harness), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                workspace = root / "workspace"
                workspace.mkdir()
                state = root / "state"
                home = root / "login-home"
                home.mkdir()
                initialize(state, workspace, ["owner:external", "worker:" + harness])
                fixture = Path(__file__).with_name("native_fixture.py")
                fixture.chmod(0o755)
                config = json.loads((state / "team.json").read_text())
                config["members"][1]["binary"] = str(fixture)
                (state / "team.json").write_text(json.dumps(config))
                store = Store(state)
                env = {
                    **os.environ,
                    "HOME": str(home),
                    "CODEX_HOME": str(home / "codex"),
                    "GROK_HOME": str(home / "grok"),
                }
                client = Client(state, "owner", env=env)
                try:
                    started = client.invoke("session_start", member="worker")
                    self.assertEqual("running", started["requested"])
                    until(lambda: store.member("worker")["state"] == "idle")
                    original_id = store.member("worker")["native_id"]
                    self.assertTrue(client.invoke("session_start", member="worker")["already_running"])
                    first = client.invoke(
                        "message_send", to="worker", body="Keep working while a tool is held", key="first"
                    )
                    until(lambda: store.inbox("worker")["messages"][0]["acknowledged"])
                    until(
                        lambda: (
                            store.events(kind="operation_started")["events"]
                            and any(
                                row["data"]["capability"] == "message_wait"
                                for row in store.events(kind="operation_started")["events"]
                            )
                        )
                    )
                    second = client.invoke(
                        "message_send", to="worker", body="New message during unfinished work", key="second"
                    )
                    until(lambda: store.inbox("worker")["messages"][1]["acknowledged"], timeout=4)
                    rows = store.inbox("worker")["messages"]
                    self.assertEqual([first["id"], second["id"]], [row["id"] for row in rows])
                    self.assertEqual(original_id, store.member("worker")["native_id"])
                    self.assertEqual("active", store.member("worker")["state"])
                    submissions = store.events(kind="message_submitted")["events"]
                    until(lambda: len(store.events(kind="message_submitted")["events"]) == 2)
                    if harness == "grok":
                        submissions = store.events(kind="message_submitted")["events"]
                        self.assertEqual("grok/_x.ai/interject", submissions[-1]["data"]["transport"])
                    else:
                        self.assertTrue(store.events(kind="native_usage")["events"])
                except Exception:
                    log = state / "logs/worker.log"
                    if log.exists():
                        print(log.read_text(), file=sys.stderr)
                    raise
                finally:
                    try:
                        client.invoke("session_stop", member="worker")
                        until(lambda: store.member("worker")["state"] in {"stopped", "failed"}, timeout=8)
                    finally:
                        client.close()
                self.assertEqual("stopped", store.member("worker")["state"])
