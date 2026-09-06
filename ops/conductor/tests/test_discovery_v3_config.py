"""Discovery/3 config, check, refusal and v1/v2 preservation tests.

Acceptance rows: D-A1, D-A2, D-A3, D-A4, D-A5, D-A6, D-A40, D-A44.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from discovery_v3_support import (  # noqa: E402
    CONFIG_LINE,
    CONSUMER,
    PROFILE_LINE,
    REFS,
    TOOL,
    V1_EXAMPLE,
    V2_EXAMPLE,
    V3_TOOLS,
    _DiscoveryV3Fixture,
    canonical_bytes,
    rpc,
)
from test_lane_mcp import FIFO_CAP, JOB  # noqa: E402


class TestDiscoveryV3Presence(_DiscoveryV3Fixture):
    def test_lane_mcp_and_lane_read_are_present(self):
        self.assertTrue(TOOL.is_file(), TOOL)
        self.assertTrue(TOOL.with_name("lane_read.py").is_file())

    def test_d_a41_lane_refs_adapter_file_is_present(self):
        self.assertTrue(
            REFS.is_file(),
            "missing public interface: ops/conductor/tools/lane_refs.py "
            "is the sole fixed Git read adapter (anchor_head, list_refs, "
            "list_tree, tree_entry, read_blob). No CLI is specified; "
            "presence is still required before discovery/3 is usable.",
        )


class TestDiscoveryV3Config(_DiscoveryV3Fixture):
    def test_d_a1_v1_check_and_discovery_query(self):
        proc = self.invoke(["check"])
        self.assertEqual(self.load_query(proc), {"valid": True, "tools": 4})
        self.assertTrue(V1_EXAMPLE.is_file(), V1_EXAMPLE)
        via_example = self.invoke(["check"], config=V1_EXAMPLE)
        self.assertEqual(self.load_query(via_example), {"valid": True, "tools": 4})
        first = self.load_query(self.query("lane_brief", {}))
        second = self.load_query(self.query("lane_brief", {}))
        self.assertEqual(first, second)
        for tool in ("lane_start", "lane_homes", "lane_handoffs", "lane_actions"):
            with self.subTest(tool=tool):
                line = self.assert_refusal(
                    self.query(tool, {"profile": "dev"}), "arguments"
                )
                self.assertIn(tool, line)

    def test_d_a2_v2_check_tools_resources_meta_and_brief(self):
        payload = {
            "version": 2,
            "dispatch_store": "store",
            "job_ids": [JOB],
            "monitor_state": "monitor",
            "consumer": CONSUMER,
            "usage_rollout": "rollout.jsonl",
            "job_registry": None,
        }
        self.plant_config(payload)
        proc = self.invoke(["check"])
        self.assertEqual(self.load_query(proc), {"valid": True, "tools": 7})
        self.assertTrue(V2_EXAMPLE.is_file(), V2_EXAMPLE)
        via_example = self.invoke(["check"], config=V2_EXAMPLE)
        self.assertEqual(self.load_query(via_example), {"valid": True, "tools": 7})
        listed = self.serve(self.handshake([rpc("tools/list", 2)]))
        self.assertEqual(listed.returncode, 0, listed.stderr)
        names = [
            tool["name"]
            for tool in self.rpc_by_id(self.rpc_objects(listed), 2)["result"]["tools"]
        ]
        self.assertEqual(len(names), 7)
        self.plant_record(JOB)
        brief = self.load_query(self.query("lane_brief", {}))
        self.assertEqual(brief.get("schema"), "agentscient.lane/v1")
        self.assertEqual(brief.get("query"), "lane_brief")
        meta = self.serve(
            self.handshake(
                [
                    rpc(
                        "tools/call",
                        3,
                        {
                            "name": "lane_brief",
                            "arguments": {},
                            "_meta": {"progressToken": "nope"},
                        },
                    )
                ]
            )
        )
        self.assertEqual(meta.returncode, 0, meta.stderr)
        obj = self.rpc_by_id(self.rpc_objects(meta), 3)
        self.assertEqual(self.lane_from_rpc(obj), brief)

    def test_d_a3_v3_check_is_eleven_tools_and_reads_no_sources(self):
        fifo = self.store / "blocked"
        fifo.parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(fifo)
        self.assertTrue(stat.S_ISFIFO(fifo.stat().st_mode))
        self.plant_tree()
        self.plant_v3_config(
            dispatch_store="store/blocked",
            job_ids=[JOB],
            retained_refs=None,
        )
        before = list(self.repo.rglob("*"))
        proc = self.invoke(["check"], cap=FIFO_CAP)
        self.assertEqual(self.load_query(proc), {"valid": True, "tools": 11})
        self.assertFalse(self.db.exists())
        self.assertFalse(self.rollout.exists())
        after = list(self.repo.rglob("*"))
        self.assertEqual(after, before)
        listed = self.serve(self.handshake([rpc("tools/list", 2)]))
        self.assertEqual(listed.returncode, 0, listed.stderr)
        tools = self.rpc_by_id(self.rpc_objects(listed), 2)["result"]["tools"]
        names = [tool["name"] for tool in tools]
        self.assertEqual(sorted(names), sorted(V3_TOOLS))
        self.assertEqual(len(tools), 11)
        by_name = {tool["name"]: tool for tool in tools}
        for name in V3_TOOLS:
            ann = by_name[name]["annotations"]
            self.assertIs(ann["readOnlyHint"], True)
            self.assertIs(ann["destructiveHint"], False)

    def test_d_a4_invalid_v3_config_refuses_before_acquisition(self):
        self.plant_tree()
        cycle = [
            {
                "record_id": "rec-a",
                "kind": "handoff",
                "revision": "a" * 64,
                "lineage": "dev",
                "work_paths": ["ops/conductor/example.md"],
                "supersedes": ["rec-b"],
            },
            {
                "record_id": "rec-b",
                "kind": "handoff",
                "revision": "b" * 64,
                "lineage": "dev",
                "work_paths": ["ops/conductor/example.md"],
                "supersedes": ["rec-a"],
            },
        ]
        conflict = [
            {
                "record_id": "rec-a",
                "kind": "handoff",
                "revision": "c" * 64,
                "lineage": "dev",
                "work_paths": ["ops/a.md"],
                "supersedes": [],
            },
            {
                "record_id": "rec-b",
                "kind": "aar",
                "revision": "c" * 64,
                "lineage": "dev",
                "work_paths": ["ops/a.md"],
                "supersedes": [],
            },
        ]
        cases = [
            (
                "extra-key",
                lambda: self.plant_v3_config(extra="nope"),
            ),
            (
                "missing-profiles",
                lambda: self.plant_config(
                    {
                        "version": 3,
                        "dispatch_store": None,
                        "job_ids": [],
                        "monitor_state": None,
                        "consumer": CONSUMER,
                        "usage_rollout": None,
                        "job_registry": None,
                        "discovery": {
                            "audience": "conductor",
                            "anchors": {"repo": str(self.repo)},
                            "repository": {
                                "id": "main",
                                "root": "repo",
                                "gitdir": "gitdir",
                                "common_gitdir": "gitdir",
                                "head": self.head,
                                "ref": None,
                            },
                            "retained_refs": None,
                            "dispatch": None,
                            "record_bindings": [],
                            "work_bindings": [],
                        },
                    }
                ),
            ),
            (
                "bool-version",
                lambda: self.plant_v3_config(version=True),
            ),
            (
                "invalid-path",
                lambda: self.plant_v3_config(
                    discovery={
                        "audience": "conductor",
                        "anchors": {"repo": str(self.repo), "gitdir": str(self.gitdir)},
                        "repository": {
                            "id": "main",
                            "root": "repo",
                            "gitdir": "gitdir",
                            "common_gitdir": "gitdir",
                            "head": self.head,
                            "ref": None,
                        },
                        "retained_refs": None,
                        "dispatch": {"anchor": "jobs", "path": "../store"},
                        "record_bindings": [],
                        "work_bindings": [],
                    }
                ),
            ),
            (
                "cycle",
                lambda: self.plant_v3_config(record_bindings=cycle),
            ),
            (
                "conflicting-revision",
                lambda: self.plant_v3_config(record_bindings=conflict),
            ),
        ]
        fifo = self.store / "blocked"
        fifo.parent.mkdir(parents=True, exist_ok=True)
        if not fifo.exists():
            os.mkfifo(fifo)
        for name, plant in cases:
            with self.subTest(name=name):
                plant()
                proc = self.invoke(["check"], cap=FIFO_CAP)
                line = self.assert_refusal(proc, "config")
                self.assertEqual(line, CONFIG_LINE)
                start = self.query("lane_start", {"profile": "dev"}, cap=FIFO_CAP)
                self.assert_refusal(start, "config")

    def test_d_a5_closed_arguments_refuse_role_path_and_unknown_fields(self):
        self.plant_tree()
        self.plant_v3_config()
        cases = [
            ("missing-profile", "lane_start", {}),
            ("unknown-field", "lane_start", {"profile": "dev", "audience": "conductor"}),
            ("role", "lane_start", {"profile": "dev", "role": "conductor"}),
            ("path", "lane_homes", {"profile": "dev", "path": "ops/"}),
            ("command", "lane_actions", {"profile": "dev", "command": "onboard"}),
            (
                "concept-and-cursor",
                "lane_homes",
                {"profile": "dev", "concept": "wire", "cursor": "a" * 64 + ":1"},
            ),
            (
                "config-switch",
                "lane_start",
                {"profile": "dev", "config": str(self.config_path)},
            ),
        ]
        for name, tool, arguments in cases:
            with self.subTest(name=name):
                proc = self.query(tool, arguments)
                line = self.assert_refusal(proc, "arguments")
                self.assertIn("expected closed arguments", line)
                self.assertIn(tool, line)

    def test_d_a6_unknown_configured_profile_uses_profile_wire(self):
        self.plant_tree()
        self.plant_v3_config()
        proc = self.query("lane_start", {"profile": "other"})
        line = self.assert_refusal(proc, "profile")
        self.assertEqual(line, PROFILE_LINE)
        mcp = self.serve(
            self.handshake(
                [
                    rpc(
                        "tools/call",
                        2,
                        {"name": "lane_start", "arguments": {"profile": "other"}},
                    )
                ]
            ),
            boot=True,
        )
        self.assertEqual(mcp.returncode, 0, mcp.stderr)
        obj = self.rpc_by_id(self.rpc_objects(mcp), 2)
        self.assert_domain_error_matches_cli(obj, PROFILE_LINE)

    def test_d_a40_reads_need_no_identity_and_readonly_hints(self):
        self.plant_tree()
        self.plant_v3_config()
        env = self.env()
        self.assertNotIn("WF_AGENT", env)
        proc = self.query("lane_start", {"profile": "dev"})
        payload = self.load_envelope(proc, "lane_start")
        self.assert_envelope(payload, "lane_start")
        listed = self.serve(self.handshake([rpc("tools/list", 2)]))
        tools = self.rpc_by_id(self.rpc_objects(listed), 2)["result"]["tools"]
        by_name = {tool["name"]: tool for tool in tools}
        for name in ("lane_start", "lane_homes", "lane_handoffs", "lane_actions"):
            ann = by_name[name]["annotations"]
            self.assertIs(ann["readOnlyHint"], True)
            self.assertIs(ann["destructiveHint"], False)

    def test_d_a44_v3_preserves_v2_bytes_on_unchanged_inputs(self):
        self.plant_record(JOB)
        v2 = {
            "version": 2,
            "dispatch_store": "store",
            "job_ids": [JOB],
            "monitor_state": "monitor",
            "consumer": CONSUMER,
            "usage_rollout": "rollout.jsonl",
            "job_registry": None,
        }
        self.plant_config(v2)
        pairs = (
            ("lane_record", {"id": JOB}),
            ("lane_brief", {}),
            ("lane_alerts", {}),
            ("lane_usage", {}),
            ("lane_findings", {"id": JOB}),
            ("lane_changes", {}),
            ("lane_jobs", {}),
        )
        v2_raw = {}
        for tool, arguments in pairs:
            proc = self.query(tool, arguments, boot=False)
            payload = self.load_query(proc)
            raw = proc.stdout.encode("utf-8")
            v2_raw[tool] = raw
            self.assertTrue(
                raw == canonical_bytes(payload)
                or raw == canonical_bytes(payload) + b"\n",
                tool,
            )
        self.plant_tree()
        self.plant_v3_config(job_ids=[JOB])
        for tool, arguments in pairs:
            with self.subTest(tool=tool):
                proc = self.query(tool, arguments, boot=False)
                raw = proc.stdout.encode("utf-8")
                self.assertEqual(raw, v2_raw[tool], tool)
                self.assertEqual(self.load_query(proc), json.loads(v2_raw[tool]))
