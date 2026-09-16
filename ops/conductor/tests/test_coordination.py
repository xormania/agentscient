"""The coordination core: participants, assignments, messages, evidence.

Contract: `ops/conductor/coordination-lever.md`. The tool
`ops/conductor/tools/coordination.py` is the subject and is run as a
subprocess under a scratch XDG_STATE_HOME, a staged lane conf, and the
real deliverable lever for the lock a claim gates on. Each session is
given its own CLAUDE_CODE_SESSION_ID, because the defect this module
exists to close is that the engine's holder is the agent string: the
rows below bind three participants that share one WF_AGENT value and
prove they are three.

Written by hand under grant 258 (owner, 2026-09-16: "hand grant ok'd",
relayed by the Lead session agentscient-11), one producer (Claude Opus
5, 1M context), the second producer absent by the owner's word
(AGENTS.md §Ground rules). The one command that reads this file is
`python3 -m unittest discover -s ops/conductor/tests -p test_coordination.py`:
red while `coordination.py` is absent, read again after it is written;
both readings are quoted in the commit that carries it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from ops.testkit import RefusalCase, World, refusal_wire, run, run_table

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "ops" / "conductor" / "tools"
TOOL = TOOLS / "coordination.py"
LOCK_LEVER = TOOLS / "deliverable.py"

# One WF_AGENT value for every session on the host, which is the state
# .claude/settings.local.json puts a host in (LD-50, instrument.py:93-99).
SHARED = "Claude Opus 5 (1M context) <noreply@example.test>"
LEAD = "sess-lead"
WORKER = "sess-worker"
CHECKER = "sess-checker"
BRANCH = "lane/session-20260916-x"


class _Scratch(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="coordination-")
        self.addCleanup(self.world.close)
        self.xdg = self.world.xdg_state
        self.conf = self.world.plant_text("lane.conf", "LANE_NAME='testlane'\n")
        self.store = self.xdg / "testlane" / "state.db"

    def env(self, session: str | None, identity: str | None = SHARED) -> dict:
        env = self.world.env(extra={"LANE_CONF": str(self.conf)})
        if identity:
            env["WF_AGENT"] = identity
        if session:
            env["CLAUDE_CODE_SESSION_ID"] = session
        return env

    def run_tool(self, *argv, session=LEAD, identity=SHARED, tool=None):
        return run(
            [sys.executable, str(tool or TOOL), *argv],
            cwd=self.world.cwd, env=self.env(session, identity), timeout=60,
        )

    def ok(self, *argv, session=LEAD, identity=SHARED) -> str:
        proc = self.run_tool(*argv, session=session, identity=identity)
        self.assertEqual(proc.exit, 0, f"{argv}: {proc.stderr}")
        return proc.stdout

    def lock(self, branch=BRANCH):
        """The real lever writes the lock a claim reads."""
        proc = run(
            [sys.executable, str(LOCK_LEVER), "add", branch, "--why", "the trial"],
            cwd=self.world.cwd, env=self.env(LEAD), timeout=60,
        )
        self.assertEqual(proc.exit, 0, proc.stderr)

    # -- fixtures ----------------------------------------------------------

    def bind_three(self):
        """Lead, worker and checker: one agent string, three sessions."""
        self.ok("bind", "--roles", "lead,coordinator", session=LEAD)
        self.ok("bind", "--roles", "worker", session=WORKER)
        self.ok("bind", "--roles", "verifier", session=CHECKER)

    def offered(self, to="PT-2"):
        self.bind_three()
        out = self.ok("draft", "a bounded repair", "--outcome", "the row refuses",
                      "--revision", "a1b2c3d", session=LEAD)
        aid = out.split()[-1]
        self.ok("offer", aid, "--to", to, session=LEAD)
        return aid

    def held(self):
        self.lock()
        aid = self.offered()
        self.ok("claim", aid, "--branch", BRANCH, "--generation", "1", session=WORKER)
        return aid

    def submitted(self):
        aid = self.held()
        self.ok("observe", aid, "--observation", "the suite ran",
                "--revision", "a1b2c3d", "--execution", "20260916T010203Z-job-x",
                session=WORKER)
        self.ok("submit", aid, "--evidence", "a1b2c3d", "--revision", "a1b2c3d",
                "--generation", "1", session=WORKER)
        return aid


class Participants(_Scratch):
    def test_one_agent_string_three_sessions_are_three_participants(self):
        """The defect the core closes: machine.py:255 compares the agent
        string, which every session on this host shares."""
        self.bind_three()
        ids = {self.ok("who", session=s).split()[1]
               for s in (LEAD, WORKER, CHECKER)}
        self.assertEqual(len(ids), 3, f"three sessions, {len(ids)} participant(s): {ids}")

    def test_who_names_this_session_not_another(self):
        self.bind_three()
        self.assertIn("worker", self.ok("who", session=WORKER))
        self.assertNotIn("worker", self.ok("who", session=LEAD))

    def test_bind_twice_replaces_this_session_row(self):
        self.ok("bind", "--roles", "worker", session=WORKER)
        first = self.ok("who", session=WORKER).split()[1]
        self.ok("bind", "--roles", "worker,verifier", session=WORKER)
        self.assertEqual(self.ok("who", session=WORKER).split()[1], first)
        self.assertIn("verifier", self.ok("who", session=WORKER))

    def test_the_acting_participant_cannot_be_supplied(self):
        """Objective §7: a caller-supplied actor confers no authority."""
        self.bind_three()
        proc = self.run_tool("who", "--participant", "PT-1", session=WORKER)
        refusal_wire(RefusalCase("supplied-participant", ("who",), "arguments"), proc)


class Assignments(_Scratch):
    def test_the_vertical_path_reaches_accepted(self):
        aid = self.submitted()
        self.ok("verify", aid, "--evidence", "a1b2c3d", "--generation", "1",
                session=CHECKER)
        self.ok("accept", aid, "--evidence", "a1b2c3d", "--generation", "1",
                session=LEAD)
        self.assertIn("accepted", self.ok("show", aid, session=LEAD))

    def test_a_worker_may_not_offer(self):
        self.bind_three()
        out = self.ok("draft", "a repair", "--outcome", "it refuses", session=LEAD)
        aid = out.split()[-1]
        proc = self.run_tool("offer", aid, "--to", "PT-2", session=WORKER)
        refusal_wire(RefusalCase("worker-offers", (), "role", named=("lead",)), proc)

    def test_a_claim_by_another_participant_refuses_recipient(self):
        self.lock()
        self.bind_three()
        aid = self.offered(to="PT-2")
        proc = self.run_tool("claim", aid, "--branch", BRANCH, "--generation", "1",
                             session=CHECKER)
        refusal_wire(RefusalCase("wrong-claimant", (), "recipient"), proc)

    def test_a_claim_off_the_lock_refuses_deliverable(self):
        self.bind_three()
        aid = self.offered()
        proc = self.run_tool("claim", aid, "--branch", "lane/not-on-the-board",
                             "--generation", "1", session=WORKER)
        refusal_wire(RefusalCase("claim-off-lock", (), "deliverable"), proc)

    def test_a_second_claim_refuses_taken(self):
        aid = self.held()
        proc = self.run_tool("claim", aid, "--branch", BRANCH, "--generation", "1",
                             session=WORKER)
        refusal_wire(RefusalCase("second-claim", (), "taken"), proc)


class GenerationAndRevision(_Scratch):
    def test_a_stale_holder_cannot_submit_after_reassignment(self):
        """AC-03: the place alone returns to `held`, so the generation is
        what refuses the old holder."""
        aid = self.held()
        self.ok("reassign", aid, "--to", "PT-3", "--why", "the worker went quiet",
                "--generation", "1", session=LEAD)
        proc = self.run_tool("submit", aid, "--evidence", "a1b2c3d",
                             "--revision", "a1b2c3d", "--generation", "1",
                             session=WORKER)
        refusal_wire(RefusalCase("stale-generation", (), "generation",
                                 named=("1", "2")), proc)

    def test_release_bumps_the_generation(self):
        aid = self.held()
        self.ok("release", aid, "--why", "blocked on the wall", "--generation", "1",
                session=WORKER)
        self.assertIn("generation 2", self.ok("show", aid, session=LEAD))

    def test_verify_refuses_an_observation_of_another_revision(self):
        self.lock()
        self.bind_three()
        aid = self.offered()
        self.ok("claim", aid, "--branch", BRANCH, "--generation", "1", session=WORKER)
        self.ok("observe", aid, "--observation", "ran at the old tree",
                "--revision", "9999999", session=WORKER)
        self.ok("submit", aid, "--evidence", "a1b2c3d", "--revision", "a1b2c3d",
                "--generation", "1", session=WORKER)
        proc = self.run_tool("verify", aid, "--evidence", "9999999",
                             "--generation", "1", session=CHECKER)
        refusal_wire(RefusalCase("stale-revision", (), "revision"), proc)

    def test_reopen_stales_the_observations_and_keeps_them(self):
        """AC-10: a changed candidate needs reassessment; the old row stays."""
        aid = self.submitted()
        self.ok("verify", aid, "--evidence", "a1b2c3d", "--generation", "1",
                session=CHECKER)
        self.ok("reopen", aid, "--revision", "beefbee", "--why", "the candidate moved",
                "--generation", "1", session=LEAD)
        current = self.ok("observations", aid, session=LEAD)
        self.assertNotIn("the suite ran", current)
        self.assertIn("the suite ran", self.ok("observations", aid, "--all", session=LEAD))


class Producers(_Scratch):
    def test_the_producer_cannot_verify_its_own_candidate(self):
        """AC-11: an independent pass is not a role label away."""
        aid = self.submitted()
        self.ok("bind", "--roles", "worker,verifier", session=WORKER)
        proc = self.run_tool("verify", aid, "--evidence", "a1b2c3d",
                             "--generation", "1", session=WORKER)
        refusal_wire(RefusalCase("self-verify", (), "producer"), proc)

    def test_the_producer_cannot_accept_its_own_candidate(self):
        aid = self.submitted()
        self.ok("verify", aid, "--evidence", "a1b2c3d", "--generation", "1",
                session=CHECKER)
        self.ok("bind", "--roles", "worker,lead", session=WORKER)
        proc = self.run_tool("accept", aid, "--evidence", "a1b2c3d",
                             "--generation", "1", session=WORKER)
        refusal_wire(RefusalCase("self-accept", (), "producer"), proc)


class Messages(_Scratch):
    def test_an_ack_does_not_resolve_an_obligation(self):
        """AC-04: acknowledgment and resolution are separate facts."""
        self.bind_three()
        mid = self.ok("send", "--to", "PT-2", "--purpose", "request",
                      "--body", "name the reading", session=LEAD).split()[1]
        self.ok("ack", mid, session=WORKER)
        self.assertIn(mid, self.ok("outstanding", session=LEAD))
        self.ok("resolve", mid, "--evidence", "a1b2c3d", session=WORKER)
        self.assertNotIn(mid, self.ok("outstanding", session=LEAD))

    def test_the_four_delivery_facts_are_kept_apart(self):
        self.bind_three()
        mid = self.ok("send", "--to", "PT-2", "--purpose", "request",
                      "--body", "name the reading", session=LEAD).split()[1]
        self.ok("deliver", mid, "--ref", "750aa45e-a0c6", session=LEAD)
        shown = self.ok("show", mid, session=LEAD)
        self.assertIn("queued", shown)
        self.assertIn("750aa45e-a0c6", shown)
        self.assertNotIn("acked", shown)

    def test_an_inform_is_not_an_obligation(self):
        self.bind_three()
        self.ok("send", "--to", "PT-2", "--purpose", "inform",
                "--body", "the trunk moved", session=LEAD)
        self.assertIn("none", self.ok("outstanding", session=LEAD))

    def test_a_role_addressee_reaches_the_holder_of_the_role(self):
        self.bind_three()
        mid = self.ok("send", "--to", "verifier", "--purpose", "request",
                      "--body", "examine the candidate", session=LEAD).split()[1]
        self.assertIn(mid, self.ok("inbox", session=CHECKER))
        self.assertNotIn(mid, self.ok("inbox", session=WORKER))

    def test_only_the_recipient_resolves(self):
        self.bind_three()
        mid = self.ok("send", "--to", "PT-2", "--purpose", "request",
                      "--body", "name the reading", session=LEAD).split()[1]
        proc = self.run_tool("resolve", mid, "--evidence", "a1b2c3d", session=CHECKER)
        refusal_wire(RefusalCase("wrong-resolver", (), "recipient"), proc)


class Resources(_Scratch):
    def test_two_sessions_cannot_hold_one_resource(self):
        """AC-09: the engine's hold is the lease; no new machinery."""
        aid = self.held()
        self.ok("reserve", "the-suite", "--for", aid, session=WORKER)
        proc = self.run_tool("reserve", "the-suite", "--for", aid, session=CHECKER)
        refusal_wire(RefusalCase("double-reserve", (), "taken"), proc)
        self.ok("free", "the-suite", "--why", "the run finished", session=WORKER)
        self.ok("reserve", "the-suite", "--for", aid, session=CHECKER)


