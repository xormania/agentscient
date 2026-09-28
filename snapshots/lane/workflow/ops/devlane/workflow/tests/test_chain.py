"""chain.py — append, verify, project, and the faults each must catch.

Every planted fault here proves it landed before the assertion runs:
``plant_sql`` refuses an UPDATE that matched no rows, and each plant carries
a ``check`` confirming the database is still recognisably the fixture.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

import support
from support import plant_sql
import canonical
import chain as chainmod
import store
from errors import Integrity, Refusal

REAL_MIGRATIONS = support.WF_DIR / "migrations"


def rows_intact(expected):
    return lambda conn: conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == expected


class ChainCase(unittest.TestCase):
    """A work order with a short, valid chain."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="wf-chain-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.db_path = self.dir / "wf.db"
        self.store = store.Store(self.db_path)
        self.addCleanup(self.store.close)
        self.store.migrate(REAL_MIGRATIONS, canonical.now())
        self.store.insert_work_order("WO-001", "objective", "tdd", 1, "a" * 64, canonical.now())
        self.chain = chainmod.Chain(self.store)

    def seed(self):
        self.chain.append("WO-001", {
            "type": chainmod.WO_OPENED, "kind": "tdd", "kind_version": 1,
            "spec_sha256": "a" * 64, "objective": "objective", "agent": "test",
        })
        self.chain.append("WO-001", {
            "type": chainmod.STAGE_ENTERED, "stage": "spec", "frozen": None, "agent": "test",
        })
        self.chain.append("WO-001", {
            "type": chainmod.STAGE_ENTERED, "stage": "red", "frozen": None, "agent": "test",
        })
        return self.store.list_events("WO-001")

    def reopen(self):
        """Reconnect, so a plant written by another connection is definitely read."""
        self.store.close()
        self.store = store.Store(self.db_path)
        self.chain = chainmod.Chain(self.store)
        return self.chain


class Append(ChainCase):
    def test_derives_the_fields_it_owns(self):
        event = self.chain.append("WO-001", {"type": chainmod.WO_OPENED, "kind": "tdd"})
        self.assertEqual(event["seq"], 1)
        self.assertEqual(event["prev"], canonical.ZERO_DIGEST)
        self.assertEqual(event["hash"], chainmod.event_hash(event))
        self.assertEqual(len(event["hash"]), 64)
        canonical.parse_time(event["time"])

    def test_payload_is_the_canonical_bytes_of_the_complete_event(self):
        event = self.chain.append("WO-001", {"type": chainmod.WO_OPENED, "kind": "tdd"})
        row = self.store.get_event("WO-001", 1)
        self.assertEqual(row["payload"], canonical.dumps(event))
        self.assertTrue(canonical.is_canonical(row["payload"]))
        self.assertIn("hash", canonical.loads(row["payload"]))

    def test_hash_is_over_the_event_without_its_own_hash_field(self):
        event = self.chain.append("WO-001", {"type": chainmod.WO_OPENED})
        without = {k: v for k, v in event.items() if k != "hash"}
        self.assertEqual(event["hash"], canonical.digest(without))
        self.assertNotEqual(event["hash"], canonical.digest(event))

    def test_second_event_links_to_the_first(self):
        first = self.chain.append("WO-001", {"type": chainmod.WO_OPENED})
        second = self.chain.append("WO-001", {"type": chainmod.STAGE_ENTERED, "stage": "spec"})
        self.assertEqual(second["seq"], 2)
        self.assertEqual(second["prev"], first["hash"])

    def test_refuses_an_append_to_an_unknown_work_order(self):
        with self.assertRaises(Refusal) as caught:
            self.chain.append("WO-404", {"type": chainmod.WO_OPENED})
        self.assertIn("work order exists", str(caught.exception))

    def test_refuses_an_event_without_a_type(self):
        with self.assertRaises(Refusal):
            self.chain.append("WO-001", {"kind": "tdd"})


