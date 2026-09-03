"""Findings from the PR #10 cross-review (Codex and Grok, both CHANGES).

Each class pins one finding. Written red before any fix, per
ops/process/tdd.md; the reviewers effectively authored these specs, and the
fix commits credit them.
"""

import json
import unittest

import support
from support import SandboxCase
import canonical
import gatekinds
from errors import EXIT_OK, EXIT_REFUSED, Refusal

OTHER = "Other Agent <noreply@example.invalid>"


class TheSkipKeepsHeldChainsOutOfTheCommit(SandboxCase):
    """[P1 Codex+Grok] do_commit filtered the bind list, not the commit.

    The held work order was skipped from `commit.landed` — and its chain file
    still rode into the git commit under the skipper's trailers. After that
    the tree was clean, so the holder's own later `wf commit` had nothing to
    commit and the lines never got a bind stamped by their author.
    """

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "mine",
                   check=EXIT_OK)
        # The other agent records on their own work order without flushing,
        # then claims it — leaving their chain dirty in the export while a
        # live claim says the work is theirs.
        self.sb.wf("open", "WO-002", "--kind", "tdd", "--objective", "theirs",
                   "--no-commit", agent=OTHER, check=EXIT_OK)
        self.sb.wf("claim", "WO-002", "--ttl", "2h", agent=OTHER, check=EXIT_OK)

    def flush(self):
        return json.loads(self.sb.wf("--json", "commit", check=EXIT_OK).stdout)

    def committed_files(self):
        return self.sb._git("show", "--name-only", "--format=", "HEAD").split()

    def test_the_held_chain_file_stays_out_of_the_git_commit(self):
        self.flush()
        files = self.committed_files()
        self.assertNotIn("ops/devlane/workflow/chains/WO-002.jsonl", files,
                         "the held chain rode into the skipper's commit")

    def test_the_held_chain_stays_dirty_for_its_holder_to_commit(self):
        self.flush()
        status = self.sb._git("status", "--porcelain")
        self.assertIn("chains/WO-002.jsonl", status,
                      "nothing left for the holder to commit and bind")
        # And the holder can: their own flush commits and binds their chain.
        body = json.loads(
            self.sb.wf("--json", "commit", agent=OTHER, check=EXIT_OK).stdout)
        self.assertIsNotNone(body.get("committed"))
        self.assertIn("ops/devlane/workflow/chains/WO-002.jsonl",
                      self.committed_files())

    def test_the_skip_is_reported_not_silent(self):
        body = self.flush()
        self.assertEqual(body.get("skipped_held"), ["WO-002"],
                         "a silent skip is a gap nobody notices")

    def test_an_expired_claim_does_not_skip(self):
        # Expiry ends the claim; the flush then binds normally. Uses a claim
        # already expired at write time rather than sleeping.
        self.sb.wf("release", "WO-002", agent=OTHER, check=EXIT_OK)
        body = self.flush()
        self.assertEqual(body.get("skipped_held", []), [])
        self.assertIn("ops/devlane/workflow/chains/WO-002.jsonl",
                      self.committed_files())


class CommitRequiresAnIdentity(SandboxCase):
    """[P1 Codex] `wf commit` never called require_agent.

    Every other appending verb refuses without an identity; commit wrote git
    commits and commit.landed events with an empty or malformed one. Every
    existing commit test silently supplied the sandbox's valid default.
    """

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   "--no-commit", check=EXIT_OK)

    def test_an_empty_identity_is_refused(self):
        proc = self.sb.wf("commit", agent="")
        self.assertEqual(proc.returncode, EXIT_REFUSED, proc.stderr)

    def test_a_bare_name_is_refused(self):
        proc = self.sb.wf("commit", agent="bare-name")
        self.assertEqual(proc.returncode, EXIT_REFUSED, proc.stderr)

    def test_no_commit_is_created_by_the_refusal(self):
        head = self.sb.head()
        self.sb.wf("commit", agent="")
        self.assertEqual(self.sb.head(), head,
                         "the refusal must land before the commit, not after")