class Decisions(_Scratch):
    def test_only_a_lead_decides(self):
        self.bind_three()
        did = self.ok("ask", "--question", "ship or hold?",
                      "--alternatives", "ship|hold", session=LEAD).split()[1]
        proc = self.run_tool("decide", did, "--choice", "ship",
                             "--rationale", "the suite is green", session=WORKER)
        refusal_wire(RefusalCase("worker-decides", (), "role", named=("lead",)), proc)

    def test_a_brief_without_counterevidence_says_so(self):
        self.bind_three()
        did = self.ok("ask", "--question", "ship or hold?",
                      "--alternatives", "ship|hold", session=LEAD).split()[1]
        self.assertIn("declared gap", self.ok("decision", did, session=LEAD))


class Brief(_Scratch):
    def test_a_restarted_participant_recovers_its_obligations(self):
        """AC-12: the brief is what a compacted session reads back."""
        aid = self.held()
        self.ok("send", "--to", "PT-2", "--purpose", "request",
                "--body", "name the reading", session=LEAD)
        brief = self.ok("brief", session=WORKER)
        self.assertIn(aid, brief)
        self.assertIn("name the reading", brief)

    def test_coverage_names_the_gap(self):
        aid = self.submitted()
        coverage = self.ok("coverage", session=LEAD)
        self.assertIn(aid, coverage)
        self.assertIn("gap", coverage)


