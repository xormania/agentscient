"""Findings from the independent review of the Slice 2 tests.

Two reviewers (GPT-5 Codex and Grok 4.6) read `test_claims`, `test_check` and
`test_marker` *before* the implementation existed. These are the guards for
what they found. Each is written to fail against the code as it stood at
`2b38828` and pass after the fix.
"""

import json
import os
import subprocess
import sys
import unittest

import support
from support import SandboxCase
import canonical
from errors import EXIT_OK, EXIT_REFUSED, EXIT_INTEGRITY, EXIT_CLAIMED


def spec(kind="tdd", version=1, stages=None, checks=None):
    return {
        "kind": kind, "version": version,
        "stages": stages or [
            {"name": "spec", "leave_requires": []},
            {"name": "security", "leave_requires": ["receipt.check:security"]},
            {"name": "done", "leave_requires": []},
        ],
        "test_scope": [], "harness_scope": [],
        "checks": checks if checks is not None else [
            {"name": "scan", "class": "security",
             "argv": ["python3", "-c", "raise SystemExit(1)"]},
            {"name": "ok-scan", "class": "security",
             "argv": ["python3", "-c", "raise SystemExit(0)"]},
        ],
    }


class SecurityGateCase(SandboxCase):
    SPEC = None

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        (self.sb.root / "gate-kinds" / "tdd.json").write_bytes(
            canonical.dumpb(self.SPEC or spec())
        )
        self.sb.commit_all("sandbox: register the gate kind")
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)

    def state(self):
        return json.loads(self.sb.wf("--json", "status", "WO-001", check=EXIT_OK).stdout)

    def events(self):
        raw = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001", check=EXIT_OK).stdout)
        return support.without_binds(raw["events"])


class OverrideCannotImpersonateTheCheck(SecurityGateCase):
    """[P1, both reviewers] A substituted command must not earn the check's class.

    Reproduced at 2b38828: the registered `scan` exits 1, but
    `wf check WO-001 scan -- <anything passing>` recorded class=security and
    satisfies=true, clearing the security gate while the scanner never ran.
    """

    def test_an_overridden_command_does_not_satisfy_the_gate(self):
        body = json.loads(
            self.sb.wf("--json", "check", "WO-001", "scan", "--",
                       "python3", "-c", "raise SystemExit(0)", check=EXIT_OK).stdout
        )
        self.assertFalse(body["satisfies"],
                         "running something else is not running the check")
        self.assertTrue(body["overridden"])
        self.assertEqual(self.state()["missing"], ["receipt.check:security"])

    def test_the_stage_still_cannot_be_left(self):
        self.sb.wf("check", "WO-001", "scan", "--",
                   "python3", "-c", "raise SystemExit(0)", check=EXIT_OK)
        proc = self.sb.wf("advance", "WO-001", check=EXIT_REFUSED)
        self.assertIn("receipt.check:security", proc.stderr)

    def test_the_substitution_is_recorded_so_a_reviewer_can_see_it(self):
        self.sb.wf("check", "WO-001", "scan", "--",
                   "python3", "-c", "raise SystemExit(0)", check=EXIT_OK)
        receipt = self.events()[-1]
        self.assertTrue(receipt["overridden"])
        self.assertEqual(receipt["registered_argv"],
                         ["python3", "-c", "raise SystemExit(1)"])
        self.assertNotEqual(receipt["argv"], receipt["registered_argv"])
        self.assertFalse(receipt["satisfies"])

    def test_running_the_registered_check_unchanged_does_satisfy(self):
        body = json.loads(
            self.sb.wf("--json", "check", "WO-001", "ok-scan", check=EXIT_OK).stdout
        )
        self.assertTrue(body["satisfies"])
        self.assertFalse(body["overridden"])
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.assertEqual(self.state()["stage"], "done")

    def test_an_argv_identical_to_the_template_is_not_an_override(self):
        body = json.loads(
            self.sb.wf("--json", "check", "WO-001", "ok-scan", "--",
                       "python3", "-c", "raise SystemExit(0)", check=EXIT_OK).stdout
        )
        self.assertFalse(body["overridden"], "the same argv is not a substitution")
        self.assertTrue(body["satisfies"])


