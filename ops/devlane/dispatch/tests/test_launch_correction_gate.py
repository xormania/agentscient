"""Launcher mint of the uncited-correction gate.

Written from scope-gate-20260910.md items 1-8 and Dispatch §Refusals
rows `correction` (exit 2, founding wire), `follows`, and `arguments`.
launch.py is the subject and is not read here.

A correction-shaped write with no --answers currently launches. A
write that passes --answers currently dies in argparse usage, which is
not one bare `correction:` or `arguments:` line. Those are the reds.
Item 7 neighbours that already launch stay the silent neighbours, and
fail until the minted record carries answers: [].
"""

from __future__ import annotations

import json
import os
import shlex
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

import launch_support as ls

FINDINGS = ls.REPO / "ops" / "conductor" / "tools" / "findings.py"
REVIEW = "20260901T000000Z-review-grok-aaaaaa"
PLAN = "20260901T030000Z-plan-claude-dddddd"
IMPLEMENT = "20260901T040000Z-code-codex-eeeeee"
AUTHOR = "20260901T050000Z-tests-grok-ffffff"
CHECK = "20260901T060000Z-check-tests-codex-111111"
SECURITY = "20260901T070000Z-review-codex-222222"
ADJUDICATE = "20260901T080000Z-adjudicate-grok-333333"
SWEEP = "20260901T090000Z-sweep-codex-444444"
MISSING = "20260101T000000Z-review-codex-000000"
OTHER_REVIEW = "20260901T000000Z-review-grok-ffffff"
OTHER_KEY = f"{OTHER_REVIEW}#1"
BAD_KEY = "not-a-key"
SCOPE_REL = ".dev/ladder-inputs/scope-gate-20260910.md"
VALID_EVIDENCE = (
    "contract item 3 of .dev/ladder-inputs/scope-gate-20260910.md: "
    "found-text missing"
)
SCOPE_BODY = "# Work order\n\n" + "".join(
    f"{n}. Item {n} of the work order.\n" for n in range(1, 11)
)
DISPOSITION_MARK = "python3 ops/conductor/tools/findings.py disposition"
RUN_CAP = 30
STAMP = "2026-09-10T12:00:01Z"
SAME = "2026-09-10T12:00:00Z"
PAST = "2000-01-01T00:00:00Z"
FUTURE = "2099-01-01T00:00:00Z"
WIRE_EXIT = 2

REVIEW_JOBS = (
    (REVIEW, "adversarial-review"),
    (CHECK, "check-tests"),
    (SECURITY, "security-audit"),
    (ADJUDICATE, "adjudicate"),
    (SWEEP, "sweep"),
)


def evidence_for(item: int, path: str = SCOPE_REL, why: str = "why") -> str:
    return f"contract item {item} of {path}: {why}"


def _store_snapshot(path: Path) -> tuple[str, bytes | None]:
    if path.is_file():
        return ("file", path.read_bytes())
    if path.exists():
        return ("other", None)
    return ("absent", None)


