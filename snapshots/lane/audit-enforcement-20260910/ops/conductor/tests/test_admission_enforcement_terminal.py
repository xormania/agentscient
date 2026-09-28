"""Frozen criteria and the draft-dev terminal path.

Written from FINDING-ADMISSION.md §Refusals, completion and independent
acceptance. ladder.sh finish WORK_ORDER is the manual terminal
entrypoint. GitHub/land stay mocked by the inherited ladder fixture.

Intended reds: finish is an unknown start form; missing declaration
does not refuse admission-criteria; a failed terminal still dispatches
another review. Success requires registration through declared launch,
executed receipts and accepted reviews, then exactly draft-pr into dev
with no additional model.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from test_ladder_lever import AGENT, BRANCH, PR_URL, _LadderFixture

DISPATCH_TESTS = Path(__file__).resolve().parents[2] / "devlane" / "dispatch" / "tests"
if str(DISPATCH_TESTS) not in sys.path:
    sys.path.insert(0, str(DISPATCH_TESTS))
import admission_enforcement_support as aes  # noqa: E402


WO_ID = "WO-term-aa41"


class TerminalDeclarationShape(unittest.TestCase):
    """GREEN: terminal object is exactly draft-pr into dev."""

    def test_terminal_is_draft_pr_into_dev(self):
        self.assertEqual(aes.TERMINAL, {"action": "draft-pr", "base": "dev"})
        body = aes.work_order(
            ident=WO_ID,
            branch="work",
            base_ref="a" * 40,
            scope={"path": "owner-scope.md", "sha256": "b" * 64},
            authority=[{"path": "addendum.md", "sha256": "c" * 64}],
            test_scope=["ops/conductor/tests/"],
            fixture=[aes.command_row("fx", "true", [])],
            acceptance=[aes.command_row("ac", "true", [])],
            final=[aes.command_row("fn", "ops/bin/suites.sh", [])],
            reviews=[{"slot": "check-tests", "job": "check-tests"}],
        )
        self.assertEqual(body["terminal"], aes.TERMINAL)
        self.assertEqual(body["final"][0]["inputs"], [])
        with self.assertRaises(ValueError):
            aes.work_order(
                ident=WO_ID,
                branch="work",
                base_ref="a" * 40,
                scope={"path": "owner-scope.md", "sha256": "b" * 64},
                authority=[{"path": "addendum.md", "sha256": "c" * 64}],
                test_scope=["ops/conductor/tests/"],
                fixture=[aes.command_row("fx2", "true", [])],
                acceptance=[aes.command_row("ac2", "true", [])],
                final=[aes.command_row("fn2", "ops/bin/suites.sh", [])],
                reviews=[{"slot": "check-tests", "job": "check-tests"}],
                terminal={"action": "merge", "base": "dev"},
            )


class LadderFinishIsTheManualTerminal(_LadderFixture):
    def plant_bound_wo(self):
        head = self.git("rev-parse", "HEAD", cwd=self.wt).stdout.strip()
        scope_sha = aes.sha256_file(self.scope_path)
        body = aes.work_order(
            ident=WO_ID,
            branch=BRANCH,
            base_ref=head,
            scope={"path": "scope.md", "sha256": scope_sha},
            authority=[{"path": "scope.md", "sha256": scope_sha}],
            test_scope=["ops/conductor/tests/"],
            fixture=[aes.command_row("fx-term", "true", [])],
            acceptance=[aes.command_row("ac-term", "true", [])],
            final=[aes.command_row("fn-term", "ops/bin/suites.sh", [])],
            reviews=aes.bound_reviews(),
        )
        wo = self.scratch / "work-order.json"
        digest = aes.write_json(wo, body)
        self.assertEqual(body["terminal"], aes.TERMINAL)
        self.assertEqual(body["fixture"][0]["inputs"], [])
        return wo, body, digest, head

    def register_through_dispatch(self, wo):
        proc = self.invoke_dispatch([
            "--job", "author-tests",
            "--harness", "grok",
            "--stage", "tests",
            "--work-order", str(wo),
            "--detach",
        ])
        text = f"{proc.stdout or ''}{proc.stderr or ''}"
        self.assertNotIn("unrecognized", text.lower(), text)
        return proc, text

    def invoke_dispatch(self, flags):
        import subprocess
        wrapper = self.wt / "ops" / "bin" / "dispatch.sh"
        return subprocess.run(
            ["bash", str(wrapper), *flags],
            cwd=str(self.wt),
            env=self.env(),
            capture_output=True,
            text=True,
            check=False,
        )

    def plant_receipts(self, rec_id, body, digest, head, *, final_ok=True):
        rec_path = (
            self.wt / ".dev" / "records" / "dispatches" / f"{rec_id}.json"
        )
        if not rec_path.is_file():
            rec_path.parent.mkdir(parents=True, exist_ok=True)
            rec_path.write_text(json.dumps({"id": rec_id}) + "\n", encoding="utf-8")
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        handles = self.scratch / "verify-bytes"
        handles.mkdir(exist_ok=True)
        stdout = aes.plant_stdout_handle(handles, "fx.out", "fixture-empty-list-ok\n")
        stderr = aes.plant_stdout_handle(handles, "fx.err", "")
        tests = [{
            "path": "ops/conductor/tests/test_admission_enforcement_terminal.py",
            "sha256": aes.sha256_file(Path(__file__)),
            "producers": [aes.BOUND_PRODUCER_ID],
        }]
        ok_cmd = {
            "id": "fx-term",
            "command": "true",
            "inputs": [],
            "exit": 0,
            "timed_out": False,
            "stdout": stdout,
            "stderr": stderr,
        }
        final_cmd = dict(ok_cmd)
        final_cmd["id"] = "fn-term"
        final_cmd["command"] = "ops/bin/suites.sh"
        if not final_ok:
            final_cmd["exit"] = 1
            final_cmd["stdout"] = aes.plant_stdout_handle(handles, "fn.out", "failed\n")
        rec["verification"] = [
            aes.verification_entry(
                dispatch=rec_id,
                attempt=1,
                phase="fixture",
                work_order_id=body["id"],
                declaration_sha256=digest,
                scope_sha256=body["scope"]["sha256"],
                ref=head,
                tests=tests,
                commands=[ok_cmd],
                by=AGENT,
            ),
            aes.verification_entry(
                dispatch=rec_id,
                attempt=1,
                phase="acceptance",
                work_order_id=body["id"],
                declaration_sha256=digest,
                scope_sha256=body["scope"]["sha256"],
                ref=head,
                tests=tests,
                commands=[dict(ok_cmd, id="ac-term")],
                by=AGENT,
            ),
            aes.verification_entry(
                dispatch=rec_id,
                attempt=1,
                phase="final",
                work_order_id=body["id"],
                declaration_sha256=digest,
                scope_sha256=body["scope"]["sha256"],
                ref=head,
                tests=tests,
                commands=[final_cmd],
                by=AGENT,
                status="ok" if final_ok else "invalid",
                reason=None if final_ok else "final command exited 1",
            ),
        ]
        rec_path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        landed = json.loads(rec_path.read_text(encoding="utf-8"))
        self.assertEqual(len(landed["verification"]), 3)
        return rec_path

    def test_finish_without_a_work_order_is_admission_criteria(self):
        proc = self.invoke(["finish"])
        text = self.combined(proc)
        self.assertEqual((proc.stdout or "").strip(), "")
        self.assertEqual(proc.returncode, 2, text)
        self.assertIn("admission-criteria", (proc.stderr or "").lower())
        self.assertIn("expected", (proc.stderr or "").lower())
        self.assertIn("needed", (proc.stderr or "").lower())

    def test_finish_unregistered_work_order_is_admission_criteria(self):
        wo, body, digest, head = self.plant_bound_wo()
        self.assertTrue(wo.is_file())
        before = self.dispatch_count(job="check-tests", stage="check-tests")
        proc = self.invoke(["finish", WO_ID])
        text = self.combined(proc)
        self.assertNotIn("unrecognized", text.lower(), text)
        self.assertEqual(self.dispatch_count(job="check-tests", stage="check-tests"), before)
        self.assertIn("admission-criteria", text.lower())
        self.assertEqual(proc.returncode, 2, text)

    def test_finish_of_a_registered_eligible_order_opens_only_a_draft_into_dev(self):
        wo, body, digest, head = self.plant_bound_wo()
        minted, mint_text = self.register_through_dispatch(wo)
        self.assertNotIn("unrecognized", mint_text.lower(), mint_text)
        rec_id = None
        for line in mint_text.splitlines():
            if line.startswith("record:"):
                rec_id = line.split(":", 1)[1].strip()
        plant = self.load_plant()
        if rec_id is None:
            rec_id = plant.get("last_id")
        self.assertTrue(rec_id, mint_text)
        self.plant_receipts(rec_id, body, digest, head, final_ok=True)
        before = self.dispatch_names()
        proc = self.invoke(["finish", WO_ID])
        text = self.combined(proc)
        self.assertNotIn("unrecognized", text.lower(), text)
        self.assertEqual(proc.returncode, 0, text)
        self.assertEqual(self.dispatch_names(), before)
        self.assertIn("pr=", (proc.stdout or ""))
        self.assertIn(PR_URL, (proc.stdout or ""))
        gh = self.gh_argvs()
        self.assertTrue(gh, "finish must invoke the mocked gh pr create")
        flat = " ".join(str(item) for row in gh for item in row)
        self.assertIn("pr create", " ".join(gh[-1]))
        self.assertIn("--draft", gh[-1])
        self.assertIn("dev", gh[-1])
        self.assertNotIn("--ready", flat)
        self.assertNotIn("merge", " ".join(gh[-1]))
        ladder = self.ladder_record()
        terminal = ladder.get("pr") or ladder.get("terminal") or {}
        self.assertTrue(terminal or "pr" in ladder, ladder)

    def test_changed_declaration_after_registration_is_admission_criteria(self):
        wo, body, digest, head = self.plant_bound_wo()
        self.register_through_dispatch(wo)
        body["final"][0]["command"] = "echo mutated-final"
        aes.write_json(wo, body)
        self.assertNotEqual(aes.sha256_file(wo), digest)
        proc = self.invoke(["finish", WO_ID])
        text = self.combined(proc)
        self.assertNotIn("unrecognized", text.lower(), text)
        self.assertIn("admission-criteria", text.lower())
        self.assertEqual(proc.returncode, 2, text)
        self.assertEqual(self.gh_argvs(), [])

    def test_failed_final_receipt_is_admission_incomplete_and_adds_no_review(self):
        wo, body, digest, head = self.plant_bound_wo()
        minted, mint_text = self.register_through_dispatch(wo)
        rec_id = self.load_plant().get("last_id")
        self.assertTrue(rec_id, mint_text)
        self.plant_receipts(rec_id, body, digest, head, final_ok=False)
        before = self.dispatch_names()
        proc = self.invoke(["finish", WO_ID])
        text = self.combined(proc)
        self.assertNotIn("unrecognized", text.lower(), text)
        self.assertIn("admission-incomplete", text.lower())
        self.assertNotEqual(proc.returncode, 0, text)
        self.assertEqual(self.dispatch_names(), before)
        self.assertEqual(self.gh_argvs(), [])

    def test_a_failed_terminal_retry_adds_no_review(self):
        wo, _body, _digest, _head = self.plant_bound_wo()
        self.register_through_dispatch(wo)
        before = self.dispatch_names()
        first = self.invoke(["finish", WO_ID])
        second = self.invoke(["finish", WO_ID])
        self.assertEqual(self.dispatch_names(), before)
        for proc in (first, second):
            text = self.combined(proc)
            self.assertNotRegex(
                text.lower(),
                r"check-tests|security-audit|adversarial-review",
            )


if __name__ == "__main__":
    unittest.main()