class VerifyOnlyExitCodes(SecurityGateCase):
    """[P1 Grok] A wrapped command's exit must not collide with wf's own map."""

    SPEC = spec(stages=[
        {"name": "spec", "leave_requires": []},
        {"name": "security", "leave_requires": ["receipt.check:build"]},
        {"name": "done", "leave_requires": []},
    ], checks=[
        {"name": "exit3", "class": "build",
         "argv": ["python3", "-c", "raise SystemExit(3)"]},
        {"name": "exit2", "class": "build",
         "argv": ["python3", "-c", "raise SystemExit(2)"]},
        {"name": "exit64", "class": "build",
         "argv": ["python3", "-c", "raise SystemExit(64)"]},
        {"name": "passes", "class": "build",
         "argv": ["python3", "-c", "raise SystemExit(0)"]},
    ])

    def test_a_wrapped_exit_three_does_not_read_as_claim_held(self):
        proc = self.sb.wf("check", "WO-001", "exit3", "--verify-only")
        self.assertEqual(proc.returncode, EXIT_REFUSED,
                         "3 means 'claimed by another agent', never 'the check failed'")
        self.assertNotEqual(proc.returncode, EXIT_CLAIMED)

    def test_a_wrapped_exit_two_does_not_read_as_integrity(self):
        proc = self.sb.wf("check", "WO-001", "exit2", "--verify-only")
        self.assertEqual(proc.returncode, EXIT_REFUSED)
        self.assertNotEqual(proc.returncode, EXIT_INTEGRITY)

    def test_a_wrapped_exit_sixtyfour_does_not_read_as_usage(self):
        proc = self.sb.wf("check", "WO-001", "exit64", "--verify-only")
        self.assertEqual(proc.returncode, EXIT_REFUSED)

    def test_the_real_exit_code_is_still_reported(self):
        body = json.loads(
            self.sb.wf("--json", "check", "WO-001", "exit3", "--verify-only").stdout
        )
        self.assertEqual(body["exit_code"], 3, "the wrapped code is evidence")
        self.assertFalse(body["recorded"])

    def test_a_passing_check_exits_zero(self):
        self.assertEqual(
            self.sb.wf("check", "WO-001", "passes", "--verify-only").returncode, EXIT_OK
        )


