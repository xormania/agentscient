"""plan extract: fixed-header tables, fenced json plan:<field> blocks, drift."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from support import EXAMPLES, FAULTS, assert_refusal, dump, load, run_plan_vet


def _pair(tmp, md_src=None, sidecar_src=None):
    """Stage an extract pair under the `*.plan.md` name the CLI takes."""
    root = Path(tmp)
    md = root / "leaf.plan.md"
    sidecar = root / "leaf.plan.json"
    shutil.copyfile(md_src or (EXAMPLES / "plan.md"), md)
    shutil.copyfile(sidecar_src or (EXAMPLES / "plan.json"), sidecar)
    return md, sidecar


class ExtractForm(unittest.TestCase):
    """Extract reads the three tables and the fenced fields; it never infers."""

    def test_extract_emits_sorted_keys_indent_2_and_a_trailing_newline(self):
        with tempfile.TemporaryDirectory(prefix="plan-extract-") as tmp:
            md, sidecar = _pair(tmp)
            sidecar.unlink()
            proc = run_plan_vet("extract", str(md))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(sidecar.is_file(), "extract writes <stem>.plan.json")
            landed = sidecar.read_bytes()
            expected = dump(load(EXAMPLES / "plan.json")).encode("utf-8")
            self.assertEqual(landed, expected)
            self.assertTrue(landed.endswith(b"\n"))
            self.assertEqual(
                landed.decode("utf-8"),
                json.dumps(json.loads(landed), sort_keys=True, indent=2) + "\n",
            )

    def test_check_is_quiet_when_the_sidecar_matches(self):
        with tempfile.TemporaryDirectory(prefix="plan-extract-") as tmp:
            md, sidecar = _pair(tmp)
            self.assertTrue(sidecar.is_file())
            proc = run_plan_vet("extract", str(md), "--check")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("plan.drift", proc.stderr)

    def test_check_draws_drift_when_key_order_differs(self):
        """Byte drift, not a value change — the cue-free half of fault 18."""
        with tempfile.TemporaryDirectory(prefix="plan-extract-") as tmp:
            md, sidecar = _pair(
                tmp,
                md_src=FAULTS / "plan.18.md",
                sidecar_src=FAULTS / "plan.18.json",
            )
            before_example = (EXAMPLES / "plan.json").read_bytes()
            after = sidecar.read_bytes()
            self.assertNotEqual(after, before_example)
            self.assertEqual(json.loads(after), json.loads(before_example))
            proc = run_plan_vet("extract", str(md), "--check")
            assert_refusal(self, proc, "plan.drift")

    def test_check_draws_drift_when_a_value_differs(self):
        with tempfile.TemporaryDirectory(prefix="plan-extract-") as tmp:
            md, sidecar = _pair(tmp)
            before = sidecar.read_bytes()
            planted = json.loads(before)
            planted["id"] = "example/leaf-reordered"
            sidecar.write_text(dump(planted), encoding="utf-8")
            after = sidecar.read_bytes()
            self.assertNotEqual(after, before)
            self.assertIn(b"example/leaf", before)
            proc = run_plan_vet("extract", str(md), "--check")
            assert_refusal(self, proc, "plan.drift")

    def test_a_field_stated_twice_is_refused(self):
        with tempfile.TemporaryDirectory(prefix="plan-extract-") as tmp:
            md, _sidecar = _pair(tmp)
            text = md.read_text(encoding="utf-8")
            self.assertIn("```json plan:id", text)
            md.write_text(
                text + "\n```json plan:id\n\"example/leaf-again\"\n```\n",
                encoding="utf-8",
            )
            landed = md.read_text(encoding="utf-8")
            self.assertGreater(landed.count("```json plan:id"), 1)
            proc = run_plan_vet("extract", str(md))
            assert_refusal(self, proc, "plan.extract-duplicate", actual="id")
            self.assertNotIn("plan.extract-missing", proc.stderr)

    def test_a_field_stated_nowhere_is_refused(self):
        with tempfile.TemporaryDirectory(prefix="plan-extract-") as tmp:
            md, _sidecar = _pair(tmp)
            text = md.read_text(encoding="utf-8")
            start = text.index("```json plan:id")
            end = text.index("```", start + 3) + 3
            stripped = text[:start] + text[end:]
            md.write_text(stripped, encoding="utf-8")
            self.assertNotIn("```json plan:id", md.read_text(encoding="utf-8"))
            self.assertIn("```json plan:parent", md.read_text(encoding="utf-8"))
            proc = run_plan_vet("extract", str(md))
            assert_refusal(self, proc, "plan.extract-missing", actual="id")
            self.assertNotIn("plan.extract-duplicate", proc.stderr)

    def test_prose_outside_tables_and_fences_is_not_read(self):
        with tempfile.TemporaryDirectory(prefix="plan-extract-") as tmp:
            md, sidecar = _pair(tmp)
            sidecar.unlink()
            extra = (
                md.read_text(encoding="utf-8")
                + "\n\nThis prose names id example/forged and must not be read.\n"
            )
            md.write_text(extra, encoding="utf-8")
            self.assertIn("example/forged", md.read_text(encoding="utf-8"))
            proc = run_plan_vet("extract", str(md))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            landed = load(sidecar)
            self.assertEqual(landed["id"], "example/leaf")
            self.assertNotEqual(landed["id"], "example/forged")

    def test_a_wrong_premises_header_is_refused(self):
        with tempfile.TemporaryDirectory(prefix="plan-extract-") as tmp:
            md, _sidecar = _pair(tmp)
            text = md.read_text(encoding="utf-8")
            broken = text.replace(
                "| # | premise | tag | source |",
                "| # | claim | tag | source |",
            )
            self.assertNotEqual(broken, text)
            md.write_text(broken, encoding="utf-8")
            self.assertIn("| # | claim | tag | source |", md.read_text(encoding="utf-8"))
            proc = run_plan_vet("extract", str(md))
            assert_refusal(
                self,
                proc,
                "plan.extract-header",
                expected="| # | premise | tag | source |",
                actual="| # | claim | tag | source |",
            )

    def test_extract_reads_a_non_empty_units_table(self):
        """A hard-coded units=[] is green on the leaf; the root table has a row.

        §4 header `| # | unit | deliverables | gate | needs |` vs §3
        `#Unit {id, deliverables, needs, stage}`: column `unit` -> id,
        `deliverables` -> deliverables, `needs` -> needs, `gate` -> stage.
        The done-command lives on gates[], not on the unit row. Pinning
        the mapping is how the corpus surfaces the header/field mismatch
        the empty table hid.
        """
        with tempfile.TemporaryDirectory(prefix="plan-extract-") as tmp:
            md, sidecar = _pair(
                tmp,
                md_src=EXAMPLES / "plan.root.md",
                sidecar_src=EXAMPLES / "plan.root.json",
            )
            sidecar.unlink()
            table = md.read_text(encoding="utf-8")
            self.assertIn("| # | unit | deliverables | gate | needs |", table)
            self.assertIn("| 1 | leaf |", table)
            proc = run_plan_vet("extract", str(md))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            landed = load(sidecar)
            self.assertGreater(len(landed["units"]), 0)
            unit = landed["units"][0]
            expected = load(EXAMPLES / "plan.root.json")["units"][0]
            self.assertEqual(unit["id"], "leaf")
            self.assertEqual(unit["deliverables"], expected["deliverables"])
            self.assertEqual(unit["needs"], expected["needs"])
            self.assertEqual(unit["stage"], "plan")
            self.assertEqual(unit, expected)

    def test_root_extract_check_is_quiet(self):
        with tempfile.TemporaryDirectory(prefix="plan-extract-") as tmp:
            md, _sidecar = _pair(
                tmp,
                md_src=EXAMPLES / "plan.root.md",
                sidecar_src=EXAMPLES / "plan.root.json",
            )
            proc = run_plan_vet("extract", str(md), "--check")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("plan.drift", proc.stderr)
