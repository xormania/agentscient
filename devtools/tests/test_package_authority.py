"""Package reductions reject backing calls and retained work before effects."""

import json
import unittest
from unittest.mock import patch

from fixtures.control import ControlFixture

from devtools import role_packages
from devtools.api import API
from devtools.development import Development
from devtools.operations import Operations, execute


class PackageAuthorityTests(unittest.TestCase):
    setUp = ControlFixture.setUp
    client = ControlFixture.client

    def narrowed(self, name, capability):
        catalog = role_packages.catalog()
        for tools in catalog["roles"][name]["mcp"].values():
            if capability in tools:
                tools.remove(capability)
        return patch("devtools.role_packages._catalog", return_value=catalog)

    def rows(self):
        with self.store.connect() as db:
            return {table: [tuple(row) for row in db.execute("SELECT * FROM " + table)]
                    for table in ("member_bindings", "work_orders", "jobs", "operations", "artifacts", "messages")}

    def test_removed_capability_denies_direct_operations_before_queue_or_launch(self):
        operations = Operations(self.store, "coder")
        for action in ("framework_inspect", "framework_generate", "work_check", "work_submit"):
            before = self.rows()
            with self.narrowed("coder", action), patch.object(operations, "launch") as launch:
                with self.subTest(action=action), self.assertRaisesRegex(ValueError, "role package does not permit"):
                    operations.start(action, {})
                launch.assert_not_called()
            self.assertEqual(before, self.rows())

    def test_queued_operation_uses_current_package_before_executing(self):
        operations = Operations(self.store, "coder")
        with patch.object(operations, "launch"):
            receipt = operations.start("work_check", {})
        ident = int(receipt["reference"].split(":")[1])
        with self.narrowed("coder", "work_check"), patch.object(Development, "check") as effect:
            execute(self.state, "coder", ident)
            effect.assert_not_called()
        result = operations.get(ident)
        self.assertEqual("failed", result["state"])
        self.assertIn("role package does not permit work_check", result["error"])
        with self.store.connect() as db:
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM job_workspaces").fetchone()[0])

    def test_framework_services_reject_package_reduction_before_workspace_use(self):
        development = Development(self.store, "coder")
        for action, invoke in (
            ("framework_inspect", lambda: development.inspect("makers")),
            ("framework_generate", lambda: development.generate("make:controller")),
            ("work_check", lambda: development.check()),
        ):
            before = self.rows()
            with self.narrowed("coder", action), patch.object(development.workspaces, "use") as workspace:
                with self.subTest(action=action), self.assertRaisesRegex(ValueError, "role package does not permit"):
                    invoke()
                workspace.assert_not_called()
            self.assertEqual(before, self.rows())

    def test_command_services_reject_removed_capabilities_before_effects(self):
        xo = API(self.state, "xo").commands
        co = API(self.state, "owner").commands
        for name, role, invoke in (
            ("direct", "co", lambda: co.direct("New", "Work", "Done", "Bounded")),
            ("monitor", "co", lambda: co.monitor()),
            ("orchestrate", "xo", lambda: xo.orchestrate([])),
            ("plan_adopt", "xo", lambda: xo.plan_adopt("update:1", [])),
            ("steer", "xo", lambda: xo.steer("pause")),
            ("conclude", "xo", lambda: xo.conclude("Ready")),
        ):
            before = self.rows()
            with self.narrowed(role, name):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "role package does not permit"):
                    invoke()
            self.assertEqual(before, self.rows())

    def test_bootstrap_co_uses_appointed_role_for_package_check(self):
        config = json.loads((self.state / "team.json").read_text())
        config["co"] = "owner"
        (self.state / "team.json").write_text(json.dumps(config))
        api = API(self.state, "owner")
        api.control.unbind("owner")
        # The operator establishes the interface before a work-order binding.
        with patch.object(api.commands, "_config", side_effect=RuntimeError("past package ceiling")):
            with self.assertRaisesRegex(RuntimeError, "past package ceiling"):
                api.commands.direct("New", "Work", "Done", "Bounded")
        before = self.rows()
        with self.narrowed("co", "direct"):
            with self.assertRaisesRegex(ValueError, "role package does not permit"):
                api.commands.direct("New", "Work", "Done", "Bounded")
        self.assertEqual(before, self.rows())


if __name__ == "__main__":
    unittest.main()
