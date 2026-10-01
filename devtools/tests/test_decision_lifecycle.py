"""Decision retention preserves credential privacy and concurrent idempotency."""

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from devtools.api import API
from devtools.decisions import Decisions
from devtools.failures import Failure, failure_info
from devtools.launch import initialize


class DecisionLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        workspace = root / "workspace"
        workspace.mkdir()
        self.state = root / "state"
        initialize(self.state, workspace, ["owner:external", "xo:external", "investigator:external"])
        self.secret = "fixture-file-only-credential-728392"
        credential = self.state / "provider.key"
        credential.write_text(self.secret)
        credential.chmod(0o600)
        team = json.loads((self.state / "team.json").read_text())
        team["project"] = {"configuration_file": "policy.json"}
        (self.state / "team.json").write_text(json.dumps(team))
        (self.state / "policy.json").write_text(json.dumps({"version": 1, "project": {
            "features": {"completion": True, "selection": False},
            "connection": {"credential": {"file": str(credential)}},
        }}))
        self.operator = API(self.state, "owner", operator=True)
        self.store = self.operator.store
        self.order = self.operator.work.work_order_create(
            title="Decision retention", objective="Retain safe evidence", done_when="One current decision"
        )["work_order"]["id"]
        self.operator.control.bind("owner", "co", self.order)
        self.operator.control.bind("xo", "xo", self.order, reports_to="owner")

    @staticmethod
    def answer(state, questions, model):
        return {"model": model, "answers": {name: {"type": "noul", "noul": 0.75} for name in questions},
                "usage": {"input_tokens": 1, "output_tokens": 1}}

    def pending(self, *, state=None, instructions="Is the retained proof complete?", sources=()):
        try:
            Decisions(self.store, "xo").select(
                "completion", state or {"proof": "Current fixture result"},
                {"complete": {"type": "noul", "instructions": instructions}}, sources,
                identity="current-fixture-proof",
            )
        except Failure as error:
            self.assertEqual("decision_pending", failure_info(error)["reason"])
            return failure_info(error)["details"]["decision"]
        self.fail("Ambiguous evaluation must await investigation")

    def row(self, ident):
        with self.store.connect() as db:
            return dict(db.execute("SELECT * FROM decisions WHERE id=?", (ident,)).fetchone())

    def test_file_credential_is_removed_from_retained_request_and_arbitrator_packet(self):
        state = {"proof": "Untrusted source included " + self.secret}
        instructions = "Judge the proof and disregard this copied value: " + self.secret
        with patch("devtools.advice.Jev.evaluate", side_effect=self.answer) as provider:
            ident = self.pending(state=state, instructions=instructions,
                                 sources=[{"description": "Source metadata " + self.secret}])
        # Existing provider redaction must also hold for the new retained decision path.
        self.assertNotIn(self.secret, json.dumps(provider.call_args.args))
        row = self.row(ident)
        self.assertNotIn(self.secret, row["request"])
        packet = API(self.state, row["arbitrator"]).call("work_context", {})["decision"]
        self.assertNotIn(self.secret, json.dumps(packet))
        assessment = self.operator.artifacts.read(int(row["evidence"].split(":")[1]), limit=256 * 1024)
        self.assertFalse(self.secret in assessment["content"], "Retained assessment leaked the fixture file credential")

    def test_resolution_reason_redacts_file_credential_in_record_artifact_and_telemetry(self):
        with patch("devtools.advice.Jev.evaluate", side_effect=self.answer):
            ident = self.pending()
        row = self.row(ident)
        API(self.state, row["arbitrator"]).call("decision_resolve", {
            "decisions": {"complete": True}, "reason": "Inspected source containing " + self.secret,
            "evidence": [row["evidence"]],
        })
        resolved = self.row(ident)
        self.assertEqual("resolved", resolved["state"])
        self.assertNotIn(self.secret, resolved["resolution"])
        artifact = self.operator.artifacts.read(int(resolved["evidence"].split(":")[1]), limit=256 * 1024)
        self.assertFalse(self.secret in artifact["content"], "Resolution artifact leaked the fixture file credential")
        self.assertNotIn(self.secret, json.dumps(self.store.events(kind="decision_resolved")))

    def test_sensitive_looking_question_identifier_keeps_its_typed_packet(self):
        with patch("devtools.advice.Jev.evaluate", side_effect=self.answer):
            with self.assertRaises(Failure) as pending:
                Decisions(self.store, "xo").select(
                    "completion", {"proof": "Password handling was measured"},
                    {"password": {"type": "noul", "instructions": "Does the measured password behavior meet the requirement?"}},
                    identity="password-proof",
                )
        self.assertEqual("decision_pending", failure_info(pending.exception)["reason"])
        row = self.row(failure_info(pending.exception)["details"]["decision"])
        packet = API(self.state, row["arbitrator"]).call("work_context", {})["decision"]
        self.assertEqual(["password"], packet["question_names"])
        self.assertEqual("noul", packet["questions"]["password"]["type"])

    def test_invalid_provider_details_do_not_expose_file_credential_to_arbitrator(self):
        error = Failure("Provider returned invalid evidence", category="evaluation_invalid", reason="invalid_response",
                        details={"provider_detail": "Echoed source value " + self.secret})
        with patch("devtools.advice.Jev.evaluate", side_effect=error):
            ident = self.pending()
        row = self.row(ident)
        self.assertNotIn(self.secret, row["failure"])
        packet = API(self.state, row["arbitrator"]).call("work_context", {})["decision"]
        self.assertEqual("evaluation_invalid", packet["failure"]["category"])
        self.assertNotIn(self.secret, json.dumps(packet))

    def test_concurrent_identical_requests_share_evaluation_and_arbitrator(self):
        entered, release, second_started = threading.Event(), threading.Event(), threading.Event()

        def evaluate(state, questions, model):
            entered.set()
            if not release.wait(5):
                raise AssertionError("Concurrent decision fixture did not release evaluation")
            return self.answer(state, questions, model)

        def second():
            second_started.set()
            return self.pending()

        with patch("devtools.advice.Jev.evaluate", side_effect=evaluate) as provider:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.pending)
                try:
                    self.assertTrue(entered.wait(5))
                    other = pool.submit(second)
                    self.assertTrue(second_started.wait(5))
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=10), other.result(timeout=10))
        self.assertEqual(1, provider.call_count)
        with self.store.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM decisions WHERE state='pending'").fetchone()[0])
            self.assertEqual(1, db.execute("SELECT count(*) FROM role_assignments WHERE role='arbitrator'").fetchone()[0])

    def test_stale_queue_snapshot_cannot_reallocate_cancelled_investigation(self):
        with patch("devtools.advice.Jev.evaluate", side_effect=self.answer):
            ident = self.pending()
        selected = Decisions(self.store, "xo")
        row = self.row(ident)
        # A watcher already captured this pending id when newer evidence supersedes it.
        selected.prune("completion", {"state": {"proof": "Newer fixture result"}}, None, "new-proof")
        self.assertEqual("stale", self.row(ident)["state"])
        with self.assertRaises(Failure) as rejected:
            selected._pending(ident)
        self.assertEqual("decision_stale", failure_info(rejected.exception)["reason"])
        with self.store.connect() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM member_bindings WHERE assignment_id=?", (row["assignment"],)).fetchone())
            self.assertEqual("cancelled", db.execute("SELECT status FROM role_assignments WHERE id=?", (row["assignment"],)).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