class VerifyOnlyOriginatesNothing(SecurityGateCase):
    """[P2, both reviewers] CI must leave the whole state untouched, not just the chain."""

    def snapshot(self):
        import hashlib

        state = {}
        for name in ("chains", "attempts", "objects"):
            root = self.sb.root / name
            state[name] = sorted(
                (p.relative_to(root).as_posix(),
                 hashlib.sha256(p.read_bytes()).hexdigest())
                for p in root.rglob("*") if p.is_file()
            ) if root.exists() else []
        state["meta"] = (self.sb.root / "meta.json").read_bytes().decode()
        state["db"] = hashlib.sha256(self.sb.db.read_bytes()).hexdigest() \
            if self.sb.db.exists() else None
        state["head"] = self.sb.head()
        state["porcelain"] = self.sb._git("status", "--porcelain")
        conn_tables = {}
        import sqlite3

        conn = sqlite3.connect(str(self.sb.db))
        try:
            for table in ("events", "attempts", "sessions", "claims", "artifacts",
                          "work_orders", "wo_state"):
                conn_tables[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()
        state["tables"] = conn_tables
        return state

    def test_nothing_at_all_changes(self):
        before = self.snapshot()
        self.sb.wf("check", "WO-001", "ok-scan", "--verify-only", check=EXIT_OK)
        after = self.snapshot()
        for key in ("chains", "attempts", "objects", "meta", "head", "porcelain",
                    "tables"):
            self.assertEqual(before[key], after[key], f"--verify-only changed {key}")

    def test_not_even_a_failing_one(self):
        before = self.snapshot()
        self.sb.wf("check", "WO-001", "scan", "--verify-only")
        after = self.snapshot()
        self.assertEqual(before["tables"], after["tables"])
        self.assertEqual(before["chains"], after["chains"])


class RequirementGrammar(SandboxCase):
    """[P1, both reviewers] The colon grammar must be validated, not assumed."""

    def register(self, requirement):
        # No init before writing: a previous iteration may have left a spec
        # that init correctly refuses, and that refusal is not this call's.
        raw = spec(stages=[
            {"name": "spec", "leave_requires": []},
            {"name": "gate", "leave_requires": [requirement]},
        ])
        (self.sb.root / "gate-kinds" / "tdd.json").write_bytes(canonical.dumpb(raw))
        self.sb.commit_all("sandbox: register")
        return self.sb.wf("init")

    def test_a_malformed_requirement_refuses_rather_than_silently_never_matching(self):
        for bad in ("receipt.check:", ":security", "receipt.check::security", ":"):
            with self.subTest(bad=bad):
                proc = self.register(bad)
                self.assertEqual(proc.returncode, EXIT_REFUSED, proc.stderr)
                self.assertIn("class-qualified", proc.stderr)

    def test_a_well_formed_requirement_is_accepted(self):
        self.assertEqual(self.register("receipt.check:security").returncode, EXIT_OK)
        self.assertEqual(self.register("receipt.green").returncode, EXIT_OK)


class MarkerBlockingIsSpecData(SandboxCase):
    """[P1 Grok] The engine must honour the flag, not the stage name 'fix'."""

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)

    def register(self, stages):
        raw = spec(kind="artifact", stages=stages, checks=[])
        (self.sb.root / "gate-kinds" / "artifact.json").write_bytes(
            canonical.dumpb(raw)
        )
        self.sb.commit_all("sandbox: register artifact")
        self.sb.wf("init", check=EXIT_OK)

    def test_a_stage_not_called_fix_is_still_held_by_the_flag(self):
        self.register([
            {"name": "draft", "leave_requires": []},
            {"name": "rework", "leave_requires": [], "blocked_by_open_markers": True},
            {"name": "done", "leave_requires": []},
        ])
        self.sb.wf("open", "WO-001", "--kind", "artifact", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)   # -> rework
        self.sb.wf("marker", "WO-001", "open", "F1", check=EXIT_OK)
        proc = self.sb.wf("advance", "WO-001", check=EXIT_REFUSED)
        self.assertIn("F1", proc.stderr)

    def test_a_stage_called_fix_without_the_flag_is_not_held(self):
        self.register([
            {"name": "draft", "leave_requires": []},
            {"name": "fix", "leave_requires": []},
            {"name": "done", "leave_requires": []},
        ])
        self.sb.wf("open", "WO-002", "--kind", "artifact", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-002", check=EXIT_OK)   # -> fix
        self.sb.wf("marker", "WO-002", "open", "F1", check=EXIT_OK)
        self.sb.wf("advance", "WO-002", check=EXIT_OK)
        self.assertEqual(
            json.loads(self.sb.wf("--json", "status", "WO-002").stdout)["stage"], "done"
        )


class TheReviewCyclePath(SandboxCase):
    """[P1, both reviewers] The path PLAN §3.5 actually describes.

    "Review findings open markers; fix cannot be left while markers from the
    current review cycle are open." The marker is opened *during review*, and
    the outcome then moves the work order to fix — that ordering was never
    exercised.
    """

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-009", "--kind", "artifact", "--objective", "doc",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-009", check=EXIT_OK)   # -> review

    def stage(self):
        return json.loads(
            self.sb.wf("--json", "status", "WO-009", check=EXIT_OK).stdout)["stage"]

    def test_a_marker_opened_in_review_holds_fix_shut_after_the_finding(self):
        self.sb.wf("marker", "WO-009", "open", "F1", "--note", "vague objective",
                   check=EXIT_OK)
        self.assertEqual(self.stage(), "review")
        self.sb.wf("outcome", "WO-009", "finding", "--by", "reviewer", check=EXIT_OK)
        self.assertEqual(self.stage(), "fix")
        proc = self.sb.wf("advance", "WO-009", check=EXIT_REFUSED)
        self.assertIn("F1", proc.stderr)
        self.sb.wf("marker", "WO-009", "close", "F1", check=EXIT_OK)
        self.sb.wf("advance", "WO-009", check=EXIT_OK)
        self.assertEqual(self.stage(), "review")

    def test_a_blocked_stage_cannot_be_escaped_by_re_entering_an_earlier_one(self):
        # advance --to is the correction path; it must not become the way
        # around a stage the spec is holding shut.
        self.sb.wf("outcome", "WO-009", "finding", "--by", "r", check=EXIT_OK)
        self.sb.wf("marker", "WO-009", "open", "F2", check=EXIT_OK)
        self.assertEqual(self.stage(), "fix")
        proc = self.sb.wf("advance", "WO-009", "--to", "draft",
                          "--reason", "start over", check=EXIT_REFUSED)
        self.assertIn("F2", proc.stderr)

    def test_markers_survive_a_rebuild_because_they_are_chain_evidence(self):
        self.sb.wf("marker", "WO-009", "open", "F3", check=EXIT_OK)
        self.sb.db.unlink()
        self.sb.wf("init", "--rebuild", check=EXIT_OK)
        body = json.loads(self.sb.wf("--json", "status", "WO-009").stdout)
        self.assertEqual(body["open_markers"], ["F3"])


class ClaimGatingCoversEveryAppendingVerb(SandboxCase):
    """[P2 Grok] Only advance was tested; exit 3 must hold for all of them."""

    OTHER = "Other Agent <noreply@example.invalid>"

    def setUp(self):
        super().setUp()
        self.sb.seed_project()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)   # -> red
        self.sb.wf("claim", "WO-001", check=EXIT_OK)

    def test_every_chain_appending_verb_refuses_for_another_agent(self):
        cases = {
            "advance": ["advance", "WO-001"],
            "red": ["red", "WO-001", "--", *support.Sandbox.GATE_ARGV],
            "outcome": ["outcome", "WO-001", "accepted", "--by", "x"],
            "marker": ["marker", "WO-001", "open", "F1"],
            "check": ["check", "WO-001", "cargo-test"],
        }
        for verb, argv in cases.items():
            with self.subTest(verb=verb):
                proc = self.sb.wf(*argv, agent=self.OTHER)
                self.assertEqual(proc.returncode, EXIT_CLAIMED,
                                 f"{verb}: {proc.stderr}")

    def test_the_holder_is_not_blocked(self):
        self.sb.wf("marker", "WO-001", "open", "F1", check=EXIT_OK)


