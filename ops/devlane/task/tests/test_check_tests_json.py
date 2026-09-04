"""check-tests prompt and deliverable carry no SKEPTIC.md and no {out}.

Written from the item-31 contract: the skeptic's report is its envelope,
not a file. The check-tests job's deliverable is the JSON envelope on
stdout; the prompt asks for no file and names no path in artifacts.
"""

from __future__ import annotations

import json
import unittest

import support

JOBS_PATH = support.APP / "jobs.json"


class _CheckTestsJob(unittest.TestCase):
    """Load the check-tests catalogue entry as data, not as a module."""

    def check_tests(self) -> dict:
        self.assertTrue(JOBS_PATH.is_file(), f"jobs.json missing: {JOBS_PATH}")
        jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(jobs, dict)
        self.assertIn("check-tests", jobs)
        spec = jobs["check-tests"]
        self.assertIsInstance(spec, dict)
        return spec


class CheckTestsPromptCarriesNoFilePath(_CheckTestsJob):
    """The check-tests prompt asks for no file and names no {out} path."""

    def test_check_tests_prompt_does_not_name_skeptic_md(self):
        prompt = self.check_tests().get("prompt")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip(), "check-tests prompt is empty")
        self.assertNotIn(
            "SKEPTIC.md",
            prompt,
            "check-tests prompt must not name SKEPTIC.md; "
            f"last 240 chars: {prompt[-240:]!r}",
        )

    def test_check_tests_prompt_does_not_name_an_out_path(self):
        prompt = self.check_tests().get("prompt")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip(), "check-tests prompt is empty")
        self.assertNotIn(
            "{out}",
            prompt,
            "check-tests prompt must not name an {out} path; "
            f"last 240 chars: {prompt[-240:]!r}",
        )


class CheckTestsDeliverableCarriesNoFilePath(_CheckTestsJob):
    """The check-tests deliverable is the envelope, not a SKEPTIC.md path."""

    def test_check_tests_deliverable_does_not_name_skeptic_md(self):
        deliverable = self.check_tests().get("deliverable")
        self.assertIsInstance(deliverable, str)
        self.assertTrue(deliverable.strip(), "check-tests deliverable is empty")
        self.assertNotIn(
            "SKEPTIC.md",
            deliverable,
            "check-tests deliverable must not name SKEPTIC.md; "
            f"got {deliverable!r}",
        )

    def test_check_tests_deliverable_does_not_name_an_out_path(self):
        deliverable = self.check_tests().get("deliverable")
        self.assertIsInstance(deliverable, str)
        self.assertTrue(deliverable.strip(), "check-tests deliverable is empty")
        self.assertNotIn(
            "out/",
            deliverable,
            "check-tests deliverable must not name an out/ path; "
            f"got {deliverable!r}",
        )
        self.assertNotIn(
            "{out}",
            deliverable,
            "check-tests deliverable must not name an {out} path; "
            f"got {deliverable!r}",
        )


if __name__ == "__main__":
    unittest.main()