class CompareAndSwap(ChainCase):
    def test_a_stale_seq_is_refused_not_overwritten(self):
        self.seed()
        with self.assertRaises(Refusal) as caught:
            self.chain.append("WO-001", {"type": chainmod.OUTCOME, "seq": 2})
        self.assertIn("contiguous", str(caught.exception))
        self.assertEqual(self.store.chain_tail("WO-001")["seq"], 3)

    def test_a_stale_prev_is_refused_not_overwritten(self):
        events = self.seed()
        with self.assertRaises(Refusal) as caught:
            self.chain.append("WO-001", {"type": chainmod.OUTCOME, "prev": events[0]["hash"]})
        self.assertIn("links to the chain tail", str(caught.exception))
        self.assertEqual(self.store.chain_tail("WO-001")["seq"], 3)

    def test_a_matching_seq_and_prev_are_accepted(self):
        events = self.seed()
        appended = self.chain.append(
            "WO-001", {"type": chainmod.OUTCOME, "seq": 4, "prev": events[-1]["hash"]}
        )
        self.assertEqual(appended["seq"], 4)

    def test_a_supplied_hash_that_does_not_match_is_refused(self):
        with self.assertRaises(Refusal) as caught:
            self.chain.append("WO-001", {"type": chainmod.WO_OPENED, "hash": "b" * 64})
        self.assertIn("supplied hash matches", str(caught.exception))

    def test_a_supplied_state_hash_that_does_not_match_is_refused(self):
        with self.assertRaises(Refusal) as caught:
            self.chain.append("WO-001", {"type": chainmod.WO_OPENED, "state_sha256": "b" * 64})
        self.assertIn("state_sha256 matches", str(caught.exception))

    def test_time_may_not_decrease(self):
        self.chain.append("WO-001", {"type": chainmod.WO_OPENED, "time": "2026-08-20T12:00:00.000000Z"})
        with self.assertRaises(Refusal) as caught:
            self.chain.append(
                "WO-001", {"type": chainmod.OUTCOME, "time": "2026-08-20T11:59:59.999999Z"}
            )
        self.assertIn("non-decreasing", str(caught.exception))

    def test_time_must_be_spelled_the_one_canonical_way(self):
        with self.assertRaises(Refusal) as caught:
            self.chain.append("WO-001", {"type": chainmod.WO_OPENED, "time": "2026-08-20T12:00:00+00:00"})
        self.assertIn("RFC3339 UTC", str(caught.exception))

    def test_supersedes_seq_must_name_an_earlier_existing_event(self):
        self.seed()
        for bad in (0, 4, 99, "2"):
            with self.subTest(bad=bad):
                with self.assertRaises(Refusal):
                    self.chain.append("WO-001", {"type": chainmod.OUTCOME, "supersedes_seq": bad})
        ok = self.chain.append("WO-001", {"type": chainmod.OUTCOME, "supersedes_seq": 2})
        self.assertEqual(ok["supersedes_seq"], 2)


class ClockRegression(ChainCase):
    """A host clock that steps backwards must not be able to stop the recorder."""

    def test_a_backward_reading_is_clamped_forward_and_recorded(self):
        readings = iter([
            "2026-08-20T12:00:00.500000Z",
            "2026-08-20T12:00:00.100000Z",   # 400ms backwards
            "2026-08-20T12:00:00.900000Z",
        ])
        clock = chainmod.Chain(self.store, now=lambda: next(readings))
        first = clock.append("WO-001", {"type": chainmod.WO_OPENED})
        second = clock.append("WO-001", {"type": chainmod.STAGE_ENTERED, "stage": "spec"})
        third = clock.append("WO-001", {"type": chainmod.STAGE_ENTERED, "stage": "red"})

        self.assertEqual(first["time"], "2026-08-20T12:00:00.500000Z")
        self.assertEqual(second["time"], first["time"], "clamped, never reordered")
        self.assertEqual(second["clock_regressed_from"], "2026-08-20T12:00:00.100000Z")
        self.assertNotIn("clock_regressed_from", first)
        self.assertNotIn("clock_regressed_from", third)
        self.assertEqual(third["time"], "2026-08-20T12:00:00.900000Z")
        # The chain still verifies, and the clamp is inert in the projection.
        self.assertEqual(clock.project("WO-001").last_seq, 3)

    def test_a_supplied_backward_time_is_still_refused(self):
        # The clamp is for the clock, not for callers: an explicitly supplied
        # out-of-order time is a caller error and stays a refusal.
        self.chain.append("WO-001", {"type": chainmod.WO_OPENED,
                                     "time": "2026-08-20T12:00:00.500000Z"})
        with self.assertRaises(Refusal) as caught:
            self.chain.append("WO-001", {"type": chainmod.OUTCOME,
                                         "time": "2026-08-20T12:00:00.100000Z"})
        self.assertIn("non-decreasing", str(caught.exception))


