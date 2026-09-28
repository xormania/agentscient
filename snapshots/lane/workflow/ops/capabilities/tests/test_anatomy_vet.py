"""anatomy positives, vacuous-scan honesty, cue-unreachable abort, both-ways.

Fixture paths this suite names (not written here):
  ops/capabilities/checks/anatomy.py
  ops/capabilities/contracts/capability.cue
  ops/capabilities/contracts/outcome.cue
  ops/capabilities/contracts/examples/anatomy/goodcap/
  ops/capabilities/capabilities/   (empty at U2; default scan root)
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from support import (
    ANATOMY_ENTRIES,
    ANATOMY_PY,
    CAPABILITIES_DIR,
    CAPABILITY_CUE,
    GOODCAP,
    MANIFEST_KEYS,
    OUTCOME_CLASSES,
    VACUOUS_HONESTY,
    assert_not_refused,
    assert_u2_refusal,
    combined,
    env_without_cue,
    goodcap_module,
    insert_protocol_body,
    last_declared_iface,
    load_named,
    prove_cue_unreachable,
    prove_dir_plant,
    prove_protocol_members,
    require_path,
    run_anatomy,
)


class PositiveControls(unittest.TestCase):
    """W5: goodcap is complete and vets."""

    def test_goodcap_vets(self):
        require_path(
            self,
            GOODCAP,
            "contracts/examples/anatomy/goodcap/ is the complete fixture",
            kind="dir",
        )
        require_path(self, ANATOMY_PY, "checks/anatomy.py is the gate")
        proc = run_anatomy("vet", str(GOODCAP))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("refused:", proc.stderr)
        assert_not_refused(self, proc, "anatomy.member-missing")
        assert_not_refused(self, proc, "anatomy.member-undeclared")
        assert_not_refused(self, proc, "anatomy.iface-unresolved")
        assert_not_refused(self, proc, "anatomy.refusals-disagree")

    def test_goodcap_is_a_complete_fixture_capability(self):
        require_path(
            self,
            GOODCAP,
            "contracts/examples/anatomy/goodcap/ is the complete fixture",
            kind="dir",
        )
        for name in ANATOMY_ENTRIES:
            path = GOODCAP / name.rstrip("/")
            if name.endswith("/"):
                self.assertTrue(path.is_dir(), f"{path} is a required directory")
            else:
                self.assertTrue(path.is_file(), f"{path} is a required file")
        manifest = load_named(
            self, GOODCAP / "capability.json", "goodcap capability.json"
        )
        for key in MANIFEST_KEYS:
            self.assertIn(key, manifest, key)
        self.assertTrue(manifest["refusals"], "goodcap declares classified refusals")
        for row in manifest["refusals"]:
            self.assertIn("name", row)
            self.assertIn("class", row)
            self.assertIn("remedy", row)
            self.assertTrue(row["name"])
            self.assertTrue(row["remedy"], "every refusal carries a remedy")
            self.assertIn(row["class"], OUTCOME_CLASSES)
        self.assertIn("migrates", manifest["tags"])
        migrations = GOODCAP / "migrations"
        self.assertTrue(migrations.is_dir())
        self.assertTrue(
            any(migrations.iterdir()),
            "goodcap migrations/ is non-empty (§6.1)",
        )
        module, _manifest = goodcap_module(self, GOODCAP)
        self.assertTrue(module.is_file(), module)
        last_declared_iface(self, manifest)
        for iface in manifest["iface"]:
            self.assertTrue(iface["name"])
            self.assertTrue(iface["members"])

    def test_capability_cue_is_present_for_vet(self):
        require_path(
            self, CAPABILITY_CUE, "contracts/capability.cue is the anatomy contract"
        )


class BothWaysMemberCheck(unittest.TestCase):
    """§2: declaration ↔ Protocol body, both directions; dunders ignored."""

    def test_goodcap_protocol_bodies_match_declared_members(self):
        require_path(
            self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir"
        )
        require_path(self, ANATOMY_PY, "checks/anatomy.py is the gate")
        proc = run_anatomy("vet", str(GOODCAP))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        assert_not_refused(self, proc, "anatomy.member-missing")
        assert_not_refused(self, proc, "anatomy.member-undeclared")

    def test_dunder_and_private_protocol_names_are_not_undeclared(self):
        require_path(
            self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir"
        )
        with tempfile.TemporaryDirectory(prefix="anatomy-dunder-") as tmp:
            planted = Path(tmp) / "goodcap"
            shutil.copytree(GOODCAP, planted)
            module, manifest = goodcap_module(self, planted)
            iface, _idx = last_declared_iface(self, manifest)
            name = iface["name"]
            original = module.read_text(encoding="utf-8")
            rewritten = insert_protocol_body(
                original,
                name,
                ["def __call__(self): ...", "_private: int"],
                members=("__call__", "_private"),
            )
            module.write_text(rewritten, encoding="utf-8")
            self.assertNotEqual(module.read_bytes(), original.encode("utf-8"))
            prove_protocol_members(
                module.read_text(encoding="utf-8"),
                name,
                "__call__",
                "_private",
            )
            prove_dir_plant(
                GOODCAP,
                planted,
                changed=(str(module.relative_to(planted)).replace("\\", "/"),),
            )
            require_path(self, ANATOMY_PY, "checks/anatomy.py is the gate")
            proc = run_anatomy("vet", str(planted))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            assert_not_refused(self, proc, "anatomy.member-undeclared")


class VacuousScanHonesty(unittest.TestCase):
    """D-U2-vacuous-honesty: empty capabilities/ is not reported clean."""

    def test_default_scan_prints_the_zero_scanned_honesty_line_and_exits_0(self):
        require_path(self, ANATOMY_PY, "checks/anatomy.py is the gate")
        if CAPABILITIES_DIR.exists():
            children = [p for p in CAPABILITIES_DIR.iterdir() if p.is_dir()]
            self.assertEqual(
                children,
                [],
                "U2's real capabilities/ is empty; "
                f"found { [p.name for p in children] }",
            )
        proc = run_anatomy("vet")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = combined(proc)
        self.assertIn(VACUOUS_HONESTY, text)
        self.assertNotIn("clean", text.lower())
        self.assertNotIn("skipped", text.lower())


class CueUnreachableIsAbort(unittest.TestCase):
    """W5 / D-U2-cue-in-ci: missing cue is a loud abort, never a skip."""

    def test_hidden_cue_draws_anatomy_cue_unreachable_as_abort(self):
        require_path(
            self, GOODCAP, "contracts/examples/anatomy/goodcap/", kind="dir"
        )
        env = env_without_cue()
        prove_cue_unreachable(self, env)
        proc = run_anatomy("vet", str(GOODCAP), env=env)
        assert_u2_refusal(self, proc, "anatomy.cue-unreachable", outcome="abort")
        self.assertEqual(proc.returncode, 1, combined(proc))
        text = combined(proc).lower()
        self.assertNotIn("skipped", text)
        self.assertNotIn("skip test", text)
