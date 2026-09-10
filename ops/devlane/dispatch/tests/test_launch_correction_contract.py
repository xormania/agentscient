"""Document pins for the uncited-correction gate in the launch contract.

Written from the numbered Contract items of
`.dev/ladder-inputs/scope-gate-20260910.md` and the planner fill-ins
in `in/plan-gate-contracts.md` (D1-D9). Slice 1 only: these tests
read `ops/devlane/dispatch/CONTRACT.md` and never import launch.py or
record.py.

Each test is a pin of one declared row, field, or quoted grammar. A
broken contract that omits that row still collects; it fails the
assertion below.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CONTRACT = REPO / "ops" / "devlane" / "dispatch" / "CONTRACT.md"

CITATION_GRAMMAR = (
    r"contract item (?P<item>[1-9][0-9]*) of (?P<path>[^\s;,]+)"
)

FOUND_TEXTS = (
    (
        "no-key",
        "no --answers key named for a correction following",
    ),
    (
        "absent",
        "absent from the findings store",
    ),
    (
        "absent-no-store",
        "(no store)",
    ),
    (
        "open",
        "key <key> still open",
    ),
    (
        "uncited",
        "without a contract citation",
    ),
    (
        "late",
        "after the mint attempt at",
    ),
)


def _section(text: str, prefix: str) -> str:
    lines = text.splitlines()
    heading_level = None
    start = None
    for i, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        rest = line[len(prefix):]
        if rest == "" or rest[0] in " \t—-":
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


def _first_table(block: str) -> list[list[str]]:
    rows: list[list[str]] = []
    in_table = False
    for line in block.splitlines():
        if line.startswith("|"):
            in_table = True
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells and all(cell and set(cell) <= set("-: ") for cell in cells):
                continue
            rows.append(cells)
            continue
        if in_table:
            break
    return rows


def _first_fence(block: str) -> str:
    parts = block.split("```")
    if len(parts) < 2:
        return ""
    body = parts[1]
    if body.startswith("text"):
        body = body.split("\n", 1)[-1]
    return body.strip()


def _row_id(cells: list[str]) -> str:
    token = cells[0].replace("`", "")
    return token.split()[0] if token.split() else ""


class _ContractPin(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.assertTrue(CONTRACT.is_file(), f"missing {CONTRACT}")
        self.text = CONTRACT.read_text(encoding="utf-8")
        self.assertTrue(self.text.strip(), "CONTRACT.md is empty")
        dispatch = _section(self.text, "## Dispatch")
        self.assertTrue(dispatch, "CONTRACT.md has no ## Dispatch section")
        self.dispatch = dispatch

    def section(self, prefix: str) -> str:
        block = _section(self.dispatch, prefix)
        self.assertTrue(block, f"Dispatch is missing {prefix!r}")
        return block

    def refusal_table(self) -> list[list[str]]:
        table = _first_table(self.section("### Refusals"))
        self.assertTrue(table, "Dispatch §Refusals has no table")
        return table

    def refusal_row(self, ident: str) -> list[str] | None:
        for cells in self.refusal_table()[1:]:
            if _row_id(cells) == ident:
                return cells
        return None

    def require_refusal_row(self, ident: str) -> list[str]:
        row = self.refusal_row(ident)
        if row is not None:
            return row
        have = [_row_id(cells) for cells in self.refusal_table()[1:]]
        self.fail(f"no refusal row id {ident!r}; have {have}")

    def row_or_section(self, ident: str) -> str:
        row = self.refusal_row(ident)
        if row is not None:
            return " ".join(row)
        return self.section("### Refusals")


class AnswersVerbIsDeclared(_ContractPin):
    """Item 2 / D1 — the declared field is --answers KEY, repeatable."""

    def test_verbs_usage_names_repeatable_answers_after_follows(self):
        usage = _first_fence(self.section("### Verbs"))
        self.assertTrue(usage, "Dispatch §Verbs has no usage fence")
        collapsed = " ".join(usage.split())
        self.assertIn(
            "[--follows ID]... [--answers KEY]...",
            collapsed,
            "§Verbs usage must declare repeatable [--answers KEY]... "
            "after [--follows ID]...",
        )


class CorrectionRefusalRow(_ContractPin):
    """Item 3 / D4 D5 D9 — class correction, five found-texts, exit 2,
    founding wire, not overridable."""

    def test_refusals_table_has_a_correction_row_that_is_not_overridable(self):
        row = self.require_refusal_row("correction")
        self.assertGreaterEqual(len(row), 2, "correction row is a table stub")
        self.assertNotIn(
            "override",
            row[0].lower(),
            "correction has no overrides row; the id cell must not "
            "mark it overridable",
        )

    def test_correction_row_names_each_found_text(self):
        blob = self.row_or_section("correction")
        for arm, fragment in FOUND_TEXTS:
            with self.subTest(arm=arm):
                self.assertIn(
                    fragment,
                    blob,
                    f"correction missing {arm} found-text {fragment!r}",
                )

    def test_correction_expected_half_is_the_constant_citation_before_stamp(self):
        blob = self.row_or_section("correction")
        self.assertIn(
            "every finding answered by this correction "
            "disposed with a contract citation before",
            blob,
        )

    def test_correction_needed_half_names_findings_py_disposition(self):
        blob = self.row_or_section("correction")
        self.assertIn(
            "python3 ops/conductor/tools/findings.py disposition",
            blob,
        )

    def test_correction_row_declares_exit_2_on_the_founding_wire(self):
        blob = self.row_or_section("correction")
        for fragment in ("exit 2", "founding wire"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, blob)


class FollowsRefusalRow(_ContractPin):
    """Item 1 / D7 — an unreadable followed record is class follows."""

    def test_refusals_table_has_a_follows_row(self):
        row = self.require_refusal_row("follows")
        self.assertGreaterEqual(len(row), 2, "follows row is a table stub")

    def test_follows_row_names_the_unreadable_record_found_text(self):
        blob = self.row_or_section("follows")
        for fragment in ("readable record", ".dev/records/dispatches"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, blob)


class AnswersRecordField(_ContractPin):
    """Item 8 / D8 — answers after follows, shaped, absence declared."""

    def test_worker_fields_list_answers_after_follows_with_the_declared_shape(self):
        fence = _first_fence(self.section("### The record"))
        self.assertTrue(fence, "Dispatch §The record has no fields fence")
        collapsed = " ".join(fence.split())
        self.assertIn(
            "follows [ids], answers [{key, disposition, disposed_at, "
            "citation {item, path}}]",
            collapsed,
        )

    def test_the_record_declares_pre_field_absence_is_not_none_answered(self):
        record = self.section("### The record")
        for fragment in ("minted before the field landed", "none answered"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, record)


class CitationGrammarQuote(_ContractPin):
    """Item 4 / D3 — the grammar is quoted once; findings.py is its home."""

    def test_citation_grammar_is_quoted_once(self):
        count = self.text.count(CITATION_GRAMMAR)
        self.assertEqual(
            count,
            1,
            f"citation grammar quoted {count} time(s), want 1: "
            f"{CITATION_GRAMMAR}",
        )

    def test_grammar_quote_names_findings_py_as_its_home(self):
        self.assertRegex(
            self.dispatch,
            re.compile(
                r"grammar.{0,240}findings\.py|findings\.py.{0,240}grammar",
                re.IGNORECASE | re.DOTALL,
            ),
        )


class KeyShapeIsDeclared(_ContractPin):
    """Item 2 / D1 — KEY is a findings-store key <record>#<n>."""

    def test_verbs_declare_the_answers_key_shape(self):
        verbs = self.section("### Verbs")
        self.assertIn("<record>#<n>", verbs)
