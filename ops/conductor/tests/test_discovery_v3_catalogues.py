"""Discovery/3 catalogues, named misses, ownership and lock membership.

Acceptance rows: D-A10, D-A22, D-A23, D-A33, D-A34, D-A48, D-A49.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from discovery_v3_support import (  # noqa: E402
    DEV_HOMES,
    _DiscoveryV3Fixture,
    constraint_only_lock,
    empty_lock,
    workflow_lock,
)


class TestDiscoveryV3Catalogues(_DiscoveryV3Fixture):
    def test_d_a10_catalogue_over_sixteen_pages_every_home_once(self):
        self.plant_tree()
        self.plant_v3_config()
        self.assertGreater(len(DEV_HOMES), 16)
        self.assertLessEqual(len(DEV_HOMES), 64)
        seen: list[str] = []
        page = self.detail("lane_homes", {"profile": "dev"})
        snap = page["snapshot"]
        while True:
            chunk = page["data"]["homes"]
            meta = self.assert_page(page["data"]["page"])
            self.assertLessEqual(len(chunk), 16)
            self.assertEqual(meta["count"], len(chunk))
            self.assertEqual(meta["offset"], len(seen))
            self.assertEqual(meta["total"], len(DEV_HOMES))
            seen.extend(row["concept"] for row in chunk)
            if not meta["more"]:
                self.assertIsNone(meta["next_cursor"])
                break
            self.assertTrue(chunk, "empty non-advancing page")
            page = self.detail(
                "lane_homes",
                {
                    "profile": "dev",
                    "snapshot": snap,
                    "cursor": meta["next_cursor"],
                },
            )
            self.assertEqual(page["snapshot"], snap)
        self.assertEqual(seen, list(DEV_HOMES), seen)
        named = self.detail("lane_homes", {"profile": "dev", "concept": "watchdog"})
        self.assertEqual(named["data"]["homes"], [])
        self.assertIsNone(named["data"]["page"])
        self.assertEqual(named["data"]["home"]["concept"], "watchdog")
        self.assertEqual(named["snapshot"], snap)

    def test_d_a22_named_misses_for_all_three_detail_queries(self):
        self.plant_tree()
        self.plant_v3_config()
        start = self.start()
        snap = start["snapshot"]
        homes = self.detail(
            "lane_homes",
            {"profile": "dev", "snapshot": snap, "concept": "undeclared"},
        )
        self.assertEqual(homes["state"], "ok")
        self.assertEqual(homes["reason"], "unknown-concept")
        self.assertEqual(homes["data"]["homes"], [])
        self.assertIsNone(homes["data"]["home"])
        self.assertIsNone(homes["data"]["page"])
        missing_key = "record/" + ("a" * 64)
        handoffs = self.detail(
            "lane_handoffs",
            {"profile": "dev", "snapshot": snap, "key": missing_key},
        )
        self.assertEqual(handoffs["state"], "ok")
        self.assertEqual(handoffs["reason"], "unknown-key")
        self.assertEqual(handoffs["data"]["candidates"], [])
        self.assertIsNone(handoffs["data"]["candidate"])
        self.assertIsNone(handoffs["data"]["page"])
        actions = self.detail(
            "lane_actions",
            {"profile": "dev", "snapshot": snap, "name": "undeclared"},
        )
        self.assertEqual(actions["state"], "ok")
        self.assertEqual(actions["reason"], "unknown-action")
        self.assertEqual(actions["data"]["actions"], [])
        self.assertIsNone(actions["data"]["action"])

    def test_d_a23_detail_reuses_start_source_closure(self):
        self.plant_tree()
        self.plant_v3_config()
        start = self.start()
        snap = start["snapshot"]
        sources = start["sources"]
        for tool, arguments in (
            ("lane_homes", {"profile": "dev", "snapshot": snap}),
            ("lane_handoffs", {"profile": "dev", "snapshot": snap}),
            ("lane_actions", {"profile": "dev", "snapshot": snap}),
            (
                "lane_actions",
                {"profile": "dev", "snapshot": snap, "name": "onboard"},
            ),
        ):
            with self.subTest(tool=tool, arguments=arguments):
                payload = self.detail(tool, arguments)
                self.assertEqual(payload["snapshot"], snap)
                self.assertEqual(payload["sources"], sources)

    def test_d_a33_governing_document_without_implementation(self):
        self.plant_tree()
        self.plant_v3_config()
        payload = self.detail("lane_homes", {"profile": "dev", "concept": "wf-runtime"})
        home = payload["data"]["home"]
        self.assertEqual(home["concept"], "wf-runtime")
        self.assertEqual(home["home"], "docs/workflow.md")
        self.assertEqual(home["contract"], "docs/workflow.md")
        self.assertIsNone(home["entrypoint"])
        self.assertIsNone(home["registry"])
        self.assertEqual(home["ownership"], "declared")
        self.assertIs(home["document_present"], True)
        self.assertIs(home["implementation_present"], False)
        self.assertIsNone(home["intended"])
        self.assertIsNone(home["installed"])
        self.assertEqual(home["evidence"], ["contract", "repo"])

    def test_d_a34_composer_lock_membership_not_constraints(self):
        cases = [
            ("packages", workflow_lock(where="packages"), True),
            ("packages-dev", workflow_lock(where="packages-dev"), True),
            ("constraint-only", constraint_only_lock(), False),
            ("absent", empty_lock(), False),
        ]
        canary = json.loads(constraint_only_lock())
        self.assertIn(b"symfony/workflow", constraint_only_lock())
        self.assertFalse(
            any(
                p["name"] == "symfony/workflow"
                for section in ("packages", "packages-dev")
                for p in canary[section]
            )
        )
        for name, lock, expected in cases:
            with self.subTest(name=name):
                self.reset_repo()
                self.plant_tree(lock=lock)
                self.plant_v3_config()
                payload = self.detail(
                    "lane_homes",
                    {"profile": "prod", "concept": "workflow-genus"},
                )
                home = payload["data"]["home"]
                self.assertIs(home["locked"], expected, home)
                self.assertIsNone(home["installed"])
                self.assertIsNone(home["activated"])
                self.assertIsNone(home["probed"])
                self.assertEqual(home["intended"], "symfony/workflow")
        self.reset_repo()
        self.plant_tree(extra={"composer.lock": b"{not-json"})
        self.plant_v3_config()
        broken = self.detail(
            "lane_homes", {"profile": "prod", "concept": "workflow-genus"}
        )
        self.assertIsNone(broken["data"]["home"]["locked"])
        aar = self.detail("lane_homes", {"profile": "dev", "concept": "aar"})
        self.assertEqual(aar["data"]["home"]["home"], "ops/conductor/handoff/README.md")
        self.assertEqual(
            aar["data"]["home"]["contract"], "ops/conductor/handoff/README.md"
        )

    def test_d_a48_home_evidence_contract_and_repo(self):
        self.plant_tree()
        self.plant_v3_config()
        runtime = self.detail("lane_homes", {"profile": "dev", "concept": "wf-runtime"})
        self.assertEqual(runtime["data"]["home"]["evidence"], ["contract", "repo"])
        genus = self.detail(
            "lane_homes", {"profile": "prod", "concept": "workflow-genus"}
        )
        self.assertEqual(genus["data"]["home"]["evidence"], ["contract", "repo"])
        self.assertIs(genus["data"]["home"]["locked"], False)
        listed = self.detail("lane_homes", {"profile": "dev"})
        for home in listed["data"]["homes"]:
            self.assertIsInstance(home.get("document_present"), (bool, type(None)))

    def test_d_a49_lane_mcp_registry_lane_read_null_mapping_history(self):
        self.plant_tree()
        self.plant_v3_config()
        mcp = self.detail("lane_homes", {"profile": "dev", "concept": "lane-mcp"})
        home = mcp["data"]["home"]
        self.assertEqual(home["registry"], "ops/conductor/registry/lane_mcp.py.json")
        self.assertEqual(home["entrypoint"], "ops/conductor/tools/lane_mcp.py")
        read = self.detail("lane_homes", {"profile": "dev", "concept": "lane-read"})
        self.assertIsNone(read["data"]["home"]["registry"])
        self.assertEqual(
            read["data"]["home"]["entrypoint"], "ops/conductor/tools/lane_read.py"
        )
        mapping = self.detail("lane_homes", {"profile": "prod", "concept": "mapping"})
        self.assertEqual(mapping["data"]["home"]["home"], "docs/mapping.md")
        self.assertEqual(mapping["data"]["home"]["contract"], "docs/mapping.md")
        self.assertEqual(mapping["data"]["home"]["intended"], "four projections")
        on_disk = (
            Path(__file__).resolve().parents[3]
            / "ops"
            / "conductor"
            / "registry"
            / "lane_mcp.py.json"
        )
        self.assertTrue(on_disk.is_file(), on_disk)
        body = json.loads(on_disk.read_text(encoding="utf-8"))
        self.assertIn("rows", body)


import unittest  # noqa: E402


def _lock_projection(case, fault, tool, arguments):
    from discovery_v3_support import contract_start_frame
    from test_discovery_v3_startup import _home_fixture

    home = _home_fixture(arguments["concept"])
    if home["intended"] == "symfony/workflow":
        raw = (case.repo / "composer.lock").read_bytes()
        try:
            lock = json.loads(raw)
        except ValueError:
            home["locked"] = None
        else:
            home["locked"] = any(
                p.get("name") == "symfony/workflow"
                for section in ("packages", "packages-dev")
                for p in lock[section]
            )
            if fault == "substring-lock":
                home["locked"] = b"symfony/workflow" in raw
            if fault == "absent-is-unknown" and not home["locked"]:
                home["locked"] = None
    reply = contract_start_frame()
    reply.update(
        query=tool,
        profile=arguments["profile"],
        data={"homes": [], "home": home, "page": None},
    )
    return reply


class TestDiscoveryV3CatalogueControls(unittest.TestCase):
    def test_faulty_lock_counterparties(self):
        from discovery_v3_support import prove_counterparty

        for fault, assertion in (
            ("substring-lock", "True is not False"),
            ("absent-is-unknown", "None is not False"),
        ):
            with self.subTest(fault=fault):
                prove_counterparty(
                    self,
                    TestDiscoveryV3Catalogues,
                    "test_d_a34_composer_lock_membership_not_constraints",
                    {"detail": _lock_projection},
                    fault=fault,
                    assertion=assertion,
                )
