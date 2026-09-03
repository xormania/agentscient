"""R1-R10: each fault draws exactly its named refusal; fixture_intact.

Amendment U2-A1 retired R7 (`registry.cycle`): under `dep.layer < layer`
every cycle is already a layer violation, so a distinct cycle check is
unrepresentable. That amendment is the named reason the R7 rows are gone.
R6 remains the layer witness.

Fixture paths this suite names (not written here):
  ops/capabilities/contracts/examples/registry.json
  ops/capabilities/contracts/examples/registry.json.digest
  ops/capabilities/contracts/faults/registry.{1-6,8,9}.json
  ops/capabilities/contracts/faults/registry.{1-6,8,9}.meta.json
  ops/capabilities/contracts/faults/registry.9.json.digest
  ops/capabilities/contracts/capabilities.cue
"""

from __future__ import annotations

import copy
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import support
from support import (
    CAPABILITIES_CUE,
    META_FIELDS,
    REGISTRY_CLAIMS,
    REGISTRY_EXAMPLE,
    REGISTRY_RUNNER_CLAIMS,
    REGISTRY_VET,
    assert_not_refused,
    assert_u2_refusal,
    combined,
    digest_sidecar,
    load,
    load_named,
    prove_plant,
    registry_fault_path,
    registry_meta_path,
    require_path,
    run_registry_vet,
    stage_registry_faults,
    write_json,
)

# Amendment U2-A1: no row 7. R6 stays; cycle is a corollary of layering.
R_ROWS = {
    1: ("registry.contract", "rejection"),
    2: ("registry.absent-key", "rejection"),
    3: ("registry.duplicate-id", "rejection"),
    4: ("registry.unknown-dep", "rejection"),
    5: ("registry.unknown-iface", "rejection"),
    6: ("registry.layer", "rejection"),
    8: ("registry.serves-duplicate", "rejection"),
    9: ("registry.stale-export", "rejection"),
}


def _clean(test):
    return load_named(
        test,
        REGISTRY_EXAMPLE,
        "contracts/examples/registry.json is the two-row positive control",
    )


def _layer(doc, layer):
    matches = [cap for cap in doc["capabilities"] if cap["layer"] == layer]
    if len(matches) != 1:
        raise AssertionError(f"expected one layer-{layer} row, got {len(matches)}")
    return matches[0]


def _vet_planted(
    test,
    clean,
    planted,
    site,
    claim,
    outcome,
    *,
    exclusive=True,
    omitted_keys=(),
    expected=None,
    actual=None,
):
    prove_plant(
        clean,
        planted,
        site=site,
        exclusive=exclusive,
        omitted_keys=omitted_keys,
    )
    with tempfile.TemporaryDirectory(prefix="registry-vet-") as tmp:
        path = write_json(Path(tmp) / "registry.json", planted)
        require_path(test, REGISTRY_VET, "checks/registry_vet.py is the gate")
        proc = run_registry_vet("vet", str(path))
        assert_u2_refusal(
            test, proc, claim, outcome=outcome, expected=expected, actual=actual
        )
        return proc


class AmendmentU2A1RetiresCycle(unittest.TestCase):
    """Amendment U2-A1 F1: registry.cycle leaves #RegistryRefusals; R7 leaves the corpus."""

    def test_registry_cycle_and_r7_are_retired(self):
        self.assertNotIn("registry.cycle", REGISTRY_CLAIMS)
        self.assertNotIn(7, R_ROWS)
        self.assertEqual(
            support.COVERAGE_CARVE_OUT,
            frozenset({"registry.cue-unreachable", "anatomy.cue-unreachable"}),
        )

    def test_every_file_fixture_registry_claim_has_an_r_row(self):
        file_claims = set(REGISTRY_CLAIMS) - REGISTRY_RUNNER_CLAIMS
        self.assertEqual(file_claims, {claim for claim, _outcome in R_ROWS.values()})
        self.assertNotIn("registry.cycle", file_claims)


