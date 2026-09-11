"""Document pins for the check-tests deliverable on the wire.

Written from contract items 1 and 2 of
`.dev/ladder-inputs/scope-item31-20260911.md`. Slice 1 only: these tests
read `ops/devlane/task/CONTRACT.md` and never import jobs.json,
envelope.py, or the runner.

Item 1: the `check-tests` jobs-table row delivers the JSON envelope on
stdout, `artifacts` empty, no file written. Item 2: each finding is a
quotation pair; the grammar is quoted once under The skeptic's finding.
The C1/C2 render-slot prose that still names `{out}/SKEPTIC.md` is
outside this work order and is not pinned here.
"""

from __future__ import annotations

import re
import unittest

import support

CONTRACT = support.REPO / "ops" / "devlane" / "task" / "CONTRACT.md"

OLD_FILE_DELIVERABLE = "a skeptic's report at `out/SKEPTIC.md`"
ENVELOPE_ON_STDOUT = "the JSON envelope on stdout"
QUOTATION_PAIR = "quotation pair"
ARTIFACTS_EMPTY = "`artifacts` empty"
NO_FILE_WRITTEN = "no file written"
VERDICT_WHEN_FINDINGS = "verdict `changes` exactly when any finding exists"
GRAMMAR_HEADING = "The skeptic's finding"
CLAIM_GRAMMAR = (
    "declared (<location>): <words verbatim>; practiced: "
    "<evidence verbatim>; misses: <the broken implementation the test "
    "would not catch>"
)
SPLIT_RULE = "the first `; practiced: ` and the last `; misses: `"
DECLARED_LOCATION_RULE = "no parentheses"
REPRODUCE_NULL = "an opinion is not a finding"
WHERE_RULE = re.compile(
    r"no whitespace.*contains `/` or `\.`|contains `/` or `\.`.*no whitespace",
    re.IGNORECASE | re.DOTALL,
)
SEVERITY_RULE = re.compile(r"`p1`.*`p2`.*`p3`|p1,\s*p2 or p3")


def _section(text: str, prefix: str) -> str:
    lines = text.splitlines()
    heading_level = None
    start = None
    for i, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        rest = line[len(prefix) :]
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


def _heading_body(text: str, title: str) -> str:
    lines = text.splitlines()
    start = None
    heading_level = None
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            continue
        hashes = len(line) - len(line.lstrip("#"))
        label = line.lstrip("#").strip()
        if label == title:
            start = i + 1
            heading_level = hashes
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


class _ContractPin(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.assertTrue(CONTRACT.is_file(), f"missing {CONTRACT}")
        self.text = CONTRACT.read_text(encoding="utf-8")
        self.assertTrue(self.text.strip(), "CONTRACT.md is empty")

    def jobs_deliverable(self, ident: str) -> str:
        tables = _tables(_section(self.text, "## Jobs"))
        for table in tables:
            for cells in table[1:]:
                if _row_id(cells) == ident:
                    return cells[1] if len(cells) > 1 else ""
        return ""

    def skeptic_finding(self) -> str:
        return _heading_body(self.text, GRAMMAR_HEADING)


class CheckTestsJobRow(_ContractPin):
    """Item 1 — check-tests delivers the envelope on stdout, no file."""

    def test_the_check_tests_row_delivers_the_json_envelope_on_stdout(self):
        mutant = OLD_FILE_DELIVERABLE
        self.assertNotIn(
            ENVELOPE_ON_STDOUT,
            mutant,
            "a file path is not the envelope on stdout",
        )
        self.assertIn(ENVELOPE_ON_STDOUT, self.jobs_deliverable("check-tests"))

    def test_the_check_tests_row_names_a_quotation_pair(self):
        mutant = "findings that survived the auditor's own attempt to refute them"
        self.assertNotIn(QUOTATION_PAIR, mutant)
        self.assertIn(QUOTATION_PAIR, self.jobs_deliverable("check-tests"))

    def test_the_check_tests_row_says_artifacts_empty(self):
        mutant = "a skeptic's report at `out/SKEPTIC.md` and name that path in artifacts"
        self.assertNotIn(ARTIFACTS_EMPTY, mutant)
        self.assertIn(ARTIFACTS_EMPTY, self.jobs_deliverable("check-tests"))

    def test_the_check_tests_row_says_no_file_written(self):
        mutant = "a skeptic's report at `out/SKEPTIC.md`; verdict `changes`"
        self.assertNotIn(NO_FILE_WRITTEN, mutant)
        self.assertIn(NO_FILE_WRITTEN, self.jobs_deliverable("check-tests"))

    def test_the_check_tests_row_verdict_changes_exactly_when_any_finding_exists(
        self,
    ):
        mutant = "verdict `changes` when any test is refuted"
        self.assertNotIn(VERDICT_WHEN_FINDINGS, mutant)
        self.assertIn(VERDICT_WHEN_FINDINGS, self.jobs_deliverable("check-tests"))

    def test_the_check_tests_row_does_not_deliver_a_skeptic_md_file(self):
        cell = self.jobs_deliverable("check-tests")
        self.assertTrue(cell, "no check-tests jobs-table row")
        self.assertNotIn(
            OLD_FILE_DELIVERABLE,
            cell,
            "item 1: the row delivers the envelope, not out/SKEPTIC.md",
        )

    def test_the_check_tests_row_points_at_the_skeptic_finding_subsection(self):
        cell = self.jobs_deliverable("check-tests")
        self.assertIn(GRAMMAR_HEADING, cell)


class SkepticFindingGrammar(_ContractPin):
    """Item 2 — the quotation-pair grammar, quoted once."""

    def test_the_skeptic_finding_subsection_exists(self):
        body = self.skeptic_finding()
        self.assertTrue(
            body.strip(),
            f"CONTRACT.md is missing subsection {GRAMMAR_HEADING!r}",
        )

    def test_the_claim_grammar_is_quoted_in_the_subsection(self):
        mutant = "Contract item 9 requires a fresh check"
        self.assertNotIn(CLAIM_GRAMMAR, mutant)
        body = self.skeptic_finding()
        self.assertIn(CLAIM_GRAMMAR, body)

    def test_the_claim_split_is_first_practiced_and_last_misses(self):
        mutant = "split the claim on every semicolon"
        self.assertNotIn(SPLIT_RULE, mutant)
        self.assertIn(SPLIT_RULE, self.skeptic_finding())

    def test_the_declared_location_has_no_parentheses(self):
        mutant = "declared (<location with (parens)>): words"
        self.assertNotIn(DECLARED_LOCATION_RULE, mutant)
        self.assertIn(DECLARED_LOCATION_RULE, self.skeptic_finding())

    def test_null_reproduce_is_refused_as_an_opinion(self):
        mutant = "reproduce may be null when the finding is an opinion"
        self.assertNotIn(REPRODUCE_NULL, mutant)
        body = self.skeptic_finding()
        self.assertIn("`null`", body)
        self.assertIn(REPRODUCE_NULL, body)

    def test_where_is_the_practiced_location_without_whitespace(self):
        mutant = "where is any string naming the test"
        self.assertIsNone(WHERE_RULE.search(mutant))
        self.assertRegex(self.skeptic_finding(), WHERE_RULE)

    def test_severity_is_p1_p2_or_p3(self):
        mutant = "severity is high, medium or low"
        self.assertIsNone(SEVERITY_RULE.search(mutant))
        self.assertRegex(self.skeptic_finding(), SEVERITY_RULE)


if __name__ == "__main__":
    unittest.main()
