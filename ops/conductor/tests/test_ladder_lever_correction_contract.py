"""Document pins for the uncited-correction stop on the ladder lever.

Written from scope-gate-20260910.md item 9 and item 4, and the planner
fill-ins in plan-gate-contracts.md (D10, D11). Slice 1 only: these tests
read `ops/conductor/ladder-lever.md` and `ops/conductor/findings/README.md`
and never import ladder.py or findings.py.

A broken contract that omits the undisposed stop, the fix-stage
--answers arguments, or the cited verb still collects; it fails the
assertion below.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LEVER = REPO / "ops" / "conductor" / "ladder-lever.md"
README = REPO / "ops" / "conductor" / "findings" / "README.md"


def _section(text: str, prefix: str) -> str:
    lines = text.splitlines()
    heading_level = None
    start = None
    for i, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        rest = line[len(prefix):]
        if rest == "" or rest[0] in " \t—-,":
            heading_level = len(line) - len(line.lstrip("#"))
            start = i + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("#"):
            hashes = len(line) - len(line.lstrip("#"))
            if hashes <= heading_level:
                break
        body.append(line)
    return "\n".join(body)


def _tables(block: str) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in block.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells and all(cell and set(cell) <= set("-: ") for cell in cells):
                continue
            current.append(cells)
            continue
        if current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _row_id(cells: list[str]) -> str:
    token = cells[0].replace("`", "")
    return token.split()[0] if token.split() else ""


class _LeverPin(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.assertTrue(LEVER.is_file(), f"missing {LEVER}")
        self.lever = LEVER.read_text(encoding="utf-8")
        self.assertTrue(self.lever.strip(), "ladder-lever.md is empty")

    def section(self, prefix: str) -> str:
        block = _section(self.lever, prefix)
        self.assertTrue(block, f"ladder-lever.md is missing {prefix!r}")
        return block

    def stage_row(self, ident: str) -> list[str]:
        tables = _tables(self.section("## Stage table"))
        self.assertTrue(tables, "stage table is missing")
        for table in tables:
            for cells in table[1:]:
                if _row_id(cells) == ident:
                    return cells
        have = [
            _row_id(cells)
            for table in tables
            for cells in table[1:]
        ]
        self.fail(f"no stage row {ident!r}; have {have}")


class FixStagesCarryAnswers(_LeverPin):
    """Item 9 / D10 — fix-tests and fix-code are corrections: --follows
    and --answers on the dispatched argv."""

    def test_fix_tests_row_names_follows_and_answers(self):
        blob = " ".join(self.stage_row("fix-tests"))
        for fragment in ("--follows", "--answers"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, blob)

    def test_fix_code_row_names_follows_and_answers(self):
        blob = " ".join(self.stage_row("fix-code"))
        for fragment in ("--follows", "--answers"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, blob)


class UndisposedStop(_LeverPin):
    """Item 9 / D10 — stop before either fix stage; resume re-checks;
    the driver never writes dispositions."""

    def test_stops_declare_reason_undisposed(self):
        self.assertIn("undisposed", self.section("## Stops"))

    def test_undisposed_stop_line_names_each_fix_stage(self):
        stops = self.section("## Stops")
        for stage in ("fix-tests", "fix-code"):
            with self.subTest(stage=stage):
                self.assertIn(
                    f"stopped stage={stage} record=none reason=undisposed",
                    stops,
                )

    def test_undisposed_stop_lists_the_keys(self):
        stops = self.section("## Stops")
        self.assertIn("undisposed keys:", stops)

    def test_the_record_stopped_object_carries_keys(self):
        record = self.section("## Record")
        self.assertRegex(
            record,
            re.compile(r"stopped.{0,160}keys|keys.{0,160}stop", re.DOTALL),
        )

    def test_resume_repeats_the_undisposed_check(self):
        self.assertRegex(
            self.lever,
            re.compile(
                r"resume.{0,240}undisposed|undisposed.{0,240}resume",
                re.IGNORECASE | re.DOTALL,
            ),
        )

    def test_the_driver_never_calls_findings_py_disposition(self):
        self.assertIn("never calls `findings.py disposition`", self.lever)


class CitedVerbOnTheLedger(_LeverPin):
    """Item 4 / D11 — the ledger README names cited and the grammar home."""

    def test_readme_names_the_cited_verb(self):
        self.assertTrue(README.is_file(), f"missing {README}")
        text = README.read_text(encoding="utf-8")
        self.assertTrue(text.strip(), "findings README is empty")
        self.assertIn("`cited`", text)

    def test_readme_names_findings_py_as_the_citation_grammar_home(self):
        self.assertTrue(README.is_file(), f"missing {README}")
        text = README.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            re.compile(
                r"grammar.{0,240}findings\.py|findings\.py.{0,240}grammar",
                re.IGNORECASE | re.DOTALL,
            ),
        )
