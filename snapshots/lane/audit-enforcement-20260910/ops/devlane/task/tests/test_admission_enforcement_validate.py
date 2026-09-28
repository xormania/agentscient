"""Task validate(admission=) for followup closure context.

Written from FINDING-ADMISSION.md: extend task validation with
keyword-only admission=None. Default preserves legacy validation.
Canonical acceptance supplies launcher-bound context.

Intended red: TypeError on admission=, or a source-bearing REVIEW
closure without a retained followup request authorizing close.
Legacy adjudication with source/ruling still parses under default.
"""

from __future__ import annotations

import unittest

import support

envelope = support.load("envelope")

STAMP = {
    "ref": "a3ac203a88a0a67feff407f3cba8adb9a656d245",
    "started": "2026-09-09T00:00:00Z",
    "ended": "2026-09-09T00:00:01Z",
}
SCOPE = "46bf342676ee1f746f0144a679e6157ddde817d79faf8def0f66827e2549eb40"
KEY = "20260908T063559Z-review-claude-6eb510#1"
KEY_TWO = "20260908T063559Z-review-claude-6eb510#2"


def _eval(*, source=None, ruling=None, classification="unproven"):
    return {
        "classification": classification,
        "scope_sha256": SCOPE,
        "requirement": None,
        "trigger": None,
        "failure": None,
        "evidence": None,
        "refutation": "followup closure context check",
        "source": source,
        "ruling": ruling,
    }


def _source(key=KEY, digest="a" * 64):
    return {"key": key, "sha256": digest}


def _review_env(findings, *, verdict="approve"):
    env = envelope.build(
        "adjudicate",
        status="ok",
        verdict=verdict,
        findings=findings,
        stamp=STAMP,
    )
    env["job"] = "adversarial-review"
    return env


def _followup_request(keys=None):
    import sys
    from pathlib import Path

    dispatch_tests = Path(__file__).resolve().parents[2] / "dispatch" / "tests"
    if str(dispatch_tests) not in sys.path:
        sys.path.insert(0, str(dispatch_tests))
    import admission_enforcement_support as aes

    keys = list(keys or [KEY])
    return aes.review_request(
        slot="security-re",
        kind="followup",
        prior=["20260908T063559Z-review-claude-6eb510"],
        projection_sha256="c" * 64,
        changes=[
            {
                "key": key,
                "correction_record": "20260909T140000Z-code-codex-aa41c3",
                "before_ref": "a" * 40,
                "after_ref": STAMP["ref"],
                "paths": ["ops/devlane/task/envelope.py"],
                "behavior": "the admitted failure no longer holds",
            }
            for key in keys
        ],
    )


class LegacyValidateWithoutAdmissionStays(unittest.TestCase):
    def test_omitted_admission_still_validates_a_legacy_review(self):
        finding = envelope.finding(
            "p2",
            "ops/devlane/task/envelope.py",
            "legacy four-field finding",
            reproduce="echo legacy",
        )
        env = envelope.build(
            "adversarial-review",
            status="ok",
            verdict="changes",
            findings=[finding],
            stamp=STAMP,
        )
        kept = envelope.validate(env)
        self.assertNotIn("evaluation", kept["findings"][0])
        self.assertEqual(kept["verdict"], "changes")

    def test_source_bearing_adjudicate_parses_under_default_admission(self):
        finding = envelope.finding(
            "p2",
            "ops/devlane/task/envelope.py",
            "independent ruling of a supplied key",
            reproduce="echo ruled",
            evaluation=_eval(source=_source(), ruling="REJECTED"),
        )
        env = envelope.build(
            "adjudicate",
            status="ok",
            verdict="approve",
            findings=[finding],
            stamp=STAMP,
        )
        kept = envelope.validate(env)
        self.assertEqual(kept["job"], "adjudicate")
        self.assertEqual(kept["findings"][0]["evaluation"]["ruling"], "REJECTED")
        self.assertEqual(kept["verdict"], "approve")
        self.assertEqual(kept["findings"][0]["evaluation"]["source"]["key"], KEY)


