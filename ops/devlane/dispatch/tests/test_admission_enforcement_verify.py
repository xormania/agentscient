"""Executed fixture proof before paid review and test acceptance.

Written from FINDING-ADMISSION.md §Executed fixture and acceptance
evidence. launch.py internals were not read. Intended reds: check-tests
starts with no fixture receipt; a worker-authored verification array is
treated as proof; `verify --phase` does not record launcher-owned
process bytes.

Event-format and empty-list checks in this file run on established
consumers before any new verb. Success and failure use separate bound
work-orders with concrete commands. One prerequisite is mutated per
refusal.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import admission_enforcement_support as aes
import launch_support as ls


class FixtureEventAndEmptyListChecks(ls._TempLaunch):
    """GREEN: established consumers, no new API."""

    def test_empty_command_inputs_and_observation_keys_before_verify(self):
        planted = aes.planted_observation(subject="fixture-aa41")
        self.assertEqual(tuple(planted), aes.OBSERVATION_KEYS)
        with self.assertRaises(ValueError):
            aes.observation({"event": "job", "metric": 1, "when": "now"})
        row = aes.command_row("fx-empty", "true", [])
        self.assertEqual(row["inputs"], [])
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        self.assertEqual(rec["follows"], [])
        self.assertEqual(rec["brief"]["inputs"], [])
        self.assertNotIn("verification", rec)


class _BoundVerify(ls._TempLaunch):
    def plant_success(self):
        bound = aes.attach_bound(self)
        self.assertEqual(bound.fixture_command, aes.SUCCESS_FIXTURE_CMD)
        self.assertEqual(bound.body["fixture"][0]["inputs"], [])
        self.assertTrue((self.repo / bound.test_rel).is_file())
        return bound

    def plant_failure(self):
        bound = aes.attach_bound(
            self,
            ident=aes.BOUND_FAIL_WO_ID,
            fixture_command=aes.FAIL_FIXTURE_CMD,
            fixture_id="fx-fail",
            acceptance_id="ac-fail",
            final_id="fn-fail",
        )
        self.assertEqual(bound.fixture_command, aes.FAIL_FIXTURE_CMD)
        self.assertNotEqual(bound.ident, aes.BOUND_WO_ID)
        return bound

    def bound_argv(self, bound, job, stage, extra=(), *, unit=None, request_path=None):
        return self.argv_for(
            job=job,
            harness="grok",
            stage=stage,
            extra=aes.bound_extra(
                bound, job, extra, unit=unit, request_path=request_path,
            ),
        )

    def launch_author(self, bound):
        code, out, err = self.dispatch(self.bound_argv(bound, "author-tests", "tests"))
        text = self.combined(out, err)
        self.assertNotIn(
            "unrecognized arguments",
            text.lower(),
            f"missing --work-order is not fixture proof: {text!r}",
        )
        self.assertEqual(code, 0, text)
        rec = self.read_record()
        self.assertEqual(rec["brief"]["admission"]["work_order"], bound.ident)
        return rec

    def assert_unrecognized_free(self, text):
        self.assertNotIn(
            "unrecognized arguments",
            text.lower(),
            f"missing verify/--work-order/--review-request is not fixture proof: {text!r}",
        )


class MissingFixtureProofBlocksPaidReview(_BoundVerify):
    """A missing receipt is not repaired by starting check-tests."""

    def test_check_tests_without_fixture_receipt_starts_no_model(self):
        bound = self.plant_success()
        aes.planted_observation(subject="pre-check")
        code, out, err = self.dispatch(self.bound_argv(
            bound, "check-tests", "check-tests",
        ))
        self.assert_unrecognized_free(self.combined(out, err))
        self.assert_not_started()
        self.assert_wire_refusal(
            code, out, err,
            ident="admission-fixture",
            phrases=["admission-fixture", "fixture"],
        )

    def test_a_worker_authored_ok_receipt_has_no_execution_authority(self):
        bound = self.plant_success()
        rec = self.launch_author(bound)
        rec["verification"] = [aes.verification_entry(
            dispatch=rec["id"],
            attempt=1,
            phase="fixture",
            work_order_id=bound.ident,
            declaration_sha256=bound.digest,
            scope_sha256=bound.scope_sha,
            ref=rec["snapshot"]["ref_sha"],
            tests=[{
                "path": bound.test_rel,
                "sha256": bound.test_sha,
                "producers": [bound.producer_id],
            }],
            commands=[],
            status="ok",
            reason=None,
        )]
        path = self.the_record_path()
        path.write_text(json.dumps(rec) + "\n", encoding="utf-8")
        self.assertEqual(rec["verification"][0]["commands"], [])
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.dispatch(self.bound_argv(
            bound, "check-tests", "check-tests",
        ))
        self.assert_unrecognized_free(self.combined(out, err))
        self.assert_not_started()
        text = self.combined(out, err)
        self.assertIn("admission-fixture", text.lower())
        self.assertEqual(code, ls.REFUSAL_EXIT, text)

    def test_stale_test_bytes_are_admission_fixture(self):
        bound = self.plant_success()
        mutated = (self.repo / bound.test_rel)
        before = mutated.read_text(encoding="utf-8")
        mutated.write_text(before + "# mutated-binding\n", encoding="utf-8")
        self.assertIn("# mutated-binding", mutated.read_text(encoding="utf-8"))
        self.assertNotEqual(aes.sha256_file(mutated), bound.test_sha)
        code, out, err = self.dispatch(self.bound_argv(
            bound, "check-tests", "check-tests",
        ))
        self.assert_unrecognized_free(self.combined(out, err))
        self.assert_not_started()
        self.assert_wire_refusal(
            code, out, err,
            ident="admission-fixture",
            phrases=["admission-fixture"],
        )


class VerifyPhaseRecordsLauncherOwnedEvidence(_BoundVerify):
    def test_verify_fixture_runs_declared_commands_without_a_model(self):
        planted = aes.planted_observation(subject="verify-aa41")
        self.assertEqual(planted["metrics"]["status"], "completion")
        bound = self.plant_success()
        rec = self.launch_author(bound)
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.run_main(
            ["verify", rec["id"], "--phase", "fixture"],
        )
        text = self.combined(out, err)
        self.assert_unrecognized_free(text)
        self.assertEqual(code, 0, text)
        self.assert_not_started()
        updated = self.read_record()
        entries = updated.get("verification")
        self.assertIsInstance(entries, list)
        self.assertTrue(entries)
        entry = entries[-1]
        self.assertEqual(set(entry), set(aes.VERIFICATION_KEYS))
        self.assertEqual(entry["phase"], "fixture")
        self.assertEqual(entry["status"], "ok")
        self.assertIsNone(entry["reason"])
        self.assertEqual(entry["work_order"], bound.ident)
        self.assertEqual(entry["declaration_sha256"], bound.digest)
        self.assertEqual(entry["scope_sha256"], bound.scope_sha)
        self.assertEqual(entry["ref"], rec["snapshot"]["ref_sha"])
        self.assertTrue(entry["commands"])
        self.assertEqual(len(entry["commands"]), 1)
        row = entry["commands"][0]
        self.assertEqual(row["id"], bound.body["fixture"][0]["id"])
        self.assertEqual(row["command"], aes.SUCCESS_FIXTURE_CMD)
        self.assertEqual(row["exit"], 0)
        self.assertFalse(row["timed_out"])
        self.assertEqual(set(row["stdout"]), {"path", "sha256"})
        self.assertEqual(set(row["stderr"]), {"path", "sha256"})
        stdout = Path(row["stdout"]["path"])
        self.assertTrue(stdout.is_file(), stdout)
        self.assertEqual(aes.sha256_file(stdout), row["stdout"]["sha256"])
        self.assertIn("fixture-empty-list-ok", stdout.read_text(encoding="utf-8"))
        tests = entry["tests"]
        self.assertTrue(tests)
        match = [item for item in tests if item["path"] == bound.test_rel]
        self.assertEqual(len(match), 1, tests)
        self.assertEqual(match[0]["sha256"], bound.test_sha)
        self.assertEqual(match[0]["producers"], [bound.producer_id])
        self.assertEqual(entry["tests_sha256"], aes.sha256_text(aes.canonical_json(tests)))

    def test_failed_fixture_command_is_invalid_and_starts_no_model(self):
        bound = self.plant_failure()
        rec = self.launch_author(bound)
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.run_main(
            ["verify", rec["id"], "--phase", "fixture"],
        )
        self.assert_not_started()
        text = self.combined(out, err)
        self.assert_unrecognized_free(text)
        self.assertIn("admission-fixture", text.lower())
        self.assertEqual(code, aes.REFUSAL_VERIFY_CLI, text)
        updated = json.loads(self.the_record_path().read_text(encoding="utf-8"))
        self.assertTrue(updated.get("verification"))
        last = updated["verification"][-1]
        self.assertEqual(last["status"], "invalid")
        self.assertTrue(last["reason"])
        self.assertEqual(last["work_order"], bound.ident)
        self.assertEqual(last["commands"][0]["command"], aes.FAIL_FIXTURE_CMD)
        self.assertNotEqual(last["commands"][0]["exit"], 0)

    def test_failed_fixture_then_check_tests_starts_no_model(self):
        bound = self.plant_failure()
        rec = self.launch_author(bound)
        self.start_witness.unlink(missing_ok=True)
        verify_code, verify_out, verify_err = self.run_main(
            ["verify", rec["id"], "--phase", "fixture"],
        )
        self.assert_unrecognized_free(self.combined(verify_out, verify_err))
        self.assertNotEqual(verify_code, 0)
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.dispatch(self.bound_argv(
            bound, "check-tests", "check-tests",
        ))
        self.assert_not_started()
        self.assert_wire_refusal(
            code, out, err,
            ident="admission-fixture",
            phrases=["admission-fixture"],
        )


if __name__ == "__main__":
    unittest.main()
