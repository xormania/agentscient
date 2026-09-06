"""C1 frontend: supervision, refusals, resume and results go through launch.

Written from ops/devlane/dispatch/CONTRACT.md §C1 and task CONTRACT.md
§What the runner does. Implementation was not read.

Vendor mode on run.py is a frontend. It must not keep a second
execution engine, a second supervisor, or a second envelope parser.
Direct verify and stub replay remain non-worker operations (pinned in
test_run.py). These cases inject a synthetic launch executor: no real
vendor, no session store, no catalogue activation.

  F1  a launch trip is returned unchanged; never rewritten to ok/approve
  F2  a launch refusal is invalid with the refusal text; no child
  F3  resume transfers the same id to canonical launch
  F4  the frontend returns launch's envelope; requested model is not
      copied onto observed spend/harness identity
"""

from __future__ import annotations

import sys
import unittest
import uuid

import support
from test_run import (
    _ok_envelope,
    _SyntheticLaunch,
    _TempRun,
    run,
)

envelope = support.load("envelope")


def _tripped_envelope(job, note):
    try:
        return envelope.build(
            job,
            status="tripped",
            verdict=None,
            note=note,
            stamp={"ref": "synthetic-ref"},
        )
    except envelope.EnvelopeError:
        return envelope.build(
            job,
            status="tripped",
            verdict="changes",
            findings=[envelope.finding(
                "p2", "alpha.py §top", note,
                reproduce="python3 -m unittest")],
            note=note,
            stamp={"ref": "synthetic-ref"},
        )


class FrontendSupervisionIsLaunchs(_TempRun):
    """F1 — vendor mode does not arm a second supervisor."""

    def test_a_canonical_launch_trip_is_returned_unchanged(self):
        note = "TRIP-" + uuid.uuid4().hex
        tripped = _tripped_envelope("author-tests", note)
        self.assertEqual(tripped.get("status"), "tripped")
        self.assertNotEqual(tripped.get("verdict"), "approve")
        syn = _SyntheticLaunch(envelope=tripped)
        self.bind_canonical_launch(syn)
        env = self.call_run(
            runtime={"harness": "codex", "model": "test-model", "role": "write"},
        )
        self.assertTrue(
            syn.calls,
            "vendor mode must transfer to canonical launch so a trip can "
            "come from that supervisor, not a second battery",
        )
        self.assertEqual(env, tripped)
        self.assertEqual(env.get("status"), "tripped")
        self.assertNotEqual(env.get("verdict"), "approve")
        self.assertEqual(env.get("note"), note)

    def test_vendor_mode_does_not_rewrite_a_launch_trip_to_ok(self):
        note = "TRIP-OK-" + uuid.uuid4().hex
        syn = _SyntheticLaunch(envelope=_tripped_envelope("author-tests", note))
        self.bind_canonical_launch(syn)
        env = self.call_run(
            runtime={"harness": "codex", "model": "test-model", "role": "write"},
        )
        self.assertTrue(syn.calls, "vendor mode must transfer")
        self.assertNotEqual(env.get("status"), "ok")
        self.assertEqual(env.get("status"), "tripped")


class FrontendRefusalsAreLaunchs(_TempRun):
    """F2 — launch refusals surface through the frontend unchanged."""

    def test_a_canonical_launch_refusal_is_invalid_with_the_refusal_text(self):
        reason = (
            "model: expected a model — a job never names one; "
            "found none; needed --model"
        )
        refused = envelope.invalid(
            "author-tests", reason, stamp={"ref": "synthetic-ref"},
        )
        syn = _SyntheticLaunch(envelope=refused)
        self.bind_canonical_launch(syn)
        recorder = self.record_popen()
        env = self.call_run(
            runtime={"harness": "codex", "model": "test-model", "role": "write"},
        )
        self.assertTrue(
            syn.calls,
            "vendor mode must transfer so launch's refusal is the result",
        )
        self.assertEqual(env, refused)
        self.assertEqual(env.get("status"), "invalid")
        self.assertIsNone(env.get("verdict"))
        self.assertIn("needed --model", env.get("note") or "")
        self.assertEqual(recorder.launch_argv(), [])

    def test_a_faulty_synthetic_executor_does_not_launch_a_harness_cli(self):
        reason = "isolation: expected a harness entry; found none; needed one"
        syn = _SyntheticLaunch(envelope=envelope.invalid(
            "author-tests", reason, stamp={"ref": "synthetic-ref"},
        ))
        self.bind_canonical_launch(syn)
        env = self.call_run(
            runtime={"harness": "codex", "model": "test-model", "role": "write"},
        )
        self.assertTrue(syn.calls, "vendor mode must transfer")
        self.assertEqual(env.get("status"), "invalid")
        self.assertFalse(
            self.record_path.exists(),
            "a refused transfer must not Popen the harness CLI",
        )


