import json
import unittest
from pathlib import Path
from unittest.mock import patch

import test_workspaces
from support import Client
from test_commands import responsibility

from devtools.advice import Advice
from devtools.api import API
from devtools.development import Development
from devtools.operations import Operations
from devtools.runtime import defaults, load, resolve
from devtools.serena_provider import Serena
from devtools.store import SCHEMA_VERSION, Store


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        test_workspaces.WorkspaceTests.setUp(self)
        team = json.loads((self.state / "team.json").read_text())
        team["members"] += [{"name": f"slot{i}", "harness": "external", "workspace": str(self.checkout)} for i in range(6)]
        team["project"].update(serena={"image": "agentscient-serena:fixture"}, development={})
        (self.state / "team.json").write_text(json.dumps(team))
        self.xo = API(self.state, "xo")
        self.xo.call("orchestrate", {"work": [responsibility("Coordinate", "nco")]})
        self.nco = self.by_role("nco")

    def by_role(self, role):
        with self.store.connect() as db:
            name = db.execute("SELECT member FROM member_bindings WHERE role=?", (role,)).fetchone()[0]
        return API(self.state, name)

    def plan(self, accept=True):
        self.nco.call("orchestrate", {"work": [responsibility("Plan", "planner")]})
        planner = self.by_role("planner")
        result = planner.call("work_report", {"kind": "result", "text": "Plan ready", "evidence": {
            "name": "plan.md", "content": "Use the maintained Maker. Edit src/Example.php. JSON response and checks complete the job."}})
        if accept:
            self.nco.call("steer", {"action": "accept", "work": "Plan", "direction": "Plan inspected and fits the mission"})
        return planner, result

    def implementation(self, result):
        item = responsibility("Implement") | {"plan": result["reference"], "editable_paths": ["src/Example.php"],
                                                "context_paths": ["README.md"]}
        self.nco.call("orchestrate", {"work": [item]})
        with self.store.connect() as db:
            name = db.execute("SELECT member FROM member_bindings WHERE role='coder' AND reports_to=?", (self.nco.member,)).fetchone()[0]
        return API(self.state, name), item

    def test_real_mcp_nco_planner_handoff_and_scoped_plan_evidence(self):
        client = Client(self.state, self.nco.member)
        self.addCleanup(client.close)
        self.assertEqual("nco", client.tool("onboard", {})["role"])
        planner, result = self.plan()
        coder, _ = self.implementation(result)
        context = coder.call("work_context", {})
        self.assertEqual("routed to nco", context["guidance"])
        self.assertEqual(["src/Example.php"], context["development"]["editable_paths"])
        self.assertEqual(result["reference"], context["assignment"]["plan"]["reference"])
        self.assertEqual(context["delegation"], Advice(self.store, coder.member).brief()["delegation"])
        evidence = coder.call("work_context", {"reference": context["assignment"]["plan"]["evidence"]})
        self.assertIn("maintained Maker", evidence["content"])
        self.assertEqual("Plan ready", coder.call("work_context", {"reference": result["reference"]})["text"])
        jobs = {r["title"] for r in self.xo.call("monitor", {})["jobs"]}
        self.assertEqual({"Feature", "Plan", "Implement"}, jobs)
        with self.assertRaises(ValueError):
            self.api.call("work_context", {"reference": result["evidence"]})
        self.assertEqual("routed to xo", self.nco.call("work_context", {})["guidance"])

    def test_planner_inspects_but_cannot_implement_or_allocate(self):
        self.nco.call("orchestrate", {"work": [responsibility("Plan", "planner")]})
        planner = self.by_role("planner")
        tools = {row["name"] for row in planner.tools()}
        self.assertTrue({"framework_inspect", "work_check", "work_report"} <= tools)
        for tool, args in [("orchestrate", {"work": [responsibility()]}),
                           ("framework_generate", {"maker": "make:command"}),
                           ("work_save", {"note": "Implement"})]:
            with self.assertRaisesRegex(ValueError, "not available"):
                planner.call(tool, args)
        planner.call("work_inspect", {})
        provider = Serena(self.state, planner.member)
        args = provider.command(planner.control.snapshot(), planner.workspaces.ensure())
        writable = [args[i + 1] for i, token in enumerate(args[:-1]) if token == "--mount" and not args[i + 1].endswith(",readonly")]
        self.assertEqual(1, len(writable))
        self.assertTrue(writable[0].endswith("dst=/workspace/.serena"))
        with self.assertRaisesRegex(ValueError, "plan evidence"):
            planner.call("work_report", {"kind": "result", "text": "Done"})

    def test_stale_plan_result_cannot_be_accepted_and_only_accepted_result_can_be_used(self):
        planner, first = self.plan(accept=False)
        self.nco.call("steer", {"action": "guide", "work": "Plan", "done_when": "Different criteria"})
        with self.assertRaisesRegex(ValueError, "current retained result"):
            self.nco.call("steer", {"action": "accept", "work": "Plan", "direction": "Use old plan"})
        second = planner.call("work_report", {"kind": "result", "text": "Revised plan", "evidence": {
            "name": "plan.md", "content": "Plan for the revised completion criteria"}})
        self.nco.call("steer", {"action": "accept", "work": "Plan", "direction": "Use revised plan"})
        with self.assertRaisesRegex(ValueError, "accept the planner"):
            self.implementation(first)
        self.implementation(second)

    def test_changed_mission_invalidates_accepted_plan(self):
        _, result = self.plan()
        self.xo.call("steer", {"action": "guide", "work": "Coordinate", "objective": "A different mission"})
        with self.assertRaisesRegex(ValueError, "mission changed"):
            self.implementation(result)

    def test_nco_cannot_create_another_nco_or_take_sibling_jobs_and_batches_rollback(self):
        with self.assertRaisesRegex(ValueError, "XO appoints"):
            self.nco.call("orchestrate", {"work": [responsibility("New"), responsibility("Recursive", "nco")]})
        self.assertFalse(self.nco.call("monitor", {})["jobs"])
        for action in ("accept", "cancel"):
            with self.assertRaisesRegex(ValueError, "unique responsibility"):
                self.nco.call("steer", {"action": action, "work": "Feature", "direction": "Take another team"})
        with self.assertRaisesRegex(ValueError, "another coordinator"):
            self.nco.call("orchestrate", {"work": [responsibility("Feature")]})

    def test_pause_resume_reaches_descendants_and_brief_changes_invalidate_all_job_bindings(self):
        self.nco.call("orchestrate", {"work": [responsibility("Plan", "planner"), responsibility("Plan", "audit")]})
        old = {role: self.by_role(role).control.snapshot() for role in ("planner", "audit")}
        self.xo.call("steer", {"action": "pause", "work": "Coordinate"})
        self.assertTrue(self.nco.control.snapshot()["paused"])
        for role in old:
            self.assertTrue(self.by_role(role).control.snapshot()["paused"])
        with self.assertRaisesRegex(ValueError, "paused"):
            self.nco.call("orchestrate", {"work": [responsibility("More")]})
        self.xo.call("steer", {"action": "resume", "work": "Coordinate"})
        before = {role: self.by_role(role).control.snapshot()["revision"] for role in old}
        self.nco.call("steer", {"action": "guide", "work": "Plan", "constraints": "Updated bounds"})
        for role in old:
            self.assertGreater(self.by_role(role).control.snapshot()["revision"], before[role])

    def test_curated_serena_mounts_and_changed_assignment_restart_view(self):
        _, result = self.plan()
        coder, item = self.implementation(result)
        coder.call("work_inspect", {})
        root = Path(coder.workspaces.ensure()["root"])
        provider = Serena(self.state, coder.member)
        scope, signature = provider.scope()
        args = provider.command(scope, coder.workspaces.ensure())
        mounts = [args[i + 1] for i, token in enumerate(args[:-1]) if token == "--mount"]
        self.assertNotIn(f"type=bind,src={root},dst=/workspace,readonly", mounts)
        self.assertIn(f"type=bind,src={root}/README.md,dst=/workspace/README.md,readonly", mounts)
        self.assertIn(f"type=bind,src={root}/src/Example.php,dst=/workspace/src/Example.php", mounts)
        targets = [next(part for part in value.split(",") if part.startswith("dst=")) for value in mounts]
        self.assertEqual(len(targets), len(set(targets)))
        (root / "src/Other.php").write_text("Out of scope")
        with self.assertRaisesRegex(ValueError, "outside this role"):
            coder.call("work_save", {"note": "Extra change"})
        provider.signature = signature
        self.nco.call("orchestrate", {"work": [item | {"editable_paths": ["src/Other.php"]}]})
        with self.assertRaisesRegex(ValueError, "Reconnect"):
            provider.scope()

    def test_maker_protection_and_operator_policy_are_reused(self):
        self.api.call("work_inspect", {})
        root = Path(self.api.workspaces.ensure()["root"])
        provider = Serena(self.state, self.api.member)
        args = provider.command(self.api.control.snapshot(), self.api.workspaces.ensure())
        self.assertIn(f"type=bind,src={root}/src/Maker,dst=/workspace/src/Maker,readonly", args)
        (root / "src/Maker/Forbidden.php").write_text("Maker code")
        with self.assertRaisesRegex(ValueError, "outside this role"):
            self.api.call("work_save", {"note": "Change a Maker"})
        with patch.object(Development, "prepare") as prepare, self.assertRaisesRegex(ValueError, "maintained Makers"):
            Development(self.store, self.api.member).generate("make:maker")
        prepare.assert_not_called()
        with self.assertRaisesRegex(ValueError, "exclude Makers"):
            self.nco.call("orchestrate", {"work": [responsibility("Edit maker") | {"editable_paths": ["src/Maker"]}]})

    def test_assignment_changes_wait_for_active_workspace_operations(self):
        _, result = self.plan()
        coder, item = self.implementation(result)
        before = coder.control.snapshot()
        with coder.workspaces.lock("job-" + str(before["job"])), self.assertRaisesRegex(ValueError, "Another operation"):
            self.nco.call("orchestrate", {"work": [item | {"editable_paths": ["src/Other.php"]}]})
        self.assertEqual(before, coder.control.snapshot())
        self.assertEqual(["src/Example.php"], coder.call("work_context", {})["assignment"]["editable_paths"])

    def test_repeated_coordination_keeps_direction_and_current_plan(self):
        self.xo.call("steer", {"action": "guide", "work": "Coordinate", "direction": "Report the outcome to XO"})
        _, result = self.plan()
        before = self.nco.control.snapshot()
        self.xo.call("orchestrate", {"work": [responsibility("Coordinate", "nco")]})
        self.assertEqual(before, self.nco.control.snapshot())
        self.implementation(result)
        self.nco.call("steer", {"action": "guide", "work": "Implement", "objective": "Implement the approved JSON behavior"})
        coder = next(row for row in self.nco.call("monitor", {})["jobs"] if row["title"] == "Implement")
        self.xo.call("steer", {"action": "guide", "work": "Coordinate", "objective": responsibility()["objective"]})
        self.assertEqual(before, self.nco.control.snapshot())
        self.assertEqual(coder, next(row for row in self.nco.call("monitor", {})["jobs"] if row["title"] == "Implement"))
        with self.store.connect() as db:
            self.assertEqual("Implement the approved JSON behavior", db.execute("SELECT objective FROM jobs WHERE title='Implement'").fetchone()[0])

    def test_replaced_file_and_new_generated_file_invalidate_curated_mounts(self):
        _, result = self.plan()
        coder, _ = self.implementation(result)
        workspace = coder.workspaces.ensure()
        root = Path(workspace["root"])
        provider = Serena(self.state, coder.member)
        scope, signature = provider.scope()
        provider.command(scope, workspace)
        replacement = root / "src/replacement.php"
        replacement.write_text("<?php // Maker or Git replaced the file")
        replacement.replace(root / "src/Example.php")
        provider.signature, provider.process = signature, object()
        def close():
            provider.process = None
        with patch.object(provider, "close", side_effect=close) as closed, patch.object(provider, "request") as request:
            with self.assertRaisesRegex(ValueError, "paths changed"):
                provider.call({"code": "s.info()"})
            closed.assert_called_once()
            request.assert_not_called()
        missing = root / "src/Example.php"
        missing.unlink()
        provider.command(scope, workspace)
        previous = provider.mount_layout
        missing.write_text("<?php // Generated")
        self.assertNotEqual(previous, provider.layout(scope, workspace))

    def test_nco_can_read_own_and_child_operations_but_not_sibling_diagnostics(self):
        self.nco.call("orchestrate", {"work": [responsibility("Plan", "planner")]})
        planner = self.by_role("planner")
        with patch.object(Operations, "launch"):
            own = Operations(self.store, self.nco.member).start("work_check", {})
            child = Operations(self.store, planner.member).start("framework_inspect", {"kind": "makers"})
            sibling = Operations(self.store, self.api.member).start("framework_inspect", {"kind": "makers"})
        for value in (own, child):
            content = self.nco.call("work_context", {"reference": value["reference"]})["content"]
            self.assertEqual(value["reference"], json.loads(content)["reference"])
        with self.assertRaisesRegex(ValueError, "not available"):
            self.nco.call("work_context", {"reference": sibling["reference"]})

    def test_existing_role_policy_remains_usable_without_implicitly_enabling_new_roles(self):
        defaults(self.state)
        path = self.state / "roles.json"
        value = json.loads(path.read_text())
        for role in ("nco", "planner"):
            del value["roles"][role]
        path.write_text(json.dumps(value))
        self.assertEqual(8, len(load(self.state)[0]["roles"]))
        with self.assertRaisesRegex(ValueError, "roles.json"):
            resolve(self.state, "planner")

    def test_upgrade_from_jev_state_preserves_reports_and_bindings(self):
        before = self.nco.call("work_report", {"text": "Coordination state"})
        scope = self.nco.control.snapshot()
        with self.store.connect() as db:
            db.execute("ALTER TABLE jobs DROP COLUMN assignment")
            db.execute("ALTER TABLE work_updates DROP COLUMN binding")
            db.execute("ALTER TABLE work_updates DROP COLUMN mission")
            db.execute("ALTER TABLE deliveries DROP COLUMN result_update")
            db.execute("PRAGMA user_version=10")
        store = Store(self.state)
        with store.connect() as db:
            self.assertEqual(SCHEMA_VERSION, db.execute("PRAGMA user_version").fetchone()[0])
        self.assertEqual(scope, self.nco.control.snapshot())
        retry = self.nco.call("work_report", {"text": "Coordination state"})
        self.assertEqual(before["reference"], retry["reference"])
        self.assertTrue(retry["reused"])

    def test_native_introspection_uses_installed_console_metadata_and_operator_policy(self):
        self.nco.call("orchestrate", {"work": [responsibility("Plan", "planner")]})
        planner = self.by_role("planner")
        # Symfony Console 8.1 JsonDescriptor: command list plus named argument/option maps.
        command = {"name": "debug:container", "description": "Display current services", "usage": [], "help": "Inspect services", "hidden": False,
                   "definition": {"arguments": {"name": {"name": "name", "is_required": False, "is_array": False, "description": "Service", "default": None}},
                                  "options": {"show-hidden": {"name": "--show-hidden", "shortcut": "", "accept_value": False,
                                                              "is_value_required": False, "is_multiple": False, "description": "Include hidden services", "default": False}}}}
        provider = Development(self.store, planner.member)
        with patch.object(provider, "prepare"), patch.object(provider, "_json", side_effect=[{"commands": [command]}, command]), \
                patch.object(provider, "run", return_value={"exit_code": 0, "output": "services"}) as run:
            provider.inspect("console", "debug:container", {"arguments": {"name": "App\\Service\\Probe"}, "options": {"show-hidden": True}})
        self.assertEqual(["php", "bin/console", "debug:container", "--no-interaction", "--no-ansi", "--show-hidden", "--", "App\\Service\\Probe"], run.call_args.args[1])
        with patch.object(provider, "prepare"), patch.object(provider, "_json", return_value={"commands": [command]}), \
                self.assertRaisesRegex(ValueError, "inspection_commands"):
            provider.inspect("console", "cache:clear", {})
