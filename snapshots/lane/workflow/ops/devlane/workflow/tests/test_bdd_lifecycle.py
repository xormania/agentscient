"""BDD traceability cases not already proved by one workflow lifecycle test."""

import json
import sqlite3
import unittest

# isort: off
# support must import FIRST: it wires sys.path so errors (a workflow
# module) resolves at all — the same load-bearing order test_ci_shape
# pins, and a sorter must not undo it
import support
import errors
# isort: on


OTHER = "Other Agent <noreply@example.invalid>"


class WorkOrderLifecycleScenarios(support.SandboxCase):
    def setUp(self):
        super().setUp()
        self.sb.seed_project()
        self.sb.wf("init", check=errors.EXIT_OK)

    def open_work_order(self, objective="lifecycle"):
        return self.sb.wf(
            "--json",
            "open",
            "WO-001",
            "--kind",
            "tdd",
            "--objective",
            objective,
            check=errors.EXIT_OK,
        )

    def state(self):
        return json.loads(
            self.sb.wf(
                "--json",
                "status",
                "WO-001",
                check=errors.EXIT_OK,
            ).stdout
        )

    def events(self):
        raw = json.loads(
            self.sb.wf(
                "--json",
                "log",
                "--full",
                "--all",
                "WO-001",
                check=errors.EXIT_OK,
            ).stdout
        )["events"]
        return support.without_binds(raw)

    def durable_counts(self):
        connection = sqlite3.connect(str(self.sb.db))
        try:
            return {
                table: connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                for table in ("work_orders", "events", "claims", "attempts")
            }
        finally:
            connection.close()

    def test_opened_work_order_is_listed_at_its_first_stage(self):
        """Scenario: an opened work order is visible with its stage"""
        opened = json.loads(self.open_work_order("visible lifecycle").stdout)
        self.assertEqual(opened["stage"], "spec")

        proc = self.sb.wf(
            "--json",
            "status",
            check=errors.EXIT_OK,
        )
        body = json.loads(proc.stdout)

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(len(body["work_orders"]), 1)
        self.assertEqual(body["work_orders"][0]["wo"], "WO-001")
        self.assertEqual(body["work_orders"][0]["kind"], "tdd@1")
        self.assertEqual(body["work_orders"][0]["stage"], "spec")

    def test_second_claim_names_the_holder_and_exits_claimed(self):
        """Scenario: a second claimant is refused

        Measured 2026-08-22: a conflicting claim exits
        errors.EXIT_CLAIMED (3) with the holder and expiry on
        stderr; the holder keeps the claim. The bdd.md exit-0
        recorded-denial pattern belongs to gate OUTCOMES, not claim
        conflicts -- this scenario states the claim contract."""
        self.open_work_order()
        self.sb.wf("claim", "WO-001", check=errors.EXIT_OK)

        proc = self.sb.wf("claim", "WO-001", agent=OTHER,
                          check=errors.EXIT_CLAIMED)
        status = self.state()

        self.assertEqual(proc.returncode, errors.EXIT_CLAIMED)
        # "names the holder" means the holder's identity, not the
        # phrase — a generic "claimed by another agent" message
        # survived the phrase assertion (Grok, PR #33 review)
        self.assertIn(f"is claimed by {self.sb.AGENT}", proc.stderr)
        self.assertEqual(status["claim"]["agent"], self.sb.AGENT)
        self.assertNotEqual(status["claim"]["agent"], OTHER)

    def test_green_before_any_red_is_refused_without_advancing(self):
        """Scenario: green before red is refused"""
        self.open_work_order()
        self.sb.wf("claim", "WO-001", check=errors.EXIT_OK)
        before = self.state()

        proc = self.sb.wf(
            "green",
            "WO-001",
            "--",
            *support.Sandbox.GATE_ARGV,
        )
        after = self.state()
        green_events = [
            event for event in self.events()
            if event["type"] == "receipt.green"
        ]

        self.assertEqual(proc.returncode, errors.EXIT_REFUSED, proc.stderr)
        self.assertEqual(after["stage"], before["stage"])
        self.assertEqual(after["seq"], before["seq"])
        self.assertEqual(green_events, [])

    def test_full_claimed_walk_leaves_a_verifiable_chain(self):
        """Scenario: the chain verifies after a full walk"""
        self.open_work_order()
        self.sb.wf("claim", "WO-001", check=errors.EXIT_OK)
        self.sb.wf("advance", "WO-001", check=errors.EXIT_OK)
        self.sb.wf(
            "red",
            "WO-001",
            "--",
            *support.Sandbox.GATE_ARGV,
            check=errors.EXIT_OK,
        )
        self.sb.wf("advance", "WO-001", check=errors.EXIT_OK)
        self.sb.make_green()
        self.sb.wf(
            "green",
            "WO-001",
            "--",
            *support.Sandbox.GATE_ARGV,
            check=errors.EXIT_OK,
        )
        self.sb.wf("advance", "WO-001", check=errors.EXIT_OK)
        self.sb.wf(
            "outcome",
            "WO-001",
            "accepted",
            "--by",
            "reviewer",
            check=errors.EXIT_OK,
        )

        self.assertEqual(self.state()["stage"], "ratify")
        event_types = [event["type"] for event in self.events()]
        for required in (
            "wo.opened",
            "receipt.red",
            "receipt.green",
            "outcome",
        ):
            self.assertIn(required, event_types)

        proc = self.sb.wf("verify")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")

    def test_unknown_claim_refusal_leaves_durable_tables_unchanged(self):
        """Scenario: a claim on a work order that does not exist is refused"""
        before = self.durable_counts()
        self.assertEqual(
            before,
            {
                "work_orders": 0,
                "events": 0,
                "claims": 0,
                "attempts": 0,
            },
            "the empty-database fixture did not land",
        )

        proc = self.sb.wf("claim", "WO-404")
        after = self.durable_counts()

        self.assertEqual(proc.returncode, errors.EXIT_REFUSED, proc.stderr)
        self.assertIn("work order exists", proc.stderr)
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
