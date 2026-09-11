"""Document pins for the check-tests stop and the custody file.

Written from contract items 3, 4 and 7 of
`.dev/ladder-inputs/scope-item31-20260911.md`. Slice 1 only: these tests
read `ops/conductor/ladder-lever.md` and never import ladder.py.

Item 3: the driver validates the envelope at the check-tests stop,
class `envelope`, never retried as a flake. Item 4: tests-fix receives
`skeptic-findings.md` the driver wrote; class `custody` refuses a
symlink. Item 7: the verb `check-envelope` is on the instrument.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LEVER = REPO / "ops" / "conductor" / "ladder-lever.md"

CUSTODY_FILE = "`skeptic-findings.md`"
DRIVER_WROTE = "written by the driver from the validated check-tests envelope"
SKEPTIC_MD = "SKEPTIC.md"
NEVER_RETRIED = "never retried"
RETRY_ONLY = "`--retry` is the only further attempt"
CHECK_ENVELOPE = "`check-envelope`"
CHECK_ENVELOPE_FORM = "PATH|-"
WIRE_THEN_STOPPED = "the wire line then the stopped line"
ENVELOPE_SHAPE = '{"field": "<dotted field>", "refusal": "<line>"}'
STOPPED_ENVELOPE = "reason=envelope"
STOPPED_CUSTODY = "reason=custody"
INVALID_ENVELOPE_PROSE = (
    "a stage refuses, trips, dies, records an invalid envelope, "
    "violates a guarantee, or an invoked write aborts"
)


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


def _row_names(cells: list[str], ident: str) -> bool:
    """True when a stop row is the named class, not a prose mention.

    The existing exit-3 condition 'records an invalid envelope' must not
    count as the envelope stop row: the ident has to be the cell, or
    the cell's first token, not a later word in a sentence.
    """
    for cell in cells:
        compact = cell.replace("`", "").strip()
        if not compact:
            continue
        if compact == ident:
            return True
        first = compact.split()[0].strip(",;:")
        if first == ident:
            return True
        if compact.startswith(ident + " ") or compact.startswith(ident + "("):
            return True
    return False


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

    def stage_input(self, ident: str) -> str:
        row = self.stage_row(ident)
        if len(row) > 4:
            return row[4]
        return " ".join(row)

    def stop_row(self, ident: str) -> list[str] | None:
        tables = _tables(self.section("## Stops"))
        for table in tables:
            for cells in table[1:]:
                if _row_names(cells, ident):
                    return cells
        return None

    def stop_blob(self, ident: str) -> str:
        row = self.stop_row(ident)
        if row is None:
            return ""
        return " ".join(row)


class TestsFixCustodyInput(_LeverPin):
    """Item 4 — tests-fix is given the driver-written custody file."""

    def test_tests_fix_input_names_skeptic_findings_md(self):
        mutant = "scope, plan, skeptic envelope and `SKEPTIC.md`"
        self.assertNotIn(CUSTODY_FILE, mutant)
        self.assertIn(CUSTODY_FILE, self.stage_input("tests-fix"))

    def test_tests_fix_input_is_written_by_the_driver_from_the_validated_envelope(
        self,
    ):
        mutant = "scope, plan, skeptic envelope and `SKEPTIC.md`"
        self.assertNotIn(DRIVER_WROTE, mutant)
        self.assertIn(DRIVER_WROTE, self.stage_input("tests-fix"))

    def test_tests_fix_input_does_not_name_skeptic_md(self):
        cell = self.stage_input("tests-fix")
        self.assertTrue(cell, "tests-fix input cell is empty")
        self.assertNotIn(
            SKEPTIC_MD,
            cell,
            "item 4: tests-fix receives the driver-written file, "
            "not a file the skeptic wrote",
        )


class EnvelopeAndCustodyStops(_LeverPin):
    """Item 3 / item 4 / item 7 — stop rows envelope and custody, exit 3."""

    def test_invalid_envelope_prose_is_not_the_envelope_stop_row(self):
        mutant = ["3", INVALID_ENVELOPE_PROSE, "the last reading, then stopped"]
        self.assertFalse(
            _row_names(mutant, "envelope"),
            "a prose mention of an invalid envelope is not class envelope",
        )
        self.assertIsNotNone(
            self.stop_row("envelope"),
            "stops table has no envelope row",
        )

    def test_custody_proof_prose_is_not_the_custody_stop_row(self):
        mutant = [
            "3",
            (
                "ordered stage rows naming job, harness, attempt, input path "
                "and digest, custody proof, dispatch record"
            ),
            "the last reading",
        ]
        self.assertFalse(
            _row_names(mutant, "custody"),
            "the record's custody proof is not class custody",
        )
        self.assertIsNotNone(
            self.stop_row("custody"),
            "stops table has no custody row",
        )

    def test_envelope_stop_is_exit_3_with_the_wire_line_then_the_stopped_line(
        self,
    ):
        blob = self.stop_blob("envelope")
        self.assertIn("3", blob)
        self.assertIn(STOPPED_ENVELOPE, blob)
        collapsed = " ".join(blob.split())
        self.assertTrue(
            "wire line" in collapsed and "stopped" in collapsed,
            "item 7: last output is the wire line then the stopped line; "
            f"found {blob!r}",
        )

    def test_custody_stop_is_exit_3_with_the_wire_line_then_the_stopped_line(
        self,
    ):
        blob = self.stop_blob("custody")
        self.assertIn("3", blob)
        self.assertIn(STOPPED_CUSTODY, blob)
        collapsed = " ".join(blob.split())
        self.assertTrue(
            "wire line" in collapsed and "stopped" in collapsed,
            "item 7: last output is the wire line then the stopped line; "
            f"found {blob!r}",
        )

    def test_envelope_stop_names_the_field(self):
        blob = self.stop_blob("envelope")
        self.assertIn("field", blob)

    def test_stops_section_states_the_last_output_shape(self):
        mutant = "the last reading, then stopped stage="
        self.assertNotIn(WIRE_THEN_STOPPED, mutant)
        stops = self.section("## Stops")
        collapsed = " ".join(stops.split())
        self.assertTrue(
            WIRE_THEN_STOPPED in collapsed
            or (
                "the wire line" in collapsed
                and "the stopped line" in collapsed
            ),
            "item 7: envelope and custody last output is the wire line "
            "then the stopped line",
        )


class CheckTestsStopNeverRetried(_LeverPin):
    """Item 3 — a malformed envelope is never retried as a flake."""

    def test_the_check_tests_stop_paragraph_exists(self):
        body = _heading_body(self.lever, "The check-tests stop")
        self.assertTrue(
            body.strip(),
            "ladder-lever.md is missing paragraph The check-tests stop",
        )

    def test_the_check_tests_stop_is_never_retried(self):
        mutant = (
            "The skeptic runs once on the first tests, never again "
            "after a test fix."
        )
        self.assertNotIn(NEVER_RETRIED, mutant)
        body = _heading_body(self.lever, "The check-tests stop")
        self.assertIn(NEVER_RETRIED, body)

    def test_retry_is_the_only_further_attempt(self):
        mutant = (
            "A stage has at most two attempts. Resume relaunches that "
            "stage once."
        )
        self.assertNotIn(RETRY_ONLY, mutant)
        body = _heading_body(self.lever, "The check-tests stop")
        self.assertIn(RETRY_ONLY, body)


class CheckEnvelopeVerb(_LeverPin):
    """Item 7 — the verb check-envelope lives on the instrument."""

    def test_instrument_names_the_check_envelope_verb(self):
        mutant = (
            "Review stages import their envelope through findings.py import"
        )
        self.assertNotIn(CHECK_ENVELOPE, mutant)
        self.assertIn(CHECK_ENVELOPE, self.section("## Instrument"))

    def test_check_envelope_accepts_a_path_or_stdin(self):
        mutant = "`check-envelope` reads whatever file the skeptic wrote"
        self.assertNotIn(CHECK_ENVELOPE_FORM, mutant)
        self.assertIn(CHECK_ENVELOPE_FORM, self.section("## Instrument"))


class RecordEnvelopeField(_LeverPin):
    """Item 3 — the stage row records the envelope field that failed."""

    def test_the_record_carries_the_envelope_field_shape(self):
        mutant = (
            "ordered stage rows naming job, harness, attempt, input path "
            "and digest, custody proof, dispatch record"
        )
        self.assertNotIn(ENVELOPE_SHAPE, mutant)
        self.assertIn(ENVELOPE_SHAPE, self.section("## Record"))


if __name__ == "__main__":
    unittest.main()
