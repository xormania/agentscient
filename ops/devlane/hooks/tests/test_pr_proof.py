"""pr-proof: a PR is marked ready or merged only against proof the system
can verify at that boundary.

Owner, 2026-09-12: "proof needs to be part of the system - it has to
generated and verified at boundaries"; "it has to be impossible to not do
the work - impossible"; "you can't take any agents word on anything - you
need proof, evidence". Measured that day: PR #141 was merged before its
checks registered (pitfall 22) and three capabilities were recorded as
done with no reading that any dispatch consumed them.

The row: `gh pr ready N` and `gh pr merge N` refuse class `pr-proof`
(a deny: the remedy, the proof, is the agent's own; owner, 2026-09-12:
"i don't want asks unless they're critical") unless the PR body carries a `## Proof` section naming corpus row ids
(`P-...`) that all exist in `ops/conductor/handoff/probes/` at the PR
head, the head is a fetched object here, and a `ci` run on that head has
completed with success (the run executed those rows). No grant escape.
`gh pr view` and every other gh verb are untouched.

One producer (Claude Fable 5.1) under hand grant 159 wrote these tests
and the row; the second producer is absent by the owner's word.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

HOOK = Path(__file__).resolve().parents[1] / "claude" / "matrix.py"
CORPUS = "ops/conductor/handoff/probes/probes-2026-09-12-fixture.jsonl"

FAKE_GH = r"""#!/usr/bin/env python3
import json, os, sys
fix = os.environ["PROOF_FIXTURES"]
args = sys.argv[1:]
with open(os.path.join(fix, "calls.log"), "a") as fh:
    fh.write(" ".join(args) + "\n")
if os.environ.get("PROOF_GH_FAIL") == "1":
    sys.stderr.write("gh: authentication failed\n"); sys.exit(1)
if args[:2] == ["pr", "view"]:
    sys.stdout.write(open(os.path.join(fix, "pr.json")).read()); sys.exit(0)
if args[:2] == ["run", "list"]:
    sys.stdout.write(open(os.path.join(fix, "runs.json")).read()); sys.exit(0)
