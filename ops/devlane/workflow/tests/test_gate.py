"""red / advance / green — the TDD gate and the frozen set (PLAN §3.3).

The acceptance bar (§13) states four of these directly: red refuses a
passing command and records a failing one; green refuses a changed
manifest, a changed argv, and a dirty tree.
"""

import json
import unittest

import support
from support import SandboxCase
import canonical
from errors import EXIT_OK, EXIT_REFUSED


class GateCase(SandboxCase):
    """A work order sitting in the red stage of a seeded project."""

    def setUp(self):
        super().setUp()
        self.sb.seed_project()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "gate",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)

    def red(self, *extra, check=EXIT_OK):
        return self.sb.wf("--json", "red", "WO-001", *extra, "--",
                          *support.Sandbox.GATE_ARGV, check=check)

    def green(self, *extra, argv=None, check=EXIT_OK):
        return self.sb.wf("--json", "green", "WO-001", *extra, "--",
                          *(argv or support.Sandbox.GATE_ARGV), check=check)

    def state(self, wo="WO-001"):
        return json.loads(self.sb.wf("--json", "status", wo, check=EXIT_OK).stdout)

    def events(self, wo="WO-001"):
        raw = json.loads(self.sb.wf("--json", "log", "--full", "--all", wo, check=EXIT_OK).stdout)["events"]
        return support.without_binds(raw)


