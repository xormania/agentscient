"""claim / release / sessions — coordination, and exit 3 (PLAN §4, Slice 2).

Written before the verbs exist. A claim is not evidence: it never touches
the chain, it is not exported, and losing it on rebuild is correct.
"""

import json
import unittest

import support
from support import SandboxCase
import canonical
from errors import EXIT_OK, EXIT_REFUSED, EXIT_CLAIMED, EXIT_USAGE

OTHER = "Other Agent <noreply@example.invalid>"


class ClaimCase(SandboxCase):
    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "claims",
                   check=EXIT_OK)

    def claim(self, *extra, agent=None, check=EXIT_OK):
        return json.loads(
            self.sb.wf("--json", "claim", "WO-001", *extra,
                       agent=agent, check=check).stdout or "{}"
        )

    def expire_the_claim(self):
        """Move the recorded expiry into the past.

        Waiting out a real TTL would make the suite slow and flaky; the
        expiry is a recorded timestamp, so moving it is the honest way to
        reach the state under test.
        """
        past = "2000-01-01T00:00:00.000000Z"
        support.plant_sql(
            self.sb.db,
            "UPDATE claims SET expires_at = ? WHERE wo_id = 'WO-001'",
            (past,),
            check=lambda c: c.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 1,
        )


class Acquire(ClaimCase):
    def test_claims_with_a_default_ttl(self):
        body = self.claim()
        self.assertEqual(body["wo"], "WO-001")
        self.assertEqual(body["agent"], support.Sandbox.AGENT)
        self.assertEqual(body["ttl_seconds"], 1800)
        self.assertFalse(body["renewed"])
        canonical.parse_time(body["expires_at"])

    def test_an_explicit_ttl_is_honoured(self):
        self.assertEqual(self.claim("--ttl", "2h")["ttl_seconds"], 7200)
        self.assertEqual(self.claim("--ttl", "45s")["ttl_seconds"], 45)

    def test_a_note_rides_with_the_claim(self):
        self.claim("--note", "driving the red stage")
        body = json.loads(self.sb.wf("--json", "status", "WO-001").stdout)
        self.assertEqual(body["claim"]["note"], "driving the red stage")

    def test_re_claiming_is_the_heartbeat_not_an_error(self):
        first = self.claim("--ttl", "45s")
        again = self.claim("--ttl", "2h")
        self.assertTrue(again["renewed"])
        self.assertGreater(again["expires_at"], first["expires_at"])
        self.assertEqual(again["acquired_at"], first["acquired_at"],
                         "a heartbeat extends the claim, it does not restart it")

    def test_a_live_claim_held_by_another_agent_exits_three(self):
        self.claim()
        proc = self.sb.wf("claim", "WO-001", agent=OTHER)
        self.assertEqual(proc.returncode, EXIT_CLAIMED, proc.stderr)
        self.assertIn("claimed by", proc.stderr)
        self.assertIn(support.Sandbox.AGENT, proc.stderr)

    def test_an_expired_claim_frees_the_work_without_anyone_overriding_it(self):
        self.claim()
        self.expire_the_claim()
        body = json.loads(
            self.sb.wf("--json", "claim", "WO-001", agent=OTHER, check=EXIT_OK).stdout
        )
        self.assertEqual(body["agent"], OTHER)
        self.assertFalse(body["renewed"])

    def test_a_ttl_that_is_not_a_duration_refuses(self):
        # `--ttl=X` rather than `--ttl X`, so argparse hands a leading-dash
        # value through as a value instead of reading it as a flag. `-5m` is
        # not here: a leading dash answers 64 on every interpreter and by
        # every spelling — see the bare-dash test below.
        for bad in ("soon", "30", "m30", "0m", "", "  "):
            with self.subTest(bad=bad):
                proc = self.sb.wf("claim", "WO-001", f"--ttl={bad}")
                self.assertEqual(proc.returncode, EXIT_REFUSED, proc.stderr)
                self.assertIn("ttl", proc.stderr)

    def test_a_bare_leading_dash_ttl_is_a_usage_error(self):
        # `--ttl -5m` is ambiguous to any argument parser; 64 is the honest
        # answer, and it is not the same answer as "that is not a duration".
        self.assertEqual(
            self.sb.wf("claim", "WO-001", "--ttl", "-5m").returncode, EXIT_USAGE
        )

    def test_claiming_an_unknown_work_order_refuses(self):
        proc = self.sb.wf("claim", "WO-404", check=EXIT_REFUSED)
        self.assertIn("work order exists", proc.stderr)

    def test_a_claim_is_not_evidence(self):
        before_events = json.loads(
            self.sb.wf("--json", "log", "--full", "--all", "WO-001").stdout
        )["events"]
        # The export always carries one pending bind (PLAN §3.6), so the
        # question is whether claiming *adds* to the tree, not whether the
        # tree is pristine.
        before_tree = self.sb._git("status", "--porcelain")
        before_head = self.sb.head()

        self.claim()

        events = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001").stdout)["events"]
        self.assertEqual([e for e in events if "claim" in e["type"]], [])
        self.assertEqual(len(events), len(before_events), "no event was appended")
        self.assertFalse((self.sb.root / "claims").exists())
        self.assertEqual(self.sb._git("status", "--porcelain"), before_tree,
                         "a claim must not touch the export")
        self.assertEqual(self.sb.head(), before_head, "a claim must not commit")


