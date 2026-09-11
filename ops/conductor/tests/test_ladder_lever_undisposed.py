"""Ladder stop before fix stages when audit findings are undisposed.

Written from scope-gate-20260910.md item 9 (and the item-1 shape the
fix stages must then carry). ladder.py is the subject and is not read
here. Tests reuse _LadderFixture; the FINDINGS_PY stub is extended with
a plant dispositions map answering `cited`, and the dispatch stub plants
stage_findings onto audit envelopes.

A driver that launches fix-tests while a finding is undisposed still
collects; it fails the stop assertion. A driver that stops but dispatches
a fix stage with one --follows and no --answers still collects; it fails
the argv assertion.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from test_ladder_lever import RUN_CAP, _LadderFixture  # noqa: E402

RECORD_ID = r"^\d{8}T\d{6}Z-[a-z-]+-[a-z]+-[0-9a-f]{6}$"
ANSWER_KEY = r"^\d{8}T\d{6}Z-[a-z-]+-[a-z]+-[0-9a-f]{6}#[1-9][0-9]*$"
SCOPE_PATH = ".dev/ladder-inputs/scope-gate-20260910.md"
CITATION = f"contract item 9 of {SCOPE_PATH}"
FINDING = {
    "severity": "p2",
    "where": "ops/conductor/ladder-lever.md",
    "claim": "UNDISPOSED_ADV_aa32 audit finding lacks a cited disposition",
    "reproduce": (
        "python3 -m unittest discover -s ops/conductor/tests "
        "-p test_ladder_lever_undisposed.py"
    ),
}

FINDINGS_CITED_PY = r'''
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

STUB = Path("@@STUB@@")
argv = sys.argv[1:]
log = STUB / "findings-argv.jsonl"
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
plant_path = STUB / "plant.json"
plant = json.loads(plant_path.read_text(encoding="utf-8"))
plant.setdefault("cwds", []).append(os.getcwd())
plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
if plant.get("ledger_fail"):
    sys.stderr.write(
        "ledger: expected a writable findings export; found a write error; "
        "needed a writable ledger\n"
    )
    raise SystemExit(3)
if argv and argv[0] == "cited":
    if len(argv) < 2 or not str(argv[1]).strip():
        sys.stderr.write(
            "key: expected KEY; found none; needed findings.py cited KEY\n"
        )
        raise SystemExit(2)
    key = argv[1]
    dispositions = plant.get("dispositions") or {}
    citation = dispositions.get(key)
    if plant.get("cited_all") and citation is None:
        citation = (
            "contract item 9 of .dev/ladder-inputs/scope-gate-20260910.md"
        )
    if citation in (None, "", "open"):
        sys.stdout.write(key + "\topen\n")
        raise SystemExit(1)
    text = str(citation)
    if text.startswith("uncited"):
        sys.stdout.write(key + "\t" + text + "\n")
        raise SystemExit(1)
    sys.stdout.write(key + "\t" + text + "\n")
    raise SystemExit(0)
if argv and argv[0] == "export":
    sys.stdout.write("{}\n")
raise SystemExit(0)
'''.lstrip()

DISPATCH_FINDINGS_NEEDLE = "findings = []\n"
DISPATCH_FINDINGS_INSERT = (
    "findings = []\n"
    "extra = (plant.get(\"stage_findings\") or {}).get(name) or []\n"
    "if extra:\n"
    "    findings.extend(list(extra))\n"
)


class _UndisposedFixture(_LadderFixture):
    """Audit-changes plant plus cited / stage_findings stub extensions."""

    def _plant_stub_scripts(self) -> None:
        super()._plant_stub_scripts()
        self._extend_dispatch_stage_findings()
        self._extend_findings_cited()

    def _extend_dispatch_stage_findings(self) -> None:
        path = self.stub_dir / "dispatch.py"
        before = path.read_text(encoding="utf-8")
        self.assertIn(
            DISPATCH_FINDINGS_NEEDLE,
            before,
            "dispatch stub findings plant anchor missing",
        )
        self.assertEqual(before.count(DISPATCH_FINDINGS_NEEDLE), 1, before)
        after = before.replace(
            DISPATCH_FINDINGS_NEEDLE, DISPATCH_FINDINGS_INSERT, 1,
        )
        self.assertNotEqual(after, before, "stage_findings insert was a no-op")
        self.assertIn("stage_findings", after)
        self._plant_bytes(path, after.encode("utf-8"))
        landed = path.read_text(encoding="utf-8")
        self.assertIn("stage_findings", landed)

    def _extend_findings_cited(self) -> None:
        body = self._fill(FINDINGS_CITED_PY)
        dest = self.stub_dir / "findings.py"
        self._plant_bytes(dest, body.encode("utf-8"))
        landed = dest.read_text(encoding="utf-8")
        self.assertIn("dispositions", landed)
        self.assertIn('argv[0] == "cited"', landed)

    def setUp(self):
        super().setUp()
        wt = self.repo / "ops" / "conductor" / "tools" / "findings.py"
        self.assertTrue(wt.is_file(), wt)
        self.assertIn("dispositions", wt.read_text(encoding="utf-8"))
        self.assertIn(
            "stage_findings",
            (self.stub_dir / "dispatch.py").read_text(encoding="utf-8"),
        )
        probe = self.cited_probe("20260901T000000Z-review-grok-aaaaaa#1")
        self.assertEqual(
            probe.returncode, 1,
            f"cited stub must treat an unknown key as open: "
            f"{probe.stdout!r} {probe.stderr!r}",
        )
        self.assertIn("\topen", probe.stdout)
        log = self.stub_dir / "findings-argv.jsonl"
        if log.exists():
            log.unlink()
        self.assertEqual(self.findings_argvs(), [])

    def cited_probe(self, key: str):
        tool = self.repo / "ops" / "conductor" / "tools" / "findings.py"
        return subprocess.run(
            [sys.executable, str(tool), "cited", key],
            cwd=str(self.invoke_cwd),
            env=self.env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )

    def plant_undisposed_audit(self, *, cited_all: bool = False) -> None:
        updates = {
            "verdicts": {"adversarial": "changes"},
            "stage_findings": {"adversarial": [FINDING]},
        }
        if cited_all:
            updates["cited_all"] = True
        self.patch_plant(**updates)
        plant = self.load_plant()
        self.assertEqual(plant["verdicts"].get("adversarial"), "changes")
        planted = (plant.get("stage_findings") or {}).get("adversarial") or []
        self.assertEqual(len(planted), 1, planted)
        self.assertEqual(planted[0]["claim"], FINDING["claim"])
        self.assertEqual(bool(plant.get("cited_all")), cited_all)

    def run_undisposed(self, *, cited_all: bool = False):
        self.plant_undisposed_audit(cited_all=cited_all)
        return self.run_ladder()

    def closed_envelope(self, name: str) -> dict:
        rec_id = self.record_id_for(name)
        path = Path(self.load_plant()["records"][rec_id]["path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        envelope = (payload.get("result") or {}).get("envelope") or {}
        self.assertIsInstance(envelope, dict, payload)
        return envelope

    def assert_finding_landed(self) -> None:
        findings = self.closed_envelope("adversarial").get("findings") or []
        self.assertEqual(len(findings), 1, findings)
        self.assertEqual(findings[0]["claim"], FINDING["claim"], findings)
        self.assertEqual(findings[0]["where"], FINDING["where"], findings)

    def adversarial_key(self) -> str:
        self.assert_finding_landed()
        rec_id = self.record_id_for("adversarial")
        self.assertRegex(rec_id, RECORD_ID, rec_id)
        key = rec_id + "#1"
        self.assertRegex(key, ANSWER_KEY, key)
        return key

    def cited_keys(self) -> list[str]:
        keys: list[str] = []
        for row in self.findings_argvs():
            if row and row[0] == "cited" and len(row) > 1:
                keys.append(str(row[1]))
        return keys

    def findings_verbs(self) -> list[str]:
        return [row[0] if row else "" for row in self.findings_argvs()]

    def undisposed_keys_line(self, proc) -> str:
        lines = [
            ln for ln in self.combined(proc).splitlines() if ln.strip()
        ]
        hits = [ln for ln in lines if "undisposed keys:" in ln]
        self.assertEqual(
            len(hits), 1,
            f"item 9: one detail line names the undisposed keys; "
            f"got {hits!r} in {self.combined(proc)!r}",
        )
        self.assertLess(
            lines.index(hits[0]),
            lines.index(lines[-1]),
            "item 9: the keys line is printed before the stopped line",
        )
        return hits[0]

    def author_tests_after_audits(self) -> list[str]:
        seen_audit = False
        later: list[str] = []
        for row in self.dispatch_calls():
            if row.get("name") in {"security", "adversarial"}:
                seen_audit = True
                continue
            if seen_audit and row.get("job") == "author-tests":
                later.append(row.get("name") or "")
        return later


class UndisposedStopsFixTests(_UndisposedFixture):
    """Item 9 — stop before fix-tests when a finding is undisposed."""

    def test_stop_line_is_undisposed_at_fix_tests_with_record_none(self):
        proc = self.run_undisposed()
        self.assert_finding_landed()
        self.assert_stopped(
            proc, stage="fix-tests", record="none", reason="undisposed",
        )

    def test_detail_line_names_the_undisposed_key(self):
        proc = self.run_undisposed()
        key = self.adversarial_key()
        line = self.undisposed_keys_line(proc)
        listed = line.split("undisposed keys:", 1)[1].split()
        self.assertEqual(len(listed), 1, line)
        self.assertEqual(listed[0], key, line)
        self.assert_stopped(
            proc, stage="fix-tests", record="none", reason="undisposed",
        )

    def test_no_author_tests_dispatch_after_the_audits(self):
        proc = self.run_undisposed()
        names = self.dispatch_names()
        self.assertIn("security", names, names)
        self.assertIn("adversarial", names, names)
        self.assertNotIn("fix-tests", names, names)
        self.assertNotIn("fix-code", names, names)
        self.assertEqual(self.author_tests_after_audits(), [], names)
        self.assert_stopped(
            proc, stage="fix-tests", record="none", reason="undisposed",
        )

    def test_fix_tests_attempt_is_not_incremented(self):
        proc = self.run_undisposed()
        row = self.stage_row(self.ladder_record(), "fix-tests")
        attempt = row.get("attempt")
        if attempt is None:
            attempt = 0
        self.assertEqual(
            int(attempt), 0,
            f"item 9: a stop before mint is not an attempt: {row!r}",
        )
        self.assertNotEqual(row.get("outcome"), "skipped", row)
        self.assert_stopped(
            proc, stage="fix-tests", record="none", reason="undisposed",
        )

    def test_record_stopped_keys_lists_the_undisposed_key(self):
        proc = self.run_undisposed()
        key = self.adversarial_key()
        record = self.ladder_record()
        stopped = record.get("stopped") or {}
        keys = stopped.get("keys")
        self.assertIsInstance(
            keys, list,
            f"item 9: stopped.keys is a list of undisposed keys; "
            f"got {stopped!r} status={record.get('status')!r}",
        )
        self.assertEqual(len(keys), 1, keys)
        self.assertEqual(keys[0], key, keys)
        self.assertEqual(record.get("status"), "stopped", record)
        self.assertEqual(stopped.get("stage"), "fix-tests", stopped)
        self.assertEqual(stopped.get("reason"), "undisposed", stopped)
        self.assert_stopped(
            proc, stage="fix-tests", record="none", reason="undisposed",
        )

    def test_driver_cites_the_undisposed_key_before_stopping(self):
        proc = self.run_undisposed()
        key = self.adversarial_key()
        asked = self.cited_keys()
        self.assertTrue(
            asked,
            f"item 9: the driver checks the key with cited; "
            f"findings argv={self.findings_argvs()!r}",
        )
        self.assertIn(key, asked, asked)
        self.assertNotIn("disposition", self.findings_verbs())
        self.assert_stopped(
            proc, stage="fix-tests", record="none", reason="undisposed",
        )


class ResumeRechecksCited(_UndisposedFixture):
    """Item 9 — resume re-runs the check; rows let the fix stages launch."""

    def test_resume_without_rows_stops_undisposed_again_not_retry_cap(self):
        first = self.run_undisposed()
        self.assert_stopped(
            first, stage="fix-tests", record="none", reason="undisposed",
        )
        ladder_id = self.ladder_record().get("id")
        self.assertTrue(ladder_id)
        second = self.invoke(["resume", ladder_id])
        self.assert_stopped(
            second, stage="fix-tests", record="none", reason="undisposed",
        )
        text = self.combined(second)
        self.assertNotIn("retry-cap", text)
        self.assertNotIn("fix-tests", self.dispatch_names())
        row = self.stage_row(self.ladder_record(ladder_id), "fix-tests")
        attempt = row.get("attempt")
        if attempt is None:
            attempt = 0
        self.assertEqual(int(attempt), 0, row)

    def test_resume_after_cited_rows_dispatches_fix_stages_with_answers(self):
        first = self.run_undisposed()
        self.assert_stopped(
            first, stage="fix-tests", record="none", reason="undisposed",
        )
        key = self.adversarial_key()
        self.patch_plant(dispositions={key: CITATION})
        landed = (self.load_plant().get("dispositions") or {}).get(key)
        self.assertEqual(landed, CITATION, landed)
        probe = self.cited_probe(key)
        self.assertEqual(
            probe.returncode, 0,
            f"plant: cited must hold after the disposition: "
            f"{probe.stdout!r} {probe.stderr!r}",
        )
        self.assertIn(CITATION, probe.stdout)
        ladder_id = self.ladder_record().get("id")
        self.assertTrue(ladder_id)
        second = self.invoke(["resume", ladder_id])
        self.assertEqual(second.returncode, 0, self.combined(second))
        names = self.dispatch_names()
        self.assertIn("fix-tests", names, names)
        self.assertIn("fix-code", names, names)
        self.assert_fix_argv("fix-tests", [key])
        self.assert_fix_argv("fix-code", [key])
        self.assertNotIn("disposition", self.findings_verbs())

    def assert_fix_argv(self, name: str, keys: list[str]) -> None:
        self.assertTrue(keys, "plant: expected finding keys")
        argv = self.dispatch_argv_for(name)
        follows = self.flag_values(argv, "--follows")
        self.assertEqual(
            len(follows), 3,
            f"item 9: {name} dispatch with --follows previous, security, "
            f"adversarial; found {follows!r} in {argv!r}",
        )
        security_id = self.record_id_for("security")
        adversarial_id = self.record_id_for("adversarial")
        self.assertEqual(follows[1], security_id, argv)
        self.assertEqual(follows[2], adversarial_id, argv)
        self.assertRegex(follows[0], RECORD_ID, follows[0])
        self.assertIn(follows[0], self.load_plant().get("records") or {}, argv)
        answers = self.flag_values(argv, "--answers")
        self.assertEqual(
            len(answers), len(keys),
            f"item 9: {name} one --answers KEY per key; "
            f"found {answers!r} in {argv!r}",
        )
        self.assertEqual(sorted(answers), sorted(keys), argv)
        for key in answers:
            self.assertRegex(key, ANSWER_KEY, key)


class CitedRowsDispatchFixStages(_UndisposedFixture):
    """Item 9 — when every key already holds, the fix stages launch
    as corrections: three --follows and one --answers per key."""

    def test_fix_tests_carries_three_follows(self):
        proc = self.run_undisposed(cited_all=True)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_finding_landed()
        self.assertIn("fix-tests", self.dispatch_names())
        argv = self.dispatch_argv_for("fix-tests")
        follows = self.flag_values(argv, "--follows")
        self.assertEqual(
            len(follows), 3,
            f"item 9: --follows previous, security, adversarial; "
            f"found {follows!r} in {argv!r}",
        )
        self.assertEqual(follows[1], self.record_id_for("security"), argv)
        self.assertEqual(follows[2], self.record_id_for("adversarial"), argv)

    def test_fix_code_carries_three_follows(self):
        proc = self.run_undisposed(cited_all=True)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertIn("fix-code", self.dispatch_names())
        argv = self.dispatch_argv_for("fix-code")
        follows = self.flag_values(argv, "--follows")
        self.assertEqual(
            len(follows), 3,
            f"item 9: --follows previous, security, adversarial; "
            f"found {follows!r} in {argv!r}",
        )
        self.assertEqual(follows[1], self.record_id_for("security"), argv)
        self.assertEqual(follows[2], self.record_id_for("adversarial"), argv)

    def test_fix_tests_carries_one_answers_per_key(self):
        proc = self.run_undisposed(cited_all=True)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        key = self.adversarial_key()
        argv = self.dispatch_argv_for("fix-tests")
        answers = self.flag_values(argv, "--answers")
        self.assertEqual(
            len(answers), 1,
            f"item 9: one --answers KEY per key; found {answers!r} "
            f"in {argv!r}",
        )
        self.assertEqual(answers[0], key, argv)

    def test_fix_code_carries_one_answers_per_key(self):
        proc = self.run_undisposed(cited_all=True)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        key = self.adversarial_key()
        argv = self.dispatch_argv_for("fix-code")
        answers = self.flag_values(argv, "--answers")
        self.assertEqual(
            len(answers), 1,
            f"item 9: one --answers KEY per key; found {answers!r} "
            f"in {argv!r}",
        )
        self.assertEqual(answers[0], key, argv)

    def test_driver_cites_the_key_before_the_fix_dispatch(self):
        proc = self.run_undisposed(cited_all=True)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        key = self.adversarial_key()
        asked = self.cited_keys()
        self.assertTrue(asked, self.findings_argvs())
        self.assertIn(key, asked, asked)
        names = self.dispatch_names()
        self.assertLess(
            names.index("adversarial"),
            names.index("fix-tests"),
            names,
        )
        self.assertNotIn("disposition", self.findings_verbs())


if __name__ == "__main__":
    unittest.main()
