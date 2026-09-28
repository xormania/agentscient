"""Task validate(admission=) for followup closure context.

Written from FINDING-ADMISSION.md: extend task validation with
keyword-only admission=None. Default preserves legacy validation.
Canonical acceptance supplies launcher-bound context.

Intended red: TypeError on admission=, or a source-bearing closure
without a retained followup request authorizing close.
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

    def test_a_source_bearing_closure_without_request_cannot_close(self):
        finding = envelope.finding(
            "p2",
            "ops/devlane/task/envelope.py",
            "requested claim closed",
            reproduce="echo closed",
            evaluation=_eval(
                source={
                    "key": "20260908T063559Z-review-claude-6eb510#1",
                    "sha256": "a" * 64,
                },
                ruling="REJECTED",
            ),
        )
        env = envelope.build(
            "adjudicate",
            status="ok",
            verdict="approve",
            findings=[finding],
            stamp=STAMP,
        )
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


if __name__ == "__main__":
    unittest.main()
