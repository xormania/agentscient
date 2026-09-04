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

import hashlib
import json
import unittest

import support

JOBS_PATH = support.APP / "jobs.json"

ENVELOPE_CLAUSE = (
    "Answer with a single JSON object and nothing else, carrying exactly "
    "these keys: job, status, verdict, counts, findings, artifacts, spend, "
    "stamp, note"
)

SPEND_TO_THE_LAUNCHER = (
    'Leave `spend` as `{"harness": "<harness>", "total": 0, "out": 0, '
    '"runs": 0}`; the launcher fills it from the session store. Do not '
    "read the store."
)

STDOUT_EMPTY_ARTIFACTS = (
    "Return the JSON envelope on stdout and leave artifacts empty."
)

def write_path_ask(text: str):
    """Return the first write-path instruction in text, or None.

    Loaded from write_path.py the way support.load loads sibling
    modules. No in-file regex, no fallback that restores one.
    """
    module = support.load("write_path")
    return module.write_path_ask(text)

# Item 31: every job other than check-tests is frozen. prompt_sha256 is
# SHA-256 of the prompt string; prompt None is pinned as None.
OTHER_JOB_WIRES = {
    "verify": {
        "adapter": "direct",
        "deliverable": (
            "one claim, executed: a reproduction or a refutation"
        ),
        "prompt": None,
        "constraints": ["read only", "never edit the snapshot"],
    },
    "adversarial-review": {
        "adapter": "harness",
        "deliverable": (
            "findings that survived the task's own attempt to refute them"
        ),
        "role": "read",
        "snapshot": "whole",
        "caps": {"timeout": 1200},
        "prompt_sha256": (
            "29f1eb4b675aba92de83d49b2e456646335fe81475ac916a15a98ca266af18dc"
        ),
        "constraints": ["read only", "do not edit the snapshot"],
    },
    "security-audit": {
        "adapter": "harness",
        "deliverable": (
            "security findings against the change, each with a "
            "reproduction, that survived the auditor's own attempt to "
            "refute them"
        ),
        "role": "read",
        "snapshot": "whole",
        "caps": {"timeout": 1200},
        "prompt_sha256": (
            "7dcf07553df5d024e327f9ddcfa118b8e6da54be705c3ff2dd4b1181da3c86ad"
        ),
        "constraints": ["read only", "do not edit the snapshot"],
    },
    "author-tests": {
        "adapter": "harness",
        "deliverable": (
            "a test file that has been run and is red for the stated reason"
        ),
        "role": "write",
        "snapshot": "whole",
        "caps": {"timeout": 1800},
        "prompt_sha256": (
            "5837d42dd53d13edd27a31ec33353791e21697596238a6fec1839ad53be48c5e"
        ),
        "constraints": ["do not edit the implementation", "no network"],
    },
    "sweep": {
        "adapter": "harness",
        "deliverable": (
            "structured findings over disjoint categories, merged"
        ),
        "role": "read",
        "snapshot": "whole",
        "prompt_sha256": (
            "69113adc3703823d99da9b40a605071b8adf37a9f3bcd16540ee4f244874b4e6"
        ),
        "constraints": ["read only", "do not edit the snapshot"],
    },
    "plan": {
        "adapter": "harness",
        "deliverable": (
            "a plan written to the job's out/PLAN.md, and an envelope "
            "naming it"
        ),
        "role": "read",
        "snapshot": "whole",
        "prompt_sha256": (
            "3548d793298215c967422d67292bc492f4769c79972ea9c4f631f175332e9afc"
        ),
        "constraints": ["read only", "do not edit the snapshot"],
    },
    "implement": {
        "adapter": "harness",
        "deliverable": (
            "commits in the snapshot that make the named test command "
            "pass, trailers per AGENTS.md"
        ),
        "role": "write",
        "snapshot": "whole",
        "caps": {"timeout": 3600},
        "prompt_sha256": (
            "464d0a35b9cd30c14559fcba0a51895cfb97bf13a8b1c9b72db854cda854a00f"
        ),
        "constraints": [
            "do not edit the files the tests live in",
            "no network",
        ],
    },
    "adjudicate": {
        "adapter": "harness",
        "deliverable": (
            "a ruling at the job's out/RULING.md: UPHELD, PARTIAL or "
            "REJECTED per finding, and what the reviewers missed"
        ),
        "role": "read",
        "snapshot": "whole",
        "prompt_sha256": (
            "3490f9e27ebc6218b847431c5676725aa8800561d2a25d08f2c146f43831a15d"
        ),
        "constraints": ["read only", "do not edit the snapshot"],
    },
}


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

    def test_security_audit_declares_caps_timeout_1200(self):
        self.assertTrue(JOBS_PATH.is_file(), f"jobs.json missing: {JOBS_PATH}")
        jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        self.assertIn("security-audit", jobs)
        self.assertIn("adversarial-review", jobs)
        audit = jobs["security-audit"]
        sibling = jobs["adversarial-review"]
        self.assertIsInstance(audit, dict)
        self.assertIsInstance(sibling, dict)
        audit_caps = audit.get("caps")
        sibling_caps = sibling.get("caps")
        self.assertIsInstance(audit_caps, dict, "security-audit must declare caps")
        self.assertIsInstance(sibling_caps, dict)
        self.assertEqual(sibling_caps.get("timeout"), 1200)
        self.assertEqual(
            audit_caps.get("timeout"), 1200,
            "security-audit declares caps.timeout 1200, like adversarial-review",
        )