class _CorrectionLaunch(ls._TempLaunch):
    """Throwaway repo plus a planted review record and an isolated ledger."""

    maxDiff = None

    def setUp(self):
        self._live_store = (
            Path.home() / ".local" / "state" / "agentscient" / "findings.db"
        )
        self._live_before = _store_snapshot(self._live_store)
        super().setUp()
        os.environ.pop("XDG_STATE_HOME", None)
        self.planted_ids: set[str] = set()
        self.store = (
            self.home / ".local" / "state" / "agentscient" / "findings.db"
        )
        self.records = self.repo / ".dev" / "records" / "dispatches"
        self.records.mkdir(parents=True, exist_ok=True)
        self.findings = self._stage_findings()
        self.scope = self.repo / SCOPE_REL
        self.plant_new_file(self.scope, SCOPE_BODY, must_contain="1. Item 1")
        self.ref = self._commit("scope file")
        self.assertFalse(
            self.store.exists(),
            "plant: isolated findings store must start absent",
        )

    def tearDown(self):
        try:
            self.assertEqual(
                _store_snapshot(self._live_store),
                self._live_before,
                f"live store mutated: {self._live_store}",
            )
        finally:
            super().tearDown()

    def findings_env(self) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "WF_AGENT": ls.AGENT,
        }
        env.pop("XDG_STATE_HOME", None)
        return env

    def _stage_findings(self) -> Path:
        self.assertTrue(FINDINGS.is_file(), f"{FINDINGS} is missing")
        dest = self.repo / "ops" / "conductor" / "tools" / "findings.py"
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = FINDINGS.read_bytes()
        dest.write_bytes(data)
        landed = dest.read_bytes()
        self.assertEqual(landed, data, "copy-findings-bytes did not land intact")
        return dest

    def findings_invoke(self, argv: list[str]):
        return subprocess.run(
            [sys.executable, str(self.findings), *argv],
            cwd=str(self.repo),
            env=self.findings_env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )

    def plant_record(
        self,
        rec_id: str,
        job: str,
        claims: list[str] | None = None,
    ) -> Path:
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
            "role": (
                "read" if job not in ("implement", "author-tests") else "write"
            ),
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
        self.plant_new_file(path, json.dumps(envelope, indent=2) + "\n")
        self.planted_ids.add(rec_id)
        return path

    def import_records(self):
        proc = self.findings_invoke(["import"])
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertTrue(self.store.is_file(), "import must create the store")
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

    def force_stamp(self, stamp: str) -> str:
        launch = self.load_launch()
        launch._now = lambda: stamp
        return stamp

    def write_argv(self, extra=(), job="implement", harness="codex", stage="code"):
        return self.argv_for(
            job=job,
            harness=harness,
            stage=stage,
            scope=SCOPE_REL,
            extra=list(extra),
        )

    def read_argv(self, extra=()):
        return self.argv_for(
            job="plan",
            harness="grok",
            stage="plan",
            extra=list(extra),
        )

    def minted_record_files(self):
        return [
            path for path in self.record_files()
            if path.stem not in self.planted_ids
        ]

    def assert_no_mint(self):
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])
        minted = self.minted_record_files()
        self.assertEqual(minted, [], f"refusal minted a record: {minted}")

    def launched_record(self):
        files = self.minted_record_files()
        self.assertEqual(
            len(files), 1, f"expected one minted record, found {files}"
        )
        return self.read_record(files[0])

    def launch_ok_minted(self, argv=None, **kwargs):
        code, out, err = self.dispatch(argv, **kwargs)
        text = self.combined(out, err)
        self.assertNotEqual(
            code, ls.REFUSAL_EXIT,
            f"happy path must not refuse (exit 3): {text!r}",
        )
        self.assertEqual(code, 0, f"happy path exits 0, got {code}: {text!r}")
        rec = self.launched_record()
        self.assertEqual(rec.get("status"), "closed")
        return rec, self.read_witness(), out, err

    def assert_wire_line(self, code, out, err, ident):
        text = self.combined(out, err)
        self.assertEqual(
            code, WIRE_EXIT,
            f"{ident} refuses with exit 2, got {code}: {text!r}",
        )
        self.assertEqual(
            (out or "").strip(), "",
            f"{ident} stdout must be empty: {out!r}",
        )
        err = err or ""
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(
            len(lines), 1,
            f"{ident} refusal must be one stderr line, not argparse "
            f"usage: {err!r}",
        )
        line = lines[0]
        self.assertNotIn("\n", line)
        lower = line.lower()
        token = ident.lower().replace("_", "-")
        self.assertRegex(
            line,
            rf"^{token}:\s*expected",
            f"{ident}: expected is the refusal class token: {line!r}",
        )
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, f"{ident} names {word}: {line!r}")
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

    def assert_expected_before_stamp(self, line: str, stamp: str | None = None):
        self.assertIn(
            "every finding answered by this correction "
            "disposed with a contract citation before",
            line,
        )
        if stamp is not None:
            self.assertIn(stamp, line)

    def assert_needed_disposition(self, needed: str, key: str, *, import_then=False):
        if import_then:
            self.assertIn(
                "python3 ops/conductor/tools/findings.py import, then",
                needed,
            )
        self.assertIn(DISPOSITION_MARK, needed)
        start = needed.index(DISPOSITION_MARK)
        try:
            parts = shlex.split(needed[start:])
        except ValueError as exc:
            self.fail(f"needed command is not shell-quotable: {needed!r} ({exc})")
        self.assertGreaterEqual(len(parts), 6, parts)
        self.assertEqual(parts[0], "python3")
        self.assertEqual(parts[1], "ops/conductor/tools/findings.py")
        self.assertEqual(parts[2], "disposition")
        self.assertEqual(parts[3], key, parts)
        self.assertTrue(parts[4].strip(), "needed omits the disposition")
        self.assertIn("contract item ", parts[5])
        self.assertIn(f" of {SCOPE_REL}", parts[5])
        self.assertIn(shlex.quote(key), needed)
        self.assertIn(shlex.quote(parts[5]), needed)
        return parts[:6]


