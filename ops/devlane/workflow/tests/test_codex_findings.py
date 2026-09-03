"""Regression guards for the six P1 findings from Codex's review of PR #3.

Each names the finding it exists to keep fixed. Every one was verified to
reproduce against `69d6377` before the fix landed.
"""

import json
import unittest

import support
from support import SandboxCase
import canonical
from errors import EXIT_OK, EXIT_REFUSED


class StagedFiles(SandboxCase):
    """[P1] Keep pre-staged files out of workflow commits."""

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)

    def test_a_pre_staged_product_file_is_not_swept_into_a_wf_commit(self):
        self.sb.write("product.rs", "fn main() {}\n")
        self.sb._git("add", "product.rs")
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)

        committed = self.sb._git("show", "--name-only", "--format=", "HEAD").split()
        self.assertNotIn("product.rs", committed,
                         "wf must not commit work it did not stage")
        self.assertTrue(any(p.endswith("chains/WO-001.jsonl") for p in committed))
        # And it stays staged, because it was never wf's to commit or to drop.
        self.assertIn("product.rs", self.sb._git("diff", "--cached", "--name-only"))


class CommitIdentity(SandboxCase):
    """[P1] Force the mandated owner identity on generated commits."""

    def setUp(self):
        super().setUp()
        self.sb._git("config", "user.name", "some-agent")
        self.sb._git("config", "user.email", "agent@example.invalid")
        self.sb.wf("init", check=EXIT_OK)

    def declare_identity(self):
        meta = self.sb.root / "meta.json"
        body = canonical.loads(meta.read_bytes())
        body["commit_identity"] = {"name": "owner", "email": "owner@example.invalid"}
        meta.write_bytes(canonical.dumpb(body))

    def test_uses_the_identity_meta_json_declares_not_the_ambient_config(self):
        self.declare_identity()
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        who = self.sb._git("log", "-1", "--format=%an <%ae>|%cn <%ce>").strip()
        self.assertEqual(who, "owner <owner@example.invalid>|owner <owner@example.invalid>")

    def test_falls_back_to_ambient_config_when_the_repo_declares_none(self):
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        self.assertIn("some-agent", self.sb._git("log", "-1", "--format=%an"))

    def test_the_export_does_not_drop_the_declared_identity(self):
        # gitio.export rewrites meta.json; rebuilding it from a literal would
        # silently delete the key that governs every future auto-commit.
        self.declare_identity()
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        self.sb.wf("export", check=EXIT_OK)
        body = canonical.loads((self.sb.root / "meta.json").read_bytes())
        self.assertEqual(body["commit_identity"]["name"], "owner")
        self.assertEqual(body["format_version"], 1)

    def test_a_malformed_commit_identity_refuses(self):
        meta = self.sb.root / "meta.json"
        body = canonical.loads(meta.read_bytes())
        body["commit_identity"] = {"name": "owner"}
        meta.write_bytes(canonical.dumpb(body))
        proc = self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                          check=EXIT_REFUSED)
        self.assertIn("commit_identity", proc.stderr)


class AgentIdentity(SandboxCase):
    """[P1] Require a complete co-author identity."""

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)

    def test_a_bare_agent_name_refuses_before_it_reaches_a_trailer(self):
        proc = self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                          agent="bare-name-agent", check=EXIT_REFUSED)
        self.assertIn("vendor address", proc.stderr)
        self.assertEqual(self.sb._git("log", "--format=%s").count("wf("), 0)

    def test_a_complete_identity_is_accepted_and_becomes_the_trailer(self):
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   agent="GPT-5 Codex <noreply@openai.com>", check=EXIT_OK)
        self.assertIn("Co-Authored-By: GPT-5 Codex <noreply@openai.com>",
                      self.sb._git("log", "-1", "--format=%B"))

    def test_shapes_that_are_not_identities(self):
        for bad in ("agent", "agent <>", "<noreply@x.ai>", "agent <not-an-email>"):
            with self.subTest(bad=bad):
                proc = self.sb.wf("open", "--kind", "tdd", "--objective", "o",
                                  agent=bad, check=EXIT_REFUSED)
                self.assertIn("identity", proc.stderr)


