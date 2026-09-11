"""Citation grammar, citation_holds, and the cited verb.

Written from scope-gate-20260910.md items 1, 4 and 9 (the ledger half)
and rulings R1, R3, R4. findings.py is the subject and is not read
here: tests load parse_citation / citation_holds as callables when
present, and invoke the staged tool as a subprocess.

A missing callable is treated as "this evidence does not parse / does
not hold", so a positive assertion is red today for the right reason
rather than an import error. Each negative case also requires the
positive neighbour so a missing callable cannot make the rejection
look green.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "findings.py"
LIVE_STORE = Path.home() / ".local" / "state" / "agentscient" / "findings.db"
AGENT = "Citation Tester <citation-tester@example.invalid>"
REC = "20260901T000000Z-review-grok-aaaaaa"
ADJ_REC = "20260901T010000Z-adjudicate-grok-bbbbbb"
SWEEP_REC = "20260901T020000Z-sweep-codex-cccccc"
SCOPE_REL = ".dev/ladder-inputs/scope-gate-20260910.md"
OTHER_REL = ".dev/ladder-inputs/other-scope.md"
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
OTHER_BODY = "# Other\n\n1. **A numbered item on another file.**\n"
ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)
RUN_CAP = 30


def _live_snapshot() -> tuple[str, bytes | None]:
    if LIVE_STORE.is_file():
        return ("file", LIVE_STORE.read_bytes())
    if LIVE_STORE.exists():
        return ("other", None)
    return ("absent", None)


def _load_findings(path: Path):
    spec = importlib.util.spec_from_file_location("findings_citation", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _item_path(got):
    if got is None:
        return None
    if hasattr(got, "group"):
        return got.group("item"), got.group("path")
    if isinstance(got, dict) and "item" in got and "path" in got:
        return str(got["item"]), str(got["path"])
    return None


class _CitationFixture(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.assertTrue(TOOL.is_file(), f"{TOOL} is missing")
        self._live_before = _live_snapshot()
        self._tmp = tempfile.TemporaryDirectory(prefix="findings-citation-")
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.scratch = root / "scratch"
        self.repo = root / "repo"
        self.records = self.repo / ".dev" / "records" / "dispatches"
        self.home.mkdir()
        self.scratch.mkdir()
        self.records.mkdir(parents=True)
        self.staged = self.repo / "ops" / "conductor" / "tools" / "findings.py"
        self.store = (
            self.home / ".local" / "state" / "agentscient" / "findings.db"
        )
        self.scope = self.repo / SCOPE_REL
        self.other = self.repo / OTHER_REL
        self._stage_tool_bytes()
        self._plant_bytes(self.scope, SCOPE_BODY.encode("utf-8"))
        self._plant_bytes(self.other, OTHER_BODY.encode("utf-8"))
        self.mod = _load_findings(self.staged)
        self.assertIsNotNone(self.mod, "staged findings.py did not load")
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

    def _stage_tool_bytes(self) -> None:
        self.staged.parent.mkdir(parents=True, exist_ok=True)
        data = TOOL.read_bytes()
        self.staged.write_bytes(data)
        landed = self.staged.read_bytes()
        self.assertEqual(landed, data, "copy-tool-bytes did not land intact")
        self.assertNotEqual(landed, ABSENT_STUB)

    def _plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")

    def env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "WF_AGENT": AGENT,
        }
        if extra:
            env.update(extra)
        return env

    def invoke(self, argv: list[str], *, extra_env: dict[str, str] | None = None):
        return subprocess.run(
            [sys.executable, str(self.staged), *argv],
            cwd=str(self.repo),
            env=self.env(extra_env),
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )

    def parse(self, evidence: str):
        fn = getattr(self.mod, "parse_citation", None)
        if not callable(fn):
            return None
        return fn(evidence)

    def holds(self, evidence: str, root: Path, scope_path: str):
        fn = getattr(self.mod, "citation_holds", None)
        if not callable(fn):
            return False, "citation_holds is not defined"
        try:
            return fn(evidence, root, scope_path)
        except TypeError:
            return False, "citation_holds does not take scope_path"

    def plant_record(self, rec_id: str, job: str, claim: str) -> Path:
        envelope = {
            "id": rec_id,
            "lane": "dev",
            "stage": "review",
            "unit": "lane/citation",
            "job": job,
            "role": "read",
            "status": "closed",
            "harness": {"name": "grok"},
            "model": {"ran": "grok-4.6"},
            "result": {
                "envelope": {
                    "status": "ok",
                    "verdict": "changes",
                    "findings": [
                        {
                            "severity": "p1",
                            "where": "ops/x.py",
                            "claim": claim,
                            "reproduce": None,
                        }
                    ],
                }
            },
        }
        path = self.records / f"{rec_id}.json"
        payload = json.dumps(envelope, indent=2) + "\n"
        self._plant_bytes(path, payload.encode("utf-8"))
        self.assertIn(claim, path.read_text(encoding="utf-8"))
        return path

    def import_records(self):
        proc = self.invoke(["import"])
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        return proc

    def store_keys(self) -> list[str]:
        if not self.store.is_file():
            return []
        con = sqlite3.connect(self.store)
        try:
            rows = list(con.execute("select key from findings order by key"))
        finally:
            con.close()
        return [row[0] for row in rows]


class ParseCitation(unittest.TestCase):
    """Item 4 / R1 — grammar only: item and path, colon is a delimiter."""

    maxDiff = None

    def setUp(self):
        self.assertTrue(TOOL.is_file(), f"{TOOL} is missing")
        self.mod = _load_findings(TOOL)
        self.assertIsNotNone(self.mod, "findings.py did not load")

    def parse(self, evidence: str):
        fn = getattr(self.mod, "parse_citation", None)
        if not callable(fn):
            return None
        return fn(evidence)

    def test_prescribed_evidence_captures_item_and_path_without_the_colon(self):
        got = self.parse(VALID_EVIDENCE)
        captured = _item_path(got)
        self.assertIsNotNone(
            captured,
            "item 4: prescribed evidence must parse to item and path",
        )
        item, path = captured
        self.assertEqual(item, "3")
        self.assertEqual(
            path,
            ".dev/ladder-inputs/scope-gate-20260910.md",
            "R1: the path stops before the colon in "
            "`contract item N of PATH: why`",
        )
        self.assertFalse(path.endswith(":"))

    def test_missing_of_is_rejected(self):
        valid = _item_path(self.parse(VALID_EVIDENCE))
        got = self.parse(
            "contract item 3 .dev/ladder-inputs/scope-gate-20260910.md"
        )
        self.assertIsNotNone(valid, "grammar must parse the prescribed evidence")
        self.assertIsNone(got, "a citation without 'of' is not a citation")

    def test_zero_item_is_rejected(self):
        valid = _item_path(self.parse(VALID_EVIDENCE))
        got = self.parse(
            "contract item 0 of .dev/ladder-inputs/scope-gate-20260910.md"
        )
        self.assertIsNotNone(valid, "grammar must parse the prescribed evidence")
        self.assertIsNone(got, "item 0 is not a numbered contract item")

    def test_bare_text_is_rejected(self):
        valid = _item_path(self.parse(VALID_EVIDENCE))
        got = self.parse("fixed in commit abc without a contract item")
        self.assertIsNotNone(valid, "grammar must parse the prescribed evidence")
        self.assertIsNone(got, "bare disposition text is not a citation")

    def test_leading_zero_multi_digit_item_is_rejected(self):
        valid = _item_path(self.parse(VALID_EVIDENCE))
        got = self.parse(
            "contract item 03 of .dev/ladder-inputs/scope-gate-20260910.md"
        )
        self.assertIsNotNone(valid, "grammar must parse the prescribed evidence")
        self.assertIsNone(
            got,
            "a leading zero is not a numbered item [1-9][0-9]*",
        )


class CitationHolds(_CitationFixture):
    """Item 4 / R3 — grammar plus the named scope file under root."""

    def test_item_present_on_the_named_scope_file_holds(self):
        ok, reason = self.holds(VALID_EVIDENCE, self.repo, SCOPE_REL)
        self.assertTrue(
            ok,
            f"item 4: numbered item on the named scope file holds; "
            f"reason={reason!r}",
        )

    def test_item_absent_from_the_named_scope_file_does_not_hold(self):
        ok, _ = self.holds(VALID_EVIDENCE, self.repo, SCOPE_REL)
        missing = (
            "contract item 99 of .dev/ladder-inputs/scope-gate-20260910.md: "
            "no such item"
        )
        bad, reason = self.holds(missing, self.repo, SCOPE_REL)
        self.assertTrue(ok, "positive neighbour must hold")
        self.assertFalse(bad, "item 99 is not a numbered line of the scope")
        self.assertTrue(reason, "a failed hold names a reason")

    def test_path_absent_from_root_does_not_hold(self):
        ok, _ = self.holds(VALID_EVIDENCE, self.repo, SCOPE_REL)
        missing = "contract item 3 of .dev/ladder-inputs/no-such-scope.md: why"
        bad, reason = self.holds(
            missing, self.repo, ".dev/ladder-inputs/no-such-scope.md"
        )
        self.assertTrue(ok, "positive neighbour must hold")
        self.assertFalse(bad, "a missing scope file does not hold")
        self.assertTrue(reason, "a failed hold names a reason")

    def test_path_outside_root_does_not_hold(self):
        ok, _ = self.holds(VALID_EVIDENCE, self.repo, SCOPE_REL)
        outside = self.scratch / "outside.md"
        self._plant_bytes(outside, SCOPE_BODY.encode("utf-8"))
        evidence = f"contract item 3 of {outside}: why"
        bad, reason = self.holds(evidence, self.repo, str(outside))
        self.assertTrue(ok, "positive neighbour must hold")
        self.assertFalse(bad, "a path outside root does not hold")
        self.assertTrue(reason, "a failed hold names a reason")

    def test_citation_to_a_different_numbered_file_does_not_hold(self):
        ok, _ = self.holds(VALID_EVIDENCE, self.repo, SCOPE_REL)
        other = "contract item 1 of .dev/ladder-inputs/other-scope.md: why"
        # The other file has item 1; R3 still refuses it as the scope.
        bad, reason = self.holds(other, self.repo, SCOPE_REL)
        self.assertTrue(ok, "positive neighbour must hold")
        self.assertFalse(
            bad,
            "R3: a citation to any file other than the correction's "
            "scope file does not hold",
        )
        self.assertTrue(reason, "a failed hold names a reason")

    def test_item_without_whitespace_after_the_dot_does_not_hold(self):
        ok, _ = self.holds(VALID_EVIDENCE, self.repo, SCOPE_REL)
        mutant_rel = ".dev/ladder-inputs/mutant-scope.md"
        mutant = self.repo / mutant_rel
        self._plant_bytes(mutant, b"# X\n3.no-space\n")
        evidence = f"contract item 3 of {mutant_rel}: why"
        bad, reason = self.holds(evidence, self.repo, mutant_rel)
        self.assertTrue(ok, "positive neighbour must hold")
        self.assertFalse(
            bad,
            "item 4: the numbered line is '^\\s*<item>\\.\\s', not '3.no-space'",
        )
        self.assertTrue(reason, "a failed hold names a reason")


class CitedVerb(_CitationFixture):
    """Item 9 ledger half / D11 — cited KEY, exits 0 / 1 / 2."""

    def test_cited_of_a_holding_disposition_prints_the_citation(self):
        self.plant_record(REC, "adversarial-review", "holding-citation")
        self.import_records()
        key = f"{REC}#1"
        self.assertIn(key, self.store_keys())
        disp = self.invoke(
            [
                "disposition",
                key,
                "fixed",
                VALID_EVIDENCE,
            ],
            extra_env={"WF_AGENT": AGENT},
        )
        self.assertEqual(disp.returncode, 0, disp.stderr or disp.stdout)
        proc = self.invoke(["cited", key])
        self.assertEqual(
            proc.returncode,
            0,
            proc.stderr or proc.stdout,
        )
        line = (proc.stdout or "").strip()
        self.assertEqual(
            line,
            f"{key}\tcontract item 3 of {SCOPE_REL}",
        )
        self.assertEqual((proc.stderr or "").strip(), "")

    def test_cited_of_an_open_key_exits_1_with_open(self):
        self.plant_record(REC, "adversarial-review", "still-open")
        self.import_records()
        key = f"{REC}#1"
        self.assertIn(key, self.store_keys())
        proc = self.invoke(["cited", key])
        self.assertEqual(proc.returncode, 1, proc.stderr or proc.stdout)
        self.assertEqual((proc.stdout or "").strip(), f"{key}\topen")

    def test_cited_of_an_uncited_disposition_exits_1_with_the_reason(self):
        self.plant_record(REC, "adversarial-review", "uncited-evidence")
        self.import_records()
        key = f"{REC}#1"
        disp = self.invoke(
            ["disposition", key, "fixed", "fixed in tests, no item"],
            extra_env={"WF_AGENT": AGENT},
        )
        self.assertEqual(disp.returncode, 0, disp.stderr or disp.stdout)
        proc = self.invoke(["cited", key])
        self.assertEqual(proc.returncode, 1, proc.stderr or proc.stdout)
        line = (proc.stdout or "").strip()
        self.assertTrue(
            line.startswith(f"{key}\tuncited:"),
            f"D11: uncited disposition is KEY\\tuncited: <reason>; got {line!r}",
        )

    def test_cited_of_an_absent_key_is_class_key_exit_2(self):
        self.plant_record(REC, "adversarial-review", "some-other-finding")
        self.import_records()
        missing = "20260901T000000Z-review-grok-ffffff#1"
        proc = self.invoke(["cited", missing])
        err = proc.stderr or ""
        self.assertEqual(proc.returncode, 2, err or proc.stdout)
        self.assertEqual((proc.stdout or "").strip(), "")
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        head = lines[0].split(":", 1)[0].strip().lower().replace("_", "-")
        self.assertEqual(head, "key", lines[0])
        lower = lines[0].lower()
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, lines[0])

    def test_cited_is_a_read_and_does_not_need_identity(self):
        self.plant_record(REC, "adversarial-review", "read-no-identity")
        self.import_records()
        key = f"{REC}#1"
        env = self.env()
        env.pop("WF_AGENT", None)
        self.assertNotIn("WF_AGENT", env)
        proc = subprocess.run(
            [sys.executable, str(self.staged), "cited", key],
            cwd=str(self.repo),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )
        head = (proc.stderr or "").split(":", 1)[0].strip().lower()
        self.assertNotEqual(
            head,
            "identity",
            "item 9: cited is a read; identity is not required",
        )
        self.assertEqual(
            proc.returncode,
            1,
            proc.stderr or proc.stdout,
        )
        self.assertEqual((proc.stdout or "").strip(), f"{key}\topen")


class ImportReviewJobs(_CitationFixture):
    """Item 1 / R4 — every review job named by the gate can acquire rows."""

    def test_import_takes_an_adjudicate_record(self):
        self.plant_record(ADJ_REC, "adjudicate", "adjudicate-marker")
        proc = self.import_records()
        self.assertIn("1 finding", proc.stdout)
        self.assertIn(f"{ADJ_REC}#1", self.store_keys())

    def test_import_takes_a_sweep_record(self):
        self.plant_record(SWEEP_REC, "sweep", "sweep-marker")
        proc = self.import_records()
        self.assertIn("1 finding", proc.stdout)
        self.assertIn(f"{SWEEP_REC}#1", self.store_keys())


if __name__ == "__main__":
    unittest.main()