class SourcedVerbInjectionIsPrecise(SandboxCase):
    """[P3 Grok] The helper matched the bare word 'open' anywhere in argv.

    `wf marker WO-1 open F1` contains "open" as the action, so the sandbox's
    convenience default was injecting `--source original` into marker-open and
    not into marker-close — a difference between two tests that was invisible.
    """

    def test_the_helper_keys_on_the_verb_not_on_any_argument(self):
        sb = self.sb
        # marker is a sourced verb since the PR #16 review (its id and note
        # are authored text), so it gets the injection by VERB —
        self.assertIn("--source",
                      sb._with_default_source(["marker", "WO-1", "close", "F1"]))
        # — while a reading verb stays uninjected even when an argument is
        # spelled like a sourced verb, which is the property under test.
        self.assertEqual(
            sb._with_default_source(["log", "--full", "--all", "WO-1", "--types", "open"]),
            ["log", "--full", "--all", "WO-1", "--types", "open"],
            "the helper must key on the verb, not on any argument",
        )
        self.assertEqual(
            sb._with_default_source(["open", "WO-1", "--kind", "tdd"]),
            ["open", "WO-1", "--kind", "tdd", "--source", "original"],
        )
        self.assertEqual(
            sb._with_default_source(["--json", "outcome", "WO-1", "accepted"]),
            ["--json", "outcome", "WO-1", "accepted", "--source", "original"],
        )


class SeededChecksAreProvenToFire(unittest.TestCase):
    """[P2, both reviewers] A checker proven only on clean input proves nothing."""

    CHECKS = support.WF_DIR / "checks"

    def run_check(self, script, cwd, *args):
        return subprocess.run(
            [sys.executable, str(self.CHECKS / script), *args],
            cwd=str(cwd), capture_output=True, text=True,
        )

    def setUp(self):
        import tempfile
        from pathlib import Path

        self.dir = Path(tempfile.mkdtemp(prefix="wf-checks-"))
        self.addCleanup(__import__("shutil").rmtree, self.dir, True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.dir)], check=True)

    def commit(self):
        subprocess.run(["git", "-C", str(self.dir), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.dir), "-c", "user.email=a@b.c",
             "-c", "user.name=t", "-c", "commit.gpgsign=false",
             "commit", "-qm", "x"], check=True
        )

    def test_the_secret_scan_fires_on_a_planted_credential(self):
        (self.dir / "config.toml").write_text(  # secret-scan: allow
            "key = 'AKIA" + "IOSFODNN7EXAMPLE'\n")
        self.commit()
        proc = self.run_check("secret_scan.py", self.dir)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("AWS access key id", proc.stdout)
        self.assertIn("config.toml", proc.stdout)

    def test_the_secret_scan_fires_on_a_private_key_block(self):
        (self.dir / "id_rsa").write_text(  # secret-scan: allow
            "-----BEGIN RSA PRIVATE" + " KEY-----\nx\n")
        self.commit()
        proc = self.run_check("secret_scan.py", self.dir)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("private key block", proc.stdout)

    def test_the_secret_scan_stays_quiet_on_a_clean_tree(self):
        (self.dir / "README.md").write_text("nothing secret here\n")
        self.commit()
        proc = self.run_check("secret_scan.py", self.dir)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("clean", proc.stdout)

    def test_the_secret_scan_ignores_untracked_files(self):
        (self.dir / "README.md").write_text("clean\n")
        self.commit()
        (self.dir / "scratch.txt").write_text("AKIA" + "IOSFODNN7EXAMPLE\n")  # secret-scan: allow
        proc = self.run_check("secret_scan.py", self.dir)
        self.assertEqual(proc.returncode, 0,
                         "an untracked scratch file must not fail the gate")

    def test_the_vocabulary_wall_fires_on_a_dev_lane_term_in_a_design_file(self):
        (self.dir / "design.md").write_text(
            "The engine records a receipt for each write.\n"
        )
        self.commit()
        proc = self.run_check("vocabulary_wall.py", self.dir)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("receipt", proc.stdout)
        self.assertIn("design.md", proc.stdout)

    def test_the_vocabulary_wall_allows_the_dev_lane_surfaces(self):
        (self.dir / "ops").mkdir()
        (self.dir / "ops" / "notes.md").write_text("the receipt and the gate\n")
        (self.dir / "AGENTS.md").write_text("work orders, gates, receipts\n")
        # Tool-config dot-directories are dev-lane surface too — the wall
        # failed CI the day .claude/ skills first named a work order, and
        # again the day .serena/ memories did.
        (self.dir / ".claude" / "skills" / "tdd").mkdir(parents=True)
        (self.dir / ".claude" / "skills" / "tdd" / "SKILL.md").write_text(
            "run wf red on the work order\n")
        (self.dir / ".serena" / "memories").mkdir(parents=True)
        (self.dir / ".serena" / "memories" / "rules.md").write_text(
            "the work order gates and receipts\n")
        self.commit()
        proc = self.run_check("vocabulary_wall.py", self.dir)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_the_vocabulary_wall_does_not_fire_on_a_word_containing_a_term(self):
        (self.dir / "design.md").write_text(
            "Aggregate staging and chaining are unrelated words.\n"
        )
        self.commit()
        proc = self.run_check("vocabulary_wall.py", self.dir)
        self.assertEqual(proc.returncode, 0, proc.stdout)


