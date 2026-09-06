"""Discovery/3 snapshots, cursors, parity and contract fingerprints.

Acceptance rows: D-A24, D-A25, D-A26, D-A39, D-A46, D-A47.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from discovery_v3_support import (  # noqa: E402
    BOOT_MISSING,
    BOOT_MODULES,
    CURSOR_INVALID,
    HEX64,
    RUN_CAP,
    SOURCE_KEYS,
    _DiscoveryV3Fixture,
    adapter_implementation_digest,
    canonical_bytes,
    digest_only_bind,
    rejected_boot_line,
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
            proc = self.query(tool, arguments)
            payload = self.load_envelope(proc, tool)
            self.assert_envelope(payload, tool, profile=arguments["profile"])
            encoded = self.assert_canonical_stdout(proc, payload)
            again_proc = self.query(tool, arguments)
            self.assertEqual(again_proc.stdout.encode("utf-8"), proc.stdout.encode("utf-8"), tool)
            self.assertEqual(payload["snapshot"], snap)
            cli[(tool, tuple(sorted(arguments.items())))] = (payload, encoded)
        requests = []
        rpc_id = 20
        for tool, arguments, uri in pairs:
            requests.append(rpc("tools/call", rpc_id, {"name": tool, "arguments": arguments}))
            rpc_id += 1
            requests.append(rpc("resources/read", rpc_id, {"uri": uri}))
            rpc_id += 1
        proc = self.serve(self.handshake(requests), boot=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        objs = self.rpc_objects(proc)
        idx = 0
        for tool, arguments, _uri in pairs:
            call_payload = self.lane_from_rpc(self.rpc_by_id(objs, 20 + idx))
            read_payload = self.lane_from_rpc(self.rpc_by_id(objs, 21 + idx))
            idx += 2
            expected, encoded = cli[(tool, tuple(sorted(arguments.items())))]
            self.assertEqual(canonical_bytes(call_payload), encoded, tool)
            self.assertEqual(canonical_bytes(read_payload), encoded, tool)
            self.assertEqual(call_payload, expected, tool)
            self.assertEqual(read_payload, expected, tool)

    def test_d_a46_failed_source_fingerprint_is_stable_until_recovery(self):
        self.plant_tree()
        pinned = self.head
        moved = self.add_commit({"docs/extra-retained.md": b"x\n"}, "extra")
        self.plant_ref("refs/heads/records/keep", moved)
        self.git("checkout", "--detach", pinned)
        self.head = pinned
        obj = self.object_path(moved)
        self.assertTrue(obj.is_file(), obj)
        saved = obj.read_bytes()
        obj.unlink()
        self.assertFalse(obj.exists())
        self.plant_v3_config(
            retained_refs="refs/heads/records/",
            source_ids=["repo", "retained"],
        )
        first = self.start()
        second = self.start()
        self.assertEqual(first["snapshot"], second["snapshot"])
        retained = [src for src in first["sources"] if src["id"] == "retained"][0]
        again = [src for src in second["sources"] if src["id"] == "retained"][0]
        self.assertEqual(retained["state"], "unavailable")
        self.assertNotEqual(retained["reason"], "disabled")
        self.assertEqual(retained["fingerprint"], again["fingerprint"])
        self._plant_bytes(obj, saved)
        self.assertEqual(obj.read_bytes(), saved)
        third = self.start()
        self.assertNotEqual(third["snapshot"], first["snapshot"])
        recovered = [src for src in third["sources"] if src["id"] == "retained"][0]
        self.assertNotEqual(recovered["fingerprint"], retained["fingerprint"])
        self.assertEqual(recovered["state"], "ok")

    def test_d_a47_trusted_boot_and_executed_byte_binding(self):
        self.plant_tree()
        self.plant_v3_config()
        self.destroy_head_object()
        self.plant_v3_config()
        check = self.invoke(["check"], boot=False)
        self.assertEqual(self.load_query(check), {"valid": True, "tools": 11})
        listed = self.serve(self.handshake([rpc("tools/list", 2)]), boot=False)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        missing = self.query("lane_start", {"profile": "dev"}, boot=False)
        line = self.assert_refusal(missing, "config")
        self.assertEqual(line, BOOT_MISSING)
        brief = self.query("lane_brief", {}, boot=False)
        self.assertEqual(brief.returncode, 0, brief.stderr)

        self.ensure_boot()
        oversized = self.boot_map()
        oversized["ops/conductor/tools/lane_refs.py"] = b"Z" * (1024 * 1024 + 1)
        over_root = Path(self._tmp.name) / "boot-oversize"
        self.plant_boot(root=over_root, components=oversized, enforce_caps=False)
        over = self.query(
            "lane_start",
            {"profile": "dev"},
            boot=True,
            boot_dir=over_root,
        )
        over_line = self.assert_refusal(over, "config")
        self.assertEqual(
            over_line,
            rejected_boot_line(
                "ops/conductor/tools/lane_refs.py", "component-oversized"
            ),
        )

        incomplete = self.boot_map()
        miss_root = Path(self._tmp.name) / "boot-missing-component"
        miss_root.mkdir()
        for rel, data in incomplete.items():
            if rel.endswith("lane_read.py"):
                continue
            self._plant_bytes(miss_root / rel, data)
        miss = self.query(
            "lane_start", {"profile": "dev"}, boot=True, boot_dir=miss_root
        )
        miss_line = self.assert_refusal(miss, "config")
        self.assertEqual(
            miss_line,
            rejected_boot_line("ops/conductor/tools/lane_read.py", "component-missing"),
        )

        not_reg_root = Path(self._tmp.name) / "boot-not-regular"
        self.plant_boot(root=not_reg_root)
        target = not_reg_root / "ops/conductor/tools/lane_mcp.py"
        target.unlink()
        target.mkdir()
        not_reg = self.query(
            "lane_start", {"profile": "dev"}, boot=True, boot_dir=not_reg_root
        )
        not_reg_line = self.assert_refusal(not_reg, "config")
        self.assertEqual(
            not_reg_line,
            rejected_boot_line("ops/conductor/tools/lane_mcp.py", "not-regular"),
        )

        file_fd = os.open(str(self.config_path), os.O_RDONLY)
        try:
            entry = self.ensure_boot() / "ops" / "conductor" / "tools" / "lane_mcp.py"
            argv = [
                sys.executable,
                "-B",
                str(entry),
                "--config",
                str(self.config_path),
                "--discovery-boot-fd",
                str(file_fd),
                "query",
                "lane_start",
                '{"profile":"dev"}',
            ]
            bad_desc = subprocess.run(
                argv,
                cwd=str(self.cwd),
                env=self.env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=RUN_CAP,
                check=False,
                pass_fds=[file_fd],
                close_fds=True,
            )
        finally:
            os.close(file_fd)
        self.assertEqual(
            self.assert_refusal(bad_desc, "config"),
            rejected_boot_line("descriptor", "descriptor-unreadable"),
        )

        artifact_a = Path(self._tmp.name) / "boot-a"
        artifact_b = Path(self._tmp.name) / "boot-b"
        base = self.boot_map()
        contract_a = base["ops/conductor/discovery-lever.md"]
        contract_b = contract_a + b"\n# discovery-boot-artifact-B\n"
        self.assertNotEqual(sha256_hex(contract_a), sha256_hex(contract_b))
        self.plant_boot(
            root=artifact_a,
            components=dict(base),
            markers={rel: "A" for rel in BOOT_MODULES},
        )
        bytes_b = dict(base)
        bytes_b["ops/conductor/discovery-lever.md"] = contract_b
        self.plant_boot(
            root=artifact_b,
            components=bytes_b,
            markers={rel: "B" for rel in BOOT_MODULES},
        )
        self.marker_path.write_bytes(b"")
        first = self.start(boot=True, boot_dir=artifact_a, entry=artifact_a / "ops/conductor/tools/lane_mcp.py")
        contract = [src for src in first["sources"] if src["id"] == "contract"][0]
        adapter = [src for src in first["sources"] if src["id"] == "adapter"][0]
        repo_src = [src for src in first["sources"] if src["id"] == "repo"][0]
        self.assertEqual(set(contract), set(SOURCE_KEYS))
        self.assertEqual(contract["state"], "ok")
        self.assertEqual(adapter["state"], "ok")
        self.assertEqual(repo_src["state"], "unavailable")
        dumped = canonical_bytes(first)
        self.assertNotIn(sha256_hex(contract_a).encode(), dumped)
        rev_a = sha256_hex(contract_a)
        rev_b = sha256_hex(contract_b)
        self.assertNotEqual(rev_a, rev_b)
        impl_a = adapter_implementation_digest(
            {
                rel: (artifact_a / rel).read_bytes()
                for rel in BOOT_MODULES
            }
        )
        markers_a = self.marker_path.read_text(encoding="ascii")
        for rel in BOOT_MODULES:
            self.assertIn("A:" + Path(rel).name, markers_a, markers_a)

        self.marker_path.write_bytes(b"")
        second = self.start(boot=True, boot_dir=artifact_b, entry=artifact_b / "ops/conductor/tools/lane_mcp.py")
        contract2 = [src for src in second["sources"] if src["id"] == "contract"][0]
        self.assertEqual(contract2["state"], "ok")
        self.assertNotEqual(contract2["fingerprint"], contract["fingerprint"])
        self.assertNotEqual(second["snapshot"], first["snapshot"])
        self.assertNotIn(rev_b.encode(), canonical_bytes(second))
        markers_b = self.marker_path.read_text(encoding="ascii")
        for rel in BOOT_MODULES:
            self.assertIn("B:" + Path(rel).name, markers_b, markers_b)

        changed_impl = dict(self.boot_map(artifact_a))
        changed_impl["ops/conductor/tools/lane_read.py"] = (
            changed_impl["ops/conductor/tools/lane_read.py"] + b"\n# adapter-byte\n"
        )
        impl_root = Path(self._tmp.name) / "boot-impl"
        self.plant_boot(root=impl_root, components=changed_impl)
        impl_run = self.start(
            boot=True,
            boot_dir=impl_root,
            entry=impl_root / "ops/conductor/tools/lane_mcp.py",
        )
        adapter_changed = [src for src in impl_run["sources"] if src["id"] == "adapter"][0]
        contract_same = [src for src in impl_run["sources"] if src["id"] == "contract"][0]
        self.assertNotEqual(adapter_changed["fingerprint"], adapter["fingerprint"])
        self.assertEqual(contract_same["fingerprint"], contract["fingerprint"])
        impl_b = adapter_implementation_digest(
            {rel: (impl_root / rel).read_bytes() for rel in BOOT_MODULES}
        )
        self.assertNotEqual(impl_a, impl_b)

        self.marker_path.write_bytes(b"")
        mixed = self.query(
            "lane_start",
            {"profile": "dev"},
            boot=True,
            boot_dir=artifact_a,
            entry=artifact_b / "ops/conductor/tools/lane_mcp.py",
        )
        mixed_line = self.assert_refusal(mixed, "config")
        self.assertEqual(
            mixed_line,
            rejected_boot_line(
                "ops/conductor/tools/lane_mcp.py", "binding-mismatch"
            ),
        )
        self.assertTrue(
            digest_only_bind(
                (artifact_a / "ops/conductor/tools/lane_mcp.py").read_bytes(),
                artifact_b / "ops/conductor/tools/lane_mcp.py",
            )
        )
        self.assertNotEqual(
            sha256_hex((artifact_a / "ops/conductor/tools/lane_mcp.py").read_bytes()),
            sha256_hex((artifact_b / "ops/conductor/tools/lane_mcp.py").read_bytes()),
        )

        live = Path(__file__).resolve().parents[3] / "ops/conductor/tools/lane_mcp.py"
        self.assertTrue(live.is_file(), live)
        self.assertNotEqual(
            live.read_bytes(),
            (artifact_a / "ops/conductor/tools/lane_mcp.py").read_bytes(),
        )
        unverified = self.query(
            "lane_start",
            {"profile": "dev"},
            boot=True,
            boot_dir=artifact_a,
            entry=live,
        )
        unverified_line = self.assert_refusal(unverified, "config")
        self.assertIn("binding-", unverified_line)
        self.assertTrue(
            unverified_line.startswith(
                "config: expected trusted discovery boot descriptor; found rejected "
            ),
            unverified_line,
        )

        loaded = self.load_acquire(artifact_a)
        self.assertEqual(
            Path(loaded.__file__).resolve(),
            (artifact_a / "ops/conductor/tools/lane_refs.py").resolve(),
        )
        captured = dict(self.boot_map(artifact_a))
        payload = self._last_config_payload
        self.assertIsInstance(payload, dict)
        try:
            first_reading = loaded.acquire(payload, captured, checkpoint=None)
        except TypeError as exc:
            self.fail(f"acquire(config, boot, *, checkpoint=None) refused: {exc}")
        outside = Path(self._tmp.name) / "mutable-lane_refs.py"
        self._plant_bytes(outside, b"raise RuntimeError('must-not-reload')\n")
        (artifact_a / "ops/conductor/tools/lane_refs.py").write_bytes(
            outside.read_bytes()
        )
        self.assertEqual(
            (artifact_a / "ops/conductor/tools/lane_refs.py").read_bytes(),
            outside.read_bytes(),
        )
        try:
            second_reading = loaded.acquire(payload, captured, checkpoint=None)
        except TypeError as exc:
            self.fail(f"acquire after pathname mutation refused: {exc}")
        self.assertEqual(
            canonical_bytes(first_reading)
            if not isinstance(first_reading, bytes)
            else first_reading,
            canonical_bytes(second_reading)
            if not isinstance(second_reading, bytes)
            else second_reading,
        )