class SourceProvenance(SandboxCase):
    """[P1] Require content provenance before auto-commit."""

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)

    def test_open_refuses_without_a_source(self):
        # raw=True bypasses the sandbox's default --source, which is exactly
        # the requirement under test.
        proc = self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                          raw=True, check=EXIT_REFUSED)
        self.assertIn("names the source", proc.stderr)

    def test_a_blank_source_is_not_a_provenance_claim(self):
        proc = self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                          "--source", "   ", raw=True, check=EXIT_REFUSED)
        self.assertIn("names the source", proc.stderr)

    def test_outcome_refuses_without_a_source(self):
        self.sb.seed_project()
        self.sb.wf("open", "WO-001", "--kind", "artifact", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        proc = self.sb.wf("outcome", "WO-001", "accepted", "--by", "x",
                          raw=True, check=EXIT_REFUSED)
        self.assertIn("names the source", proc.stderr)

    def test_advance_needs_none_because_it_records_no_content(self):
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)

    def test_a_receipt_sources_itself_from_the_command_it_ran(self):
        self.sb.seed_project()
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=EXIT_OK)
        events = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001").stdout)["events"]
        receipt = next(e for e in events if e["type"] == "receipt.red")
        self.assertEqual(
            receipt["sources"],
            ["generated: " + " ".join(support.Sandbox.GATE_ARGV)],
        )

    def test_an_explicit_source_still_wins_on_a_receipt(self):
        self.sb.seed_project()
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.wf("red", "WO-001", "--source", "owner 2026-08-20", "--",
                   *support.Sandbox.GATE_ARGV, check=EXIT_OK)
        events = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001").stdout)["events"]
        receipt = next(e for e in events if e["type"] == "receipt.red")
        self.assertEqual(receipt["sources"], ["owner 2026-08-20"])


class OutcomeAtomicity(SandboxCase):
    """[P1] Validate outcome movement before appending its statement."""

    def spec_with(self, stages, version=2):
        raw = canonical.loads(
            (self.sb.root / "gate-kinds" / "artifact.json").read_bytes()
        )
        raw["version"] = version
        raw["stages"] = stages
        path = self.sb.root / "gate-kinds" / f"artifact@{version}.json"
        path.write_bytes(canonical.dumpb(raw))
        self.sb.commit_all(f"sandbox: register artifact@{version}")
        self.sb.wf("init", check=EXIT_OK)

    def test_an_unresolvable_movement_records_nothing(self):
        # advance declared on the last stage: the movement cannot resolve, and
        # the statement must not survive the refusal.
        self.sb.wf("init", check=EXIT_OK)
        self.spec_with([
            {"name": "draft", "leave_requires": []},
            {"name": "last", "leave_requires": [],
             "outcomes": {"accepted": "advance"}},
        ])
        self.sb.wf("open", "WO-001", "--kind", "artifact", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        before = json.loads(self.sb.wf("--json", "status", "WO-001").stdout)

        proc = self.sb.wf("outcome", "WO-001", "accepted", "--by", "x",
                          check=EXIT_REFUSED)
        self.assertIn("stage to advance into", proc.stderr)

        after = json.loads(self.sb.wf("--json", "status", "WO-001").stdout)
        self.assertEqual(after["seq"], before["seq"],
                         "a refusal must record nothing, not half a transition")
        self.assertEqual(after["outcomes"], [])
        self.assertEqual(after["head"], before["head"])


class ForwardNamedOutcome(SandboxCase):
    """[P1] Enforce evidence for forward named outcomes."""

    def test_a_named_forward_target_cannot_step_over_leave_requires(self):
        # The hole: the evidence check tested only the literal "advance"
        # effect, so a spec naming a later stage skipped every receipt.
        self.sb.seed_project()
        self.sb.wf("init", check=EXIT_OK)
        raw = canonical.loads((self.sb.root / "gate-kinds" / "tdd.json").read_bytes())
        raw["version"] = 2
        raw["stages"] = [
            {"name": "spec", "leave_requires": [],
             "outcomes": {"skip": "impl", "back": "spec"}},
            {"name": "red", "leave_requires": ["receipt.red"]},
            {"name": "impl", "leave_requires": ["receipt.green"],
             "seals_frozen_set": True},
        ]
        raw["stages"][0]["leave_requires"] = ["receipt.red"]
        (self.sb.root / "gate-kinds" / "tdd@2.json").write_bytes(canonical.dumpb(raw))
        self.sb.commit_all("sandbox: register tdd@2")
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)

        proc = self.sb.wf("outcome", "WO-001", "skip", "--by", "x",
                          check=EXIT_REFUSED)
        self.assertIn("evidence its gate kind requires", proc.stderr)
        self.assertIn("receipt.red", proc.stderr)

        # Backward movement stays recordable whatever is missing.
        self.sb.wf("outcome", "WO-001", "back", "--by", "x", check=EXIT_OK)


if __name__ == "__main__":
    unittest.main()