if __name__ == "__main__":
    unittest.main()


class CiMatrixCommandForm(SandboxCase):
    """[P1, both reviewers] PLAN §7 runs `wf check --verify-only NAME`, no --kind."""

    def test_the_plans_command_form_works_without_a_kind(self):
        self.sb.wf("init", check=EXIT_OK)
        proc = self.sb.wf("check", "--verify-only", "vocabulary-wall", check=EXIT_OK)
        self.assertEqual(proc.returncode, EXIT_OK)

    def test_an_unregistered_name_refuses_and_lists_what_exists(self):
        self.sb.wf("init", check=EXIT_OK)
        proc = self.sb.wf("check", "--verify-only", "nosuch", check=EXIT_REFUSED)
        self.assertIn("registered by some gate kind", proc.stderr)
        self.assertIn("secret-scan", proc.stderr)

    def test_a_name_two_kinds_define_differently_refuses_rather_than_guessing(self):
        self.sb.wf("init", check=EXIT_OK)
        raw = spec(kind="other", version=1, checks=[
            {"name": "secret-scan", "class": "security",
             "argv": ["python3", "-c", "raise SystemExit(0)"]},
        ])
        (self.sb.root / "gate-kinds" / "other.json").write_bytes(canonical.dumpb(raw))
        self.sb.commit_all("sandbox: a second kind defining the same check name")
        self.sb.wf("init", check=EXIT_OK)
        proc = self.sb.wf("check", "--verify-only", "secret-scan", check=EXIT_REFUSED)
        self.assertIn("identifies one command", proc.stderr)
        self.assertIn("--kind", proc.stderr)

    def test_kind_disambiguates_it(self):
        self.sb.wf("init", check=EXIT_OK)
        raw = spec(kind="other", version=1, checks=[
            {"name": "secret-scan", "class": "security",
             "argv": ["python3", "-c", "raise SystemExit(0)"]},
        ])
        (self.sb.root / "gate-kinds" / "other.json").write_bytes(canonical.dumpb(raw))
        self.sb.commit_all("sandbox: second kind")
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("check", "--verify-only", "--kind", "other", "secret-scan",
                   check=EXIT_OK)


# TheGatesJobRunsRealChecks lived here. It asserted that the WF:gates matrix
# was a hand-written list of registered check names — correct while the matrix
# was static, and wrong the moment PLAN §7's "derive the matrix from
# `wf status --checks --json`" landed. Its two questions are both asked more
# precisely in test_ci_shape.DerivedMatrix, which additionally asserts that the
# list is *not* hand-written, that an empty matrix is guarded, and that a new
# check reaches CI with no code change.


class VerifyOnlyTouchesNoSession(SecurityGateCase):
    """[P2, verifier F2] CI originates no state — sessions included.

    The earlier isolation test compared row *counts*, and setUp had already
    created a session for the test agent, so a write by --verify-only was
    invisible. Reproduced with a distinct agent: `wf check --verify-only`
    under a CI identity created a session row.
    """

    CI_AGENT = "CI Runner <noreply@example.invalid>"

    def sessions(self):
        import sqlite3

        conn = sqlite3.connect(str(self.sb.db))
        try:
            return sorted(conn.execute(
                "SELECT agent, last_seen FROM sessions").fetchall())
        finally:
            conn.close()

    def test_a_ci_identity_leaves_no_session_behind(self):
        before = self.sessions()
        self.sb.wf("check", "WO-001", "ok-scan", "--verify-only",
                   agent=self.CI_AGENT, check=EXIT_OK)
        self.assertEqual(self.sessions(), before,
                         "--verify-only must not record presence")
        self.assertNotIn(self.CI_AGENT, [a for a, _ in self.sessions()])

    def test_the_no_work_order_form_leaves_none_either(self):
        before = self.sessions()
        self.sb.wf("check", "--verify-only", "--kind", "tdd", "ok-scan",
                   agent=self.CI_AGENT, check=EXIT_OK)
        self.assertEqual(self.sessions(), before)

    def test_a_recording_verb_still_does_record_presence(self):
        # The control: presence is still tracked for real work, or this fix
        # would have quietly disabled sessions everywhere.
        self.sb.wf("marker", "WO-001", "open", "F1", agent=self.CI_AGENT,
                   check=EXIT_OK)
        self.assertIn(self.CI_AGENT, [a for a, _ in self.sessions()])


