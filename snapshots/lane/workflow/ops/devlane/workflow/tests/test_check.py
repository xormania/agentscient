"""check — registered checks, the security class, and --verify-only (PLAN §3.4).

Written before the verb exists. Security is not special-cased in the engine:
a security stage is a stage whose spec requires receipts from checks of
class `security`, and the scanners themselves are argv templates in data.
"""

import json
import unittest

import support
from support import SandboxCase
import canonical
from errors import EXIT_OK, EXIT_REFUSED


def spec_with_checks(checks, stages=None, version=2, kind="tdd"):
    return {
        "kind": kind,
        "version": version,
        "stages": stages or [
            {"name": "spec", "leave_requires": []},
            {"name": "gate", "leave_requires": ["receipt.check"]},
            {"name": "done", "leave_requires": []},
        ],
        "test_scope": [],
        "harness_scope": [],
        "checks": checks,
    }


class CheckCase(SandboxCase):
    """A work order whose current stage is gated on a check receipt."""

    CHECKS = [
        {"name": "passes", "class": "build", "argv": ["python3", "-c", "raise SystemExit(0)"]},
        {"name": "fails", "class": "build", "argv": ["python3", "-c", "raise SystemExit(3)"]},
        {"name": "scan", "class": "security",
         "argv": ["python3", "-c", "print('no findings')"]},
    ]

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        path = self.sb.root / "gate-kinds" / "tdd@2.json"
        path.write_bytes(canonical.dumpb(spec_with_checks(self.CHECKS)))
        self.sb.commit_all("sandbox: register tdd@2 with checks")
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "checks",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)   # -> gate

    def check(self, name, *extra, check=EXIT_OK):
        proc = self.sb.wf("--json", "check", "WO-001", name, *extra, check=check)
        return proc

    def state(self):
        return json.loads(self.sb.wf("--json", "status", "WO-001", check=EXIT_OK).stdout)

    def events(self):
        raw = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001", check=EXIT_OK).stdout)
        return support.without_binds(raw["events"])


class Recording(CheckCase):
    def test_starts_gated_on_a_check_receipt(self):
        self.assertEqual(self.state()["stage"], "gate")
        self.assertEqual(self.state()["missing"], ["receipt.check"])

    def test_a_passing_check_records_a_satisfying_receipt(self):
        body = json.loads(self.check("passes").stdout)
        self.assertEqual(body["exit_code"], 0)
        self.assertTrue(body["satisfies"])
        receipt = self.events()[-1]
        self.assertEqual(receipt["type"], "receipt.check")
        self.assertEqual(receipt["check"], "passes")
        self.assertEqual(receipt["class"], "build")
        self.assertEqual(receipt["argv"], ["python3", "-c", "raise SystemExit(0)"])
        self.assertEqual(self.state()["missing"], [])

    def test_a_failing_check_is_recorded_and_does_not_satisfy(self):
        # Records are evidence: a failed scan is important evidence, and
        # recording it is not the same as it counting as a pass.
        proc = self.check("fails", check=EXIT_OK)
        body = json.loads(proc.stdout)
        self.assertEqual(body["exit_code"], 3)
        self.assertFalse(body["satisfies"])
        receipt = self.events()[-1]
        self.assertEqual(receipt["type"], "receipt.check")
        self.assertFalse(receipt["satisfies"])
        self.assertEqual(self.state()["missing"], ["receipt.check"],
                         "a failed check must not satisfy the stage")

    def test_a_failed_check_does_not_let_the_stage_be_left(self):
        self.check("fails")
        proc = self.sb.wf("advance", "WO-001", check=EXIT_REFUSED)
        self.assertIn("receipt.check", proc.stderr)

    def test_a_passing_check_does_let_the_stage_be_left(self):
        self.check("passes")
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.assertEqual(self.state()["stage"], "done")

    def test_the_receipt_carries_the_same_evidence_shape_as_red_and_green(self):
        self.check("passes")
        receipt = self.events()[-1]
        for field in ("stage", "check", "class", "argv", "cwd", "exit_code",
                      "duration_ms", "stdout_sha256", "stderr_sha256",
                      "head_sha", "tree_dirty", "agent", "sources"):
            self.assertIn(field, receipt, field)

    def test_the_class_comes_from_the_spec_not_from_the_engine(self):
        self.check("scan")
        self.assertEqual(self.events()[-1]["class"], "security")

    def test_an_unregistered_check_refuses_and_names_the_registered_ones(self):
        proc = self.sb.wf("check", "WO-001", "nosuch", check=EXIT_REFUSED)
        self.assertIn("registered by the gate kind", proc.stderr)
        self.assertIn("passes", proc.stderr)
        self.assertIn("scan", proc.stderr)

    def test_an_explicit_command_overrides_the_template(self):
        body = json.loads(
            self.check("passes", "--", "python3", "-c", "raise SystemExit(7)").stdout
        )
        self.assertEqual(body["exit_code"], 7)
        self.assertEqual(self.events()[-1]["argv"],
                         ["python3", "-c", "raise SystemExit(7)"])

    def test_a_dirty_tree_is_refused_like_any_other_receipt(self):
        self.sb.write("scratch.txt", "uncommitted\n")
        proc = self.sb.wf("check", "WO-001", "passes", check=EXIT_REFUSED)
        self.assertIn("working tree is clean", proc.stderr)


