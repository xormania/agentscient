"""C1 frontend: task vendor mode refuses; launch owns worker supervision.

Corrected from original Grok 4784cd45. No run.resume, no injectable
run.canonical_launch, no callback-return oracle. Direct verify and stub
replay stay local. Canonical trip/refusal/resume/result projection is
exercised through launch.main in dispatch adoption tests.
"""

from __future__ import annotations

import sys
import unittest

from test_run import (
    _TempRun,
    run,
)


class FrontendSupervisionIsLaunchs(_TempRun):
    """F1 — vendor mode does not arm a second supervisor."""

    def test_a_canonical_launch_trip_is_returned_unchanged(self):
        env = self.call_run(
            runtime={"harness": "codex", "model": "test-model", "role": "write"},
        )
        self.assert_vendor_refusal(env)
        self.assertNotEqual(env.get("status"), "tripped")
        self.assertNotEqual(env.get("status"), "ok")
        self.assertNotEqual(env.get("verdict"), "approve")
        self.assertFalse(hasattr(run, "canonical_launch"))

    def test_vendor_mode_does_not_rewrite_a_launch_trip_to_ok(self):
        env = self.call_run(
            runtime={"harness": "codex", "model": "test-model", "role": "write"},
        )
        self.assert_vendor_refusal(env)
        self.assertNotEqual(env.get("status"), "ok")
        self.assertNotEqual(env.get("verdict"), "approve")


class FrontendRefusalsAreLaunchs(_TempRun):
    """F2 — task vendor refusal is its own invalid envelope, not a child."""

    def test_a_canonical_launch_refusal_is_invalid_with_the_refusal_text(self):
        recorder = self.record_popen()
        env = self.call_run(
            runtime={"harness": "codex", "model": "test-model", "role": "write"},
        )
        self.assert_vendor_refusal(env)
        self.assertIn("needed ops/devlane/dispatch/launch.py", env.get("note") or "")
        self.assertEqual(recorder.launch_argv(), [])
        self.assertFalse(self.record_path.exists())

    def test_a_faulty_synthetic_executor_does_not_launch_a_harness_cli(self):
        env = self.call_run(
            runtime={"harness": "codex", "model": "test-model", "role": "write"},
        )
        self.assert_vendor_refusal(env)
        self.assertFalse(
            self.record_path.exists(),
            "a refused vendor mode must not Popen the harness CLI",
        )
        self.assertFalse(hasattr(run, "canonical_launch"))


class FrontendResumeDelegates(_TempRun):
    """F3 — resume is launch.py resume ID, not run.resume."""

    def test_resume_is_a_public_seam_that_transfers_the_same_id(self):
        self.assertFalse(
            hasattr(run, "resume"),
            "run.resume is not a public seam; resume is launch.py resume ID",
        )
        env = self.call_run(
            runtime={"harness": "codex", "model": "test-model", "role": "write"},
        )
        self.assert_vendor_refusal(env)
        self.assertNotIn("resume", (env.get("note") or "").lower())

    def test_resume_does_not_invent_a_new_dispatch_id(self):
        self.assertFalse(hasattr(run, "resume"))
        self.assertFalse(hasattr(run, "canonical_launch"))
        env = self.call_run(
            job="adversarial-review",
            runtime={"harness": "grok", "model": "test-model", "role": "read"},
        )
        self.assert_vendor_refusal(
            env, job="adversarial-review", harness="grok",
        )


class FrontendResultsAreLaunchs(_TempRun):
    """F4 — task vendor refusal is not a rebuilt launch envelope."""

    def test_the_frontend_returns_launchs_envelope_without_rebuilding_it(self):
        env = self.call_run(
            runtime={"harness": "codex", "model": "alias-requested",
                     "role": "write"},
        )
        self.assert_vendor_refusal(env, model="alias-requested")
        spend = env.get("spend") if isinstance(env.get("spend"), dict) else {}
        self.assertEqual(spend.get("harness"), None)
        self.assertNotEqual(spend.get("harness"), "alias-requested")

    def test_requested_model_is_not_copied_onto_observed_spend(self):
        env = self.call_run(
            runtime={"harness": "codex", "model": "alias-requested",
                     "role": "write"},
        )
        self.assert_vendor_refusal(env, model="alias-requested")
        spend = env.get("spend") if isinstance(env.get("spend"), dict) else {}
        self.assertEqual(spend.get("harness"), None)
        self.assertNotEqual(spend.get("harness"), "alias-requested")
        stamp = env.get("stamp") if isinstance(env.get("stamp"), dict) else {}
        self.assertEqual(stamp.get("ref"), self.ref)


class FrontendDirectAndStubStayLocal(_TempRun):
    """Controls: non-worker operations do not take the launch path."""

    def test_direct_verify_does_not_see_a_synthetic_launch_trip(self):
        recorder = self.record_popen()
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
        self.assertEqual(recorder.launch_argv(), [])
        self.assertEqual(env.get("status"), "ok")
        self.assertEqual(env.get("verdict"), "approve")
        self.assertNotEqual(env.get("status"), "tripped")
        self.assertFalse(self.record_path.exists())


if __name__ == "__main__":
    unittest.main()