class DeepVerifyCoversCheckReceipts(SecurityGateCase):
    """[P2, verifier C2] receipt.check was never re-verified against its tree.

    verify.py only re-hashed receipt.red and receipt.green, so a check
    receipt's manifest — the thing that ties it to a tree state — went
    unexamined by the deep pass.
    """

    def test_a_clean_check_receipt_is_counted_as_re_verified(self):
        self.sb.wf("check", "WO-001", "ok-scan", check=EXIT_OK)
        body = json.loads(self.sb.wf("--json", "verify", "--deep",
                                     check=EXIT_OK).stdout)
        entry = body["work_orders"][0]
        self.assertGreaterEqual(entry["receipts"]["checked"], 1,
                                "the check receipt must be re-verified")

    def test_a_forged_check_manifest_is_caught(self):
        self.sb.wf("check", "WO-001", "ok-scan", check=EXIT_OK)
        self.sb.wf("verify", "--deep", check=EXIT_OK)

        events = json.loads(
            self.sb.wf("--json", "log", "--full", "--all", "WO-001", check=EXIT_OK).stdout)["events"]
        receipt = next(e for e in events if e["type"] == "receipt.check")
        decoy = receipt["stdout_sha256"]
        self.assertNotEqual(decoy, receipt["test_manifest_sha256"])

        forged = support.relink_chain(
            "WO-001",
            [{**e, "test_manifest_sha256": decoy}
             if e["type"] == "receipt.check" else e for e in events],
        )
        payload = support.chain_bytes_for(forged)
        current = self.sb.chain_file("WO-001").read_bytes()
        support.plant_bytes(
            self.sb.chain_file("WO-001"), lambda raw: payload,
            expect="edit" if len(payload) == len(current)
                   else ("grow" if len(payload) > len(current) else "shrink"),
            recognisable=lambda raw: support.jsonl_lines(raw) == len(events),
        )
        self.sb.commit_all("sandbox: forge the check manifest")
        self.sb.db.unlink()
        self.sb.wf("init", "--rebuild", check=EXIT_OK)

        self.sb.wf("verify", check=EXIT_OK)   # per-row checks all pass
        proc = self.sb.wf("verify", "--deep")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("does not re-hash from the tree it names", proc.stderr)


class ClaimAcquisitionIsAtomic(SandboxCase):
    """[P1, verifier D1a] Two agents could both hold one work order.

    coord.claim did SELECT then UPSERT in separate implicit transactions, and
    the UPSERT carried no WHERE guard — `DO UPDATE SET agent=excluded.agent`
    overwrites a live claim held by anyone. Sequentially the precondition
    check hid it; concurrently the verifier measured both processes exiting 0
    in 16 of 25 races.

    There was no concurrency test anywhere in the suite, which is why this
    shipped.
    """

    ROUNDS = 8

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)

    def race(self, wo, agents):
        import threading

        barrier = threading.Barrier(len(agents))
        results = {}

        def go(agent):
            barrier.wait()
            results[agent] = self.sb.wf("claim", wo, "--ttl", "1h",
                                        agent=agent).returncode

        threads = [threading.Thread(target=go, args=(a,)) for a in agents]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results

    def holders(self):
        import sqlite3

        conn = sqlite3.connect(str(self.sb.db))
        try:
            return conn.execute("SELECT wo_id, agent FROM claims").fetchall()
        finally:
            conn.close()

    def test_only_one_agent_wins_a_contested_claim(self):
        agents = [f"Agent{i} <a{i}@example.invalid>" for i in range(3)]
        for r in range(self.ROUNDS):
            wo = f"WO-{r + 1:03d}"
            self.sb.wf("open", wo, "--kind", "tdd", "--objective", "race",
                       check=EXIT_OK)
            results = self.race(wo, agents)
            winners = [a for a, code in results.items() if code == EXIT_OK]
            with self.subTest(round=r):
                self.assertEqual(len(winners), 1,
                                 f"round {r}: {results} — exactly one may win")
                for agent, code in results.items():
                    if agent not in winners:
                        self.assertEqual(code, EXIT_CLAIMED, f"{agent}: {code}")
                rows = [row for row in self.holders() if row[0] == wo]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0][1], winners[0],
                                 "the recorded holder must be the process that won")

    def test_a_loser_never_overwrites_the_recorded_holder(self):
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)
        a = "Agent A <a@example.invalid>"
        b = "Agent B <b@example.invalid>"
        self.sb.wf("claim", "WO-001", "--ttl", "1h", agent=a, check=EXIT_OK)
        for _ in range(5):
            self.sb.wf("claim", "WO-001", "--ttl", "1h", agent=b,
                       check=EXIT_CLAIMED)
        self.assertEqual([r[1] for r in self.holders()], [a])


