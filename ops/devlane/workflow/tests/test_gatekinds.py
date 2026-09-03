"""gatekinds.py — gate kinds are data, and malformed data refuses (PLAN §6)."""

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

import support
import canonical
import gatekinds
from errors import Refusal

REGISTRY = support.WF_DIR / "gate-kinds"

VALID = {
    "kind": "demo",
    "version": 1,
    "stages": [
        {"name": "a", "leave_requires": []},
        {"name": "b", "leave_requires": ["receipt.red"], "seals_frozen_set": True},
        {"name": "c", "actor": "owner", "outcomes": {"ok": "terminal", "back": "a"}},
    ],
    "test_scope": ["src/**"],
    "harness_scope": ["Makefile"],
    "checks": [{"name": "t", "class": "build", "argv": ["make", "test"]}],
}


class SeededRegistry(unittest.TestCase):
    """The two kinds Slice 1 ships (PLAN §11)."""

    def setUp(self):
        self.specs = gatekinds.load_specs(REGISTRY)

    def test_seeds_tdd_and_artifact(self):
        self.assertEqual(sorted(self.specs), [("artifact", 1), ("tdd", 1)])

    def test_tdd_matches_the_stage_order_the_plan_states(self):
        spec = gatekinds.latest(self.specs, "tdd")
        self.assertEqual(spec.stage_names, ["spec", "red", "impl", "review", "ratify"])
        self.assertEqual(spec.leave_requires("red"), ["receipt.red"])
        self.assertEqual(spec.leave_requires("impl"), ["receipt.green"])
        self.assertTrue(spec.seals_frozen_set("impl"))
        self.assertFalse(spec.seals_frozen_set("red"))
        self.assertEqual(
            spec.outcomes("review"),
            {"accepted": "advance", "finding": "impl", "denied": "terminal"},
        )
        self.assertEqual(spec.actor("ratify"), "owner")
        self.assertIsNone(spec.actor("review"))

    def test_artifact_runs_draft_review_fix_ratify_and_returns_to_review(self):
        spec = gatekinds.latest(self.specs, "artifact")
        self.assertEqual(spec.stage_names, ["draft", "review", "fix", "ratify"])
        self.assertEqual(spec.next_stage("draft"), "review")
        # A fix stage that fell through positionally would skip re-review.
        self.assertEqual(spec.next_stage("fix"), "review")
        self.assertEqual(spec.outcomes("review")["accepted"], "ratify")
        self.assertEqual(spec.outcomes("review")["finding"], "fix")
        self.assertIsNone(spec.next_stage("ratify"))

    def test_the_digest_is_over_the_decoded_value_not_the_file_bytes(self):
        # Re-indenting a spec file must not repin every work order that uses
        # it; changing what it *says* must.
        spec = gatekinds.latest(self.specs, "tdd")
        reindented = gatekinds.Spec(canonical.loads(canonical.dumpb(spec.raw)))
        self.assertEqual(reindented.sha256, spec.sha256)
        changed = copy.deepcopy(spec.raw)
        changed["stages"][1]["leave_requires"] = []
        self.assertNotEqual(gatekinds.Spec(changed).sha256, spec.sha256)

    def test_an_unknown_stage_refuses_and_names_the_ones_that_exist(self):
        spec = gatekinds.latest(self.specs, "tdd")
        with self.assertRaises(Refusal) as caught:
            spec.stage("nosuch")
        self.assertIn("spec, red, impl", str(caught.exception))


class Validation(unittest.TestCase):
    def bad(self, mutate):
        raw = copy.deepcopy(VALID)
        mutate(raw)
        with self.assertRaises(Refusal) as caught:
            gatekinds.Spec(raw)
        return str(caught.exception)

    def test_accepts_the_valid_shape(self):
        spec = gatekinds.Spec(copy.deepcopy(VALID))
        self.assertEqual(spec.kind, "demo")
        self.assertEqual(spec.first_stage, "a")
        self.assertEqual(spec.toolchain_argv, None)

    def test_rejects_a_missing_kind(self):
        self.assertIn("names a kind", self.bad(lambda r: r.pop("kind")))

    def test_rejects_a_non_positive_version(self):
        self.assertIn("positive integer", self.bad(lambda r: r.update(version=0)))
        self.assertIn("positive integer", self.bad(lambda r: r.update(version=True)))

    def test_rejects_an_empty_stage_list(self):
        self.assertIn("at least one stage", self.bad(lambda r: r.update(stages=[])))

    def test_rejects_duplicate_stage_names(self):
        self.assertIn(
            "unique", self.bad(lambda r: r["stages"].append({"name": "a"}))
        )

    def test_rejects_an_effect_that_is_not_a_verb_or_a_declared_stage(self):
        message = self.bad(
            lambda r: r["stages"][2]["outcomes"].update({"oops": "nowhere"})
        )
        self.assertIn("advance, stay, terminal, or a declared stage", message)

    def test_rejects_advance_to_naming_a_stage_that_does_not_exist(self):
        self.assertIn(
            "advance_to names a declared stage",
            self.bad(lambda r: r["stages"][0].update(advance_to="zzz")),
        )

    def test_rejects_a_check_without_a_class_or_argv(self):
        self.assertIn(
            "name, a class and an argv",
            self.bad(lambda r: r["checks"].append({"name": "x"})),
        )

    def test_rejects_a_scope_that_is_not_a_list_of_globs(self):
        self.assertIn("test_scope", self.bad(lambda r: r.update(test_scope="src/**")))
        self.assertIn("harness_scope", self.bad(lambda r: r.update(harness_scope=[1])))

    def test_rejects_a_non_boolean_seal_flag(self):
        self.assertIn(
            "seals_frozen_set is a boolean",
            self.bad(lambda r: r["stages"][1].update(seals_frozen_set="yes")),
        )

    def test_rejects_an_empty_toolchain_argv(self):
        self.assertIn(
            "toolchain_argv", self.bad(lambda r: r.update(toolchain_argv=[]))
        )


class Loading(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="wf-gk-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write(self, name, raw):
        (self.dir / name).write_bytes(canonical.dumpb(raw))

    def test_keys_specs_by_kind_and_version_from_their_content(self):
        self.write("demo.json", VALID)
        self.write("demo@2.json", {**copy.deepcopy(VALID), "version": 2})
        specs = gatekinds.load_specs(self.dir)
        self.assertEqual(sorted(specs), [("demo", 1), ("demo", 2)])
        self.assertEqual(gatekinds.latest(specs, "demo").version, 2)

    def test_refuses_two_files_registering_the_same_version(self):
        self.write("demo.json", VALID)
        self.write("copy.json", VALID)
        with self.assertRaises(Refusal) as caught:
            gatekinds.load_specs(self.dir)
        self.assertIn("registered once", str(caught.exception))

    def test_refuses_a_file_that_is_not_json(self):
        (self.dir / "broken.json").write_text("{not json")
        with self.assertRaises(Refusal) as caught:
            gatekinds.load_specs(self.dir)
        self.assertIn("is JSON", str(caught.exception))

    def test_refuses_an_unknown_kind_and_names_the_known_ones(self):
        self.write("demo.json", VALID)
        specs = gatekinds.load_specs(self.dir)
        with self.assertRaises(Refusal) as caught:
            gatekinds.latest(specs, "nosuch")
        self.assertIn("demo", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
