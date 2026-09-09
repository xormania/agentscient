"""Finding-admission ladder routing: consume the corrections projection.

Written from FINDING-ADMISSION.md §Ledger and correction interface and
ops/conductor/ladder-lever.md. ladder.py is not read. Dispatch and land
stay mocked; the selector under test is the driver. findings.py is
replaced with a corrections-aware stub after the inherited fixture seeds.

Intended reds: the driver still routes tests-fix from a raw changes
verdict, never calls `corrections`, and does not stop on an admission
refusal. A missing tool file is not these cases' red.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import unittest
from pathlib import Path

from test_ladder_lever import _LadderFixture

ADMITTED_KEY = "20260904T120000Z-review-codex-aa0132#1"
ADMITTED_FAIL = "ADMITTED_FAILURE_aa32 closure undeclared read"
HELD_KEY = "20260904T120000Z-review-codex-aa0132#2"
HELD_CLAIM = "HELD_UNPROVEN_aa32 agy help was not measured"
HELD_REASON = "unproven"

CORRECTIONS_STUB = r'''
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
if argv and argv[0] == "corrections":
    mode = plant.get("admission") or "empty"
    if mode == "refuse":
        sys.stderr.write(
            "admission-incomplete: expected a complete evaluated review; "
            "found status=invalid; needed finish the review before correction\n"
        )
        raise SystemExit(2)
    ref = "missing-ref"
    scope = "missing-scope"
    if "--ref" in argv:
        ref = argv[argv.index("--ref") + 1]
    if "--scope-sha256" in argv:
        scope = argv[argv.index("--scope-sha256") + 1]
    admitted = []
    held = []
    if mode == "mixed":
        admitted = [{
            "key": "@@ADMITTED_KEY@@",
            "evaluation_record": "planted-eval",
            "evaluation_n": 1,
            "evaluation": {
                "classification": "demonstrated-defect",
                "failure": "@@ADMITTED_FAIL@@",
                "requirement": "closure() refuses undeclared reads",
            },
        }]
        held = [{"key": "@@HELD_KEY@@", "reason": "@@HELD_REASON@@"}]
    else:
        held = [{"key": "@@HELD_KEY@@", "reason": "@@HELD_REASON@@"}]
    sys.stdout.write(json.dumps({
        "ref": ref,
        "scope_sha256": scope,
        "admitted": admitted,
        "held": held,
    }) + "\n")
    raise SystemExit(0)
if argv and argv[0] == "export":
    sys.stdout.write("{}\n")
raise SystemExit(0)
'''.lstrip()


class AdmissionRouting(_LadderFixture):
    def _install_corrections_stub(self, mode: str) -> None:
        plant = self.load_plant()
        plant["admission"] = mode
        text = json.dumps(plant, indent=2) + "\n"
        self._plant_bytes(self.stub_dir / "plant.json", text.encode("utf-8"))
        body = (
            CORRECTIONS_STUB
            .replace("@@STUB@@", str(self.stub_dir))
            .replace("@@ADMITTED_KEY@@", ADMITTED_KEY)
            .replace("@@ADMITTED_FAIL@@", ADMITTED_FAIL)
            .replace("@@HELD_KEY@@", HELD_KEY)
            .replace("@@HELD_REASON@@", HELD_REASON)
        )
        dest = self.repo / "ops" / "conductor" / "tools" / "findings.py"
        payload = "#!/usr/bin/env python3\n" + body
        self._plant_bytes(dest, payload.encode("utf-8"))
        mode_bits = dest.stat().st_mode
        dest.chmod(mode_bits | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.assertTrue(os.access(dest, os.X_OK), dest)
        self.assertIn("corrections", dest.read_text(encoding="utf-8"))
        rel = "ops/conductor/tools/findings.py"
        self.git("add", rel)
        self.git("commit", "-m", "plant corrections stub\n")
        self.assertEqual(self.porcelain(), "")
        self.assertIn("corrections", dest.read_text(encoding="utf-8"))

    def _corrections_argvs(self) -> list[list[str]]:
        return [
            row for row in self.findings_argvs()
            if row and row[0] == "corrections"
        ]

    def test_legacy_changes_invokes_corrections_before_tests_fix(self):
        self.patch_plant(verdicts={"check-tests": "changes"})
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        calls = self._corrections_argvs()
        self.assertGreaterEqual(
            len(calls),
            1,
            f"driver never called corrections: {self.findings_argvs()!r}",
        )
        argv = calls[0]
        self.assertIn("--ref", argv)
        ref = argv[argv.index("--ref") + 1]
        self.assertRegex(ref, r"^[0-9a-f]{40}$", argv)
        self.assertIn("--scope-sha256", argv)
        digest = argv[argv.index("--scope-sha256") + 1]
        expected = hashlib.sha256(
            self.scope_path.read_bytes()
        ).hexdigest()
        self.assertEqual(digest, expected, argv)
        self.assertIn("check-tests", self.dispatch_names())

    def test_empty_admitted_skips_tests_fix_despite_changes(self):
        self._install_corrections_stub("empty")
        self.patch_plant(verdicts={"check-tests": "changes"})
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        names = self.dispatch_names()
        self.assertNotIn("tests-fix", names)
        self.assertIn("check-tests", names)
        self.assertIn("code", names)
        record = self.ladder_record()
        row = self.stage_row(record, "tests-fix")
        self.assertEqual(row.get("outcome"), "skipped", row)
        condition = str(row.get("condition") or row.get("skipped") or "")
        self.assertTrue(condition.strip(), row)

    def test_admitted_defect_selects_tests_fix_with_only_admitted_demand(self):
        self._install_corrections_stub("mixed")
        self.patch_plant(verdicts={"check-tests": "changes"})
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        names = self.dispatch_names()
        self.assertIn("tests-fix", names)
        text = self.inputs_text(self.dispatch_argv_for("tests-fix"))
        self.assertIn(ADMITTED_FAIL, text)
        self.assertIn(ADMITTED_KEY, text)
        self.assertNotIn(HELD_CLAIM, text)
        self.assertNotIn("SKEPTIC_MD_BODY_aa32", text)

    def test_refused_corrections_read_stops_as_admission_not_retry(self):
        self._install_corrections_stub("refuse")
        self.patch_plant(verdicts={"check-tests": "changes"})
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 3, self.combined(proc))
        text = self.combined(proc).replace("_", "-")
        self.assertTrue(
            "reason=admission" in text or "admission-incomplete" in text,
            text,
        )
        self.assertNotIn("tests-fix", self.dispatch_names())
        self.assertEqual(self.dispatch_names().count("check-tests"), 1)


if __name__ == "__main__":
    unittest.main()