class CommitIsClaimGated(SandboxCase):
    """[P1, verifier D2] wf commit was the one appending verb with no gate.

    do_commit appends commit.landed stamped with ctx.agent into every chain in
    the pending export. A non-holder running a bare `wf commit` therefore
    writes their identity into work orders somebody else holds. The gating
    test's case list omitted both `commit` and `green`, which is exactly why
    the one real hole stayed uncaught.
    """

    OTHER = "Other Agent <noreply@example.invalid>"

    def setUp(self):
        super().setUp()
        self.sb.seed_project()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("--no-commit", "advance", "WO-001", check=EXIT_OK)
        self.sb.wf("claim", "WO-001", check=EXIT_OK)

    def events(self):
        raw = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001", check=EXIT_OK).stdout)
        return raw["events"]

    def test_naming_a_claimed_work_order_refuses(self):
        before = len(self.events())
        proc = self.sb.wf("commit", "WO-001", agent=self.OTHER)
        self.assertEqual(proc.returncode, EXIT_CLAIMED, proc.stderr)
        self.assertEqual(len(self.events()), before,
                         "a refused commit must not have appended a bind")

    def test_a_bare_flush_skips_the_claimed_chain_rather_than_refusing(self):
        # Refusing the whole commit would let one agent's claim block every
        # other agent's auto-commit, since the export legitimately carries
        # other work orders' lines. Skipping the bind closes the actual harm:
        # a bind is stamped with ctx.agent, so binding somebody else's chain
        # writes their work under this agent's name.
        before = len(self.events())
        self.sb.wf("commit", agent=self.OTHER, check=EXIT_OK)
        self.assertEqual(len(self.events()), before,
                         "no bind may be appended to a chain held by another")

    def test_no_bind_carries_the_wrong_agent(self):
        # The holder's own flush first, so at least one bind exists — a loop
        # over an empty list asserts nothing (Grok, PR #10 review).
        self.sb.wf("commit", check=EXIT_OK)
        self.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV,
                   check=EXIT_OK)
        self.sb.wf("commit", agent=self.OTHER)
        binds = [e for e in self.events() if e["type"] == "commit.landed"]
        self.assertTrue(binds, "no bind recorded at all — nothing was tested")
        for bind in binds:
            self.assertNotEqual(bind["agent"], self.OTHER)

    def test_the_holder_can_flush(self):
        # EXIT_OK alone also passes on "nothing to commit" (Grok, PR #10
        # review) — assert a commit actually happened and bound this chain.
        body = json.loads(self.sb.wf("--json", "commit", check=EXIT_OK).stdout)
        self.assertIsNotNone(body["committed"], body)
        self.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV,
                   check=EXIT_OK)
        binds = [e for e in self.events() if e["type"] == "commit.landed"]
        self.assertTrue(binds, "the holder's flush must bind their chain")
        self.assertEqual({b["agent"] for b in binds}, {support.Sandbox.AGENT})

    def test_green_is_gated_too(self):
        self.sb.wf("commit", check=EXIT_OK)
        self.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.make_green()
        proc = self.sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV,
                          agent=self.OTHER)
        self.assertEqual(proc.returncode, EXIT_CLAIMED, proc.stderr)


class SessionExpiryIsTested(SandboxCase):
    """[P2, verifier D3] Planting `if True:` in the expiry predicate passed 340 tests.

    An implementation with no session expiry at all was indistinguishable from
    a correct one: `status.sessions` would list every agent that ever touched
    the repo and nothing would notice. Absence is the assertion that kills it.
    """

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)

    def agents(self):
        body = json.loads(self.sb.wf("--json", "status", check=EXIT_OK).stdout)
        return [s["agent"] for s in body["sessions"]]

    def test_a_stale_session_drops_out_of_status(self):
        stale = "Stale Agent <stale@example.invalid>"
        self.sb.wf("status", agent=stale, check=EXIT_OK)
        self.assertIn(stale, self.agents())

        support.plant_sql(
            self.sb.db,
            "UPDATE sessions SET last_seen = ? WHERE agent = ?",
            ("2000-01-01T00:00:00.000000Z", stale),
            check=lambda c: c.execute(
                "SELECT COUNT(*) FROM sessions").fetchone()[0] >= 1,
        )
        self.assertNotIn(stale, self.agents(),
                         "an expired session must not read as active")

    def test_a_fresh_session_stays(self):
        fresh = "Fresh Agent <fresh@example.invalid>"
        self.sb.wf("status", agent=fresh, check=EXIT_OK)
        self.assertIn(fresh, self.agents())

    def test_touching_again_revives_a_stale_session(self):
        agent = "Returning Agent <r@example.invalid>"
        self.sb.wf("status", agent=agent, check=EXIT_OK)
        support.plant_sql(
            self.sb.db,
            "UPDATE sessions SET last_seen = ? WHERE agent = ?",
            ("2000-01-01T00:00:00.000000Z", agent),
            check=lambda c: c.execute(
                "SELECT COUNT(*) FROM sessions").fetchone()[0] >= 1,
        )
        self.assertNotIn(agent, self.agents())
        self.sb.wf("status", agent=agent, check=EXIT_OK)
        self.assertIn(agent, self.agents(), "re-appearing is the heartbeat")


