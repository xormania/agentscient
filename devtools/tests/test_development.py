import json
import sys
import unittest
from unittest.mock import patch

import test_workspaces
from support import Client, until

from devtools.api import API
from devtools.development import Development
from devtools.operations import Operations, execute
from devtools.workspaces import git


class DevelopmentTests(unittest.TestCase):
    setUp = test_workspaces.WorkspaceTests.setUp
    prepared = test_workspaces.WorkspaceTests.prepared

    def configure(self, checks=None):
        root = self.prepared()
        (root / "composer.json").write_text("{}")
        (root / "composer.lock").write_text("{}")
        (root / "vendor").mkdir(exist_ok=True)
        (root / "vendor/autoload.php").write_text("<?php")
        import hashlib

        (root / "vendor/.agentscient-dependencies").write_text(hashlib.sha256(b"{}{}").hexdigest())
        config = json.loads((self.state / "team.json").read_text())
        config["project"]["development"] = {
            "checks": checks or {"fixture": [sys.executable, "-c", "print('measured')"]}
        }
        (self.state / "team.json").write_text(json.dumps(config))
        self.api = API(self.state, "coder")
        return root

    def test_checks_complete_after_client_disconnect_and_route_evidence(self):
        self.configure({"fixture": [sys.executable, "-c", "import time; time.sleep(0.7); print('measured')"]})
        client = Client(self.state, "coder")
        receipt = client.tool("work_check", {})
        self.assertIn(receipt["state"], {"queued", "running"})
        client.close()
        result = until(
            lambda: next((r for r in self.api.operations.inspect()["operations"] if r["state"] == "completed"), None)
        )
        self.assertTrue(result["result"]["passed"])
        evidence = self.api.call("work_context", {"reference": result["result"]["checks"][0]["evidence"]})
        self.assertIn("measured", evidence["content"])
        for member in ("coder", "xo"):
            messages = self.store.inbox(member)["messages"]
            self.assertTrue(any('"state":"completed"' in row["body"] for row in messages))

    def test_active_retry_reuses_operation_and_worker_rechecks_binding(self):
        self.configure()
        with patch.object(Operations, "launch"):
            first = self.api.call("work_check", {})
            second = self.api.call("work_check", {})
            self.assertEqual(first["reference"], second["reference"])
            with self.assertRaisesRegex(ValueError, "already using"):
                self.api.call("framework_inspect", {"kind": "mate"})
            API(self.state, "xo").call("steer", {"action": "pause", "work": "Feature"})
            execute(self.state, "coder", int(first["reference"].split(":")[1]))
        # Even diagnostic/check calls must not start new execution after pause.
        value = self.api.operations.inspect()["operations"][0]
        self.assertEqual("failed", value["state"])
        self.assertIn("paused", value["error"])

    def test_dead_worker_is_uncertain_without_automatic_replay(self):
        self.configure()
        with patch.object(Operations, "launch"):
            receipt = self.api.call("work_check", {})
        ident = int(receipt["reference"].split(":")[1])
        with self.store.connect() as db:
            db.execute("UPDATE operations SET state='running' WHERE id=?", (ident,))
        self.api.operations.tick()
        self.assertEqual("uncertain", self.api.operations.get(ident)["state"])

    def test_maker_metadata_controls_arguments_without_shell_or_global_options(self):
        metadata = {
            "name": "make:command",
            "definition": {
                "arguments": {"name": {"is_required": True, "is_array": False}},
                "options": {
                    "option": {"accept_value": True, "is_multiple": True},
                    "env": {"accept_value": True, "is_multiple": False},
                },
            },
        }
        payload = "name; $(touch marker)"
        argv = Development.maker_argv(metadata, {"name": payload}, {"option": ["one:bool", "two:string"]})
        self.assertEqual(payload, argv[-1])
        self.assertEqual("--", argv[-2])
        self.assertIn("--option=one:bool", argv)
        with self.assertRaisesRegex(ValueError, "managed"):
            Development.maker_argv(metadata, {"name": "Valid"}, {"env": "prod"})
        with self.assertRaisesRegex(ValueError, "metadata"):
            Development.maker_argv(metadata, {"name": "Valid", "command": "shell"}, {})

    def test_failed_checks_preserve_checkpoint_and_prevent_publication(self):
        root = self.configure({"broken": [sys.executable, "-c", "raise SystemExit(2)"]})
        (root / ".gitignore").write_text("/vendor/\n")
        git(root, "add", ".gitignore")
        git(root, "commit", "-m", "Fixture ignores")
        with patch("devtools.github.GitHub") as provider:
            value = self.api.workspaces.submit("Measured validation failure")
        self.assertEqual("needs_attention", value["state"])
        self.assertFalse(value["validation"]["passed"])
        provider.assert_not_called()
        self.assertTrue(value["checkpoint"].startswith("checkpoint:"))

    def test_test_writer_cannot_use_non_test_maker(self):
        self.configure()
        scope = self.api.control.snapshot()
        self.api.control.bind("coder", "test_writer", scope["work_order"], scope["job"], "xo")
        with self.assertRaisesRegex(ValueError, "make:test"):
            Development(self.store, "coder").generate("make:command", {"name": "app:wrong"})


if __name__ == "__main__":
    unittest.main()