class Absence(_Scratch):
    def test_a_read_with_no_store_looked_and_found_nothing(self):
        self.assertFalse(self.store.exists())
        self.assertIn("no store", self.ok("assignments", session=LEAD))
        self.assertFalse(self.store.exists(), "a read created the store")


class Wire(_Scratch):
    ROWS = (
        RefusalCase("unknown-verb", ("teleport",), "arguments"),
        RefusalCase("no-identity", ("bind", "--roles", "worker"), "identity"),
        RefusalCase("bad-id", ("show", "A-x"), "id"),
        RefusalCase("unknown-id", ("show", "A-404"), "unknown"),
    )

    def test_the_refusal_wire_holds_on_every_row(self):
        self.bind_three()
        run_table(self, self.ROWS, lambda row: self.run_tool(
            *row.argv, session=LEAD,
            identity=None if row.id == "no-identity" else SHARED))

    def test_a_bind_with_no_session_id_refuses_session(self):
        proc = self.run_tool("bind", "--roles", "worker", session=None)
        refusal_wire(RefusalCase("no-session", (), "session"), proc)

    def test_a_verb_before_bind_refuses_participant(self):
        proc = self.run_tool("draft", "a repair", "--outcome", "it refuses",
                             session=LEAD)
        refusal_wire(RefusalCase("unbound", (), "participant"), proc)


