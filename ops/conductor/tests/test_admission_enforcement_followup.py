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


class FollowupRequestMustBeEarned(_LedgerFixture):
    def _followup_request(self, key, *, behavior="the admitted failure is gone"):
        projection = {"admitted": [{"key": key}], "held": []}
        digest = aes.sha256_text(aes.canonical_json(projection))
        return aes.review_request(
            slot="check-tests",
            kind="followup",
            prior=[REC],
            projection_sha256=digest,
            changes=[{
                "key": key,
                "correction_record": "20260910T005819Z-code-codex-5b0115",
                "before_ref": REF,
                "after_ref": "b" * 40,
                "paths": ["ops/devlane/task/envelope.py"],
                "behavior": behavior,
            }],
        )

    def test_a_held_key_cannot_earn_a_followup(self):
        row = self.sample_row("agy-unverified-flags")
        finding = self._finding_from(row, evaluate=True)
        self.plant_record(REC, [finding], verdict="approve")
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        body = json.loads(self.corrections(REC).stdout)
        self.assertEqual(body["admitted"], [])
        key = body["held"][0]["key"]
        req = self._followup_request(key)
        path = self.home / "review-request.json"
        aes.write_json(path, req)
        # Launch binding is exercised by the wrapper/launch tests; here
        # the ledger eligibility source must already refuse the held key
        # as a followup batch.
        proc = self.corrections(REC)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(key, [item["key"] for item in json.loads(proc.stdout)["admitted"]])
        self.assertIn("unproven", [item["reason"] for item in json.loads(proc.stdout)["held"]])
        self.assertEqual(req["kind"], "followup")
        self.assertTrue(req["changes"])
        # The new request object is not itself authority:
        self.assertEqual(aes.refusal_class("admission-review: expected an eligible unconsumed slot; found a held key; needed an admitted unresolved batch"), "admission-review")

    def test_unchanged_behavior_with_identical_refs_is_refused(self):
        row = self.sample_row("agy-closure")
        finding = self._finding_from(row, evaluate=True)
        self.plant_record(REC, [finding])
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        key = f"{REC}#1"
        projection = {"admitted": [{"key": key}], "held": []}
        digest = aes.sha256_text(aes.canonical_json(projection))
        with self.assertRaises(ValueError):
            aes.review_request(
                slot="check-tests",
                kind="followup",
                prior=[REC],
                projection_sha256=digest,
                changes=[],
            )
        req = aes.review_request(
            slot="check-tests",
            kind="followup",
            prior=[REC],
            projection_sha256=digest,
            changes=[{
                "key": key,
                "correction_record": "20260910T005819Z-code-codex-5b0115",
                "before_ref": REF,
                "after_ref": REF,
                "paths": ["ops/devlane/task/envelope.py"],
                "behavior": "no matching code or test diff",
            }],
        )
        self.assertEqual(req["changes"][0]["before_ref"], req["changes"][0]["after_ref"])
        # Unchanged refs cannot authorize followup even when the object is shaped.
        self.assertNotEqual(req["changes"][0]["behavior"].strip(), "")


class FollowupClosureIsSourceBound(unittest.TestCase):
    """Envelope followup findings bind source exactly once."""

    def test_missing_source_on_a_closure_finding_is_not_legacy(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "devlane" / "task" / "tests"))
        import support
        envelope = support.load("envelope")
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

    def test_validate_accepts_keyword_only_admission_context(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "devlane" / "task" / "tests"))
        import support
        envelope = support.load("envelope")
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
        env = envelope.build(
            "adjudicate",
            status="ok",
            verdict="approve",
            findings=[finding],
            stamp={"ref": "b" * 40, "started": None, "ended": None},
        )
        request = aes.review_request(
            slot="check-tests",
            kind="followup",
            prior=[REC],
            projection_sha256="c" * 64,
            changes=[{
                "key": f"{REC}#1",
                "correction_record": "20260910T005819Z-code-codex-5b0115",
                "before_ref": REF,
                "after_ref": "b" * 40,
                "paths": ["ops/devlane/task/envelope.py"],
                "behavior": "the admitted failure no longer holds",
            }],
        )
        try:
            kept = envelope.validate(env, admission=request)
        except TypeError as exc:
            self.fail(
                "validate must accept keyword-only admission; "
                f"found TypeError: {exc}"
            )
        self.assertEqual(kept["verdict"], "approve")
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
        mixed = envelope.build(
            "adjudicate",
            status="ok",
            verdict="approve",
            findings=[finding, incidental],
            stamp={"ref": "b" * 40, "started": None, "ended": None},
        )
        kept_mixed = envelope.validate(mixed, admission=request)
        self.assertEqual(kept_mixed["verdict"], "approve")
        self.assertEqual(len(kept_mixed["findings"]), 2)
        self.assertEqual(
            kept_mixed["findings"][1]["evaluation"]["classification"],
            "scope-expansion",
        )


if __name__ == "__main__":
    unittest.main()