class Red(GateCase):
    def test_refuses_a_command_that_passes(self):
        """Scenario: a red that passes is refused as dishonest"""
        self.sb.make_green()
        proc = self.red(check=EXIT_REFUSED)
        self.assertIn("the test command fails", proc.stderr)
        self.assertEqual(self.state()["satisfied"], [],
                         "a refused red must record no evidence")

    def test_records_a_command_that_fails(self):
        body = json.loads(self.red().stdout)
        self.assertEqual(body["exit_code"], 1)
        self.assertEqual(body["satisfied"], ["receipt.red"])
        self.assertEqual(body["missing"], [])
        self.assertEqual(len(body["test_manifest_sha256"]), 64)

    def test_the_receipt_records_the_git_state_it_ran_against(self):
        # The tree the command ran against, not the wf auto-commit that
        # records it afterwards — that commit did not exist yet.
        ran_against = self.sb.head()
        self.red()
        receipt = self.events()[-1]
        self.assertEqual(receipt["type"], "receipt.red")
        self.assertEqual(receipt["head_sha"], ran_against)
        self.assertNotEqual(receipt["head_sha"], self.sb.head())
        self.sb._git("merge-base", "--is-ancestor", receipt["head_sha"], self.sb.head())
        self.assertFalse(receipt["tree_dirty"])
        self.assertEqual(receipt["argv"], support.Sandbox.GATE_ARGV)
        self.assertEqual(receipt["cwd"], ".")
        self.assertIsNone(receipt["toolchain"], "tdd@1 declares no toolchain")
        self.assertEqual(len(receipt["stdout_sha256"]), 64)
        self.assertEqual(len(receipt["stderr_sha256"]), 64)

    def test_full_outputs_go_to_the_object_store_and_tails_stay_inline(self):
        self.red()
        receipt = self.events()[-1]
        for digest in (receipt["stdout_sha256"], receipt["stderr_sha256"]):
            stored = self.sb.root / "objects" / digest[:2] / digest
            self.assertTrue(stored.exists())
            self.assertEqual(canonical.sha256_hex(stored.read_bytes()), digest)
        self.assertLessEqual(len(receipt["stderr_tail"]), 400)

    def test_the_manifest_covers_test_scope_and_harness_scope(self):
        first = json.loads(self.red().stdout)["test_manifest_sha256"]
        self.assertEqual(json.loads(self.red().stdout)["manifest_files"], 2)

        # Harness: a Cargo.toml edit must move the frozen hash, because that
        # is how a frozen test gets deselected without touching a test file.
        self.sb.write("Cargo.toml", '[package]\nname = "demo"\nedition = "2021"\n')
        self.sb.commit_all("sandbox: touch the harness")
        second = json.loads(self.red().stdout)["test_manifest_sha256"]
        self.assertNotEqual(first, second)

        # Test scope: editing a test moves it too.
        self.sb.write("crates/demo/tests/gate.py",
                      support.Sandbox.GATE_SOURCE + "# changed\n")
        self.sb.commit_all("sandbox: touch a test")
        third = json.loads(self.red().stdout)["test_manifest_sha256"]
        self.assertNotEqual(second, third)

    def test_refuses_a_dirty_tree(self):
        self.sb.write("crates/demo/tests/gate.py", support.Sandbox.GATE_SOURCE + "#\n")
        proc = self.red(check=EXIT_REFUSED)
        self.assertIn("working tree is clean", proc.stderr)
        self.assertIn("crates/demo/tests/gate.py", proc.stderr)

    def test_allow_dirty_records_tree_dirty(self):
        self.sb.write("crates/demo/tests/gate.py", support.Sandbox.GATE_SOURCE + "#\n")
        body = json.loads(self.red("--allow-dirty").stdout)
        self.assertTrue(body["tree_dirty"])
        self.assertTrue(self.events()[-1]["tree_dirty"])

    def test_wf_own_export_does_not_count_as_a_dirty_tree(self):
        # The export is one bind behind by construction (PLAN §3.6): after any
        # verb, the chain file on disk really is modified. If that counted as
        # dirt, no second command could ever run. Nothing is planted here —
        # the pending bind is the genuine article.
        self.red()
        dirt = self.sb._git("status", "--porcelain").strip().splitlines()
        self.assertEqual(len(dirt), 1, dirt)
        self.assertTrue(dirt[0].endswith("chains/WO-001.jsonl"),
                        "the fixture requires real, uncommitted wf export")
        self.sb.wf("advance", "WO-001", check=EXIT_OK)

    def test_a_dirty_path_outside_the_export_does_count(self):
        # The control: the exclusion is scoped to wf's own paths, not a
        # blanket "ignore dirt".
        self.sb.write("crates/demo/tests/gate.py", support.Sandbox.GATE_SOURCE + "#\n")
        proc = self.red(check=EXIT_REFUSED)
        self.assertIn("working tree is clean", proc.stderr)

    def test_refuses_in_a_stage_that_does_not_ask_for_a_red_receipt(self):
        self.sb.wf("open", "WO-002", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        proc = self.sb.wf("red", "WO-002", "--", *support.Sandbox.GATE_ARGV,
                          check=EXIT_REFUSED)
        self.assertIn("requires receipt.red", proc.stderr)

    def test_refuses_without_a_command(self):
        proc = self.sb.wf("red", "WO-001", check=EXIT_REFUSED)
        self.assertIn("given a command to run", proc.stderr)

    def test_refuses_a_command_that_does_not_exist(self):
        proc = self.sb.wf("red", "WO-001", "--", "no-such-binary-xyz",
                          check=EXIT_REFUSED)
        self.assertIn("the command exists", proc.stderr)


class Advance(GateCase):
    def test_seals_the_frozen_set_from_the_latest_red(self):
        digest = json.loads(self.red().stdout)["test_manifest_sha256"]
        body = json.loads(self.sb.wf("--json", "advance", "WO-001", check=EXIT_OK).stdout)
        self.assertEqual(body["stage"], "impl")
        self.assertEqual(body["sealed_manifest_sha256"], digest)
        frozen = body["frozen"]
        self.assertEqual(frozen["manifest_sha256"], digest)
        self.assertEqual(frozen["argv"], support.Sandbox.GATE_ARGV)
        red = [e for e in self.events() if e["type"] == "receipt.red"][-1]
        self.assertEqual(frozen["red_seq"], red["seq"])
        self.assertEqual(frozen["red_hash"], red["hash"])

    def test_seals_the_latest_red_when_several_were_recorded(self):
        first = json.loads(self.red().stdout)["test_manifest_sha256"]
        self.sb.write("crates/demo/tests/gate.py",
                      support.Sandbox.GATE_SOURCE + "# second\n")
        self.sb.commit_all("sandbox: change the test")
        second = json.loads(self.red().stdout)["test_manifest_sha256"]
        self.assertNotEqual(first, second)
        body = json.loads(self.sb.wf("--json", "advance", "WO-001", check=EXIT_OK).stdout)
        self.assertEqual(body["sealed_manifest_sha256"], second)

    def test_refuses_when_the_stage_still_needs_evidence(self):
        proc = self.sb.wf("advance", "WO-001", check=EXIT_REFUSED)
        self.assertIn("evidence its gate kind requires", proc.stderr)
        self.assertIn("receipt.red", proc.stderr)

    def test_refuses_on_a_stage_that_is_left_by_recording_an_outcome(self):
        self.red()
        self.sb.wf("advance", "WO-001", check=EXIT_OK)   # impl
        self.sb.make_green()
        self.green()
        self.sb.wf("advance", "WO-001", check=EXIT_OK)   # review
        proc = self.sb.wf("advance", "WO-001", check=EXIT_REFUSED)
        self.assertIn("left by recording an outcome", proc.stderr)

    def test_to_requires_a_reason(self):
        self.red()
        proc = self.sb.wf("advance", "WO-001", "--to", "spec", check=EXIT_REFUSED)
        self.assertIn("states a reason", proc.stderr)

    def test_to_refuses_a_forward_jump(self):
        proc = self.sb.wf("advance", "WO-001", "--to", "review",
                          "--reason", "skip ahead", check=EXIT_REFUSED)
        self.assertIn("re-enters an earlier stage", proc.stderr)

    def test_to_an_unknown_stage_names_the_ones_that_exist(self):
        proc = self.sb.wf("advance", "WO-001", "--to", "nosuch",
                          "--reason", "r", check=EXIT_REFUSED)
        self.assertIn("spec, red, impl", proc.stderr)

    def test_re_entering_red_voids_the_frozen_set_and_keeps_the_old_path(self):
        self.red()
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.assertIsNotNone(self.state()["frozen"])
        self.sb.wf("advance", "WO-001", "--to", "red",
                   "--reason", "spec changed", check=EXIT_OK)
        after = self.state()
        self.assertEqual(after["stage"], "red")
        self.assertIsNone(after["frozen"], "re-entry voids the seal")
        # Nothing is rewritten; the voided path stays in the chain.
        stages = [e["stage"] for e in self.events() if e["type"] == "stage.entered"]
        self.assertEqual(stages, ["spec", "red", "impl", "red"])
        self.assertEqual(self.events()[-1]["reason"], "spec changed")


class Green(GateCase):
    def setUp(self):
        super().setUp()
        self.red()
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.frozen = self.state()["frozen"]

    def test_records_on_a_clean_match_and_binds_the_red_receipt(self):
        self.sb.make_green()
        body = json.loads(self.green().stdout)
        self.assertEqual(body["exit_code"], 0)
        self.assertEqual(body["satisfied"], ["receipt.green"])
        receipt = self.events()[-1]
        self.assertEqual(receipt["type"], "receipt.green")
        self.assertEqual(receipt["red_seq"], self.frozen["red_seq"])
        self.assertEqual(receipt["red_hash"], self.frozen["red_hash"])
        self.assertEqual(receipt["frozen_manifest_sha256"],
                         self.frozen["manifest_sha256"])
        self.assertEqual(receipt["test_manifest_sha256"],
                         self.frozen["manifest_sha256"])

    def test_refuses_a_changed_manifest(self):
        self.sb.make_green()
        self.sb.write("crates/demo/tests/gate.py",
                      support.Sandbox.GATE_SOURCE + "# deselected\n")
        self.sb.commit_all("sandbox: change a frozen test")
        proc = self.green(check=EXIT_REFUSED)
        self.assertIn("equals the frozen set", proc.stderr)
        self.assertIn(self.frozen["manifest_sha256"], proc.stderr)

    def test_refuses_a_changed_argv(self):
        """Scenario: green runs the frozen command, not a fresh one"""
        self.sb.make_green()
        proc = self.green(argv=support.Sandbox.GATE_ARGV + ["--extra"],
                          check=EXIT_REFUSED)
        self.assertIn("same command the bound red recorded", proc.stderr)

    def test_refuses_a_dirty_tree(self):
        self.sb.write("src.txt", "uncommitted\n")
        proc = self.green(check=EXIT_REFUSED)
        self.assertIn("working tree is clean", proc.stderr)

    def test_refuses_a_command_that_fails(self):
        proc = self.green(check=EXIT_REFUSED)
        self.assertIn("the test command succeeds", proc.stderr)
        self.assertEqual(self.state()["satisfied"], [])

    def test_a_voided_frozen_set_cannot_be_used_and_is_replaced(self):
        # PLAN §13 lists a voided frozen set among the planted faults. Voiding
        # must have teeth in both directions: the old seal becomes unusable,
        # and the next seal is a fresh measurement rather than the old one
        # coming back.
        self.sb.make_green()
        old_seal = self.frozen["manifest_sha256"]

        self.sb.wf("advance", "WO-001", "--to", "red",
                   "--reason", "spec changed", check=EXIT_OK)
        self.assertIsNone(self.state()["frozen"], "re-entry voids the seal")

        # The old seal is gone even though the tree still matches it exactly.
        proc = self.sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV,
                          check=EXIT_REFUSED)
        self.assertIn("requires receipt.green", proc.stderr)

        # Re-proving red against a changed test scope reseals a different set.
        self.sb.write("crates/demo/tests/gate.py",
                      support.Sandbox.GATE_SOURCE + "# rescoped\n")
        self.sb.make_red()
        self.red()
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        new_seal = self.state()["frozen"]["manifest_sha256"]
        self.assertNotEqual(new_seal, old_seal, "a void must reseal, not restore")
        self.sb.make_green()
        self.green()

    def test_refuses_in_impl_entered_without_a_seal(self):
        # A gate kind whose implementation stage does not seal would leave
        # green with nothing to compare against; the refusal names that.
        self.sb.wf("advance", "WO-001", "--to", "red",
                   "--reason", "reopened", check=EXIT_OK)
        self.red()
        path = self.sb.root / "gate-kinds" / "tdd.json"
        spec = canonical.loads(path.read_bytes())
        spec["stages"][2]["seals_frozen_set"] = False
        spec["version"] = 2
        (self.sb.root / "gate-kinds" / "tdd@2.json").write_bytes(canonical.dumpb(spec))
        # gate-kinds is tracked source of truth, not wf's own export, so a new
        # spec file is a dirty tree until it is committed.
        self.sb.commit_all("sandbox: register tdd@2")
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-002", "--kind", "tdd", "--objective", "unsealed",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-002", check=EXIT_OK)
        self.sb.wf("red", "WO-002", "--", *support.Sandbox.GATE_ARGV, check=EXIT_OK)
        self.sb.wf("advance", "WO-002", check=EXIT_OK)
        self.sb.make_green()
        proc = self.sb.wf("green", "WO-002", "--", *support.Sandbox.GATE_ARGV,
                          check=EXIT_REFUSED)
        self.assertIn("a frozen set is sealed", proc.stderr)


class NextSuggestsTheGate(GateCase):
    def test_next_names_the_red_command_from_the_build_check(self):
        body = json.loads(self.sb.wf("--json", "next", "WO-001", check=EXIT_OK).stdout)
        self.assertEqual(body["missing"], ["receipt.red"])
        support.assert_runnable(self, body["advances"])
        self.assertEqual(body["advances"][-6:],
                         ["red", "WO-001", "--", "cargo", "test", "--workspace"])
        self.assertTrue(body["advances_complete"])

    def test_next_names_the_frozen_argv_for_green(self):
        self.red()
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        body = json.loads(self.sb.wf("--json", "next", "WO-001", check=EXIT_OK).stdout)
        self.assertEqual(body["missing"], ["receipt.green"])
        support.assert_runnable(self, body["advances"])
        tail = ["green", "WO-001", "--"] + support.Sandbox.GATE_ARGV
        self.assertEqual(body["advances"][-len(tail):], tail)
        self.assertTrue(body["advances_complete"])


if __name__ == "__main__":
    unittest.main()
