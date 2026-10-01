"""CO launch choices honor the current configured identity before registration."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devtools import console, role_packages
from devtools.api import API
from devtools.control import Control
from devtools.launch import initialize
from devtools.store import Store


class COConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.state = self.root / "state"
        initialize(self.state, self.workspace, ["owner:external"], co="owner", runtime=True)
        self.store = Store(self.state)
        self.packages = copy.deepcopy(role_packages.catalog())
        configured = patch.object(role_packages, "_catalog", return_value=self.packages)
        configured.start()
        self.addCleanup(configured.stop)
        self.policy = json.loads((self.state / "roles.json").read_text())
        for profile in self.policy["profiles"].values():
            profile.update(binary=sys.executable, model="approved", reasoning="low")
        self.write_policy()
        vendors = json.loads((self.state / "vendors.json").read_text())
        for vendor in vendors["vendors"].values():
            vendor["available"] = True
        (self.state / "vendors.json").write_text(json.dumps(vendors))
        self.private = self.root / "private"
        self.private.mkdir()

    def write_policy(self):
        (self.state / "roles.json").write_text(json.dumps(self.policy))

    def bind(self, role):
        api = API(self.state, "owner", operator=True)
        order = api.work.work_order_create(title="CO configuration", objective="Preserve the current interface",
                                           done_when="Launch uses its configured role")["work_order"]["id"]
        api.control.bind("owner", role, order)
        return Control(self.store, "owner").snapshot()

    def launch(self, **arguments):
        # Exercise resolution, registration and retained runtime snapshots without
        # opening a native process or reading the operator's credentials.
        with patch.object(console, "prepare", return_value=(self.private, {}, {})), \
                patch.object(console, "command", return_value=(["fixture"], "fixture-session")), \
                patch.object(console, "relay", return_value=0), patch.object(console, "retain_login"):
            self.assertEqual(0, console.run(self.state, **arguments))
        return self.store.events(kind="session_starting")["events"][-1]["data"]["settings"]

    def test_initial_unbound_co_uses_configured_default_identity(self):
        self.packages["roles"]["interface"] = self.packages["roles"].pop("co")
        self.packages["defaults"]["co"] = "interface"
        self.policy["roles"]["interface"] = self.policy["roles"].pop("co")
        self.write_policy()
        self.assertIsNone(Control(self.store, "owner").snapshot())
        selected = self.launch()
        self.assertEqual("interface", selected["selection"]["role"])
        self.assertEqual("interface", selected["role_package"]["role"])
        self.assertIsNone(Control(self.store, "owner").snapshot())

    def test_existing_bound_co_uses_its_identity_and_profile_preferences(self):
        self.packages["roles"]["liaison"] = copy.deepcopy(self.packages["roles"]["co"])
        self.packages["roles"]["liaison"]["runtime"]["harnesses"] = ["claude"]
        self.policy["roles"]["liaison"] = ["claude"]
        self.write_policy()
        scope = self.bind("liaison")
        selected = self.launch()
        self.assertEqual("co", self.packages["defaults"]["co"])
        self.assertEqual("liaison", selected["selection"]["role"])
        self.assertEqual("liaison", selected["role_package"]["role"])
        self.assertEqual("claude", selected["harness"])
        self.assertEqual(scope, Control(self.store, "owner").snapshot())
        before = self.store.member("owner")
        with patch.object(console, "prepare") as prepare, self.assertRaisesRegex(ValueError, "configured preferences"):
            console.run(self.state, profile="codex")
        prepare.assert_not_called()
        self.assertEqual(before, self.store.member("owner"))

    def test_model_and_reasoning_overrides_are_checked_before_session_registration(self):
        runtime = self.packages["roles"]["co"]["runtime"]
        runtime["model"] = {"default": None, "allowed": ["approved", "alternate"]}
        runtime["reasoning"] = {"default": None, "allowed": ["low", "medium"]}
        selected = self.launch(model="alternate", reasoning="medium")
        self.assertEqual(("alternate", "medium"), (selected["model"], selected["reasoning"]))
        self.assertEqual("approved", json.loads((self.state / "roles.json").read_text())["profiles"]["codex"]["model"])
        before = self.store.member("owner")
        starts = self.store.events(kind="session_starting")["events"]
        for arguments in ({"model": "forbidden"}, {"reasoning": "high"}):
            with self.subTest(arguments=arguments), patch.object(console, "prepare") as prepare, \
                    self.assertRaisesRegex(ValueError, "explicit permitted"):
                console.run(self.state, **arguments)
            prepare.assert_not_called()
            self.assertEqual(before, self.store.member("owner"))
            self.assertEqual(starts, self.store.events(kind="session_starting")["events"])

    def test_non_co_binding_is_rejected_before_runtime_resolution_or_registration(self):
        # Trusted repair can bind this appointed member differently; launching the
        # CO must not relabel that live responsibility as the default interface.
        self.bind("co")
        with self.store.connect() as db:
            db.execute("UPDATE member_bindings SET role='coder' WHERE member='owner'")
        before = self.store.member("owner")
        with patch.object(console, "resolve") as resolve, patch.object(console, "prepare") as prepare, \
                self.assertRaisesRegex(ValueError, "current binding must use the CO behavior"):
            console.run(self.state)
        resolve.assert_not_called()
        prepare.assert_not_called()
        self.assertEqual(before, self.store.member("owner"))
        self.assertEqual([], self.store.events(kind="session_starting")["events"])

    def test_binding_changes_during_resolution_prevent_session_registration(self):
        self.packages["roles"]["liaison"] = copy.deepcopy(self.packages["roles"]["co"])
        self.bind("co")
        resolve = console.resolve
        # Check the whole snapshot: trusted rebinding, a newer direction, and a
        # pause each invalidate the runtime decision, even with the same harness.
        for mutation in ("role='liaison'", "revision=revision+1", "paused=1"):
            with self.subTest(mutation=mutation):
                with self.store.connect() as db:
                    db.execute("UPDATE member_bindings SET role='co',paused=0 WHERE member='owner'")
                before = self.store.member("owner")

                def rebind(*args, **kwargs):
                    config = resolve(*args, **kwargs)
                    with self.store.connect() as db:
                        db.execute("UPDATE member_bindings SET " + mutation + " WHERE member='owner'")
                    return config

                with patch.object(console, "resolve", side_effect=rebind), patch.object(console, "prepare") as prepare, \
                        self.assertRaisesRegex(ValueError, "Work binding changed"):
                    console.run(self.state)
                prepare.assert_not_called()
                self.assertEqual(before, self.store.member("owner"))
                self.assertEqual([], self.store.events(kind="session_starting")["events"])

    def test_initial_binding_created_during_resolution_prevents_session_registration(self):
        self.assertIsNone(Control(self.store, "owner").snapshot())
        resolve = console.resolve
        bound = []

        def bind(*args, **kwargs):
            config = resolve(*args, **kwargs)
            bound.append(self.bind("co"))
            return config

        with patch.object(console, "resolve", side_effect=bind), patch.object(console, "prepare") as prepare, \
                self.assertRaisesRegex(ValueError, "Work binding changed"):
            console.run(self.state)
        prepare.assert_not_called()
        self.assertEqual(bound[0], Control(self.store, "owner").snapshot())
        self.assertIsNone(self.store.member("owner")["generation"])
        self.assertEqual([], self.store.events(kind="session_starting")["events"])


if __name__ == "__main__":
    unittest.main()