class FrontendResumeDelegates(_TempRun):
    """F3 — resume is launch resume of the same id, not a new engine."""

    def test_resume_is_a_public_seam_that_transfers_the_same_id(self):
        job_id = "20260906T000000Z-tests-grok-abcdef"
        note = "RESUME-" + uuid.uuid4().hex
        syn = _SyntheticLaunch(envelope=_ok_envelope("author-tests", note=note))
        self.bind_canonical_launch(syn)
        fn = getattr(run, "resume", None)
        self.assertTrue(
            callable(fn),
            "missing public seam run.resume(id) that transfers to "
            "canonical launch; task must not own a second resume engine",
        )
        env = fn(job_id)
        self.assertTrue(
            syn.calls,
            "resume must invoke canonical_launch, not a second executor",
        )
        blob = syn.selection_blob()
        self.assertIn(job_id, blob)
        self.assertIn("resume", blob.lower())
        self.assertEqual(env, syn.envelope)

    def test_resume_does_not_invent_a_new_dispatch_id(self):
        job_id = "20260906T010101Z-review-codex-123456"
        syn = _SyntheticLaunch(envelope=_ok_envelope(
            "adversarial-review", note="resume-id"))
        self.bind_canonical_launch(syn)
        fn = getattr(run, "resume", None)
        self.assertTrue(callable(fn), "missing public seam run.resume(id)")
        fn(job_id)
        self.assertTrue(syn.calls)
        blob = syn.selection_blob()
        self.assertIn(job_id, blob)
        self.assertNotIn("20260906T010101Z-review-codex-999999", blob)


class FrontendResultsAreLaunchs(_TempRun):
    """F4 — the accepted result is launch's envelope, not a rebuilt copy."""

    def test_the_frontend_returns_launchs_envelope_without_rebuilding_it(self):
        note = "RESULT-" + uuid.uuid4().hex
        launched = _ok_envelope("author-tests", note=note)
        syn = _SyntheticLaunch(envelope=launched)
        self.bind_canonical_launch(syn)
        env = self.call_run(
            runtime={"harness": "codex", "model": "alias-requested",
                     "role": "write"},
        )
        self.assertTrue(syn.calls, "vendor mode must transfer")
        self.assertEqual(env, launched)
        self.assertEqual(env.get("note"), note)
        self.assertIs(env, launched)

    def test_requested_model_is_not_copied_onto_observed_spend(self):
        note = "MODEL-" + uuid.uuid4().hex
        launched = envelope.build(
            "author-tests",
            status="ok",
            verdict="changes",
            findings=[envelope.finding(
                "p2", "alpha.py §top", note,
                reproduce="python3 -m unittest")],
            spend={"harness": "stream-ran-model", "total": 0, "out": 0,
                   "runs": 0},
            stamp={"ref": "synthetic-ref"},
            note=note,
        )
        self.assertEqual(launched["spend"]["harness"], "stream-ran-model")
        syn = _SyntheticLaunch(envelope=launched)
        self.bind_canonical_launch(syn)
        env = self.call_run(
            runtime={"harness": "codex", "model": "alias-requested",
                     "role": "write"},
        )
        self.assertTrue(syn.calls, "vendor mode must transfer")
        spend = env.get("spend") if isinstance(env.get("spend"), dict) else {}
        self.assertEqual(spend.get("harness"), "stream-ran-model")
        self.assertNotEqual(spend.get("harness"), "alias-requested")


class FrontendDirectAndStubStayLocal(_TempRun):
    """Controls: non-worker operations do not take the launch path."""

    def test_direct_verify_does_not_see_a_synthetic_launch_trip(self):
        syn = _SyntheticLaunch(envelope=_tripped_envelope(
            "verify", "should-not-apply"))
        self.bind_canonical_launch(syn)
        env = self.call_run(
            "verify",
            require={
                "scope": "python exits 0",
                "constraints": ["read only"],
                "claim": "python exits 0",
                "command": [sys.executable, "-c", "pass"],
            },
            runtime={"harness": "direct", "role": "read"},
        )
        self.assertFalse(syn.calls)
        self.assertEqual(env.get("status"), "ok")
        self.assertEqual(env.get("verdict"), "approve")
        self.assertNotEqual(env.get("status"), "tripped")


if __name__ == "__main__":
    unittest.main()
