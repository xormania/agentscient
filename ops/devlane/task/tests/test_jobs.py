"""Harness job prompts ask for the envelope.

Written from ops/devlane/task/jobs.json: every harness job's prompt except
author-tests ends with the envelope clause. The author-tests brief must
ask for the same envelope the other harness jobs do.

The clause, verbatim:

    Answer with a single JSON object and nothing else, carrying exactly
    these keys: job, status, verdict, counts, findings, artifacts,
    spend, stamp, note
"""

from __future__ import annotations

import json
import unittest

import support

JOBS_PATH = support.APP / "jobs.json"

ENVELOPE_CLAUSE = (
    "Answer with a single JSON object and nothing else, carrying exactly "
    "these keys: job, status, verdict, counts, findings, artifacts, spend, "
    "stamp, note"
)


class AuthorTestsBriefAsksForTheEnvelope(unittest.TestCase):
    """The author-tests brief asks for the envelope."""

    def test_the_author_tests_brief_asks_for_the_envelope(self):
        self.assertTrue(JOBS_PATH.is_file(), f"jobs.json missing: {JOBS_PATH}")
        jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(jobs, dict)
        self.assertIn("author-tests", jobs)
        spec = jobs["author-tests"]
        self.assertIsInstance(spec, dict)
        prompt = spec.get("prompt")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip(), "author-tests prompt is empty")
        self.assertIn(
            ENVELOPE_CLAUSE,
            prompt,
            "author-tests brief must ask for the envelope; "
            f"last 240 chars: {prompt[-240:]!r}",
        )


class SecurityAuditIsInTheCatalogue(unittest.TestCase):
    """security-audit is a read, whole-tree job with the envelope."""

    def test_security_audit_is_a_read_whole_job_with_the_envelope(self):
        self.assertTrue(JOBS_PATH.is_file(), f"jobs.json missing: {JOBS_PATH}")
        jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(jobs, dict)
        self.assertIn("security-audit", jobs)
        spec = jobs["security-audit"]
        self.assertIsInstance(spec, dict)
        self.assertEqual(spec.get("role"), "read")
        self.assertEqual(spec.get("snapshot"), "whole")
        prompt = spec.get("prompt")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip(), "security-audit prompt is empty")
        for token in ("{ref}", "{base}", "{diff}", "{scope}"):
            self.assertIn(token, prompt, f"security-audit prompt missing {token}")
        self.assertIn(
            ENVELOPE_CLAUSE,
            prompt,
            "security-audit brief must ask for the envelope; "
            f"last 240 chars: {prompt[-240:]!r}",
        )


if __name__ == "__main__":
    unittest.main()
