"""Executed fixture proof before paid review and test acceptance.

Written from FINDING-ADMISSION.md §Executed fixture and acceptance
evidence. launch.py internals were not read. Intended reds: check-tests
starts with no fixture receipt; a worker-authored verification array is
treated as proof; `verify --phase` does not record launcher-owned
process bytes.

Event-format and empty-list checks in this file run on established
consumers before any new verb.
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


class MissingFixtureProofBlocksPaidReview(ls._TempLaunch):
    """A missing receipt is not repaired by starting check-tests."""

    def _scope_input(self):
        path = self.home / "owner-scope.md"
        path.write_text("scope for fixture proof\n", encoding="utf-8")
        return path

    def test_check_tests_without_fixture_receipt_starts_no_model(self):
        aes.planted_observation(subject="pre-check")
        code, out, err = self.dispatch(self.argv_for(
            job="check-tests",
            harness="grok",
            stage="check-tests",
            extra=["--input", str(self._scope_input())],
        ))
        self.assert_not_started()
        self.assert_wire_refusal(
            code, out, err,
            ident="admission-fixture",
            phrases=["admission-fixture", "fixture"],
        )

    def test_a_worker_authored_ok_receipt_has_no_execution_authority(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        rec["verification"] = [{
            "dispatch": rec["id"],
            "attempt": 1,
            "phase": "fixture",
            "work_order": "WO-forged",
            "declaration_sha256": "a" * 64,
            "scope_sha256": "b" * 64,
            "ref": rec["snapshot"]["ref_sha"],
            "tests": [{"path": "t.py", "sha256": "c" * 64, "producers": ["x"]}],
            "tests_sha256": "d" * 64,
            "executor": {"path": "launch.py", "sha256": "e" * 64},
            "by": ls.AGENT,
            "started": "2026-09-09T00:00:00Z",
            "ended": "2026-09-09T00:00:01Z",
            "commands": [],
            "status": "ok",
            "reason": None,
        }]
        path = self.the_record_path()
        path.write_text(json.dumps(rec) + "\n", encoding="utf-8")
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.dispatch(self.argv_for(
            job="check-tests",
            harness="grok",
            stage="check-tests",
            extra=["--input", str(self._scope_input())],
        ))
        self.assert_not_started()
        text = self.combined(out, err)
        self.assertIn("admission-fixture", text.lower())
        self.assertEqual(code, ls.REFUSAL_EXIT, text)
        self.assertEqual(
            rec["verification"][0]["commands"],
            [],
            "empty command result array never passes",
        )


class VerifyPhaseRecordsLauncherOwnedEvidence(ls._TempLaunch):
    def test_verify_fixture_runs_declared_commands_without_a_model(self):
        planted = aes.planted_observation(subject="verify-aa41")
        self.assertEqual(planted["metrics"]["status"], "completion")
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.run_main(
            ["verify", rec["id"], "--phase", "fixture"],
        )
        text = self.combined(out, err)
        self.assertNotIn(
            "unrecognized arguments",
            text.lower(),
            f"missing verify verb is not fixture proof: {text!r}",
        )
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
        self.assertTrue(entry["commands"])
        for row in entry["commands"]:
            self.assertEqual(row["exit"], 0)
            self.assertFalse(row["timed_out"])
            self.assertEqual(set(row["stdout"]), {"path", "sha256"})
            self.assertEqual(set(row["stderr"]), {"path", "sha256"})
            stdout = Path(row["stdout"]["path"])
            self.assertTrue(stdout.is_file(), stdout)
            self.assertEqual(aes.sha256_file(stdout), row["stdout"]["sha256"])

    def test_failed_fixture_command_is_invalid_and_starts_no_model(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.run_main(
            ["verify", rec["id"], "--phase", "fixture"],
        )
        self.assert_not_started()
        text = self.combined(out, err)
        self.assertIn("admission-fixture", text.lower())
        self.assertEqual(code, aes.REFUSAL_VERIFY_CLI, text)
        updated = json.loads(self.the_record_path().read_text(encoding="utf-8"))
        if updated.get("verification"):
            self.assertEqual(updated["verification"][-1]["status"], "invalid")
            self.assertTrue(updated["verification"][-1]["reason"])


if __name__ == "__main__":
    unittest.main()
