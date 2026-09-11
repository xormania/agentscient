"""Uncited-correction gate: correction.py check, the five found-texts.

Written from scope-gate-20260910.md items 1-8 and 10, and rulings R1,
R2, R5, R6, R7, R8. The tool is the subject and is not read here.
When the file is absent a stub that exits 0 with no output is invoked,
so the assertions fail rather than the suite erroring on a missing
path. findings.py is staged only to plant the ledger; the gate is
invoked as a subprocess against that planted HOME and records dir.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CORRECTION = REPO / "ops" / "conductor" / "tools" / "correction.py"
FINDINGS = REPO / "ops" / "conductor" / "tools" / "findings.py"
REGISTRY = REPO / "ops" / "conductor" / "registry" / "correction.py.json"
LIVE_STORE = Path.home() / ".local" / "state" / "agentscient" / "findings.db"
AGENT = "Correction Tester <correction-tester@example.invalid>"

REVIEW = "20260901T000000Z-review-grok-aaaaaa"
PLAN = "20260901T030000Z-plan-claude-dddddd"
IMPLEMENT = "20260901T040000Z-code-codex-eeeeee"
AUTHOR = "20260901T050000Z-tests-grok-ffffff"
CHECK = "20260901T060000Z-check-tests-codex-111111"
MISSING = "20260101T000000Z-review-codex-000000"
OTHER_KEY = "20260901T000000Z-review-grok-ffffff#1"
BAD_KEY = "not-a-key"
ZERO_KEY = f"{REVIEW}#0"
SCOPE_REL = ".dev/ladder-inputs/scope-gate-20260910.md"
VALID_EVIDENCE = (
    "contract item 3 of .dev/ladder-inputs/scope-gate-20260910.md: "
    "found-text missing"
)
SCOPE_BODY = (
    "# Work order\n"
    "\n"
    "1. **Correction, defined mechanically.**\n"
    "2. **Findings are named, not inferred.**\n"
    "3. **Refusal at mint, on the wire.**\n"
    "4. **Citation shape.**\n"
)
ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)
RUN_CAP = 30
FUTURE = "2099-01-01T00:00:00Z"
PAST = "2000-01-01T00:00:00Z"
SAME = "2026-09-10T12:00:00Z"

REGISTRY_ROWS = (
    {
        "argv": ["check"],
        "class": "arguments",
        "identity": False,
    },
    {
        "argv": [
            "check",
            "--job",
            "implement",
            "--role",
            "write",
            "--at",
            "2026-01-01T00:00:00Z",
            "--follows",
            MISSING,
        ],
        "class": "follows",
        "identity": False,
    },
)


def _live_snapshot() -> tuple[str, bytes | None]:
    if LIVE_STORE.is_file():
        return ("file", LIVE_STORE.read_bytes())
    if LIVE_STORE.exists():
        return ("other", None)
    return ("absent", None)


class _GateFixture(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self._live_before = _live_snapshot()
        self._tmp = tempfile.TemporaryDirectory(prefix="correction-gate-")
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.scratch = root / "scratch"
        self.repo = root / "repo"
        self.records = self.repo / ".dev" / "records" / "dispatches"
        self.jobs_root = root / "jobs"
        self.home.mkdir()
        self.scratch.mkdir()
        self.records.mkdir(parents=True)
        self.jobs_root.mkdir()
        self.store = (
            self.home / ".local" / "state" / "agentscient" / "findings.db"
        )
        self.scope = self.repo / SCOPE_REL
        self.findings = self.repo / "ops" / "conductor" / "tools" / "findings.py"
        self._stage_findings()
        self._plant_bytes(self.scope, SCOPE_BODY.encode("utf-8"))
        self.tool = self._correction_tool()
        self.assertFalse(
            self.store.exists(),
            "plant: isolated store must start absent",
        )

    def tearDown(self):
        try:
            self.assertEqual(
                _live_snapshot(),
                self._live_before,
                f"live store mutated: {LIVE_STORE}",
            )
        finally:
            self._tmp.cleanup()

    def _stage_findings(self) -> None:
        self.assertTrue(FINDINGS.is_file(), f"{FINDINGS} is missing")
        self.findings.parent.mkdir(parents=True, exist_ok=True)
        data = FINDINGS.read_bytes()
        self.findings.write_bytes(data)
        landed = self.findings.read_bytes()
        self.assertEqual(landed, data, "copy-findings-bytes did not land intact")
        self.assertNotEqual(landed, ABSENT_STUB)

    def _correction_tool(self) -> Path:
        if CORRECTION.is_file():
            return CORRECTION
        stub = self.scratch / "correction.py"
        stub.write_bytes(ABSENT_STUB)
        self.assertEqual(stub.read_bytes(), ABSENT_STUB)
        return stub

    def _plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")

    def env(self) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "WF_AGENT": AGENT,
        }

    def findings_invoke(self, argv: list[str]):
        return subprocess.run(
            [sys.executable, str(self.findings), *argv],
            cwd=str(self.repo),
            env=self.env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )

    def plant_record(self, rec_id: str, job: str, claims: list[str] | None = None):
        if claims is None:
            claims = [f"claim-{rec_id}"]
        findings = [
            {
                "severity": "p1",
                "where": "ops/x.py",
                "claim": claim,
                "reproduce": None,
            }
            for claim in claims
        ]
        envelope = {
            "id": rec_id,
            "lane": "dev",
            "stage": "review",
            "unit": "lane/correction",
            "job": job,
            "role": "read" if job not in ("implement", "author-tests") else "write",
            "status": "closed",
            "harness": {"name": "grok"},
            "model": {"ran": "grok-4.6"},
            "result": {
                "envelope": {
                    "status": "ok",
                    "verdict": "changes",
                    "findings": findings,
                }
            },
        }
        path = self.records / f"{rec_id}.json"
        payload = json.dumps(envelope, indent=2) + "\n"
        self._plant_bytes(path, payload.encode("utf-8"))
        return path

    def import_records(self):
        proc = self.findings_invoke(["import"])
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        return proc

    def dispose(self, key: str, disposition: str, evidence: str):
        proc = self.findings_invoke(
            ["disposition", key, disposition, evidence]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        return proc

    def set_disposed_at(self, key: str, stamp: str) -> None:
        self.assertTrue(self.store.is_file(), "store missing for timestamp plant")
        con = sqlite3.connect(self.store)
        try:
            con.execute(
                "update findings set disposed_at = ? where key = ?",
                (stamp, key),
            )
            con.commit()
            rows = list(
                con.execute(
                    "select disposed_at from findings where key = ?",
                    (key,),
                )
            )
        finally:
            con.close()
        self.assertEqual(rows, [(stamp,)])

    def check(
        self,
        *,
        job: str = "implement",
        role: str = "write",
        at: str = FUTURE,
        follows: list[str] | None = None,
        inputs: list[str] | None = None,
        answers: list[str] | None = None,
        extra: list[str] | None = None,
    ):
        argv = [
            "check",
            "--job",
            job,
            "--role",
            role,
            "--at",
            at,
            "--records",
            str(self.records),
            "--jobs-root",
            str(self.jobs_root),
            "--root",
            str(self.repo),
        ]
        for rec in follows or []:
            argv.extend(["--follows", rec])
        for path in inputs or []:
            argv.extend(["--input", path])
        for key in answers or []:
            argv.extend(["--answers", key])
        if extra:
            argv.extend(extra)
        return subprocess.run(
            [sys.executable, str(self.tool), *argv],
            cwd=str(self.repo),
            env=self.env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )

    def assert_refusal(self, proc, class_name: str) -> str:
        err = proc.stderr or ""
        self.assertEqual(proc.returncode, 2, err or proc.stdout)
        self.assertEqual((proc.stdout or "").strip(), "")
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"item 3: one stderr line: {err!r}")
        line = lines[0]
        head = line.split(":", 1)[0].strip().lower().replace("_", "-")
        self.assertEqual(
            head,
            class_name,
            f"refusal class must be {class_name!r}: {line!r}",
        )
        lower = line.lower()
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, line)
        self.assertLess(lower.index("expected"), lower.index("found"), line)
        self.assertLess(lower.index("found"), lower.index("needed"), line)
        return line

    def found_clause(self, line: str) -> str:
        lower = line.lower()
        start = lower.index("found ")
        end = lower.index("; needed")
        return line[start + len("found ") : end]

    def needed_clause(self, line: str) -> str:
        lower = line.lower()
        start = lower.index("needed ")
        return line[start + len("needed ") :]

    def assert_expected_before_stamp(self, line: str, stamp: str) -> None:
        self.assertIn(
            "every finding answered by this correction "
            "disposed with a contract citation before",
            line,
        )
        self.assertIn(stamp, line)


class FiveFoundTexts(_GateFixture):
    """Item 3 — distinct found-texts, founding wire, exact needed command."""

    def test_no_answers_key_named_for_a_correction(self):
        self.plant_record(REVIEW, "adversarial-review")
        proc = self.check(follows=[REVIEW])
        line = self.assert_refusal(proc, "correction")
        self.assert_expected_before_stamp(line, FUTURE)
        found = self.found_clause(line)
        self.assertIn("no --answers key named for a correction following", found)
        self.assertIn(REVIEW, found)
        self.assertIn("adversarial-review", found)
        needed = self.needed_clause(line)
        self.assertIn("pass --answers", needed)
        self.assertIn(
            "python3 ops/conductor/tools/findings.py disposition",
            needed,
        )

    def test_key_absent_from_the_store_names_the_path(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        self.assertTrue(self.store.is_file())
        proc = self.check(follows=[REVIEW], answers=[OTHER_KEY])
        line = self.assert_refusal(proc, "correction")
        self.assert_expected_before_stamp(line, FUTURE)
        found = self.found_clause(line)
        self.assertIn(OTHER_KEY, found)
        self.assertIn("absent from the findings store", found)
        self.assertIn(str(self.store), found)
        self.assertNotIn("(no store)", found)
        needed = self.needed_clause(line)
        self.assertIn(
            "python3 ops/conductor/tools/findings.py import, then",
            needed,
        )
        self.assertIn(f"'{OTHER_KEY}'", needed)

    def test_missing_store_names_no_store_and_does_not_create_one(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.assertFalse(self.store.exists())
        proc = self.check(follows=[REVIEW], answers=[f"{REVIEW}#1"])
        line = self.assert_refusal(proc, "correction")
        found = self.found_clause(line)
        self.assertIn("absent from the findings store", found)
        self.assertIn("(no store)", found)
        self.assertIn(str(self.home), found)
        self.assertFalse(
            self.store.exists(),
            "item 3: the gate never creates the store",
        )

    def test_key_still_open(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        proc = self.check(follows=[REVIEW], answers=[key])
        line = self.assert_refusal(proc, "correction")
        found = self.found_clause(line)
        self.assertIn(f"key {key} still open", found)
        needed = self.needed_clause(line)
        self.assertIn(f"'{key}'", needed)
        self.assertIn(
            "python3 ops/conductor/tools/findings.py disposition",
            needed,
        )

    def test_disposed_without_a_contract_citation(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        self.dispose(key, "fixed", "fixed in tests, no item")
        proc = self.check(follows=[REVIEW], answers=[key])
        line = self.assert_refusal(proc, "correction")
        found = self.found_clause(line)
        self.assertIn(key, found)
        self.assertIn("without a contract citation", found)
        self.assertIn("fixed", found)

    def test_newlines_in_evidence_still_one_stderr_line(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        self.dispose(key, "fixed", "line one\nline two without a citation")
        proc = self.check(follows=[REVIEW], answers=[key])
        line = self.assert_refusal(proc, "correction")
        self.assertNotIn("\n", line)
        self.assertIn("without a contract citation", line)

    def test_disposed_after_the_mint_attempt(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        self.dispose(key, "fixed", VALID_EVIDENCE)
        proc = self.check(follows=[REVIEW], answers=[key], at=PAST)
        line = self.assert_refusal(proc, "correction")
        found = self.found_clause(line)
        self.assertIn(key, found)
        self.assertIn("after the mint attempt at", found)
        self.assertIn(PAST, found)

    def test_same_second_is_not_before_the_mint(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        self.dispose(key, "fixed", VALID_EVIDENCE)
        self.set_disposed_at(key, SAME)
        proc = self.check(follows=[REVIEW], answers=[key], at=SAME)
        line = self.assert_refusal(proc, "correction")
        found = self.found_clause(line)
        self.assertIn(
            f"disposed at {SAME}, not before the mint attempt at {SAME}",
            found,
        )
        needed = self.needed_clause(line)
        self.assertIn("wait one second and retry", needed)

    def test_item_present_in_grammar_but_absent_from_the_file_is_uncited(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        evidence = (
            "contract item 99 of .dev/ladder-inputs/scope-gate-20260910.md: "
            "no such item"
        )
        self.dispose(key, "fixed", evidence)
        proc = self.check(follows=[REVIEW], answers=[key])
        line = self.assert_refusal(proc, "correction")
        self.assertIn("without a contract citation", self.found_clause(line))

    def test_first_failure_in_answers_order_is_the_open_key(self):
        self.plant_record(REVIEW, "adversarial-review", ["one", "two"])
        self.import_records()
        first = f"{REVIEW}#1"
        second = f"{REVIEW}#2"
        self.dispose(second, "fixed", VALID_EVIDENCE)
        proc = self.check(follows=[REVIEW], answers=[first, second])
        line = self.assert_refusal(proc, "correction")
        found = self.found_clause(line)
        self.assertIn(f"key {first} still open", found)
        self.assertNotIn(second, found)


class AcceptPath(_GateFixture):
    """Item 8 — accepted correction prints keys and citations."""

    def test_satisfying_row_prints_json_answers_with_citations(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        self.dispose(key, "fixed", VALID_EVIDENCE)
        proc = self.check(follows=[REVIEW], answers=[key])
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertEqual((proc.stderr or "").strip(), "")
        body = (proc.stdout or "").strip()
        self.assertTrue(body, "accept path prints JSON on stdout")
        payload = json.loads(body)
        self.assertTrue(payload["correction"])
        rows = payload["answers"]
        self.assertEqual(len(rows), 1, rows)
        row = rows[0]
        self.assertEqual(row["key"], key)
        self.assertEqual(row["disposition"], "fixed")
        self.assertTrue(row["disposed_at"])
        self.assertLess(row["disposed_at"], FUTURE)
        citation = row["citation"]
        self.assertEqual(str(citation["item"]), "3")
        self.assertEqual(citation["path"], SCOPE_REL)

    def test_author_tests_following_check_tests_is_a_correction(self):
        self.plant_record(CHECK, "check-tests")
        proc = self.check(job="author-tests", follows=[CHECK])
        line = self.assert_refusal(proc, "correction")
        self.assertIn("no --answers key named", line)
        self.assertIn(CHECK, line)
        self.assertIn("check-tests", line)


class NonCorrections(_GateFixture):
    """Item 7 / R8 — write jobs that are not the item-1 shape are untouched."""

    def _assert_not_a_correction(self, proc) -> None:
        err = proc.stderr or ""
        head = err.split(":", 1)[0].strip().lower().replace("_", "-")
        self.assertNotEqual(
            head,
            "correction",
            "item 7: the gate does not inspect a non-correction",
        )
        if proc.returncode != 0:
            self.assertEqual(proc.returncode, 2, err or proc.stdout)
            self.assertEqual(head, "arguments", err)
            return
        body = (proc.stdout or "").strip()
        self.assertTrue(body, "non-correction prints JSON")
        payload = json.loads(body)
        self.assertFalse(payload["correction"])

    def test_write_following_a_plan_record_is_not_a_correction(self):
        self.plant_record(PLAN, "plan")
        proc = self.check(follows=[PLAN])
        self._assert_not_a_correction(proc)

    def test_write_following_an_implement_record_is_not_a_correction(self):
        self.plant_record(IMPLEMENT, "implement")
        proc = self.check(follows=[IMPLEMENT])
        self._assert_not_a_correction(proc)

    def test_write_following_an_author_tests_record_is_not_a_correction(self):
        self.plant_record(AUTHOR, "author-tests")
        proc = self.check(follows=[AUTHOR])
        self._assert_not_a_correction(proc)

    def test_write_following_nothing_is_not_a_correction(self):
        proc = self.check()
        self._assert_not_a_correction(proc)

    def test_read_role_following_a_review_is_not_inspected(self):
        self.plant_record(REVIEW, "adversarial-review")
        proc = self.check(job="check-tests", role="read", follows=[REVIEW])
        self._assert_not_a_correction(proc)
        self.assertFalse(
            self.store.exists(),
            "item 7: a read role does not open the store",
        )

    def test_answers_on_a_non_correction_is_not_a_correction_refusal(self):
        self.plant_record(PLAN, "plan")
        proc = self.check(follows=[PLAN], answers=[f"{REVIEW}#1"])
        self._assert_not_a_correction(proc)
        err = proc.stderr or ""
        self.assertNotIn(
            "still open",
            err,
            "item 7: answers on a non-correction are not looked up",
        )
        self.assertNotIn("absent from the findings store", err)


class OutInputShape(_GateFixture):
    """Item 1 — an input under a review job's out/ is the correction shape."""

    def test_out_input_without_answers_is_the_no_key_arm(self):
        self.plant_record(REVIEW, "adversarial-review")
        note = self.jobs_root / REVIEW / "out" / "note.md"
        self._plant_bytes(note, b"review artifact\n")
        proc = self.check(inputs=[str(note)])
        line = self.assert_refusal(proc, "correction")
        self.assertIn("no --answers key named", line)
        self.assertIn(REVIEW, line)