sys.stderr.write("fake gh: unexpected " + " ".join(args) + "\n"); sys.exit(2)
"""


class PrProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pr-proof-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.bin = self.tmp / "bin"
        self.fix = self.tmp / "fix"
        self.repo = self.tmp / "repo"
        for directory in (self.home, self.bin, self.fix, self.repo):
            directory.mkdir()
        support.plant_executable(self.bin / "gh", FAKE_GH)
        support.plant_executable(self.bin / "cue", "#!/bin/sh\nexit 0\n")
        self.env = support.isolated_env(self.home, extra_path=self.bin,
                                        extra={"PROOF_FIXTURES": str(self.fix)})
        self.assertEqual(Path(shutil.which("gh", path=self.env["PATH"])).resolve(),
                         (self.bin / "gh").resolve(), "INVALID: fake gh not first on PATH")
        support.git(self.repo, self.env, "init", "-q", "-b", "dev")
        support.configure_identity(self.repo, self.env)
        (self.repo / "ops" / "lane.conf").parent.mkdir(parents=True)
        (self.repo / "ops" / "lane.conf").write_text(
            "LANE_NAME='agentscient'\nTRUNK_BRANCH='dev'\nSCOPE_CAP='1024'\n")
        corpus = self.repo / CORPUS
        corpus.parent.mkdir(parents=True)
        corpus.write_text(json.dumps({"id": "P-FIX-1", "kind": "serve", "lane": "git",
                                      "question": "q", "serve": "git log -1", "expect": "x"}) + "\n")
        support.git(self.repo, self.env, "add", "-A")
        support.git(self.repo, self.env, "commit", "-q", "-m", "fixture")
        self.head = support.git(self.repo, self.env, "rev-parse", "HEAD").stdout.strip()

    def plant(self, *, body, head=None, runs=None):
        head = head or self.head
        (self.fix / "pr.json").write_text(json.dumps(
            {"body": body, "headRefOid": head, "headRefName": "lane/fixture", "isDraft": True}))
        if runs is None:
            runs = [{"name": "ci", "workflowName": "ci", "status": "completed",
                     "conclusion": "success", "headSha": head}]
        (self.fix / "runs.json").write_text(json.dumps(runs))

    def run_bash(self, command, env=None):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command},
                              "cwd": str(self.repo)})
        return subprocess.run([sys.executable, str(HOOK)], cwd=str(self.repo),
                              env=env or self.env, input=payload, capture_output=True,
                              text=True, check=False, timeout=60)

    def refusal(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.strip(), "hook let the call through")
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        # pr-proof is a hard row with no grant escape; it denies, because
        # the proof is the agent's to add (owner, 2026-09-12)
        self.assertEqual(out["permissionDecision"], "deny")
        reason = out["permissionDecisionReason"]
        self.assertTrue(reason.startswith("[matrix:pr-proof] pr-proof: expected "), reason)
        self.assertIn("; found ", reason)
        self.assertIn("; needed ", reason)
        return reason

    def allowed(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "", proc.stdout)

    GOOD = "## What\n\nx\n\n## Proof\n\nRows at the head: P-FIX-1.\n\n## Why\n\ny\n"

    def test_ready_and_merge_pass_with_proof_rows_at_a_green_head(self):
        self.plant(body=self.GOOD)
        self.allowed(self.run_bash("gh pr ready 12"))
        self.allowed(self.run_bash("gh pr merge 12 --merge"))
        calls = (self.fix / "calls.log").read_text()
        self.assertIn("pr view 12", calls)
        self.assertIn("run list", calls)
        self.assertIn(self.head, calls)

    def test_no_proof_section_refuses(self):
        self.plant(body="## What\n\nx\n\n## Readings\n\nsee P-FIX-1\n")
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("Proof", reason)

    def test_proof_section_without_ids_refuses(self):
        self.plant(body="## Proof\n\nwe tested it by hand\n")
        self.refusal(self.run_bash("gh pr ready 12"))

    def test_an_id_absent_from_the_corpus_at_the_head_is_named(self):
        self.plant(body="## Proof\n\nP-FIX-1 and P-FIX-NOPE\n")
        reason = self.refusal(self.run_bash("gh pr merge 12 --merge"))
        self.assertIn("P-FIX-NOPE", reason)
        self.assertNotIn("P-FIX-1,", reason)

    def test_a_head_not_fetched_here_refuses_with_the_fetch(self):
        self.plant(body=self.GOOD, head="0" * 40)
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("git fetch", reason)

    def test_no_completed_run_on_the_head_refuses(self):
        self.plant(body=self.GOOD, runs=[{"name": "ci", "workflowName": "ci",
                                          "status": "in_progress", "conclusion": None,
                                          "headSha": self.head}])
        reason = self.refusal(self.run_bash("gh pr ready 12"))
        self.assertIn("run", reason)
        self.plant(body=self.GOOD, runs=[])
        self.refusal(self.run_bash("gh pr ready 12"))

    def test_a_failed_run_on_the_head_refuses(self):
        self.plant(body=self.GOOD, runs=[{"name": "ci", "workflowName": "ci",
                                          "status": "completed", "conclusion": "failure",
                                          "headSha": self.head}])
        reason = self.refusal(self.run_bash("gh pr merge 12 --merge"))
        self.assertIn("failure", reason)

    def test_a_run_on_another_sha_does_not_count(self):
        self.plant(body=self.GOOD, runs=[{"name": "ci", "workflowName": "ci",
                                          "status": "completed", "conclusion": "success",
                                          "headSha": "f" * 40}])
        self.refusal(self.run_bash("gh pr ready 12"))

    def test_gh_failing_is_could_not_look_not_a_pass(self):
        self.plant(body=self.GOOD)
        env = dict(self.env, PROOF_GH_FAIL="1")
        self.refusal(self.run_bash("gh pr ready 12", env=env))

    def test_a_grant_is_no_escape(self):
        self.plant(body="## What\n\nno proof\n")
        self.refusal(self.run_bash("HAND_GRANT=1 gh pr ready 12"))

    def test_other_gh_verbs_are_untouched(self):
        self.plant(body="## What\n\nno proof\n")
        for command in ("gh pr view 12", "gh pr checks 12", "gh pr list",
                        "gh run list --branch dev", "gh pr create --draft --fill"):
            proc = self.run_bash(command)
            self.assertNotIn("pr-proof", proc.stdout, command)
        self.assertNotIn("pr view", (self.fix / "calls.log").read_text() if (self.fix / "calls.log").exists() else "")

    def test_the_pr_number_may_come_after_flags(self):
        self.plant(body=self.GOOD)
        self.allowed(self.run_bash("gh pr merge --merge --subject 'x' 12"))
        self.plant(body="## What\n\nno proof\n")
        self.refusal(self.run_bash("gh pr merge --merge 12"))

    def test_a_selected_repository_is_read_for_its_proof(self):
        """Codex review of PR #158 (2026-09-12): `-R`/`--repo` selects another
        repository; the proof is read there, never from this repository's
        PR of the same number."""
        self.plant(body=self.GOOD)
        for command, selected in (("gh pr merge 12 --repo owner/other --merge", "owner/other"),
                                  ("gh pr ready -R owner/other 12", "owner/other"),
                                  ("gh pr ready 12 --repo=owner/third", "owner/third")):
            (self.fix / "calls.log").write_text("")
            self.allowed(self.run_bash(command))
            calls = (self.fix / "calls.log").read_text().splitlines()
            view = [c for c in calls if c.startswith("pr view 12")]
            runs = [c for c in calls if c.startswith("run list")]
            self.assertEqual(len(view), 1, calls)
            self.assertEqual(len(runs), 1, calls)
            self.assertIn(f"-R {selected}", view[0], command)
            self.assertIn(f"-R {selected}", runs[0], command)

    def test_no_selected_repository_selects_none(self):
        self.plant(body=self.GOOD)
        self.allowed(self.run_bash("gh pr ready 12"))
        self.assertNotIn("-R", (self.fix / "calls.log").read_text())

    def test_the_docstring_table_names_the_row(self):
        text = HOOK.read_text(encoding="utf-8")
        self.assertIn("pr-proof", text.split('"""', 2)[1])


if __name__ == "__main__":
    unittest.main()
