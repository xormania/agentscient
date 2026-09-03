"""outcome — effects come from the spec, and owner-reserved ones are
recorded without being applied (PLAN §3.5, D10)."""

import json
import unittest

import support
from support import SandboxCase
from errors import EXIT_OK, EXIT_REFUSED


class OutcomeCase(SandboxCase):
    """A tdd work order driven to its review stage."""

    def setUp(self):
        super().setUp()
        self.sb.seed_project()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)                       # red
        self.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)                       # impl
        self.sb.make_green()
        self.sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)                       # review

    def outcome(self, value, by="test-agent", *extra, check=EXIT_OK):
        return self.sb.wf("--json", "outcome", "WO-001", value, "--by", by,
                          *extra, check=check)

    def state(self):
        return json.loads(self.sb.wf("--json", "status", "WO-001", check=EXIT_OK).stdout)

    def events(self):
        raw = json.loads(
            self.sb.wf("--json", "log", "--full", "--all", "WO-001", check=EXIT_OK).stdout
        )["events"]
        return support.without_binds(raw)


class DeclaredEffects(OutcomeCase):
    def test_starts_in_review(self):
        self.assertEqual(self.state()["stage"], "review")

    def test_an_advancing_outcome_moves_to_the_next_stage(self):
        body = json.loads(self.outcome("accepted").stdout)
        self.assertEqual(body["declared_effect"], "advance")
        self.assertEqual(body["applied_effect"], "advance")
        self.assertEqual(body["stage"], "ratify")
        self.assertFalse(body["actor_reserved"])

    def test_the_statement_and_the_move_are_two_separate_events(self):
        self.outcome("accepted")
        types = [e["type"] for e in self.events()[-2:]]
        self.assertEqual(types, ["outcome", "stage.entered"])
        moved = self.events()[-1]
        self.assertEqual(moved["from_stage"], "review")
        self.assertEqual(moved["via_outcome"], "accepted")

    def test_a_named_stage_effect_re_enters_that_stage(self):
        body = json.loads(self.outcome("finding").stdout)
        self.assertEqual(body["declared_effect"], "impl")
        self.assertEqual(body["stage"], "impl")
        # Re-entering impl reseals from the latest red, so green can run again.
        self.assertIsNotNone(body["frozen"])
        self.assertEqual(body["satisfied"], [], "a new stage starts with no evidence")

    def test_a_terminal_outcome_closes_the_work_order_and_exits_zero(self):
        # "A recorded denial exits 0": recording the denial succeeded.
        proc = self.outcome("denied", check=EXIT_OK)
        body = json.loads(proc.stdout)
        self.assertEqual(body["applied_effect"], "terminal")
        self.assertEqual(body["status"], "terminal")
        self.assertEqual(proc.returncode, 0)

    def test_a_terminal_work_order_refuses_further_appends(self):
        self.outcome("denied")
        for argv in (["advance", "WO-001"],
                     ["outcome", "WO-001", "accepted", "--by", "x"]):
            with self.subTest(argv=argv):
                proc = self.sb.wf(*argv, check=EXIT_REFUSED)
                self.assertIn("the work order is open", proc.stderr)

    def test_records_who_stated_it_and_the_note(self):
        self.outcome("accepted", "grok-4.6", "--note", "looks right")
        event = [e for e in self.events() if e["type"] == "outcome"][-1]
        self.assertEqual(event["by"], "grok-4.6")
        self.assertEqual(event["note"], "looks right")
        self.assertEqual(event["agent"], support.Sandbox.AGENT,
                         "the stating actor and the recording agent are distinct")


