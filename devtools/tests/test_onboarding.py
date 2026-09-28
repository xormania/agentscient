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
                api.control.bind(member, role, self.order, self.job, "xo")
            value = api.call("onboard", {})
            self.assertEqual(role, value["role"])
            self.assertEqual(role, value["context"]["role"])
            self.assertEqual([r["name"] for r in api.tools()], value["tools"])
            self.assertEqual(2, len(value["skills"]))
            skill = api.call("skill_read", {"name": value["skills"][1]["name"]})
            self.assertEqual(value["role_instructions"], skill["content"])
            texts.add(value["role_instructions"])
            if role not in {"co", "xo"}:
                self.assertNotIn("SECRET SIBLING", json.dumps(value))
                with self.assertRaises(ValueError):
                    api.call("skill_read", {"name": "agentscient-co"})
        self.assertEqual(8, len(texts))
        self.assertEqual(8, len(self.store.events(kind="onboarding_delivered", limit=50)["events"]))
        self.assertEqual(8, len(self.store.events(kind="skill_loaded", limit=50)["events"]))

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
        self.assertIn("mate_resource", skill["mcp_adapter"])
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

    def test_adapter_changes_are_versioned_in_the_catalog_and_delivery_events(self):
        self.configure()
        name = "mate-symfony-profiler-debugging"
        before = self.api.call("onboard", {})
        original = self.api.call("skill_read", {"name": name})
        with patch("devtools.onboarding.ADAPTER", "Revised MCP syntax and restrictions"):
            after = self.api.call("onboard", {})
            changed = self.api.call("skill_read", {"name": name})
        self.assertEqual(original["sha256"], changed["sha256"])
        self.assertNotEqual(original["guidance_sha256"], changed["guidance_sha256"])
        self.assertNotEqual(before["revision"], after["revision"])
        self.assertEqual(before["skills"][:2], after["skills"][:2])
        catalog_entry = next(row for row in after["skills"] if row["name"] == name)
        self.assertEqual(changed["guidance_sha256"], catalog_entry["guidance_sha256"])
        events = self.store.events(kind="skill_loaded")["events"]
        self.assertEqual([original["guidance_sha256"], changed["guidance_sha256"]],
                         [row["data"]["guidance_sha256"] for row in events])
