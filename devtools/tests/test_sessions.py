import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import ENTRY, Client, retain_native
from test_commands import GOAL, responsibility

from devtools.api import API
from devtools.control import ROLES, Control
from devtools.launch import configuration, initialize
from devtools.profiles import hook, prepare, retain_login
from devtools.runtime import resolve
from devtools.sessions import Lease
from devtools.store import Store


class SessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state, self.workspace = self.root / "state", self.root / "workspace"
        self.workspace.mkdir()
        initialize(self.state, self.workspace, ["owner:external"], co="owner", runtime=True)
        policy = json.loads((self.state / "roles.json").read_text())
        for row in policy["profiles"].values():
            row.update(binary="/bin/true", model="selected-model", reasoning="high")
        (self.state / "roles.json").write_text(json.dumps(policy))
        vendors = json.loads((self.state / "vendors.json").read_text())
        for row in vendors["vendors"].values():
            row["available"] = True
        (self.state / "vendors.json").write_text(json.dumps(vendors))
        self.store, self.co = Store(self.state), API(self.state, "owner")

    def bind(self):
        self.co.call("direct", GOAL)
        with self.store.connect() as db:
            member = db.execute("SELECT member FROM member_bindings WHERE role='xo'").fetchone()[0]
            db.execute("UPDATE member_bindings SET launch_pending=0")
        return API(self.state, member)

    def test_generation_fences_existing_and_reconnecting_clients_and_hooks(self):
        self.bind()
        self.co.call("work_report", {"text": "Preserve this decision", "kind": "progress"})
        old = Client(self.state, "owner")
        self.addCleanup(old.close)
        first = self.store.begin_session("owner", os.getpid())
        with self.assertRaisesRegex(ValueError, "replaced"):
            old.tool("direct", GOAL)
        current = Client(self.state, "owner", generation=first)
        self.addCleanup(current.close)
        self.assertIn("Preserve this decision", json.dumps(current.tool("onboard", {})))
        with Lease(self.store, "owner", first).hold():
            with self.assertRaisesRegex(ValueError, "in flight"):
                self.store.begin_session("owner", os.getpid())
        self.store.session("owner", generation=first, state="stopped", desired="stopped", pid=None)
        second = self.store.begin_session("owner", os.getpid())
        self.assertNotEqual(first, second)
        with self.assertRaisesRegex(ValueError, "replaced"):
            current.tool("work_report", {"text": "Stale decision", "kind": "progress"})
        with self.assertRaisesRegex(ValueError, "replaced"):
            Client(self.state, "owner", generation=first)
        with self.assertRaisesRegex(ValueError, "replaced"):
            hook(self.state, "owner", "claude", {"hook_event_name": "Stop"}, first)
        replacement = Client(self.state, "owner", generation=second)
        self.addCleanup(replacement.close)
        context = replacement.tool("work_context", {})
        self.assertIn("Preserve this decision", json.dumps(context))
        self.assertNotIn("Stale decision", json.dumps(context))

    def test_all_roles_keep_bindings_on_replacement_and_use_current_vendor_policy(self):
        xo = self.bind()
        roles = [role for role in ROLES if role not in {"co", "xo"}]
        for role in roles:
            xo.call("orchestrate", {"work": [responsibility(("coder" if role == "audit" else role) + " work", role)]})
        before = {row["name"]: Control(self.store, row["name"]).snapshot() for row in self.store.members()}
        vendor_path = self.state / "vendors.json"
        vendors = json.loads(vendor_path.read_text())
        vendors["vendors"]["openai"]["available"] = False
        vendor_path.write_text(json.dumps(vendors))
        with self.assertRaisesRegex(ValueError, "No runtime available"):
            resolve(self.state, "co", profile="codex")
        for role in roles:
            xo.call(
                "steer",
                {
                    "action": "replace",
                    "work": ("coder" if role == "audit" else role) + " work",
                    "role": role,
                    "direction": "Recover on available vendor",
                },
            )
        self.co.call("restart_xo", {"reason": "Recover coordination on available vendor"})
        for member, original in before.items():
            current = Control(self.store, member).snapshot()
            for key in ("role", "work_order", "job", "reports_to"):
                self.assertEqual(original[key], current[key])
            if member != "owner":
                self.assertEqual(1, current["launch_pending"])
                self.assertEqual("claude", configuration(self.state, member)["harness"])
        with self.assertRaisesRegex(ValueError, "not available"):
            xo.call("restart_xo", {"reason": "Cannot replace my own superior"})

    def test_external_reconnect_after_native_exit_preserves_context_and_generation_fences(self):
        self.bind()
        self.co.call("work_report", {"text": "Decision before handover", "kind": "progress"})
        first = self.store.begin_session("owner", os.getpid())
        old_native = Client(self.state, "owner", generation=first)
        self.addCleanup(old_native.close)
        old_unversioned = Client(self.state, "owner")
        self.addCleanup(old_unversioned.close)
        self.store.session("owner", generation=first, state="stopped", desired="stopped", pid=None)
        for client in (old_native, old_unversioned):
            with self.assertRaisesRegex(ValueError, "stopped or been replaced"):
                client.tool("onboard", {})
        with self.assertRaisesRegex(ValueError, "stopped or been replaced"):
            Client(self.state, "owner", generation=first)

        external = Client(self.state, "owner")
        self.addCleanup(external.close)
        self.assertIn("Decision before handover", json.dumps(external.tool("onboard", {})))
        external.tool("work_report", {"text": "Decision from external CO", "kind": "progress"})
        second = self.store.begin_session("owner", os.getpid())
        with self.assertRaisesRegex(ValueError, "stopped or been replaced"):
            external.tool("work_report", {"text": "Stale external decision", "kind": "progress"})
        current = Client(self.state, "owner", generation=second)
        self.addCleanup(current.close)
        context = json.dumps(current.tool("onboard", {}))
        self.assertIn("Decision from external CO", context)
        self.assertNotIn("Stale external decision", context)
        rows = [json.loads(line) for line in (self.state / "telemetry/owner.jsonl").read_text().splitlines()]
        frames = [row for row in rows if row["component"] == "mcp" and row["kind"] in {"mcp_in", "mcp_out"}]
        self.assertTrue(frames)
        self.assertTrue(all("connection_generation" in row["context"] for row in frames))

    def test_stopping_generation_cannot_claim_the_replacement_recovery_direction(self):
        xo = self.bind()
        first = self.store.begin_session(xo.member, os.getpid())
        original = self.store.take_delivery(xo.member, scoped=True, generation=first)
        self.assertIsNotNone(original)
        self.store.acknowledge(xo.member, original["id"])
        self.co.call("restart_xo", {"reason": "Switch to the available vendor"})
        # The old delivery loop may already have observed desired=running before
        # restart_xo commits the stop and queues the replacement's direction.
        self.assertIsNone(self.store.take_delivery(xo.member, scoped=True, generation=first))
        self.store.session(xo.member, generation=first, state="stopped", pid=None)
        second = self.store.begin_session(xo.member, os.getpid())
        self.assertIsNone(self.store.take_delivery(xo.member, scoped=True, generation=first))
        recovery = self.store.take_delivery(xo.member, scoped=True, generation=second)
        self.assertIn("Recover your existing work and team", recovery["body"])
        self.assertIn("Switch to the available vendor", recovery["body"])

    def test_private_generation_profiles_do_not_rebind_old_native_clients(self):
        self.bind()
        first = self.store.begin_session("owner", os.getpid())
        with patch.dict(os.environ, {"CODEX_HOME": str(self.root / "login")}):
            directory, _, server = prepare(self.state, "owner", "codex")
            self.store.session("owner", state="stopped", desired="stopped", pid=None)
            second = self.store.begin_session("owner", os.getpid())
            next_directory, _, next_server = prepare(self.state, "owner", "codex")
        self.assertNotEqual(directory, next_directory)
        self.assertIn(first, server["args"])
        self.assertIn(second, next_server["args"])
        self.assertIn(first, (directory / "hooks.json").read_text())

    def test_private_login_refresh_survives_handover_and_changed_operator_login_wins(self):
        original = self.root / "login"
        original.mkdir()
        source = original / "auth.json"
        source.write_text('{"refresh_token":"original-login"}')
        with patch.dict(os.environ, {"CODEX_HOME": str(original)}):
            first = self.store.begin_session("owner", os.getpid())
            private, _, _ = prepare(self.state, "owner", "codex")
            (private / "auth.json").write_text('{"refresh_token":"refreshed-private-login"}')
            retain_login(self.state, "owner", "codex", first)
            self.store.session("owner", state="stopped", desired="stopped", pid=None)
            self.store.begin_session("owner", os.getpid())
            next_private, _, _ = prepare(self.state, "owner", "codex")
            self.assertIn("refreshed-private-login", (next_private / "auth.json").read_text())
            self.assertIn("original-login", source.read_text())
            source.write_text('{"refresh_token":"new-operator-login"}')
            current, _, _ = prepare(self.state, "owner", "codex")
            self.assertIn("new-operator-login", (current / "auth.json").read_text())

    def test_native_co_launch_and_cross_harness_handover_recover_context_and_trace_output(self):
        self.bind()
        self.co.call("work_report", {"text": "Preserve this decision", "kind": "progress"})
        fixture = Path(__file__).with_name("co_fixture.py")
        fixture.chmod(0o755)
        policy = json.loads((self.state / "roles.json").read_text())
        for row in policy["profiles"].values():
            row["binary"] = str(fixture)
        (self.state / "roles.json").write_text(json.dumps(policy))
        home = self.root / "home"
        home.mkdir()
        env = {
            **os.environ,
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "GROK_HOME": str(home / ".grok"),
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "TEST_API_KEY": "test-secret-split-value",
        }
        generations = []
        for harness in ("codex", "claude", "grok"):
            result = subprocess.run(
                [sys.executable, str(ENTRY), "co", "--state", str(self.state), "--profile", harness],
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("Live CO response " + harness, result.stdout)
            generations.append(self.store.member("owner")["generation"])
            self.assertEqual("stopped", self.store.member("owner")["state"])
            self.assertEqual("external", self.store.member("owner")["harness"])
        self.assertEqual(3, len(set(generations)))
        rows = [json.loads(line) for line in (self.state / "telemetry/owner.jsonl").read_text().splitlines()]
        output = [row for row in rows if row["kind"] == "terminal_output"]
        self.assertEqual({"codex", "claude", "grok"}, {row["context"]["harness"] for row in output})
        self.assertNotIn(env["TEST_API_KEY"], json.dumps(rows))
        self.assertIn("[REDACTED]", json.dumps(output))
        self.assertIn("CO recovered using grok", json.dumps(self.co.call("work_context", {})))
        retain_native(self.state, "co-handover")
