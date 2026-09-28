"""Lane-MCP review regressions, written from lane-mcp-lever.md.

Reuses the fixture in test_lane_mcp.py. The tools are not read here.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from test_lane_mcp import (  # noqa: E402
    CONSUMER,
    JOB,
    _LaneMcpFixture,
    rpc,
)

# CPython 3.12 json.loads RecursionError is above ~16000 nested objects.
NEST_DEPTH = 20000


def _nested_json(depth: int = NEST_DEPTH) -> bytes:
    return (b'{"k":' * depth) + b"1" + (b"}" * depth)


class TestLaneMcpReview(_LaneMcpFixture):
    def _insert_event_evidence(self, event_id: int, evidence: str) -> None:
        con = sqlite3.connect(str(self.db))
        try:
            con.execute(
                "INSERT INTO events(id, route, consumer, condition_id, "
                "monitor, subject, state, summary, evidence, observed_at, "
                "delivery, dedup_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    event_id,
                    "jobs",
                    CONSUMER,
                    "job_change",
                    "jobs",
                    f"subject-{event_id}",
                    "ok",
                    f"summary-{event_id}",
                    evidence,
                    "2026-09-04T12:00:00Z",
                    "queued",
                    f"dedup-{event_id}",
                ),
            )
            con.commit()
            landed = con.execute(
                "SELECT evidence FROM events WHERE id=?", (event_id,)
            ).fetchone()
        finally:
            con.close()
        self.assertEqual(landed[0], evidence)

    def _set_event_evidence(self, event_id: int, evidence: str) -> None:
        con = sqlite3.connect(str(self.db))
        try:
            con.execute(
                "UPDATE events SET evidence=? WHERE id=?",
                (evidence, event_id),
            )
            con.commit()
            landed = con.execute(
                "SELECT evidence FROM events WHERE id=?", (event_id,)
            ).fetchone()
        finally:
            con.close()
        self.assertEqual(landed[0], evidence)

    def _serve_tool_then_ping(self, tool: str, arguments: dict):
        return self.serve(
            self.handshake(
                [
                    rpc(
                        "tools/call",
                        2,
                        {"name": tool, "arguments": arguments},
                    ),
                    rpc("ping", 3),
                ]
            )
        )

    def test_alert_subject_257_to_1024_allowed_and_invalid_lookahead_keeps_prefix(
        self,
    ):
        subject_257 = "S" * 257
        subject_1024 = "T" * 1024
        self.assertEqual(len(subject_257.encode("utf-8")), 257)
        self.assertEqual(len(subject_1024.encode("utf-8")), 1024)
        self.plant_events(
            [
                {
                    "id": 1,
                    "consumer": CONSUMER,
                    "subject": subject_257,
                    "delivery": "queued",
                    "evidence": "ev-1",
                },
                {
                    "id": 2,
                    "consumer": CONSUMER,
                    "subject": subject_1024,
                    "delivery": "queued",
                    "evidence": "ev-2",
                },
            ]
        )
        self._insert_event_evidence(3, "{not-json")
        con = sqlite3.connect(str(self.db))
        try:
            rows = con.execute(
                "SELECT id, subject, evidence FROM events ORDER BY id"
            ).fetchall()
        finally:
            con.close()
        self.assertEqual(
            rows,
            [
                (1, subject_257, '"ev-1"'),
                (2, subject_1024, '"ev-2"'),
                (3, "subject-3", "{not-json"),
            ],
        )
        proc = self.query("lane_alerts", {"after": 0, "limit": 2})
        payload = self.assert_lane(self.load_query(proc), "lane_alerts")
        self.assertEqual(payload["state"], "ok", payload)
        events = payload["events"]
        self.assertEqual(len(events), 2, payload)
        self.assertEqual([event["id"] for event in events], [1, 2])
        self.assertEqual(events[0]["subject"], subject_257)
        self.assertEqual(events[1]["subject"], subject_1024)
        self.assertEqual(payload["more"], True)
        self.assertEqual(payload["next_after"], 2)

    def test_deep_record_json_unavailable_and_later_ping_survives(self):
        nested = _nested_json()
        rec = self.plant_record(raw=nested)
        self.assertEqual(rec.read_bytes(), nested)
        served = self._serve_tool_then_ping("lane_record", {"id": JOB})
        self.assertEqual(served.returncode, 0, served.stderr)
        objs = self.rpc_objects(served)
        called = self.rpc_by_id(objs, 2)
        self.assertNotIn("error", called, called)
        lane = self.assert_lane(self.lane_from_rpc(called), "lane_record")
        self.assertEqual(lane["state"], "unavailable", lane)
        self.assertTrue(lane.get("reason"))
        ping = self.rpc_by_id(objs, 3)
        self.assertEqual(ping.get("result"), {})
        proc = self.query("lane_record", {"id": JOB})
        payload = self.assert_lane(self.load_query(proc), "lane_record")
        self.assertEqual(payload["state"], "unavailable", payload)
        self.assertTrue(payload.get("reason"))

    def test_deep_alert_evidence_or_usage_row_does_not_terminate_server(self):
        nested = _nested_json()
        nested_text = nested.decode("ascii")
        for kind in ("alerts", "usage"):
            with self.subTest(kind=kind):
                self.reset_sources()
                if kind == "alerts":
                    self.plant_events(
                        [
                            {
                                "id": 1,
                                "consumer": CONSUMER,
                                "delivery": "queued",
                            }
                        ]
                    )
                    self._set_event_evidence(1, nested_text)
                    tool, arguments = "lane_alerts", {}
                    expect = ("unavailable",)
                else:
                    self.plant_rollout([], prefix=nested + b"\n")
                    self.assertEqual(
                        self.rollout.read_bytes(), nested + b"\n"
                    )
                    tool, arguments = "lane_usage", {}
                    expect = ("unknown", "unavailable")
                served = self._serve_tool_then_ping(tool, arguments)
                self.assertEqual(served.returncode, 0, served.stderr)
                objs = self.rpc_objects(served)
                called = self.rpc_by_id(objs, 2)
                self.assertNotIn("error", called, called)
                lane = self.assert_lane(self.lane_from_rpc(called), tool)
                self.assertIn(lane["state"], expect, lane)
                self.assertTrue(lane.get("reason"))
                if kind == "usage":
                    metrics = lane.get("metrics") or {}
                    self.assertNotEqual(metrics.get("input"), 0)
                ping = self.rpc_by_id(objs, 3)
                self.assertEqual(ping.get("result"), {})
