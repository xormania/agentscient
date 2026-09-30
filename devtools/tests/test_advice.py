import io
import json
import os
import socket
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from unittest.mock import MagicMock, patch

import test_delivery
import test_workspaces
from support import Client, adopt_plan, fixture_work
from test_commands import responsibility

from devtools.api import API
from devtools.jev import MAX_RESPONSE, MODEL, Jev, checked_response
from devtools.jev_config import load as load_policy
from devtools.runtime import defaults
from devtools.store import SCHEMA_VERSION, Store, canonical, stamp
from devtools.workspaces import Workspaces


def answer(state, questions, model=MODEL):
    answers = {}
    for name, question in questions.items():
        kind = question["type"]
        if kind == "noul":
            answers[name] = {"type": kind, "noul": 0.8}
        else:
            options = list(question["criteria"]) if kind == "choice" else list(map(str, range(len(question["criteria"]))))
            selected = "unknown" if "unknown" in options else options[0]
            answers[name] = {"type": kind, "confidence": 0.9,
                             "probabilities": {key: float(key == selected) for key in options},
                             "choice" if kind == "choice" else "score": selected if kind == "choice" else 0}
            if kind == "score":
                answers[name]["legend"] = dict(enumerate(question["criteria"]))
                answers[name]["legend"] = {str(k): v for k, v in answers[name]["legend"].items()}
    return {"model": model, "answers": answers, "usage": {"input_tokens": 600, "output_tokens": 40}}


