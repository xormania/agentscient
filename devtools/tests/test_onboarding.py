import json
import unittest
from unittest.mock import patch

import test_control
import test_development

from devtools.api import API
from devtools.control import ROLES
from devtools.development import Development
from devtools.onboarding import MATE, Onboarding, document


class OnboardingTests(unittest.TestCase):
    setUp = test_control.ControlTests.setUp
    client = test_control.ControlTests.client

    def test_each_role_receives_its_own_brief_and_skill_catalog_with_current_tools(self):
        texts = set()
        for role in ROLES:
            member = "owner" if role == "co" else "xo" if role == "xo" else "coder"
            api = API(self.state, member)
            if role not in {"co", "xo"}:
                api.control.bind(member, role, self.order, None if role == "planner" else self.job, "xo")
            value = api.call("onboard", {})
            self.assertEqual(role, value["role"])
            self.assertEqual(role, value["context"]["role"])
            self.assertEqual([r["name"] for r in api.tools()], value["tools"])
            self.assertEqual(2, len(value["skills"]))
            skill = api.call("skill_read", {"name": value["skills"][1]["name"]})
            self.assertEqual(value["role_instructions"], skill["content"])
            texts.add(value["role_instructions"])
            if role not in {"co", "xo", "nco"}:
                self.assertNotIn("SECRET SIBLING", json.dumps(value))
                with self.assertRaises(ValueError):
                    api.call("skill_read", {"name": "agentscient-co"})
        self.assertEqual(len(ROLES), len(texts))
        self.assertEqual(len(ROLES), len(self.store.events(kind="onboarding_delivered", limit=50)["events"]))
        self.assertEqual(len(ROLES), len(self.store.events(kind="skill_loaded", limit=50)["events"]))

    def test_role_change_and_revocation_refresh_onboarding_without_harness_dependence(self):
        api = API(self.state, "coder")
        first = api.call("onboard", {})
        for harness in ("codex", "claude", "grok"):
            with self.store.connect() as db:
                db.execute("UPDATE members SET harness=? WHERE name='coder'", (harness,))
            self.assertEqual(first["revision"], api.call("onboard", {})["revision"])
        api.control.bind("coder", "research", self.order, self.job, "xo")
        second = api.call("onboard", {})
        self.assertNotEqual(first["revision"], second["revision"])
        with self.assertRaises(ValueError):
            api.call("skill_read", {"name": first["skills"][1]["name"]})
        api.control.unbind("coder")
        with self.assertRaisesRegex(ValueError, "not available"):
            api.call("onboard", {})

    def test_command_guidance_matches_interface_planning_and_job_authority(self):
        co = API(self.state, "owner").call("onboard", {})
        self.assertIn("xor's interface", co["responsibility"])
        self.assertIn("Relay xor's authorized objective", co["role_instructions"])
        self.assertIn("direct", co["tools"])
        self.assertIn("monitor", co["tools"])
        self.assertFalse({"conclude", "restart_xo", "work_assess", "steer", "orchestrate"} & set(co["tools"]))
        self.assertNotIn("`conclude", co["role_instructions"])
        self.assertNotIn("`restart_xo", co["role_instructions"])

        xo = API(self.state, "xo").call("onboard", {})
        self.assertIn("plan_adopt", xo["tools"])
        self.assertIn("conclude", xo["tools"])
        self.assertIn("one-job plan", xo["role_instructions"])
        self.assertIn("one `nco` per job", xo["role_instructions"])
        self.assertIn("superior steering", xo["role_instructions"])

        api = API(self.state, "coder")
        api.control.bind("coder", "nco", self.order, self.job, "xo")
        nco = api.call("onboard", {})
        self.assertIn("one assigned job", nco["role_instructions"])
        self.assertIn("do not commission a planner or another NCO", nco["role_instructions"])
        self.assertNotIn("conclude", nco["tools"])
        api.control.bind("coder", "planner", self.order, None, "xo")
        planner = api.call("onboard", {})
        self.assertIn("Propose jobs", planner["role_instructions"])
        self.assertIn("XO's `plan_adopt`", planner["role_instructions"])
        self.assertFalse({"plan_adopt", "steer", "orchestrate"} & set(planner["tools"]))
        self.assertIn("do not use harness-native subagents", planner["shared"])

    def test_catalog_has_valid_shared_skills_and_cannot_escape_source_tree(self):
        for name in MATE:
            self.assertEqual(64, len(document(name)["sha256"]))
        with self.assertRaises(ValueError):
            document("../../AGENTS")
        original = Onboarding(API(self.state, "coder")).startup()
        self.assertIn("Call onboard", original)
        self.assertNotIn("model_provider", original)


