"""The diagnostics feed — a class, not machinery (PLAN §9).

"Diagnostics snapshots recorded as receipt.check receipts (class
diagnostics) — same evidence shape, no new machinery." The load-bearing test
is not that `diagnostics` works; it is that the engine never learned the
word, which is §6's zero-engine-change requirement.
"""

import json
import subprocess
import sys
import unittest

import support
from support import SandboxCase
import canonical
from errors import EXIT_OK, EXIT_REFUSED, EXIT_INTEGRITY

CHECK = support.WF_DIR / "checks" / "diagnostics.py"


def producer(body: str):
    return ["python3", "-c", body]


def kind_with(class_name, argv, stage_requires):
    return {
        "kind": "tdd", "version": 1,
        "stages": [
            {"name": "spec", "leave_requires": []},
            {"name": "gate", "leave_requires": [stage_requires]},
            {"name": "done", "leave_requires": []},
        ],
        "test_scope": [], "harness_scope": [],
        "checks": [
            {"name": "snapshot", "class": class_name, "argv": argv},
            {"name": "other", "class": "build",
             "argv": ["python3", "-c", "raise SystemExit(0)"]},
        ],
    }


class TheClassIsData(SandboxCase):
    """The engine must not know what "diagnostics" means."""

    def register(self, class_name):
        raw = kind_with(
            class_name,
            ["python3", "-c", "raise SystemExit(0)"],
            f"receipt.check:{class_name}",
        )
        (self.sb.root / "gate-kinds" / "tdd.json").write_bytes(canonical.dumpb(raw))
        self.sb.commit_all(f"sandbox: register a {class_name} class")
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)

    def state(self):
        return json.loads(
            self.sb.wf("--json", "status", "WO-001", check=EXIT_OK).stdout)

    def drive(self, class_name):
        self.sb.wf("init", check=EXIT_OK)
        self.register(class_name)
        self.assertEqual(self.state()["missing"], [f"receipt.check:{class_name}"])
        self.sb.wf("check", "WO-001", "snapshot", check=EXIT_OK)
        self.assertEqual(self.state()["missing"], [])
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        return self.state()["stage"]

    def test_a_diagnostics_class_gates_a_stage(self):
        self.assertEqual(self.drive("diagnostics"), "done")

    def test_a_class_nobody_has_ever_named_behaves_identically(self):
        # This is the real test of §6: if the engine had special-cased
        # "diagnostics", an invented class would not work.
        self.assertEqual(self.drive("kumquat"), "done")

    def test_the_word_diagnostics_appears_in_no_engine_module(self):
        modules = [p for p in support.WF_DIR.glob("*.py")]
        self.assertGreater(len(modules), 5)
        offenders = []
        for path in modules:
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if "diagnostic" in line.lower() and not line.strip().startswith("#"):
                    offenders.append(f"{path.name}:{number}: {line.strip()[:70]}")
        self.assertEqual(offenders, [],
                         "a check class must be data the engine never names")

    def test_a_wrong_class_does_not_satisfy(self):
        self.sb.wf("init", check=EXIT_OK)
        self.register("diagnostics")
        self.sb.wf("check", "WO-001", "other", check=EXIT_OK)
        self.assertEqual(self.state()["missing"], ["receipt.check:diagnostics"])
        self.sb.wf("advance", "WO-001", check=EXIT_REFUSED)


class RecordedLikeAnyReceipt(SandboxCase):
    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        raw = kind_with("diagnostics",
                        ["python3", str(CHECK), "--", "python3", "-c",
                         "print('{\"severity\":\"warning\",\"message\":\"m\"}')"],
                        "receipt.check:diagnostics")
        (self.sb.root / "gate-kinds" / "tdd.json").write_bytes(canonical.dumpb(raw))
        self.sb.commit_all("sandbox: diagnostics kind")
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)

    def events(self):
        raw = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001", check=EXIT_OK).stdout)
        return support.without_binds(raw["events"])

    def test_the_snapshot_lands_in_the_object_store(self):
        self.sb.wf("check", "WO-001", "snapshot", check=EXIT_OK)
        receipt = self.events()[-1]
        self.assertEqual(receipt["type"], "receipt.check")
        self.assertEqual(receipt["class"], "diagnostics")
        digest = receipt["stdout_sha256"]
        stored = self.sb.root / "objects" / digest[:2] / digest
        self.assertTrue(stored.exists())
        self.assertIn(b"diagnostics:", stored.read_bytes())

    def test_deep_verify_re_verifies_it_like_any_other_check(self):
        self.sb.wf("check", "WO-001", "snapshot", check=EXIT_OK)
        body = json.loads(self.sb.wf("--json", "verify", "--deep",
                                     check=EXIT_OK).stdout)
        self.assertGreaterEqual(body["work_orders"][0]["receipts"]["checked"], 1)

    def test_a_forged_diagnostics_receipt_is_caught(self):
        self.sb.wf("check", "WO-001", "snapshot", check=EXIT_OK)
        events = json.loads(
            self.sb.wf("--json", "log", "--full", "--all", "WO-001", check=EXIT_OK).stdout)["events"]
        receipt = next(e for e in events if e["type"] == "receipt.check")
        decoy = receipt["stdout_sha256"]
        forged = support.relink_chain(
            "WO-001",
            [{**e, "test_manifest_sha256": decoy}
             if e["type"] == "receipt.check" else e for e in events])
        payload = support.chain_bytes_for(forged)
        current = self.sb.chain_file("WO-001").read_bytes()
        support.plant_bytes(
            self.sb.chain_file("WO-001"), lambda raw: payload,
            expect="edit" if len(payload) == len(current)
                   else ("grow" if len(payload) > len(current) else "shrink"),
            recognisable=lambda raw: support.jsonl_lines(raw) == len(events))
        self.sb.commit_all("sandbox: forge")
        self.sb.db.unlink()
        self.sb.wf("init", "--rebuild", check=EXIT_OK)
        self.sb.wf("verify", check=EXIT_OK)
        proc = self.sb.wf("verify", "--deep")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)


