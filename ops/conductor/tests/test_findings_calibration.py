"""Findings-ledger `calibrate` tests, written from the slice-1 contract.

`ops/conductor/tools/findings.py` is the subject and is not read here.
Tests invoke it as a subprocess with HOME pointed at a temp dir.

The live store (`~/.local/state/agentscient/findings.db` at import-time
HOME) must stay untouched — asserted in tearDown.

`calibrate` is a new writing verb: it upserts grader rows, is
idempotent, refuses `identity` and `calibration`, leaves `export`
byte-identical, and makes `export --calibration` deterministic. Today
the verb is unknown (class `arguments`); the exit-0 assertion is the
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
        self.scratch = root / "scratch"
        self.home.mkdir()
        self.scratch.mkdir()
        self.store = self.home / ".local" / "state" / "agentscient" / "findings.db"
        self.assertFalse(self.store.exists(), "isolated store must start absent")
        self.staged = self.scratch / "findings.py"
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
            cwd=str(self.scratch),
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )

    def assert_refusal(self, proc, class_name: str) -> None:
        err = proc.stderr or ""
        compact = err.lower().replace("_", "-")
        token = class_name.lower().replace("_", "-")
        self.assertIn(token, compact, err)
        self.assertEqual(proc.returncode, 2, err)
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        lower = err.lower()
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, err)
        self.assertLess(lower.index("expected"), lower.index("found"), err)
        self.assertLess(lower.index("found"), lower.index("needed"), err)
        self.assertEqual((proc.stdout or "").strip(), "")

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

    def export_calibration(self):
        return self.invoke(["export", "--calibration"], agent=None)


class CalibrateWrites(_CalibrateFixture):
    def test_calibrate_upserts_a_row_under_temp_home(self):
        proc = self.calibrate([ROW])
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        exported = self.export_calibration()
        self.assertEqual(exported.returncode, 0, exported.stderr)
        rows = self.parse_jsonl(exported.stdout)
        self.assertEqual(len(rows), 1, exported.stdout)
        self.assertEqual(rows[0]["record"], ROW["record"])
        self.assertEqual(rows[0]["app"], ROW["app"])
        self.assertEqual(rows[0]["fault_id"], ROW["fault_id"])
        self.assertEqual(rows[0]["finding_key"], ROW["finding_key"])
        self.assertEqual(rows[0]["class"], "caught")
        self.assertEqual(rows[0]["claim"], ROW["claim"])

    def test_calibrate_is_idempotent_on_the_same_row(self):
        first = self.calibrate([ROW])
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.calibrate([ROW])
        self.assertEqual(second.returncode, 0, second.stderr)
        exported = self.export_calibration()
        self.assertEqual(exported.returncode, 0, exported.stderr)
        rows = self.parse_jsonl(exported.stdout)
        self.assertEqual(len(rows), 1, exported.stdout)

    def test_calibrate_upserts_by_record_app_fault_and_finding_key(self):
        first = self.calibrate([ROW])
        self.assertEqual(first.returncode, 0, first.stderr)
        updated = dict(ROW)
        updated["class"] = "missed"
        updated["claim"] = "UPDATED_CLAIM_SYN"
        second = self.calibrate([updated])
        self.assertEqual(second.returncode, 0, second.stderr)
        exported = self.export_calibration()
        rows = self.parse_jsonl(exported.stdout)
        self.assertEqual(len(rows), 1, exported.stdout)
        self.assertEqual(rows[0]["class"], "missed")
        self.assertEqual(rows[0]["claim"], "UPDATED_CLAIM_SYN")

    def test_calibrate_accepts_null_fault_id_and_finding_key(self):
        row = dict(ROW)
        row["fault_id"] = None
        row["finding_key"] = None
        row["class"] = "unmatched"
        proc = self.calibrate([row])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        exported = self.export_calibration()
        rows = self.parse_jsonl(exported.stdout)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["fault_id"])
        self.assertIsNone(rows[0]["finding_key"])


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

    def test_calibrate_refuses_calibration_on_a_missing_key(self):
        row = dict(ROW)
        del row["app"]
        proc = self.calibrate([row])
        self.assert_refusal(proc, "calibration")

    def test_calibrate_refuses_calibration_on_an_unknown_class(self):
        row = dict(ROW)
        row["class"] = "not-a-class"
        proc = self.calibrate([row])
        self.assert_refusal(proc, "calibration")


class ExportStaysPut(_CalibrateFixture):
    def test_findings_export_is_byte_identical_after_calibrate(self):
        before = self.export_findings()
        self.assertEqual(before.returncode, 0, before.stderr)
        proc = self.calibrate([ROW])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        after = self.export_findings()
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertEqual(after.stdout, before.stdout)

    def test_export_calibration_is_deterministic(self):
        other = dict(ROW)
        other["fault_id"] = "SYN-02"
        other["finding_key"] = None
        other["class"] = "missed"
        proc = self.calibrate([ROW, other])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        first = self.export_calibration()
        second = self.export_calibration()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertTrue(first.stdout.strip(), "calibration export is empty")
        rows = self.parse_jsonl(first.stdout)
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
