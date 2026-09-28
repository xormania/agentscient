"""plan vet: raw presence, relational rules, fail-fast, economics, definition."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import support
from support import (
    EXAMPLES,
    PLAN_KEYS,
    assert_refusal,
    dump,
    expected_carry_bytes,
    expected_change_minutes,
    load,
    prove_plant,
    run_plan_vet,
    skip_without_cue,
)


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(obj), encoding="utf-8")
    return path


class RawPresence(unittest.TestCase):
    """Step 1 runs without cue: every #Plan key stated, no derived key."""

    def test_a_change_key_under_economics_is_derived(self):
        clean = load(EXAMPLES / "plan.json")
        planted = dict(clean)
        economics = dict(planted["economics"])
        economics["change"] = {"minutes": 9}
        planted["economics"] = economics
        prove_plant(clean, planted, site=("economics", "change"))
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "leaf.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            self.assertIn('"change"', path.read_text(encoding="utf-8"))
            proc = run_plan_vet("vet", str(path))
            assert_refusal(self, proc, "plan.derived-key", actual="change")

    def test_fail_fast_names_absent_key_before_derived_key(self):
        clean = load(EXAMPLES / "plan.json")
        planted = dict(clean)
        del planted["units"]
        economics = dict(planted["economics"])
        economics["carry"] = {"bytes": 1}
        planted["economics"] = economics
        prove_plant(
            clean,
            planted,
            omitted_keys=("units",),
            site=("units",),
            exclusive=False,
        )
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "leaf.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            self.assertIn("plan.absent-key", proc.stderr)
            self.assertNotIn("plan.derived-key", proc.stderr)
            self.assertNotEqual(proc.returncode, 0)

    def test_the_clean_leaf_does_not_draw_a_raw_presence_refusal(self):
        """Cue-free positive: an always-refusing vet is no longer green."""
        self.assertTrue(
            support.PLAN_VET.is_file(),
            "plan_vet.py is the gate; a missing file is this test's red",
        )
        proc = run_plan_vet("vet", str(EXAMPLES / "plan.json"))
        for claim in (
            "plan.absent-key",
            "plan.derived-key",
            "plan.root-parent",
            "plan.stale-parent",
        ):
            self.assertNotIn(claim, proc.stderr, proc.stderr)
        missing = [key for key in PLAN_KEYS if key not in load(EXAMPLES / "plan.json")]
        self.assertEqual(missing, [])


