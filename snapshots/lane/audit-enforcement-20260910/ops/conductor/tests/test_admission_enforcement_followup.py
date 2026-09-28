"""Earned followup and complete supplied-key closure.

Written from FINDING-ADMISSION.md §Review eligibility. findings.py
corrections is the established eligibility source. --review-request is
the new launch binding. Intended reds: held/unrelated keys still
dispatch; incomplete closure still accepts; incidental findings become
new conditions.

Preserve original independent ledger tests byte-for-byte.
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


class CorrectionsProjectionRemainsTheEligibilitySource(_LedgerFixture):
    """GREEN: existing corrections CLI, empty lists, held vs admitted."""

    def test_admitted_and_held_keys_are_explicit_including_empty_admitted(self):
        row = self.sample_row("agy-unverified-flags")
        finding = self._finding_from(row, evaluate=True)
        self.assertEqual(finding["evaluation"]["classification"], "unproven")
        self.plant_record(REC, [finding], verdict="approve")
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(REC)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout)
        self.assertEqual(body["admitted"], [])
        self.assertEqual(aes.retain_list(body["admitted"], default=["x"]), [])
        self.assertEqual(body["held"][0]["reason"], "unproven")

    def test_a_demonstrated_defect_is_admitted_once(self):
        row = self.sample_row("agy-closure")
        finding = self._finding_from(row, evaluate=True)
        self.assertEqual(finding["evaluation"]["classification"], "demonstrated-defect")
        self.plant_record(REC, [finding])
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(REC)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout)
        self.assertEqual(len(body["admitted"]), 1)
        self.assertEqual(body["admitted"][0]["key"], f"{REC}#1")
        self.assertEqual(body["held"], [])


class FollowupRequestMustBeEarned(ls._TempLaunch):
    """Launch/wrapper eligibility: held and unchanged keys refuse; earned passes."""

    def _plant_changed_path(self, bound):
        before = self.root_sha
        path = self.repo / bound.test_rel
        text = path.read_text(encoding="utf-8") + "# corrected-behavior\n"
        path.write_text(text, encoding="utf-8")
        self.assertIn("# corrected-behavior", path.read_text(encoding="utf-8"))
        after = self._commit("code: change bound fixture behavior")
        self.ref = after
        self.assertNotEqual(before, after)
        return before, after

    def test_an_admitted_changed_key_with_a_followup_slot_starts_once(self):
        bound = aes.attach_bound(self)
        before, after = self._plant_changed_path(bound)
        key = f"{aes.BOUND_REVIEW_ID}#1"
        projection = {"admitted": [{"key": key}], "held": []}
        req_path = self.home / "followup-request.json"
        aes.write_followup_request(
            req_path,
            slot="security-re",
            prior=[aes.BOUND_REVIEW_ID],
            projection=projection,
            key=key,
            correction_record=aes.BOUND_CORRECTION_ID,
            before_ref=before,
            after_ref=after,
            paths=[bound.test_rel],
            behavior="the admitted empty-list substitution no longer holds",
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
        self.assertNotIn("unrecognized arguments", text.lower(), text)
        self.assertEqual(code, 0, text)
        rec = self.read_record()
        review = rec["brief"]["admission"]["review"]
        self.assertEqual(review["kind"], "followup")
        self.assertEqual(review["slot"], "security-re")
        self.assertEqual(review["changes"][0]["after_ref"], after)
        self.assertNotEqual(review["changes"][0]["before_ref"], after)
        self.assertTrue(self.start_witness.is_file())

    def test_a_held_key_cannot_earn_a_followup(self):
        bound = aes.attach_bound(self)
        before, after = self._plant_changed_path(bound)
        key = f"{aes.BOUND_REVIEW_ID}#1"
        projection = {
            "admitted": [],
            "held": [{"key": key, "reason": "unproven"}],
        }
        req_path = self.home / "followup-request.json"
        aes.write_followup_request(
            req_path,
            slot="security-re",
            prior=[aes.BOUND_REVIEW_ID],
            projection=projection,
            key=key,
            correction_record=aes.BOUND_CORRECTION_ID,
            before_ref=before,
            after_ref=after,
            paths=[bound.test_rel],
            behavior="held unproven key is not an admitted unresolved batch",
        )
        self.assertEqual(projection["admitted"], [])
        code, out, err = self.dispatch(self.argv_for(
            job="security-audit",
            harness="grok",
            stage="review",
            extra=aes.bound_extra(
                bound, "security-audit", request_path=req_path,
            ),
        ))
        text = self.combined(out, err)
        self.assertNotIn("unrecognized arguments", text.lower(), text)
        self.assert_not_started()
        self.assert_wire_refusal(
            code, out, err,
            ident="admission-review",
            phrases=["admission-review", "held"],
        )

    def test_unchanged_behavior_with_identical_refs_is_refused(self):
        bound = aes.attach_bound(self)
        key = f"{aes.BOUND_REVIEW_ID}#1"
        projection = {"admitted": [{"key": key}], "held": []}
        req_path = self.home / "followup-request.json"
        req, _digest = aes.write_followup_request(
            req_path,
            slot="security-re",
            prior=[aes.BOUND_REVIEW_ID],
            projection=projection,
            key=key,
            correction_record=aes.BOUND_CORRECTION_ID,
            before_ref=self.ref,
            after_ref=self.ref,
            paths=[bound.test_rel],
            behavior="no matching code or test diff",
        )
        self.assertEqual(req["changes"][0]["before_ref"], req["changes"][0]["after_ref"])
        code, out, err = self.dispatch(self.argv_for(
            job="security-audit",
            harness="grok",
            stage="review",
            extra=aes.bound_extra(
                bound, "security-audit", request_path=req_path,
            ),
        ))
        text = self.combined(out, err)
        self.assertNotIn("unrecognized arguments", text.lower(), text)
        self.assert_not_started()
        self.assert_wire_refusal(
            code, out, err,
            ident="admission-review",
            phrases=["admission-review"],
        )


class FollowupClosureIsSourceBound(unittest.TestCase):
    """Envelope followup findings bind source exactly once."""

    def _envelope(self):
        import importlib.util
        path = (
            Path(__file__).resolve().parents[2]
            / "devlane" / "task" / "tests" / "support.py"
        )
        spec = importlib.util.spec_from_file_location("task_admission_support", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.load("envelope")

    def test_missing_source_on_a_closure_finding_is_not_legacy(self):
        envelope = self._envelope()
        evaluation = {
            "classification": "unproven",
            "scope_sha256": "a" * 64,
            "requirement": None,
            "trigger": None,
            "failure": None,
            "evidence": None,
            "refutation": "the requested claim no longer holds",
            "source": None,
            "ruling": "REJECTED",
        }
        with self.assertRaises(envelope.EnvelopeError):
            envelope.finding(
                "p2",
                "ops/devlane/task/envelope.py",
                "requested claim closed",
                reproduce="echo closed",
                evaluation=evaluation,
            )

    def test_validate_complete_versus_partial_supplied_key_closure(self):
        envelope = self._envelope()
        finding = envelope.finding(
            "p2",
            "ops/devlane/task/envelope.py",
            "requested claim closed",
            reproduce="echo closed",
            evaluation={
                "classification": "unproven",
                "scope_sha256": "a" * 64,
                "requirement": None,
                "trigger": None,
                "failure": None,
                "evidence": None,
                "refutation": "counter-evidence at the new ref",
                "source": {"key": f"{REC}#1", "sha256": "a" * 64},
                "ruling": "REJECTED",
            },
        )
        request = aes.review_request(
            slot="security-re",
            kind="followup",
            prior=[REC],
            projection_sha256="c" * 64,
            changes=[{
                "key": f"{REC}#1",
                "correction_record": aes.BOUND_CORRECTION_ID,
                "before_ref": REF,
                "after_ref": "b" * 40,
                "paths": ["ops/devlane/task/envelope.py"],
                "behavior": "the admitted failure no longer holds",
            }],
        )
        env = envelope.build(
            "adjudicate",
            status="ok",
            verdict="approve",
            findings=[finding],
            stamp={"ref": "b" * 40, "started": None, "ended": None},
        )
        env["job"] = "adversarial-review"
        try:
            kept = envelope.validate(env, admission=request)
        except TypeError as exc:
            self.fail(
                "validate must accept keyword-only admission; "
                f"found TypeError: {exc}"
            )
        self.assertEqual(kept["verdict"], "approve")
        two_key = aes.review_request(
            slot="security-re",
            kind="followup",
            prior=[REC],
            projection_sha256="c" * 64,
            changes=[
                request["changes"][0],
                {
                    "key": f"{REC}#2",
                    "correction_record": aes.BOUND_CORRECTION_ID,
                    "before_ref": REF,
                    "after_ref": "b" * 40,
                    "paths": ["ops/devlane/task/envelope.py"],
                    "behavior": "second admitted failure no longer holds",
                },
            ],
        )
        try:
            with self.assertRaises(envelope.EnvelopeError):
                envelope.validate(env, admission=two_key)
        except TypeError as exc:
            self.fail(
                "validate must accept keyword-only admission; "
                f"found TypeError: {exc}"
            )
        incidental = envelope.finding(
            "p3",
            "ops/other.py",
            "incidental expansion",
            reproduce=None,
            evaluation={
                "classification": "scope-expansion",
                "scope_sha256": "a" * 64,
                "requirement": None,
                "trigger": None,
                "failure": None,
                "evidence": None,
                "refutation": "new capability outside this request",
                "source": None,
                "ruling": None,
            },
        )
        mixed = dict(env)
        mixed["findings"] = [finding, incidental]
        mixed["counts"] = {"p1": 0, "p2": 1, "p3": 1, "opinions": 1}
        try:
            kept_mixed = envelope.validate(mixed, admission=request)
        except TypeError as exc:
            self.fail(
                "validate must accept keyword-only admission; "
                f"found TypeError: {exc}"
            )
        self.assertEqual(kept_mixed["verdict"], "approve")
        self.assertEqual(len(kept_mixed["findings"]), 2)
        self.assertEqual(
            kept_mixed["findings"][1]["evaluation"]["classification"],
            "scope-expansion",
        )


if __name__ == "__main__":
    unittest.main()