class RuntimeRegistryFaults(unittest.TestCase):
    """Each remaining §6.2 R-row, planted from the clean example."""

    def test_r1_extra_key_on_a_capability_element_draws_registry_contract(self):
        clean = _clean(self)
        planted = copy.deepcopy(clean)
        planted["capabilities"][0]["notes"] = "extra"
        proc = _vet_planted(
            self,
            clean,
            planted,
            ("capabilities", 0, "notes"),
            "registry.contract",
            "rejection",
        )
        text = combined(proc)
        self.assertIn("notes", text)

    def test_r1_list_element_closedness_is_also_a_cue_vet_failure(self):
        """V4: extra key inside [...#Capability] must be refused by cue itself."""
        clean = _clean(self)
        planted = copy.deepcopy(clean)
        planted["capabilities"][0]["notes"] = "extra"
        prove_plant(clean, planted, site=("capabilities", 0, "notes"))
        require_path(self, CAPABILITIES_CUE, "contracts/capabilities.cue")
        self.assertIsNotNone(
            shutil.which("cue"),
            "cue must be on PATH; a missing binary is registry.cue-unreachable, not a skip",
        )
        with tempfile.TemporaryDirectory(prefix="registry-r1-cue-") as tmp:
            path = write_json(Path(tmp) / "registry.json", planted)
            proc = subprocess.run(
                [
                    "cue",
                    "vet",
                    "-c",
                    "-d",
                    "#Registry",
                    str(CAPABILITIES_CUE),
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=support.REPO,
            )
            self.assertNotEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            text = (proc.stderr or "") + (proc.stdout or "")
            self.assertIn("notes", text)

    def test_r2_deleted_deps_key_draws_registry_absent_key(self):
        clean = _clean(self)
        planted = copy.deepcopy(clean)
        del planted["capabilities"][0]["deps"]
        _vet_planted(
            self,
            clean,
            planted,
            ("capabilities", 0, "deps"),
            "registry.absent-key",
            "rejection",
        )

    def test_r3_duplicate_id_draws_registry_duplicate_id(self):
        clean = _clean(self)
        planted = copy.deepcopy(clean)
        planted["capabilities"][1]["id"] = planted["capabilities"][0]["id"]
        _vet_planted(
            self,
            clean,
            planted,
            ("capabilities", 1, "id"),
            "registry.duplicate-id",
            "rejection",
        )

    def test_r4_dep_naming_a_missing_id_draws_registry_unknown_dep(self):
        clean = _clean(self)
        planted = copy.deepcopy(clean)
        layer1 = _layer(planted, 1)
        layer1["deps"] = [{"id": "no.such.capability", "iface": "Anything"}]
        _vet_planted(
            self,
            clean,
            planted,
            ("capabilities", planted["capabilities"].index(layer1), "deps"),
            "registry.unknown-dep",
            "rejection",
            actual="no.such.capability",
        )

    def test_r5_dep_iface_not_declared_on_the_target_draws_registry_unknown_iface(self):
        clean = _clean(self)
        planted = copy.deepcopy(clean)
        layer0 = _layer(planted, 0)
        layer1 = _layer(planted, 1)
        declared = [iface["name"] for iface in layer0["iface"]]
        self.assertTrue(declared)
        layer1["deps"] = [{"id": layer0["id"], "iface": "NotDeclared"}]
        self.assertNotIn("NotDeclared", declared)
        _vet_planted(
            self,
            clean,
            planted,
            ("capabilities", planted["capabilities"].index(layer1), "deps"),
            "registry.unknown-iface",
            "rejection",
            actual="NotDeclared",
        )

    def test_r6_layer0_depending_on_layer1_draws_registry_layer(self):
        clean = _clean(self)
        planted = copy.deepcopy(clean)
        layer0 = _layer(planted, 0)
        layer1 = _layer(planted, 1)
        iface = layer1["iface"][0]["name"]
        layer0["deps"] = [{"id": layer1["id"], "iface": iface}]
        _vet_planted(
            self,
            clean,
            planted,
            ("capabilities", planted["capabilities"].index(layer0), "deps"),
            "registry.layer",
            "rejection",
        )

    def test_r8_two_rows_serving_the_same_name_draws_registry_serves_duplicate(self):
        clean = _clean(self)
        planted = copy.deepcopy(clean)
        name = "shared.resource"
        planted["capabilities"][0]["serves"] = [name]
        planted["capabilities"][1]["serves"] = [name]
        self.assertEqual(planted["capabilities"][0]["serves"], planted["capabilities"][1]["serves"])
        self.assertNotEqual(planted, clean)
        with tempfile.TemporaryDirectory(prefix="registry-serves-") as tmp:
            path = write_json(Path(tmp) / "registry.json", planted)
            require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
            proc = run_registry_vet("vet", str(path))
            assert_u2_refusal(
                self, proc, "registry.serves-duplicate", outcome="rejection"
            )

    def test_r9_stale_digest_sidecar_draws_registry_stale_export(self):
        clean = _clean(self)
        self.assertNotIn("digest", clean)
        source_sidecar = digest_sidecar(REGISTRY_EXAMPLE)
        require_path(
            self,
            source_sidecar,
            "contracts/examples/registry.json.digest is the current sidecar",
        )
        original = source_sidecar.read_bytes()
        self.assertTrue(original, "clean digest sidecar must be non-empty")
        with tempfile.TemporaryDirectory(prefix="registry-stale-") as tmp:
            path = write_json(Path(tmp) / "registry.json", clean)
            sidecar = digest_sidecar(path)
            sidecar.write_text("0" * 64 + "\n", encoding="utf-8")
            self.assertTrue(sidecar.is_file())
            self.assertNotEqual(sidecar.read_bytes(), original)
            self.assertNotEqual(sidecar.read_bytes(), b"")
            require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
            proc = run_registry_vet("vet", str(path))
            assert_u2_refusal(self, proc, "registry.stale-export", outcome="rejection")

    def test_absent_digest_sidecar_draws_registry_stale_export(self):
        """Amendment U2-A1 F2: absence of the sidecar is a refusal, never a skip."""
        clean = _clean(self)
        self.assertNotIn("digest", clean)
        with tempfile.TemporaryDirectory(prefix="registry-no-digest-") as tmp:
            path = write_json(Path(tmp) / "registry.json", clean)
            sidecar = digest_sidecar(path)
            self.assertFalse(sidecar.exists(), "absence plant: sidecar must not be written")
            require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
            proc = run_registry_vet("vet", str(path))
            assert_u2_refusal(self, proc, "registry.stale-export", outcome="rejection")


class CommittedRegistryFaults(unittest.TestCase):
    """§6.2 corpus: plant landed against `from` at required `site`, then the named refusal."""

    R_ROWS = R_ROWS

    def _assert_planted(self, n):
        meta_path = registry_meta_path(n)
        fault_path = registry_fault_path(n)
        meta = load_named(
            self, meta_path, f"contracts/faults/registry.{n}.meta.json"
        )
        require_path(
            self, fault_path, f"contracts/faults/registry.{n}.json is R{n}"
        )
        for field in META_FIELDS:
            self.assertIn(field, meta, field)
            self.assertTrue(meta[field], field)
        source = support.CONTRACTS / meta["from"]
        require_path(self, source, f"R{n} meta.from {meta['from']}")
        clean = load(source)
        planted = load(fault_path)
        site = meta["site"]
        self.assertTrue(site, f"R{n} meta must name site")
        if list(site) == ["digest"] or site == "digest":
            sidecar = digest_sidecar(fault_path)
            source_sidecar = digest_sidecar(source)
            require_path(
                self,
                sidecar,
                f"R{n} digest sidecar is the planted stale currency",
            )
            self.assertTrue(sidecar.read_bytes(), f"R{n} digest sidecar is empty")
            if source_sidecar.is_file():
                self.assertNotEqual(
                    sidecar.read_bytes(),
                    source_sidecar.read_bytes(),
                    f"R{n} digest sidecar must differ from {meta['from']}.digest",
                )
            self.assertIsInstance(planted, dict)
            self.assertIn("capabilities", planted)
            self.assertNotIn("digest", planted)
        else:
            omitted = tuple(meta.get("omitted_keys") or ())
            prove_plant(clean, planted, site=tuple(site), omitted_keys=omitted)
        return meta, fault_path

    def test_every_committed_r_fault_plant_landed(self):
        self.assertNotIn(7, self.R_ROWS)
        for n in self.R_ROWS:
            with self.subTest(n=n):
                self._assert_planted(n)

    def test_committed_registry_faults_are_exactly_the_r_rows(self):
        self.assertNotIn(7, self.R_ROWS)
        for n in self.R_ROWS:
            require_path(
                self,
                registry_fault_path(n),
                f"contracts/faults/registry.{n}.json",
            )
        numbered = set()
        for path in support.FAULTS.glob("registry.*.json"):
            name = path.name
            if name.endswith(".digest"):
                continue
            stem = name[len("registry.") : -len(".json")]
            if stem.isdigit():
                numbered.add(int(stem))
        self.assertEqual(numbered, set(self.R_ROWS))

    def test_r1_committed_draws_registry_contract(self):
        self._assert_draws(1)

    def test_r2_committed_draws_registry_absent_key(self):
        self._assert_draws(2)

    def test_r3_committed_draws_registry_duplicate_id(self):
        self._assert_draws(3)

    def test_r4_committed_draws_registry_unknown_dep(self):
        self._assert_draws(4)

    def test_r5_committed_draws_registry_unknown_iface(self):
        self._assert_draws(5)

    def test_r6_committed_draws_registry_layer(self):
        self._assert_draws(6)

    def test_r8_committed_draws_registry_serves_duplicate(self):
        self._assert_draws(8)

    def test_r9_committed_stale_digest_draws_registry_stale_export(self):
        self._assert_draws(9)

    def _assert_draws(self, n):
        meta, fault_path = self._assert_planted(n)
        claim, outcome = self.R_ROWS[n]
        self.assertIn(claim, meta["reject_path"].replace("\\", ""))
        require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
        proc = run_registry_vet("vet", str(fault_path))
        assert_u2_refusal(self, proc, claim, outcome=outcome)


class FaultsSubcommand(unittest.TestCase):
    """§3.4 layer 1 / W4: faults covers #RegistryRefusals; R10 is deletion."""

    def test_faults_is_quiet_when_every_enumerated_refusal_has_a_firing_fixture(self):
        for n in R_ROWS:
            require_path(
                self,
                registry_fault_path(n),
                f"contracts/faults/registry.{n}.json",
            )
            require_path(
                self,
                registry_meta_path(n),
                f"contracts/faults/registry.{n}.meta.json",
            )
        require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
        proc = run_registry_vet("faults")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        assert_not_refused(self, proc, "registry.undemonstrated")

    def test_r10_deleting_r4_draws_registry_undemonstrated(self):
        with tempfile.TemporaryDirectory(prefix="registry-faults-r10-") as tmp:
            root = stage_registry_faults(self, Path(tmp) / "faults", R_ROWS)
            target = root / "registry.4.json"
            self.assertTrue(target.is_file())
            original = target.read_bytes()
            self.assertTrue(original, "R4 fixture was empty before deletion")
            target.unlink()
            self.assertFalse(target.is_file(), "R10 plant: scratch R4 must be gone")
            self.assertTrue(
                (root / "registry.3.json").is_file(),
                "deleting R4 must leave the rest of the scratch corpus recognisable",
            )
            self.assertTrue(
                registry_fault_path(4).is_file(),
                "the committed R4 fixture must be untouched",
            )
            require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
            proc = run_registry_vet("faults", str(root))
            assert_u2_refusal(self, proc, "registry.undemonstrated", outcome="finding")

    def test_deleting_r9_is_undemonstrated_not_carved_out(self):
        """Nothing else may join the two-name carve-out (U2-A1 F3)."""
        with tempfile.TemporaryDirectory(prefix="registry-faults-r9-") as tmp:
            root = stage_registry_faults(self, Path(tmp) / "faults", R_ROWS)
            target = root / "registry.9.json"
            self.assertTrue(target.is_file())
            target.unlink()
            self.assertFalse(target.is_file())
            self.assertTrue(registry_fault_path(9).is_file())
            require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
            proc = run_registry_vet("faults", str(root))
            assert_u2_refusal(
                self,
                proc,
                "registry.undemonstrated",
                outcome="finding",
                actual="registry.stale-export",
            )

    def test_faults_fires_fault_intact_when_a_fault_matches_the_clean_example(self):
        require_path(
            self, REGISTRY_EXAMPLE, "contracts/examples/registry.json"
        )
        with tempfile.TemporaryDirectory(prefix="registry-faults-intact-") as tmp:
            root = stage_registry_faults(self, Path(tmp) / "faults", R_ROWS)
            target = root / "registry.1.json"
            original = target.read_bytes()
            target.write_bytes(REGISTRY_EXAMPLE.read_bytes())
            self.assertEqual(target.read_bytes(), REGISTRY_EXAMPLE.read_bytes())
            self.assertNotEqual(target.read_bytes(), original)
            self.assertNotEqual(
                registry_fault_path(1).read_bytes(),
                target.read_bytes(),
                "the committed R1 fixture must be untouched",
            )
            require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
            proc = run_registry_vet("faults", str(root))
            assert_u2_refusal(self, proc, "registry.fault-intact", outcome="finding")

    def test_faults_fires_fault_mismatch_when_a_fault_draws_the_wrong_name(self):
        with tempfile.TemporaryDirectory(prefix="registry-faults-mismatch-") as tmp:
            root = stage_registry_faults(self, Path(tmp) / "faults", R_ROWS)
            r1 = root / "registry.1.json"
            r3 = root / "registry.3.json"
            r1_meta = load(root / "registry.1.meta.json")
            self.assertIn("contract", r1_meta["reject_path"])
            original = r1.read_bytes()
            r1.write_bytes(r3.read_bytes())
            self.assertEqual(r1.read_bytes(), r3.read_bytes())
            self.assertNotEqual(r1.read_bytes(), original)
            self.assertNotEqual(r1.read_bytes(), REGISTRY_EXAMPLE.read_bytes())
            self.assertNotEqual(
                registry_fault_path(1).read_bytes(),
                r1.read_bytes(),
                "the committed R1 fixture must be untouched",
            )
            require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
            proc = run_registry_vet("faults", str(root))
            assert_u2_refusal(self, proc, "registry.fault-mismatch", outcome="finding")
