import io
import json
import math
import os
import unittest
from unittest.mock import patch

import test_workspaces

from devtools.api import API
from devtools.completion import GENERATED, SOURCE, Completion, generate, validate
from devtools.store import canonical, stamp
from devtools.workspaces import git


def answer(state, questions, model):
    return {"model": model, "answers": {name: {"type": "noul", "noul": 0.97} for name in questions},
            "usage": {"input_tokens": 800, "output_tokens": 40}}


class CompletionTests(unittest.TestCase):
    def setUp(self):
        test_workspaces.WorkspaceTests.setUp(self)
        self.xo = API(self.state, "xo")
        self.job = self.api.control.snapshot()["job"]
        self.order = self.xo.control.snapshot()["work_order"]
        self.gate = Completion(self.store, "xo")
        self.configure({})
        self.requests = []

        def evaluate(state, questions, model):
            self.requests.append((state, questions, model))
            return answer(state, questions, model)

        self.provider = patch("devtools.advice.Jev.evaluate", side_effect=evaluate).start()
        self.addCleanup(self.provider.stop)

    def configure(self, value):
        config = json.loads((self.state / "team.json").read_text())
        if value is None:
            config["project"].pop("jev", None)
        else:
            config["project"]["jev"] = value
        (self.state / "team.json").write_text(json.dumps(config))

    def report(self, content="Measured requested behavior: expected Works, observed Works."):
        return self.api.call("work_report", {"kind": "result", "text": "Feature ready", "evidence": {
            "name": "proof.txt", "content": content}})

    def operation(self, passed=True, revision="a" * 40, name="behavior", *, job=None, state="completed", checks=True, uncommitted=None, arguments=None):
        scope = self.api.control.snapshot()
        saved = self.api.artifacts.ingest("measure-" + name + ".txt", io.BytesIO(b"Expected Works; observed Works"), "text/plain", work_order=self.order, job=job or self.job)
        result = {"passed": passed, "revision": revision, "uncommitted": uncommitted or [],
                  "checks": [{"check": name, "exit_code": 0 if passed else 1, "evidence": "artifact:" + str(saved["artifact"]["id"])}] if checks else []}
        with self.store.connect() as db:
            return db.execute("INSERT INTO operations(member,work_order,job,binding,action,arguments,state,result,error,created,updated) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                "coder", self.order, job or self.job, canonical(scope), "work_check", canonical(arguments or {}), state,
                canonical(result), "Worker disappeared" if state == "uncertain" else None, stamp(), stamp())).lastrowid

    def assignment(self):
        brief = {"name": "Feature implementation", "role": "coder", "objective": "Implement behavior", "done_when": "Behavior demonstrated", "constraints": "Product only"}
        with self.store.connect() as db:
            ident = db.execute("INSERT INTO role_assignments(work_order,job,name,role,brief,details,created_by,created,updated) VALUES (?,?,?,?,?,?,?,?,?)", (
                self.order, self.job, brief["name"], "coder", canonical(brief), "{}", "xo", stamp(), stamp())).lastrowid
            db.execute("UPDATE member_bindings SET assignment_id=? WHERE member='coder'", (ident,))
        return ident

    def capture(self, report, revision, clean=True):
        provenance = {"provider": "work_report", "reference": report["reference"],
                      "source_revision": revision, "workspace_clean": clean, "revision_kind": "report_capture"}
        with self.store.connect() as db:
            db.execute("INSERT OR IGNORE INTO artifact_sources(artifact,provider,reference,metadata) VALUES (?,?,?,?)", (
                int(report["evidence"].split(":")[1]), "work_report", report["reference"], canonical(provenance)))

    def test_absent_jev_retains_existing_gates_and_explicit_off_is_operator_owned(self):
        for config in (None, {"completion": False}):
            self.configure(config)
            self.assertEqual("disabled", self.gate.require("job", job=self.job)["state"])
        self.assertEqual([], self.requests)
        self.configure({"completion": "false"})
        with self.assertRaisesRegex(ValueError, "boolean"):
            self.gate.require("job", job=self.job)

    def test_result_claim_without_retained_proof_does_not_call_jev(self):
        self.api.call("work_report", {"kind": "result", "text": "All done"})
        with self.assertRaisesRegex(ValueError, "claim alone"):
            self.gate.require("job", job=self.job)
        self.assertEqual([], self.requests)
        self.assertEqual(1, len(self.store.events(kind="completion_blocked")["events"]))

    def test_assignment_uses_its_original_brief_and_full_owner_boundaries(self):
        assignment = self.assignment()
        self.report()
        self.assertEqual("ready", self.gate.require("assignment", assignment=assignment)["state"])
        state = self.requests[0][0]
        self.assertEqual("Implement behavior", state["requirements"]["objective"])
        self.assertEqual("Behavior demonstrated", state["requirements"]["done_when"])
        self.assertEqual("Implement", state["owner"]["objective"])
        self.assertEqual("Feature", state["job"]["objective"])
        self.assertIn("specialist need not", state["boundary_rule"])

    def test_each_required_condition_must_pass_no_average_or_done_plan_substitution(self):
        self.report("Only the happy path was measured; recovery remains untested.")

        def incomplete(state, questions, model):
            result = answer(state, questions, model)
            result["answers"]["done_when"]["noul"] = 0.4
            return result

        self.provider.side_effect = incomplete
        with self.assertRaisesRegex(ValueError, "done_when"):
            self.gate.require("job", job=self.job)
        event = self.store.events(kind="completion_assessed")["events"][0]
        self.assertEqual(["done_when"], event["data"]["unresolved"])
        self.assertTrue(event["data"]["evidence"].startswith("artifact:"))

    def test_original_owner_goal_survives_narrowed_job_and_cancelled_contributions(self):
        self.report()
        with self.store.connect() as db:
            db.execute("UPDATE work_orders SET objective='Deliver happy path and recovery',done_when='Both paths measured' WHERE id=?", (self.order,))
            db.execute("UPDATE jobs SET objective='Happy path',status='cancelled' WHERE id=?", (self.job,))
        self.gate.require("work_order")
        state = self.requests[0][0]
        self.assertEqual("Deliver happy path and recovery", state["requirements"]["objective"])
        self.assertEqual("cancelled", state["jobs"][0]["status"])
        self.assertIn("cancelled jobs", state["boundary_rule"])

    def test_mechanical_failure_cannot_be_overridden_by_high_jev_probability(self):
        self.report()
        self.operation(passed=False)
        with self.assertRaisesRegex(ValueError, "behavior"):
            self.gate.require("job", job=self.job, revision="a" * 40)
        self.assertEqual([], self.requests)
        with self.assertRaisesRegex(ValueError, "ci check to pass"):
            self.gate.require("job", job=self.job, mechanical={"ci": {"passed": False}})

    def test_failed_or_uncertain_operation_without_named_checks_blocks(self):
        self.report()
        self.operation(passed=False, checks=False)
        with self.assertRaisesRegex(ValueError, "measurement to pass"):
            self.gate.require("job", job=self.job)
        self.operation(state="uncertain")
        with self.assertRaisesRegex(ValueError, "completed current measurement"):
            self.gate.require("job", job=self.job)
        self.assertEqual([], self.requests)

    def test_current_measurement_supersedes_failure_and_identical_proof_cache_reuses_request(self):
        self.report()
        self.operation(passed=False)
        self.operation(passed=True)
        first = self.gate.require("job", job=self.job, revision="a" * 40)
        second = self.gate.require("job", job=self.job, revision="a" * 40)
        self.assertEqual(first["evidence"], second["evidence"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(1, len(self.requests))
        self.assertTrue(any(p["current_source"] is True for p in self.requests[0][0]["proof"]))

    def test_unrelated_named_check_cannot_erase_failed_check(self):
        self.report()
        self.operation(passed=False, name="recovery", arguments={"check": "recovery"})
        self.operation(passed=True, name="happy", arguments={"check": "happy"})
        with self.assertRaisesRegex(ValueError, "recovery"):
            self.gate.require("job", job=self.job)

    def test_other_revision_cannot_mask_current_failed_measurement(self):
        self.report()
        self.operation(passed=False, revision="a" * 40)
        self.operation(passed=True, revision="b" * 40)
        with self.assertRaisesRegex(ValueError, "behavior"):
            self.gate.require("job", job=self.job, revision="a" * 40)

    def test_old_check_and_current_claim_cannot_prove_current_code(self):
        self.report()
        self.operation(revision="a" * 40)
        with self.assertRaisesRegex(ValueError, "current source revision"):
            self.gate.require("job", job=self.job, revision="b" * 40)
        self.assertEqual([], self.requests)

    def test_report_capture_is_current_document_provenance_not_executed_measurement(self):
        report = self.report("Design deliverable: requested behavior and its verification are defined.")
        self.capture(report, "a" * 40)
        self.gate.require("job", job=self.job, revision="a" * 40)
        proof = self.requests[0][0]["proof"][0]
        self.assertEqual("report_capture", proof["kind"])
        self.assertTrue(proof["current_source"])
        self.assertIn("not execution", self.requests[0][1]["done_when"]["instructions"]["rules"][-1])

    def test_reused_artifact_selects_only_the_current_reports_capture(self):
        first = self.report()
        self.capture(first, "a" * 40)
        with self.assertRaisesRegex(ValueError, "current source revision"):
            self.gate.require("job", job=self.job, revision="b" * 40)
        second = self.api.call("work_report", {"kind": "result", "text": "Feature verified again", "evidence": {
            "name": "proof.txt", "content": "Measured requested behavior: expected Works, observed Works."}})
        self.assertEqual(first["evidence"], second["evidence"])
        self.capture(second, "b" * 40)
        self.gate.require("job", job=self.job, revision="b" * 40)
        self.assertEqual("b" * 40, self.requests[0][0]["proof"][0]["source_revision"])

    def test_actual_report_capture_rebinds_identical_proof_after_saved_source_changes(self):
        root = test_workspaces.WorkspaceTests.prepared(self)
        before = git(root, "rev-parse", "HEAD").stdout.decode().strip()
        first = self.report("Current design deliverable defines expected feature behavior.")
        self.gate.require("job", job=self.job, revision=before)
        (root / "src/Example.php").write_text("Implemented and verified behavior\n")
        self.api.call("work_save", {"note": "Implement behavior"})
        after = git(root, "rev-parse", "HEAD").stdout.decode().strip()
        second = self.report("Current design deliverable defines expected feature behavior.")
        self.assertNotEqual(first["reference"], second["reference"])
        self.assertEqual(first["evidence"], second["evidence"])
        self.gate.require("job", job=self.job, revision=after)
        proof = self.requests[-1][0]["proof"][0]
        self.assertEqual(after, proof["source_revision"])
        self.assertTrue(proof["workspace_clean"])
        self.assertEqual("report_capture", proof["kind"])

    def test_unrelated_capture_or_dirty_capture_cannot_make_proof_current(self):
        report = self.report()
        self.capture(report, "a" * 40)
        foreign = {**report, "reference": "update:999999"}
        self.capture(foreign, "b" * 40)
        with self.assertRaisesRegex(ValueError, "current source revision"):
            self.gate.require("job", job=self.job, revision="b" * 40)
        with self.store.connect() as db:
            db.execute("DELETE FROM artifact_sources")
        self.capture(report, "b" * 40, clean=False)
        with self.assertRaisesRegex(ValueError, "current source revision"):
            self.gate.require("job", job=self.job, revision="b" * 40)
        self.assertEqual([], self.requests)

    def test_dirty_measurement_and_mismatched_ci_revision_block(self):
        self.report()
        self.operation(uncommitted=["src/Example.php"])
        with self.assertRaisesRegex(ValueError, "saved source"):
            self.gate.require("job", job=self.job)
        with self.store.connect() as db:
            db.execute("DELETE FROM operations")
        with self.assertRaisesRegex(ValueError, "ci evidence for the current"):
            self.gate.require("job", job=self.job, revision="a" * 40, mechanical={"ci": {"passed": True, "revision": "b" * 40}})

    def test_same_named_checks_in_two_owned_jobs_remain_independent(self):
        self.report()
        self.operation(passed=False)
        other = self.xo.work.job_create(title="Other", objective="Other", done_when="Works", constraints="Product", work_order=self.order)["job"]["id"]
        self.operation(passed=True, job=other)
        with self.assertRaisesRegex(ValueError, "job " + str(self.job)):
            self.gate.require("work_order")

    def test_job_and_assignment_secrets_from_independent_xo_are_never_sent(self):
        self.report()
        self.xo.control.bind("docs", "xo", self.order, reports_to="co")
        other = API(self.state, "docs").work.job_create(title="Sibling secret", objective="Private objective", done_when="Private criterion", work_order=self.order)["job"]["id"]
        with self.assertRaisesRegex(ValueError, "outside current work"):
            self.gate.require("job", job=other)
        with self.assertRaisesRegex(ValueError, "independent command teams"):
            self.gate.require("work_order")
        self.assertEqual([], self.requests)
        self.assertNotIn("Sibling secret", json.dumps(self.store.events(kind="completion_blocked")))

    def test_jev_unavailable_keeps_boundary_closed_and_retains_failure_event(self):
        self.report()
        self.provider.side_effect = ValueError("Jev temporarily unavailable")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.gate.require("job", job=self.job)
        self.assertEqual("unavailable", self.store.events(kind="jev_evaluation")["events"][0]["data"]["outcome"])
        self.assertEqual(1, len(self.store.events(kind="completion_blocked")["events"]))

    def test_malformed_required_probabilities_never_accept(self):
        self.report()
        for probability in (math.nan, True, -0.1, 1.1, "1"):
            result = answer({}, {name: {} for name in ("objective", "done_when", "constraints")}, "jev-1.13.0")
            result.update(evidence="artifact:1", cache_hit=False)
            result["answers"]["objective"]["noul"] = probability
            with self.subTest(probability=probability), patch("devtools.completion.Advice.evaluate", return_value=result), self.assertRaisesRegex(ValueError, "invalid.*probability"):
                self.gate.require("job", job=self.job)
        with patch("devtools.completion.Advice.evaluate", return_value={"evidence": "artifact:1", "answers": {}, "cache_hit": False}), self.assertRaisesRegex(ValueError, "incomplete"):
            self.gate.require("job", job=self.job)

    def test_owner_change_during_jev_cannot_accept_stale_proof(self):
        self.report()

        def changed(state, questions, model):
            with self.store.connect() as db:
                db.execute("UPDATE work_orders SET objective='New owner goal' WHERE id=?", (self.order,))
            return answer(state, questions, model)

        self.provider.side_effect = changed
        with self.assertRaisesRegex(ValueError, "changed during assessment"):
            self.gate.require("job", job=self.job)

    def test_acceptance_receipt_rechecks_owner_goal_and_operator_policy(self):
        self.report()
        receipt = self.gate.require("job", job=self.job)
        self.gate.verify(receipt)
        with self.store.connect() as db:
            db.execute("UPDATE work_orders SET done_when='Recovery must be measured' WHERE id=?", (self.order,))
        with self.assertRaisesRegex(ValueError, "changed after assessment"):
            self.gate.verify(receipt)
        receipt = self.gate.require("job", job=self.job)
        self.configure({"model": "jev-1.14.0"})
        with self.assertRaisesRegex(ValueError, "policy changed"):
            self.gate.verify(receipt)

    def test_changed_result_changes_assessment_cache_and_raw_retained_input(self):
        self.report()
        first = self.gate.require("job", job=self.job)
        self.report("Measured feature and recovery with new evidence.")
        second = self.gate.require("job", job=self.job)
        self.assertNotEqual(first["evidence"], second["evidence"])
        content = self.xo.call("work_context", {"reference": second["evidence"]})["content"]
        retained = json.loads(content)
        self.assertEqual("completion", retained["purpose"])
        self.assertIn("questions", retained["request"])
        self.assertEqual(2, len(self.requests))


class CompletionPolicyTests(unittest.TestCase):
    def test_export_preserves_all_required_boundaries_and_criteria(self):
        import hashlib

        value = json.loads(GENERATED.read_text())
        policy = validate(value, hashlib.sha256(SOURCE.read_bytes()).hexdigest())
        self.assertEqual({"objective", "done_when", "constraints"}, set(policy["questions"]))
        del value["policy"]["questions"]["constraints"]
        with self.assertRaisesRegex(ValueError, "objective, done_when and constraints"):
            validate(value, value["source_sha256"])

    def test_cue_generated_policy_agrees_when_cue_is_available(self):
        cue = os.environ.get("AGENTSCIENT_CUE")
        if not cue:
            self.skipTest("Maintainer CUE drift check runs in CI")
        self.assertEqual(json.loads(GENERATED.read_text()), generate(cue))