class FollowsRefusals(_GateFixture):
    """Item 1 / R5 / R6 — shape is read from the record, never guessed."""

    def test_unknown_followed_id_is_class_follows(self):
        proc = self.check(follows=[MISSING])
        line = self.assert_refusal(proc, "follows")
        self.assertIn(MISSING, line)
        self.assertIn(".dev/records/dispatches", line)

    def test_malformed_followed_id_is_class_follows(self):
        proc = self.check(follows=["not-an-id"])
        line = self.assert_refusal(proc, "follows")
        self.assertIn("not-an-id", line)

    def test_record_id_field_mismatch_is_class_follows(self):
        path = self.plant_record(REVIEW, "adversarial-review")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["id"] = CHECK
        self._plant_bytes(
            path, (json.dumps(payload, indent=2) + "\n").encode("utf-8")
        )
        proc = self.check(follows=[REVIEW])
        line = self.assert_refusal(proc, "follows")
        self.assertIn(REVIEW, line)

    def test_job_outside_the_registry_is_class_follows(self):
        self.plant_record(REVIEW, "not-a-job")
        proc = self.check(follows=[REVIEW])
        line = self.assert_refusal(proc, "follows")
        self.assertIn(REVIEW, line)

    def test_symlink_escape_from_records_is_class_follows(self):
        outside = self.scratch / f"{REVIEW}.json"
        self.plant_record(REVIEW, "adversarial-review")
        src = self.records / f"{REVIEW}.json"
        outside.write_bytes(src.read_bytes())
        src.unlink()
        src.symlink_to(outside)
        self.assertTrue(src.is_symlink())
        proc = self.check(follows=[REVIEW])
        line = self.assert_refusal(proc, "follows")
        self.assertIn(REVIEW, line)


