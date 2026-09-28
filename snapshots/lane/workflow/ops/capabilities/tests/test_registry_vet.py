"""registry-vet positives, Refusal.outcome, cue-unreachable abort, W6 rows.

Fixture paths this suite names (not written here):
  ops/capabilities/checks/registry_vet.py
  ops/capabilities/contracts/outcome.cue
  ops/capabilities/contracts/capabilities.cue
  ops/capabilities/contracts/examples/registry.json
  ops/capabilities/contracts/examples/registry.empty.json
  ops/capabilities/capabilities.json
"""

from __future__ import annotations

import unittest

import support
from support import (
    ARTIFACT_JSON,
    CAPABILITIES_CUE,
    CI_DEV_YML,
    LIVE_EXPORT,
    OUTCOME_CLASSES,
    OUTCOME_CUE,
    REGISTRY_EMPTY,
    REGISTRY_EXAMPLE,
    REGISTRY_VET,
    assert_not_refused,
    assert_u2_refusal,
    combined,
    digest_sidecar,
    env_without_cue,
    load_named,
    load_refusal,
    prove_cue_unreachable,
    require_path,
    run_registry_vet,
)


class RefusalOutcome(unittest.TestCase):
    """W3 / D-U2-errors-outcome: outcome is required and one of four classes."""

    def setUp(self):
        self.Refusal = load_refusal()

    def test_omitting_outcome_is_refused_construction(self):
        # W3: TypeError/refused construction — ValueError also satisfies.
        with self.assertRaises((TypeError, ValueError)):
            self.Refusal(
                "registry.layer",
                expected="dep.layer < layer",
                actual="0 depends on 1",
                needed="point the dep at a lower layer",
            )

    def test_each_outcome_class_is_accepted(self):
        for outcome in OUTCOME_CLASSES:
            with self.subTest(outcome=outcome):
                try:
                    refusal = self.Refusal(
                        "registry.layer",
                        expected="dep.layer < layer",
                        actual="0 depends on 1",
                        needed="point the dep at a lower layer",
                        outcome=outcome,
                    )
                except TypeError as exc:
                    self.fail(
                        "Refusal must take required outcome= in "
                        f"{OUTCOME_CLASSES}; got TypeError: {exc}"
                    )
                self.assertEqual(refusal.outcome, outcome)
                self.assertEqual(refusal.needed, "point the dep at a lower layer")

    def test_str_renders_outcome_class_and_remedy(self):
        try:
            refusal = self.Refusal(
                "registry.layer",
                expected="dep.layer < layer",
                actual="0 depends on 1",
                needed="point the dep at a lower layer",
                outcome="rejection",
            )
        except TypeError as exc:
            self.fail(f"Refusal must take required outcome=; got TypeError: {exc}")
        text = str(refusal)
        self.assertIn("refused:", text)
        self.assertIn("registry.layer", text)
        self.assertRegex(text, r"(?im)^(?:outcome|class):\s*rejection\s*$")
        self.assertIn("needed:", text)
        self.assertIn("point the dep at a lower layer", text)

    def test_an_unknown_outcome_class_is_refused(self):
        try:
            self.Refusal(
                "registry.layer",
                expected="dep.layer < layer",
                actual="0 depends on 1",
                needed="point the dep at a lower layer",
                outcome="error",
            )
        except (TypeError, ValueError):
            try:
                self.Refusal(
                    "registry.layer",
                    expected="dep.layer < layer",
                    actual="0 depends on 1",
                    needed="point the dep at a lower layer",
                    outcome="rejection",
                )
            except TypeError as exc:
                self.fail(
                    "Refusal must accept outcome='rejection' before "
                    f"unknown classes can be judged; got {exc}"
                )
            return
        self.fail("outcome='error' is outside #OutcomeClass and must be refused")


