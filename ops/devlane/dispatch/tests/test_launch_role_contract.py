"""Document pins for the read-role write-instruction refusal.

Written from contract items 5 and 7 of
`.dev/ladder-inputs/scope-item31-20260911.md`. Slice 1 only: these tests
read `ops/devlane/dispatch/CONTRACT.md` and never import launch.py.

Item 5: a read-role prompt with a positive instruction to write a path
is refused at render, class `role`, naming the job and the sentence.
Item 7: the refusal is one stderr line, exit 2, founding wire.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CONTRACT = REPO / "ops" / "devlane" / "dispatch" / "CONTRACT.md"

EXPECTED = "a read-role prompt with no instruction to write a path"
FOUND_JOB = "found job check-tests:"
FOUND_SENTENCE = (
    "Write the report to {out}/SKEPTIC.md and name that path in artifacts"
)
NEEDED = (
    "drop the sentence from the prompt or declare the job a write role"
)
EXIT_2 = "exit 2"
FOUNDING_WIRE = "founding wire"


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

    def refusals(self) -> str:
        block = _section(self.dispatch, "### Refusals")
        self.assertTrue(block, "Dispatch is missing ### Refusals")
        return block

    def refusal_table(self) -> list[list[str]]:
        table = _first_table(self.refusals())
        self.assertTrue(table, "Dispatch §Refusals has no table")
        return table

    def refusal_row(self, ident: str) -> list[str] | None:
        for cells in self.refusal_table()[1:]:
            if _row_id(cells) == ident:
                return cells
        return None

    def role_blob(self) -> str:
        row = self.refusal_row("role")
        if row is None:
            return ""
        return " ".join(row)


class RoleRefusalRow(_ContractPin):
    """Item 5 / item 7 — class role, exit 2, founding wire."""

    def test_refusals_table_has_a_role_row(self):
        have = [_row_id(cells) for cells in self.refusal_table()[1:]]
        self.assertIsNotNone(
            self.refusal_row("role"),
            f"no refusal row id 'role'; have {have}",
        )

    def test_role_row_declares_exit_2(self):
        mutant = "`role` (exit 3, mid-act stop)"
        self.assertNotIn("exit 2", mutant)
        self.assertIn(EXIT_2, self.role_blob())

    def test_role_row_declares_the_founding_wire(self):
        mutant = "`role` (exit 2, before the gate)"
        self.assertNotIn(FOUNDING_WIRE, mutant)
        self.assertIn(FOUNDING_WIRE, self.role_blob())

    def test_role_expected_half_is_a_read_role_prompt_with_no_write_instruction(
        self,
    ):
        mutant = "expected a write-role prompt that names an output file"
        self.assertNotIn(EXPECTED, mutant)
        self.assertIn(EXPECTED, self.role_blob())

    def test_role_found_half_names_the_job(self):
        mutant = "found a prompt that writes a file"
        self.assertNotIn(FOUND_JOB, mutant)
        self.assertIn(FOUND_JOB, self.role_blob())

    def test_role_found_half_names_the_sentence(self):
        mutant = "found job check-tests: a prose report"
        self.assertNotIn(FOUND_SENTENCE, mutant)
        self.assertIn(FOUND_SENTENCE, self.role_blob())

    def test_role_needed_half_drops_the_sentence_or_declares_a_write_role(self):
        mutant = "needed remove {out} from the template values"
        self.assertNotIn(NEEDED, mutant)
        self.assertIn(NEEDED, self.role_blob())


if __name__ == "__main__":
    unittest.main()
