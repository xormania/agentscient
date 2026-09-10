"""Manual and ladder review-slot eligibility.

Written from FINDING-ADMISSION.md §Review eligibility. Intended reds:
a second whole check-tests starts; a renamed unit or new id resets the
slot; concurrent duplicates both spawn a model.

Initial request shape is checked on established JSON helpers first.
"""

from __future__ import annotations

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


class SecondWholeReviewIsRefused(ls._TempLaunch):
    def _check_tests_argv(self, extra=()):
        scope = self.home / "owner-scope.md"
        scope.write_text("review slot scope\n", encoding="utf-8")
        return self.argv_for(
            job="check-tests",
            harness="grok",
            stage="check-tests",
            extra=["--input", str(scope), *extra],
        )

    def test_the_first_eligible_check_tests_is_the_only_initial_slot(self):
        first = self.dispatch(self._check_tests_argv())
        self.assertEqual(first[0], 0, first[2])
        first_id = self.read_record()["id"]
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.dispatch(self._check_tests_argv())
        self.assert_not_started()
        self.assert_wire_refusal(
            code, out, err,
            ident="admission-review",
            phrases=["admission-review", "slot"],
        )
        ids = [p.stem for p in self.record_files()]
        self.assertEqual(ids, [first_id])

    def test_a_renamed_unit_does_not_buy_another_initial_review(self):
        first = self.dispatch(self._check_tests_argv())
        self.assertEqual(first[0], 0, first[2])
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.dispatch(self._check_tests_argv(
            extra=["--unit", "other-unit"],
        ))
        self.assert_not_started()
        text = self.combined(out, err)
        self.assertIn("admission-review", text.lower())
        self.assertEqual(code, ls.REFUSAL_EXIT, text)

    def test_a_new_dispatch_id_is_not_another_initial_review(self):
        first = self.dispatch(self._check_tests_argv())
        self.assertEqual(first[0], 0, first[2])
        before = {p.stem for p in self.record_files()}
        self.start_witness.unlink(missing_ok=True)
        code, out, err = self.dispatch(self._check_tests_argv())
        self.assert_not_started()
        text = self.combined(out, err)
        self.assertIn("admission-review", text.lower())
        self.assertEqual(code, ls.REFUSAL_EXIT, text)
        after = {p.stem for p in self.record_files()}
        self.assertEqual(after, before)


class ReviewRequestFlagBindsTheSlot(ls._TempLaunch):
    def test_initial_review_request_is_retained_on_the_brief(self):
        req = aes.review_request(slot="check-tests", kind="initial")
        self.assertEqual(req["prior"], [])
        path = self.home / "review-request.json"
        aes.write_json(path, req)
        scope = self.home / "owner-scope.md"
        scope.write_text("review request scope\n", encoding="utf-8")
        code, out, err = self.dispatch(self.argv_for(
            job="check-tests",
            harness="grok",
            stage="check-tests",
            extra=[
                "--review-request", str(path),
                "--input", str(scope),
            ],
        ))
        text = self.combined(out, err)
        self.assertNotIn("unrecognized arguments", text.lower(), text)
        self.assertEqual(code, 0, text)
        rec = self.read_record()
        review = rec["brief"]["admission"]["review"]
        self.assertEqual(review["slot"], "check-tests")
        self.assertEqual(review["kind"], "initial")
        self.assertEqual(review["prior"], [])
        self.assertEqual(review["changes"], [])


if __name__ == "__main__":
    unittest.main()