class MateSkillTests(unittest.TestCase):
    setUp = test_development.DevelopmentTests.setUp
    prepared = test_development.DevelopmentTests.prepared
    configure = test_development.DevelopmentTests.configure

    def test_mate_skills_are_available_only_with_tools_and_resources_use_mcp(self):
        self.assertEqual(2, len(self.api.call("onboard", {})["skills"]))
        self.configure()
        value = self.api.call("onboard", {})
        self.assertEqual(8, len(value["skills"]))
        skill = self.api.call("skill_read", {"name": "mate-symfony-profiler-debugging"})
        self.assertIn("mate_resource", skill["content"])
        self.assertNotIn("mcp_adapter", skill)
        with patch.object(Development, "_json", return_value={"collectors": []}) as call:
            Development(self.store, "coder").inspect("mate_resource", resource="symfony-profiler://profile/abc123")
        self.assertIn("resources:read", call.call_args.args[1])
        with self.assertRaises(ValueError):
            Development(self.store, "coder").inspect("mate_resource", resource="file:///private")

    def test_onboarding_and_skill_reads_keep_the_binding_captured_before_a_rebind(self):
        self.configure()
        scope = self.api.control.snapshot()
        expected = self.api.call("onboard", {})

        def rebind(role):
            self.api.control.bind("coder", role, scope["work_order"], scope["job"], "xo")

        captured = self.api.call("onboard", {}, on_context=lambda: rebind("docs"))
        self.assertEqual("coder", captured["role"])
        self.assertEqual("coder", captured["context"]["role"])
        self.assertEqual(expected["tools"], captured["tools"])
        self.assertEqual(expected["skills"], captured["skills"])
        subsequent = self.api.call("onboard", {})
        self.assertEqual("docs", subsequent["role"])
        self.assertNotIn("framework_generate", subsequent["tools"])
        self.assertEqual(4, len(subsequent["skills"]))

        rebind("coder")
        name = "mate-symfony-profiler-debugging"
        skill = self.api.call("skill_read", {"name": name}, on_context=lambda: rebind("docs"))
        self.assertEqual(name, skill["name"])
        with self.assertRaisesRegex(ValueError, "current onboard catalog"):
            self.api.call("skill_read", {"name": name})

    def test_catalog_is_compact_and_source_changes_remain_versioned(self):
        self.configure()
        before = self.api.call("onboard", {})
        self.assertEqual([True, True] + [False] * 6, [s["loaded"] for s in before["skills"]])
        self.assertLess(len(json.dumps(before["skills"])), 2300)
        self.assertNotIn("source", before["skills"][0])
        self.assertNotIn(before["shared"], Onboarding(self.api).startup())
        for name in MATE:
            skill = self.api.call("skill_read", {"name": name})
            self.assertIn("framework_inspect", skill["content"])
            self.assertNotIn("vendor/bin/mate", skill["content"])
            self.assertNotIn("composer show", skill["content"])
            self.assertNotIn("bin/console", skill["content"])
            self.assertEqual(64, len(skill["sha256"]))
        name = MATE[0]
        original = self.api.call("skill_read", {"name": name})
        def revised(request):
            value = document(request)
            return value | {"content": value["content"] + " Revised guidance."} if request == name else value
        with patch("devtools.onboarding.document", side_effect=revised):
            after = self.api.call("onboard", {})
            changed = self.api.call("skill_read", {"name": name})
        self.assertNotEqual(original["guidance_sha256"], changed["guidance_sha256"])
        self.assertNotEqual(before["revision"], after["revision"])
        events = self.store.events(kind="skill_loaded")["events"]
        self.assertEqual(changed["guidance_sha256"], events[-1]["data"]["guidance_sha256"])

    def test_mate_discovery_lists_names_but_named_inspection_retains_schema(self):
        self.configure()
        schema = {"name": "server-info", "description": "Runtime facts", "input_schema": {"type": "object"}}
        with patch.object(Development, "_json", return_value={"tools": {"server-info": schema}}):
            listing = Development(self.store, "coder").inspect("mate")["result"]
            self.assertEqual([{"name": "server-info", "description": "Runtime facts"}], listing["tools"])
            detail = Development(self.store, "coder").inspect("mate", name="server-info")["result"]
            self.assertEqual(schema, detail)