class Refusals(OutcomeCase):
    def test_refuses_a_value_the_stage_does_not_declare(self):
        proc = self.outcome("ratified", check=EXIT_REFUSED)
        self.assertIn("declared by this stage", proc.stderr)
        self.assertIn("accepted, denied, finding", proc.stderr)

    def test_refuses_on_a_stage_that_declares_no_outcomes(self):
        self.sb.wf("open", "WO-002", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        proc = self.sb.wf("outcome", "WO-002", "accepted", "--by", "x",
                          check=EXIT_REFUSED)
        self.assertIn("declares outcomes", proc.stderr)
        self.assertIn("left by advancing", proc.stderr)

    def test_by_is_required(self):
        self.assertEqual(
            self.sb.wf("outcome", "WO-001", "accepted").returncode, 64
        )

    def test_a_denial_stays_recordable_when_evidence_is_missing(self):
        # Refusing to record a denial because something is missing would make
        # the record less honest, not more careful.
        self.sb.wf("advance", "WO-001", "--to", "red", "--reason", "reopened",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", "--to", "review", "--reason", "x",
                   check=EXIT_REFUSED)  # forward jumps still refuse


class OwnerReserved(OutcomeCase):
    """An agent typing 'ratified' must never become workflow state (D10)."""

    def setUp(self):
        super().setUp()
        self.outcome("accepted")          # review -> ratify
        self.assertEqual(self.state()["stage"], "ratify")

    def test_the_effect_is_withheld_when_an_agent_states_it(self):
        body = json.loads(self.outcome("ratified", "test-agent").stdout)
        self.assertEqual(body["declared_effect"], "terminal")
        self.assertIsNone(body["applied_effect"])
        self.assertTrue(body["actor_reserved"])
        self.assertEqual(body["status"], "open", "the work order must not close")
        self.assertEqual(body["stage"], "ratify")

    def test_the_effect_is_withheld_even_when_by_says_owner(self):
        # --by is evidence a statement was made, not proof of who made it.
        # The spec's actor marking is what gates the effect, not this flag.
        body = json.loads(self.outcome("ratified", "owner").stdout)
        self.assertIsNone(body["applied_effect"])
        self.assertEqual(body["status"], "open")
        event = [e for e in self.events() if e["type"] == "outcome"][-1]
        self.assertEqual(event["by"], "owner")
        self.assertIsNone(event["effect"])
        self.assertEqual(event["declared_effect"], "terminal")
        self.assertTrue(event["actor_reserved"])

    def test_the_statement_is_still_recorded_and_visible(self):
        self.outcome("ratified", "owner")
        self.assertIn("ratified", self.state()["outcomes"])
        self.assertEqual(self.events()[-1]["type"], "outcome")
        self.assertEqual(self.events()[-1]["value"], "ratified")

    def test_no_stage_entered_event_follows_a_withheld_effect(self):
        before = len(self.events())
        self.outcome("denied", "owner")
        after = self.events()
        self.assertEqual(len(after), before + 1, "exactly one event, no movement")
        self.assertEqual(after[-1]["type"], "outcome")

    def test_next_says_the_attestation_is_the_owners_merge(self):
        body = json.loads(self.sb.wf("--json", "next", "WO-001", check=EXIT_OK).stdout)
        self.assertIn("reserved to owner", body["note"])
        self.assertIn("D10", body["note"])
        support.assert_runnable(self, body["advances"])
        # Position-independent: the prefix may carry --root for a
        # non-default state root (as it does in this sandbox).
        argv = body["advances"]
        idx = argv.index("outcome")
        self.assertEqual(argv[idx:idx + 2], ["outcome", "WO-001"])
        self.assertEqual(body["advances"][-2:], ["--by", "owner"])


class ArtifactKind(SandboxCase):
    """The seeded artifact kind: draft -> review -> fix -> review -> ratify."""

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-009", "--kind", "artifact", "--objective", "doc",
                   check=EXIT_OK)

    def stage(self):
        return json.loads(
            self.sb.wf("--json", "status", "WO-009", check=EXIT_OK).stdout
        )["stage"]

    def test_a_finding_returns_to_fix_and_fix_returns_to_review(self):
        self.assertEqual(self.stage(), "draft")
        self.sb.wf("advance", "WO-009", check=EXIT_OK)
        self.assertEqual(self.stage(), "review")
        self.sb.wf("outcome", "WO-009", "finding", "--by", "codex", check=EXIT_OK)
        self.assertEqual(self.stage(), "fix")
        # Without advance_to this would fall through to ratify and skip review.
        self.sb.wf("advance", "WO-009", check=EXIT_OK)
        self.assertEqual(self.stage(), "review")

    def test_accepted_jumps_review_straight_to_ratify(self):
        self.sb.wf("advance", "WO-009", check=EXIT_OK)
        self.sb.wf("outcome", "WO-009", "accepted", "--by", "codex", check=EXIT_OK)
        self.assertEqual(self.stage(), "ratify")

    def test_ratify_is_owner_reserved_here_too(self):
        self.sb.wf("advance", "WO-009", check=EXIT_OK)
        self.sb.wf("outcome", "WO-009", "accepted", "--by", "codex", check=EXIT_OK)
        body = json.loads(
            self.sb.wf("--json", "outcome", "WO-009", "ratified", "--by", "owner",
                       check=EXIT_OK).stdout
        )
        self.assertIsNone(body["applied_effect"])
        self.assertEqual(body["status"], "open")


if __name__ == "__main__":
    unittest.main()