class AdmissionContextIsKeywordOnly(unittest.TestCase):
    def test_validate_accepts_admission_none_as_legacy(self):
        finding = envelope.finding(
            "p2",
            "ops/devlane/task/envelope.py",
            "legacy four-field finding",
            reproduce="echo legacy",
        )
        env = envelope.build(
            "adversarial-review",
            status="ok",
            verdict="changes",
            findings=[finding],
            stamp=STAMP,
        )
        try:
            kept = envelope.validate(env, admission=None)
        except TypeError as exc:
            self.fail(
                "validate must accept keyword-only admission=None; "
                f"found TypeError: {exc}"
            )
        self.assertEqual(kept["verdict"], "changes")

    def test_a_source_bearing_review_without_request_cannot_close(self):
        finding = envelope.finding(
            "p2",
            "ops/devlane/task/envelope.py",
            "requested claim closed",
            reproduce="echo closed",
            evaluation=_eval(source=_source(), ruling="REJECTED"),
        )
        env = _review_env([finding])
        try:
            envelope.validate(env, admission=None)
        except TypeError as exc:
            self.fail(
                "validate must accept keyword-only admission; "
                f"found TypeError: {exc}"
            )
        except envelope.EnvelopeError:
            return
        self.fail(
            "a source-bearing review closure without its retained "
            "followup request cannot authorize closure"
        )

    def test_complete_supplied_key_closure_is_accepted(self):
        request = _followup_request([KEY])
        finding = envelope.finding(
            "p2",
            "ops/devlane/task/envelope.py",
            "requested claim closed",
            reproduce="echo closed",
            evaluation=_eval(source=_source(), ruling="REJECTED"),
        )
        env = _review_env([finding])
        try:
            kept = envelope.validate(env, admission=request)
        except TypeError as exc:
            self.fail(
                "validate must accept keyword-only admission; "
                f"found TypeError: {exc}"
            )
        self.assertEqual(kept["verdict"], "approve")
        self.assertEqual(kept["findings"][0]["evaluation"]["source"]["key"], KEY)

    def test_missing_supplied_key_ruling_is_refused(self):
        request = _followup_request([KEY, KEY_TWO])
        finding = envelope.finding(
            "p2",
            "ops/devlane/task/envelope.py",
            "only one of two requested keys closed",
            reproduce="echo closed",
            evaluation=_eval(source=_source(), ruling="REJECTED"),
        )
        env = _review_env([finding])
        try:
            with self.assertRaises(envelope.EnvelopeError):
                envelope.validate(env, admission=request)
        except TypeError as exc:
            self.fail(
                "validate must accept keyword-only admission; "
                f"found TypeError: {exc}"
            )

    def test_duplicate_supplied_key_ruling_is_refused(self):
        request = _followup_request([KEY])
        first = envelope.finding(
            "p2",
            "ops/devlane/task/envelope.py",
            "requested claim closed",
            reproduce="echo closed",
            evaluation=_eval(source=_source(), ruling="REJECTED"),
        )
        second = envelope.finding(
            "p2",
            "ops/devlane/task/envelope.py",
            "duplicate closure of the same key",
            reproduce="echo closed again",
            evaluation=_eval(source=_source(), ruling="REJECTED"),
        )
        env = _review_env([first, second])
        try:
            with self.assertRaises(envelope.EnvelopeError):
                envelope.validate(env, admission=request)
        except TypeError as exc:
            self.fail(
                "validate must accept keyword-only admission; "
                f"found TypeError: {exc}"
            )

    def test_incidental_expansion_stays_visible_without_changing_verdict(self):
        request = _followup_request([KEY])
        closed = envelope.finding(
            "p2",
            "ops/devlane/task/envelope.py",
            "requested claim closed",
            reproduce="echo closed",
            evaluation=_eval(source=_source(), ruling="REJECTED"),
        )
        incidental = envelope.finding(
            "p3",
            "ops/other.py",
            "incidental expansion",
            reproduce=None,
            evaluation=_eval(
                source=None,
                ruling=None,
                classification="scope-expansion",
            ),
        )
        env = _review_env([closed])
        env["findings"] = [closed, incidental]
        env["counts"]["p3"] = 1
        env["counts"]["opinions"] = 1
        try:
            kept = envelope.validate(env, admission=request)
        except TypeError as exc:
            self.fail(
                "validate must accept keyword-only admission; "
                f"found TypeError: {exc}"
            )
        self.assertEqual(kept["verdict"], "approve")
        self.assertEqual(len(kept["findings"]), 2)
        self.assertEqual(
            kept["findings"][1]["evaluation"]["classification"],
            "scope-expansion",
        )
        self.assertIsNone(kept["findings"][1]["evaluation"]["source"])
