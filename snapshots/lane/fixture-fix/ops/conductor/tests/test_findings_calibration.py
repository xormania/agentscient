"""Findings-ledger `calibrate` tests, written from the slice-1 contract.

`ops/conductor/tools/findings.py` is the subject and is not read here.
Tests invoke it as a subprocess with HOME pointed at a temp dir.

The live store (`~/.local/state/agentscient/findings.db` at import-time
HOME) must stay untouched — asserted in tearDown.

`calibrate` is a new writing verb: it upserts grader rows keyed on
record, app, fault id and finding key, is idempotent, refuses
`identity` and `calibration` before acting, leaves `export`
byte-identical to today's empty findings export, writes
`ops/conductor/findings/calibration.jsonl` via `export --calibration`,
and makes that export deterministic across insertion order. Today the
verb is unknown (class `arguments`); the exit-0 assertion is the
intended red.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "findings.py"

_IMPORT_XDG = os.environ.get("XDG_STATE_HOME")
LIVE_STORES = []
if _IMPORT_XDG:
    LIVE_STORES.append(Path(_IMPORT_XDG) / "agentscient" / "findings.db")
LIVE_STORES.append(Path.home() / ".local" / "state" / "agentscient" / "findings.db")

AGENT = "Calibration Tester <calibration-tester@example.invalid>"
MALFORMED_AGENT = "JustAName"
RUN_CAP = 30

ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)

ROW = {
    "record": "20260904T000000Z-review-grok-synth01",
    "app": "synth",
    "fault_id": "SYN-01",
    "finding_key": "20260904T000000Z-review-grok-synth01#1",
    "class": "caught",
    "harness": "grok",
    "model": "grok-4.6",
    "claim": "CAUGHT_CLAIM_SYN",
}

PRESENT_KEYS = ("record", "app", "class", "harness", "model", "claim")


def _live_snapshot() -> list[tuple[str, str, bytes | None]]:
    snaps = []
    for path in LIVE_STORES:
        if path.is_file():
            snaps.append((str(path), "file", path.read_bytes()))
        elif path.exists():
            snaps.append((str(path), "other", None))
        else:
            snaps.append((str(path), "absent", None))
    return snaps


class _CalibrateFixture(unittest.TestCase):
    def setUp(self):
        self.assertTrue(TOOL.is_file(), f"{TOOL} is missing")
        self._live_before = _live_snapshot()
        self._tmp = tempfile.TemporaryDirectory(prefix="findings-calibrate-")
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.repo = root / "repo"
        self.home.mkdir()
        self.repo.mkdir()
        self.store = self.home / ".local" / "state" / "agentscient" / "findings.db"
        self.assertFalse(self.store.exists(), "isolated store must start absent")
        self.staged = self.repo / "ops" / "conductor" / "tools" / "findings.py"
        self.calibration_jsonl = (
            self.repo / "ops" / "conductor" / "findings" / "calibration.jsonl"
        )
        self.calibration_jsonl.parent.mkdir(parents=True, exist_ok=True)
        self._stage_tool_bytes()

    def tearDown(self):
        try:
            self.assertEqual(
                _live_snapshot(),
                self._live_before,
                "live findings store mutated",
            )
        finally:
            self._tmp.cleanup()

    def _stage_tool_bytes(self) -> None:
        self.staged.parent.mkdir(parents=True, exist_ok=True)
        data = TOOL.read_bytes()
        self.staged.write_bytes(data)
        landed = self.staged.read_bytes()
        self.assertEqual(landed, data, "copy-tool-bytes did not land intact")
        self.assertEqual(len(landed), len(data))
        self.assertNotEqual(landed, ABSENT_STUB)

    def env(self, *, agent: str | None = AGENT) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if agent is not None:
            env["WF_AGENT"] = agent
        return env

    def invoke(
        self,
        argv: list[str],
        *,
        agent: str | None = AGENT,
        stdin: str = "",
    ):
        env = self.env(agent=agent)
        if agent is None:
            self.assertNotIn("WF_AGENT", env)
        return subprocess.run(
            [sys.executable, str(self.staged), *argv],
            cwd=str(self.repo),
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )

    def assert_refusal(self, proc, class_name: str) -> None:
        err = proc.stderr or ""
        self.assertEqual(proc.returncode, 2, err)
        self.assertEqual((proc.stdout or "").strip(), "")
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        line = lines[0]
        token = class_name.lower().replace("_", "-")
        head = line.split(":", 1)[0].strip().lower().replace("_", "-")
        self.assertEqual(
            head,
            token,
            f"refusal class must be the leading token {token!r}: {line!r}",
        )
        lower = line.lower()
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, err)
        self.assertLess(lower.index("expected"), lower.index("found"), err)
        self.assertLess(lower.index("found"), lower.index("needed"), err)

    def jsonl(self, rows: list[dict]) -> str:
        return "".join(json.dumps(row) + "\n" for row in rows)

    def parse_jsonl(self, text: str) -> list[dict]:
        rows = []
        for line in text.splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def calibrate(self, rows: list[dict], **kwargs):
        return self.invoke(["calibrate"], stdin=self.jsonl(rows), **kwargs)

    def export_findings(self):
        return self.invoke(["export"], agent=None)

    def export_calibration(self, *, agent: str | None = AGENT):
        return self.invoke(["export", "--calibration"], agent=agent)

    def exported_rows(self) -> list[dict]:
        exported = self.export_calibration()
        self.assertEqual(exported.returncode, 0, exported.stderr)
        return self.parse_jsonl(exported.stdout)


class RefusalShape(_CalibrateFixture):
    def test_embedded_class_token_is_not_a_refusal(self):
        proc = subprocess.CompletedProcess(
            args=["findings.py"],
            returncode=2,
            stdout="",
            stderr="not-identity garbage expected x; found y; needed z\n",
        )
        with self.assertRaises(AssertionError):
            self.assert_refusal(proc, "identity")


class CalibrateWrites(_CalibrateFixture):
    def test_calibrate_upserts_a_row_under_temp_home(self):
        proc = self.calibrate([ROW])
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        rows = self.exported_rows()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["record"], ROW["record"])
        self.assertEqual(rows[0]["app"], ROW["app"])
        self.assertEqual(rows[0]["fault_id"], ROW["fault_id"])
        self.assertEqual(rows[0]["finding_key"], ROW["finding_key"])
        self.assertEqual(rows[0]["class"], "caught")
        self.assertEqual(rows[0]["claim"], ROW["claim"])
        self.assertEqual(rows[0]["harness"], ROW["harness"])
        self.assertEqual(rows[0]["model"], ROW["model"])

    def test_calibrate_is_idempotent_on_the_same_row(self):
        first = self.calibrate([ROW])
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.calibrate([ROW])
        self.assertEqual(second.returncode, 0, second.stderr)
        rows = self.exported_rows()
        self.assertEqual(len(rows), 1, rows)

    def test_calibrate_upserts_non_key_fields_on_the_same_key(self):
        first = self.calibrate([ROW])
        self.assertEqual(first.returncode, 0, first.stderr)
        updated = dict(ROW)
        updated["class"] = "missed"
        updated["claim"] = "UPDATED_CLAIM_SYN"
        updated["harness"] = "codex"
        updated["model"] = "gpt-5.6"
        second = self.calibrate([updated])
        self.assertEqual(second.returncode, 0, second.stderr)
        rows = self.exported_rows()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["class"], "missed")
        self.assertEqual(rows[0]["claim"], "UPDATED_CLAIM_SYN")
        self.assertEqual(rows[0]["harness"], "codex")
        self.assertEqual(rows[0]["model"], "gpt-5.6")

    def test_calibrate_discriminates_each_part_of_the_composite_key(self):
        variants = [
            ROW,
            {**ROW, "record": "other-record"},
            {**ROW, "app": "other-app"},
            {**ROW, "fault_id": "SYN-02"},
            {**ROW, "finding_key": f"{ROW['record']}#2"},
        ]
        proc = self.calibrate(variants)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = self.exported_rows()
        self.assertEqual(len(rows), 5, rows)
        keys = {
            (row["record"], row["app"], row["fault_id"], row["finding_key"])
            for row in rows
        }
        self.assertEqual(len(keys), 5, keys)
        updated = dict(ROW)
        updated["claim"] = "ONLY_DEFAULT_KEY_UPDATED"
        second = self.calibrate([updated])
        self.assertEqual(second.returncode, 0, second.stderr)
        after = self.exported_rows()
        self.assertEqual(len(after), 5, after)
        matched = [
            row
            for row in after
            if (row["record"], row["app"], row["fault_id"], row["finding_key"])
            == (ROW["record"], ROW["app"], ROW["fault_id"], ROW["finding_key"])
        ]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["claim"], "ONLY_DEFAULT_KEY_UPDATED")
        others = [
            row
            for row in after
            if (row["record"], row["app"], row["fault_id"], row["finding_key"])
            != (ROW["record"], ROW["app"], ROW["fault_id"], ROW["finding_key"])
        ]
        self.assertEqual(len(others), 4)
        self.assertEqual({row["claim"] for row in others}, {ROW["claim"]})

    def test_calibrate_null_keys_are_distinct_rows(self):
        first = dict(ROW)
        first["fault_id"] = None
        first["finding_key"] = None
        first["class"] = "unmatched"
        first["claim"] = "NULL_A"
        second = dict(first)
        second["record"] = "other-record"
        second["claim"] = "NULL_B"
        third = dict(ROW)
        third["fault_id"] = None
        third["finding_key"] = f"{ROW['record']}#9"
        third["class"] = "unlocated"
        third["claim"] = "NULL_FAULT"
        fourth = dict(ROW)
        fourth["fault_id"] = "SYN-09"
        fourth["finding_key"] = None
        fourth["class"] = "missed"
        fourth["claim"] = "NULL_FINDING"
        proc = self.calibrate([first, second, third, fourth])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = self.exported_rows()
        self.assertEqual(len(rows), 4, rows)
        keys = {
            (row["record"], row["app"], row["fault_id"], row["finding_key"])
            for row in rows
        }
        self.assertEqual(len(keys), 4, keys)
        again = self.calibrate([first])
        self.assertEqual(again.returncode, 0, again.stderr)
        after = self.exported_rows()
        self.assertEqual(len(after), 4, after)


class CalibrateRefuses(_CalibrateFixture):
    def test_calibrate_refuses_identity_without_wf_agent(self):
        proc = self.calibrate([ROW], agent=None)
        self.assert_refusal(proc, "identity")

    def test_calibrate_refuses_identity_on_a_malformed_agent(self):
        proc = self.calibrate([ROW], agent=MALFORMED_AGENT)
        self.assert_refusal(proc, "identity")

    def test_calibrate_refuses_calibration_on_empty_stdin(self):
        proc = self.invoke(["calibrate"], stdin="")
        self.assert_refusal(proc, "calibration")

    def test_calibrate_refuses_calibration_on_non_json(self):
        proc = self.invoke(["calibrate"], stdin="not-json\n")
        self.assert_refusal(proc, "calibration")

    def test_calibrate_refuses_calibration_on_each_missing_key(self):
        for key in PRESENT_KEYS:
            with self.subTest(missing=key):
                row = dict(ROW)
                del row[key]
                proc = self.calibrate([row])
                self.assert_refusal(proc, "calibration")
                self.assertFalse(self.store.exists())

    def test_calibrate_refuses_calibration_on_an_unknown_class(self):
        row = dict(ROW)
        row["class"] = "not-a-class"
        proc = self.calibrate([row])
        self.assert_refusal(proc, "calibration")

    def test_calibrate_refuses_before_acting_on_mixed_valid_and_invalid(self):
        bad = dict(ROW)
        del bad["app"]
        proc = self.calibrate([ROW, bad])
        self.assert_refusal(proc, "calibration")
        self.assertFalse(self.store.exists())
        exported = self.export_calibration()
        if exported.returncode == 0:
            self.assertEqual(exported.stdout.strip(), "")
        self.assertFalse(self.calibration_jsonl.exists())


class ExportStaysPut(_CalibrateFixture):
    def test_findings_export_is_byte_identical_to_today_after_calibrate(self):
        before = self.export_findings()
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(
            before.stdout,
            "",
            "empty-store findings export is empty today",
        )
        proc = self.calibrate([ROW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        after = self.export_findings()
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertEqual(after.stdout, before.stdout)
        self.assertEqual(after.stdout, "")

    def test_export_calibration_refuses_identity_without_wf_agent(self):
        proc = self.calibrate([ROW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if self.calibration_jsonl.exists():
            self.calibration_jsonl.unlink()
        exported = self.export_calibration(agent=None)
        self.assert_refusal(exported, "identity")
        self.assertFalse(
            self.calibration_jsonl.exists(),
            "export --calibration must not write the tracked jsonl without identity",
        )

    def test_export_calibration_refuses_identity_on_a_malformed_agent(self):
        proc = self.calibrate([ROW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        exported = self.export_calibration(agent=MALFORMED_AGENT)
        self.assert_refusal(exported, "identity")

    def test_export_calibration_writes_tracked_jsonl_deterministically(self):
        other = dict(ROW)
        other["fault_id"] = "SYN-02"
        other["finding_key"] = None
        other["class"] = "missed"
        other["claim"] = "MISSED_CLAIM_SYN"
        proc = self.calibrate([ROW, other])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        first = self.export_calibration()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(first.stdout.strip(), "calibration export is empty")
        self.assertTrue(
            self.calibration_jsonl.is_file(),
            "export --calibration writes ops/conductor/findings/calibration.jsonl",
        )
        self.assertEqual(
            self.calibration_jsonl.read_text(encoding="utf-8"),
            first.stdout,
        )
        second = self.export_calibration()
        self.assertEqual(second.stdout, first.stdout)
        if self.store.is_file():
            self.store.unlink()
        self.calibration_jsonl.unlink()
        reversed_rows = self.calibrate([other, ROW])
        self.assertEqual(reversed_rows.returncode, 0, reversed_rows.stderr)
        third = self.export_calibration()
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertEqual(third.stdout, first.stdout)
        self.assertEqual(
            self.calibration_jsonl.read_text(encoding="utf-8"),
            first.stdout,
        )


if __name__ == "__main__":
    unittest.main()