class AdviceTests(unittest.TestCase):
    def setUp(self):
        test_workspaces.WorkspaceTests.setUp(self)
        self.configure({})
        self.xo = API(self.state, "xo")
        self.requests = []

        def evaluate(state, questions, model):
            self.requests.append((state, questions, model))
            return answer(state, questions, model)

        self.provider = patch("devtools.advice.Jev.evaluate", side_effect=evaluate).start()
        self.addCleanup(patch.stopall)

    def configure(self, value):
        config = json.loads((self.state / "team.json").read_text())
        if value is None:
            config["project"].pop("jev", None)
        else:
            config["project"]["jev"] = value
        (self.state / "team.json").write_text(json.dumps(config))

    def assess(self, sources=None, questions=None, api=None):
        return (api or self.api).call("work_assess", {
            "sources": sources or [{"path": "src/Example.php"}],
            "questions": questions or [{"name": "relevant", "instructions": "Does this implement the required behavior?"}],
        })

    def test_opt_in_role_catalogs_and_real_mcp_cached_result(self):
        self.configure(None)
        self.assertNotIn("work_assess", {r["name"] for r in self.api.tools()})
        with self.assertRaisesRegex(ValueError, "not available"):
            self.assess()
        self.configure({})
        self.assertIn("assignment_advise", {r["name"] for r in self.xo.tools()})
        self.assertNotIn("assignment_advise", {r["name"] for r in self.api.tools()})
        self.assertNotIn("work_assess", {r["name"] for r in API(self.state, "docs").tools()})
        first = self.assess()
        client = Client(self.state, "coder")
        self.addCleanup(client.close)
        result = client.tool("work_assess", {
            "sources": [{"path": "src/Example.php"}],
            "questions": [{"name": "relevant", "instructions": "Does this implement the required behavior?"}],
        })
        self.assertTrue(result["cache_hit"])
        self.assertEqual(first["evidence"], result["evidence"])
        self.assertEqual(1, len(self.requests))
        self.assertNotIn("original", json.dumps(result))
        retained = self.api.call("work_context", {"reference": result["evidence"]})
        self.assertIn("questions", json.loads(retained["content"]))

    def test_batch_typed_questions_and_partial_utf8_ranges(self):
        root = test_workspaces.WorkspaceTests.prepared(self)
        (root / "src/Example.php").write_text("aéé rest of file")
        result = self.assess(sources=[{"path": "src/Example.php", "limit": 4}], questions=[
            {"name": "relevant", "instructions": "Relevant?"},
            {"name": "layer", "type": "choice", "instructions": "Which layer?", "options": ["domain", "storage"]},
            {"name": "fit", "type": "score", "instructions": "How relevant?", "levels": ["unrelated", "related"]},
        ])
        source = result["results"][0]["source"]
        self.assertTrue(source["partial"])
        self.assertEqual(3, source["next_offset"])
        self.assertEqual("aé", self.requests[0][0]["sources"][0]["content"])
        self.assertEqual({"relevant", "layer", "fit"}, result["results"][0]["answers"].keys())
        self.assertIn("partial range", self.requests[0][1]["s0_q0"]["instructions"])
        self.assess(sources=[{"path": "src/Example.php", "offset": 3}])
        with self.assertRaisesRegex(ValueError, "character boundary"):
            self.assess(sources=[{"path": "src/Example.php", "offset": 2}])

    def test_planned_role_scope_and_shared_context_are_supplied_to_jev(self):
        co = API(self.state, "co")
        document = co.call("work_report", {"text": "Prepared specification", "evidence": {
            "name": "scope.md", "content": "Preserve the existing endpoint behavior"}})
        order = co.call("work_context", {})["work"]
        co.call("direct", {**{key: order[key] for key in ("title", "objective", "done_when", "constraints")},
                           "context": [document["evidence"]]})
        adopt_plan(self.xo, [{"name": "Feature", "objective": "Deliver the feature", "done_when": "Feature works",
                             "constraints": "Product changes only"}])
        assignment = {"name": "Feature", "job": "Feature", "role": "coder",
                      "objective": "Implement signed receipts", "done_when": "Receipt signatures validate",
                      "constraints": "Do not modify other endpoints"}
        self.xo.call("orchestrate", {"work": [assignment]})
        self.xo.call("steer", {"action": "resume", "work": "Feature", "assignment": "Feature"})
        self.api.call("work_assess", {"proposal": "Add signed receipts"})
        brief = self.requests[-1][0]["brief"]
        self.assertEqual({key: assignment[key] for key in ("name", "role", "objective", "done_when", "constraints")},
                         brief["role_assignment"])
        self.assertEqual([document["evidence"]], brief["context"])
        self.assertNotEqual(brief["job"]["objective"], brief["role_assignment"]["objective"])

    def test_identical_concurrent_evidence_requests_reuse_one_evaluation(self):
        evidence = self.api.artifacts.save("shared.txt", content="same diagnostic")
        sources = [{"reference": "artifact:" + str(evidence["artifact"]["id"])}]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.assess(sources=sources, api=API(self.state, "coder")), range(2)))
        self.assertEqual(1, len(self.requests))
        self.assertEqual(results[0]["evidence"], results[1]["evidence"])
        self.assertEqual({False, True}, {r["cache_hit"] for r in results})

    def test_cache_changes_with_source_question_model_and_work_scope(self):
        first = self.assess()
        self.assertTrue(self.assess()["cache_hit"])
        root = test_workspaces.WorkspaceTests.prepared(self)
        (root / "src/Example.php").write_text("new implementation\n")
        changed = self.assess()
        self.assertNotEqual(first["fingerprint"], changed["fingerprint"])
        self.assess(questions=[{"name": "relevant", "instructions": "Does it handle recovery?"}])
        self.configure({"model": "jev-1.14.0"})
        self.assess()
        self.xo.call("orchestrate", {"work": [responsibility("Feature") | {"objective": "Different requirement"}]})
        self.assess()
        self.assertEqual(5, len(self.requests))
        events = self.store.events(kind="jev_evaluation")["events"]
        self.assertEqual(1, sum(r["data"].get("cache_hit", False) for r in events))
        self.assertIsNone(events[1]["data"]["usage"])

    def test_concurrent_cache_wait_covers_configured_retries(self):
        policy = load_policy()
        policy["transport"].update(timeout=60, max_attempts=3, max_retry_delay=5)
        (self.state / "slow-jev.json").write_text(json.dumps(policy))
        self.configure({"policy_file": "slow-jev.json"})
        evaluating, waiting = Event(), Event()
        original_lock = Workspaces.lock

        @contextmanager
        def checked_lock(spaces, name, timeout=0):
            if name.startswith("jev-"):
                self.assertGreaterEqual(timeout, 190)  # Three 60s attempts and two 5s backoffs.
                if evaluating.is_set():
                    waiting.set()
            with original_lock(spaces, name, timeout):
                yield

        def evaluate(state, questions, model):
            evaluating.set()
            self.assertTrue(waiting.wait(5), "Second request did not wait for the in-flight evaluation")
            return answer(state, questions, model)

        self.provider.side_effect = evaluate
        with patch.object(Workspaces, "lock", checked_lock), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.api.call, "work_assess", {"proposal": "Add logging"})
            self.assertTrue(evaluating.wait(5))
            second = pool.submit(API(self.state, "coder").call, "work_assess", {"proposal": "Add logging"})
            results = [first.result(), second.result()]
        self.assertEqual(1, self.provider.call_count)
        self.assertEqual(results[0]["evidence"], results[1]["evidence"])
        self.assertEqual([False, True], [result["cache_hit"] for result in results])

    def test_sources_reject_escape_symlinks_environment_and_nonregular_files(self):
        root = test_workspaces.WorkspaceTests.prepared(self)
        (root / "src/link.php").symlink_to(self.checkout / "README.md")
        (root / "src/indirect").symlink_to(self.checkout / "src", target_is_directory=True)
        (root / "src/.env.local").write_text("secret")
        (root / "src/binary").write_bytes(b"\0\xff")
        os.mkfifo(root / "src/pipe")
        for path in ("../README.md", "/etc/passwd", ".git", "src/link.php", "src/indirect/Example.php",
                     "src/.env.local", "src/pipe", "src/binary"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.assess(sources=[{"path": path}])
        self.assertEqual([], self.requests)

    def test_scope_checked_before_evidence_is_sent_and_co_cannot_assess(self):
        own = self.api.artifacts.save("diagnostic.txt", content="retained diagnostic")
        ref = "artifact:" + str(own["artifact"]["id"])
        self.assess(sources=[{"reference": ref}])
        fixture_work(self.xo, [responsibility("Other", "docs")])
        foreign = API(self.state, "docs").artifacts.save("private.txt", content="other job evidence")
        with self.assertRaisesRegex(ValueError, "not available"):
            self.assess(sources=[{"reference": "artifact:" + str(foreign["artifact"]["id"])}])
        co = API(self.state, "co")
        self.assertNotIn("work_assess", {row["name"] for row in co.tools()})
        for sources in ([{"path": "src/Example.php"}], [{"reference": ref}]):
            with self.subTest(sources=sources), self.assertRaisesRegex(ValueError, "not available"):
                self.assess(sources=sources, api=co)
        from devtools.advice import Advice

        with self.assertRaisesRegex(ValueError, "CO relays"):
            Advice(self.store, "co").assess(sources=[{"reference": ref}], questions=[{"name": "fit", "instructions": "Fit?"}])
        with self.assertRaisesRegex(ValueError, "does not evaluate"):
            co.control.report("Accept it", evaluation={"reference": ref, "stage": "decision"})
        self.assertEqual(1, len(self.requests))

    def test_operation_evidence_uses_existing_scoped_reads_and_reports_partial(self):
        scope = self.api.control.snapshot()
        with self.store.connect() as db:
            ident = db.execute(
                "INSERT INTO operations(member,work_order,job,binding,action,arguments,state,result,created,updated) VALUES (?,?,?,?,?,?,'completed',?,?,?)",
                (self.api.member, scope["work_order"], scope["job"], canonical(scope), "work_check", "{}",
                 canonical({"diagnostic": "é" * 5000}), stamp(), stamp()),
            ).lastrowid
        result = self.assess(sources=[{"reference": f"operation:{ident}", "limit": 400}])
        source = result["results"][0]["source"]
        self.assertEqual("characters", source["offset_units"])
        self.assertEqual(400, source["next_offset"])
        self.assertTrue(source["partial"])

    def test_paused_and_rebound_work_rejects_advice(self):
        self.xo.call("steer", {"action": "pause", "work": "Feature"})
        with self.assertRaisesRegex(ValueError, "active current work"):
            self.assess()
        self.xo.call("steer", {"action": "resume", "work": "Feature"})

        def replace_scope(state, questions, model):
            self.api.control.unbind("coder")
            return answer(state, questions, model)

        self.provider.side_effect = replace_scope
        with self.assertRaisesRegex(ValueError, "active current work"):
            self.assess()

    def test_provider_failure_retains_no_fake_assessment_and_normal_work_still_works(self):
        self.provider.side_effect = ValueError("Jev is unavailable")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.assess()
        self.assertEqual("prepared", self.api.call("work_inspect", {})["workspace"])
        self.assertEqual([], self.api.artifacts.list(query="jev-")["artifacts"])
        self.assertEqual("unavailable", self.store.events(kind="jev_evaluation")["events"][0]["data"]["outcome"])

    def test_secrets_are_filtered_before_provider_and_unknown_model_is_rejected(self):
        root = test_workspaces.WorkspaceTests.prepared(self)
        (root / "src/Example.php").write_text("Bearer abcdefghi\nprivate-demo-key-12345")
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "private-demo-key-12345"}):
            self.assess()
        sent = json.dumps(self.requests)
        self.assertNotIn("abcdefghi", sent)
        self.assertNotIn("private-demo-key-12345", sent)
        self.configure({"model": "jev-latest"})
        with self.assertRaisesRegex(ValueError, "pinned"):
            self.assess()

    def test_invalid_questions_and_sources_do_not_call_provider(self):
        bad = [
            {"sources": [{"path": "src/Example.php", "reference": "artifact:1"}]},
            {"sources": [{}]},
            {"questions": [{"name": "a", "type": "choice", "instructions": "Select"}]},
            {"questions": [{"name": "a", "instructions": "Select", "levels": ["one", "two"]}]},
            {"questions": [{"name": "a", "type": "choice", "instructions": "Select", "options": ["same", "same"]}]},
            {"questions": [{"name": "a", "instructions": "First"}, {"name": "a", "instructions": "Second"}]},
            {"sources": [{"path": "src/Example.php", "limit": 8001}]},
        ]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.assess(**value)
        self.assertFalse(self.requests)

    def test_assignment_uses_current_jobs_runtime_evidence_and_does_not_allocate(self):
        defaults(self.state)
        team = json.loads((self.state / "team.json").read_text())
        team["runtime"] = True
        (self.state / "team.json").write_text(json.dumps(team))
        policy = json.loads((self.state / "roles.json").read_text())
        for profile in policy["profiles"].values():
            profile.update(binary="/bin/true", model="fixture-model", reasoning="high")
        (self.state / "roles.json").write_text(json.dumps(policy))
        vendors = json.loads((self.state / "vendors.json").read_text())
        vendors["vendors"]["openai"]["available"] = True
        (self.state / "vendors.json").write_text(json.dumps(vendors))
        self.configure({"profile_evidence": {"codex": "2026-09-28 fixture: passed representative PHP task"}})
        before = self.store.members()
        result = self.xo.call("assignment_advise", {"work": [responsibility("Feature"), responsibility("Review", "audit")]})
        self.assertEqual(before, self.store.members())
        self.assertEqual(1, len(self.requests))
        state = self.requests[0][0]
        self.assertEqual("Feature", state["current_jobs"][0]["title"])
        self.assertEqual({"codex"}, state["runtimes"]["coder"]["profiles"].keys())
        self.assertIn("representative", state["runtimes"]["coder"]["profiles"]["codex"]["evidence"])
        self.assertIsNone(result["recommendations"][0]["runtime"]["profile"])
        self.assertEqual("codex", result["recommendations"][0]["runtime"]["configured_default"])
        self.assertIn("operator policy", result["next"])
        with self.assertRaisesRegex(ValueError, "not available"):
            self.api.call("assignment_advise", {"work": [responsibility()]})

    def test_assignment_handles_fixed_team_and_reports_missing_performance_evidence(self):
        result = self.xo.call("assignment_advise", {"work": [responsibility()]})
        profiles = self.requests[0][0]["runtimes"]["coder"]["profiles"]
        self.assertEqual({"docs"}, profiles.keys())
        self.assertIn("No performance evidence", profiles["docs"]["evidence"])
        self.assertTrue(self.xo.call("assignment_advise", {"work": [responsibility()]})["cache_hit"])
        self.assertIsNone(result["recommendations"][0]["runtime"]["profile"])

    def retained(self, result):
        return json.loads(self.api.artifacts.read(int(result["evidence"].split(":")[1]), limit=256 * 1024)["content"])

    def test_replay_preserves_exact_sanitized_request_after_source_changes(self):
        root = test_workspaces.WorkspaceTests.prepared(self)
        (root / "src/Example.php").write_text("Uncommitted behavior; Bearer private-demo-key")
        result = self.assess()
        (root / "src/Example.php").write_text("Replacement behavior")
        saved = self.retained(result)
        state, questions, model = self.requests[-1]
        self.assertEqual({"state": state, "questions": questions, "model": model}, saved["request"])
        self.assertIn("Uncommitted behavior", json.dumps(saved))
        self.assertNotIn("private-demo-key", json.dumps(saved))
        current = self.api.control.snapshot()
        self.assertEqual({key: current[key] for key in saved["binding"]}, saved["binding"])
        self.assertNotIn("request", result)

    def test_scope_assessment_combines_sources_with_configured_rubric_and_invalidates_cache(self):
        root = test_workspaces.WorkspaceTests.prepared(self)
        (root / "src/Other.php").write_text("Other evidence")
        args = {"proposal": "Add logging while implementing the JSON response", "sources": [
            {"path": "src/Example.php"}, {"path": "src/Other.php"}]}
        first = self.api.call("work_assess", args)
        self.assertEqual("scope", first["purpose"])
        state, questions, _ = self.requests[-1]
        self.assertEqual(2, len(state["sources"]))
        self.assertEqual(load_policy()["scope"]["questions"], questions)
        self.assertTrue(self.api.call("work_assess", args)["cache_hit"])
        policy = load_policy()
        policy["scope"]["version"] += 1
        policy["scope"]["questions"]["scope"]["instructions"] += " Logging may be a separate proposal."
        (self.state / "custom-jev.json").write_text(json.dumps(policy))
        self.configure({"policy_file": "custom-jev.json"})
        changed = self.api.call("work_assess", args)
        self.assertNotEqual(first["fingerprint"], changed["fingerprint"])
        self.assertEqual(2, self.retained(changed)["policy"]["scope"]["version"])
        for bad in ({}, {"proposal": "x", "questions": [{"name": "x", "instructions": "x"}]}):
            with self.assertRaises(ValueError):
                self.api.call("work_assess", bad)

    def test_sensitive_rubric_identifiers_preserve_schema_and_scrub_text(self):
        policy = load_policy()
        secret = "private-rubric-secret"
        policy["scope"]["questions"] = {
            "password": {"type": "noul", "instructions": "Check " + secret},
            "api_key": {"type": "choice", "instructions": "Select a credential category",
                        "criteria": {"password": "Check Bearer secret-token", "token": secret}},
            "access_token": {"type": "score", "instructions": "Assess handling",
                             "criteria": ["Absent", "Includes " + secret]},
        }
        (self.state / "rubric.json").write_text(json.dumps(policy))
        self.configure({"policy_file": "rubric.json"})
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": secret}):
            result = self.api.call("work_assess", {"proposal": "Check credential handling"})
            cached = self.api.call("work_assess", {"proposal": "Check credential handling"})
        state, questions, model = self.requests[-1]
        self.assertEqual({"password", "api_key", "access_token"}, questions.keys())
        self.assertEqual("noul", questions["password"]["type"])
        self.assertEqual({"password", "token"}, questions["api_key"]["criteria"].keys())
        self.assertEqual("[REDACTED]", questions["api_key"]["criteria"]["token"])
        checked_response(answer(state, questions, model), questions, model)
        saved = self.retained(result)
        self.assertEqual(questions, saved["request"]["questions"])
        self.assertEqual(questions, saved["policy"]["scope"]["questions"])
        self.assertNotIn(secret, json.dumps(saved))
        self.assertNotIn("secret-token", json.dumps(saved))
        self.assertEqual(result["evidence"], cached["evidence"])
        self.assertTrue(cached["cache_hit"])
        self.assertEqual(1, self.provider.call_count)

    def test_feedback_links_decision_outcome_and_retries_without_changing_assignments(self):
        result = self.api.call("work_assess", {"proposal": "Add logging"})
        before = self.api.control.snapshot()
        args = {"kind": "recommendation", "text": "Keep logging as a separate proposal.",
                "evaluation": {"reference": result["evidence"], "stage": "decision", "label": "deferred"}}
        decision = self.xo.call("work_report", args)
        self.assertTrue(self.xo.call("work_report", args)["reused"])
        outcome = self.xo.call("work_report", {"kind": "result", "text": "JSON service complete; no extra logging.",
            "evaluation": {"reference": result["evidence"], "stage": "outcome", "decision": decision["reference"], "label": "useful"}})
        read = self.xo.call("work_context", {"reference": outcome["reference"]})
        self.assertEqual(decision["reference"], read["evaluation"]["decision"])
        self.assertEqual(before, self.api.control.snapshot())
        self.assertEqual(2, len(self.store.events(kind="jev_feedback")["events"]))
        with self.assertRaisesRegex(ValueError, "Command roles"):
            self.api.call("work_report", args)

    def test_feedback_rejects_stale_unregistered_and_mismatched_evaluations(self):
        first = self.api.call("work_assess", {"proposal": "Add logging"})
        args = {"text": "Decision", "evaluation": {"reference": first["evidence"], "stage": "decision"}}
        decision = self.xo.call("work_report", args)
        second = self.api.call("work_assess", {"proposal": "Add caching"})
        with self.assertRaisesRegex(ValueError, "same evaluation"):
            self.xo.call("work_report", {"text": "Outcome", "evaluation": {
                "reference": second["evidence"], "stage": "outcome", "decision": decision["reference"]}})
        self.xo.call("steer", {"action": "guide", "work": "Feature", "objective": "Different requirement"})
        with self.assertRaisesRegex(ValueError, "changed assignment"):
            self.xo.call("work_report", args | {"text": "New decision based on stale evidence"})
        fake = self.api.artifacts.save("fake.json", content=json.dumps(self.retained(first)))
        with self.assertRaisesRegex(ValueError, "recorded Jev"):
            self.xo.call("work_report", {"text": "Fake", "evaluation": {
                "reference": f"artifact:{fake['artifact']['id']}", "stage": "decision"}})

    def test_existing_database_upgrade_preserves_reports_and_retry_identity(self):
        args = {"text": "Existing report"}
        report = self.api.call("work_report", args)
        with self.store.connect() as db:
            db.execute("ALTER TABLE work_updates DROP COLUMN evaluation")
            db.execute("PRAGMA user_version=9")
        upgraded = Store(self.state)
        with upgraded.connect() as db:
            self.assertEqual(SCHEMA_VERSION, db.execute("PRAGMA user_version").fetchone()[0])
        retry = API(self.state, "coder").call("work_report", args)
        self.assertEqual(report["reference"], retry["reference"])
        self.assertTrue(retry["reused"])

    def test_invalid_operator_policy_fails_before_provider(self):
        policy = load_policy()
        policy["transport"]["timeout"] = float("nan")
        (self.state / "bad.json").write_text(json.dumps(policy))
        self.configure({"policy_file": "bad.json"})
        with self.assertRaisesRegex(ValueError, "transport"):
            self.api.call("work_assess", {"proposal": "Add logging"})
        self.assertFalse(self.requests)


