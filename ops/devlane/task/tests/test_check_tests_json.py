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

# The prompt must ask for the envelope on stdout and empty artifacts.
# A regression that replaces this clause with a file write is the
# finding the name-list used to miss.
STDOUT_EMPTY_ARTIFACTS = (
    "Return the JSON envelope on stdout and leave artifacts empty."
)

# A write-path ask is a write/create/persist/save/store/emit verb
# together with a path-shaped token, or an artifacts-output
# instruction. Names are not listed: REPORT.rst and
# reports/findings.json are caught by shape, not by being on a list.
# SKEPTIC.md is still named below as the role-card cousin that must
# not be confused with test-skeptic.md.
WRITE_PATH_ASK = re.compile(
    r"(?is)"
    r"\b(?:write|create|persist|save|store|emit|dump)\b"
    r".{0,200}?"
    r"(?:\{out\}|(?<![A-Za-z])out/|/\S+|\b[\w.-]+\.\w{1,8}\b)"
)
ARTIFACTS_OUTPUT_ASK = re.compile(
    r"(?i)\b(?:write|name|include|put|place)\b.{0,80}\bartifacts\b"
)


def write_path_ask(text: str):
    """Return the first write-path instruction in text, or None."""
    if not isinstance(text, str) or not text.strip():
        return None
    match = WRITE_PATH_ASK.search(text)
    if match:
        return match
    return ARTIFACTS_OUTPUT_ASK.search(text)

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
        match = write_path_ask(prompt)
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
        match = ARTIFACTS_OUTPUT_ASK.search(prompt)
        self.assertIsNone(
            match,
            "check-tests prompt must not name a path in artifacts; "
            f"matched {match.group(0)!r} in {prompt!r}"
            if match
            else "",
        )

    def test_check_tests_prompt_asks_for_stdout_and_empty_artifacts(self):
        prompt = self.check_tests().get("prompt")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip(), "check-tests prompt is empty")
        self.assertIn(
            STDOUT_EMPTY_ARTIFACTS,
            prompt,
            "check-tests prompt must ask for the JSON envelope on stdout "
            "and empty artifacts; last 240 chars: "
            f"{prompt[-240:]!r}",
        )


class ReadRolePromptRejectsAnyWritePath(_CheckTestsJob):
    """The read-role prompt test rejects any write path, not a blacklist.

    The name-list (SKEPTIC.md, {out}, /tmp, REPORT.txt, two phrases)
    accepted a prompt that created REPORT.rst and one that persisted
    reports/findings.json. Shape, not names, is the pin.
    """

    def test_creating_report_rst_is_a_write_path(self):
        prompt = (
            "Create REPORT.rst in the repository and include it in "
            "artifacts. Return the JSON envelope on stdout and leave "
            "artifacts empty."
        )
        match = write_path_ask(prompt)
        self.assertIsNotNone(
            match,
            "a prompt that creates REPORT.rst must be a write path; "
            "a name-list that omits REPORT.rst misses this",
        )

    def test_persisting_findings_json_is_a_write_path(self):
        prompt = (
            "Adopt the role card at ops/process/roles/test-skeptic.md. "
            "Persist the skeptic findings under reports/findings.json."
        )
        match = write_path_ask(prompt)
        self.assertIsNotNone(
            match,
            "a prompt that persists reports/findings.json must be a "
            "write path; requiring only SKEPTIC.md/{out} misses this",
        )

    def test_write_path_detection_is_by_shape_not_a_name_list(self):
        names = (
            "NOTES.rst",
            "out/custom.bin",
            "var/review.html",
            "tmp/SKEPTIC.out",
        )
        for name in names:
            prompt = (
                f"Create {name} in the repository and include it in "
                "artifacts."
            )
            match = write_path_ask(prompt)
            self.assertIsNotNone(
                match,
                f"write-path detection must catch {name!r} by shape, "
                "not by listing filenames",
            )

    def test_the_live_read_role_prompt_is_not_a_write_path(self):
        spec = self.check_tests()
        self.assertEqual(spec.get("role"), "read", spec)
        prompt = spec.get("prompt")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip(), "check-tests prompt is empty")
        match = write_path_ask(prompt)
        self.assertIsNone(
            match,
            "check-tests is a read role; its prompt asks for a write "
            f"path: {match.group(0)!r}"
            if match
            else "",
        )
        self.assertIn(STDOUT_EMPTY_ARTIFACTS, prompt)


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
