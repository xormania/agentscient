import copy
import json
import unittest
from unittest.mock import patch

import test_control
from test_advice import answer

from devtools.api import API
from devtools.control import REQUEST_BINDING
from devtools.diagnostics import Diagnostics, deliver_guidance, failed, project_context
from devtools.onboarding import document


class DiagnosticTests(unittest.TestCase):
    setUp_base = test_control.ControlTests.setUp
    client = test_control.ControlTests.client

    def setUp(self):
        self.setUp_base()
        self.api = API(self.state, "coder")
        config = json.loads((self.state / "team.json").read_text())
        config.setdefault("project", {})["jev"] = {}
        config["project"]["development"] = {}
        (self.state / "team.json").write_text(json.dumps(config))
        self.diagnostics = Diagnostics(self.store, "coder")

    def report(self, text, kind="finding", evidence=None, member="coder"):
        args = {"text": text, "kind": kind}
        if evidence:
            args["evidence"] = {"name": "observation.txt", "content": evidence}
        return API(self.state, member).call("work_report", args)

    def context(self):
        return self.api.control.work_context(project=False)

    @staticmethod
    def relevance(state, questions, model):
        response = answer(state, questions, model)
        for index, fact in enumerate(state["facts"]):
            response["answers"][f"fact_{index}"]["noul"] = 0.01 if fact["text"] == "Unrelated color preference" else 0.9
        return response

    def test_low_noul_hides_only_background_and_raw_reports_remain_readable(self):
        relevant = self.report("The current interface is available")
        unrelated = self.report("Unrelated color preference")
        blocker = self.report("Current dependency needs a decision", kind="blocker")
        evidence = self.report("An observed color preference", evidence="Retained evidence")
        result = self.report("Observed result", kind="result")
        context = self.context()
        context["incoming"] = [{"text": "Required live direction", "type": "direction"}]
        original = copy.deepcopy(context)
        with patch("devtools.advice.Jev.evaluate", side_effect=self.relevance) as provider:
            projected = self.diagnostics.project(context)
        self.assertEqual(original, context)
        self.assertEqual([result["reference"], evidence["reference"], blocker["reference"], relevant["reference"]],
                         [row["reference"] for row in projected["recent_activity"]])
        for key in original.keys() - {"recent_activity"}:
            self.assertEqual(original[key], projected[key])
        request = provider.call_args.args[0]
        self.assertEqual("coder", request["brief"]["role"])
        self.assertEqual("Implement contract", request["brief"]["job"]["objective"])
        self.assertNotIn("SECRET SIBLING", json.dumps(request))
        self.assertEqual("Unrelated color preference", self.api.control.work_context(reference=unrelated["reference"])["text"])
        event = self.store.events(kind="context_projected")["events"][-1]["data"]
        omitted = next(row for row in event["facts"] if row["reference"] == unrelated["reference"])
        self.assertFalse(omitted["delivered"])
        self.assertEqual(64, len(omitted["source_sha256"]))
        self.assertFalse(self.store.events(kind="skill_missed")["events"])

    def test_error_truncation_and_evidence_are_never_relevance_candidates(self):
        for text in ("Failed check needs inspection", "Required boundary remains", "x" * 650):
            self.report(text)
        self.report("Result is ready", kind="result")
        self.report("Evidence is available", evidence="Observed")
        original = self.context()
        with patch("devtools.advice.Jev.evaluate") as provider:
            self.assertEqual(original, self.diagnostics.project(original))
        provider.assert_not_called()

    def test_uncertain_boundary_and_provider_failure_preserve_context(self):
        self.report("Unrelated color preference")
        context = self.context()
        def uncertain(state, questions, model):
            response = answer(state, questions, model)
            response["answers"]["fact_0"]["noul"] = 0.2
            return response
        with patch("devtools.advice.Jev.evaluate", side_effect=uncertain):
            self.assertEqual(context, self.diagnostics.project(context))
        for response in (ValueError("Unavailable"), {"answers": {}}, {"answers": {"fact_0": {"noul": float("nan")}}}):
            with patch("devtools.diagnostics.Advice.evaluate", side_effect=response if isinstance(response, Exception) else None,
                       return_value=response):
                self.assertEqual(context, self.diagnostics.project(context))

    def test_scope_and_wrong_role_context_do_not_reach_the_provider(self):
        sibling = self.report("Sibling fact", member="audit")
        sibling_context = API(self.state, "audit").control.work_context(project=False)
        forged = self.context()
        forged["recent_activity"] = sibling_context["recent_activity"]
        with patch("devtools.advice.Jev.evaluate") as provider:
            self.assertEqual(forged, self.diagnostics.project(forged))
            self.assertEqual(sibling_context, self.diagnostics.project(sibling_context))
        provider.assert_not_called()
        with self.assertRaisesRegex(ValueError, "not available"):
            self.api.control.work_context(reference=sibling["reference"])

    def test_rebind_and_mission_change_discard_assessment(self):
        self.report("Unrelated color preference")
        context = self.context()
        def rebind(state, questions, model):
            self.api.control.bind("coder", "docs", self.order, self.job, "xo")
            return self.relevance(state, questions, model)
        with patch("devtools.advice.Jev.evaluate", side_effect=rebind):
            self.assertEqual(context, self.diagnostics.project(context))
        self.api.control.bind("coder", "coder", self.order, self.job, "xo")
        context = self.context()
        def revised_goal(state, questions, model):
            with self.store.connect() as db:
                db.execute("UPDATE jobs SET objective='Document the color preference' WHERE id=?", (self.job,))
            return self.relevance(state, questions, model)
        with patch("devtools.advice.Jev.evaluate", side_effect=revised_goal):
            self.assertEqual(context, self.diagnostics.project(context))
        with patch("devtools.advice.Jev.evaluate") as provider:
            self.assertEqual(context, self.diagnostics.project(context))
        provider.assert_not_called()  # A stale brief is not assessed as the replacement mission.

    def test_current_context_reuses_retained_assessment_but_changed_role_reassesses(self):
        self.report("Unrelated color preference")
        context = self.context()
        with patch("devtools.advice.Jev.evaluate", side_effect=self.relevance) as provider:
            first = self.diagnostics.project(context)
            self.assertEqual(first, self.diagnostics.project(context))
            self.assertEqual(1, provider.call_count)
            self.api.control.bind("coder", "research", self.order, self.job, "xo")
            self.diagnostics.project(self.context())
            self.assertEqual(2, provider.call_count)
            self.assertEqual("research", provider.call_args.args[0]["brief"]["role"])

    def test_recovery_delivers_canonical_role_or_permitted_mate_method(self):
        result = {"passed": False, "checks": [{"exit_code": 1, "output": "Cannot autowire service: container wiring"}]}
        guidance = self.diagnostics.guidance("work_check", result)
        self.assertEqual("mate-symfony-service-inspection", guidance["skill"]["name"])
        self.assertEqual(document(guidance["skill"]["name"])["content"], guidance["skill"]["content"])
        self.assertIn("retained evidence", guidance["next_action"])
        self.api.control.bind("coder", "docs", self.order, self.job, "xo")
        guidance = self.diagnostics.guidance("framework_inspect", error="Missing PHP extension")
        self.assertEqual("agentscient-docs", guidance["skill"]["name"])
        events = self.store.events(kind="skill_guidance_delivered")["events"]
        self.assertEqual(2, len(events))
        self.assertEqual("docs", events[-1]["data"]["role"])
        self.assertEqual(64, len(events[-1]["data"]["sha256"]))
        self.assertFalse(self.store.events(kind="skill_loaded")["events"])

    def test_silence_for_success_unbound_interface_and_stale_binding(self):
        for result in ({"passed": True}, {"state": "queued"}, {"state": "completed", "result": {"passed": True}}):
            self.assertEqual({}, self.diagnostics.guidance("work_check", result))
        self.assertEqual({}, Diagnostics(self.store, "owner").guidance("monitor", error="Failure"))
        self.assertEqual({}, Diagnostics(self.store, "idle").guidance("work_context", error="Failure"))
        scope = self.api.control.snapshot()
        token = REQUEST_BINDING.set(("coder", scope))
        try:
            self.api.control.bind("coder", "docs", self.order, self.job, "xo")
            self.assertEqual({}, self.diagnostics.guidance("work_check", error="Failure"))
        finally:
            REQUEST_BINDING.reset(token)

    def test_finished_failure_and_serena_error_are_detected(self):
        self.assertTrue(failed({"state": "completed", "result": {"passed": False}}))
        self.assertTrue(failed({"validation": {"checks": [{"exit_code": 2}]}}))
        self.assertFalse(failed({"checks": None}))
        self.assertFalse(failed({"checks": 4}))
        self.assertFalse(failed({"exit_code": 0}))
        result = {"isError": True, "content": [{"type": "text", "text": "Missing PHP extension simplexml"}]}
        self.assertEqual("mate-php-environment-check", self.diagnostics.guidance("serena_repl", result)["skill"]["name"])

    def test_advisory_faults_cannot_replace_the_original_outcome(self):
        context = self.context()
        with patch.object(Diagnostics, "project", side_effect=OSError("Unavailable source")):
            self.assertIs(context, project_context(self.store, "coder", context))
        with patch.object(Diagnostics, "guidance", side_effect=ValueError("Invalid skill")):
            self.assertEqual({}, deliver_guidance(self.store, "coder", "work_check", error="Original failure"))
            with patch.object(self.store, "event", side_effect=OSError("Telemetry unavailable")):
                self.assertEqual({}, deliver_guidance(self.store, "coder", "work_check", error="Original failure"))
        self.assertEqual(1, len(self.store.events(kind="context_projection_unavailable")["events"]))
        self.assertEqual(1, len(self.store.events(kind="diagnostic_guidance_unavailable")["events"]))


if __name__ == "__main__":
    unittest.main()
