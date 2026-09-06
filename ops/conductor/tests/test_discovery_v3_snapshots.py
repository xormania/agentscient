"""Discovery/3 snapshots, cursors, parity and contract fingerprints.

Acceptance rows: D-A24, D-A25, D-A26, D-A39, D-A46, D-A47.
"""

from __future__ import annotations

import os
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
        self.plant_v3_config(extra_profile={
            "label": "documentation",
            "work_roots": ["docs/"],
            "homes": ["wire", "onboard"],
            "startup_homes": ["wire"],
            "source_ids": ["repo"],
            "lineage": "docs",
        })
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
                {"id": j, "lineage": "dev", "work_paths": ["ops/a.md"]}
                for j in jobs
            ],
        )
        start = self.start()
        snap = start["snapshot"]
        total_work = 5
        self.assertEqual(len(start["data"]["work"]), 5)
        homes = self.detail("lane_homes", {"profile": "dev"})
        home_total = homes["data"]["page"]["total"]
        cases = [
            ("malformed", "lane_start", {"profile": "dev", "snapshot": snap, "cursor": "nope"}),
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
        first = self.start()
        second = self.start()
        self.assertEqual(first, second)
        self.assertEqual(canonical_bytes(first), canonical_bytes(second))
        dumped = canonical_bytes(first)
        self.assertNotIn(b"T1", dumped)
        snap = first["snapshot"]
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
            payload = self.detail(tool, arguments) if tool != "lane_start" else self.start(arguments)
            again = self.detail(tool, arguments) if tool != "lane_start" else self.start(arguments)
            self.assertEqual(payload, again, tool)
            self.assertEqual(payload["snapshot"], snap)
            cli[(tool, tuple(sorted(arguments.items())))] = payload
        requests = []
        rpc_id = 20
        for tool, arguments, uri in pairs:
            requests.append(rpc("tools/call", rpc_id, {"name": tool, "arguments": arguments}))
            rpc_id += 1
            requests.append(rpc("resources/read", rpc_id, {"uri": uri}))
            rpc_id += 1
        proc = self.serve(self.handshake(requests))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        objs = self.rpc_objects(proc)
        idx = 0
        for tool, arguments, _uri in pairs:
            call_payload = self.lane_from_rpc(self.rpc_by_id(objs, 20 + idx))
            read_payload = self.lane_from_rpc(self.rpc_by_id(objs, 21 + idx))
            idx += 2
            expected = cli[(tool, tuple(sorted(arguments.items())))]
            self.assertEqual(call_payload, expected, tool)
            self.assertEqual(read_payload, expected, tool)

    def test_d_a46_failed_source_fingerprint_is_stable_until_recovery(self):
        self.plant_tree()
        self.plant_v3_config(
            retained_refs="refs/heads/records/",
            source_ids=["repo", "retained"],
        )
        first = self.start()
        second = self.start()
        self.assertEqual(first["snapshot"], second["snapshot"])
        retained = [src for src in first["sources"] if src["id"] == "retained"][0]
        again = [src for src in second["sources"] if src["id"] == "retained"][0]
        self.assertEqual(retained["fingerprint"], again["fingerprint"])
        self.plant_ref("refs/heads/records/r0", self.head)
        third = self.start()
        self.assertNotEqual(third["snapshot"], first["snapshot"])
        recovered = [src for src in third["sources"] if src["id"] == "retained"][0]
        self.assertNotEqual(recovered["fingerprint"], retained["fingerprint"])

    def test_d_a47_contract_revision_tracks_launch_supplied_bytes(self):
        self.plant_tree()
        self.plant_v3_config()
        self.assertTrue(CONTRACT_PATH.is_file(), CONTRACT_PATH)
        original = CONTRACT_PATH.read_bytes()
        planted = (self.repo / "ops/conductor/discovery-lever.md").read_bytes()
        staged = self.contract_copy.read_bytes()
        self.assertEqual(planted, original)
        self.assertEqual(staged, original)
        first = self.start()
        contract = [src for src in first["sources"] if src["id"] == "contract"][0]
        self.assertEqual(contract["state"], "ok")
        revision = sha256_hex(original)
        dumped = canonical_bytes(first)
        self.assertIn(revision.encode(), dumped)
        mutated = original + b"\n# fixture-byte-change\n"
        self._plant_bytes(self.contract_copy, mutated)
        objects = self.gitdir / "objects"
        mode = objects.stat().st_mode
        os.chmod(objects, 0)
        try:
            second = self.start()
        finally:
            os.chmod(objects, mode)
        contract2 = [src for src in second["sources"] if src["id"] == "contract"][0]
        self.assertEqual(contract2["state"], "ok")
        repo_src = [src for src in second["sources"] if src["id"] == "repo"][0]
        self.assertEqual(repo_src["state"], "unavailable")
        self.assertNotEqual(second["snapshot"], first["snapshot"])
        self.assertIn(sha256_hex(mutated).encode(), canonical_bytes(second))
        self.assertNotEqual(contract2["fingerprint"], contract["fingerprint"])