class Reducer(unittest.TestCase):
    def test_entering_a_stage_clears_evidence_and_resets_the_frozen_set(self):
        state = chainmod.initial_state("WO-001")
        state = chainmod.apply_event(state, {"type": chainmod.STAGE_ENTERED, "stage": "red", "frozen": None}, 1)
        state = chainmod.apply_event(state, {"type": chainmod.RECEIPT_RED}, 2)
        self.assertEqual(state["satisfied"], ["receipt.red"])
        state = chainmod.apply_event(
            state, {"type": chainmod.STAGE_ENTERED, "stage": "impl", "frozen": {"manifest_sha256": "x"}}, 3
        )
        self.assertEqual(state["satisfied"], [])
        self.assertEqual(state["frozen"], {"manifest_sha256": "x"})
        self.assertEqual(state["stage_seq"], 3)

    def test_re_entering_an_earlier_stage_voids_the_frozen_set(self):
        state = chainmod.initial_state("WO-001")
        state = chainmod.apply_event(
            state, {"type": chainmod.STAGE_ENTERED, "stage": "impl", "frozen": {"manifest_sha256": "x"}}, 1
        )
        state = chainmod.apply_event(
            state, {"type": chainmod.STAGE_ENTERED, "stage": "red", "frozen": None, "reason": "reopened"}, 2
        )
        self.assertIsNone(state["frozen"])

    def test_an_unknown_event_type_is_inert_rather_than_an_error(self):
        # PLAN §6: a new event type must cost zero engine changes.
        state = chainmod.initial_state("WO-001")
        before = dict(state)
        after = chainmod.apply_event(state, {"type": "something.new", "payload": 1}, 1)
        self.assertEqual(after, before)

    def test_any_receipt_type_counts_as_evidence(self):
        state = chainmod.apply_event(
            chainmod.initial_state("WO-001"), {"type": "receipt.conformance"}, 1
        )
        self.assertEqual(state["satisfied"], ["receipt.conformance"])

    def test_a_terminal_outcome_closes_the_work_order(self):
        state = chainmod.apply_event(
            chainmod.initial_state("WO-001"),
            {"type": chainmod.OUTCOME, "value": "denied", "effect": "terminal"}, 1,
        )
        self.assertEqual(state["status"], "terminal")

    def test_apply_event_does_not_mutate_its_input(self):
        state = chainmod.initial_state("WO-001")
        snapshot = canonical.dumps(state)
        chainmod.apply_event(state, {"type": chainmod.RECEIPT_RED}, 1)
        self.assertEqual(canonical.dumps(state), snapshot)


class VerifyClean(ChainCase):
    def test_a_fresh_chain_verifies_and_projects(self):
        self.seed()
        projection = self.chain.project("WO-001")
        self.assertEqual(projection.last_seq, 3)
        self.assertEqual(projection.state["stage"], "red")
        self.assertEqual(projection.state["kind"], "tdd")

    def test_an_empty_chain_verifies(self):
        projection = self.chain.project("WO-001")
        self.assertEqual(projection.last_seq, 0)
        self.assertEqual(projection.state["stage"], None)

    def test_projecting_an_unknown_work_order_refuses_rather_than_blocks(self):
        with self.assertRaises(Refusal):
            self.chain.project("WO-404")