class AdviceReviewTests(unittest.TestCase):
    setUp_base = test_workspaces.WorkspaceTests.setUp
    prepared = test_workspaces.WorkspaceTests.prepared
    setUp = test_delivery.DeliveryTests.setUp
    auditor = test_delivery.DeliveryTests.auditor
    configure = AdviceTests.configure

    def test_auditor_assesses_submitted_snapshot_not_producers_unsubmitted_source(self):
        self.configure({})
        audit = self.auditor()
        (self.workspace / "src/Example.php").write_text("Unsubmitted changes\n")
        with patch("devtools.advice.Jev.evaluate", side_effect=answer) as provider:
            result = audit.call("work_assess", {
                "sources": [{"path": "src/Example.php"}],
                "questions": [{"name": "review", "instructions": "Is the delivered implementation relevant?"}],
            })
        source = provider.call_args.args[0]["sources"][0]
        self.assertEqual("Delivered implementation\n", source["content"])
        self.assertEqual(self.head, result["results"][0]["source"]["revision"])
        self.assertNotIn("work_save", {row["name"] for row in audit.tools()})


class JevTransportTests(unittest.TestCase):
    def setUp(self):
        self.questions = {"q": {"type": "noul", "instructions": "Is it relevant?"}}
        self.key = patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-secret-never-log"})
        self.key.start()
        self.addCleanup(self.key.stop)
        self.opener = MagicMock()
        self.factory = patch("devtools.jev.urllib.request.build_opener", return_value=self.opener)
        self.factory.start()
        self.addCleanup(self.factory.stop)

    def response(self, value):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = value if isinstance(value, bytes) else json.dumps(value).encode()
        return response

    def test_official_endpoint_auth_bounded_io_and_typed_response(self):
        self.opener.open.return_value = self.response(answer({}, self.questions))
        result = Jev().evaluate({"text": "source"}, self.questions)
        request = self.opener.open.call_args.args[0]
        self.assertEqual("https://api.typesafe.ai/v1/systemone", request.full_url)
        self.assertEqual("Bearer test-secret-never-log", request.get_header("Authorization"))
        self.assertEqual(8, self.opener.open.call_args.kwargs["timeout"])
        self.assertEqual(0.8, result["answers"]["q"]["noul"])

    def test_documented_score_wire_format_and_configured_timeout(self):
        questions = {"frustration": {"type": "score", "instructions": "How frustrated?",
                                     "criteria": ["Calm", "Frustrated", "Very angry"]}}
        value = {"model": MODEL, "answers": {"frustration": {
            "type": "score", "score": 1.05, "legend": {"0": "Calm", "1": "Frustrated", "2": "Very angry"},
            "probabilities": {"0": 0.0, "1": 0.95, "2": 0.05}, "confidence": 0.92}},
            "usage": {"input_tokens": 304, "output_tokens": 18}}
        self.opener.open.return_value = self.response(value)
        settings = load_policy()["transport"] | {"timeout": 3}
        response = Jev(settings).evaluate("Help! My payouts have been failing for 3 days.", questions)
        self.assertEqual(value, response)
        self.assertEqual(3, self.opener.open.call_args.kwargs["timeout"])
        wire = json.loads(self.opener.open.call_args.args[0].data)
        self.assertEqual({"state", "model", "questions"}, wire.keys())
        value["answers"]["frustration"].pop("legend")
        with self.assertRaisesRegex(ValueError, "legend"):
            checked_response(value, questions, MODEL)

    def test_rate_limit_retry_is_bounded_and_error_body_never_leaks(self):
        limited = urllib.error.HTTPError("url", 429, "secret", {"Retry-After": "0.5"}, io.BytesIO(b"secret input"))
        self.opener.open.side_effect = [limited, self.response(answer({}, self.questions))]
        with patch("devtools.jev.time.sleep") as sleep:
            Jev().evaluate({}, self.questions)
            sleep.assert_called_once_with(0.5)
        self.opener.open.side_effect = urllib.error.HTTPError("url", 529, "secret", {"Retry-After": "60"}, io.BytesIO(b"secret"))
        with patch("devtools.jev.time.sleep") as sleep, self.assertRaisesRegex(ValueError, "HTTP 529") as caught:
            Jev().evaluate({}, self.questions)
        sleep.assert_not_called()
        self.assertNotIn("secret", str(caught.exception))

    def test_timeout_redirect_and_oversize_fail_without_external_details(self):
        for error in [socket.timeout("secret"), urllib.error.URLError("secret"),
                      urllib.error.HTTPError("url", 302, "secret", {}, io.BytesIO(b"secret"))]:
            self.opener.open.side_effect = error
            with self.subTest(error=error), self.assertRaises(ValueError) as caught:
                Jev().evaluate({}, self.questions)
            self.assertNotIn("secret", str(caught.exception))
        self.opener.open.side_effect = None
        self.opener.open.return_value = self.response(b"x" * (MAX_RESPONSE + 1))
        with self.assertRaisesRegex(ValueError, "size limit"):
            Jev().evaluate({}, self.questions)
        self.opener.open.reset_mock()
        with self.assertRaisesRegex(ValueError, "input budget"):
            Jev().evaluate("x" * 30000, self.questions)
        self.opener.open.assert_not_called()

    def test_missing_key_invalid_json_unknown_options_nan_and_model_mismatch(self):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}), self.assertRaisesRegex(ValueError, "TYPESAFE_API_KEY"):
            Jev().evaluate({}, self.questions)
        self.opener.open.return_value = self.response(b"not JSON")
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            Jev().evaluate({}, self.questions)
        questions = {"q": {"type": "choice", "instructions": "Choose", "criteria": {"a": None, "b": None}}}
        for change in [
            {"choice": "invented"}, {"confidence": float("nan")}, {"probabilities": {"a": 0.2, "b": 0.2}},
            {"probabilities": {"a": 1, "invented": 0}},
        ]:
            value = answer({}, questions)
            value["answers"]["q"].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                checked_response(value, questions, MODEL)
        for value in [answer({}, questions) | {"model": "jev-latest"},
                      answer({}, questions) | {"answers": {}}, answer({}, questions) | {"usage": {}}]:
            with self.assertRaises(ValueError):
                checked_response(value, questions, MODEL)
