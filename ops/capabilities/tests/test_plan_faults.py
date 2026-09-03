"""The §5 fault corpus: each plant draws exactly its named refusal."""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

import support
from support import (
    EXAMPLES,
    FAULTS,
    PLAN_CUE,
    assert_refusal,
    dump,
    load,
    prove_plant,
    run_plan_vet,
    skip_without_cue,
)


def _meta(n):
    return load(FAULTS / f"plan.{n}.meta.json")


def _fault_path(n):
    return FAULTS / f"plan.{n}.json"


def _from_path(n):
    rel = _meta(n)["from"]
    return support.CONTRACTS / rel


class ProvePlant(unittest.TestCase):
    """The harness itself catches a moved-anchor plant."""

    def test_a_plant_at_the_wrong_site_is_rejected(self):
        clean = load(EXAMPLES / "plan.json")
        planted = dict(clean)
        discharge = dict(clean["discharge"])
        discharge["design_to"] = "docs/elsewhere.md"
        planted["discharge"] = discharge
        self.assertNotEqual(planted, clean)
        with self.assertRaises(AssertionError) as raised:
            prove_plant(clean, planted, site=("deliverables", 0, "path"))
        self.assertIn("named site", str(raised.exception))

    def test_a_plant_at_the_named_site_is_accepted(self):
        clean = load(EXAMPLES / "plan.json")
        planted = dict(clean)
        deliverables = [dict(clean["deliverables"][0])]
        deliverables[0]["path"] = "contracts/other.cue"
        planted["deliverables"] = deliverables
        prove_plant(clean, planted, site=("deliverables", 0, "path"))


