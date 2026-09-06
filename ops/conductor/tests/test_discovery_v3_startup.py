"""Discovery/3 startup, profiles, work lists and continuations.

Acceptance rows: D-A7, D-A8, D-A9, D-A20, D-A21, D-A35, D-A38,
D-A38b, D-A38c, D-A43.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from discovery_v3_support import (  # noqa: E402
    ACTIONS,
    CONTRACT_PATH,
    DEV_STARTUP,
    DOCS_PROFILE,
    HEX64,
    LAW,
    ONBOARD_LAW,
    ONBOARD_PATH,
    PROD_STARTUP,
    START_CAP,
    STATE_NAMES,
    UNSUPPORTED,
    _DiscoveryV3Fixture,
    canonical_bytes,
    extract_path_oneliner_table,
    rpc,
)


def _job(n: int) -> str:
    return f"job{n:02d}"


class TestDiscoveryV3Startup(_DiscoveryV3Fixture):
    def test_d_a7_shipped_dev_startup_and_pageable_catalogue(self):
        self.plant_tree()
        self.plant_v3_config()
        payload = self.start()
        self.assert_start_frame(payload)
        data = payload["data"]
        encoded = canonical_bytes(payload)
        self.assertLessEqual(len(encoded), START_CAP, len(encoded))
        self.assertLessEqual(len(self.query("lane_start", {"profile": "dev"}).stdout.encode()), START_CAP)
        names = [row["concept"] for row in data["homes"]]
        self.assertEqual(names, list(DEV_STARTUP), names)
        for row in data["homes"]:
            self.assertIs(row["document_present"], True, row)
            self.assertIs(row["implementation_present"], True, row)
        self.assertIn("retained source not searched", data["omissions"])
        seen: list[str] = []
        page = self.detail("lane_homes", {"profile": "dev"})
        homes = page["data"]["homes"]
        self.assertTrue(homes, homes)
        self.assert_page(page["data"]["page"])
        while True:
            chunk = page["data"]["homes"]
            self.assertLessEqual(len(chunk), 16, len(chunk))
            seen.extend(row["concept"] for row in chunk)
            meta = page["data"]["page"]
            if not meta["more"]:
                break
            nxt = meta["next_cursor"]
            snap = page["snapshot"]
            page = self.detail(
                "lane_homes",
                {"profile": "dev", "snapshot": snap, "cursor": nxt},
            )
        self.assertEqual(len(seen), len(set(seen)), seen)
        self.assertGreaterEqual(len(seen), 17, seen)
        self.assertNotIn("mapping", seen)
        self.assertNotIn("packages", seen)
        self.assertNotIn("projections", seen)
        self.assertIn("lane-mcp", seen)
        self.assertIn("dispatch", seen)
        self.assertIn("onboard", seen)

    def test_d_a8_shipped_prod_startup_and_lock_absence(self):
        self.plant_tree()
        self.plant_v3_config()
        payload = self.start({"profile": "prod"})
        self.assert_start_frame(payload, profile="prod")
        names = [row["concept"] for row in payload["data"]["homes"]]
        self.assertEqual(names, list(PROD_STARTUP), names)
        encoded = canonical_bytes(payload)
        self.assertLessEqual(len(encoded), START_CAP, len(encoded))
        mapping = self.detail(
            "lane_homes", {"profile": "prod", "concept": "mapping"}
        )
        home = mapping["data"]["home"]
        self.assertEqual(home["concept"], "mapping")
        self.assertIs(home["document_present"], True)
        self.assertIsNone(home["installed"])
        self.assertIsNone(home["activated"])
        self.assertIsNone(home["probed"])
        self.assertIsNone(home["locked"])
        self.assertEqual(home["intended"], "four projections")
        genus = self.detail(
            "lane_homes", {"profile": "prod", "concept": "workflow-genus"}
        )
        self.assertIs(genus["data"]["home"]["locked"], False)
        self.assertIsNone(genus["data"]["home"]["installed"])

    def test_d_a9_added_docs_profile_uses_same_algorithms(self):
        self.plant_tree()
        self.plant_v3_config(extra_profile=DOCS_PROFILE)
        payload = self.start({"profile": "docs"})
        self.assert_start_frame(payload, profile="docs")
        names = [row["concept"] for row in payload["data"]["homes"]]
        self.assertEqual(names, ["wire"])
        homes = self.detail("lane_homes", {"profile": "docs"})
        concepts = [row["concept"] for row in homes["data"]["homes"]]
        self.assertEqual(concepts, ["wire", "onboard"])
        page = self.assert_page(homes["data"]["page"])
        self.assertEqual(page["total"], 2)
        self.assertEqual(page["count"], 2)
        self.assertFalse(page["more"])
        miss = self.detail(
            "lane_homes", {"profile": "docs", "concept": "dispatch"}
        )
        self.assertEqual(miss["reason"], "unknown-concept")
        self.assertIsNone(miss["data"]["home"])
        self.assertEqual(miss["data"]["homes"], [])

    def test_d_a20_register_ledger_prs_are_unsupported_local_readings(self):
        self.plant_tree()
        self.plant_v3_config()
        decoy = self.home / ".local" / "state" / "agentscient"
        decoy.mkdir(parents=True)
        (decoy / "decisions.db").write_bytes(b"not-a-register")
        payload = self.start()
        self.assert_start_frame(payload)
        by_name = {row["name"]: row for row in payload["data"]["state_sources"]}
        for name in ("register", "ledger", "prs"):
            row = by_name[name]
            self.assertEqual(row["status"], "unavailable")
            self.assertIsNone(row["summary"])
            self.assertEqual(row["reason"], UNSUPPORTED)
            self.assertEqual(row["evidence"], [])
        self.assertEqual([row["name"] for row in payload["data"]["state_sources"]], list(STATE_NAMES))

    def test_d_a21_zero_then_malformed_authorized_dispatch_counts(self):
        self.plant_tree()
        self.plant_v3_config(job_ids=[], dispatch_store="store")
        zero = self.start()
        disp = [row for row in zero["data"]["state_sources"] if row["name"] == "dispatches"][0]
        self.assertEqual(disp["status"], "ok")
        self.assertEqual(
            disp["summary"],
            {"configured": 0, "readable": 0, "unknown": 0, "unavailable": 0},
        )
        self.assertEqual(disp["evidence"], [])
        self.assertEqual(zero["data"]["work"], [])
        self.plant_dispatch("job01", raw=b"{not-json")
        self.plant_v3_config(
            job_ids=["job01"],
            source_ids=["repo", "dispatch/job01"],
        )
        bad = self.start()
        disp = [row for row in bad["data"]["state_sources"] if row["name"] == "dispatches"][0]
        self.assertEqual(disp["summary"]["configured"], 1)
        self.assertEqual(disp["summary"]["unavailable"], 1)
        self.assertEqual(disp["summary"]["readable"], 0)
        self.assertNotIn("pid", json.dumps(disp))
        self.assertNotIn("running", json.dumps(disp).lower())

    def test_d_a35_onboard_presence_only_and_lifecycle_disabled(self):
        self.plant_tree()
        self.plant_v3_config()
        payload = self.start()
        by_name = {row["name"]: row for row in payload["data"]["actions"]}
        onboard = by_name["onboard"]
        self.assertEqual(onboard["owner"], ACTIONS[0][1])
        self.assertEqual(onboard["entrypoint"], ACTIONS[0][2])
        self.assertIs(onboard["implementation_present"], True)
        self.assertIs(onboard["available"], True)
        self.assertIsNone(onboard["installed"])
        self.assertIsNone(onboard["reason"])
        for name in ("handoff", "aar", "closeout"):
            row = by_name[name]
            self.assertIs(row["implementation_present"], False)
            self.assertIs(row["available"], False)
            self.assertIsNone(row["entrypoint"])
            self.assertEqual(row["reason"], "disabled")
            named = self.detail("lane_actions", {"profile": "dev", "name": name})
            self.assertEqual(named["data"]["actions"], [])
            self.assertEqual(named["data"]["action"]["name"], name)
            self.assertEqual(named["data"]["action"]["reason"], "disabled")

    def test_d_a38_initial_work_drop_and_frame_failures(self):
        jobs = [_job(n) for n in range(1, 9)]
        fat = "W" * 256
        for rec_id in jobs:
            self.plant_dispatch(
                rec_id,
                recorded_status=fat,
                extra={"status": fat},
            )
        bindings = [
            {
                "id": rec_id,
                "lineage": "dev",
                "work_paths": ["ops/conductor/example.md"],
            }
            for rec_id in jobs
        ]
        self.plant_tree()
        self.plant_v3_config(
            job_ids=jobs,
            source_ids=["repo", *[f"dispatch/{j}" for j in jobs]],
            work_bindings=bindings,
        )
        payload = self.start()
        self.assert_start_frame(payload)
        encoded = canonical_bytes(payload)
        self.assertLessEqual(len(encoded), START_CAP, len(encoded))
        omissions = payload["data"]["omissions"]
        work = payload["data"]["work"]
        snap = payload["snapshot"]
        self.assertEqual(work, [])
        self.assertIn("work omitted: 8", omissions)
        self.assertIn(f"work next cursor: {snap}:0", omissions)
        cont = self.start(
            {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:0"}
        )
        self.assert_start_frame(cont)
        self.assertEqual(cont["snapshot"], snap)
        self.assertEqual([row["name"] for row in cont["data"]["actions"]], [a[0] for a in ACTIONS])
        self.assertEqual([row["path"] for row in cont["data"]["law"]], [p for p, _ in LAW])
        self.assertLessEqual(len(canonical_bytes(cont)), START_CAP)
        self.assertTrue(cont["data"]["work"], cont["data"]["work"])
        self.assertLessEqual(len(cont["data"]["work"]), 8)
        huge = self.plant_dispatch(
            "huge01",
            raw=(json.dumps({"id": "huge01", "status": "X" * (START_CAP + 10)}) + "\n").encode(),
        )
        self.assertGreater(huge.stat().st_size, 0)
        self.plant_v3_config(
            job_ids=["huge01"],
            source_ids=["repo", "dispatch/huge01"],
            work_bindings=[
                {"id": "huge01", "lineage": "dev", "work_paths": ["ops/a.md"]}
            ],
        )
        overflow = self.query("lane_start", {"profile": "dev"})
        payload = self.load_envelope(overflow, "lane_start")
        self.assertEqual(payload["state"], "unavailable", payload)
        self.assertIn(
            payload["reason"],
            ("item-exceeds-cap", "page-frame-exceeds-cap", "response-exceeds-cap"),
        )
        self.assertIsNone(payload["data"])
        self.assertLessEqual(len(canonical_bytes(payload)), START_CAP)

    def test_d_a38b_twenty_work_cards_page_eight_eight_four(self):
        jobs = [_job(n) for n in range(1, 21)]
        self.plant_tree()
        for rec_id in jobs:
            self.plant_dispatch(rec_id)
        bindings = [
            {
                "id": rec_id,
                "lineage": "dev",
                "work_paths": ["ops/conductor/example.md"],
            }
            for rec_id in jobs
        ]
        self.plant_v3_config(
            job_ids=jobs,
            source_ids=["repo", *[f"dispatch/{j}" for j in jobs]],
            work_bindings=bindings,
        )
        check = self.load_query(self.invoke(["check"]))
        self.assertEqual(check, {"valid": True, "tools": 11})
        first = self.start()
        self.assert_start_frame(first)
        snap = first["snapshot"]
        work0 = first["data"]["work"]
        self.assertEqual(len(work0), 8, work0)
        self.assertEqual([row["id"] for row in work0], jobs[:8])
        self.assertIn("work omitted: 12", first["data"]["omissions"])
        self.assertIn(f"work next cursor: {snap}:8", first["data"]["omissions"])
        second = self.start(
            {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:8"}
        )
        self.assertEqual(second["snapshot"], snap)
        work1 = second["data"]["work"]
        self.assertEqual(len(work1), 8)
        self.assertEqual([row["id"] for row in work1], jobs[8:16])
        self.assertIn("work omitted: 4", second["data"]["omissions"])
        self.assertIn(f"work next cursor: {snap}:16", second["data"]["omissions"])
        third = self.start(
            {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:16"}
        )
        work2 = third["data"]["work"]
        self.assertEqual(len(work2), 4)
        self.assertEqual([row["id"] for row in work2], jobs[16:])
        self.assertNotIn("work omitted:", "\n".join(third["data"]["omissions"]))
        self.assertNotIn("work next cursor:", "\n".join(third["data"]["omissions"]))
        seen = [row["id"] for row in work0 + work1 + work2]
        self.assertEqual(seen, jobs)
        for page in (first, second, third):
            self.assertEqual(
                [row["name"] for row in page["data"]["actions"]],
                [a[0] for a in ACTIONS],
            )
            self.assertEqual(page["data"]["handoffs"], first["data"]["handoffs"])
            self.assertEqual(page["snapshot"], snap)
            self.assertLessEqual(len(canonical_bytes(page)), START_CAP)
        mcp = self.serve(
            self.handshake(
                [
                    rpc(
                        "tools/call",
                        2,
                        {
                            "name": "lane_start",
                            "arguments": {
                                "profile": "dev",
                                "snapshot": snap,
                                "cursor": f"{snap}:8",
                            },
                        },
                    )
                ]
            ),
            boot=True,
        )
        self.assertEqual(self.lane_from_rpc(self.rpc_by_id(self.rpc_objects(mcp), 2)), second)

    def test_d_a38c_twenty_one_dispatch_ids_five_card_continuations(self):
        jobs = [f"d{n:02d}" for n in range(1, 22)]
        self.assertEqual(len(jobs), 21)
        self.plant_tree()
        source_ids = ["repo", *[f"dispatch/{j}" for j in jobs]]
        self.assertEqual(len(source_ids), 22)
        closure_ids = [
            "adapter",
            "config",
            "contract",
            "repo",
            "retained",
            *[f"dispatch/{j}" for j in jobs],
        ]
        status = self.pad_status_for_five_card_pages(jobs, sorted(closure_ids))
        self.assertEqual(len(status.encode("utf-8")), len(status))
        for rec_id in jobs:
            self.plant_dispatch(rec_id, recorded_status=status)
        self.plant_v3_config(
            job_ids=jobs,
            source_ids=source_ids,
            work_bindings=[],
            retained_refs=None,
        )
        check = self.load_query(self.invoke(["check"]))
        self.assertEqual(check, {"valid": True, "tools": 11})
        first = self.start()
        self.assert_start_frame(first)
        snap = first["snapshot"]
        self.assertRegex(snap, HEX64)
        ids = [src["id"] for src in first["sources"]]
        self.assertEqual(len(ids), 26, ids)
        self.assertIn("retained", ids)
        retained = [src for src in first["sources"] if src["id"] == "retained"][0]
        self.assertEqual(retained["state"], "unavailable")
        self.assertEqual(retained["reason"], "disabled")
        self.assertEqual(first["data"]["work"], [])
        self.assertIn("work omitted: 21", first["data"]["omissions"])
        self.assertIn(f"work next cursor: {snap}:0", first["data"]["omissions"])
        offsets = (0, 5, 10, 15, 20)
        counts = (5, 5, 5, 5, 1)
        omitted = (16, 11, 6, 1, 0)
        seen: list[str] = []
        for offset, count, left in zip(offsets, counts, omitted, strict=True):
            page = self.start(
                {
                    "profile": "dev",
                    "snapshot": snap,
                    "cursor": f"{snap}:{offset}",
                }
            )
            self.assertEqual(page["snapshot"], snap)
            work = page["data"]["work"]
            self.assertEqual(len(work), count, (offset, work))
            for card in work:
                self.assertEqual(card["relevance"], "unknown")
                self.assertIsNone(card["lineage"])
                self.assertEqual(card["reason"], "metadata-missing")
            seen.extend(row["id"] for row in work)
            text = "\n".join(page["data"]["omissions"])
            if left:
                nxt = offset + count
                self.assertIn(f"work omitted: {left}", page["data"]["omissions"])
                self.assertIn(f"work next cursor: {snap}:{nxt}", page["data"]["omissions"])
            else:
                self.assertNotIn("work omitted:", text)
                self.assertNotIn("work next cursor:", text)
            self.assertLessEqual(len(canonical_bytes(page)), START_CAP)
            self.assertEqual(
                [row["name"] for row in page["data"]["actions"]],
                [a[0] for a in ACTIONS],
            )
        self.assertEqual(seen, jobs)
        refuse_21 = self.query(
            "lane_start",
            {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:21"},
        )
        self.assert_refusal(refuse_21, "cursor")
        twenty = jobs[:20]
        self.plant_v3_config(
            job_ids=twenty,
            source_ids=["repo", *[f"dispatch/{j}" for j in twenty]],
            work_bindings=[],
        )
        other = self.start()
        snap20 = other["snapshot"]
        refuse_past = self.query(
            "lane_start",
            {"profile": "dev", "snapshot": snap20, "cursor": f"{snap20}:20"},
        )
        self.assert_refusal(refuse_past, "cursor")

    def test_d_a43_independent_start_then_targeted_detail(self):
        inner = b"relevant handoff body for docs lineage"
        extra = {"ops/conductor/handoff/HANDOFF-docs.md": inner}
        self.plant_tree(extra=extra)
        digest = hashlib.sha256(inner).hexdigest()
        binding = {
            "record_id": "session-docs",
            "kind": "handoff",
            "revision": digest,
            "lineage": "docs",
            "work_paths": ["docs/wire.md"],
            "supersedes": [],
        }
        self.plant_v3_config(
            extra_profile=DOCS_PROFILE,
            record_bindings=[binding],
        )
        for profile, startup in (
            ("dev", DEV_STARTUP),
            ("prod", PROD_STARTUP),
            ("docs", ("wire",)),
        ):
            with self.subTest(profile=profile):
                start = self.start({"profile": profile})
                self.assert_start_frame(start, profile=profile)
                names = [row["concept"] for row in start["data"]["homes"]]
                self.assertEqual(tuple(names), tuple(startup))
                first = names[0]
                detail = self.detail(
                    "lane_homes", {"profile": profile, "concept": first}
                )
                home = detail["data"]["home"]
                self.assertEqual(home["concept"], first)
                self.assertTrue(home["home"])
                self.assertIn(home["ownership"], ("declared", "unresolved"))
        docs = self.detail("lane_handoffs", {"profile": "docs"})
        selection = docs["data"]["handoffs"]
        self.assertEqual(selection["selection"], "one")
        self.assertEqual(selection["selected_key"], f"record/{digest}")
        self.assertIs(selection["complete"], True)
        self.assertEqual(selection["current"], 1)
        named = self.detail(
            "lane_handoffs",
            {"profile": "docs", "key": f"record/{digest}"},
        )
        self.assertEqual(named["data"]["candidate"]["key"], f"record/{digest}")
        self.assertEqual(named["data"]["handoffs"]["selected_key"], f"record/{digest}")

    def test_discovery_five_onboard_seven_law_tables_equal(self):
        self.assertTrue(CONTRACT_PATH.is_file(), CONTRACT_PATH)
        self.assertTrue(ONBOARD_PATH.is_file(), ONBOARD_PATH)
        discovery_rows = extract_path_oneliner_table(
            CONTRACT_PATH.read_text(encoding="utf-8")
        )
        onboard_rows = extract_path_oneliner_table(
            ONBOARD_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(discovery_rows, LAW)
        self.assertEqual(len(discovery_rows), 5, discovery_rows)
        self.assertEqual(onboard_rows, ONBOARD_LAW)
        self.assertEqual(len(onboard_rows), 7, onboard_rows)
        self.assertEqual(onboard_rows[:5], discovery_rows)
        self.assertEqual(onboard_rows[5:], ONBOARD_LAW[5:])
        self.plant_tree()
        self.plant_v3_config()
        start = self.start()
        self.assertEqual([row["path"] for row in start["data"]["law"]], [p for p, _ in LAW])
        self.assertEqual(
            [row["one_liner"] for row in start["data"]["law"]],
            [one for _, one in LAW],
        )
        self.assertEqual(len(start["data"]["law"]), 5)
        self.git("rm", "-f", "--", "CONTRIB.md")
        self.git("commit", "-m", "drop contrib for one-absence arithmetic\n")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()
        self.plant_v3_config()
        missing = self.start()
        law = missing["data"]["law"]
        self.assertEqual(len(law), 5)
        by_path = {row["path"]: row for row in law}
        self.assertEqual(by_path["CONTRIB.md"]["status"], "missing")
        present = [row for row in law if row["status"] == "present"]
        self.assertEqual(len(present), 4, law)