class VerifyOnly(CheckCase):
    """CI mode: run the registered command, record nothing, exit meaningfully."""

    def test_records_nothing_and_propagates_a_passing_exit(self):
        before = len(self.events())
        proc = self.sb.wf("check", "WO-001", "passes", "--verify-only", check=EXIT_OK)
        self.assertEqual(len(self.events()), before, "CI must originate no state")
        self.assertNotIn("receipt.check", self.state()["satisfied"])
        self.assertEqual(proc.returncode, EXIT_OK)

    def test_propagates_a_failing_exit(self):
        proc = self.sb.wf("check", "WO-001", "fails", "--verify-only")
        self.assertNotEqual(proc.returncode, EXIT_OK)

    def test_verify_only_does_not_need_a_work_order(self):
        # The CI matrix runs checks against the tree, not against a chain.
        proc = self.sb.wf("check", "--verify-only", "--kind", "tdd", "passes",
                          check=EXIT_OK)
        self.assertEqual(proc.returncode, EXIT_OK)

    def test_verify_only_leaves_the_tree_untouched(self):
        # The export already carries one pending bind from setUp (PLAN §3.6),
        # so the question is whether --verify-only *adds* to the tree.
        before = self.sb._git("status", "--porcelain")
        before_head = self.sb.head()
        self.sb.wf("check", "WO-001", "passes", "--verify-only", check=EXIT_OK)
        self.assertEqual(self.sb._git("status", "--porcelain"), before)
        self.assertEqual(self.sb.head(), before_head, "CI mode must not commit")


class SecurityStage(SandboxCase):
    """A security stage is a stage whose spec requires a security-class check."""

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        spec = spec_with_checks(
            [
                {"name": "scan", "class": "security",
                 "argv": ["python3", "-c", "raise SystemExit(0)"]},
                {"name": "build", "class": "build",
                 "argv": ["python3", "-c", "raise SystemExit(0)"]},
            ],
            stages=[
                {"name": "spec", "leave_requires": []},
                {"name": "security", "leave_requires": ["receipt.check:security"]},
                {"name": "done", "leave_requires": []},
            ],
        )
        (self.sb.root / "gate-kinds" / "tdd@2.json").write_bytes(canonical.dumpb(spec))
        self.sb.commit_all("sandbox: register a security stage")
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "sec",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)

    def state(self):
        return json.loads(self.sb.wf("--json", "status", "WO-001", check=EXIT_OK).stdout)

    def test_a_build_class_check_does_not_satisfy_a_security_requirement(self):
        self.sb.wf("check", "WO-001", "build", check=EXIT_OK)
        self.assertEqual(self.state()["missing"], ["receipt.check:security"])
        proc = self.sb.wf("advance", "WO-001", check=EXIT_REFUSED)
        self.assertIn("security", proc.stderr)

    def test_a_security_class_check_does(self):
        self.sb.wf("check", "WO-001", "scan", check=EXIT_OK)
        self.assertEqual(self.state()["missing"], [])
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.assertEqual(self.state()["stage"], "done")


class SeededSecurityChecks(SandboxCase):
    """D8: the day-one security seed ships as data, not as engine code."""

    def test_the_shipped_gate_kinds_register_a_security_class_check(self):
        for kind in ("tdd", "artifact"):
            with self.subTest(kind=kind):
                spec = canonical.loads(
                    (support.WF_DIR / "gate-kinds" / f"{kind}.json").read_bytes()
                )
                classes = {c["class"] for c in spec.get("checks", [])}
                self.assertIn("security", classes,
                              f"{kind} must seed at least one security check")

    def test_the_vocabulary_wall_check_is_registered_and_runnable(self):
        spec = canonical.loads(
            (support.WF_DIR / "gate-kinds" / "artifact.json").read_bytes()
        )
        names = {c["name"] for c in spec.get("checks", [])}
        self.assertIn("vocabulary-wall", names)


if __name__ == "__main__":
    unittest.main()