class EveryHarnessPromptLeavesSpendToTheLauncher(unittest.TestCase):
    """Harness jobs do not hunt usage; the launcher fills spend."""

    def test_every_harness_prompt_leaves_spend_to_the_launcher(self):
        self.assertTrue(JOBS_PATH.is_file(), f"jobs.json missing: {JOBS_PATH}")
        jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(jobs, dict)
        harness_jobs = [
            name for name, spec in jobs.items()
            if isinstance(spec, dict) and spec.get("adapter") == "harness"
        ]
        self.assertGreater(
            len(harness_jobs), 0,
            "jobs.json must name at least one harness job",
        )
        missing = []
        for name in harness_jobs:
            prompt = jobs[name].get("prompt")
            self.assertIsInstance(prompt, str, f"{name} prompt is not a string")
            self.assertTrue(prompt.strip(), f"{name} prompt is empty")
            if SPEND_TO_THE_LAUNCHER not in prompt:
                missing.append(name)
        self.assertEqual(
            missing, [],
            "every harness job prompt leaves spend to the launcher; "
            f"missing from {missing!r}",
        )


class CheckTestsReadRolePromptRejectsAnyWritePath(unittest.TestCase):
    """check-tests is a read role; its prompt test is not a blacklist."""

    def jobs(self) -> dict:
        self.assertTrue(JOBS_PATH.is_file(), f"jobs.json missing: {JOBS_PATH}")
        payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(payload, dict)
        return payload

    def test_write_path_ask_comes_from_write_path_py(self):
        path = support.APP / "write_path.py"
        self.assertTrue(path.is_file(), f"write_path.py is absent: {path}")
        module = support.load("write_path")
        fn = getattr(module, "write_path_ask", None)
        self.assertTrue(
            callable(fn),
            "write_path.py must export write_path_ask",
        )

    def test_check_tests_role_is_read(self):
        jobs = self.jobs()
        self.assertIn("check-tests", jobs)
        spec = jobs["check-tests"]
        self.assertIsInstance(spec, dict)
        self.assertEqual(
            spec.get("role"),
            "read",
            "check-tests is a read role; a write-path prompt is a "
            f"role change, not a deliverable tweak: {spec!r}",
        )

    def test_a_report_rst_write_prompt_is_rejected_by_shape(self):
        prompt = (
            "Create REPORT.rst in the repository and include it in "
            "artifacts. Return the JSON envelope on stdout and leave "
            "artifacts empty."
        )
        match = write_path_ask(prompt)
        self.assertIsNotNone(
            match,
            "read-role prompt test must reject REPORT.rst by shape, "
            "not because REPORT.txt is on a name list",
        )

    def test_a_findings_json_persist_prompt_is_rejected_by_shape(self):
        prompt = (
            "Persist the skeptic findings under reports/findings.json."
        )
        match = write_path_ask(prompt)
        self.assertIsNotNone(
            match,
            "read-role prompt test must reject reports/findings.json "
            "by shape, not by listing SKEPTIC.md or {out}",
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

    def test_live_check_tests_prompt_is_not_a_write_path(self):
        spec = self.jobs()["check-tests"]
        prompt = spec.get("prompt")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip(), "check-tests prompt is empty")
        match = write_path_ask(prompt)
        self.assertIsNone(
            match,
            "check-tests read-role prompt asks for a write path: "
            f"{match.group(0)!r}"
            if match
            else "",
        )
        self.assertIn(
            STDOUT_EMPTY_ARTIFACTS,
            prompt,
            "check-tests prompt must keep the stdout / empty-artifacts "
            f"clause; last 240 chars: {prompt[-240:]!r}",
        )


class OtherJobWiresAreUnchanged(unittest.TestCase):
    """Item 31: the job wire is unchanged for every other job."""

    def test_every_other_job_wire_is_unchanged(self):
        self.assertTrue(JOBS_PATH.is_file(), f"jobs.json missing: {JOBS_PATH}")
        jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(jobs, dict)
        self.assertIn("check-tests", jobs)
        others = {
            name: spec for name, spec in jobs.items() if name != "check-tests"
        }
        self.assertEqual(
            set(others),
            set(OTHER_JOB_WIRES),
            "another job was added or removed; check-tests is the only "
            f"job in this bucket: {sorted(others)!r}",
        )
        for name, expected in OTHER_JOB_WIRES.items():
            spec = others[name]
            self.assertIsInstance(spec, dict, name)
            expected_keys = {
                ("prompt" if key == "prompt_sha256" else key)
                for key in expected
            }
            self.assertEqual(
                set(spec),
                expected_keys,
                f"{name} keys changed: {sorted(spec)!r}",
            )
            for key, value in expected.items():
                if key == "prompt_sha256":
                    prompt = spec.get("prompt")
                    self.assertIsInstance(prompt, str, name)
                    digest = hashlib.sha256(
                        prompt.encode("utf-8"),
                    ).hexdigest()
                    self.assertEqual(
                        digest,
                        value,
                        f"{name} prompt changed",
                    )
                    continue
                self.assertEqual(
                    spec.get(key),
                    value,
                    f"{name}.{key} changed",
                )


if __name__ == "__main__":
    unittest.main()