class Release(ClaimCase):
    def test_the_holder_can_release(self):
        self.claim()
        body = json.loads(self.sb.wf("--json", "release", "WO-001", check=EXIT_OK).stdout)
        self.assertTrue(body["released"])
        self.assertIsNone(
            json.loads(self.sb.wf("--json", "status", "WO-001").stdout)["claim"]
        )

    def test_another_agent_cannot_release_a_live_claim(self):
        self.claim()
        proc = self.sb.wf("release", "WO-001", agent=OTHER)
        self.assertEqual(proc.returncode, EXIT_CLAIMED, proc.stderr)
        self.assertIn("released by its holder", proc.stderr)

    def test_releasing_when_nothing_is_held_is_a_no_op_success(self):
        body = json.loads(self.sb.wf("--json", "release", "WO-001", check=EXIT_OK).stdout)
        self.assertFalse(body["released"])

    def test_an_expired_claim_can_be_cleared_by_anyone(self):
        self.claim()
        self.expire_the_claim()
        body = json.loads(
            self.sb.wf("--json", "release", "WO-001", agent=OTHER, check=EXIT_OK).stdout
        )
        self.assertTrue(body["released"])
        self.assertTrue(body["was_expired"])


class ClaimsGateTheChain(ClaimCase):
    """Claimed work is not yours to take (AGENTS.md §Teamwork)."""

    def test_another_agent_cannot_append_while_a_claim_is_live(self):
        self.claim()
        proc = self.sb.wf("advance", "WO-001", agent=OTHER)
        self.assertEqual(proc.returncode, EXIT_CLAIMED, proc.stderr)
        self.assertIn("claimed by", proc.stderr)

    def test_the_holder_works_normally(self):
        self.claim()
        self.sb.wf("advance", "WO-001", check=EXIT_OK)

    def test_an_unclaimed_work_order_is_open_to_anyone(self):
        self.sb.wf("advance", "WO-001", agent=OTHER, check=EXIT_OK)

    def test_an_expired_claim_stops_blocking(self):
        self.claim()
        self.expire_the_claim()
        self.sb.wf("advance", "WO-001", agent=OTHER, check=EXIT_OK)

    def test_reading_is_never_blocked(self):
        self.claim()
        for argv in (["status", "WO-001"], ["next", "WO-001"], ["log", "WO-001"],
                     ["verify"]):
            with self.subTest(argv=argv):
                self.sb.wf(*argv, agent=OTHER, check=EXIT_OK)


class NextAndStatusShowTheClaim(ClaimCase):
    def test_next_carries_the_claim_it_reserved_a_key_for(self):
        # Slice 1 shipped "claim": null so this shape would not move.
        self.claim("--ttl", "2h")
        body = json.loads(self.sb.wf("--json", "next", "WO-001").stdout)
        self.assertEqual(body["claim"]["agent"], support.Sandbox.AGENT)
        canonical.parse_time(body["claim"]["expires_at"])

    def test_an_expired_claim_reads_as_no_claim(self):
        self.claim()
        self.expire_the_claim()
        body = json.loads(self.sb.wf("--json", "next", "WO-001").stdout)
        self.assertIsNone(body["claim"])


class Sessions(ClaimCase):
    def test_status_reports_who_is_active(self):
        self.sb.wf("status", agent=OTHER, check=EXIT_OK)
        body = json.loads(self.sb.wf("--json", "status", check=EXIT_OK).stdout)
        agents = {s["agent"] for s in body["sessions"]}
        self.assertIn(OTHER, agents)
        self.assertIn(support.Sandbox.AGENT, agents)

    def test_sessions_are_one_row_per_agent_not_per_invocation(self):
        for _ in range(3):
            self.sb.wf("status", check=EXIT_OK)
        body = json.loads(self.sb.wf("--json", "status", check=EXIT_OK).stdout)
        mine = [s for s in body["sessions"] if s["agent"] == support.Sandbox.AGENT]
        self.assertEqual(len(mine), 1)

    def test_sessions_are_not_exported(self):
        before = self.sb._git("status", "--porcelain")
        self.sb.wf("status", check=EXIT_OK)
        self.assertFalse((self.sb.root / "sessions").exists())
        self.assertEqual(self.sb._git("status", "--porcelain"), before,
                         "recording presence must not touch the export")


class NotExported(ClaimCase):
    def test_a_rebuild_drops_claims_and_that_is_correct(self):
        self.claim()
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.db.unlink()
        self.sb.wf("init", "--rebuild", check=EXIT_OK)
        self.assertIsNone(
            json.loads(self.sb.wf("--json", "status", "WO-001").stdout)["claim"],
            "a claim that outlived the agent holding it is worse than none",
        )


if __name__ == "__main__":
    unittest.main()
