"""audit: a PR is flipped ready only against a closed security audit at its head.

Owner, 2026-09-16: "i'd like if you have daybreak security audits made
required for draft pr's - and resolution required before they can be made
ready for review". The rule text is the audit row of CONTRIB.md's ready
table, owned by PR #245; this file is its mechanical gate.

The row: `gh pr ready N` refuses class `audit` (a deny: the remedy, the
audit, is the agent's own) unless the `## Proof` section names a
security-audit dispatch record that, read at the PR head, is closed, ran
on the codex harness at the model `ops/lane.conf` names in
MODEL_CODEX_SECURITY_AUDIT, carries an audited sha its own fields agree
on, and has every finding of its envelope disposed in the findings export
at that head. A commit after the audited sha voids the audit unless
everything it touched is inside the records set the row declares, or it is
a fix commit in CONTRIB.md's shape citing a finding of that audit — owner,
2026-09-16: "you can't keep re-auditing after fixes - draw a line". The
citation the gate parses is a `Finding:` line carrying the ledger key
`<record id>#<n>`, beside the `Verified:` line that shape requires.

Only the branch's own commits are judged: the gate walks
`<audited>..<head>` first-parent, skipping merge commits and anything
reachable from `origin/<trunk>`, so a forward merge of the trunk never
voids the audit (agentscient-11, 2026-09-16, measured on #242 — the
dispatcher merges the trunk forward before every launch, and the rule as
written voided every branch that had dispatched anything). The
merge verb does not carry the row: GitHub refuses to merge a draft, so the ready flip
binds first and the `pr-proof` row binds the lineage after it.

Which field carries the audited sha is measured, not assumed. Over the
542 records under .dev/records/dispatches on 2026-09-16: no record carries
a `stamp` key; `result.head` and `snapshot.ref_sha` disagree on 318 of
them, every one a write-role job whose worker committed past its snapshot;
on all 28 security-audit records the two agree, because a read-role job
commits nothing. The gate therefore reads the head from `snapshot.ref_sha`
and `result.head` and refuses naming both when they disagree, and never
reads `lineage.base_sha`, which is the base the snapshot was cut from.

One producer (Claude Opus 5 (1M context)) under hand grant 264 wrote
these tests, the row and the gate; the second producer is absent by the
owner's word (AGENTS.md, dev-lane changes by hand).
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

import support

from ops.testkit import World, run

HOOK = Path(__file__).resolve().parents[1] / "claude" / "matrix.py"
CORPUS = "ops/conductor/handoff/probes/probes-2026-09-16-fixture.jsonl"
RECORDS = support.DISPATCH_RECORDS
EXPORT = support.FINDINGS_EXPORT
AUDIT = support.AUDIT_RECORD_ID
MODEL = support.AUDIT_MODEL
TIMEOUT = 60


a_record = support.security_audit_record
an_export = support.findings_export


class AuditAtTheHead(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="pr-audit-")
        self.addCleanup(self.world.close)
        self.world.require("git")
        self.hook = self._subject()
        self.repo = self.world.cwd
        self._plant_gh(pr={"body": "", "headRefOid": "0" * 40,
                           "headRefName": "lane/fixture", "isDraft": True}, runs=[])
        self.env = self.world.env()
        self.assertEqual(
            Path(shutil.which("gh", path=self.env["PATH"])).resolve(),
            (self.world.bin / "gh").resolve(),
            "INVALID: fake gh not first on PATH",
        )
        self.world.git("init", "-q", "-b", "dev")
        self.plant_conf(MODEL)
        self.world.plant_text(
            self.repo / CORPUS,
            json.dumps({"id": "P-FIX-1", "kind": "serve", "lane": "git",
                        "question": "q", "serve": "git log -1",
                        "expect": "x"}) + "\n",
        )
        self.audited = self.commit("the tree the audit read")

    # -- the world ---------------------------------------------------------

    def _subject(self):
        staged = self.world.stage(HOOK, siblings=("miss.py", "command_shape.py"))
        src = HOOK.parent.parent / "boundaries.json"
        self.world.plant_bytes(staged.parent.parent / "boundaries.json", src.read_bytes())
        return staged

    def _plant_gh(self, *, pr, runs):
        self.world.tools.plant(
            "gh",
            stderr="fake gh: unexpected\n",
            exit=2,
            responses=[
                {"match": ["pr", "view"], "stdout": json.dumps(pr), "stderr": "", "exit": 0},
                {"match": ["run", "list"], "stdout": json.dumps(runs), "stderr": "", "exit": 0},
            ],
        )

    def plant_conf(self, model):
        """The lane conf, planted on disk: the gate reads it at check time,
        so a test may move the model without moving the tree."""
        self.world.plant_text(
            self.repo / "ops" / "lane.conf",
            "LANE_NAME='agentscient'\nTRUNK_BRANCH='dev'\n"
            + (f"MODEL_CODEX_SECURITY_AUDIT='{model}'\n" if model else ""),
        )

    def commit(self, message):
        self.world.git("add", "-A")
        self.world.git("commit", "-q", "-m", message)
        return self.world.git("rev-parse", "HEAD").stdout.strip()

    def close_audit(self, *, record=None, rows=None):
        """Plant the audit's record and the dispositions it needs, commit
        them, and answer the head that commit made."""
        record = a_record(audited=self.audited) if record is None else record
        rows = ((f"{AUDIT}#1", "fixed"), (f"{AUDIT}#2", "ruled")) if rows is None else rows
        self.world.plant_text(self.repo / RECORDS / f"{AUDIT}.json",
                              json.dumps(record, indent=1))
        self.world.plant_text(self.repo / EXPORT, an_export(*rows))
        return self.commit("records: the security audit and its dispositions")

    # -- the call ----------------------------------------------------------

    GOOD = ("## What\n\nx\n\n## Proof\n\nRows at the head: P-FIX-1.\n"
            f"Security audit: {AUDIT}.\n\n## Why\n\ny\n")

    def plant(self, *, body, head, runs=None):
        if runs is None:
            runs = [{"name": "ci", "workflowName": "ci", "status": "completed",
                     "conclusion": "success", "headSha": head}]
        self._plant_gh(pr={"body": body, "headRefOid": head,
                           "headRefName": "lane/fixture", "isDraft": True}, runs=runs)

    def run_bash(self, command):
        payload = json.dumps({"tool_name": "Bash",
                              "tool_input": {"command": command},
                              "cwd": str(self.repo)})
        return run([sys.executable, str(self.hook)], cwd=str(self.repo),
                   env=self.env, stdin=payload, timeout=TIMEOUT)

    def refusal(self, proc):
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertTrue(proc.stdout.strip(), "hook let the call through")
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        reason = out["permissionDecisionReason"]
        self.assertTrue(reason.startswith("[matrix:audit] audit: expected "), reason)
        self.assertIn("; found ", reason)
        self.assertIn("; needed ", reason)
        return reason

    def allowed(self, proc):
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "", proc.stdout)

    # -- the rows ----------------------------------------------------------

    def test_ready_passes_with_a_closed_audit_at_the_head(self):
        head = self.close_audit()
        self.plant(body=self.GOOD, head=head)
        self.allowed(self.run_bash("gh pr ready 12"))

    def test_a_proof_section_naming_no_record_refuses(self):
        head = self.close_audit()
        self.plant(body="## Proof\n\nRows at the head: P-FIX-1.\n", head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("security-audit", reason)

    def test_a_record_absent_at_the_head_is_named(self):
        head = self.close_audit()
        absent = "20260916T130000Z-review-codex-ffffff"
        self.plant(body=f"## Proof\n\nP-FIX-1. Audit: {absent}.\n", head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn(absent, reason)

    def test_an_unclosed_audit_refuses(self):
        head = self.close_audit(record=a_record(audited=self.audited, status="launched"))
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("launched", reason)

    def test_another_job_is_not_a_security_audit(self):
        head = self.close_audit(
            record=a_record(audited=self.audited, job="adversarial-review"))
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("adversarial-review", reason)

    def test_another_harness_refuses(self):
        head = self.close_audit(record=a_record(audited=self.audited, harness="grok"))
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("grok", reason)
        self.assertIn("codex", reason)

    def test_a_model_other_than_the_conf_refuses(self):
        head = self.close_audit(
            record=a_record(audited=self.audited, ran="gpt-5", requested="gpt-5"))
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("gpt-5", reason)
        self.assertIn(MODEL, reason)

    def test_a_requested_model_the_run_did_not_honour_refuses(self):
        head = self.close_audit(
            record=a_record(audited=self.audited, requested=MODEL, ran="gpt-5"))
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("gpt-5", reason)

    def test_the_model_comes_from_the_conf_read_at_check_time(self):
        """The conf names the model, never the gate: a conf moved on disk
        moves the gate with it, and the tree the audit read is untouched."""
        head = self.close_audit(
            record=a_record(audited=self.audited, ran="gpt-other", requested="gpt-other"))
        self.plant(body=self.GOOD, head=head)
        self.refusal(self.run_bash("gh pr ready 12"))
        self.plant_conf("gpt-other")
        self.plant(body=self.GOOD, head=head)
        self.allowed(self.run_bash("gh pr ready 12"))

    def test_a_conf_naming_no_audit_model_is_could_not_look(self):
        head = self.close_audit()
        self.plant_conf("")
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("MODEL_CODEX_SECURITY_AUDIT", reason)

    def test_two_head_fields_that_disagree_refuse_naming_both(self):
        """A security audit commits nothing, so the ref it read and the head
        it reports are one sha; two answers are never read as met."""
        other = "f" * 40
        head = self.close_audit(record=a_record(audited=self.audited, result_head=other))
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn(self.audited[:8], reason)
        self.assertIn(other[:8], reason)

    def test_the_base_the_snapshot_was_cut_from_is_not_the_head(self):
        """`lineage.base_sha` is the base, not the head: a record whose base
        differs still passes when the two head fields name the head."""
        head = self.close_audit(record=a_record(audited=self.audited, base="e" * 40))
        self.plant(body=self.GOOD, head=head)
        self.allowed(self.run_bash("gh pr ready 12"))

    def test_an_open_finding_refuses_and_is_named(self):
        head = self.close_audit(rows=((f"{AUDIT}#1", "fixed"), (f"{AUDIT}#2", "open")))
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn(f"{AUDIT}#2", reason)
        self.assertNotIn(f"{AUDIT}#1", reason)

    def test_a_finding_absent_from_the_export_is_undisposed(self):
        head = self.close_audit(rows=((f"{AUDIT}#1", "fixed"),))
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn(f"{AUDIT}#2", reason)

    def test_an_export_absent_at_the_head_is_undisposed(self):
        record = a_record(audited=self.audited)
        self.world.plant_text(self.repo / RECORDS / f"{AUDIT}.json",
                              json.dumps(record, indent=1))
        head = self.commit("records: the audit, its dispositions unexported")
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("undisposed", reason)

    def test_a_code_commit_after_the_audit_voids_it_and_names_the_path(self):
        self.close_audit()
        self.world.plant_text(self.repo / "ops" / "devlane" / "hooks" / "claude" / "new.py",
                              "# a change the audit never read\n")
        head = self.commit("code: a change after the audit")
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("ops/devlane/hooks/claude/new.py", reason)

    def fix_commit(self, *, finding, verified=True,
                   path="ops/devlane/hooks/claude/new.py"):
        """A commit in CONTRIB.md's fix-commit shape (### Fix commit)."""
        self.world.plant_text(self.repo / path, f"# the fix for {finding}\n")
        body = f"hooks: the finding applied\n\nFinding: [P1] {finding} a.py: the claim\n"
        if verified:
            body += f"Verified: `python3 -m unittest` at {self.audited}\n"
        return self.commit(body)

    def test_a_fix_commit_citing_a_finding_of_the_audit_keeps_it_standing(self):
        """Owner, 2026-09-16: "you can't keep re-auditing after fixes - draw
        a line". The fix is still disposed, which the export at the head says."""
        self.close_audit()
        head = self.fix_commit(finding=f"{AUDIT}#1")
        self.plant(body=self.GOOD, head=head)
        self.allowed(self.run_bash("gh pr ready 12"))

    def test_a_fix_commit_citing_no_finding_key_voids_the_audit(self):
        self.close_audit()
        head = self.fix_commit(finding="[P1]")
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("ops/devlane/hooks/claude/new.py", reason)

    def test_a_fix_commit_citing_another_audits_finding_voids_it(self):
        self.close_audit()
        head = self.fix_commit(finding="20260916T130000Z-review-codex-ffffff#1")
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("ops/devlane/hooks/claude/new.py", reason)

    def test_a_fix_commit_citing_a_finding_the_audit_never_made_voids_it(self):
        self.close_audit()
        head = self.fix_commit(finding=f"{AUDIT}#9")
        self.plant(body=self.GOOD, head=head)
        self.refusal(self.run_bash("gh pr ready 12"))

    def test_a_fix_commit_without_its_verified_line_voids_the_audit(self):
        self.close_audit()
        head = self.fix_commit(finding=f"{AUDIT}#1", verified=False)
        self.plant(body=self.GOOD, head=head)
        self.refusal(self.run_bash("gh pr ready 12"))

    def test_a_records_only_commit_does_not_void_the_audit(self):
        """agentscient-11, 2026-09-16: the strict rule voids every audit by
        its own record, since that record is committed after the audit
        closes. A commit inside the records set leaves the audit standing."""
        self.close_audit()
        self.world.plant_text(
            self.repo / "ops" / "conductor" / "handoff" / "note.md",
            "# a hand-off written after the audit\n")
        head = self.commit("records: a hand-off after the audit")
        self.plant(body=self.GOOD, head=head)
        self.allowed(self.run_bash("gh pr ready 12"))

    def test_an_aar_an_idea_and_a_lesson_do_not_void_the_audit(self):
        """The three locations a closing session writes, joined to the set
        as data on the row: a close is not a change to the tree audited."""
        self.close_audit()
        for path in ("ops/conductor/AAR-2026-09-16-fixture.md",
                     "ops/conductor/ideas/I-999-fixture.md",
                     "ops/conductor/lessons/L-999-fixture.md"):
            self.world.plant_text(self.repo / path,
                                  "# a record written after the audit\n")
        head = self.commit("records: an AAR, an idea and a lesson after the audit")
        self.plant(body=self.GOOD, head=head)
        self.allowed(self.run_bash("gh pr ready 12"))

    def test_a_conductor_tool_is_not_a_record_and_voids_the_audit(self):
        """The clean neighbour of the row above: the set is prefixes named
        on the row, never the whole conductor directory."""
        self.close_audit()
        self.world.plant_text(self.repo / "ops" / "conductor" / "tools" / "new.py",
                              "# a lever written after the audit\n")
        head = self.commit("conductor: a lever after the audit")
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("ops/conductor/tools/new.py", reason)

    def merge_the_trunk_forward(self):
        """What `dispatch.sh` does before every launch: the trunk moves
        under the branch and is merged in. Answers the merge commit's sha."""
        branch = self.world.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.world.git("checkout", "-q", "-b", "trunkwork", self.audited)
        self.world.plant_text(self.repo / "ops" / "bin" / "trunk.sh",
                              "# a change another session landed on the trunk\n")
        trunk_head = self.commit("lane: a lever another session landed on the trunk")
        self.world.git("update-ref", "refs/remotes/origin/dev", trunk_head)
        self.world.git("checkout", "-q", branch)
        self.world.git("merge", "-q", "--no-ff", "-m",
                       f"merge: dev forward into lane/fixture at {trunk_head[:8]}",
                       "trunkwork")
        head = self.world.git("rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(head, trunk_head, "INVALID: no merge commit was made")
        return head

    def test_a_forward_merge_of_the_trunk_does_not_void_the_audit(self):
        """agentscient-11, 2026-09-16, measured on #242: the dispatcher
        merges the trunk forward before every launch, so judging what that
        merge brings in voided every branch that had dispatched anything."""
        self.close_audit()
        head = self.merge_the_trunk_forward()
        self.plant(body=self.GOOD, head=head)
        self.allowed(self.run_bash("gh pr ready 12"))

    def test_the_branchs_own_commit_after_a_forward_merge_still_voids_it(self):
        """The clean neighbour of the row above: narrowing the walk to the
        branch's own commits must not stop it reaching them."""
        self.close_audit()
        self.merge_the_trunk_forward()
        self.world.plant_text(
            self.repo / "ops" / "devlane" / "hooks" / "claude" / "after.py",
            "# a change the audit never read\n")
        head = self.commit("code: a change after the forward merge")
        self.plant(body=self.GOOD, head=head)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("ops/devlane/hooks/claude/after.py", reason)

    def test_merge_does_not_carry_the_row(self):
        """Ruling of 2026-09-16, the owner's words being about ready: GitHub
        refuses to merge a draft, so the ready flip binds first."""
        self.plant(body="## What\n\nx\n\n## Proof\n\nP-FIX-1\n", head=self.audited)
        self.allowed(self.run_bash("gh pr merge 12 --merge"))

    def test_a_grant_is_no_escape(self):
        head = self.close_audit(rows=((f"{AUDIT}#1", "open"), (f"{AUDIT}#2", "open")))
        self.plant(body=self.GOOD, head=head)
        self.refusal(self.run_bash("HAND_GRANT=1 gh pr ready 12"))

    def test_other_gh_verbs_are_untouched(self):
        head = self.close_audit(rows=((f"{AUDIT}#1", "open"), (f"{AUDIT}#2", "open")))
        self.plant(body=self.GOOD, head=head)
        for command in ("gh pr view 12", "gh pr checks 12", "gh pr list",
                        "gh pr create --draft --fill"):
            proc = self.run_bash(command)
            self.assertNotIn("audit", proc.stdout, command)

    def test_the_docstring_table_names_the_row(self):
        """docs/tests.md rule 9: the assertion must be able to fail, so it
        pins the table entry and not the word `audit` that `security-audit`
        already carries into the table above it."""
        table = self.hook.read_text(encoding="utf-8").split('"""', 2)[1]
        self.assertIn("\n    audit ", table)


if __name__ == "__main__":
    unittest.main()
