"""check-tests deliverable is the JSON envelope on stdout, not a file.

Written from the item-31 contract: the skeptic's report is its envelope,
not a file. The check-tests job's deliverable is the JSON envelope on
stdout (verdict, counts, findings as quotation pairs with reproduce
commands); the prompt asks for no file and names no path in artifacts.
The job wire is unchanged for every other job.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest

import support

JOBS_PATH = support.APP / "jobs.json"

# Canonical SHA-256 of every jobs.json entry except check-tests
# (json.dumps sort_keys=True, ensure_ascii=False, separators=(",", ":")).
OTHER_JOBS_SHA256 = (
    "fdab3e7b2d9b6673f9fd5567b557b56b54ecab0394b3e310ab692e2183219c9c"
)
OTHER_JOB_NAMES = (
    "verify",
    "adversarial-review",
    "security-audit",
    "author-tests",
    "sweep",
    "plan",
    "implement",
    "adjudicate",
)

# Output-path asks in the prompt: a file to write, a path in artifacts,
# or any of the forms the skeptic showed still passing ({out} was
# already forbidden; /tmp/REPORT.txt was not). SKEPTIC.md is the output
# filename (exact case); it must not match the role-card path
# test-skeptic.md.
PROMPT_OUTPUT_PATH = re.compile(
    r"\{out\}"
    r"|SKEPTIC\.md"
    r"|/tmp\b"
    r"|\bREPORT\.txt\b"
    r"|(?i:write the report to)"
    r"|(?i:name that path in artifacts)"
    r"|(?i:name .{0,80} in artifacts)"
)

# A path of any form in the deliverable: slash, {out}, or a filename.
DELIVERABLE_PATH = re.compile(
    r"\{out\}"
    r"|out/"
    r"|/\S+"
    r"|\b\S+\.(md|txt|json|jsonl)\b"
)


class _CheckTestsJob(unittest.TestCase):
    """Load the catalogue as data, not as a module."""

    def jobs(self) -> dict:
        self.assertTrue(JOBS_PATH.is_file(), f"jobs.json missing: {JOBS_PATH}")
        payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(payload, dict)
        return payload

    def check_tests(self) -> dict:
        jobs = self.jobs()
        self.assertIn("check-tests", jobs)
        spec = jobs["check-tests"]
        self.assertIsInstance(spec, dict)
        return spec


class CheckTestsPromptCarriesNoFilePath(_CheckTestsJob):
    """The check-tests prompt asks for no file and names no path."""

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

    def test_check_tests_prompt_asks_for_no_path_of_any_form(self):
        prompt = self.check_tests().get("prompt")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip(), "check-tests prompt is empty")
        match = PROMPT_OUTPUT_PATH.search(prompt)
        self.assertIsNone(
            match,
            "check-tests prompt asks for a path as output; "
            f"matched {match.group(0)!r} in {prompt!r}"
            if match
            else "",
        )

    def test_check_tests_prompt_names_no_path_in_artifacts(self):
        prompt = self.check_tests().get("prompt")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip(), "check-tests prompt is empty")
        self.assertNotRegex(
            prompt,
            r"(?i)(write|name).{0,80}artifacts",
            "check-tests prompt must not name a path in artifacts; "
            f"last 240 chars: {prompt[-240:]!r}",
        )


class CheckTestsDeliverableIsTheJsonEnvelopeOnStdout(_CheckTestsJob):
    """The deliverable is the JSON envelope on stdout, not a file path."""

    def test_check_tests_deliverable_names_the_json_envelope_on_stdout(self):
        deliverable = self.check_tests().get("deliverable")
        self.assertIsInstance(deliverable, str)
        self.assertTrue(deliverable.strip(), "check-tests deliverable is empty")
        self.assertIn(
            "JSON envelope on stdout",
            deliverable,
            "check-tests deliverable must name the JSON envelope on stdout; "
            f"got {deliverable!r}",
        )

    def test_check_tests_deliverable_asks_for_quotation_pairs(self):
        deliverable = self.check_tests().get("deliverable")
        self.assertIsInstance(deliverable, str)
        self.assertTrue(deliverable.strip(), "check-tests deliverable is empty")
        self.assertIn(
            "quotation pair",
            deliverable.lower(),
            "check-tests deliverable must ask for findings as quotation "
            f"pairs; got {deliverable!r}",
        )

    def test_check_tests_deliverable_asks_for_reproduce_commands(self):
        deliverable = self.check_tests().get("deliverable")
        self.assertIsInstance(deliverable, str)
        self.assertTrue(deliverable.strip(), "check-tests deliverable is empty")
        self.assertIn(
            "reproduce",
            deliverable.lower(),
            "check-tests deliverable must ask for reproduce commands; "
            f"got {deliverable!r}",
        )

    def test_check_tests_deliverable_asks_for_no_path_of_any_form(self):
        deliverable = self.check_tests().get("deliverable")
        self.assertIsInstance(deliverable, str)
        self.assertTrue(deliverable.strip(), "check-tests deliverable is empty")
        match = DELIVERABLE_PATH.search(deliverable)
        self.assertIsNone(
            match,
            "check-tests deliverable asks for a path; "
            f"matched {match.group(0)!r} in {deliverable!r}"
            if match
            else "",
        )

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


class OtherJobWiresAreUnchanged(_CheckTestsJob):
    """The job wire is unchanged for every other job."""

    def test_every_other_job_wire_is_unchanged(self):
        jobs = self.jobs()
        self.assertIn("check-tests", jobs)
        others = {
            name: spec for name, spec in jobs.items() if name != "check-tests"
        }
        self.assertEqual(
            set(others),
            set(OTHER_JOB_NAMES),
            "another job was added or removed; check-tests is the only "
            f"job in this bucket: {sorted(others)!r}",
        )
        canonical = json.dumps(
            others, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.assertEqual(
            digest,
            OTHER_JOBS_SHA256,
            "another job's role, snapshot, deliverable, constraints, or "
            "prompt changed; check-tests is the only job in this bucket",
        )


if __name__ == "__main__":
    unittest.main()