class ExpiryEndsAClaimForItsOwnHolderToo(SandboxCase):
    """[P2 Codex+Grok] A lapsed claim reacquired by the same agent reported
    `renewed: true` with the pre-gap acquired_at — a hold that expired
    presented as a continuous heartbeat."""

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)

    def test_reacquiring_after_expiry_is_not_a_renewal(self):
        import time

        first = json.loads(
            self.sb.wf("--json", "claim", "WO-001", "--ttl", "1s",
                       check=EXIT_OK).stdout)
        time.sleep(1.2)
        second = json.loads(
            self.sb.wf("--json", "claim", "WO-001", "--ttl", "1h",
                       check=EXIT_OK).stdout)
        self.assertFalse(second["renewed"],
                         "an expired claim cannot be renewed, only retaken")
        self.assertGreater(second["acquired_at"], first["acquired_at"],
                           "a retake starts a new hold; the old stamp lies")

    def test_a_live_reclaim_is_still_a_renewal(self):
        first = json.loads(
            self.sb.wf("--json", "claim", "WO-001", "--ttl", "1h",
                       check=EXIT_OK).stdout)
        second = json.loads(
            self.sb.wf("--json", "claim", "WO-001", "--ttl", "1h",
                       check=EXIT_OK).stdout)
        self.assertTrue(second["renewed"])
        self.assertEqual(second["acquired_at"], first["acquired_at"])


class ClassValidationBindsToChecksOnly(unittest.TestCase):
    """[P2 Codex] The declared-class rule over-reached, and crashed on the
    malformed case it existed to refuse."""

    def base(self):
        return {
            "kind": "k", "version": 1,
            "stages": [{"name": "s", "leave_requires": []}],
            "checks": [{"name": "scan", "class": "security",
                        "argv": ["true"]}],
        }

    def test_a_non_check_receipt_class_needs_no_registered_check(self):
        # The reducer records receipt.<kind>:<class> for any receipt carrying
        # a class; only receipt.check receipts come from the checks registry.
        # Requiring conformance evidence must not depend on an unrelated
        # check happening to declare the same class word.
        raw = self.base()
        raw["stages"][0]["leave_requires"] = ["receipt.conformance:certified"]
        spec = gatekinds.Spec(raw, source="test")  # must load, not refuse
        self.assertEqual(spec.leave_requires("s"),
                         ["receipt.conformance:certified"])

    def test_a_check_requirement_class_must_still_be_declared(self):
        raw = self.base()
        raw["stages"][0]["leave_requires"] = ["receipt.check:sekurity"]
        with self.assertRaises(Refusal):
            gatekinds.Spec(raw, source="test")

    def test_malformed_checks_refuse_instead_of_crashing(self):
        for bad in (None, [None], [{"name": "x"}], "checks", [["a"]]):
            raw = self.base()
            raw["checks"] = bad
            raw["stages"][0]["leave_requires"] = ["receipt.check:security"]
            try:
                gatekinds.Spec(raw, source="test")
            except Refusal:
                pass  # the promised load-time refusal
            except Exception as exc:
                self.fail(f"checks={bad!r} raised {type(exc).__name__}: {exc}")
            else:
                self.fail(f"checks={bad!r} was accepted")


class NextIsReplayableWhenTheRootIsNotTheDefault(SandboxCase):
    """[P2 Codex+Grok] `advances` omitted --root, so the argv acted on the
    DEFAULT root (the real repo beside wf.py) when replayed verbatim from a
    sandbox or any non-default checkout. Every test papered over it by
    appending --root by hand."""

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)

    def test_the_advancing_argv_names_the_root_it_was_computed_for(self):
        body = json.loads(
            self.sb.wf("--json", "next", "WO-001", check=EXIT_OK).stdout)
        argv = body["advances"]
        self.assertIn("--root", argv,
                      "without --root the argv replays against the wrong root")
        root = argv[argv.index("--root") + 1]
        self.assertEqual(canonical.loads(canonical.dumpb(root)), root)
        self.assertTrue((support.Path(root) / "gate-kinds").is_dir()
                        if support.Path(root).is_absolute()
                        else (support.Path(self.sb.dir) / root
                              / "gate-kinds").is_dir(),
                        f"--root {root} does not point at the state root")

    def test_replaying_verbatim_advances_this_root_not_the_default(self):
        import os
        import subprocess

        body = json.loads(
            self.sb.wf("--json", "next", "WO-001", check=EXIT_OK).stdout)
        argv = list(body["advances"])
        support.assert_runnable(self, argv)
        proc = subprocess.run(
            argv, cwd=str(self.sb.dir), capture_output=True, text=True,
            env=dict(os.environ, WF_AGENT=support.Sandbox.AGENT),
        )
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
        self.assertEqual(
            json.loads(self.sb.wf("--json", "status", "WO-001").stdout)["stage"],
            "red", "the verbatim argv must act on THIS sandbox's chain")


if __name__ == "__main__":
    unittest.main()
