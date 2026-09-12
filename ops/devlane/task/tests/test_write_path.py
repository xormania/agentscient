"""The read-role write guard, item 5 of item 31 as amended (owner, 2026-09-11).

Planted both ways: the sentences that must fire and the neighbours that must
not, the declared-output exemption, and the CLI on planted jobs files under
a temporary HOME. One producer wrote the module and this file (grant 149).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

WRITE_PATH = support.APP / "write_path.py"
OLD_SKEPTIC = "Write the report to {out}/SKEPTIC.md and name that path in artifacts"
D1 = (
    "Every refuted or weak test is one finding, a quotation pair. Write no file: "
    "artifacts is an empty object and the envelope on stdout is the whole deliverable. "
    "Review only — do not edit."
)


def _job(prompt: str, role: str = "read", outputs=None) -> dict:
    job = {"adapter": "harness", "role": role, "prompt": prompt, "deliverable": "x", "snapshot": "whole"}
    if outputs is not None:
        job["outputs"] = outputs
    return job


class WriteInstruction(unittest.TestCase):
    def setUp(self):
        self.mod = support.load("write_path")
        self.fn = self.mod.write_instruction

    def test_the_old_skeptic_sentence_fires(self):
        self.assertEqual(self.fn(OLD_SKEPTIC), OLD_SKEPTIC)

    def test_please_write_and_copy_to_fire(self):
        self.assertIsNotNone(self.fn("Please write /tmp/result.md"))
        self.assertIsNotNone(self.fn("Copy the report to /tmp/result.md"))

    def test_a_verb_after_and_with_a_path_fires(self):
        sentence = "Judge the tests and then save the verdict to notes/verdict.md"
        self.assertEqual(self.fn(sentence), sentence)

    def test_the_wire_prompt_does_not_fire(self):
        self.assertIsNone(self.fn(D1))

    def test_negated_sentences_do_not_fire(self):
        self.assertIsNone(self.fn("Do not write to {out}/X.md"))
        self.assertIsNone(self.fn("Write no file"))
        self.assertIsNone(self.fn("Never save anything under out/"))

    def test_a_path_without_a_verb_and_a_verb_without_a_path_do_not_fire(self):
        self.assertIsNone(self.fn("The report lives at out/SKEPTIC.md"))
        self.assertIsNone(self.fn("Write clearly and briefly"))

    def test_a_declared_output_is_exempt_and_an_undeclared_one_is_not(self):
        declared = self.mod.declared_paths([{"kind": "file", "path": "PLAN.md", "artifact": "plan"}])
        self.assertIsNone(self.fn("Write the plan to {out}/PLAN.md and name that path in artifacts", declared))
        self.assertIsNotNone(self.fn("Write the plan to {out}/PLAN.md and save notes to {out}/NOTES.md", declared))
        self.assertIsNotNone(self.fn("Write the plan to {out}/PLAN.md", frozenset()))


class TheCli(unittest.TestCase):
    def setUp(self):
        self.mod = support.load("write_path")
        self.tmp = tempfile.TemporaryDirectory(prefix="write-path-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()

    def run_cli(self, jobs: dict, *names: str):
        path = Path(self.tmp.name) / "jobs.json"
        path.write_text(json.dumps(jobs, indent=1), encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.home), "LC_ALL": "C"}
        return subprocess.run(
            [sys.executable, str(WRITE_PATH), "--jobs", str(path), *names],
            capture_output=True, text=True, env=env, check=False, timeout=60,
        )

    def test_the_old_check_tests_entry_refuses_role_on_the_wire(self):
        proc = self.run_cli({"check-tests": _job(OLD_SKEPTIC)}, "check-tests")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        lines = proc.stderr.strip().splitlines()
        self.assertEqual(len(lines), 1, proc.stderr)
        self.assertRegex(lines[0], r"^role: expected .+; found job check-tests: \".+\"; needed .+$")
        self.assertIn(OLD_SKEPTIC, lines[0])

    def test_the_wire_entry_passes(self):
        proc = self.run_cli({"check-tests": _job(D1)}, "check-tests")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout + proc.stderr, "")

    def test_a_declared_output_passes_and_every_job_is_checked_without_a_name(self):
        jobs = {
            "plan": _job("Write the plan to {out}/PLAN.md and name that path in artifacts",
                         outputs=[{"kind": "file", "path": "PLAN.md", "artifact": "plan"}]),
            "implement": _job("Write the code to src/x.py", role="write"),
        }
        proc = self.run_cli(jobs)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        jobs["sweep"] = _job("Save the sweep to out/SWEEP.md")
        proc = self.run_cli(jobs)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("found job sweep:", proc.stderr)

    def test_an_unknown_job_refuses_job(self):
        proc = self.run_cli({"check-tests": _job(D1)}, "nope")
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(proc.stderr.startswith("job: expected "), proc.stderr)

    def test_the_live_jobs_file_holds(self):
        proc = subprocess.run(
            [sys.executable, str(WRITE_PATH)],
            capture_output=True, text=True, check=False, timeout=60,
            env={"PATH": os.environ.get("PATH", ""), "HOME": str(self.home), "LC_ALL": "C"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