class FiveFoundTexts(_CorrectionLaunch):
    """Item 3 — distinct found-texts, founding wire, no mint."""

    def test_no_answers_key_named_for_a_correction(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.force_stamp(STAMP)
        code, out, err = self.dispatch(
            self.write_argv(extra=["--follows", REVIEW]),
        )
        line = self.assert_wire_line(code, out, err, "correction")
        self.assert_no_mint()
        self.assert_expected_before_stamp(line, STAMP)
        found = self.found_clause(line)
        self.assertEqual(
            found,
            f"no --answers key named for a correction following {REVIEW} "
            f"(adversarial-review)",
        )
        needed = self.needed_clause(line)
        self.assertIn("pass --answers", needed)
        self.assertIn(DISPOSITION_MARK, needed)
        self.assertIn(shlex.quote(f"{REVIEW}#1"), needed)

    def test_key_absent_from_the_store(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        self.force_stamp(STAMP)
        code, out, err = self.dispatch(self.write_argv(extra=[
            "--follows", REVIEW, "--answers", OTHER_KEY,
        ]))
        line = self.assert_wire_line(code, out, err, "correction")
        self.assert_no_mint()
        self.assert_expected_before_stamp(line, STAMP)
        found = self.found_clause(line)
        self.assertEqual(
            found,
            f"key {OTHER_KEY} absent from the findings store {self.store}",
        )
        self.assertNotIn("(no store)", found)
        self.assert_needed_disposition(
            self.needed_clause(line), OTHER_KEY, import_then=True,
        )

    def test_missing_store_names_no_store_and_does_not_create_one(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.assertFalse(self.store.exists())
        key = f"{REVIEW}#1"
        self.force_stamp(STAMP)
        code, out, err = self.dispatch(self.write_argv(extra=[
            "--follows", REVIEW, "--answers", key,
        ]))
        line = self.assert_wire_line(code, out, err, "correction")
        self.assert_no_mint()
        found = self.found_clause(line)
        self.assertIn("absent from the findings store", found)
        self.assertIn("(no store)", found)
        self.assertIn(str(self.store), found)
        self.assertFalse(
            self.store.exists(),
            "item 3: the gate never creates the store",
        )
        self.assert_needed_disposition(
            self.needed_clause(line), key, import_then=True,
        )

    def test_key_still_open(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        self.force_stamp(STAMP)
        code, out, err = self.dispatch(self.write_argv(extra=[
            "--follows", REVIEW, "--answers", key,
        ]))
        line = self.assert_wire_line(code, out, err, "correction")
        self.assert_no_mint()
        found = self.found_clause(line)
        self.assertEqual(found, f"key {key} still open")
        self.assert_needed_disposition(self.needed_clause(line), key)

    def test_disposed_without_a_contract_citation(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        self.dispose(key, "fixed", "fixed in tests, no item")
        self.force_stamp(STAMP)
        code, out, err = self.dispatch(self.write_argv(extra=[
            "--follows", REVIEW, "--answers", key,
        ]))
        line = self.assert_wire_line(code, out, err, "correction")
        self.assert_no_mint()
        found = self.found_clause(line)
        self.assertIn(key, found)
        self.assertIn("without a contract citation", found)
        self.assertIn("fixed", found)
        self.assert_needed_disposition(self.needed_clause(line), key)

    def test_newlines_in_evidence_still_one_stderr_line(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        self.dispose(key, "fixed", "line one\nline two without a citation")
        code, out, err = self.dispatch(self.write_argv(extra=[
            "--follows", REVIEW, "--answers", key,
        ]))
        line = self.assert_wire_line(code, out, err, "correction")
        self.assert_no_mint()
        self.assertNotIn("\n", line)
        self.assertIn("without a contract citation", line)

    def test_disposed_after_the_mint_attempt(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        self.dispose(key, "fixed", VALID_EVIDENCE)
        self.set_disposed_at(key, FUTURE)
        self.force_stamp(STAMP)
        code, out, err = self.dispatch(self.write_argv(extra=[
            "--follows", REVIEW, "--answers", key,
        ]))
        line = self.assert_wire_line(code, out, err, "correction")
        self.assert_no_mint()
        found = self.found_clause(line)
        self.assertIn(key, found)
        self.assertIn("after the mint attempt at", found)
        self.assertIn(FUTURE, found)
        self.assertIn(STAMP, found)
        self.assert_needed_disposition(self.needed_clause(line), key)

    def test_same_second_is_not_before_the_mint(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        self.dispose(key, "fixed", VALID_EVIDENCE)
        self.set_disposed_at(key, SAME)
        self.force_stamp(SAME)
        code, out, err = self.dispatch(self.write_argv(extra=[
            "--follows", REVIEW, "--answers", key,
        ]))
        line = self.assert_wire_line(code, out, err, "correction")
        self.assert_no_mint()
        found = self.found_clause(line)
        self.assertEqual(
            found,
            f"key {key} disposed at {SAME}, not before the mint attempt "
            f"at {SAME}",
        )
        needed = self.needed_clause(line)
        self.assertIn("wait one second and retry", needed)
        self.assertNotIn(DISPOSITION_MARK, needed)

    def test_first_failure_in_answers_order_is_the_open_key(self):
        self.plant_record(REVIEW, "adversarial-review", ["one", "two"])
        self.import_records()
        first = f"{REVIEW}#1"
        second = f"{REVIEW}#2"
        self.dispose(second, "fixed", VALID_EVIDENCE)
        self.set_disposed_at(second, PAST)
        self.force_stamp(STAMP)
        code, out, err = self.dispatch(self.write_argv(extra=[
            "--follows", REVIEW,
            "--answers", first,
            "--answers", second,
        ]))
        line = self.assert_wire_line(code, out, err, "correction")
        self.assert_no_mint()
        found = self.found_clause(line)
        self.assertEqual(found, f"key {first} still open")
        self.assertNotIn(second, found)


class AcceptRecordsAnswers(_CorrectionLaunch):
    """Item 8 — an accepted correction's record carries keys and citations."""

    def test_satisfying_row_records_answers_and_reuses_the_gate_stamp(self):
        self.plant_record(REVIEW, "adversarial-review")
        self.import_records()
        key = f"{REVIEW}#1"
        self.dispose(key, "fixed", VALID_EVIDENCE)
        self.set_disposed_at(key, PAST)
        self.force_stamp(STAMP)
        rec, witness, _out, err = self.launch_ok_minted(self.write_argv(extra=[
            "--follows", REVIEW, "--answers", key,
        ]))
        self.assertTrue(witness["argv"])
        self.assertEqual((err or "").strip(), "")
        self.assertEqual(rec["at"]["launched"], STAMP)
        self.assertEqual(rec["follows"], [REVIEW])
        rows = rec["answers"]
        self.assertEqual(len(rows), 1, rows)
        row = rows[0]
        self.assertEqual(row["key"], key)
        self.assertEqual(row["disposition"], "fixed")
        self.assertEqual(row["disposed_at"], PAST)
        self.assertEqual(str(row["citation"]["item"]), "3")
        self.assertEqual(row["citation"]["path"], SCOPE_REL)


class NonCorrectionsUntouched(_CorrectionLaunch):
    """Item 7 — a write that is not the item-1 shape is not inspected."""

    def _assert_neighbour(self, rec):
        self.assertEqual(rec.get("answers"), [])
        self.assertIsInstance(rec["answers"], list)

    def test_write_following_a_plan_record_is_not_a_correction(self):
        self.plant_record(PLAN, "plan")
        rec, *_ = self.launch_ok_minted(self.write_argv(extra=["--follows", PLAN]))
        self.assertEqual(rec["follows"], [PLAN])
        self._assert_neighbour(rec)

    def test_write_following_an_implement_record_is_not_a_correction(self):
        self.plant_record(IMPLEMENT, "implement")
        rec, *_ = self.launch_ok_minted(
            self.write_argv(extra=["--follows", IMPLEMENT]),
        )
        self._assert_neighbour(rec)

    def test_write_following_an_author_tests_record_is_not_a_correction(self):
        self.plant_record(AUTHOR, "author-tests")
        rec, *_ = self.launch_ok_minted(
            self.write_argv(extra=["--follows", AUTHOR]),
        )
        self._assert_neighbour(rec)

    def test_write_following_nothing_is_not_a_correction(self):
        rec, *_ = self.launch_ok(self.write_argv())
        self.assertEqual(rec["follows"], [])
        self._assert_neighbour(rec)

    def test_read_job_following_a_review_is_not_inspected(self):
        self.plant_record(REVIEW, "adversarial-review")
        rec, *_ = self.launch_ok_minted(
            self.read_argv(extra=["--follows", REVIEW]),
        )
        self.assertEqual(rec["job"], "plan")
        self.assertEqual(rec["role"], "read")
        self._assert_neighbour(rec)
        self.assertFalse(
            self.store.exists(),
            "item 7: a read role does not open the store",
        )

    def test_read_job_following_an_unknown_id_launches(self):
        rec, *_ = self.launch_ok(self.read_argv(extra=["--follows", MISSING]))
        self.assertEqual(rec["follows"], [MISSING])
        self._assert_neighbour(rec)


class CorrectionShape(_CorrectionLaunch):
    """Item 1 — write-role + review follow or out/ input is a correction."""

    def test_every_review_job_follow_is_a_correction(self):
        for rec_id, job in REVIEW_JOBS:
            with self.subTest(job=job):
                self.plant_record(rec_id, job)
                self.force_stamp(STAMP)
                code, out, err = self.dispatch(
                    self.write_argv(extra=["--follows", rec_id]),
                )
                line = self.assert_wire_line(code, out, err, "correction")
                self.assert_no_mint()
                found = self.found_clause(line)
                self.assertEqual(
                    found,
                    f"no --answers key named for a correction following "
                    f"{rec_id} ({job})",
                )

    def test_out_input_under_a_review_job_is_a_correction(self):
        self.plant_record(REVIEW, "adversarial-review")
        note = self.jobs_root / REVIEW / "out" / "note.md"
        self.plant_new_file(note, "review artifact\n")
        self.force_stamp(STAMP)
        code, out, err = self.dispatch(
            self.write_argv(extra=["--input", str(note)]),
        )
        line = self.assert_wire_line(code, out, err, "correction")
        self.assert_no_mint()
        self.assertIn("no --answers key named", line)
        self.assertIn(REVIEW, line)
        self.assertIn("adversarial-review", line)

    def test_author_tests_following_check_tests_is_a_correction(self):
        self.plant_record(CHECK, "check-tests")
        self.force_stamp(STAMP)
        code, out, err = self.dispatch(self.write_argv(
            extra=["--follows", CHECK],
            job="author-tests",
            harness="grok",
            stage="tests",
        ))
        line = self.assert_wire_line(code, out, err, "correction")
        self.assert_no_mint()
        found = self.found_clause(line)
        self.assertEqual(
            found,
            f"no --answers key named for a correction following {CHECK} "
            f"(check-tests)",
        )

    def test_write_following_an_unknown_id_is_follows(self):
        code, out, err = self.dispatch(
            self.write_argv(extra=["--follows", MISSING]),
        )
        line = self.assert_wire_line(code, out, err, "follows")
        self.assert_no_mint()
        self.assertIn(MISSING, line)
        self.assertIn(".dev/records/dispatches", line)


class AnswersOnNonCorrection(_CorrectionLaunch):
    """Item 2 / item 7 — --answers on a non-correction is arguments, not a gate inspection."""

    def test_answers_on_a_write_following_a_plan_is_arguments(self):
        self.plant_record(PLAN, "plan")
        key = f"{REVIEW}#1"
        code, out, err = self.dispatch(self.write_argv(extra=[
            "--follows", PLAN, "--answers", key,
        ]))
        line = self.assert_wire_line(code, out, err, "arguments")
        self.assert_no_mint()
        needed = self.needed_clause(line).lower()
        self.assertIn("remove --answers", needed)
        self.assertNotIn("still open", line)
        self.assertNotIn("absent from the findings store", line)

    def test_answers_on_a_write_following_nothing_is_arguments(self):
        key = f"{REVIEW}#1"
        code, out, err = self.dispatch(
            self.write_argv(extra=["--answers", key]),
        )
        line = self.assert_wire_line(code, out, err, "arguments")
        self.assert_no_mint()
        self.assertIn("remove --answers", self.needed_clause(line).lower())

    def test_malformed_answers_key_is_arguments_and_not_echoed(self):
        self.plant_record(REVIEW, "adversarial-review")
        code, out, err = self.dispatch(self.write_argv(extra=[
            "--follows", REVIEW, "--answers", BAD_KEY,
        ]))
        line = self.assert_wire_line(code, out, err, "arguments")
        self.assert_no_mint()
        self.assertNotIn(
            BAD_KEY,
            line,
            "a key that fails the shape is never echoed in the remedy",
        )


class NoOverride(_CorrectionLaunch):
    """Item 6 — the gate has no overrides row and no hand-grant escape."""

    def test_override_correction_is_refused_as_override(self):
        self.plant_record(REVIEW, "adversarial-review")
        code, out, err = self.dispatch(self.write_argv(extra=[
            "--follows", REVIEW, "--override", "correction:reason",
        ]))
        text = self.combined(out, err)
        self.assertEqual(
            code, ls.REFUSAL_EXIT,
            f"item 6: --override correction:reason is the existing "
            f"override refusal, exit 3, got {code}: {text!r}",
        )
        self.assert_no_mint()
        lower = text.lower()
        self.assertIn("override", lower)
        self.assertNotIn("hand-grant", lower)
        lines = [ln for ln in (err or "").splitlines() if ln.strip()]
        if lines:
            head = lines[0].split(":", 1)[0].strip().lower()
            self.assertNotEqual(head, "correction")


if __name__ == "__main__":
    unittest.main()
