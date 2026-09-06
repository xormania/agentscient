"""Discovery/3 snapshots, cursors, parity and contract fingerprints.

Acceptance rows: D-A24, D-A25, D-A26, D-A39, D-A46, D-A47.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from discovery_v3_support import (  # noqa: E402
    CONTRACT_PATH,
    CURSOR_INVALID,
    HEX64,
    _DiscoveryV3Fixture,
    canonical_bytes,
    rpc,
    sha256_hex,
)


class TestDiscoveryV3Snapshots(_DiscoveryV3Fixture):
    def test_d_a24_retained_ref_move_changes_snapshot(self):
        inner = b"same blob bytes"
        extra = {"ops/conductor/handoff/HANDOFF-keep.md": inner}
        self.plant_tree(extra=extra)
        first_commit = self.head
        self.plant_ref("refs/heads/records/keep", first_commit)
        self.plant_v3_config(
            retained_refs="refs/heads/records/",
            source_ids=["repo", "retained"],
        )
        first = self.start()
        snap1 = first["snapshot"]
        self.assertRegex(snap1, HEX64)
        moved = self.add_commit(
            {"ops/conductor/handoff/HANDOFF-keep.md": inner, "docs/moved.md": b"x"},
            "identical blob new commit",
        )
        self.plant_ref("refs/heads/records/keep", moved)
        self.plant_v3_config(
            retained_refs="refs/heads/records/",
            source_ids=["repo", "retained"],
        )
        second = self.start()
        snap2 = second["snapshot"]
        self.assertNotEqual(snap2, snap1)
        stale = self.query(
            "lane_handoffs",
            {"profile": "dev", "snapshot": snap1, "cursor": f"{snap1}:1"},
        )
        line = self.assert_refusal(stale, "cursor")
        self.assertIn(snap2, line)
        self.assertIn(snap1, line)
        self.assertIn("needed restart from lane_start", line)

    def test_d_a25_content_profile_binding_and_failure_change_snapshot(self):
        self.plant_tree()
        self.plant_v3_config()
        base = self.start()
        snap = base["snapshot"]
        self.add_commit({"docs/wire.md": b"changed wire document\n"}, "content")
        self.plant_v3_config()
        after_content = self.start()
        self.assertNotEqual(after_content["snapshot"], snap)
        self.plant_v3_config(
            extra_profile={
                "label": "documentation",
                "work_roots": ["docs/"],
                "homes": ["wire", "onboard"],
                "startup_homes": ["wire"],
                "source_ids": ["repo"],
                "lineage": "docs",
            }
        )
        after_profile = self.start()
        self.assertNotEqual(after_profile["snapshot"], after_content["snapshot"])
        inner = b"bound"
        self.add_commit({"ops/conductor/handoff/HANDOFF-x.md": inner}, "bind")
        self.plant_v3_config(
            record_bindings=[
                {
                    "record_id": "bound",
                    "kind": "handoff",
                    "revision": sha256_hex(inner),
                    "lineage": "dev",
                    "work_paths": ["ops/a.md"],
                    "supersedes": [],
                }
            ]
        )
        after_bind = self.start()
        self.assertNotEqual(after_bind["snapshot"], after_profile["snapshot"])
        self.plant_v3_config(
            retained_refs="refs/heads/records/",
            source_ids=["repo", "retained"],
        )
        after_fail = self.start()
        self.assertNotEqual(after_fail["snapshot"], after_bind["snapshot"])
        refuse = self.query(
            "lane_homes",
            {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:1"},
        )
        self.assert_refusal(refuse, "cursor")

    def test_d_a26_cursor_grammar_bounds_and_no_leading_zeros(self):
        jobs = [f"job{n:02d}" for n in range(1, 6)]
        self.plant_tree()
        for rec_id in jobs:
            self.plant_dispatch(rec_id)
        self.plant_v3_config(
            job_ids=jobs,
            source_ids=["repo", *[f"dispatch/{j}" for j in jobs]],
            work_bindings=[
                {"id": j, "lineage": "dev", "work_paths": ["ops/a.md"]} for j in jobs
            ],
        )
        start = self.start()
        snap = start["snapshot"]
        total_work = 5
        self.assertEqual(len(start["data"]["work"]), 5)
        homes = self.detail("lane_homes", {"profile": "dev"})
        home_total = homes["data"]["page"]["total"]
        cases = [
            (
                "malformed",
                "lane_start",
                {"profile": "dev", "snapshot": snap, "cursor": "nope"},
            ),
            (
                "leading-zero",
                "lane_start",
                {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:01"},
            ),
            (
                "missing-snapshot",
                "lane_start",
                {"profile": "dev", "cursor": f"{snap}:0"},
            ),
            (
                "mismatch",
                "lane_start",
                {"profile": "dev", "snapshot": "b" * 64, "cursor": f"{snap}:0"},
            ),
            (
                "start-past-total",
                "lane_start",
                {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:{total_work}"},
            ),
            (
                "start-above-20",
                "lane_start",
                {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:21"},
            ),
            (
                "homes-offset-zero",
                "lane_homes",
                {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:0"},
            ),
            (
                "homes-past",
                "lane_homes",
                {
                    "profile": "dev",
                    "snapshot": snap,
                    "cursor": f"{snap}:{home_total}",
                },
            ),
        ]
        for name, tool, arguments in cases:
            with self.subTest(name=name):
                proc = self.query(tool, arguments)
                line = self.assert_refusal(proc, "cursor")
                if name == "mismatch":
                    self.assertIn(snap, line)
                    self.assertIn("b" * 64, line)
                else:
                    self.assertEqual(line, CURSOR_INVALID)
        ok_zero = self.start(
            {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:0"}
        )
        self.assertEqual(ok_zero["snapshot"], snap)
        if home_total > 1:
            ok_home = self.detail(
                "lane_homes",
                {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:1"},
            )
            self.assertEqual(ok_home["data"]["page"]["offset"], 1)

    def test_d_a39_stationary_cli_tool_resource_byte_identity(self):
        self.plant_tree()
        self.plant_v3_config()
        first = self.raw_query("lane_start", {"profile": "dev"})
        second = self.raw_query("lane_start", {"profile": "dev"})
        self.assertEqual(first, second)
        snap = self.load_query(self.query("lane_start", {"profile": "dev"}))["snapshot"]
        pairs = [
            ("lane_start", {"profile": "dev"}, "lane://start/dev"),
            ("lane_homes", {"profile": "dev"}, "lane://homes/dev"),
            ("lane_handoffs", {"profile": "dev"}, "lane://handoffs/dev"),
            ("lane_actions", {"profile": "dev"}, "lane://actions/dev"),
            (
                "lane_homes",
                {"profile": "dev", "concept": "wire"},
                "lane://homes/dev/wire",
            ),
            (
                "lane_actions",
                {"profile": "dev", "name": "onboard"},
                "lane://actions/dev/onboard",
            ),
        ]
        cli = {}
        for tool, arguments, _uri in pairs:
            raw = self.raw_query(tool, arguments)
            self.assertEqual(raw, self.raw_query(tool, arguments), tool)
            payload = self.load_query(self.query(tool, arguments))
            self.assertEqual(
                raw, canonical_bytes(payload) + b"\n", "noncanonical CLI bytes"
            )
            self.assertEqual(payload["snapshot"], snap)
            cli[(tool, tuple(sorted(arguments.items())))] = raw
        requests = []
        rpc_id = 20
        for tool, arguments, uri in pairs:
            requests.append(
                rpc("tools/call", rpc_id, {"name": tool, "arguments": arguments})
            )
            rpc_id += 1
            requests.append(rpc("resources/read", rpc_id, {"uri": uri}))
            rpc_id += 1
        proc = self.serve(self.handshake(requests))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        objs = self.rpc_objects(proc)
        idx = 0
        for tool, arguments, _uri in pairs:
            call_bytes = self.rpc_bytes(self.rpc_by_id(objs, 20 + idx))
            read_bytes = self.rpc_bytes(self.rpc_by_id(objs, 21 + idx), resource=True)
            idx += 2
            expected = cli[(tool, tuple(sorted(arguments.items())))]
            # Remove no arbitrary whitespace: one measured CLI framing LF only.
            self.assertEqual(call_bytes + b"\n", expected, tool)
            self.assertEqual(read_bytes + b"\n", expected, tool)

    def test_d_a46_failed_source_fingerprint_is_stable_until_recovery(self):
        self.plant_tree()
        path = self.plant_dispatch("broken", raw=b"{not-json")
        self.assertEqual(path.read_bytes(), b"{not-json")
        self.plant_v3_config(job_ids=["broken"], source_ids=["repo", "dispatch/broken"])
        config_before = self.config_path.read_bytes()
        first = self.start()
        second = self.start()
        failed = next(src for src in first["sources"] if src["id"] == "dispatch/broken")
        again = next(src for src in second["sources"] if src["id"] == "dispatch/broken")
        self.assertEqual(
            (failed["state"], failed["reason"]), ("unavailable", "malformed")
        )
        self.assertEqual(again, failed)
        self.assertEqual(first["snapshot"], second["snapshot"])
        self.plant_dispatch("broken")
        self.assertNotEqual(path.read_bytes(), b"{not-json")
        self.assertEqual(self.config_path.read_bytes(), config_before)
        third = self.start()
        recovered = next(
            src for src in third["sources"] if src["id"] == "dispatch/broken"
        )
        self.assertEqual((recovered["state"], recovered["reason"]), ("ok", None))
        self.assertNotEqual(recovered["fingerprint"], failed["fingerprint"])
        self.assertNotEqual(third["snapshot"], first["snapshot"])
        self.assertEqual(
            [s for s in first["sources"] if s["id"] != "dispatch/broken"],
            [s for s in third["sources"] if s["id"] != "dispatch/broken"],
        )

    def test_d_a47_contract_revision_tracks_launch_supplied_bytes(self):
        self.plant_tree()
        self.plant_v3_config()
        self.assertTrue(CONTRACT_PATH.is_file(), CONTRACT_PATH)
        original = CONTRACT_PATH.read_bytes()
        planted = (self.repo / "ops/conductor/discovery-lever.md").read_bytes()
        staged = self.contract_copy.read_bytes()
        self.assertEqual(planted, original)
        self.assertEqual(staged, original)
        # Fail repo from the first reading, without chmod or changing config.
        with self.missing_head_object():
            first = self.start()
            contract = next(src for src in first["sources"] if src["id"] == "contract")
            self.assertEqual((contract["state"], contract["reason"]), ("ok", None))
            self.assertEqual(
                contract["fingerprint"], self.contract_fingerprint(original)
            )
            self.assertEqual(
                next(s for s in first["sources"] if s["id"] == "repo")["state"],
                "unavailable",
            )
            mutated = original + b"\n# fixture-byte-change\n"
            self._plant_bytes(self.contract_copy, mutated)
            self.assertNotEqual(self.contract_copy.read_bytes(), original)
            second = self.start()
            contract2 = next(
                src for src in second["sources"] if src["id"] == "contract"
            )
            self.assertEqual((contract2["state"], contract2["reason"]), ("ok", None))
            self.assertEqual(
                contract2["fingerprint"], self.contract_fingerprint(mutated)
            )
            self.assertNotEqual(contract2["fingerprint"], contract["fingerprint"])
            self.assertNotEqual(second["snapshot"], first["snapshot"])
            self.assertEqual(
                next(s for s in second["sources"] if s["id"] == "repo")["state"],
                "unavailable",
            )
            self.assertEqual(
                [s for s in first["sources"] if s["id"] != "contract"],
                [s for s in second["sources"] if s["id"] != "contract"],
            )


def _source_reply(case, fault, arguments=None, **kwargs):
    """Immutable Source fixtures; only definition uses the full hash recipe."""
    import json

    from discovery_v3_support import contract_start_frame

    reply = contract_start_frame()
    config = json.loads(case.config_path.read_bytes())
    sources = reply["sources"]
    next(s for s in sources if s["id"] == "config")["fingerprint"] = sha256_hex(
        canonical_bytes(config)
    )
    if config["job_ids"]:
        raw = (case.store / "broken" / "record.json").read_bytes()
        failed = raw == b"{not-json"
        source = dict(
            id="dispatch/broken",
            state="unavailable" if failed else "ok",
            reason="malformed" if failed else None,
            fingerprint=sha256_hex(raw),
        )
        if fault == "empty-instead-of-failure" and failed:
            source.update(state="ok", reason=None)
        if fault == "no-recovery-fingerprint":
            source["fingerprint"] = "b" * 64
        sources.append(source)
    else:
        raw = case.contract_copy.read_bytes()
        source = next(s for s in sources if s["id"] == "contract")
        source["fingerprint"] = case.contract_fingerprint(raw)
        if fault == "bare-revision":
            source["fingerprint"] = sha256_hex(raw)
        if fault == "compiled-definition":
            source["fingerprint"] = case.contract_fingerprint(
                CONTRACT_PATH.read_bytes()
            )
        next(s for s in sources if s["id"] == "repo").update(
            state="unavailable", reason="unreadable"
        )
    sources.sort(key=lambda s: s["id"])
    reply["snapshot"] = sha256_hex(
        canonical_bytes(
            dict(
                protocol="discovery/3",
                audience="conductor",
                profile="dev",
                sources=sources,
            )
        )
    )
    return reply


def _parity_packet(tool):
    from discovery_v3_support import contract_start_frame

    reply = contract_start_frame()
    reply["query"] = tool
    if tool == "lane_homes":
        reply["data"] = {"homes": [], "home": None, "page": None}
        reply["reason"] = "unknown-concept"
    elif tool == "lane_handoffs":
        reply["data"] = {
            "candidates": [],
            "candidate": None,
            "handoffs": reply["data"]["handoffs"],
            "page": {
                "offset": 0,
                "count": 0,
                "total": 0,
                "more": False,
                "next_cursor": None,
            },
        }
    elif tool == "lane_actions":
        reply["data"] = {"actions": reply["data"]["actions"], "action": None}
    return reply


def _parity_query(case, fault, tool, arguments, **kwargs):
    import subprocess

    raw = canonical_bytes(_parity_packet(tool)).decode() + "\n"
    if fault == "cli-trailing-space":
        raw += " "
    return subprocess.CompletedProcess([], 0, raw, "")


def _parity_serve(case, fault, lines, **kwargs):
    import json
    import subprocess

    responses = []
    for line in lines:
        req = json.loads(line)
        if req["method"] not in ("tools/call", "resources/read"):
            continue
        resource = req["method"] == "resources/read"
        tool = (
            "lane_" + req["params"]["uri"].split("/")[2]
            if resource
            else req["params"]["name"]
        )
        packet = _parity_packet(tool)
        text = canonical_bytes(packet).decode()
        if fault == "rpc-key-order":
            text = json.dumps(packet, separators=(",", ":"), sort_keys=False)
        if fault == "rpc-escape-drift":
            text = text.replace("lane", "\\u006cane")
        if fault == "rpc-trailing-lf":
            text += "\n"
        result = (
            {
                "contents": [
                    {
                        "uri": req["params"]["uri"],
                        "mimeType": "application/json",
                        "text": text,
                    }
                ]
            }
            if resource
            else {
                "content": [{"type": "text", "text": text}],
                "structuredContent": packet,
            }
        )
        responses.append({"jsonrpc": "2.0", "id": req["id"], "result": result})
    return subprocess.CompletedProcess(
        [], 0, "\n".join(json.dumps(r) for r in responses), ""
    )


import unittest  # noqa: E402


class TestDiscoveryV3SnapshotControls(unittest.TestCase):
    def test_faulty_source_counterparties(self):
        from discovery_v3_support import definition_fingerprint, prove_counterparty

        # Measured independently with sha256sum over a hand-spelled 297-byte
        # canonical source object (empty config/anchors, exact b"abc\n" bytes).
        self.assertEqual(
            definition_fingerprint({}, [], b"abc\n"),
            "a21cdc7a895ff8970a59c804ca293476315a798b9e8f275137aeb2d8f43bb498",
        )
        for method, fault, assertion in (
            (
                "test_d_a46_failed_source_fingerprint_is_stable_until_recovery",
                "empty-instead-of-failure",
                "unavailable",
            ),
            (
                "test_d_a46_failed_source_fingerprint_is_stable_until_recovery",
                "no-recovery-fingerprint",
                "==",
            ),
            (
                "test_d_a47_contract_revision_tracks_launch_supplied_bytes",
                "bare-revision",
                "!=",
            ),
            (
                "test_d_a47_contract_revision_tracks_launch_supplied_bytes",
                "compiled-definition",
                "!=",
            ),
        ):
            with self.subTest(fault=fault):
                prove_counterparty(
                    self,
                    TestDiscoveryV3Snapshots,
                    method,
                    {"start": _source_reply},
                    fault=fault,
                    assertion=assertion,
                )

    def test_faulty_projection_counterparties(self):
        from discovery_v3_support import prove_counterparty

        for fault, assertion in (
            ("cli-trailing-space", "noncanonical CLI"),
            ("rpc-key-order", "noncanonical MCP"),
            ("rpc-escape-drift", "noncanonical MCP"),
            ("rpc-trailing-lf", "noncanonical MCP"),
        ):
            with self.subTest(fault=fault):
                prove_counterparty(
                    self,
                    TestDiscoveryV3Snapshots,
                    "test_d_a39_stationary_cli_tool_resource_byte_identity",
                    {"query": _parity_query, "serve": _parity_serve},
                    fault=fault,
                    assertion=assertion,
                )
