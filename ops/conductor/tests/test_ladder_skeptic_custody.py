"""Driver-written custody file for tests-fix, item 4.

Written from contract items 4 and 7 of
`.dev/ladder-inputs/scope-item31-20260911.md`. The tool is the subject
and is not read here. Tests reuse _LadderFixture.

Item 4: tests-fix receives a regular file the driver wrote under the
ladder inputs directory from the validated envelope, recorded with
path and digest; a symlink or a path outside is class custody.
Item 7: the refusal is one stderr line, exit 2, stdout empty.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from test_ladder_lever import (  # noqa: E402
    SKEPTIC_BODY,
    SKEPTIC_FINDINGS,
    WELL_FORMED_SKEPTIC_COUNTS,
    WELL_FORMED_SKEPTIC_FINDING,
    _LadderFixture,
)

SENTINEL = "CUSTODY_TARGET_UNTOUCHED_aa32\n"


def _finding():
    return dict(WELL_FORMED_SKEPTIC_FINDING)


class _CustodyFixture(_LadderFixture):
    """Valid check-tests envelope, optional SKEPTIC.md trap on disk."""

    def plant_valid_changes(self, **extra):
        envelope = {
            "verdict": "changes",
            "findings": [_finding()],
            "counts": dict(WELL_FORMED_SKEPTIC_COUNTS),
            "artifacts": {},
        }
        self.patch_plant(
            verdicts={"check-tests": "changes"},
            skeptic_md=True,
            skeptic_text=SKEPTIC_BODY,
            skeptic_envelope=envelope,
            **extra,
        )
        planted = self.load_plant()
        self.assertTrue(planted["skeptic_md"])
        self.assertEqual(planted["skeptic_envelope"]["artifacts"], {})

    def input_paths_for_tests_fix(self) -> list[Path]:
        argv = self.dispatch_argv_for("tests-fix")
        paths = []
        for raw in self.flag_values(argv, "--input"):
            path = Path(raw)
            if not path.is_absolute():
                path = self.repo / path
            paths.append(path)
        return paths

    def assert_custody_refusal(self, proc) -> str:
        line = self.assert_refusal(proc, "custody")
        self.assertNotIn("tests-fix", self.dispatch_names())
        record = self.ladder_record()
        stopped = record.get("stopped") or {}
        reasons = [stopped.get("reason")]
        for row in record.get("stages") or []:
            reasons.append(row.get("reason"))
        self.assertIn("custody", reasons, record)
        return line


class TestsFixReceivesTheCustodyFile(_CustodyFixture):
    """Item 4 — path, digest, regular file, header, body, commit."""

    def test_tests_fix_argv_names_skeptic_findings_md_not_skeptic_md(self):
        self.plant_valid_changes()
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        trap = self.repo / "SKEPTIC.md"
        self.assertTrue(trap.is_file(), "plant: SKEPTIC.md must exist on disk")
        self.assertEqual(trap.read_text(encoding="utf-8"), SKEPTIC_BODY)
        paths = self.input_paths_for_tests_fix()
        names = [path.name for path in paths]
        self.assertIn(SKEPTIC_FINDINGS, names, paths)
        self.assertNotIn("SKEPTIC.md", names, paths)
        wanted = self.skeptic_findings_path().resolve()
        self.assertTrue(
            any(path.resolve() == wanted for path in paths),
            paths,
        )

    def test_the_custody_file_is_a_regular_file_with_the_envelope(self):
        self.plant_valid_changes()
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        path = self.skeptic_findings_path()
        self.assertTrue(path.is_file(), path)
        self.assertFalse(path.is_symlink(), path)
        self.assertTrue(stat.S_ISREG(path.lstat().st_mode), path)
        rec_id = self.record_id_for("check-tests")
        text = path.read_text(encoding="utf-8")
        first, sep, rest = text.partition("\n")
        self.assertTrue(sep, text)
        self.assertIn("check-tests envelope", first)
        self.assertIn(rec_id, first)
        body = json.loads(rest)
        self.assertEqual(body.get("artifacts"), {})
        self.assertEqual(body.get("verdict"), "changes")
        self.assertEqual(body.get("findings"), [_finding()])
        dispatch = Path(self.load_plant()["records"][rec_id]["path"])
        envelope = json.loads(dispatch.read_text(encoding="utf-8"))["result"][
            "envelope"
        ]
        self.assertEqual(body["findings"], envelope["findings"])
        self.assertEqual(body["counts"], envelope["counts"])

    def test_the_tests_fix_row_records_path_and_digest(self):
        self.plant_valid_changes()
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        path = self.skeptic_findings_path()
        self.assertTrue(path.is_file(), path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        row = self.stage_row(self.ladder_record(), "tests-fix")
        inp = row.get("input") or {}
        self.assertIsInstance(inp, dict, row)
        self.assertEqual(inp.get("sha256"), digest, row)
        recorded = Path(str(inp.get("path") or ""))
        if not recorded.is_absolute():
            recorded = self.repo / recorded
        self.assertEqual(recorded.resolve(), path.resolve(), row)

    def test_the_custody_file_is_in_the_record_commit(self):
        self.plant_valid_changes()
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        path = self.skeptic_findings_path()
        self.assertTrue(path.is_file(), path)
        rel = str(path.relative_to(self.repo))
        listed = self.git("ls-files", "--", rel).stdout.strip()
        self.assertEqual(listed, rel, listed)
        self.assertTrue(
            self.ladder_record_commits(),
            "item 4: the driver commits the custody file with the record",
        )


class CustodyRefusesASymlink(_CustodyFixture):
    """Item 4 / item 7 — symlink target and inputs dir are not followed."""

    def _stop_after_tests(self) -> str:
        self.plant_valid_changes(trip_stages=["tests"])
        first = self.run_ladder()
        rec_id = self.record_id_for("tests")
        self.assert_stopped(
            first, stage="tests", record=rec_id, reason="tripped",
        )
        self.close_tripped_record()
        return self.ladder_id()

    def test_a_planted_symlink_at_the_custody_name_is_refused(self):
        ladder_id = self._stop_after_tests()
        inputs_dir = self.ladder_inputs_dir(ladder_id)
        inputs_dir.mkdir(parents=True, exist_ok=True)
        target = self.root / "outside-skeptic-aa32.md"
        target.write_text(SENTINEL, encoding="utf-8")
        self.assertEqual(target.read_text(encoding="utf-8"), SENTINEL)
        link = inputs_dir / SKEPTIC_FINDINGS
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(target)
        self.assertTrue(link.is_symlink(), link)
        self.assertEqual(os.readlink(link), str(target))
        self.git("add", "-A", "--", ".dev")
        self.git("commit", "-m", "plant custody symlink trap\n")
        self.assertEqual(self.porcelain(), "")
        self.patch_plant(trip_stages=[])
        second = self.invoke(["resume", ladder_id])
        line = self.assert_custody_refusal(second)
        self.assertIn("symlink", line.lower())
        self.assertTrue(link.is_symlink(), "item 4: the symlink stays in place")
        self.assertEqual(
            target.read_text(encoding="utf-8"),
            SENTINEL,
            "item 4: the symlink target is not written",
        )

    def test_a_planted_symlinked_inputs_directory_is_refused(self):
        ladder_id = self._stop_after_tests()
        inputs_dir = self.ladder_inputs_dir(ladder_id)
        outside = self.root / "outside-inputs-aa32"
        if inputs_dir.exists() or inputs_dir.is_symlink():
            if inputs_dir.is_symlink():
                inputs_dir.unlink()
            else:
                shutil.move(str(inputs_dir), str(outside))
        if not outside.exists():
            outside.mkdir()
        marker = outside / "sentinel-aa32"
        if not marker.is_file():
            marker.write_text(SENTINEL, encoding="utf-8")
        self.assertEqual(marker.read_text(encoding="utf-8"), SENTINEL)
        if inputs_dir.exists() or inputs_dir.is_symlink():
            if inputs_dir.is_dir() and not inputs_dir.is_symlink():
                shutil.rmtree(inputs_dir)
            else:
                inputs_dir.unlink()
        inputs_dir.symlink_to(outside)
        self.assertTrue(inputs_dir.is_symlink(), inputs_dir)
        self.git("add", "-A", "--", ".dev")
        self.git("commit", "-m", "plant custody inputs-dir symlink trap\n")
        self.assertEqual(self.porcelain(), "")
        self.assertEqual(os.readlink(inputs_dir), str(outside))
        self.patch_plant(trip_stages=[])
        second = self.invoke(["resume", ladder_id])
        line = self.assert_custody_refusal(second)
        self.assertIn("symlink", line.lower())
        self.assertTrue(
            inputs_dir.is_symlink(),
            "item 4: the inputs directory stays a symlink",
        )
        written = outside / SKEPTIC_FINDINGS
        self.assertFalse(
            written.exists(),
            "item 4: the driver does not write through the symlink; "
            f"found {written}",
        )
        self.assertEqual(marker.read_text(encoding="utf-8"), SENTINEL)


if __name__ == "__main__":
    unittest.main()
