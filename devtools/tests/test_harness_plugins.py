"""A registered fourth harness traverses real configuration and lifecycle dispatch."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devtools import adapters, role_packages
from devtools.api import API
from devtools.harnesses import get
from devtools.launch import agent, configuration, initialize, team_config
from devtools.profiles import permitted
from devtools.store import Store


class HarnessPluginTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.state = self.root / "state"
        self.manifest = self.root / "adapters.json"
        document = json.loads(adapters.MANIFEST.read_text())
        document["adapters"]["harness"]["fixture"] = "devtools.tests.harness_plugin_fixture:FixtureHarness"
        self.manifest.write_text(json.dumps(document))
        registry = patch.object(adapters, "MANIFEST", self.manifest)
        registry.start()
        self.addCleanup(registry.stop)
        packages = copy.deepcopy(role_packages.catalog())
        packages["roles"]["coder"]["runtime"]["harnesses"].append("fixture")
        catalogue = patch.object(role_packages, "_catalog", return_value=packages)
        catalogue.start()
        self.addCleanup(catalogue.stop)
        initialize(self.state, self.workspace, ["owner:external", "worker:fixture"])
        team = json.loads((self.state / "team.json").read_text())
        team["members"][1].update(binary=sys.executable, model="fixture-model")
        (self.state / "team.json").write_text(json.dumps(team))
        self.store = Store(self.state)
        operator = API(self.state, "owner", operator=True)
        order = operator.work.work_order_create(title="Adapter fixture", objective="Dispatch selected harness",
                                                done_when="Configured adapter runs")
        operator.control.bind("owner", "co", order["work_order"]["id"])
        operator.control.bind("worker", "coder", order["work_order"]["id"], reports_to="owner")

    def test_fourth_registered_harness_uses_its_own_profile_permission_console_and_session(self):
        selected = configuration(self.state, "worker")
        self.assertEqual("fixture", selected["harness"])
        with patch("devtools.launch.signal.signal"), patch("devtools.processes.register"):
            agent(self.state, "worker")
        current = self.store.member("worker")
        self.assertEqual("stopped", current["state"])
        self.assertEqual("fixture-session", current["native_id"])
        rows = self.store.events(actor="worker", kind="fixture_harness_ran")["events"]
        self.assertEqual(1, len(rows))
        self.assertEqual({"harness": "fixture"}, rows[0]["data"]["profile"])
        self.assertEqual({"fixture_allowed": True}, rows[0]["data"]["permission"])
        self.assertEqual("fixture-model", rows[0]["data"]["argv"][-1])
        self.assertEqual(1, len(self.store.events(actor="worker", kind="fixture_login_retained")["events"]))
        self.assertFalse(permitted("fixture", "shell", {"command": "should never run"}))

    def test_unregistered_or_incomplete_adapter_never_uses_a_builtin_fallback(self):
        team = json.loads((self.state / "team.json").read_text())
        team["members"][1]["harness"] = "unregistered"
        (self.state / "team.json").write_text(json.dumps(team))
        with self.assertRaisesRegex(ValueError, "Invalid"):
            team_config(self.state)
        self.assertFalse(permitted("unregistered", "search_tool", {}))
        document = json.loads(self.manifest.read_text())
        document["adapters"]["harness"]["incomplete"] = "types:SimpleNamespace"
        self.manifest.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError, "Harness adapters"):
            get("incomplete")
