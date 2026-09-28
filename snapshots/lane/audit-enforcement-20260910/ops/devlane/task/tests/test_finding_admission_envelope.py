"""Finding-admission envelope: evaluation shape, duties, verdicts.

Written from ops/devlane/task/FINDING-ADMISSION.md and the owner scope
(in/owner-scope.md). envelope.py internals were not read. Each case pins
a promised caller-facing outcome:

  A1  evaluation is optional; absence is legacy, never demonstrated
  A2  explicit null is invalid; the object is closed
  A3  demonstrated-defect needs requirement, trigger, failure, evidence
  A4  reproduction vs execution-path reproduce rules
  A5  counts stay a raw tally; opinions is not admission
  A6  completed reviews: changes iff any demonstrated-defect
  A7  incomplete review cannot approve; partial findings are retained
  A8  invalid evidence is refused, not repaired
  A9  a documentation or test finding can be a demonstrated-defect

Intended reds on the unchanged implementation: evaluation is dropped by
build() or refused by validate() as an extra finding key; finding() has
no evaluation argument; ENVELOPE_SCHEMA names only the four fields.
A TypeError from the new keyword is reported as a failed assertion, not
left as a collection error.
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
CLAIM = "the closure gate refuses an undeclared WORKER_HARNESSES read"
WHERE = "ops/conductor/tools/laneconf.py closure()"
REPRO = (
    "python3 ops/conductor/tools/laneconf.py closure; "
    "observed: undeclared read, exit 1"
)


def _four(severity="p2", *, reproduce=REPRO, where=WHERE, claim=CLAIM):
    return envelope.finding(severity, where, claim, reproduce=reproduce)


def _eval(
    classification,
    *,
    requirement=None,
    trigger=None,
    failure=None,
    evidence=None,
    refutation="checked reachability against the agreed scope",
    source=None,
    ruling=None,
    extra=None,
):
    body = {
        "classification": classification,
        "scope_sha256": SCOPE,
        "requirement": requirement,
        "trigger": trigger,
        "failure": failure,
        "evidence": evidence,
        "refutation": refutation,
        "source": source,
        "ruling": ruling,
    }
    if extra:
        body.update(extra)
    return body


def _defect(**kwargs):
    defaults = dict(
        requirement=(
            "closure() refuses undeclared reads; "
            "ops/conductor/tools/laneconf.py"
        ),
        trigger="WORKER_HARNESSES absent from tracked conf, get() reader present",
        failure="expected exit 0; found undeclared read and exit 1",
        evidence={"kind": "reproduction", "details": "ran: " + REPRO},
        refutation=(
            "current docstring-only tree does not trip _reads; "
            "the amendment still names the reader against live closure"
        ),
    )
    defaults.update(kwargs)
    return _eval("demonstrated-defect", **defaults)


def _unproven(**kwargs):
    defaults = dict(
        requirement=None,
        trigger=None,
        failure=None,
        evidence=None,
        refutation=(
            "agy --help was not measured; missing evidence that the "
            "flag spellings are wrong"
        ),
    )
    defaults.update(kwargs)
    return _eval("unproven", **defaults)


def _expansion(**kwargs):
    defaults = dict(
        requirement=None,
        trigger=None,
        failure=None,
        evidence=None,
        refutation=(
            "exhaustive-match-or-refuse in every helper is a new "
            "guarantee outside agreed scope"
        ),
    )
    defaults.update(kwargs)
    return _eval("scope-expansion", **defaults)


def _with_eval(finding, evaluation):
    planted = dict(finding)
    planted["evaluation"] = evaluation
    return planted


def _build(findings, *, verdict="changes", status="ok", note=None, job=None):
    kwargs = dict(
        job=job or "adversarial-review",
        status=status,
        verdict=verdict,
        findings=findings,
        stamp=STAMP,
    )
    if note is not None:
        kwargs["note"] = note
    return envelope.build(**kwargs)


class EvaluationIsOptionalAndClosed(unittest.TestCase):
    """A1/A2 — absent is legacy; null and extra keys refuse."""

    def test_omitted_evaluation_stays_a_four_field_legacy_finding(self):
        env = _build([_four()], verdict="changes")
        finding = env["findings"][0]
        self.assertEqual(
            list(finding),
            ["severity", "where", "claim", "reproduce"],
        )
        self.assertNotIn("evaluation", finding)
        envelope.validate(env)

    def test_finding_accepts_keyword_only_evaluation(self):
        evaluation = _unproven()
        try:
            got = envelope.finding(
                "p2",
                WHERE,
                CLAIM,
                reproduce=REPRO,
                evaluation=evaluation,
            )
        except TypeError as exc:
            self.fail(
                "finding() must accept keyword-only evaluation; "
                f"found TypeError: {exc}"
            )
        self.assertEqual(got["evaluation"], evaluation)
        self.assertEqual(got["severity"], "p2")

    def test_explicit_null_evaluation_is_invalid(self):
        try:
            envelope.finding(
                "p2",
                WHERE,
                CLAIM,
                reproduce=REPRO,
                evaluation=None,
            )
        except TypeError as exc:
            self.fail(
                "finding() must refuse explicit null evaluation as "
                f"EnvelopeError, not TypeError: {exc}"
            )
        except envelope.EnvelopeError:
            return
        planted = _with_eval(_four(), None)
        with self.assertRaises(envelope.EnvelopeError):
            _build([planted])

    def test_build_preserves_a_valid_unproven_evaluation(self):
        evaluation = _unproven()
        env = _build([_with_eval(_four(), evaluation)], verdict="approve")
        kept = env["findings"][0]
        self.assertIn(
            "evaluation",
            kept,
            "build dropped evaluation while normalizing the finding",
        )
        self.assertEqual(kept["evaluation"], evaluation)
        envelope.validate(env)

    def test_an_extra_evaluation_key_is_refused(self):
        evaluation = _unproven(extra={"guess": "not-a-field"})
        planted = _with_eval(_four(), evaluation)
        self.assertIn("guess", planted["evaluation"])
        with self.assertRaises(envelope.EnvelopeError):
            _build([planted])

    def test_an_extra_finding_key_beside_evaluation_is_refused(self):
        env = _build([_with_eval(_four(), _unproven())], verdict="approve")
        kept = env["findings"][0]
        self.assertIn(
            "evaluation",
            kept,
            "build dropped evaluation while normalizing the finding",
        )
        kept["priority"] = "admit-anyway"
        self.assertIn("priority", kept)
        with self.assertRaises(envelope.EnvelopeError):
            envelope.validate(env)

    def test_blank_refutation_is_refused(self):
        evaluation = _unproven(refutation="   ")
        planted = _with_eval(_four(), evaluation)
        with self.assertRaises(envelope.EnvelopeError):
            _build([planted])


class DemonstratedDefectRequiresFourDuties(unittest.TestCase):
    """A3/A4/A8/A9 — duties, reproduce kinds, no repair, docs/tests."""

    def test_a_valid_reproduction_defect_is_kept(self):
        evaluation = _defect()
        env = _build([_with_eval(_four(), evaluation)])
        kept = env["findings"][0]
        self.assertIn(
            "evaluation",
            kept,
            "build dropped evaluation while normalizing the finding",
        )
        self.assertEqual(kept["evaluation"]["classification"], "demonstrated-defect")
        self.assertEqual(kept["evaluation"]["evidence"]["kind"], "reproduction")
        self.assertEqual(env["verdict"], "changes")

    def test_missing_requirement_refuses_a_demonstrated_defect(self):
        evaluation = _defect(requirement=None)
        planted = _with_eval(_four(), evaluation)
        self.assertIsNone(planted["evaluation"]["requirement"])
        with self.assertRaises(envelope.EnvelopeError):
            _build([planted])

    def test_execution_path_permits_a_null_reproduce(self):
        evaluation = _defect(
            evidence={
                "kind": "execution-path",
                "details": (
                    "entry closure(); input key absent from tracked conf; "
                    "branch _reads; failing unread/undeclared check; "
                    "expected exit 0, actual exit 1"
                ),
            },
        )
        finding = _with_eval(_four(reproduce=None), evaluation)
        env = _build([finding])
        kept = env["findings"][0]
        self.assertIsNone(kept["reproduce"])
        self.assertIn(
            "evaluation",
            kept,
            "build dropped evaluation while normalizing the finding",
        )
        self.assertEqual(
            kept["evaluation"]["evidence"]["kind"],
            "execution-path",
        )
        self.assertEqual(env["counts"]["opinions"], 1)
        self.assertEqual(env["counts"]["p2"], 1)
        self.assertEqual(env["verdict"], "changes")

    def test_reproduction_kind_without_reproduce_is_refused(self):
        evaluation = _defect()
        self.assertEqual(evaluation["evidence"]["kind"], "reproduction")
        finding = _with_eval(_four(reproduce=None), evaluation)
        self.assertIsNone(finding["reproduce"])
        with self.assertRaises(envelope.EnvelopeError):
            _build([finding])

    def test_unknown_evidence_kind_is_refused_not_repaired(self):
        evaluation = _defect(
            evidence={"kind": "hearsay", "details": "someone said so"},
        )
        planted = _with_eval(_four(), evaluation)
        with self.assertRaises(envelope.EnvelopeError):
            env = _build([planted])
            envelope.validate(env)

    def test_a_documentation_finding_can_be_a_demonstrated_defect(self):
        evaluation = _defect(
            requirement=(
                "CONTRACT.md §Refusals is the table of every dispatch "
                "refusal id; ops/devlane/dispatch/CONTRACT.md"
            ),
            trigger="amendment adds worker/executable ids only in prose",
            failure=(
                "expected ids in §Refusals; found prose-only ids and "
                "contradictory row scopes"
            ),
            evidence={
                "kind": "execution-path",
                "details": (
                    "entry CONTRACT.md §Refusals; supported input the "
                    "amendment text; branch table vs prose; failing "
                    "contradiction on write-role-unadmitted/resume-store"
                ),
            },
        )
        finding = _with_eval(
            _four(
                where="ops/devlane/dispatch/CONTRACT.md:805-834",
                claim="new refusal ids bypass the document's own table",
                reproduce=None,
            ),
            evaluation,
        )
        env = _build([finding])
        kept = env["findings"][0]
        self.assertIn(
            "evaluation",
            kept,
            "build dropped evaluation while normalizing the finding",
        )
        self.assertEqual(
            kept["evaluation"]["classification"],
            "demonstrated-defect",
        )


class VerdictsFollowAdmissionNotPriority(unittest.TestCase):
    """A5/A6/A7 — raw counts; changes vs approve; incomplete retained."""

    def test_any_demonstrated_defect_forces_changes(self):
        findings = [
            _with_eval(_four(), _defect()),
            _with_eval(
                _four(
                    severity="p3",
                    claim="flag spellings were not measured",
                    reproduce=None,
                ),
                _unproven(),
            ),
        ]
        with self.assertRaises(envelope.EnvelopeError):
            _build(findings, verdict="approve")
        env = _build(findings, verdict="changes")
        self.assertEqual(env["verdict"], "changes")
        self.assertEqual(len(env["findings"]), 2)
        self.assertIn("evaluation", env["findings"][0])
        self.assertEqual(
            env["findings"][0]["evaluation"]["classification"],
            "demonstrated-defect",
        )
        self.assertEqual(env["counts"]["p2"], 1)
        self.assertEqual(env["counts"]["p3"], 1)
        self.assertEqual(env["counts"]["opinions"], 1)

    def test_unproven_and_expansion_may_accompany_approve(self):
        findings = [
            _with_eval(_four(claim="missing help measurement"), _unproven()),
            _with_eval(
                _four(severity="p3", claim="new exhaustive-match guarantee"),
                _expansion(),
            ),
        ]
        env = _build(findings, verdict="approve")
        self.assertEqual(env["verdict"], "approve")
        for item in env["findings"]:
            self.assertIn(
                "evaluation",
                item,
                "build dropped evaluation while normalizing the finding",
            )
        classes = [
            item["evaluation"]["classification"] for item in env["findings"]
        ]
        self.assertEqual(classes, ["unproven", "scope-expansion"])
        self.assertEqual(env["counts"]["p2"], 1)
        self.assertEqual(env["counts"]["p3"], 1)

    def test_an_incomplete_review_keeps_partial_findings_and_no_approve(self):
        finding = _with_eval(_four(), _defect())
        env = _build(
            [finding],
            status="invalid",
            verdict=None,
            note="review stopped before self-evaluation finished",
        )
        self.assertEqual(env["status"], "invalid")
        self.assertIsNone(env["verdict"])
        self.assertEqual(len(env["findings"]), 1)
        kept = env["findings"][0]
        self.assertIn(
            "evaluation",
            kept,
            "build dropped evaluation while normalizing the finding",
        )
        self.assertEqual(
            kept["evaluation"]["classification"],
            "demonstrated-defect",
        )
        with self.assertRaises(envelope.EnvelopeError):
            _build(
                [finding],
                status="invalid",
                verdict="approve",
                note="review stopped",
            )
        tripped = _build(
            [finding],
            status="tripped",
            verdict="changes",
            note="cap wire tripped",
        )
        self.assertEqual(tripped["status"], "tripped")
        self.assertEqual(tripped["verdict"], "changes")
        with self.assertRaises(envelope.EnvelopeError):
            _build(
                [finding],
                status="tripped",
                verdict="approve",
                note="cap wire tripped",
            )


class SchemaDeclaresEvaluation(unittest.TestCase):
    """ENVELOPE_SCHEMA names the optional closed evaluation member."""

    def test_schema_allows_evaluation_and_forbids_other_finding_keys(self):
        schema = envelope.ENVELOPE_SCHEMA
        items = schema["properties"]["findings"]["items"]
        self.assertFalse(items.get("additionalProperties", True))
        props = items["properties"]
        self.assertIn("evaluation", props)
        evaluation = props["evaluation"]
        types = evaluation.get("type")
        if isinstance(types, list):
            self.assertNotIn("null", types)
        else:
            self.assertNotEqual(types, "null")
        self.assertNotIn(
            None,
            evaluation.get("enum") or (),
        )
        inner = evaluation
        if "oneOf" in evaluation or "anyOf" in evaluation:
            alts = evaluation.get("oneOf") or evaluation.get("anyOf")
            inner = [alt for alt in alts if alt.get("type") == "object"][0]
        self.assertFalse(inner.get("additionalProperties", True))
        required = set(inner.get("required") or ())
        self.assertEqual(
            required,
            {
                "classification",
                "scope_sha256",
                "requirement",
                "trigger",
                "failure",
                "evidence",
                "refutation",
                "source",
                "ruling",
            },
        )


if __name__ == "__main__":
    unittest.main()