class PlantedFaults(ChainCase):
    """Each fault is planted, proven to have landed, then required to be caught."""

    def setUp(self):
        super().setUp()
        self.events = self.seed()
        self.clean = [dict(r) for r in self.events]
        # The fixture must verify before anything is planted, or a later
        # "detected" result would be proving nothing.
        self.chain.project("WO-001")

    def test_detects_a_corrupted_payload_byte(self):
        payload = self.clean[1]["payload"]
        corrupted = payload.replace('"spec"', '"spek"')
        self.assertNotEqual(corrupted, payload, "plant: the anchor must be present")
        self.assertEqual(len(corrupted), len(payload))
        plant_sql(
            self.db_path,
            "UPDATE events SET payload = ? WHERE wo_id='WO-001' AND seq=2",
            (corrupted,),
            check=rows_intact(3),
        )
        with self.assertRaises(Integrity) as caught:
            self.reopen().verify("WO-001")
        self.assertIn("recomputed hash does not match", str(caught.exception))

    def test_detects_a_dropped_row(self):
        # Dropping the *tail* leaves a shorter but self-consistent chain; no
        # per-row check can see it, which is exactly why the commit cross-bind
        # and the append-only prefix walk exist (PLAN §3.6). Here: a middle row.
        plant_sql(
            self.db_path,
            "DELETE FROM events WHERE wo_id='WO-001' AND seq=2",
            check=rows_intact(2),
        )
        with self.assertRaises(Integrity) as caught:
            self.reopen().verify("WO-001")
        self.assertIn("not contiguous", str(caught.exception))

    def test_detects_a_rewritten_indexed_column(self):
        plant_sql(
            self.db_path,
            "UPDATE events SET time='2099-01-01T00:00:00.000000Z' WHERE wo_id='WO-001' AND seq=2",
            check=rows_intact(3),
        )
        with self.assertRaises(Integrity) as caught:
            self.reopen().verify("WO-001")
        self.assertIn("disagrees with the hashed payload", str(caught.exception))

    def test_detects_a_broken_prev_link(self):
        # The payload and its column are edited together, and the hash is
        # recomputed, so only the *link* is wrong. A checker that stopped at
        # per-row rehashing would pass this.
        event = canonical.loads(self.clean[2]["payload"])
        event["prev"] = "0" * 63 + "1"
        event["hash"] = chainmod.event_hash(event)
        plant_sql(
            self.db_path,
            "UPDATE events SET payload=?, prev=?, hash=? WHERE wo_id='WO-001' AND seq=3",
            (canonical.dumps(event), event["prev"], event["hash"]),
            check=rows_intact(3),
        )
        with self.assertRaises(Integrity) as caught:
            self.reopen().verify("WO-001")
        self.assertIn("prev does not link", str(caught.exception))

    def test_detects_a_non_canonical_re_encoding(self):
        # Same value, different bytes. Every hash still checks out, because the
        # hash is taken over the decoded object; only the byte comparison
        # catches this. A rewritten row is a rewritten record.
        import json

        event = canonical.loads(self.clean[1]["payload"])
        spaced = json.dumps(event, sort_keys=True, separators=(", ", ": "))
        self.assertNotEqual(spaced, self.clean[1]["payload"])
        self.assertEqual(canonical.loads(spaced), event, "plant: value must be unchanged")
        plant_sql(
            self.db_path,
            "UPDATE events SET payload=? WHERE wo_id='WO-001' AND seq=2",
            (spaced,),
            check=rows_intact(3),
        )
        with self.assertRaises(Integrity) as caught:
            self.reopen().verify("WO-001")
        self.assertIn("not in canonical form", str(caught.exception))

    def test_detects_a_state_hash_rewritten_consistently_through_the_chain(self):
        # The hardest shape: payload, columns and hash all agree with each
        # other. Only replaying the chain and comparing against the state the
        # events actually produce catches it.
        event = canonical.loads(self.clean[2]["payload"])
        event["state_sha256"] = "c" * 64
        event["hash"] = chainmod.event_hash(event)
        plant_sql(
            self.db_path,
            "UPDATE events SET payload=?, state_sha256=?, hash=? WHERE wo_id='WO-001' AND seq=3",
            (canonical.dumps(event), event["state_sha256"], event["hash"]),
            check=rows_intact(3),
        )
        reopened = self.reopen()
        reopened.verify("WO-001")  # per-row checks pass by construction
        with self.assertRaises(Integrity) as caught:
            reopened.project("WO-001")
        self.assertIn("replayed state does not match", str(caught.exception))

    def test_detects_a_tampered_state_row(self):
        tampered = canonical.dumps({"wo": "WO-001", "stage": "ratify", "status": "terminal"})
        plant_sql(
            self.db_path,
            "UPDATE wo_state SET state_json=? WHERE wo_id='WO-001'",
            (tampered,),
            check=lambda c: c.execute("SELECT COUNT(*) FROM wo_state").fetchone()[0] == 1,
        )
        with self.assertRaises(Integrity) as caught:
            self.reopen().project("WO-001")
        self.assertIn("state row", str(caught.exception))

    def test_detects_a_state_row_left_behind_at_an_older_head(self):
        plant_sql(
            self.db_path,
            "UPDATE wo_state SET last_seq=2 WHERE wo_id='WO-001'",
            check=lambda c: c.execute("SELECT COUNT(*) FROM wo_state").fetchone()[0] == 1,
        )
        with self.assertRaises(Integrity) as caught:
            self.reopen().project("WO-001")
        self.assertIn("different chain head", str(caught.exception))

    def test_detects_a_deleted_state_row(self):
        plant_sql(
            self.db_path,
            "DELETE FROM wo_state WHERE wo_id='WO-001'",
            check=lambda c: c.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 3,
        )
        with self.assertRaises(Integrity) as caught:
            self.reopen().project("WO-001")
        self.assertIn("no state row", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
