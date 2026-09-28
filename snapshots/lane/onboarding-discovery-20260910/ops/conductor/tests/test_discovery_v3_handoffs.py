"""Discovery/3 handoff selection, trust wrapping and relevance.

Acceptance rows: D-A11, D-A12, D-A13, D-A14, D-A15, D-A16, D-A17,
D-A17b, D-A17c, D-A18, D-A19, D-A32, D-A37, D-A45.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from discovery_v3_support import (  # noqa: E402
    DETAIL_CAP,
    HOSTILE_INNER,
    _DiscoveryV3Fixture,
    canonical_bytes,
    record_key,
    rpc,
    sha256_hex,
    wrap_untrusted_record,
)


def _bind(record_id: str, inner: bytes, lineage: str, paths: list[str], supersedes=None, kind="handoff"):
    return {
        "record_id": record_id,
        "kind": kind,
        "revision": sha256_hex(inner),
        "lineage": lineage,
        "work_paths": paths,
        "supersedes": list(supersedes or []),
    }


class TestDiscoveryV3Handoffs(_DiscoveryV3Fixture):
    def test_d_a11_empty_head_and_empty_retained_is_complete_none(self):
        self.plant_tree()
        self.plant_v3_config(
            retained_refs="refs/heads/records/",
            source_ids=["repo", "retained"],
        )
        payload = self.detail("lane_handoffs", {"profile": "dev"})
        self.assertEqual(payload["state"], "ok")
        data = payload["data"]
        self.assertEqual(data["candidates"], [])
        self.assertIsNone(data["candidate"])
        sel = data["handoffs"]
        self.assertIs(sel["complete"], True)
        self.assertEqual(sel["selection"], "none")
        self.assertIsNone(sel["selected_key"])
        self.assertEqual(sel["current"], 0)
        self.assertEqual(sel["stale"], 0)
        self.assertEqual(sel["unknown"], 0)
        page = self.assert_page(data["page"])
        self.assertEqual(page, {"offset": 0, "count": 0, "total": 0, "more": False, "next_cursor": None})
        retained = [src for src in payload["sources"] if src["id"] == "retained"][0]
        self.assertEqual(retained["state"], "ok")

    def test_d_a12_retained_unknown_filename_is_enumerated_and_named(self):
        inner = b"retained hidden handoff body\n"
        self.plant_tree()
        hidden = "ops/conductor/handoff/HANDOFF-hidden.md"
        commit = self.add_commit({hidden: inner}, "hidden")
        self.plant_ref("refs/heads/records/hidden", commit)
        self.git("checkout", "--detach", self.head)
        binding = _bind("session-h", inner, "dev", ["ops/conductor/example.md"])
        self.plant_v3_config(
            retained_refs="refs/heads/records/",
            source_ids=["repo", "retained"],
            record_bindings=[binding],
        )
        listed = self.detail("lane_handoffs", {"profile": "dev"})
        sel = listed["data"]["handoffs"]
        self.assertEqual(sel["selection"], "one")
        key = record_key(inner)
        self.assertEqual(sel["selected_key"], key)
        self.assertEqual(sel["current"], 1)
        self.assertIs(sel["complete"], True)
        named = self.detail("lane_handoffs", {"profile": "dev", "key": key})
        cand = named["data"]["candidate"]
        self.assertEqual(cand["key"], key)
        self.assertIsNotNone(cand["body"])
        self.assertEqual(cand["provenance"]["path"], hidden)
        self.assertEqual(cand["body_bytes"], len(inner))
        self.assertEqual(
            cand["body"], wrap_untrusted_record(key, sha256_hex(inner), inner)
        )

    def test_d_a13_two_current_handoffs_are_multiple_without_tiebreak(self):
        a = b"first current handoff"
        b = b"second current handoff"
        extra = {
            "ops/conductor/handoff/HANDOFF-one.md": a,
            "ops/conductor/handoff/HANDOFF-two.md": b,
        }
        self.plant_tree(extra=extra)
        bindings = [
            _bind("session-one", a, "dev", ["ops/a.md"]),
            _bind("session-two", b, "dev", ["ops/b.md"]),
        ]
        self.plant_v3_config(record_bindings=bindings)
        payload = self.detail("lane_handoffs", {"profile": "dev"})
        sel = payload["data"]["handoffs"]
        self.assertEqual(sel["selection"], "multiple")
        self.assertIsNone(sel["selected_key"])
        self.assertEqual(sel["current"], 2)
        self.assertIs(sel["complete"], True)
        keys = [row["key"] for row in payload["data"]["candidates"]]
        self.assertEqual(keys, sorted(keys))
        self.reset_repo()
        same_id_a = b"rev-one of shared"
        same_id_b = b"rev-two of shared"
        self.plant_tree(
            extra={
                "ops/conductor/handoff/HANDOFF-r1.md": same_id_a,
                "ops/conductor/handoff/HANDOFF-r2.md": same_id_b,
            }
        )
        tied = [
            _bind("shared", same_id_a, "dev", ["ops/a.md"]),
            _bind("shared", same_id_b, "dev", ["ops/a.md"]),
        ]
        self.plant_v3_config(record_bindings=tied)
        tied_payload = self.detail("lane_handoffs", {"profile": "dev"})
        self.assertEqual(tied_payload["data"]["handoffs"]["selection"], "multiple")
        self.assertIsNone(tied_payload["data"]["handoffs"]["selected_key"])
        self.assertEqual(tied_payload["data"]["handoffs"]["current"], 2)

    def test_d_a14_identical_bytes_share_a_key_distinct_blobs_do_not(self):
        same = b"identical handoff bytes"
        other = b"distinct handoff bytes"
        extra = {
            "ops/conductor/handoff/HANDOFF-alpha.md": same,
            "ops/conductor/handoff/HANDOFF-beta.md": same,
            "ops/conductor/handoff/HANDOFF-gamma.md": other,
        }
        self.plant_tree(extra=extra)
        bindings = [
            _bind("dup", same, "dev", ["ops/a.md"]),
            _bind("other", other, "dev", ["ops/b.md"]),
        ]
        self.plant_v3_config(record_bindings=bindings)
        payload = self.detail("lane_handoffs", {"profile": "dev"})
        cards = {row["key"]: row for row in payload["data"]["candidates"]}
        self.assertEqual(len(cards), 2)
        dup = cards[record_key(same)]
        self.assertEqual(dup["occurrences"], 2)
        self.assertEqual(dup["revision"], sha256_hex(same))
        self.assertEqual(cards[record_key(other)]["occurrences"], 1)
        provenances = [
            row["provenance"]["path"]
            for row in payload["data"]["candidates"]
            if row.get("provenance")
        ]
        self.assertEqual(len(provenances), 2)

    def test_d_a15_supersedes_marks_stale_and_aar_never_selected(self):
        old = b"old handoff body"
        new = b"new handoff body that supersedes"
        aar = b"aar body must not be selected as handoff"
        extra = {
            "ops/conductor/handoff/HANDOFF-old.md": old,
            "ops/conductor/handoff/HANDOFF-new.md": new,
            "ops/conductor/AAR-done.md": aar,
        }
        self.plant_tree(extra=extra)
        bindings = [
            _bind("old-id", old, "dev", ["ops/a.md"]),
            _bind("new-id", new, "dev", ["ops/a.md"], supersedes=["old-id"]),
            _bind("aar-id", aar, "dev", ["ops/a.md"], kind="aar", supersedes=["old-id"]),
        ]
        self.plant_v3_config(record_bindings=bindings)
        payload = self.detail("lane_handoffs", {"profile": "dev"})
        sel = payload["data"]["handoffs"]
        self.assertEqual(sel["selection"], "one")
        self.assertEqual(sel["selected_key"], record_key(new))
        self.assertEqual(sel["current"], 1)
        self.assertEqual(sel["stale"], 1)
        by_key = {row["key"]: row for row in payload["data"]["candidates"]}
        self.assertEqual(by_key[record_key(old)]["freshness"], "stale")
        self.assertEqual(by_key[record_key(new)]["freshness"], "current")
        self.assertEqual(by_key[record_key(aar)]["kind"], "aar")
        self.assertNotEqual(sel["selected_key"], record_key(aar))

    def test_d_a16_stale_page_keeps_terminal_current_selection(self):
        bodies: list[bytes] = []
        extra: dict[str, bytes] = {}
        bindings = []
        for i in range(16):
            inner = f"stale-handoff-{i:02d}-body".encode()
            bodies.append(inner)
            extra[f"ops/conductor/handoff/HANDOFF-{i:02d}.md"] = inner
            prev = [f"h{i - 1:02d}"] if i else []
            bindings.append(
                _bind(f"h{i:02d}", inner, "dev", ["ops/a.md"], supersedes=prev)
            )
        terminal = b"terminal-current-handoff-body"
        n = 0
        while record_key(terminal) <= max(record_key(b) for b in bodies):
            n += 1
            terminal = f"terminal-current-handoff-body-{n}".encode()
        extra["ops/conductor/handoff/HANDOFF-terminal.md"] = terminal
        bindings.append(
            _bind("h16", terminal, "dev", ["ops/a.md"], supersedes=["h15"])
        )
        self.plant_tree(extra=extra)
        self.plant_v3_config(record_bindings=bindings)
        first = self.detail("lane_handoffs", {"profile": "dev"})
        sel = first["data"]["handoffs"]
        expected_key = record_key(terminal)
        expected_sel = {
            "selection": "one",
            "selected_key": expected_key,
            "current": 1,
            "stale": 16,
            "unknown": 0,
            "complete": True,
        }
        self.assertEqual(sel, expected_sel)
        page = self.assert_page(first["data"]["page"])
        self.assertEqual(page["count"], 16)
        self.assertEqual(page["total"], 17)
        self.assertTrue(page["more"])
        keys0 = [row["key"] for row in first["data"]["candidates"]]
        self.assertEqual(len(keys0), 16)
        self.assertNotIn(expected_key, keys0)
        for row in first["data"]["candidates"]:
            self.assertEqual(row["freshness"], "stale", row)
            self.assertNotEqual(row["key"], expected_key)
        snap = first["snapshot"]
        second = self.detail(
            "lane_handoffs",
            {"profile": "dev", "snapshot": snap, "cursor": page["next_cursor"]},
        )
        self.assertEqual(second["data"]["handoffs"], expected_sel)
        keys1 = [row["key"] for row in second["data"]["candidates"]]
        self.assertEqual(keys1, [expected_key])
        self.assertEqual(second["data"]["candidates"][0]["freshness"], "current")
        stale_key = record_key(bodies[0])
        named = self.detail(
            "lane_handoffs", {"profile": "dev", "key": stale_key}
        )
        self.assertEqual(named["data"]["handoffs"], expected_sel)
        cand = named["data"]["candidate"]
        self.assertEqual(cand["key"], stale_key)
        self.assertEqual(cand["freshness"], "stale")
        self.assertIsNotNone(cand["body"])
        self.assertNotEqual(named["data"]["handoffs"]["selected_key"], stale_key)

    def test_d_a17_unbound_unreadable_or_missing_blocks_selection(self):
        good = b"good bound current handoff"
        unbound = b"observed unbound handoff"
        extra = {
            "ops/conductor/handoff/HANDOFF-good.md": good,
            "ops/conductor/handoff/HANDOFF-loose.md": unbound,
        }
        self.plant_tree(extra=extra)
        missing_inner = b"bound but absent from the tree"
        bindings = [
            _bind("good-id", good, "dev", ["ops/a.md"]),
            _bind("missing-id", missing_inner, "dev", ["ops/b.md"]),
        ]
        self.plant_v3_config(record_bindings=bindings)
        payload = self.detail("lane_handoffs", {"profile": "dev"})
        sel = payload["data"]["handoffs"]
        self.assertEqual(sel["selection"], "unknown")
        self.assertIsNone(sel["selected_key"])
        self.assertIsNone(sel["current"])
        self.assertIsNone(sel["stale"])
        self.assertIsNone(sel["unknown"])
        self.assertIs(sel["complete"], False)
        keys = {row["key"]: row for row in payload["data"]["candidates"]}
        self.assertIn(record_key(unbound), keys)
        self.assertEqual(keys[record_key(unbound)]["reason"], "metadata-missing")
        self.assertIsNone(keys[record_key(unbound)]["body"])
        self.assertIsNone(keys[record_key(unbound)]["provenance"])
        missing_key = record_key(missing_inner)
        self.assertIn(missing_key, keys)
        self.assertEqual(keys[missing_key]["reason"], "missing-bound-record")
        self.assertEqual(keys[missing_key]["occurrences"], 0)

    def test_d_a17b_unbound_aars_do_not_block_handoff_selection(self):
        good = b"readable bound current handoff"
        aar = b"unbound aar body"
        extra = {
            "ops/conductor/handoff/HANDOFF-good.md": good,
            "ops/conductor/AAR-loose.md": aar,
        }
        self.plant_tree(extra=extra)
        self.plant_v3_config(
            record_bindings=[_bind("good-id", good, "dev", ["ops/a.md"])]
        )
        payload = self.detail("lane_handoffs", {"profile": "dev"})
        sel = payload["data"]["handoffs"]
        self.assertEqual(sel["selection"], "one")
        self.assertEqual(sel["selected_key"], record_key(good))
        self.assertIs(sel["complete"], True)
        self.assertEqual(sel["current"], 1)
        self.assertEqual(sel["stale"], 0)
        self.assertEqual(sel["unknown"], 0)
        aar_card = [row for row in payload["data"]["candidates"] if row["kind"] == "aar"]
        self.assertTrue(aar_card)
        self.assertEqual(aar_card[0]["reason"], "metadata-missing")

    def test_d_a17c_unbound_head_records_leak_no_body(self):
        extra = {}
        for i in range(1, 5):
            extra[f"ops/conductor/handoff/HANDOFF-{i}.md"] = f"unbound-handoff-{i}".encode()
            extra[f"ops/conductor/AAR-{i}.md"] = f"unbound-aar-{i}".encode()
        self.plant_tree(extra=extra)
        self.plant_v3_config(record_bindings=[], retained_refs=None)
        payload = self.detail("lane_handoffs", {"profile": "dev"})
        sel = payload["data"]["handoffs"]
        self.assertEqual(sel["selection"], "unknown")
        self.assertIs(sel["complete"], False)
        self.assertIsNone(sel["selected_key"])
        self.assertIsNone(sel["current"])
        cards = payload["data"]["candidates"]
        kinds = [row["kind"] for row in cards]
        self.assertEqual(kinds.count("handoff"), 4, cards)
        self.assertEqual(kinds.count("aar"), 4, cards)
        for row in cards:
            self.assertIsNone(row["body"])
            self.assertIsNone(row["provenance"])
            self.assertIsNone(row["body_bytes"])
            self.assertEqual(row["reason"], "metadata-missing")
            dumped = canonical_bytes(row)
            self.assertNotIn(b"unbound-handoff", dumped)
            self.assertNotIn(b"unbound-aar", dumped)

    def test_d_a18_root_and_lineage_filter_without_cross_profile_leak(self):
        dev_body = b"dev only handoff"
        prod_body = b"prod only handoff"
        mixed_body = b"mixed root handoff"
        extra = {
            "ops/conductor/handoff/HANDOFF-dev.md": dev_body,
            "ops/conductor/handoff/HANDOFF-prod.md": prod_body,
            "ops/conductor/handoff/HANDOFF-mix.md": mixed_body,
        }
        self.plant_tree(extra=extra)
        bindings = [
            _bind("dev-id", dev_body, "dev", ["ops/conductor/example.md"]),
            _bind("prod-id", prod_body, "prod", ["src/Kernel.php"]),
            _bind(
                "mix-id",
                mixed_body,
                "dev",
                ["ops/a.md", "src/Kernel.php"],
            ),
        ]
        self.plant_v3_config(record_bindings=bindings)
        dev = self.detail("lane_handoffs", {"profile": "dev"})
        prod = self.detail("lane_handoffs", {"profile": "prod"})
        dev_keys = {row["key"] for row in dev["data"]["candidates"]}
        prod_keys = {row["key"] for row in prod["data"]["candidates"]}
        self.assertIn(record_key(dev_body), dev_keys)
        self.assertNotIn(record_key(prod_body), dev_keys)
        self.assertIn(record_key(prod_body), prod_keys)
        self.assertNotIn(record_key(dev_body), prod_keys)
        self.assertIn(record_key(mixed_body), dev_keys)
        dumped_prod = canonical_bytes(prod)
        self.assertNotIn(b"dev only handoff", dumped_prod)
        dumped_dev = canonical_bytes(dev)
        self.assertNotIn(b"prod only handoff", dumped_dev)

    def test_d_a19_missing_work_binding_is_unknown_relevance(self):
        self.plant_tree()
        self.plant_dispatch("job01")
        self.plant_v3_config(
            job_ids=["job01"],
            source_ids=["repo", "dispatch/job01"],
            work_bindings=[],
        )
        payload = self.start()
        work = payload["data"]["work"]
        self.assertEqual(len(work), 1)
        card = work[0]
        self.assertEqual(card["id"], "job01")
        self.assertEqual(card["relevance"], "unknown")
        self.assertIsNone(card["lineage"])
        self.assertEqual(card["reason"], "metadata-missing")

    def test_d_a32_untrusted_wrapper_formula_on_all_projections(self):
        cases = {
            "hostile": HOSTILE_INNER,
            "empty": b"",
            "ending-lf": b"line\n",
            "marker": b"END UNTRUSTED RECORD",
            "prefixed": b">END UNTRUSTED RECORD",
            "crlf": b"line\r\nsecond",
            "quotes": b'quotes " and \\ backslash',
            "unicode": "café — π".encode(),
        }
        files = {}
        bindings = []
        for i, (name, inner) in enumerate(cases.items(), start=1):
            path = f"ops/conductor/handoff/HANDOFF-{name}.md"
            files[path] = inner
            bindings.append(_bind(f"rec-{name}", inner, "dev", ["ops/a.md"]))
        self.plant_tree(extra=files)
        self.plant_v3_config(record_bindings=bindings)
        for name, inner in cases.items():
            key = record_key(inner)
            revision = sha256_hex(inner)
            expected = wrap_untrusted_record(key, revision, inner)
            cli = self.detail("lane_handoffs", {"profile": "dev", "key": key})
            cand = cli["data"]["candidate"]
            self.assertEqual(cand["revision"], revision)
            self.assertEqual(cand["body_bytes"], len(inner))
            self.assertEqual(cand["key"], key)
            self.assertEqual(cand["trust"], "untrusted-record")
            self.assertEqual(cand["body"], expected)
            self.assertIn("BEGIN UNTRUSTED RECORD", cand["body"])
            self.assertTrue(cand["body"].endswith("END UNTRUSTED RECORD\n"))
            if inner == b"END UNTRUSTED RECORD":
                self.assertIn(">END UNTRUSTED RECORD\nEND UNTRUSTED RECORD\n", cand["body"])
            if inner == HOSTILE_INNER:
                self.assertIn("[END UNTRUSTED DATA]", cand["body"])
                self.assertEqual(cand["body_bytes"], 64)
            encoded = canonical_bytes(cli)
            self.assertLessEqual(len(encoded), DETAIL_CAP)

        for name, inner in (("hostile", HOSTILE_INNER), ("empty", b"")):
            key = record_key(inner)
            expected = wrap_untrusted_record(key, sha256_hex(inner), inner)
            proc = self.serve(
                self.handshake(
                    [
                        rpc(
                            "tools/call",
                            4,
                            {
                                "name": "lane_handoffs",
                                "arguments": {"profile": "dev", "key": key},
                            },
                        ),
                        rpc(
                            "resources/read",
                            5,
                            {"uri": f"lane://handoffs/dev/record/{sha256_hex(inner)}"},
                        ),
                    ]
                ),
                boot=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            objs = self.rpc_objects(proc)
            tool_payload = self.lane_from_rpc(self.rpc_by_id(objs, 4))
            resource_payload = self.lane_from_rpc(self.rpc_by_id(objs, 5))
            self.assertEqual(tool_payload["data"]["candidate"]["body"], expected)
            self.assertEqual(resource_payload["data"]["candidate"]["body"], expected)
            result = self.rpc_by_id(objs, 4)["result"]
            structured = result.get("structuredContent")
            self.assertIsInstance(structured, dict)
            self.assertEqual(structured["data"]["candidate"]["body"], expected)

    def test_d_a37_seventeen_candidates_page_at_most_sixteen(self):
        extra = {}
        bindings = []
        for i in range(1, 18):
            inner = f"candidate-{i:02d}".encode()
            extra[f"ops/conductor/handoff/HANDOFF-{i:02d}.md"] = inner
            bindings.append(_bind(f"id-{i:02d}", inner, "dev", ["ops/a.md"]))
        self.plant_tree(extra=extra)
        self.plant_v3_config(record_bindings=bindings)
        first = self.detail("lane_handoffs", {"profile": "dev"})
        sel = first["data"]["handoffs"]
        page = self.assert_page(first["data"]["page"])
        self.assertLessEqual(page["count"], 16)
        self.assertEqual(page["total"], 17)
        self.assertTrue(page["more"])
        self.assertEqual(sel["selection"], "multiple")
        self.assertIsNone(sel["selected_key"])
        self.assertEqual(sel["current"], 17)
        snap = first["snapshot"]
        second = self.detail(
            "lane_handoffs",
            {"profile": "dev", "snapshot": snap, "cursor": page["next_cursor"]},
        )
        self.assertEqual(second["data"]["handoffs"], sel)
        self.assertEqual(second["data"]["page"]["offset"] + second["data"]["page"]["count"], 17)
        named_inner = b"candidate-01"
        named = self.detail(
            "lane_handoffs",
            {"profile": "dev", "key": record_key(named_inner)},
        )
        self.assertEqual(named["data"]["candidate"]["key"], record_key(named_inner))
        self.assertIsNone(named["data"]["page"])
        self.assertEqual(named["data"]["handoffs"], sel)

    def test_d_a45_other_profile_key_matches_nonexistent(self):
        inner = b"prod only secret handoff prose"
        extra = {"ops/conductor/handoff/HANDOFF-prod.md": inner}
        self.plant_tree(extra=extra)
        self.plant_v3_config(
            record_bindings=[_bind("prod-id", inner, "prod", ["src/Kernel.php"])]
        )
        missing = "record/" + ("f" * 64)
        known = record_key(inner)
        other = self.detail(
            "lane_handoffs", {"profile": "dev", "key": known}
        )
        none = self.detail(
            "lane_handoffs", {"profile": "dev", "key": missing}
        )
        self.assertEqual(other["reason"], "unknown-key")
        self.assertEqual(none["reason"], "unknown-key")
        self.assertEqual(other["data"], none["data"])
        self.assertIsNone(other["data"]["candidate"])
        dumped = canonical_bytes(other)
        self.assertNotIn(b"prod only secret", dumped)
        self.assertNotIn(b"HANDOFF-prod.md", dumped)