class DispatchedWorkers(_Scratch):
    """A dispatched Codex or Grok worker has no harness session id of its
    own, so it could hold no participant and every mutation it made
    refused class participant. The launcher mints a session id per
    dispatch; a dispatcher binds a participant to it. Raised by
    agentscient-1c against the contract at 537f3a35."""

    MINTED = "dispatch-7f3a4c21"

    def as_worker(self, *argv, sid=None):
        """The worker's environment: the older CLAUDE_SESSION_ID key, which
        is what the launcher sets and instrument.session() already admits."""
        env = self.world.env(extra={"LANE_CONF": str(self.conf)})
        env["WF_AGENT"] = SHARED
        env["CLAUDE_SESSION_ID"] = sid or self.MINTED
        return run([sys.executable, str(TOOL), *argv],
                   cwd=self.world.cwd, env=env, timeout=60)

    def dispatched(self):
        self.lock()
        self.ok("bind", "--roles", "lead,coordinator,dispatcher", session=LEAD)
        aid = self.ok("draft", "review the core", "--outcome", "findings",
                      "--revision", "a1b2c3d", session=LEAD).split()[-1]
        self.ok("bind-for", "--session", self.MINTED, "--roles", "worker",
                "--for", aid, session=LEAD)
        return aid

    def test_a_dispatched_worker_holds_a_participant_of_its_own(self):
        self.dispatched()
        who = self.as_worker("who")
        self.assertEqual(who.exit, 0, who.stderr)
        self.assertIn("worker", who.stdout)
        self.assertIn(self.MINTED, who.stdout)
        self.assertNotIn("PT-1 ", who.stdout)

    def test_a_dispatched_worker_can_record_its_own_findings(self):
        aid = self.dispatched()
        done = self.as_worker("observe", aid, "--observation", "the row refuses",
                              "--revision", "a1b2c3d")
        self.assertEqual(done.exit, 0, done.stderr)
        self.assertIn("the row refuses", self.ok("observations", aid, session=LEAD))

    def test_only_a_dispatcher_binds_a_participant_for_another_session(self):
        self.bind_three()
        proc = self.run_tool("bind-for", "--session", self.MINTED, "--roles", "worker",
                             "--for", "A-1", session=WORKER)
        refusal_wire(RefusalCase("worker-binds-for", (), "role",
                                 named=("dispatcher",)), proc)

    def test_the_binding_records_its_issuer_and_its_assignment(self):
        aid = self.dispatched()
        listed = self.ok("participants", session=LEAD)
        self.assertIn("bound by PT-1", listed)
        self.assertIn(f"for {aid}", listed)


if __name__ == "__main__":
    unittest.main()