class ArgumentsShape(_GateFixture):
    """Item 2 / R2 — a key that fails the shape is refused, never echoed."""

    def test_malformed_answers_key_is_arguments_and_not_echoed(self):
        self.plant_record(REVIEW, "adversarial-review")
        proc = self.check(follows=[REVIEW], answers=[BAD_KEY])
        line = self.assert_refusal(proc, "arguments")
        self.assertNotIn(
            BAD_KEY,
            line,
            "R2: a key that fails the shape is never echoed",
        )

    def test_zero_n_answers_key_is_arguments_and_not_echoed(self):
        self.plant_record(REVIEW, "adversarial-review")
        proc = self.check(follows=[REVIEW], answers=[ZERO_KEY])
        line = self.assert_refusal(proc, "arguments")
        self.assertNotIn(
            ZERO_KEY,
            line,
            "R2: n starts at 1; #0 is not echoed in the remedy",
        )


class NoOverride(_GateFixture):
    """Item 6 — no overrides row and no hand-grant escape."""

    def test_override_flag_does_not_admit_a_correction(self):
        self.plant_record(REVIEW, "adversarial-review")
        proc = self.check(
            follows=[REVIEW],
            extra=["--override", "correction:reason"],
        )
        err = proc.stderr or ""
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        head = err.split(":", 1)[0].strip().lower().replace("_", "-")
        self.assertNotEqual(head, "correction")
        self.assertNotIn("override permitted", err.lower())
        self.assertNotIn("hand-grant", err.lower())
        body = (proc.stdout or "").strip()
        if body:
            payload = json.loads(body)
            self.assertFalse(payload.get("correction"))


class RegistryJoin(_GateFixture):
    """Item 10 — the gate joins the refusal registry with two hermetic rows."""

    def test_registry_file_has_the_two_hermetic_rows(self):
        self.assertTrue(
            REGISTRY.is_file(),
            "item 10: correction.py joins the registry in the landing change",
        )
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["tool"], "correction.py")
        self.assertEqual(data["rows"], list(REGISTRY_ROWS))

    def test_bare_check_is_class_arguments(self):
        proc = subprocess.run(
            [sys.executable, str(self.tool), "check"],
            cwd=str(self.repo),
            env=self.env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )
        self.assert_refusal(proc, "arguments")


if __name__ == "__main__":
    unittest.main()
