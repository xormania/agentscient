"""check-tests deliverable is the JSON envelope on stdout, not a file.

Written from the item-31 contract: the skeptic's report is its envelope,
not a file. The check-tests job's deliverable is the JSON envelope on
stdout (verdict, counts, findings as quotation pairs with reproduce
commands); the prompt asks for no file and names no path in artifacts.
The job wire is unchanged for every other job.
"""

from __future__ import annotations

import json
import re
import unittest

import support
import test_jobs

JOBS_PATH = support.APP / "jobs.json"

# The prompt must ask for the envelope on stdout and empty artifacts.
# A regression that replaces this clause with a file write is the
# finding the name-list used to miss.
STDOUT_EMPTY_ARTIFACTS = (
    "Return the JSON envelope on stdout and leave artifacts empty."
)

# Artifacts-output instruction, kept here only for the deliverable
# prompt pin. write_path_ask itself comes from write_path.py — no
# in-file write-path regex and no fallback that restores one.
ARTIFACTS_OUTPUT_ASK = re.compile(
    r"(?i)\b(?:write|name|include|put|place)\b.{0,80}\bartifacts\b"
)


def write_path_ask(text: str):
    """Return the first write-path instruction in text, or None."""
    module = support.load("write_path")
    return module.write_path_ask(text)

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

    def test_write_path_ask_comes_from_write_path_py(self):
        path = support.APP / "write_path.py"
        self.assertTrue(path.is_file(), f"write_path.py is absent: {path}")
        module = support.load("write_path")
        fn = getattr(module, "write_path_ask", None)
        self.assertTrue(
            callable(fn),
            "write_path.py must export write_path_ask",
        )

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

    def test_create_review_in_the_repository_is_a_write_path(self):
        path = support.APP / "write_path.py"
        self.assertTrue(path.is_file(), f"write_path.py is absent: {path}")
        prompt = "Create REVIEW in the repository"
        match = write_path_ask(prompt)
        self.assertIsNotNone(
            match,
            "a write verb plus an extensionless relative name is a "
            "write path; requiring a slash, an extension, or {out} "
            "misses Create REVIEW in the repository",
        )

    def test_create_notes_in_the_repository_is_a_write_path(self):
        path = support.APP / "write_path.py"
        self.assertTrue(path.is_file(), f"write_path.py is absent: {path}")
        prompt = "Create NOTES in the repository"
        match = write_path_ask(prompt)
        self.assertIsNotNone(
            match,
            "a write verb plus an extensionless relative name is a "
            "write path; a slash/extension matcher plus a special-case "
            "for Create REVIEW misses Create NOTES in the repository",
        )

    def test_extensionless_relative_names_are_write_paths_by_shape(self):
        path = support.APP / "write_path.py"
        self.assertTrue(path.is_file(), f"write_path.py is absent: {path}")
        names = ("NOTES", "CHANGELOG", "TODO")
        missed = []
        for name in names:
            prompt = f"Create {name} in the repository"
            match = write_path_ask(prompt)
            if match is None:
                missed.append(prompt)
        self.assertEqual(
            missed,
            [],
            "path-shaped includes an extensionless relative name, not "
            "only slash, extension, {out}, or Create REVIEW; missed "
            f"{missed!r}",
        )

    def test_write_verb_plus_path_token_is_not_a_verb_blacklist(self):
        """Security P2 and adversarial P2: shape, not a verb list.

        Declared (PLAN-check-tests-json-2.md:89-92): a write verb plus a
        path-shaped token; path-shaped includes an extensionless relative
        name (`REVIEW`), not only slash, extension, or `{out}`. The tests
        say the read-role prompt rejects any write path, not a blacklist.

        Practiced: `Generate REVIEW in the repository` (security P2) and
        `Create REVIEW on disk` / `Dump REVIEW in the repository`
        (adversarial P2) are not write paths, so planting either as the
        live check-tests prompt leaves the existing guard tests green.
        One test names both findings because they are the same
        declared-versus-practiced gap.
        """
        path = support.APP / "write_path.py"
        self.assertTrue(path.is_file(), f"write_path.py is absent: {path}")
        plants = (
            "Generate REVIEW in the repository",
            "Create REVIEW on disk",
            "Dump REVIEW in the repository",
            "Generate NOTES in the repository",
            "Dump CHANGELOG in the repository",
            "Create TODO on disk",
        )
        self.assertEqual(len(plants), 6)
        missed = []
        for prompt in plants:
            if write_path_ask(prompt) is None:
                missed.append(prompt)
        self.assertEqual(
            missed,
            [],
            "write-path detection remains a verb blacklist "
            "(create|persist|save|store|write) and treats an "
            "extensionless name as a path only with "
            "'in the repository'; security P2 Generate REVIEW and "
            "adversarial P2 Create REVIEW on disk / Dump REVIEW must "
            f"be write paths: missed {missed!r}",
        )
        live = self.check_tests().get("prompt")
        self.assertIsInstance(live, str)
        self.assertTrue(live.strip(), "check-tests prompt is empty")
        self.assertIsNone(
            write_path_ask(live),
            "the live check-tests prompt must stay not a write path",
        )
        self.assertIn(STDOUT_EMPTY_ARTIFACTS, live)
        planted_live = (
            "Create REVIEW on disk. " + STDOUT_EMPTY_ARTIFACTS
        )
        self.assertIsNotNone(
            write_path_ask(planted_live),
            "planting the adversarial Create REVIEW on disk prompt as "
            "the live check-tests brief must be a write path; a "
            "blacklist that misses it leaves the no-file tests green",
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


class OtherJobWiresAreUnchanged(test_jobs.OtherJobWiresAreUnchanged):
    """The job wire is unchanged for every other job.

    Delegates to test_jobs.OtherJobWiresAreUnchanged so the merge-base
    comparison exists once. Compare each other job to the catalogue at
    git merge-base HEAD origin/dev, never to a frozen digest. If
    origin/dev is absent, read base_sha from the ladder record or skip
    with a declared reason.
    """


class NoFrozenJobWireDigestRemains(unittest.TestCase):
    """No test under task/tests or conductor/tests pins a job wire
    other than check-tests to a frozen SHA-256 digest.

    Other jobs compare to the catalogue at merge-base, as in
    test_jobs.OtherJobWiresAreUnchanged. A 64-hex literal in these
    trees is a frozen pin; remaining pins must be none.
    """

    HEX64 = re.compile(r"""['"][0-9a-f]{64}['"]""")
    ROOTS = (
        support.REPO / "ops" / "devlane" / "task" / "tests",
        support.REPO / "ops" / "conductor" / "tests",
    )

    def test_no_frozen_digest_literal_pins_a_job_wire(self):
        pins = []
        scanned = 0
        for root in self.ROOTS:
            self.assertTrue(root.is_dir(), f"tests directory missing: {root}")
            files = sorted(root.glob("test_*.py"))
            self.assertGreater(
                len(files),
                0,
                f"no test_*.py under {root}; the sweep would pass vacuously",
            )
            for path in files:
                scanned += 1
                text = path.read_text(encoding="utf-8")
                for match in self.HEX64.finditer(text):
                    rel = path.relative_to(support.REPO).as_posix()
                    pins.append(f"{rel}:{match.group(0)}")
        self.assertGreater(
            scanned,
            0,
            "scanned no test files; the sweep would pass vacuously",
        )
        self.assertEqual(
            pins,
            [],
            "a frozen SHA-256 literal still pins a job wire; compare "
            "other jobs to the catalogue at merge-base instead: "
            f"{pins!r}",
        )


if __name__ == "__main__":
    unittest.main()
