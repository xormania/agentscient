"""A1-A11: each fault draws exactly its named refusal; fixture_intact.

Amendment U2-A1: A7's committed variant is `anatomy.migrates-empty`
(migrations/ holding only `.gitkeep`); A10 is `anatomy.iface-unresolved`;
A11 is `anatomy.refusals-disagree`. Member plants target the last of
≥2 ifaces.

Fixture paths this suite names (not written here):
  ops/capabilities/contracts/examples/anatomy/goodcap/
  ops/capabilities/contracts/faults/anatomy.{1..11}/
  ops/capabilities/contracts/faults/anatomy.{1..11}.meta.json
  ops/capabilities/contracts/capability.cue
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import support
from support import (
    ANATOMY_CLAIMS,
    ANATOMY_PY,
    ANATOMY_RUNNER_CLAIMS,
    CAPABILITY_CUE,
    GOODCAP,
    META_FIELDS,
    assert_u2_refusal,
    combined,
    goodcap_module,
    insert_protocol_body,
    last_declared_iface,
    load,
    load_named,
    prove_dir_plant,
    prove_dir_site,
    prove_protocol_members,
    rel_files,
    require_path,
    run_anatomy,
    stage_anatomy_faults,
    write_json,
)

A_ROWS = {
    1: ("anatomy.missing", "rejection"),
    2: ("anatomy.extra", "rejection"),
    3: ("anatomy.member-missing", "rejection"),
    4: ("anatomy.member-undeclared", "rejection"),
    5: ("anatomy.manifest", "rejection"),
    6: ("anatomy.manifest", "rejection"),
    7: ("anatomy.migrates-empty", "rejection"),
    8: ("anatomy.undemonstrated", "finding"),
    9: ("anatomy.unparsed", "finding"),
    10: ("anatomy.iface-unresolved", "rejection"),
    11: ("anatomy.refusals-disagree", "rejection"),
}


def _stage_goodcap(tmp):
    dest = Path(tmp) / "goodcap"
    shutil.copytree(GOODCAP, dest)
    return dest


def _vet_dir(test, planted, claim, outcome, **kwargs):
    require_path(test, ANATOMY_PY, "checks/anatomy.py is the gate")
    proc = run_anatomy("vet", str(planted))
    assert_u2_refusal(test, proc, claim, outcome=outcome, **kwargs)
    return proc


def _migrations_files(root):
    return sorted(
        name
        for name in rel_files(root)
        if name == "migrations" or name.startswith("migrations/")
    )


def _faults_files(root):
    return sorted(
        name
        for name in rel_files(root)
        if name == "faults" or name.startswith("faults/")
    )


class AmendmentU2A1AnatomyRows(unittest.TestCase):
    """Coverage set, new A-rows, A7 claim change."""

    def test_coverage_carve_out_is_exactly_the_two_cue_unreachable_names(self):
        self.assertEqual(
            support.COVERAGE_CARVE_OUT,
            frozenset({"registry.cue-unreachable", "anatomy.cue-unreachable"}),
        )
        file_claims = set(ANATOMY_CLAIMS) - ANATOMY_RUNNER_CLAIMS
        self.assertEqual(file_claims, {claim for claim, _outcome in A_ROWS.values()})
        self.assertIn("anatomy.iface-unresolved", file_claims)
        self.assertIn("anatomy.refusals-disagree", file_claims)
        self.assertIn("anatomy.migrates-empty", file_claims)


class RuntimeAnatomyFaults(unittest.TestCase):
    """Each §6.2 A-row, planted from goodcap."""

    def test_a1_removing_faults_dir_draws_anatomy_missing(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a1-") as tmp:
            planted = _stage_goodcap(tmp)
            shutil.rmtree(planted / "faults")
            self.assertFalse((planted / "faults").exists())
            self.assertTrue((planted / "capability.json").is_file())
            removed = _faults_files(GOODCAP)
            self.assertTrue(removed, "goodcap must ship faults/ files to delete")
            prove_dir_plant(GOODCAP, planted, removed=removed)
            _vet_dir(self, planted, "anatomy.missing", "rejection")

    def test_a2_extra_notes_md_draws_anatomy_extra(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a2-") as tmp:
            planted = _stage_goodcap(tmp)
            extra = planted / "notes.md"
            extra.write_text("not in #Anatomy\n", encoding="utf-8")
            self.assertTrue(extra.is_file())
            prove_dir_plant(GOODCAP, planted, added=("notes.md",))
            _vet_dir(self, planted, "anatomy.extra", "rejection")

    def test_a3_manifest_member_absent_from_protocol_draws_anatomy_member_missing(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a3-") as tmp:
            planted = _stage_goodcap(tmp)
            manifest_path = planted / "capability.json"
            manifest = load(manifest_path)
            iface, idx = last_declared_iface(self, manifest)
            members = list(iface["members"])
            self.assertNotIn("close", members)
            members.append("close")
            iface = dict(iface)
            iface["members"] = members
            ifaces = list(manifest["iface"])
            ifaces[idx] = iface
            planted_manifest = dict(manifest)
            planted_manifest["iface"] = ifaces
            write_json(manifest_path, planted_manifest)
            support.prove_plant(
                manifest,
                planted_manifest,
                site=("iface", idx, "members"),
            )
            prove_dir_plant(
                GOODCAP, planted, changed=("capability.json",)
            )
            _vet_dir(
                self,
                planted,
                "anatomy.member-missing",
                "rejection",
                actual="close",
            )

    def test_a4_protocol_method_not_in_manifest_draws_anatomy_member_undeclared(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a4-") as tmp:
            planted = _stage_goodcap(tmp)
            module, manifest = goodcap_module(self, planted)
            declared = set()
            for iface in manifest["iface"]:
                declared.update(iface["members"])
            self.assertNotIn("drop", declared)
            iface, _idx = last_declared_iface(self, manifest)
            name = iface["name"]
            original = module.read_text(encoding="utf-8")
            rewritten = insert_protocol_body(
                original, name, ["def drop(self): ..."], members=("drop",)
            )
            module.write_text(rewritten, encoding="utf-8")
            prove_protocol_members(module.read_text(encoding="utf-8"), name, "drop")
            self.assertNotEqual(module.read_bytes(), original.encode("utf-8"))
            prove_dir_plant(
                GOODCAP,
                planted,
                changed=(str(module.relative_to(planted)).replace("\\", "/"),),
            )
            _vet_dir(
                self,
                planted,
                "anatomy.member-undeclared",
                "rejection",
                actual="drop",
            )

    def test_a4_annotated_attribute_not_in_manifest_draws_anatomy_member_undeclared(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a4attr-") as tmp:
            planted = _stage_goodcap(tmp)
            module, manifest = goodcap_module(self, planted)
            declared = set()
            for iface in manifest["iface"]:
                declared.update(iface["members"])
            self.assertNotIn("closed", declared)
            iface, _idx = last_declared_iface(self, manifest)
            name = iface["name"]
            original = module.read_text(encoding="utf-8")
            rewritten = insert_protocol_body(
                original, name, ["closed: bool"], members=("closed",)
            )
            module.write_text(rewritten, encoding="utf-8")
            prove_protocol_members(module.read_text(encoding="utf-8"), name, "closed")
            prove_dir_plant(
                GOODCAP,
                planted,
                changed=(str(module.relative_to(planted)).replace("\\", "/"),),
            )
            _vet_dir(
                self,
                planted,
                "anatomy.member-undeclared",
                "rejection",
                actual="closed",
            )

    def test_a5_refusal_row_without_remedy_draws_anatomy_manifest(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a5-") as tmp:
            planted = _stage_goodcap(tmp)
            manifest_path = planted / "capability.json"
            manifest = load(manifest_path)
            self.assertTrue(manifest["refusals"])
            row = dict(manifest["refusals"][0])
            self.assertIn("remedy", row)
            del row["remedy"]
            refusals = list(manifest["refusals"])
            refusals[0] = row
            planted_manifest = dict(manifest)
            planted_manifest["refusals"] = refusals
            write_json(manifest_path, planted_manifest)
            support.prove_plant(
                manifest, planted_manifest, site=("refusals", 0, "remedy")
            )
            prove_dir_plant(GOODCAP, planted, changed=("capability.json",))
            proc = _vet_dir(self, planted, "anatomy.manifest", "rejection")
            self.assertIn("remedy", combined(proc))

    def test_a6_refusal_class_error_draws_anatomy_manifest(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a6-") as tmp:
            planted = _stage_goodcap(tmp)
            manifest_path = planted / "capability.json"
            manifest = load(manifest_path)
            row = dict(manifest["refusals"][0])
            row["class"] = "error"
            refusals = list(manifest["refusals"])
            refusals[0] = row
            planted_manifest = dict(manifest)
            planted_manifest["refusals"] = refusals
            write_json(manifest_path, planted_manifest)
            support.prove_plant(
                manifest, planted_manifest, site=("refusals", 0, "class")
            )
            prove_dir_plant(GOODCAP, planted, changed=("capability.json",))
            proc = _vet_dir(self, planted, "anatomy.manifest", "rejection")
            self.assertIn("error", combined(proc))

    def test_a7_migrates_tagged_migrations_absent_draws_anatomy_missing(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a7-") as tmp:
            planted = _stage_goodcap(tmp)
            shutil.rmtree(planted / "migrations")
            self.assertFalse((planted / "migrations").exists())
            removed = _migrations_files(GOODCAP)
            self.assertTrue(removed, "goodcap must ship migrations/ files to delete")
            prove_dir_plant(GOODCAP, planted, removed=removed)
            _vet_dir(self, planted, "anatomy.missing", "rejection")

    def test_a7_empty_migrations_dir_draws_anatomy_migrates_empty(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a7empty-") as tmp:
            planted = _stage_goodcap(tmp)
            migrations = planted / "migrations"
            self.assertTrue(migrations.is_dir())
            removed = sorted(
                name
                for name in rel_files(GOODCAP)
                if name.startswith("migrations/") and name != "migrations/.gitkeep"
            )
            self.assertTrue(
                removed,
                "goodcap migrations/ must hold a migration entry besides .gitkeep",
            )
            for child in list(migrations.iterdir()):
                if child.name == ".gitkeep":
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            gitkeep = migrations / ".gitkeep"
            added = ()
            if not gitkeep.is_file():
                gitkeep.write_text("", encoding="utf-8")
                added = ("migrations/.gitkeep",)
            self.assertTrue(gitkeep.is_file())
            self.assertEqual(
                sorted(p.name for p in migrations.iterdir()),
                [".gitkeep"],
            )
            prove_dir_plant(GOODCAP, planted, removed=removed, added=added)
            _vet_dir(self, planted, "anatomy.migrates-empty", "rejection")

    def test_a8_declared_refusal_without_a_faults_fixture_draws_undemonstrated(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a8-") as tmp:
            planted = _stage_goodcap(tmp)
            faults = planted / "faults"
            self.assertTrue(faults.is_dir())
            removed = sorted(
                name
                for name in rel_files(GOODCAP)
                if name.startswith("faults/")
            )
            self.assertTrue(removed, "goodcap faults/ must hold fixtures to delete")
            for name in removed:
                path = planted / name
                if path.is_file():
                    path.unlink()
            self.assertTrue(faults.is_dir())
            self.assertFalse(any(p.is_file() for p in faults.rglob("*")))
            prove_dir_plant(GOODCAP, planted, removed=removed)
            _vet_dir(self, planted, "anatomy.undemonstrated", "finding")

    def test_a9_unparseable_module_draws_anatomy_unparsed_as_finding(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a9-") as tmp:
            planted = _stage_goodcap(tmp)
            module, _manifest = goodcap_module(self, planted)
            original = module.read_bytes()
            module.write_text("def oops(\n", encoding="utf-8")
            self.assertNotEqual(module.read_bytes(), original)
            self.assertTrue(original, "module was recognisable before the plant")
            prove_dir_plant(
                GOODCAP,
                planted,
                changed=(str(module.relative_to(planted)).replace("\\", "/"),),
            )
            proc = _vet_dir(self, planted, "anatomy.unparsed", "finding")
            self.assertNotIn("skipped", combined(proc).lower())

    def test_a10_declared_iface_whose_protocol_is_absent_draws_iface_unresolved(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a10-") as tmp:
            planted = _stage_goodcap(tmp)
            manifest_path = planted / "capability.json"
            manifest = load(manifest_path)
            last_declared_iface(self, manifest)
            module, _loaded = goodcap_module(self, planted)
            tree = ast.parse(module.read_text(encoding="utf-8"))
            class_names = [
                node.name for node in tree.body if isinstance(node, ast.ClassDef)
            ]
            self.assertTrue(class_names, "goodcap module must declare Protocol classes")
            self.assertNotIn("NotInModule", class_names)
            extra = {"name": "NotInModule", "members": ["ping"]}
            ifaces = list(manifest["iface"]) + [extra]
            planted_manifest = dict(manifest)
            planted_manifest["iface"] = ifaces
            write_json(manifest_path, planted_manifest)
            support.prove_plant(
                manifest, planted_manifest, site=("iface", len(ifaces) - 1)
            )
            prove_dir_plant(GOODCAP, planted, changed=("capability.json",))
            _vet_dir(
                self,
                planted,
                "anatomy.iface-unresolved",
                "rejection",
                actual="NotInModule",
            )

    def test_a11_extra_manifest_refusal_draws_anatomy_refusals_disagree(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a11-") as tmp:
            planted = _stage_goodcap(tmp)
            manifest_path = planted / "capability.json"
            manifest = load(manifest_path)
            self.assertTrue(manifest["refusals"])
            extra = {
                "name": "goodcap.planted-disagree",
                "class": "rejection",
                "remedy": "drop the planted row",
            }
            refusals = list(manifest["refusals"]) + [extra]
            planted_manifest = dict(manifest)
            planted_manifest["refusals"] = refusals
            write_json(manifest_path, planted_manifest)
            support.prove_plant(
                manifest, planted_manifest, site=("refusals", len(refusals) - 1)
            )
            prove_dir_plant(GOODCAP, planted, changed=("capability.json",))
            _vet_dir(self, planted, "anatomy.refusals-disagree", "rejection")

    def test_a11_contract_md_disagrees_with_the_manifest(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a11-md-") as tmp:
            planted = _stage_goodcap(tmp)
            manifest = load(planted / "capability.json")
            self.assertTrue(manifest["refusals"])
            name = manifest["refusals"][0]["name"]
            md = planted / "CONTRACT.md"
            original = md.read_text(encoding="utf-8")
            self.assertIn(name, original)
            replacement = "goodcap.md-disagree"
            self.assertNotEqual(replacement, name)
            idx = original.index(name)
            planted_text = original[:idx] + replacement + original[idx + len(name) :]
            self.assertNotEqual(planted_text, original)
            self.assertIn(replacement, planted_text)
            md.write_text(planted_text, encoding="utf-8")
            prove_dir_plant(GOODCAP, planted, changed=("CONTRACT.md",))
            _vet_dir(self, planted, "anatomy.refusals-disagree", "rejection")

    def test_a11_contract_cue_disagrees_with_the_manifest(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-a11-cue-") as tmp:
            planted = _stage_goodcap(tmp)
            manifest = load(planted / "capability.json")
            self.assertTrue(manifest["refusals"])
            name = manifest["refusals"][0]["name"]
            cue = planted / "contract.cue"
            original = cue.read_text(encoding="utf-8")
            self.assertIn(name, original)
            replacement = "goodcap.cue-disagree"
            self.assertNotEqual(replacement, name)
            idx = original.index(name)
            planted_text = original[:idx] + replacement + original[idx + len(name) :]
            self.assertNotEqual(planted_text, original)
            self.assertIn(replacement, planted_text)
            cue.write_text(planted_text, encoding="utf-8")
            prove_dir_plant(GOODCAP, planted, changed=("contract.cue",))
            _vet_dir(self, planted, "anatomy.refusals-disagree", "rejection")


class CueLevelManifestFaults(unittest.TestCase):
    """W1: A5/A6 are cue-level #Refusal faults on #Manifest."""

    def test_a5_cue_vet_names_the_missing_remedy_path(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        require_path(self, CAPABILITY_CUE, "contracts/capability.cue")
        with tempfile.TemporaryDirectory(prefix="anatomy-a5-cue-") as tmp:
            planted = _stage_goodcap(tmp)
            manifest_path = planted / "capability.json"
            manifest = load(manifest_path)
            row = dict(manifest["refusals"][0])
            del row["remedy"]
            refusals = list(manifest["refusals"])
            refusals[0] = row
            planted_manifest = dict(manifest)
            planted_manifest["refusals"] = refusals
            write_json(manifest_path, planted_manifest)
            self.assertIsNotNone(
                shutil.which("cue"),
                "cue must be on PATH; a missing binary is anatomy.cue-unreachable, not a skip",
            )
            proc = subprocess.run(
                [
                    "cue",
                    "vet",
                    "-c",
                    "-d",
                    "#Manifest",
                    str(CAPABILITY_CUE),
                    str(manifest_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=support.REPO,
            )
            self.assertNotEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            text = (proc.stderr or "") + (proc.stdout or "")
            self.assertIn("remedy", text)

    def test_a6_cue_vet_names_the_illegal_class(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        require_path(self, CAPABILITY_CUE, "contracts/capability.cue")
        with tempfile.TemporaryDirectory(prefix="anatomy-a6-cue-") as tmp:
            planted = _stage_goodcap(tmp)
            manifest_path = planted / "capability.json"
            manifest = load(manifest_path)
            row = dict(manifest["refusals"][0])
            row["class"] = "error"
            refusals = list(manifest["refusals"])
            refusals[0] = row
            planted_manifest = dict(manifest)
            planted_manifest["refusals"] = refusals
            write_json(manifest_path, planted_manifest)
            self.assertIsNotNone(
                shutil.which("cue"),
                "cue must be on PATH; a missing binary is anatomy.cue-unreachable, not a skip",
            )
            proc = subprocess.run(
                [
                    "cue",
                    "vet",
                    "-c",
                    "-d",
                    "#Manifest",
                    str(CAPABILITY_CUE),
                    str(manifest_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=support.REPO,
            )
            self.assertNotEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            text = (proc.stderr or "") + (proc.stdout or "")
            self.assertIn("error", text)


class CommittedAnatomyFaults(unittest.TestCase):
    """§6.2 corpus directories + meta sidecars; site is required (U2-A1 F4)."""

    A_ROWS = A_ROWS

    def _assert_planted(self, n):
        meta_path = support.anatomy_meta_path(n)
        fault_dir = support.anatomy_fault_dir(n)
        meta = load_named(
            self, meta_path, f"contracts/faults/anatomy.{n}.meta.json"
        )
        require_path(
            self,
            fault_dir,
            f"contracts/faults/anatomy.{n}/ is A{n}",
            kind="dir",
        )
        for field in META_FIELDS:
            self.assertIn(field, meta, field)
            self.assertTrue(meta[field], field)
        source = support.CONTRACTS / meta["from"]
        require_path(
            self, source, f"A{n} meta.from {meta['from']}", kind="dir"
        )
        site = meta["site"]
        self.assertTrue(site, f"A{n} meta must name site")
        prove_dir_site(source, fault_dir, site)
        return meta, fault_dir

    def test_every_committed_a_fault_plant_landed(self):
        for n in self.A_ROWS:
            with self.subTest(n=n):
                self._assert_planted(n)

    def test_committed_anatomy_faults_are_exactly_the_a_rows(self):
        for n in self.A_ROWS:
            require_path(
                self,
                support.anatomy_fault_dir(n),
                f"contracts/faults/anatomy.{n}/",
                kind="dir",
            )
        numbered = set()
        for path in support.FAULTS.glob("anatomy.*"):
            if path.suffix == ".json" and path.name.endswith(".meta.json"):
                continue
            if path.is_dir() and path.name.startswith("anatomy."):
                stem = path.name[len("anatomy.") :]
                if stem.isdigit():
                    numbered.add(int(stem))
        self.assertEqual(numbered, set(self.A_ROWS))

    def test_a1_committed_draws_anatomy_missing(self):
        self._assert_draws(1)

    def test_a2_committed_draws_anatomy_extra(self):
        self._assert_draws(2)

    def test_a3_committed_draws_anatomy_member_missing(self):
        self._assert_draws(3)

    def test_a4_committed_draws_anatomy_member_undeclared(self):
        self._assert_draws(4)

    def test_a5_committed_draws_anatomy_manifest(self):
        self._assert_draws(5)

    def test_a6_committed_draws_anatomy_manifest(self):
        self._assert_draws(6)

    def test_a7_committed_draws_anatomy_migrates_empty(self):
        self._assert_draws(7)

    def test_a8_committed_draws_anatomy_undemonstrated(self):
        self._assert_draws(8)

    def test_a9_committed_draws_anatomy_unparsed(self):
        self._assert_draws(9)

    def test_a10_committed_draws_anatomy_iface_unresolved(self):
        self._assert_draws(10)

    def test_a11_committed_draws_anatomy_refusals_disagree(self):
        self._assert_draws(11)

    def _assert_draws(self, n):
        meta, fault_dir = self._assert_planted(n)
        claim, outcome = self.A_ROWS[n]
        self.assertIn(claim, meta["reject_path"].replace("\\", ""))
        _vet_dir(self, fault_dir, claim, outcome)


class FaultsSubcommand(unittest.TestCase):
    """§3.4 layer 1 / W5: faults covers #AnatomyRefusals; mutations are scratch-only."""

    def test_faults_is_quiet_when_every_enumerated_refusal_has_a_firing_fixture(self):
        for n in A_ROWS:
            require_path(
                self,
                support.anatomy_fault_dir(n),
                f"contracts/faults/anatomy.{n}/",
                kind="dir",
            )
            require_path(
                self,
                support.anatomy_meta_path(n),
                f"contracts/faults/anatomy.{n}.meta.json",
            )
        require_path(self, ANATOMY_PY, "checks/anatomy.py is the gate")
        proc = run_anatomy("faults")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        support.assert_not_refused(self, proc, "anatomy.undemonstrated")

    def test_deleting_a3_draws_anatomy_undemonstrated(self):
        with tempfile.TemporaryDirectory(prefix="anatomy-faults-a3-") as tmp:
            root = stage_anatomy_faults(self, Path(tmp) / "faults", A_ROWS)
            target = root / "anatomy.3"
            self.assertTrue(target.is_dir())
            shutil.rmtree(target)
            self.assertFalse(target.exists())
            self.assertTrue(
                (root / "anatomy.4").is_dir(),
                "deleting A3 must leave the rest of the scratch corpus recognisable",
            )
            self.assertTrue(
                support.anatomy_fault_dir(3).is_dir(),
                "the committed A3 fixture must be untouched",
            )
            require_path(self, ANATOMY_PY, "checks/anatomy.py is the gate")
            proc = run_anatomy("faults", str(root))
            assert_u2_refusal(self, proc, "anatomy.undemonstrated", outcome="finding")

    def test_deleting_a7_is_undemonstrated_not_carved_out(self):
        """migrates-empty is a committed file-fixture subject, not a carve-out."""
        with tempfile.TemporaryDirectory(prefix="anatomy-faults-a7-") as tmp:
            root = stage_anatomy_faults(self, Path(tmp) / "faults", A_ROWS)
            target = root / "anatomy.7"
            self.assertTrue(target.is_dir())
            shutil.rmtree(target)
            self.assertFalse(target.exists())
            self.assertTrue(support.anatomy_fault_dir(7).is_dir())
            require_path(self, ANATOMY_PY, "checks/anatomy.py is the gate")
            proc = run_anatomy("faults", str(root))
            assert_u2_refusal(
                self,
                proc,
                "anatomy.undemonstrated",
                outcome="finding",
                actual="anatomy.migrates-empty",
            )

    def test_faults_fires_fault_intact_when_a_fault_matches_goodcap(self):
        require_path(self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir")
        with tempfile.TemporaryDirectory(prefix="anatomy-faults-intact-") as tmp:
            root = stage_anatomy_faults(self, Path(tmp) / "faults", A_ROWS)
            target = root / "anatomy.1"
            shutil.rmtree(target)
            shutil.copytree(GOODCAP, target)
            self.assertEqual(rel_files(target), rel_files(GOODCAP))
            self.assertNotEqual(
                rel_files(support.anatomy_fault_dir(1)),
                rel_files(target),
                "the committed A1 fixture must be untouched",
            )
            require_path(self, ANATOMY_PY, "checks/anatomy.py is the gate")
            proc = run_anatomy("faults", str(root))
            assert_u2_refusal(self, proc, "anatomy.fault-intact", outcome="finding")

    def test_faults_fires_fault_mismatch_when_a_fault_draws_the_wrong_name(self):
        with tempfile.TemporaryDirectory(prefix="anatomy-faults-mismatch-") as tmp:
            root = stage_anatomy_faults(self, Path(tmp) / "faults", A_ROWS)
            a1 = root / "anatomy.1"
            a2 = root / "anatomy.2"
            a1_meta = load(root / "anatomy.1.meta.json")
            self.assertIn("missing", a1_meta["reject_path"])
            before = rel_files(a1)
            shutil.rmtree(a1)
            shutil.copytree(a2, a1)
            self.assertEqual(rel_files(a1), rel_files(a2))
            self.assertNotEqual(rel_files(a1), before)
            self.assertNotEqual(
                rel_files(support.anatomy_fault_dir(1)),
                rel_files(a1),
                "the committed A1 fixture must be untouched",
            )
            require_path(self, ANATOMY_PY, "checks/anatomy.py is the gate")
            proc = run_anatomy("faults", str(root))
            assert_u2_refusal(self, proc, "anatomy.fault-mismatch", outcome="finding")