class RelationalRules(unittest.TestCase):
    """Rules the §5 table does not plant, each a named refusal."""

    def _planted_child(self, mutate, site):
        clean = load(EXAMPLES / "plan.json")
        planted = mutate(dict(clean))
        prove_plant(clean, planted, site=site)
        return planted

    def test_settled_dropped_names_the_missing_id(self):
        skip_without_cue()

        def mutate(doc):
            doc["settled"] = [row for row in doc["settled"] if row["id"] != "D-root-one"]
            return doc

        planted = self._planted_child(mutate, ("settled",))
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "leaf.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            assert_refusal(self, proc, "plan.settled-dropped", expected="D-root-one")

    def test_scope_oversize_refuses_owner_words_over_1024_bytes(self):
        skip_without_cue()
        parent_words = load(EXAMPLES / "plan.root.json")["scope"]["owner_words"]
        suffix = " | 2026-08-30: "
        pad = "x" * (1025 - len((parent_words + suffix).encode("utf-8")))

        def mutate(doc):
            scope = dict(doc["scope"])
            scope["owner_words"] = parent_words + suffix + pad
            doc["scope"] = scope
            return doc

        planted = self._planted_child(mutate, ("scope", "owner_words"))
        self.assertEqual(len(planted["scope"]["owner_words"].encode("utf-8")), 1025)
        self.assertTrue(planted["scope"]["owner_words"].startswith(parent_words))
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "leaf.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            assert_refusal(self, proc, "plan.scope-oversize")

    def test_scope_of_exactly_1024_bytes_vets(self):
        skip_without_cue()
        parent_words = load(EXAMPLES / "plan.root.json")["scope"]["owner_words"]
        suffix = " | 2026-08-30: "
        pad = "x" * (1024 - len((parent_words + suffix).encode("utf-8")))

        def mutate(doc):
            scope = dict(doc["scope"])
            scope["owner_words"] = parent_words + suffix + pad
            doc["scope"] = scope
            return doc

        planted = self._planted_child(mutate, ("scope", "owner_words"))
        self.assertEqual(len(planted["scope"]["owner_words"].encode("utf-8")), 1024)
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "leaf.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("plan.scope-oversize", proc.stderr)

    def test_a_multiline_new_decision_is_refused(self):
        skip_without_cue()

        def mutate(doc):
            decision = dict(doc["decisions"][0])
            decision["sentence"] = "First line.\nSecond line."
            doc["decisions"] = [decision]
            return doc

        planted = self._planted_child(mutate, ("decisions", 0, "sentence"))
        self.assertIn("\n", planted["decisions"][0]["sentence"])
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "leaf.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            assert_refusal(self, proc, "plan.decision-multiline")

    def test_a_new_decision_over_512_bytes_is_refused(self):
        skip_without_cue()

        def mutate(doc):
            decision = dict(doc["decisions"][0])
            decision["sentence"] = "x" * 513
            doc["decisions"] = [decision]
            return doc

        planted = self._planted_child(mutate, ("decisions", 0, "sentence"))
        self.assertEqual(len(planted["decisions"][0]["sentence"].encode("utf-8")), 513)
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "leaf.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            assert_refusal(self, proc, "plan.decision-multiline")

    def test_a_new_decision_of_exactly_512_bytes_vets(self):
        skip_without_cue()

        def mutate(doc):
            decision = dict(doc["decisions"][0])
            decision["sentence"] = "x" * 512
            doc["decisions"] = [decision]
            return doc

        planted = self._planted_child(mutate, ("decisions", 0, "sentence"))
        self.assertEqual(len(planted["decisions"][0]["sentence"].encode("utf-8")), 512)
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "leaf.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("plan.decision-multiline", proc.stderr)

    def test_an_unknown_decision_status_is_refused(self):
        skip_without_cue()

        def mutate(doc):
            decision = dict(doc["decisions"][0])
            decision["status"] = "unknown"
            doc["decisions"] = [decision]
            return doc

        planted = self._planted_child(mutate, ("decisions", 0, "status"))
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "leaf.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            # §4 step 2 re-issues CUE errors as plan.<field>, so plan.status.
            assert_refusal(self, proc, "plan.status", actual="unknown")

    def test_new_false_cannot_be_owner_ratified(self):
        skip_without_cue()

        def mutate(doc):
            decision = {
                "id": "D-carried",
                "new": False,
                "premises": list(doc["premises"]),
                "ratified_by": "owner",
                "sentence": "A not-new decision is parent-ratified by construction.",
                "status": "standing",
            }
            doc["decisions"] = [decision]
            return doc

        planted = self._planted_child(mutate, ("decisions",))
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "leaf.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            assert_refusal(self, proc, "plan.ratified_by", actual="owner")

    def test_an_unknown_ratified_by_is_refused(self):
        skip_without_cue()

        def mutate(doc):
            decision = dict(doc["decisions"][0])
            decision["ratified_by"] = "nobody"
            doc["decisions"] = [decision]
            return doc

        planted = self._planted_child(mutate, ("decisions", 0, "ratified_by"))
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "leaf.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            assert_refusal(self, proc, "plan.ratified_by", actual="nobody")

    def test_pending_blocks_a_unit_from_code(self):
        skip_without_cue()
        clean = load(EXAMPLES / "plan.root.json")
        planted = dict(clean)
        units = [dict(clean["units"][0])]
        units[0]["stage"] = "code"
        planted["units"] = units
        decisions = [dict(clean["decisions"][0])]
        decisions[0]["ratified_by"] = "pending"
        planted["decisions"] = decisions
        prove_plant(
            clean, planted, site=("units", 0, "stage"), exclusive=False
        )
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "root.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            assert_refusal(self, proc, "plan.stage-blocked")

    def test_revisit_blocks_a_unit_from_code(self):
        skip_without_cue()
        clean = load(EXAMPLES / "plan.root.json")
        planted = dict(clean)
        units = [dict(clean["units"][0])]
        units[0]["stage"] = "code"
        planted["units"] = units
        decisions = [dict(clean["decisions"][0])]
        decisions[0]["status"] = "revisit"
        planted["decisions"] = decisions
        prove_plant(
            clean, planted, site=("units", 0, "stage"), exclusive=False
        )
        with tempfile.TemporaryDirectory(prefix="plan-vet-") as tmp:
            path = Path(tmp) / "root.plan.json"
            path.write_text(dump(planted), encoding="utf-8")
            proc = run_plan_vet("vet", str(path))
            assert_refusal(self, proc, "plan.stage-blocked")

    def test_stale_parent_refusal_names_the_digest_it_expected(self):
        skip_without_cue()
        expected = hashlib.sha256(
            (EXAMPLES / "plan.root.json").read_bytes()
        ).hexdigest()
        planted = load(support.FAULTS / "plan.1.json")
        self.assertNotEqual(planted["parent"]["sha256"], expected)
        proc = run_plan_vet("vet", str(support.FAULTS / "plan.1.json"))
        assert_refusal(
            self,
            proc,
            "plan.stale-parent",
            expected=expected,
            actual=planted["parent"]["sha256"],
        )