class ReleaseWritesNothing(SandboxCase):
    """[P2, verifier D4] Making release write to the chain was undetectable.

    The verifier made cmd_release call do_commit — appending commit.landed,
    flushing the export and making a git commit — and the suite's failure set
    was identical to clean. Four tests covered release and none looked at the
    chain, the export or HEAD.
    """

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("claim", "WO-001", check=EXIT_OK)

    def test_release_touches_neither_the_chain_nor_the_export_nor_head(self):
        before_events = json.loads(
            self.sb.wf("--json", "log", "--full", "--all", "WO-001", check=EXIT_OK).stdout)["events"]
        before_tree = self.sb._git("status", "--porcelain")
        before_head = self.sb.head()

        self.sb.wf("release", "WO-001", check=EXIT_OK)

        after = json.loads(
            self.sb.wf("--json", "log", "--full", "--all", "WO-001", check=EXIT_OK).stdout)["events"]
        self.assertEqual(len(after), len(before_events), "release appended an event")
        self.assertEqual(self.sb._git("status", "--porcelain"), before_tree)
        self.assertEqual(self.sb.head(), before_head, "release made a commit")

    def test_a_refused_release_writes_nothing_either(self):
        other = "Other Agent <noreply@example.invalid>"
        before_head = self.sb.head()
        before_tree = self.sb._git("status", "--porcelain")
        self.sb.wf("release", "WO-001", agent=other, check=EXIT_CLAIMED)
        self.assertEqual(self.sb.head(), before_head)
        self.assertEqual(self.sb._git("status", "--porcelain"), before_tree)


class RequirementClassMustExist(SandboxCase):
    """[P2, verifier B1a] A typo made a stage permanently unsatisfiable.

    `receipt.check:securty` passes the shape check, loads clean, and then no
    registered check can ever satisfy it. The engine still never learns the
    word "security" — it just requires the class to be one the spec itself
    declares.
    """

    def register(self, requirement):
        raw = spec(stages=[
            {"name": "spec", "leave_requires": []},
            {"name": "gate", "leave_requires": [requirement]},
        ])
        (self.sb.root / "gate-kinds" / "tdd.json").write_bytes(canonical.dumpb(raw))
        self.sb.commit_all("sandbox: register")
        return self.sb.wf("init")

    def test_a_class_no_check_declares_refuses_at_load(self):
        proc = self.register("receipt.check:securty")
        self.assertEqual(proc.returncode, EXIT_REFUSED, proc.stderr)
        self.assertIn("securty", proc.stderr)
        self.assertIn("security", proc.stderr, "the message should name what exists")

    def test_a_declared_class_is_accepted(self):
        self.assertEqual(self.register("receipt.check:security").returncode, EXIT_OK)


class NextEmitsARunnableCommand(SecurityGateCase):
    """[P2, verifier B1b] next put the requirement string in the check-name slot.

    PLAN §4 promises "the exact argv that advances it". For a class-qualified
    stage it emitted ["wf","check",wo,"receipt.check:security"], which replays
    to exit 1.
    """

    def test_the_advancing_argv_actually_runs(self):
        body = json.loads(self.sb.wf("--json", "next", "WO-001",
                                     check=EXIT_OK).stdout)
        self.assertEqual(body["missing"], ["receipt.check:security"])
        argv = body["advances"]
        self.assertNotIn("receipt.check:security", argv,
                         "a requirement string is not a check name")
        # Two security checks are registered, so there is no single exact
        # argv and next says so — but what it does emit must still run.
        self.assertFalse(body["advances_complete"])
        self.assertIn("carries that class", body["note"])
        support.assert_runnable(self, argv)
        # The emitted candidate is "ok-scan" by sort order; say so, so a
        # reordering does not silently swap in the failing "scan" and turn
        # the assertions below into luck (Grok, PR #10 review).
        self.assertIn("ok-scan", argv)
        proc = subprocess.run(
            argv, cwd=str(self.sb.dir),
            capture_output=True, text=True,
            env=dict(os.environ, WF_AGENT=support.Sandbox.AGENT))
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
        self.assertEqual(
            json.loads(self.sb.wf("--json", "status", "WO-001").stdout)["missing"], []
        )

    def test_one_candidate_gives_an_exact_argv(self):
        raw = spec(checks=[
            {"name": "only-scan", "class": "security",
             "argv": ["python3", "-c", "raise SystemExit(0)"]},
        ])
        (self.sb.root / "gate-kinds" / "tdd.json").write_bytes(canonical.dumpb(raw))
        self.sb.commit_all("sandbox: one security check")
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-002", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-002", check=EXIT_OK)
        body = json.loads(self.sb.wf("--json", "next", "WO-002",
                                     check=EXIT_OK).stdout)
        support.assert_runnable(self, body["advances"])
        self.assertEqual(body["advances"][-3:], ["check", "WO-002", "only-scan"])
        self.assertTrue(body["advances_complete"])
        # Replayed as given — argv[0] included — which is the actual promise.
        self.assertEqual(
            subprocess.run(body["advances"] + ["--root", str(self.sb.root)],
                           cwd=str(self.sb.dir), capture_output=True, text=True,
                           env=dict(os.environ, WF_AGENT=support.Sandbox.AGENT)
                           ).returncode, EXIT_OK)
        self.assertEqual(
            json.loads(self.sb.wf("--json", "status", "WO-002").stdout)["missing"], []
        )