class TheProducerParser(unittest.TestCase):
    """Proven to fire, not merely to stay quiet."""

    def run_it(self, *args):
        return subprocess.run([sys.executable, str(CHECK), *args],
                              capture_output=True, text=True)

    def test_fires_on_an_error(self):
        proc = self.run_it("--", *producer(
            "print('{\"severity\":\"error\",\"message\":\"boom\"}')"))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)

    def test_reads_the_cargo_nested_shape(self):
        proc = self.run_it("--", *producer(
            "print('{\"reason\":\"compiler-message\",\"message\":"
            "{\"level\":\"error\",\"rendered\":\"E0308\"}}')"))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)

    def test_reads_numeric_lsp_severities(self):
        proc = self.run_it("--", *producer("print('{\"severity\":1}')"))
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_warnings_alone_do_not_fail(self):
        proc = self.run_it("--", *producer(
            "print('{\"level\":\"warning\",\"message\":\"m\"}')"))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("warning=1", proc.stdout)

    def test_fail_on_warning_does(self):
        proc = self.run_it("--fail-on", "warning", "--", *producer(
            "print('{\"level\":\"warning\",\"message\":\"m\"}')"))
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_a_producer_that_cannot_run_is_not_clean(self):
        # "No diagnostics" and "nothing ran" must never be the same answer.
        proc = self.run_it("--", "no-such-binary-xyz")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("could not run", proc.stderr)

    def test_unparsable_output_is_reported_not_swallowed(self):
        proc = self.run_it("--", *producer("print('not json at all')"))
        self.assertIn("unparsed=1", proc.stdout)

    def test_no_producer_is_a_usage_error(self):
        self.assertEqual(self.run_it().returncode, 64)

    def test_an_unknown_severity_threshold_is_a_usage_error(self):
        proc = self.run_it("--fail-on", "catastrophe", "--", *producer("print('{}')"))
        self.assertEqual(proc.returncode, 64)

    def test_a_clean_producer_says_what_it_read(self):
        proc = self.run_it("--", *producer("pass"))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("none", proc.stdout)


class TheShippedRegistration(unittest.TestCase):
    def test_tdd_registers_a_diagnostics_check_that_is_not_in_ci(self):
        spec = canonical.loads(
            (support.WF_DIR / "gate-kinds" / "tdd.json").read_bytes())
        entry = [c for c in spec["checks"] if c["class"] == "diagnostics"]
        self.assertEqual(len(entry), 1)
        workspace = (
            support.WF_DIR.parent.parent.parent / "Cargo.toml").is_file()
        if workspace:
            # the flip is two-sided (test_ci_shape/test_gate_binding):
            # with a workspace, staying out of CI is the defect
            self.assertIs(entry[0].get("ci"), True,
                          "a Cargo workspace exists; flip diagnostics"
                          " into the matrix with it")
        else:
            self.assertFalse(entry[0].get("ci", False),
                             "it drives cargo, which has no workspace yet")
        self.assertIn("diagnostics.py", " ".join(entry[0]["argv"]))


class TypeFilterIsExactNotAPrefix(SandboxCase):
    """An audit finding on the drafts: no test distinguished exact matching
    from `startswith`, and a prefix implementation would have passed every
    type test in the suite."""

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "artifact", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("marker", "WO-001", "open", "F1", check=EXIT_OK)
        self.sb.wf("marker", "WO-001", "close", "F1", check=EXIT_OK)

    def matched(self, *args):
        body = json.loads(
            self.sb.wf("--json", "log", "--full", "--all", "WO-001", *args, check=EXIT_OK).stdout)
        return body["matched"], body["considered"]

    def test_a_sibling_type_is_not_matched(self):
        matched, considered = self.matched("--type", "marker.open")
        self.assertEqual(matched, 1, "marker.close must not match marker.open")
        self.assertGreater(considered, matched)

    def test_a_bare_prefix_refuses_rather_than_matching_every_receipt(self):
        # `receipt.` is not a type. A startswith implementation would answer
        # it with every receipt in the chain, which is a filter inventing a
        # result rather than refusing a typo.
        proc = self.sb.wf("log", "--full", "--all", "WO-001", "--type", "receipt.")
        self.assertEqual(proc.returncode, EXIT_REFUSED, proc.stderr)

    def test_a_truncated_type_refuses(self):
        for bad in ("marker", "stage", "receipt", "outcom"):
            with self.subTest(bad=bad):
                self.assertEqual(
                    self.sb.wf("log", "--full", "--all", "WO-001", "--type", bad).returncode,
                    EXIT_REFUSED)
