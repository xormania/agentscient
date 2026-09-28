"""Manual and ladder review-slot eligibility.

Written from FINDING-ADMISSION.md §Review eligibility. Intended reds:
a second whole check-tests starts; a renamed unit or new id resets the
slot; concurrent duplicates both spawn a model.

Initial request shape is checked on established JSON helpers first.
Every launch uses the same bound work-order and initial request.
"""

from __future__ import annotations

import concurrent.futures
import os
import subprocess
import sys
import unittest

import admission_enforcement_support as aes
import launch_support as ls


class InitialRequestShapeIsClosed(unittest.TestCase):
    """GREEN helper: initial vs followup request objects."""

    def test_initial_has_empty_prior_and_changes(self):
        req = aes.review_request(slot="check-tests", kind="initial")
        self.assertEqual(set(req), set(aes.REVIEW_REQUEST_KEYS))
        self.assertEqual(req["prior"], [])
        self.assertEqual(req["changes"], [])
        self.assertIsNone(req["projection_sha256"])
        self.assertEqual(
            aes.retain_list(req["prior"], default=["invented"]),
            [],
        )

    def test_followup_rejects_empty_changes(self):
        with self.assertRaises(ValueError):
            aes.review_request(
                slot="check-tests",
                kind="followup",
                prior=[],
                projection_sha256=None,
                changes=[],
            )


class _BoundSlots(ls._TempLaunch):
    def plant_bound(self):
        bound = aes.attach_bound(self)
        self.assertEqual(bound.request["kind"], "initial")
        self.assertEqual(bound.request["prior"], [])
        return bound

    def bound_argv(self, bound, extra=(), *, unit=None):
        return self.argv_for(
            job="check-tests",
            harness="grok",
            stage="check-tests",
            extra=aes.bound_extra(bound, "check-tests", extra, unit=unit),
        )

    def assert_unrecognized_free(self, text):
        self.assertNotIn(
            "unrecognized arguments",
            text.lower(),
            f"missing --work-order/--review-request is not slot proof: {text!r}",
        )

    def dispatch_subprocess(self, argv):
        env = os.environ.copy()
        return subprocess.run(
            [sys.executable, str(aes.LAUNCH), *argv],
            cwd=str(self.repo),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )


class SecondWholeReviewIsRefused(_BoundSlots):
    def test_the_first_eligible_check_tests_is_the_only_initial_slot(self):
        bound = self.plant_bound()
        first = self.dispatch(self.bound_argv(bound))
        self.assert_unrecognized_free(self.combined(first[1], first[2]))
        self.assertEqual(first[0], 0, first[2])
        first_id = self.read_record()["id"]
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.dispatch(self.bound_argv(bound))
        self.assert_unrecognized_free(self.combined(out, err))
        self.assert_not_started()
        self.assert_wire_refusal(
            code, out, err,
            ident="admission-review",
            phrases=["admission-review", "slot"],
        )
        ids = [p.stem for p in self.record_files()]
        self.assertEqual(ids, [first_id])

    def test_a_renamed_unit_does_not_buy_another_initial_review(self):
        bound = self.plant_bound()
        first = self.dispatch(self.bound_argv(bound))
        self.assert_unrecognized_free(self.combined(first[1], first[2]))
        self.assertEqual(first[0], 0, first[2])
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.dispatch(self.bound_argv(bound, unit="other-unit"))
        self.assert_unrecognized_free(self.combined(out, err))
        self.assert_not_started()
        text = self.combined(out, err)
        self.assertIn("admission-review", text.lower())
        self.assertEqual(code, ls.REFUSAL_EXIT, text)

    def test_a_new_dispatch_id_is_not_another_initial_review(self):
        bound = self.plant_bound()
        first = self.dispatch(self.bound_argv(bound))
        self.assert_unrecognized_free(self.combined(first[1], first[2]))
        self.assertEqual(first[0], 0, first[2])
        before = {p.stem for p in self.record_files()}
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.dispatch(self.bound_argv(bound))
        self.assert_unrecognized_free(self.combined(out, err))
        self.assert_not_started()
        text = self.combined(out, err)
        self.assertIn("admission-review", text.lower())
        self.assertEqual(code, ls.REFUSAL_EXIT, text)
        after = {p.stem for p in self.record_files()}
        self.assertEqual(after, before)

    def test_simultaneous_duplicate_initial_reviews_only_one_starts(self):
        bound = self.plant_bound()
        argv = self.bound_argv(bound)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(self.dispatch_subprocess, argv) for _ in range(2)]
            procs = [fut.result() for fut in futs]
        texts = [((p.stdout or "") + (p.stderr or "")) for p in procs]
        for text in texts:
            self.assert_unrecognized_free(text)
        codes = sorted(p.returncode for p in procs)
        self.assertEqual(codes, [0, ls.REFUSAL_EXIT], texts)
        refused = [p for p in procs if p.returncode != 0]
        self.assertEqual(len(refused), 1)
        self.assertIn("admission-review", (refused[0].stderr or "").lower())
        started = [p for p in procs if p.returncode == 0]
        self.assertEqual(len(started), 1)
        records = self.record_files()
        self.assertEqual(len(records), 1, records)


class ReviewRequestFlagBindsTheSlot(_BoundSlots):
    def test_initial_review_request_is_retained_on_the_brief(self):
        bound = self.plant_bound()
        self.assertEqual(bound.request["prior"], [])
        code, out, err = self.dispatch(self.bound_argv(bound))
        text = self.combined(out, err)
        self.assert_unrecognized_free(text)
        self.assertEqual(code, 0, text)
        rec = self.read_record()
        review = rec["brief"]["admission"]["review"]
        self.assertEqual(review["slot"], "check-tests")
        self.assertEqual(review["kind"], "initial")
        self.assertEqual(review["prior"], [])
        self.assertEqual(review["changes"], [])


sys.path.insert(0, str(aes.WRAPPER.parent.parent / "tests"))
from test_dispatch_wrapper import _WrapperFixture  # noqa: E402


class WrapperForwardsBoundFlags(_WrapperFixture):
    """Wrapper entrypoint: --work-order and --review-request are forwarded."""

    def test_dry_run_forwards_work_order_and_review_request(self):
        wo = self.scratch / "work-order.json"
        req = self.scratch / "review-request.json"
        # Wrapper forwards FILE paths; declaration shape is launch's duty.
        aes.write_json(wo, {"id": aes.BOUND_WO_ID, "path": "work-order.json"})
        aes.write_json(req, aes.initial_request())
        proc = self.invoke(self.full_flags(
            "--work-order", str(wo),
            "--review-request", str(req),
            job="check-tests",
            stage="check-tests",
        ))
        text = self.combined(proc)
        self.assertNotIn("unrecognized", text.lower(), text)
        payload = self.parse_dry_run_object(proc)
        argv = payload.get("argv") or []
        self.assertIn("--work-order", argv, argv)
        self.assertEqual(argv[argv.index("--work-order") + 1], str(wo))
        self.assertIn("--review-request", argv, argv)
        self.assertEqual(argv[argv.index("--review-request") + 1], str(req))


if __name__ == "__main__":
    unittest.main()