class FaultCorpus(unittest.TestCase):
    """Eighteen committed faults, one refusal each."""

    def _assert_planted(self, n):
        meta = _meta(n)
        clean = load(_from_path(n))
        planted = load(_fault_path(n))
        omitted = tuple(meta.get("omitted_keys") or ())
        if n == 18:
            clean_bytes = _from_path(n).read_bytes()
            planted_bytes = _fault_path(n).read_bytes()
            self.assertNotEqual(
                planted_bytes, clean_bytes, "fault 18 is a byte-order plant"
            )
            self.assertEqual(
                json.loads(planted_bytes),
                json.loads(clean_bytes),
                "fault 18 must remain the same document",
            )
            return meta
        site = meta.get("site")
        self.assertTrue(site, f"fault {n} meta must name site")
        prove_plant(clean, planted, omitted_keys=omitted, site=tuple(site))
        return meta

    def _assert_draws(self, n, *, needs_cue=True):
        meta = self._assert_planted(n)
        if needs_cue:
            skip_without_cue()
        proc = run_plan_vet("vet", str(_fault_path(n)))
        pattern = re.compile(meta["reject_path"])
        self.assertRegex(
            proc.stderr,
            pattern,
            f"fault {n} must draw {meta['reject_path']}; stderr was {proc.stderr!r}",
        )
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        claim = meta["reject_path"].replace("\\", "")
        assert_refusal(self, proc, claim)

    def test_every_fault_plant_landed_at_its_named_site(self):
        for n in range(1, 19):
            with self.subTest(n=n):
                self._assert_planted(n)

    def test_fault_01_stale_parent(self):
        self._assert_draws(1)

    def test_fault_02_deliverables_mismatch(self):
        self._assert_draws(2)

    def test_fault_03_reopened(self):
        self._assert_draws(3)

    def test_fault_04_undelegated(self):
        self._assert_draws(4)

    def test_fault_05_gate_half(self):
        self._assert_draws(5)

    def test_fault_06_premise_tag(self):
        self._assert_draws(6)

    def test_fault_07_root_parent(self):
        self._assert_draws(7, needs_cue=False)

    def test_fault_08_leaf_open(self):
        self._assert_draws(8)

    def test_fault_09_premise_empty(self):
        self._assert_draws(9)

    def test_fault_10_scope_drift(self):
        self._assert_draws(10)

    def test_fault_11_gate_cost_absent(self):
        self._assert_draws(11)

    def test_fault_12_boundary_without_boundary_at(self):
        self._assert_draws(12)

    def test_fault_13_decision_not_new(self):
        self._assert_draws(13)

    def test_fault_14_decision_unratified(self):
        self._assert_draws(14)

    def test_fault_15_derived_key(self):
        self._assert_draws(15, needs_cue=False)

    def test_fault_16_bound_prose(self):
        self._assert_draws(16)

    def test_fault_17_absent_key(self):
        self._assert_draws(17, needs_cue=False)

    def test_fault_18_drift(self):
        self._assert_draws(18)

    def test_fault_18_extract_check_draws_drift_without_cue(self):
        """Drift is extract --check of a key-reordered sidecar; no cue."""
        self._assert_planted(18)
        with __import__("tempfile").TemporaryDirectory(prefix="plan-drift-") as tmp:
            root = Path(tmp)
            md = root / "leaf.plan.md"
            sidecar = root / "leaf.plan.json"
            md.write_bytes((FAULTS / "plan.18.md").read_bytes())
            sidecar.write_bytes((FAULTS / "plan.18.json").read_bytes())
            proc = run_plan_vet("extract", str(md), "--check")
            assert_refusal(self, proc, "plan.drift")

    def test_fault_17_passes_cue_vet_c_with_the_named_definition(self):
        """After-action 5d87918: CUE cannot see an omitted key; the raw check must.

        `-d '#Plan'` is load-bearing: without it cue unifies the JSON with
        the package top level and exits 0 for any document.
        """
        skip_without_cue()
        self._assert_planted(17)
        self.assertTrue(
            PLAN_CUE.is_file(),
            "plan.cue is the contract cue vet -c runs against",
        )
        proc = subprocess.run(
            [
                "cue",
                "vet",
                "-c",
                "-d",
                "#Plan",
                str(PLAN_CUE),
                str(_fault_path(17)),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=support.REPO,
        )
        self.assertEqual(
            proc.returncode,
            0,
            "omitting units must pass cue vet -c -d '#Plan'; "
            f"stderr={proc.stderr!r}",
        )


class FaultsSubcommand(unittest.TestCase):
    """`plan vet faults` runs the corpus and is quiet only when all 18 fire."""

    def test_faults_is_quiet_when_every_fault_draws_its_refusal(self):
        skip_without_cue()
        numbered = list(range(1, 19))
        for n in numbered:
            self.assertTrue(
                _fault_path(n).is_file(), f"missing fault file plan.{n}.json"
            )
            self.assertTrue(
                (FAULTS / f"plan.{n}.meta.json").is_file(),
                f"missing sidecar plan.{n}.meta.json",
            )
        required = (
            "contract",
            "fault",
            "from",
            "change",
            "violates",
            "reject_path",
            "site",
        )
        for n in numbered:
            meta = _meta(n)
            for field in required:
                if n == 18 and field == "site":
                    self.assertIn("change", meta)
                    continue
                self.assertIn(field, meta, field)
                self.assertTrue(meta[field], field)
            self.assertEqual(meta["contract"], "plan")
            self.assertEqual(meta["fault"], f"plan.{n}.json")
        proc = run_plan_vet("faults")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_faults_fires_when_a_fault_matches_the_example(self):
        self.assertTrue(support.PLAN_VET.is_file(), support.PLAN_VET)
        target = _fault_path(1)
        original = target.read_bytes()
        self.addCleanup(target.write_bytes, original)
        target.write_bytes((EXAMPLES / "plan.json").read_bytes())
        self.assertEqual(target.read_bytes(), (EXAMPLES / "plan.json").read_bytes())
        proc = run_plan_vet("faults")
        self.assertNotEqual(proc.returncode, 0, proc.stderr)

    def test_faults_fires_when_a_fault_vets_clean(self):
        skip_without_cue()
        self.assertTrue(support.PLAN_VET.is_file(), support.PLAN_VET)
        target = _fault_path(2)
        original = target.read_bytes()
        self.addCleanup(target.write_bytes, original)
        target.write_bytes((EXAMPLES / "plan.new-false.json").read_bytes())
        self.assertNotEqual(target.read_bytes(), original)
        self.assertNotEqual(
            json.loads(target.read_bytes()),
            json.loads((EXAMPLES / "plan.json").read_bytes()),
        )
        proc = run_plan_vet("faults")
        self.assertNotEqual(proc.returncode, 0, proc.stderr)

    def test_faults_fires_when_a_fault_misses_its_reject_path(self):
        skip_without_cue()
        self.assertTrue(support.PLAN_VET.is_file(), support.PLAN_VET)
        meta_path = FAULTS / "plan.1.meta.json"
        original = meta_path.read_bytes()
        self.addCleanup(meta_path.write_bytes, original)
        meta = load(meta_path)
        meta["reject_path"] = "plan\\.nope"
        meta_path.write_text(dump(meta), encoding="utf-8")
        self.assertEqual(load(meta_path)["reject_path"], "plan\\.nope")
        self.assertNotEqual(meta_path.read_bytes(), original)
        proc = run_plan_vet("faults")
        self.assertNotEqual(proc.returncode, 0, proc.stderr)


class PositiveControls(unittest.TestCase):
    """A negative control with no positive beside it proved nothing."""

    def _vet_clean(self, path: Path):
        skip_without_cue()
        self.assertTrue(path.is_file(), path)
        proc = run_plan_vet("vet", str(path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("refused:", proc.stderr)

    def test_the_clean_leaf_vets(self):
        self._vet_clean(EXAMPLES / "plan.json")

    def test_the_clean_root_vets(self):
        self._vet_clean(EXAMPLES / "plan.root.json")

    def test_new_false_with_parent_premises_vets(self):
        self._vet_clean(EXAMPLES / "plan.new-false.json")

    def test_boundary_gate_with_boundary_at_vets(self):
        self._vet_clean(EXAMPLES / "plan.boundary.json")

    def test_a_superseded_decision_vets(self):
        self._vet_clean(EXAMPLES / "plan.superseded.json")

    def test_scope_that_appends_a_dated_ruling_vets(self):
        self._vet_clean(EXAMPLES / "plan.scope-append.json")

    def test_a_design_decision_ratified_by_conductor_vets(self):
        self._vet_clean(EXAMPLES / "plan.conductor.json")

    def test_owner_ratified_standing_at_stage_code_vets(self):
        self._vet_clean(EXAMPLES / "plan.stage-code.json")
