"""Discovery/3 startup, profiles, work lists and continuations.

Acceptance rows: D-A7, D-A8, D-A9, D-A20, D-A21, D-A35, D-A38,
D-A38b, D-A38c, D-A43.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from discovery_v3_support import (  # noqa: E402
    ACTIONS,
    DEV_STARTUP,
    DOCS_PROFILE,
    HEX64,
    PROD_STARTUP,
    START_CAP,
    STATE_NAMES,
    UNSUPPORTED,
    _DiscoveryV3Fixture,
    canonical_bytes,
    contract_start_frame,
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
        self.assertLessEqual(
            len(self.query("lane_start", {"profile": "dev"}).stdout.encode()), START_CAP
        )
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
        mapping = self.detail("lane_homes", {"profile": "prod", "concept": "mapping"})
        home = mapping["data"]["home"]
        self.assertEqual(home["concept"], "mapping")
        self.assertIs(home["document_present"], True)
        self.assertIsNone(home["installed"])
        self.assertIsNone(home["activated"])
        self.assertIsNone(home["probed"])
        self.assertIsNone(home["locked"])
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
        miss = self.detail("lane_homes", {"profile": "docs", "concept": "dispatch"})
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
        self.assertEqual(
            [row["name"] for row in payload["data"]["state_sources"]], list(STATE_NAMES)
        )

    def test_d_a21_zero_then_malformed_authorized_dispatch_counts(self):
        self.plant_tree()
        self.plant_v3_config(job_ids=[], dispatch_store="store")
        zero = self.start()
        disp = [
            row for row in zero["data"]["state_sources"] if row["name"] == "dispatches"
        ][0]
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
        disp = [
            row for row in bad["data"]["state_sources"] if row["name"] == "dispatches"
        ][0]
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

        def size(count):
            return len(
                canonical_bytes(contract_start_frame(jobs, status=fat, count=count))
            )

        self.assertLessEqual(size(0), START_CAP)
        self.assertLessEqual(size(1), START_CAP)
        self.assertGreater(size(8), START_CAP)
        payload = self.start()
        self.assert_work_page(payload, payload, jobs, 0, 0)
        snap = payload["snapshot"]
        seen = []
        offset = 0
        while offset < len(jobs):
            cont = self.start({"snapshot": snap, "cursor": f"{snap}:{offset}"})
            count = len(cont["data"]["work"])
            self.assertGreater(count, 0)
            self.assertLessEqual(count, 8)
            self.assert_work_page(payload, cont, jobs, offset, count)
            # Independent fit computation includes final omission strings.
            self.assertLessEqual(
                len(
                    canonical_bytes(
                        contract_start_frame(
                            jobs, status=fat, offset=offset, count=count
                        )
                    )
                ),
                START_CAP,
            )
            if offset + count < len(jobs) and count < 8:
                self.assertGreater(
                    len(
                        canonical_bytes(
                            contract_start_frame(
                                jobs, status=fat, offset=offset, count=count + 1
                            )
                        )
                    ),
                    START_CAP,
                )
            seen += [card["id"] for card in cont["data"]["work"]]
            offset += count
        self.assertEqual(seen, jobs)

        # Oversized source status is null under the 256-byte text rule, so it
        # cannot plant an oversized Work. Use legal long IDs to fill the frame.
        for width, reason in (
            (30, "item-exceeds-cap"),
            (128, "page-frame-exceeds-cap"),
        ):
            with self.subTest(reason=reason):
                wide_jobs = [f"d{n:02d}" + "x" * (width - 3) for n in range(1, 22)]
                for job in wide_jobs:
                    self.plant_dispatch(job, recorded_status="X" * 256)
                self.plant_v3_config(
                    job_ids=wide_jobs,
                    source_ids=["repo", *["dispatch/" + j for j in wide_jobs]],
                )
                size0 = len(
                    canonical_bytes(
                        contract_start_frame(wide_jobs, bound=False, status="X" * 256)
                    )
                )
                size1 = len(
                    canonical_bytes(
                        contract_start_frame(
                            wide_jobs, bound=False, status="X" * 256, count=1
                        )
                    )
                )
                if reason == "item-exceeds-cap":
                    self.assertLessEqual(size0, START_CAP)
                    self.assertGreater(size1, START_CAP)
                    initial = self.start()
                    self.assert_work_page(initial, initial, wide_jobs, 0, 0)
                    snap = initial["snapshot"]
                    overflow = self.start({"snapshot": snap, "cursor": f"{snap}:0"})
                else:
                    self.assertGreater(size0, START_CAP)
                    overflow = self.start()
                self.assertEqual(overflow["state"], "unavailable")
                self.assertEqual(overflow["reason"], reason)
                self.assertIsNone(overflow["data"])
                self.assertLessEqual(len(canonical_bytes(overflow)), START_CAP)

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
        for offset, count in ((0, 8), (8, 8), (16, 4)):
            self.assertLessEqual(
                len(
                    canonical_bytes(
                        contract_start_frame(jobs, offset=offset, count=count)
                    )
                ),
                START_CAP,
            )
        first = self.start()
        self.assert_start_frame(first)
        snap = first["snapshot"]
        work0 = first["data"]["work"]
        self.assertEqual(len(work0), 8, work0)
        self.assertEqual([row["id"] for row in work0], jobs[:8])
        self.assertIn("work omitted: 12", first["data"]["omissions"])
        self.assertIn(f"work next cursor: {snap}:8", first["data"]["omissions"])
        second = self.start({"profile": "dev", "snapshot": snap, "cursor": f"{snap}:8"})
        self.assertEqual(second["snapshot"], snap)
        work1 = second["data"]["work"]
        self.assertEqual(len(work1), 8)
        self.assertEqual([row["id"] for row in work1], jobs[8:16])
        self.assertIn("work omitted: 4", second["data"]["omissions"])
        self.assertIn(f"work next cursor: {snap}:16", second["data"]["omissions"])
        third = self.start({"profile": "dev", "snapshot": snap, "cursor": f"{snap}:16"})
        work2 = third["data"]["work"]
        self.assertEqual(len(work2), 4)
        self.assertEqual([row["id"] for row in work2], jobs[16:])
        self.assertNotIn("work omitted:", "\n".join(third["data"]["omissions"]))
        self.assertNotIn("work next cursor:", "\n".join(third["data"]["omissions"]))
        seen = [row["id"] for row in work0 + work1 + work2]
        self.assertEqual(seen, jobs)
        for page, offset, count in ((first, 0, 8), (second, 8, 8), (third, 16, 4)):
            self.assert_work_page(first, page, jobs, offset, count)
            arguments = (
                {"profile": "dev"}
                if offset == 0
                else {"profile": "dev", "snapshot": snap, "cursor": f"{snap}:{offset}"}
            )
            proc = self.serve(
                self.handshake(
                    [
                        rpc(
                            "tools/call",
                            2,
                            {"name": "lane_start", "arguments": arguments},
                        )
                    ]
                )
            )
            self.assertEqual(
                self.rpc_bytes(self.rpc_by_id(self.rpc_objects(proc), 2)),
                canonical_bytes(page),
            )
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
            )
        )
        self.assertEqual(
            self.lane_from_rpc(self.rpc_by_id(self.rpc_objects(mcp), 2)), second
        )

    def test_d_a38c_twenty_one_dispatch_ids_five_card_continuations(self):
        jobs = [f"d{n:02d}" for n in range(1, 22)]
        self.assertEqual(len(jobs), 21)
        self.plant_tree()
        for rec_id in jobs:
            self.plant_dispatch(rec_id, recorded_status="S" * 86)
        source_ids = ["repo", *[f"dispatch/{j}" for j in jobs]]
        self.assertEqual(len(source_ids), 22)
        self.plant_v3_config(
            job_ids=jobs,
            source_ids=source_ids,
            work_bindings=[],
            retained_refs=None,
        )
        # 86 UTF-8 ASCII status bytes: legal (<=256), plus 80 bytes/card
        # compared with "closed". Measured against the full contract frame.
        for offset in (0, 5, 10, 15):
            self.assertLessEqual(
                len(
                    canonical_bytes(
                        contract_start_frame(
                            jobs, bound=False, status="S" * 86, offset=offset, count=5
                        )
                    )
                ),
                START_CAP,
            )
            self.assertGreater(
                len(
                    canonical_bytes(
                        contract_start_frame(
                            jobs, bound=False, status="S" * 86, offset=offset, count=6
                        )
                    )
                ),
                START_CAP,
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
            self.assert_work_page(first, page, jobs, offset, count)
            proc = self.serve(
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
                                    "cursor": f"{snap}:{offset}",
                                },
                            },
                        )
                    ]
                )
            )
            obj = self.rpc_by_id(self.rpc_objects(proc), 2)
            self.assertEqual(self.rpc_bytes(obj), canonical_bytes(page))
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
                self.assertIn(
                    f"work next cursor: {snap}:{nxt}", page["data"]["omissions"]
                )
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
        self.assertEqual(
            selection,
            {
                "selection": "one",
                "selected_key": f"record/{digest}",
                "current": 1,
                "stale": 0,
                "unknown": 0,
                "complete": True,
            },
        )
        named = self.detail(
            "lane_handoffs", {"profile": "docs", "key": f"record/{digest}"}
        )
        self.assertEqual(named["data"]["candidate"]["key"], f"record/{digest}")
        self.assertEqual(named["data"]["handoffs"], selection)


def _startup_reply(case, fault, arguments=None, **kwargs):
    """Scripted contract counterparty for these finite startup fixtures only."""
    args = arguments or {}
    config = json.loads(case.config_path.read_bytes())
    jobs = config["job_ids"]
    profile = args.get("profile", "dev")
    offset = int(args.get("cursor", "a:0").split(":")[-1])
    bound = bool(config["discovery"]["work_bindings"])
    status = (
        json.loads((case.store / jobs[0] / "record.json").read_bytes())["status"]
        if jobs
        else "closed"
    )
    count = 0
    if jobs:
        width = len(jobs[0])
        if width == 128 or (width == 30 and "cursor" in args):
            reply = contract_start_frame()
            reply.update(
                state="unavailable",
                reason="page-frame-exceeds-cap" if width == 128 else "item-exceeds-cap",
                data=None,
            )
            if fault == "wrong-overflow":
                reply["reason"] = "response-exceeds-cap"
            return reply
        if width == 30:
            count = 0
        elif len(jobs) == 8:
            count = 0 if "cursor" not in args else (7 if offset == 0 else 1)
        elif len(jobs) == 20 and bound:
            count = min(8, 20 - offset)
        elif len(jobs) in (20, 21) and not bound:
            count = 0 if "cursor" not in args else min(5, len(jobs) - offset)
        else:
            raise AssertionError("counterparty fixture not declared")
    reply = contract_start_frame(
        jobs, bound=bound, status=status, offset=offset, count=count
    )
    reply["profile"] = profile
    for card in reply["data"]["work"]:
        card["revision"] = hashlib.sha256(
            (case.store / card["id"] / "record.json").read_bytes()
        ).hexdigest()
    reply["data"]["homes"] = [
        {
            k: _home_fixture(concept)[k]
            for k in (
                "concept",
                "home",
                "entrypoint",
                "document_present",
                "implementation_present",
            )
        }
        for concept in config["profiles"][profile]["startup_homes"]
    ]
    if fault == "never-drop" and jobs and "cursor" not in args:
        reply["data"]["work"] = contract_start_frame(
            jobs, bound=bound, status=status, count=1
        )["data"]["work"]
    if fault == "lost-owner" and "cursor" in args:
        reply["data"]["homes"] = []
    if fault == "underfilled" and "cursor" in args:
        reply["data"]["work"] = reply["data"]["work"][:-1]
    if fault == "wrong-status" and reply["data"]["work"]:
        reply["data"]["work"][0]["recorded_status"] = "invented"
    return reply


def _home_fixture(concept):
    from discovery_v3_support import CONCEPTS

    row = next(row for row in CONCEPTS if row[0] == concept)
    return dict(
        concept=concept,
        home=row[1],
        contract=row[2],
        entrypoint=row[3],
        registry=row[4],
        ownership="declared",
        document_present=True,
        implementation_present=None if row[5] == "none" else row[5] != "unbuilt",
        locked=False if row[6] == "symfony/workflow" else None,
        installed=None,
        activated=None,
        probed=None,
        intended=row[6],
        evidence=["contract", "repo"],
    )


def _startup_detail(case, fault, tool, arguments, **kwargs):
    reply = contract_start_frame()
    reply.update(query=tool, profile=arguments["profile"])
    if tool == "lane_homes":
        home = _home_fixture(arguments["concept"])
        if fault == "nonpackage-false" and home["concept"] == "mapping":
            home["locked"] = False
        reply["data"] = {"homes": [], "home": home, "page": None}
    else:
        inner = b"relevant handoff body for docs lineage"
        key = "record/" + hashlib.sha256(inner).hexdigest()
        selection = dict(
            selection="one",
            selected_key=key,
            current=1,
            stale=0,
            unknown=0,
            complete=True,
        )
        if fault == "false-none":
            selection.update(selection="none", selected_key=None, current=0)
        reply["data"] = {
            "handoffs": selection,
            "candidate": {"key": key},
            "candidates": [],
            "page": None,
        }
    return reply


def _startup_invoke(case, fault, args, **kwargs):
    import subprocess

    if args == ["check"]:
        return subprocess.CompletedProcess(args, 0, '{"tools":11,"valid":true}\n', "")
    raise AssertionError("undeclared counterparty invocation")


def _startup_query(case, fault, tool, args, **kwargs):
    import subprocess

    from discovery_v3_support import CURSOR_INVALID

    return subprocess.CompletedProcess([], 2, "", CURSOR_INVALID + "\n")


def _startup_serve(case, fault, lines, **kwargs):
    import subprocess

    responses = []
    for line in lines:
        req = json.loads(line)
        if req["method"] == "tools/call":
            payload = _startup_reply(case, fault, req["params"]["arguments"])
            responses.append(
                {
                    "jsonrpc": "2.0",
                    "id": req["id"],
                    "result": {
                        "content": [
                            {"type": "text", "text": canonical_bytes(payload).decode()}
                        ],
                        "structuredContent": payload,
                    },
                }
            )
    return subprocess.CompletedProcess(
        [], 0, "\n".join(json.dumps(p) for p in responses), ""
    )


class TestDiscoveryV3StartupControls(unittest.TestCase):
    def test_contract_size_premises_and_encoder(self):
        # Independently audited closed frame from discovery-examples.md, not
        # guessed from a reviewer estimate or obtained from a running subject.
        base = contract_start_frame()
        probe = _DiscoveryV3Fixture()
        probe.assert_start_frame(base)
        self.assertEqual(len(canonical_bytes(base)), 3641)
        self.assertEqual(
            canonical_bytes({"z": "é", "a": '\\"\n'}),
            b'{"a":"\\\\\\"\\n","z":"\\u00e9"}',
        )
        jobs20 = [_job(n) for n in range(1, 21)]
        self.assertEqual(
            [
                len(canonical_bytes(contract_start_frame(jobs20, offset=o, count=c)))
                for o, c in ((0, 8), (8, 8), (16, 4))
            ],
            [8111, 8111, 7313],
        )
        jobs21 = [f"d{n:02d}" for n in range(1, 22)]
        self.assertEqual(
            len(canonical_bytes(contract_start_frame(jobs21, bound=False, count=6))),
            7890,
        )
        for offset, expected in (
            (0, (8107, 8370)),
            (5, (8108, 8371)),
            (10, (8107, 8370)),
            (15, (8107, 8264)),
        ):
            sizes = tuple(
                len(
                    canonical_bytes(
                        contract_start_frame(
                            jobs21, bound=False, status="S" * 86, offset=offset, count=n
                        )
                    )
                )
                for n in (5, 6)
            )
            self.assertEqual(sizes, expected)
            self.assertLessEqual(sizes[0], START_CAP)
            self.assertGreater(sizes[1], START_CAP)

    def test_faulty_startup_counterparties(self):
        from discovery_v3_support import prove_counterparty

        replacements = {
            "start": _startup_reply,
            "detail": _startup_detail,
            "invoke": _startup_invoke,
            "query": _startup_query,
            "serve": _startup_serve,
        }
        cases = [
            (
                "test_d_a8_shipped_prod_startup_and_lock_absence",
                "nonpackage-false",
                "False is not None",
            ),
            (
                "test_d_a38_initial_work_drop_and_frame_failures",
                "never-drop",
                "Lists differ",
            ),
            (
                "test_d_a38_initial_work_drop_and_frame_failures",
                "wrong-overflow",
                "response-exceeds-cap",
            ),
            (
                "test_d_a38b_twenty_work_cards_page_eight_eight_four",
                "lost-owner",
                "homes",
            ),
            (
                "test_d_a38b_twenty_work_cards_page_eight_eight_four",
                "wrong-status",
                "work card changed",
            ),
            (
                "test_d_a38c_twenty_one_dispatch_ids_five_card_continuations",
                "underfilled",
                "Lists differ",
            ),
            ("test_d_a43_independent_start_then_targeted_detail", "false-none", "none"),
        ]
        for method, fault, assertion in cases:
            with self.subTest(method=method, fault=fault):
                prove_counterparty(
                    self,
                    TestDiscoveryV3Startup,
                    method,
                    replacements,
                    fault=fault,
                    assertion=assertion,
                )