class PositiveControls(unittest.TestCase):
    """W4: clean two-row registry and the empty export both vet."""

    def test_clean_registry_example_vets(self):
        require_path(
            self,
            REGISTRY_EXAMPLE,
            "contracts/examples/registry.json is the two-row positive control",
        )
        require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
        require_path(
            self,
            digest_sidecar(REGISTRY_EXAMPLE),
            "contracts/examples/registry.json.digest is the current sidecar",
        )
        proc = run_registry_vet("vet", str(REGISTRY_EXAMPLE))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("refused:", proc.stderr)
        assert_not_refused(self, proc, "registry.stale-export")

    def test_clean_registry_has_two_rows_exercising_every_field(self):
        doc = load_named(
            self,
            REGISTRY_EXAMPLE,
            "contracts/examples/registry.json is the two-row positive control",
        )
        caps = doc["capabilities"]
        self.assertEqual(len(caps), 2, "§6.1: two fixture rows")
        for cap in caps:
            for key in support.CAPABILITY_KEYS:
                self.assertIn(key, cap, key)
            self.assertTrue(cap["iface"], "iface is a non-empty list of #Iface")
            for iface in cap["iface"]:
                self.assertIn("name", iface)
                self.assertTrue(iface["name"])
                self.assertIn("members", iface)
                self.assertTrue(iface["members"], "members is a non-empty list")
        by_layer = {cap["layer"]: cap for cap in caps}
        self.assertEqual(sorted(by_layer), [0, 1])
        layer0 = by_layer[0]
        layer1 = by_layer[1]
        self.assertIn("migrates", layer0["tags"])
        self.assertGreaterEqual(len(layer0["iface"]), 2)
        self.assertTrue(layer1["deps"])
        self.assertEqual(layer1["deps"][0]["id"], layer0["id"])
        dep_iface = layer1["deps"][0]["iface"]
        self.assertIn(dep_iface, [iface["name"] for iface in layer0["iface"]])

    def test_empty_registry_example_vets(self):
        doc = load_named(
            self,
            REGISTRY_EMPTY,
            "contracts/examples/registry.empty.json is the empty-export shape",
        )
        self.assertEqual(doc["capabilities"], [])
        self.assertNotIn("digest", doc)
        require_path(
            self,
            digest_sidecar(REGISTRY_EMPTY),
            "contracts/examples/registry.empty.json.digest is the current sidecar",
        )
        require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
        proc = run_registry_vet("vet", str(REGISTRY_EMPTY))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("refused:", proc.stderr)
        assert_not_refused(self, proc, "registry.stale-export")

    def test_live_export_is_empty_and_vets(self):
        doc = load_named(
            self,
            LIVE_EXPORT,
            "capabilities.json is the committed empty live export",
        )
        self.assertIn("capabilities", doc)
        self.assertEqual(doc["capabilities"], [])
        self.assertNotIn("digest", doc)
        require_path(
            self,
            digest_sidecar(LIVE_EXPORT),
            "capabilities.json.digest is the live currency sidecar",
        )
        require_path(self, REGISTRY_VET, "checks/registry_vet.py is the gate")
        proc = run_registry_vet("vet", str(LIVE_EXPORT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("refused:", proc.stderr)
        assert_not_refused(self, proc, "registry.stale-export")

    def test_export_json_does_not_carry_a_digest_field(self):
        """#Registry stays closed and digest-free (Amendment U2-A1 F2)."""
        for path, why in (
            (REGISTRY_EXAMPLE, "contracts/examples/registry.json is the two-row positive control"),
            (REGISTRY_EMPTY, "contracts/examples/registry.empty.json is the empty-export shape"),
            (LIVE_EXPORT, "capabilities.json is the committed empty live export"),
        ):
            with self.subTest(path=str(path)):
                doc = load_named(self, path, why)
                self.assertNotIn("digest", doc)

    def test_outcome_and_capabilities_cue_are_present_for_vet(self):
        require_path(self, OUTCOME_CUE, "contracts/outcome.cue is the taxonomy")
        require_path(
            self, CAPABILITIES_CUE, "contracts/capabilities.cue is the registry"
        )


class CueUnreachableIsAbort(unittest.TestCase):
    """W4 / D-U2-cue-in-ci: missing cue is a loud abort, never a skip."""

    def test_hidden_cue_draws_registry_cue_unreachable_as_abort(self):
        require_path(
            self,
            REGISTRY_EXAMPLE,
            "contracts/examples/registry.json is the two-row positive control",
        )
        env = env_without_cue()
        prove_cue_unreachable(self, env)
        proc = run_registry_vet("vet", str(REGISTRY_EXAMPLE), env=env)
        assert_u2_refusal(self, proc, "registry.cue-unreachable", outcome="abort")
        self.assertEqual(proc.returncode, 1, combined(proc))
        text = combined(proc).lower()
        self.assertNotIn("skipped", text)
        self.assertNotIn("skip test", text)


class Registration(unittest.TestCase):
    """W6: both checks are registered ci:true with the pinned argv."""

    def test_artifact_json_registers_registry_vet_and_anatomy(self):
        doc = load_named(
            self, ARTIFACT_JSON, "gate-kinds/artifact.json is the check registry"
        )
        rows = {row["name"]: row for row in doc["checks"]}
        self.assertIn("registry-vet", rows)
        self.assertIn("anatomy", rows)
        registry = rows["registry-vet"]
        anatomy = rows["anatomy"]
        self.assertEqual(registry["class"], "policy")
        self.assertEqual(anatomy["class"], "policy")
        self.assertIs(registry["ci"], True)
        self.assertIs(anatomy["ci"], True)
        self.assertEqual(
            registry["argv"],
            [
                "python3",
                "ops/capabilities/checks/registry_vet.py",
                "vet",
                "ops/capabilities/capabilities.json",
            ],
        )
        self.assertEqual(
            anatomy["argv"],
            ["python3", "ops/capabilities/checks/anatomy.py", "vet"],
        )

    def test_ci_dev_yml_installs_cue_for_registry_vet_and_anatomy(self):
        require_path(self, CI_DEV_YML, "ci-dev.yml is the CI runner")
        text = CI_DEV_YML.read_text(encoding="utf-8")
        self.assertIn("matrix.check == 'registry-vet'", text)
        self.assertIn("matrix.check == 'anatomy'", text)
        self.assertIn("0.14.1", text)
        self.assertRegex(
            text,
            r"if:\s*matrix\.check == 'registry-vet' \|\| matrix\.check == 'anatomy'",
        )
