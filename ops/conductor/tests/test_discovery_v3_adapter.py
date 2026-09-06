"""Discovery/3 adapter bounds, custody, subprocess-free core and launch FILE.

Acceptance rows: D-A27, D-A28, D-A29, D-A30, D-A31, D-A36, D-A41, D-A42.
"""

from __future__ import annotations

import ast
import json
import os
import stat
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from discovery_v3_support import (  # noqa: E402
    READ,
    REFS,
    SUBPROCESS_NAMES,
    TOOL,
    WRITER_MODULES,
    _DiscoveryV3Fixture,
    canonical_bytes,
    omitted_check_accepts,
    record_key,
    sha256_hex,
)


class TestDiscoveryV3Adapter(_DiscoveryV3Fixture):
    def test_d_a27_declared_overflows_never_unique_partial_selection(self):
        extra = {
            f"ops/conductor/handoff/HANDOFF-{i:03d}.md": f"rec-{i:03d}".encode()
            for i in range(257)
        }
        self.plant_tree(extra=extra)
        self.plant_v3_config(record_bindings=[])
        overflow = self.query("lane_handoffs", {"profile": "dev"})
        payload = self.load_envelope(overflow, "lane_handoffs")
        self.assertEqual(payload["state"], "unavailable")
        self.assertEqual(payload["reason"], "record-overflow")
        self.assertIsNone(payload["data"])
        self.reset_repo()
        self.plant_tree()
        base = self.head
        for i in range(65):
            self.plant_ref(f"refs/heads/records/r{i:02d}", base)
        self.plant_v3_config(
            retained_refs="refs/heads/records/",
            source_ids=["repo", "retained"],
        )
        refs = self.detail("lane_handoffs", {"profile": "dev"})
        retained = [src for src in refs["sources"] if src["id"] == "retained"][0]
        self.assertEqual(retained["state"], "unavailable")
        self.assertEqual(retained["reason"], "ref-overflow")
        sel = refs["data"]["handoffs"]
        self.assertIs(sel["complete"], False)
        self.assertEqual(sel["selection"], "unknown")
        self.assertIsNone(sel["selected_key"])
        self.reset_repo()
        fat_tree = {f"ops/conductor/handoff/pad-{i:04d}.txt": b"x" for i in range(4097)}
        self.plant_tree(extra=fat_tree)
        self.plant_v3_config()
        tree = self.detail("lane_handoffs", {"profile": "dev"})
        repo_src = [src for src in tree["sources"] if src["id"] == "repo"][0]
        self.assertEqual(repo_src["state"], "unavailable")
        self.assertEqual(repo_src["reason"], "tree-overflow")
        self.reset_repo()
        oversize = b"Z" * (1024 * 1024 + 1)
        self.plant_tree(extra={"ops/conductor/handoff/HANDOFF-fat.md": oversize})
        self.plant_v3_config(
            record_bindings=[
                {
                    "record_id": "fat",
                    "kind": "handoff",
                    "revision": sha256_hex(oversize),
                    "lineage": "dev",
                    "work_paths": ["ops/a.md"],
                    "supersedes": [],
                }
            ]
        )
        big = self.detail("lane_handoffs", {"profile": "dev"})
        reasons = {src["reason"] for src in big["sources"]}
        self.assertTrue(
            reasons & {"oversized", "budget-exceeded", "record-overflow", "unreadable"},
            reasons,
        )
        if big["state"] == "ok":
            self.assertNotEqual(big["data"]["handoffs"]["selection"], "one")

    def test_d_a28_unreadable_empty_and_disabled_namespaces(self):
        self.plant_tree()
        self.plant_v3_config()
        disabled = self.start()
        retained = [src for src in disabled["sources"] if src["id"] == "retained"][0]
        self.assertEqual(retained["state"], "unavailable")
        self.assertEqual(retained["reason"], "disabled")
        self.assertIn("retained source not searched", disabled["data"]["omissions"])
        self.plant_v3_config(
            retained_refs="refs/heads/records/",
            source_ids=["repo", "retained"],
        )
        empty = self.detail("lane_handoffs", {"profile": "dev"})
        retained_ok = [src for src in empty["sources"] if src["id"] == "retained"][0]
        self.assertEqual(retained_ok["state"], "ok")
        self.assertIs(empty["data"]["handoffs"]["complete"], True)
        self.assertEqual(empty["data"]["handoffs"]["selection"], "none")
        records_dir = self.gitdir / "refs" / "heads" / "records"
        records_dir.mkdir(parents=True, exist_ok=True)
        planted = self.make_inaccessible(records_dir)
        self.assertIn(planted, ("chmod-0", "fifo-not-dir"), planted)
        try:
            self.plant_v3_config(
                retained_refs="refs/heads/records/",
                source_ids=["repo", "retained"],
            )
            unread = self.detail("lane_handoffs", {"profile": "dev"})
        finally:
            if records_dir.exists() and records_dir.is_dir():
                os.chmod(records_dir, 0o755)
        retained_bad = [src for src in unread["sources"] if src["id"] == "retained"][0]
        self.assertEqual(retained_bad["state"], "unavailable")
        self.assertEqual(retained_bad["reason"], "unreadable")
        sel = unread["data"]["handoffs"]
        self.assertEqual(sel["selection"], "unknown")
        self.assertIs(sel["complete"], False)

    def test_d_a29_unsafe_paths_and_ambient_git_are_rejected(self):
        self.plant_tree()
        outside = Path(self._tmp.name) / "outside"
        outside.mkdir()
        (outside / "secret").write_bytes(b"secret-should-not-leak")
        decoy = self.cwd / ".git"
        decoy.mkdir()
        (decoy / "HEAD").write_text("ref: refs/heads/decoy\n", encoding="utf-8")
        link = self.repo / "ops" / "link-escape"
        try:
            link.symlink_to(outside)
        except OSError:
            link = None
        fifo = self.repo / "ops" / "fifo"
        os.mkfifo(fifo)
        self.assertTrue(stat.S_ISFIFO(fifo.stat().st_mode))
        self.plant_v3_config()
        env = {
            "GIT_DIR": str(decoy),
            "GIT_WORK_TREE": str(self.cwd),
            "GIT_COMMON_DIR": str(decoy),
        }
        before_decoy = (decoy / "HEAD").read_bytes()
        payload = self.start(extra_env=env)
        self.assertEqual((decoy / "HEAD").read_bytes(), before_decoy)
        dumped = canonical_bytes(payload)
        self.assertNotIn(b"secret-should-not-leak", dumped)
        self.assertNotIn(b"decoy", dumped.lower())
        alt = self.repo / ".git" / "objects" / "info" / "alternates"
        alt.parent.mkdir(parents=True, exist_ok=True)
        self._plant_bytes(alt, str(outside).encode() + b"\n")
        after_alt = self.query("lane_start", {"profile": "dev"}, extra_env=env)
        alt_payload = self.load_envelope(after_alt, "lane_start")
        if alt_payload["state"] == "ok":
            repo_src = [src for src in alt_payload["sources"] if src["id"] == "repo"][0]
            self.assertNotEqual(repo_src["reason"], None)
        else:
            self.assertIn(
                alt_payload["reason"],
                ("unsafe-path", "repository-mismatch", "unreadable"),
            )
        self.assertNotIn(b"secret-should-not-leak", canonical_bytes(alt_payload))

    def test_d_a30_only_verified_tree_outputs_become_inputs(self):
        extra = {
            "ops/conductor/handoff/HANDOFF-ok.md": b"ok body",
            "ops/conductor/link.md": b"not-a-record",
        }
        self.plant_tree(extra=extra)
        target = self.repo / "ops" / "conductor" / "link.md"
        if target.exists():
            target.unlink()
        try:
            (self.repo / "ops" / "conductor" / "link.md").symlink_to("HANDOFF-ok.md")
        except OSError:
            pass
        else:
            self.git("add", "-f", "--", "ops/conductor/link.md")
            self.git("commit", "-m", "symlink blob\n")
            self.head = self.git("rev-parse", "HEAD").stdout.strip()
        self.plant_v3_config()
        payload = self.detail("lane_handoffs", {"profile": "dev"})
        dumped = canonical_bytes(payload)
        self.assertNotIn(b"not-a-record", dumped)
        bogus = self.query(
            "lane_handoffs",
            {
                "profile": "dev",
                "blob": "a" * 40,
                "path": "ops/conductor/handoff/HANDOFF-ok.md",
            },
        )
        self.assert_refusal(bogus, "arguments")
        missing_law = self.repo / "CONTRIB.md"
        if missing_law.exists():
            self.git("rm", "-f", "--", "CONTRIB.md")
            self.git("commit", "-m", "drop contrib\n")
            self.head = self.git("rev-parse", "HEAD").stdout.strip()
            self.plant_v3_config()
        start = self.start()
        contrib = [row for row in start["data"]["law"] if row["path"] == "CONTRIB.md"][0]
        self.assertIn(contrib["status"], ("missing", "unavailable"))

    def test_d_a31_changed_during_read_is_unavailable(self):
        self.plant_tree()
        first = self.head
        second = self.add_commit({"docs/race.md": b"mutated-ref\n"}, "race")
        self.git("checkout", "--detach", first)
        self.head = first
        self.plant_ref("refs/heads/records/keep", first)
        rec_path = self.store / "job01" / "record.json"
        original = (json.dumps({"id": "job01", "status": "closed"}) + "\n").encode()
        mutated = (json.dumps({"id": "job01", "status": "closed", "n": 1}) + "\n").encode()
        self._plant_bytes(rec_path, original)
        self.assertEqual(rec_path.read_bytes(), original)
        self.plant_v3_config(
            job_ids=["job01"],
            source_ids=["repo", "retained", "dispatch/job01"],
            retained_refs="refs/heads/records/",
        )
        self.ensure_boot()

        events: list[dict] = []
        order: list[str] = []

        def mutate_retained(event):
            closed = self.assert_checkpoint_event(event)
            events.append(dict(closed))
            order.append(f"{closed['phase']}:{closed['source_id']}")
            if (
                closed["phase"] == "before-final-revalidation"
                and closed["source_id"] == "retained"
            ):
                self.git("update-ref", "refs/heads/records/keep", second)
                got = self.git("rev-parse", "refs/heads/records/keep").stdout.strip()
                self.assertEqual(got, second)
                order.append("mutated:retained")

        result = self.call_acquire(checkpoint=mutate_retained)
        self.assertTrue(events, "checkpoint was not reached")
        pairs = [(e["phase"], e["source_id"]) for e in events]
        self.assertEqual(len(pairs), len(set(pairs)), pairs)
        self.assertIn(("before-final-revalidation", "retained"), pairs)
        self.assertIn("mutated:retained", order)
        self.assertLess(
            order.index("before-final-revalidation:retained"),
            order.index("mutated:retained"),
        )
        self.assert_changed_during_read(result)
        self.assertTrue(omitted_check_accepts(events, {"state": "ok", "data": {}}))

        self.git("update-ref", "refs/heads/records/keep", first)
        file_events: list[dict] = []

        def mutate_dispatch(event):
            closed = self.assert_checkpoint_event(event)
            file_events.append(dict(closed))
            if (
                closed["phase"] == "before-file-postcheck"
                and closed["source_id"] == "dispatch/job01"
            ):
                self._plant_bytes(rec_path, mutated)
                self.assertEqual(rec_path.read_bytes(), mutated)
                self.assertNotEqual(mutated, original)

        file_result = self.call_acquire(checkpoint=mutate_dispatch)
        self.assertTrue(
            any(
                e["phase"] == "before-file-postcheck"
                and e["source_id"] == "dispatch/job01"
                for e in file_events
            ),
            file_events,
        )
        self.assert_changed_during_read(file_result)

        self._plant_bytes(rec_path, original)
        self.git("update-ref", "refs/heads/records/keep", first)
        stationary_events: list[dict] = []

        def stationary(event):
            stationary_events.append(self.assert_checkpoint_event(event))

        neighbor = self.call_acquire(checkpoint=stationary)
        self.assertTrue(stationary_events)
        if isinstance(neighbor, dict) and neighbor.get("state") == "unavailable":
            self.assertNotEqual(neighbor.get("reason"), "changed-during-read", neighbor)
        else:
            self.assertIsNotNone(neighbor)

        disabled = self.plant_v3_config(
            job_ids=[],
            source_ids=["repo"],
            retained_refs=None,
        )
        del disabled
        disabled_events: list[dict] = []

        def capture_disabled(event):
            disabled_events.append(self.assert_checkpoint_event(event))

        self.call_acquire(checkpoint=capture_disabled)
        self.assertFalse(
            any(e["source_id"] == "retained" for e in disabled_events),
            disabled_events,
        )
        self.assertTrue(
            any(
                e["phase"] == "before-final-revalidation" and e["source_id"] == "repo"
                for e in disabled_events
            ),
            disabled_events,
        )

        self.reset_repo()
        self.plant_tree()
        self.plant_v3_config(source_ids=["repo"], retained_refs=None)
        self.destroy_head_object()
        self.plant_v3_config(source_ids=["repo"], retained_refs=None)
        failed_events: list[dict] = []

        def capture_failed(event):
            failed_events.append(self.assert_checkpoint_event(event))

        failed = self.call_acquire(checkpoint=capture_failed)
        self.assertFalse(
            any(
                e["phase"] == "before-final-revalidation" and e["source_id"] == "repo"
                for e in failed_events
            ),
            failed_events,
        )
        self.assertIsNotNone(failed)

    def test_d_a36_body_and_frame_caps_do_not_truncate(self):
        inner = b"B" * 2049
        extra = {"ops/conductor/handoff/HANDOFF-big.md": inner}
        self.plant_tree(extra=extra)
        self.plant_v3_config(
            record_bindings=[
                {
                    "record_id": "big",
                    "kind": "handoff",
                    "revision": sha256_hex(inner),
                    "lineage": "dev",
                    "work_paths": ["ops/a.md"],
                    "supersedes": [],
                }
            ]
        )
        named = self.detail(
            "lane_handoffs", {"profile": "dev", "key": record_key(inner)}
        )
        cand = named["data"]["candidate"]
        self.assertIsNone(cand["body"])
        self.assertEqual(cand["body_bytes"], 2049)
        self.assertEqual(cand["reason"], "body-exceeds-cap")
        self.assertEqual(cand["revision"], sha256_hex(inner))
        unicode_inner = ("é" * 1025).encode()
        self.assertGreater(len(unicode_inner), 2048)
        self.add_commit(
            {"ops/conductor/handoff/HANDOFF-uni.md": unicode_inner}, "unicode"
        )
        self.plant_v3_config(
            record_bindings=[
                {
                    "record_id": "uni",
                    "kind": "handoff",
                    "revision": sha256_hex(unicode_inner),
                    "lineage": "dev",
                    "work_paths": ["ops/a.md"],
                    "supersedes": [],
                }
            ]
        )
        uni = self.detail(
            "lane_handoffs",
            {"profile": "dev", "key": record_key(unicode_inner)},
        )
        self.assertIsNone(uni["data"]["candidate"]["body"])
        self.assertEqual(uni["data"]["candidate"]["reason"], "body-exceeds-cap")

    def test_d_a41_read_core_has_no_subprocess_and_leaves_trees_unchanged(self):
        self.assertTrue(READ.is_file(), READ)
        names = self.imported_names(READ)
        self.assertNotIn("subprocess", names)
        self.assertNotIn("Popen", names)
        self.assertNotIn("lane_refs", names)
        for writer in WRITER_MODULES:
            self.assertNotIn(writer, names, writer)
        source = READ.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(READ))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in SUBPROCESS_NAMES:
                self.fail(f"read core uses {node.attr}")
        self.plant_tree()
        self.plant_v3_config()
        before = self.owned_surface()
        before_git = self.git("rev-parse", "HEAD").stdout.strip()
        before_status = self.git("status", "--porcelain").stdout
        self.start()
        after = self.owned_surface()
        self.assertEqual(after, before)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), before_git)
        self.assertEqual(self.git("status", "--porcelain").stdout, before_status)
        cache = list(self.scratch.glob("**/__pycache__")) + list(
            self.scratch.glob("**/*.pyc")
        )
        self.assertEqual(cache, [])
        if REFS.is_file():
            refs_names = self.imported_names(REFS)
            self.assertNotIn("launch", refs_names)
        self.assertTrue(TOOL.is_file())

    def test_d_a42_conductor_descriptor_rejects_overrides_job_bound_is_distinct(self):
        self.plant_tree()
        conductor = self.plant_v3_config()
        job_config = self.work / "job-bound.json"
        self.plant_v3_config(path=job_config, extra_profile={
            "label": "documentation",
            "work_roots": ["docs/"],
            "homes": ["wire", "onboard"],
            "startup_homes": ["wire"],
            "source_ids": ["repo"],
            "lineage": "docs",
        })
        self.assertNotEqual(job_config.read_bytes(), conductor.read_bytes())
        via_job = self.invoke(
            ["query", "lane_start", json.dumps({"profile": "docs"})],
            config=job_config,
        )
        docs = self.load_envelope(via_job, "lane_start")
        self.assertEqual(docs["profile"], "docs")
        via_conductor = self.query("lane_start", {"profile": "docs"})
        self.assert_refusal(via_conductor, "profile")
        for arguments in (
            {"profile": "dev", "config": str(job_config)},
            {"profile": "dev", "audience": "worker"},
            {"profile": "dev", "role": "worker"},
            {"profile": "dev", "repository": str(self.repo)},
            {"profile": "dev", "path": "ops/"},
        ):
            with self.subTest(arguments=arguments):
                proc = self.query("lane_start", arguments, config=conductor)
                self.assert_refusal(proc, "arguments")
                before = self.owned_surface()
                self.assertEqual(self.owned_surface(), before)