class StageCodePositive(unittest.TestCase):
    """Rule 7's two negatives need a positive at stage code beside them."""

    def test_owner_ratified_standing_may_enter_code(self):
        skip_without_cue()
        proc = run_plan_vet("vet", str(EXAMPLES / "plan.stage-code.json"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("plan.stage-blocked", proc.stderr)
        self.assertEqual(load(EXAMPLES / "plan.stage-code.json")["units"][0]["stage"], "code")
        self.assertEqual(
            load(EXAMPLES / "plan.stage-code.json")["decisions"][0]["ratified_by"],
            "owner",
        )
        self.assertEqual(
            load(EXAMPLES / "plan.stage-code.json")["decisions"][0]["status"],
            "standing",
        )


class DefinitionAndEconomics(unittest.TestCase):
    """`--definition` is a real seam; `--economics` derives numbers."""

    def test_definition_plan_vets_the_clean_leaf(self):
        skip_without_cue()
        proc = run_plan_vet(
            "vet", str(EXAMPLES / "plan.json"), "--definition", "#Plan"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_unknown_definition_is_refused_without_cue(self):
        proc = run_plan_vet(
            "vet", str(EXAMPLES / "plan.json"), "--definition", "#Nope"
        )
        assert_refusal(self, proc, "plan.definition", actual="#Nope")

    def test_economics_derives_carry_bytes_and_change_minutes(self):
        leaf = load(EXAMPLES / "plan.json")
        carry, md_b, js_b, ow_b = expected_carry_bytes(
            EXAMPLES / "plan.md",
            EXAMPLES / "plan.json",
            leaf["scope"]["owner_words"],
        )
        self.assertGreater(carry, 0)
        self.assertEqual(md_b, (EXAMPLES / "plan.md").stat().st_size)
        self.assertEqual(js_b, (EXAMPLES / "plan.json").stat().st_size)
        self.assertEqual(ow_b, len("framework first".encode("utf-8")))
        child = (
            support.REPO / "ops" / "capabilities" / "tests" / "_cascade.plan.json"
        )
        payload = {
            "economics": {"write": {"minutes": 4, "tag": "assumed"}},
            "id": "example/leaf/cascade",
            "parent": {
                "bound_to": "sidecar",
                "id": "example/leaf",
                "sha256": "0" * 64,
                "unit": "cascade",
            },
        }
        child.write_text(dump(payload), encoding="utf-8")
        self.addCleanup(child.unlink, missing_ok=True)
        self.assertTrue(child.is_file())
        self.assertEqual(load(child)["economics"]["write"]["minutes"], 4)
        change = expected_change_minutes("example/leaf")
        self.assertGreaterEqual(change, 4)
        proc = run_plan_vet("vet", str(EXAMPLES / "plan.json"), "--economics")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("plan.derived-key", proc.stderr)
        text = combined_text(proc)
        self.assertRegex(text, rf"carry[^\n]*\b{carry}\b")
        self.assertRegex(text, rf"change[^\n]*\b{change}\b")
        self.assertRegex(text, r"bytes")
        self.assertRegex(text, r"minutes")

    def test_economics_does_not_skip_a_hand_written_carry(self):
        proc = run_plan_vet(
            "vet", str(support.FAULTS / "plan.15.json"), "--economics"
        )
        assert_refusal(self, proc, "plan.derived-key", actual="carry")


def combined_text(proc):
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


class ParentLayout(unittest.TestCase):
    """Parent resolution is the plans/<unit>.plan.json layout, not a fixture path."""

    def _layout(self, tmp, *, child_sentence=None, include_child=True):
        root_dir = Path(tmp)
        plans = root_dir / "plans"
        parent = dict(load(EXAMPLES / "plan.root.json"))
        parent["id"] = "example"
        parent_path = _write(root_dir / "example.plan.json", parent)
        digest = hashlib.sha256(parent_path.read_bytes()).hexdigest()
        child = dict(load(EXAMPLES / "plan.json"))
        child["parent"] = {
            "bound_to": "sidecar",
            "id": "example",
            "sha256": digest,
            "unit": "leaf",
        }
        if child_sentence is not None:
            decision = dict(child["decisions"][0])
            decision["sentence"] = child_sentence
            child["decisions"] = [decision]
        child_path = None
        if include_child:
            child_path = _write(plans / "leaf.plan.json", child)
        return parent_path, child_path, parent, child

    def test_a_child_in_the_plans_layout_vets_against_its_parent_sidecar(self):
        skip_without_cue()
        with tempfile.TemporaryDirectory(prefix="plan-layout-") as tmp:
            _parent_path, child_path, _parent, child = self._layout(tmp)
            self.assertEqual(child["parent"]["id"], "example")
            self.assertTrue(child_path.is_file())
            proc = run_plan_vet("vet", str(child_path))
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_parent_open_is_undelegated_when_the_child_sidecar_is_missing(self):
        skip_without_cue()
        with tempfile.TemporaryDirectory(prefix="plan-layout-") as tmp:
            parent_path, child_path, parent, _child = self._layout(
                tmp, include_child=False
            )
            self.assertIsNone(child_path)
            self.assertTrue(parent["open"])
            self.assertFalse((Path(tmp) / "plans" / "leaf.plan.json").is_file())
            proc = run_plan_vet("vet", str(parent_path))
            assert_refusal(self, proc, "plan.undelegated")

    def test_parent_open_is_undelegated_when_the_child_does_not_list_it(self):
        skip_without_cue()
        with tempfile.TemporaryDirectory(prefix="plan-layout-") as tmp:
            parent_path, child_path, parent, child = self._layout(
                tmp, child_sentence="a different piece of work"
            )
            what = parent["open"][0]["what"]
            self.assertNotEqual(child["decisions"][0]["sentence"], what)
            self.assertEqual(child["open"], [])
            self.assertTrue(child_path.is_file())
            proc = run_plan_vet("vet", str(parent_path))
            assert_refusal(self, proc, "plan.undelegated", expected=what)

    def test_parent_open_is_quiet_when_the_child_lists_it(self):
        skip_without_cue()
        with tempfile.TemporaryDirectory(prefix="plan-layout-") as tmp:
            parent_path, child_path, parent, child = self._layout(tmp)
            self.assertEqual(
                child["decisions"][0]["sentence"], parent["open"][0]["what"]
            )
            self.assertTrue(child_path.is_file())
            proc = run_plan_vet("vet", str(parent_path))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("plan.undelegated", proc.stderr)



