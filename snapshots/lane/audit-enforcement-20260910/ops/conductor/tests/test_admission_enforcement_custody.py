"""Custody, producer independence, legacy records, fixture omissions.

Written from FINDING-ADMISSION.md matrix rows Admission fixture
omissions and Custody, producer and legacy. Original ledger tests are
not modified. Intended reds: same-producer evidence still selects
correction; a raw mixed report is accepted as test-author input; a
legacy unevaluated row seeds a fresh correction.

Existing corrections/import read behaviour stays. Fresh dispatch of a
followup that uses legacy evidence is the advancement refusal.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from test_finding_admission_ledger import REC, REF, _LedgerFixture

DISPATCH_TESTS = Path(__file__).resolve().parents[2] / "devlane" / "dispatch" / "tests"
if str(DISPATCH_TESTS) not in sys.path:
    sys.path.insert(0, str(DISPATCH_TESTS))
import admission_enforcement_support as aes  # noqa: E402
import launch_support as ls  # noqa: E402


class EstablishedCustodySurfaces(_LedgerFixture):
    """GREEN: empty admitted, unknown keys, live store untouched."""

    def test_unknown_record_is_admission_binding_and_stdout_stays_empty(self):
        proc = self.corrections("no-such-record")
        self.assert_refusal(proc, "admission-binding")
        self.assertEqual((proc.stdout or "").strip(), "")

    def test_explicit_empty_admitted_is_not_substituted(self):
        row = self.sample_row("agy-unverified-flags")
        finding = self._finding_from(row, evaluate=True)
        self.plant_record(REC, [finding], verdict="approve")
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        body = json.loads(self.corrections(REC).stdout)
        self.assertEqual(body["admitted"], [])
        self.assertEqual(len(body["admitted"]), 0)

    def test_legacy_unevaluated_rows_remain_readable_on_import(self):
        row = self.sample_row("agy-closure")
        finding = self._finding_from(row, evaluate=False)
        self.assertNotIn("evaluation", finding)
        self.plant_record(REC, [finding], verdict="changes")
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        exported = self.export_rows()
        match = [item for item in exported if item["key"] == f"{REC}#1"]
        self.assertEqual(len(match), 1, exported)
        self.assertEqual(match[0]["claim"], row["claim"])
        self.assertEqual(match[0].get("evaluations") or [], [])


class SameProducerAndLegacyCannotAdvance(_LedgerFixture):
    def test_a_raw_report_is_not_a_permitted_test_author_projection(self):
        row = self.sample_row("agy-closure")
        finding = self._finding_from(row, evaluate=True)
        path = self.plant_record(
            REC,
            [finding],
            extra_outputs=[("SKEPTIC.md", b"raw mixed skeptic report\n")],
        )
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        body = json.loads(self.corrections(REC).stdout)
        self.assertTrue(body["admitted"])
        raw = self.dispatch_job_dir(REC) / "out" / "SKEPTIC.md"
        self.assertTrue(raw.is_file())
        admitted = body["admitted"][0]
        dumped = json.dumps(admitted)
        self.assertNotIn("raw mixed skeptic report", dumped)
        self.assertNotIn(str(raw), dumped)
        self.assertTrue(path.is_file())

    def test_a_key_outside_the_supplied_batch_refuses_the_whole_read(self):
        row = self.sample_row("agy-closure")
        finding = self._finding_from(row, evaluate=True)
        self.plant_record(REC, [finding])
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(REC, "20260908T000000Z-review-grok-dead01")
        self.assert_refusal(proc, "admission-binding")
        self.assertEqual((proc.stdout or "").strip(), "")


class LegacyEvidenceCannotAuthorizeFreshDispatch(ls._TempLaunch):
    """Fresh launch/acceptance using legacy unevaluated evidence refuses."""

    def test_followup_of_a_legacy_unevaluated_key_is_refused(self):
        bound = aes.attach_bound(self)
        rec_dir = self.repo / ".dev" / "records" / "dispatches"
        rec_dir.mkdir(parents=True, exist_ok=True)
        legacy_id = aes.BOUND_REVIEW_ID
        finding = {
            "severity": "p2",
            "where": "ops/devlane/task/envelope.py",
            "claim": "legacy unevaluated finding",
            "reproduce": "echo legacy",
        }
        rec = {
            "id": legacy_id,
            "lane": "dev",
            "stage": "review",
            "unit": "work",
            "lineage": {"branch": self.lineage, "base_sha": self.root_sha},
            "follows": [],
            "job": "security-audit",
            "role": "read",
            "dispatched_by": ls.AGENT,
            "at": {"launched": "2026-09-09T13:00:00Z", "closed": "2026-09-09T13:01:00Z"},
            "snapshot": {
                "mode": "whole",
                "ref_name": self.ref,
                "ref_sha": self.ref,
                "behind_tip": 0,
                "root": str(self.home / "legacy-snap"),
            },
            "harness": {
                "name": "claude",
                "version": "1.0.5",
                "isolation": {
                    "mechanism": "home",
                    "observed": {"unresolved": "behavioural probe has not run"},
                    "home": str(self.home / "legacy-home"),
                },
                "sandbox": "always-approve",
                "containment": "policy",
                "argv": ["claude"],
            },
            "model": {
                "requested": "claude-opus",
                "effort_requested": None,
                "effort_argv": [],
                "ran": "claude-opus",
                "read_from": None,
            },
            "session": {
                "id": "00000000-0000-4000-8000-0000000000b2",
                "stream": None,
                "stream_sha256_at_close": None,
            },
            "brief": {
                "template": {"path": "ops/devlane/task/jobs.json", "sha256": "c" * 64},
                "scope": aes.BOUND_SCOPE_TEXT,
                "inputs": [],
                "sha256": bound.scope_sha,
                "bytes": len(aes.BOUND_SCOPE_TEXT),
            },
            "caps": {"cap-out": 500000, "source": "wires.py"},
            "overrides": [],
            "attempts": [],
            "result": {
                "envelope": {
                    "job": "security-audit",
                    "status": "ok",
                    "verdict": "changes",
                    "counts": {"p1": 0, "p2": 1, "p3": 0, "opinions": 0},
                    "findings": [finding],
                    "artifacts": {},
                    "spend": {"harness": "claude", "total": 0, "out": 0, "runs": 1},
                    "stamp": {"ref": self.ref, "started": None, "ended": None},
                    "note": None,
                }
            },
            "status": "closed",
        }
        self.assertNotIn("evaluation", finding)
        aes.write_json(rec_dir / f"{legacy_id}.json", rec)
        key = f"{legacy_id}#1"
        req_path = self.home / "followup-request.json"
        aes.write_followup_request(
            req_path,
            slot="security-re",
            prior=[legacy_id],
            projection={"admitted": [{"key": key}], "held": []},
            key=key,
            correction_record=aes.BOUND_CORRECTION_ID,
            before_ref=self.root_sha,
            after_ref=self.ref,
            paths=[bound.test_rel],
            behavior="legacy unevaluated key cannot close",
        )
        code, out, err = self.dispatch(self.argv_for(
            job="security-audit",
            harness="grok",
            stage="review",
            extra=aes.bound_extra(
                bound, "security-audit", request_path=req_path,
            ),
        ))
        text = self.combined(out, err)
        self.assertNotIn(
            "unrecognized arguments",
            text.lower(),
            f"missing flags are not legacy-custody proof: {text!r}",
        )
        self.assert_not_started()
        self.assertIn("admission-", text.lower())
        self.assertEqual(code, ls.REFUSAL_EXIT, text)


class VerificationProvenanceCannotBeWorkerProse(unittest.TestCase):
    """New verification receipts need nonempty producers from retained diffs."""

    def recmod(self):
        path = (
            Path(__file__).resolve().parents[2]
            / "devlane" / "dispatch" / "record.py"
        )
        import importlib.util
        spec = importlib.util.spec_from_file_location("custody_record", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _minimum(self):
        return {
            "id": "20260826T000000Z-plan-grok-abc123",
            "lane": "dev",
            "stage": "plan",
            "unit": "work",
            "lineage": {"branch": "work", "base_sha": "a" * 40},
            "follows": [],
            "job": "plan",
            "role": "read",
            "dispatched_by": "Custody Tester <custody@example.invalid>",
            "at": {"launched": "2026-08-26T00:00:00Z", "closed": None},
            "snapshot": {
                "mode": "whole",
                "ref_name": "HEAD",
                "ref_sha": "b" * 40,
                "behind_tip": 0,
                "root": "/tmp/jobs/id/snapshot",
            },
            "harness": {
                "name": "grok",
                "version": "1.0.5",
                "isolation": {
                    "mechanism": "home",
                    "env": {"GROK_HOME": "/tmp/jobs/id/home/grok"},
                    "home": "/tmp/jobs/id/home/grok",
                    "auth_files": ["auth.json"],
                    "store": "/tmp/jobs/id/home/grok/sessions",
                    "observed": {"unresolved": "behavioural probe has not run"},
                },
                "sandbox": "plan",
                "containment": "policy",
                "argv": ["grok", "-s", "uuid"],
            },
            "model": {
                "requested": "alias-requested",
                "effort_requested": None,
                "effort_argv": [],
                "ran": None,
                "read_from": None,
            },
            "session": {
                "id": "00000000-0000-4000-8000-000000000001",
                "stream": None,
                "stream_sha256_at_close": None,
            },
            "brief": {
                "template": {
                    "path": "ops/devlane/task/jobs.json",
                    "sha256": "c" * 64,
                },
                "scope": "pin",
                "inputs": [],
                "sha256": "d" * 64,
                "bytes": 3,
            },
            "caps": {"cap-out": 500000, "source": "wires.py"},
            "overrides": [],
            "attempts": [],
            "result": None,
            "status": "launched",
        }

    def test_empty_producers_are_not_fixture_proof(self):
        record = self.recmod()
        payload = self._minimum()
        payload["verification"] = [{
            "dispatch": payload["id"],
            "attempt": 1,
            "phase": "fixture",
            "work_order": "WO-custody",
            "declaration_sha256": "a" * 64,
            "scope_sha256": "b" * 64,
            "ref": "b" * 40,
            "tests": [{"path": "t.py", "sha256": "c" * 64, "producers": []}],
            "tests_sha256": "d" * 64,
            "executor": {"path": "ops/devlane/dispatch/launch.py", "sha256": "e" * 64},
            "by": payload["dispatched_by"],
            "started": "2026-09-09T00:00:00Z",
            "ended": "2026-09-09T00:00:01Z",
            "commands": [{
                "id": "fx",
                "command": "true",
                "inputs": [],
                "exit": 0,
                "timed_out": False,
                "stdout": {"path": "/tmp/out", "sha256": "f" * 64},
                "stderr": {"path": "/tmp/err", "sha256": "0" * 64},
            }],
            "status": "ok",
            "reason": None,
        }]
        self.assertEqual(payload["verification"][0]["tests"][0]["producers"], [])
        with self.assertRaises(Exception) as caught:
            record.validate(payload)
        text = str(caught.exception).lower()
        self.assertTrue(
            "producer" in text or "verification" in text or "admission" in text,
            text,
        )


class IndependentProducerIsRequired(_LedgerFixture):
    def test_same_harness_and_model_cannot_close_a_dispute(self):
        original = self._finding_from(self.sample_row("agy-closure"), evaluate=True)
        self.plant_record(
            REC,
            [original],
            harness="grok",
            model_ran="grok-4.6",
        )
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        ruling = dict(original["evaluation"])
        ruling.update(
            {
                "source": {"key": f"{REC}#1", "sha256": aes.sha256_text(aes.canonical_json(original))},
                "ruling": "REJECTED",
                "classification": "unproven",
                "requirement": None,
                "trigger": None,
                "failure": None,
                "evidence": None,
                "refutation": "same producer cannot settle its own finding",
            }
        )
        adj_id = "20260908T070000Z-adjudicate-grok-same01"
        self.plant_record(
            adj_id,
            [{
                "severity": "p2",
                "where": original["where"],
                "claim": "rejected by the same producer",
                "reproduce": original["reproduce"],
                "evaluation": ruling,
            }],
            job="adjudicate",
            harness="grok",
            model_ran="grok-4.6",
        )
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(REC, adj_id)
        if proc.returncode == 0:
            body = json.loads(proc.stdout)
            held = {item["key"]: item["reason"] for item in body["held"]}
            self.assertIn(f"{REC}#1", held)
            self.assertEqual(held[f"{REC}#1"], "disputed")
        else:
            self.assert_refusal(proc)
            self.assertIn("admission-", (proc.stderr or "").lower())


if __name__ == "__main__":
    unittest.main()
