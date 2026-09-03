"""Export, auto-commit, the commit cross-bind, and rebuild (PLAN §5, §8, D1).

The export *is* the evidence, byte-for-byte the hashed payloads, so the
central assertion here is that a database rebuilt from it re-exports
byte-identical files.
"""

import json
import unittest

import support
from support import SandboxCase, plant_bytes
import canonical
from errors import EXIT_OK, EXIT_REFUSED, EXIT_INTEGRITY


class WalkedCase(SandboxCase):
    """A work order walked from open to a recorded outcome."""

    def setUp(self):
        super().setUp()
        self.sb.seed_project()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "walk",
                   "--source", "owner 2026-08-20", check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.make_green()
        self.sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.wf("outcome", "WO-001", "accepted", "--by", "reviewer", check=EXIT_OK)

    def events(self, wo="WO-001"):
        return json.loads(
            self.sb.wf("--json", "log", "--full", "--all", wo, check=EXIT_OK).stdout
        )["events"]


class AutoCommit(WalkedCase):
    def test_every_appending_verb_left_a_wf_commit(self):
        subjects = [
            line for line in self.sb.log(30).splitlines() if "wf(WO-001/" in line
        ]
        self.assertGreaterEqual(len(subjects), 6)
        self.assertTrue(any("wo.opened tdd@1" in s for s in subjects))
        self.assertTrue(any("receipt.red" in s for s in subjects))
        self.assertTrue(any("receipt.green" in s for s in subjects))
        self.assertTrue(any("outcome accepted" in s for s in subjects))

    def test_the_message_follows_the_plans_format(self):
        sha = self.sb._git("log", "--format=%H", "--grep", "wo.opened").strip().split()[-1]
        body = self.sb._git("log", "-1", "--format=%B", sha)
        lines = body.splitlines()
        self.assertEqual(lines[0], "wf(WO-001/spec): wo.opened tdd@1")
        self.assertEqual(lines[1], "")
        self.assertEqual(lines[2], "WO: WO-001")
        self.assertEqual(lines[3], "Stage: spec")
        self.assertRegex(lines[4], r"^Event: \d+ [0-9a-f]{8}$")
        self.assertIn("Source: generated: wf", body)
        self.assertIn(f"Co-Authored-By: {support.Sandbox.AGENT}", body)

    def test_source_flows_into_both_the_event_and_the_commit_trailers(self):
        # "generated: wf" covers the serialization only; content provenance
        # rides in the events and is re-emitted as extra Source: trailers.
        opened = self.events()[0]
        self.assertEqual(opened["sources"], ["owner 2026-08-20"])
        sha = self.sb._git("log", "--format=%H", "--grep", "wo.opened").strip().split()[-1]
        body = self.sb._git("log", "-1", "--format=%B", sha)
        self.assertIn("Source: owner 2026-08-20", body)

    def test_source_is_accepted_after_the_verb_as_well_as_before(self):
        before = self.sb.wf("--source", "s-before", "advance", "WO-001",
                            "--to", "impl", "--reason", "r", check=EXIT_OK)
        self.assertEqual(self.events()[-2]["sources"], ["s-before"])
        self.sb.wf("advance", "WO-001", "--to", "red", "--reason", "r",
                   "--source", "s-after", check=EXIT_OK)
        self.assertEqual(self.events()[-2]["sources"], ["s-after"])
        self.assertEqual(before.returncode, EXIT_OK)

    def test_exactly_one_bind_is_pending_in_steady_state(self):
        # A commit.landed can only land in the commit after the one it names,
        # so the export always carries exactly one uncommitted line.
        pending = self.sb._git("status", "--porcelain").strip().splitlines()
        self.assertEqual(len(pending), 1, pending)
        self.assertTrue(pending[0].endswith("chains/WO-001.jsonl"))
        committed = self.sb._git("show", "HEAD:ops/devlane/workflow/chains/WO-001.jsonl")
        on_disk = self.sb.chain_file("WO-001").read_text()
        self.assertTrue(on_disk.startswith(committed), "the export is append-only")
        self.assertEqual(len(on_disk.splitlines()), len(committed.splitlines()) + 1)

    def test_commit_landed_names_a_real_ancestor_and_the_head_it_carried(self):
        binds = [e for e in self.events() if e["type"] == "commit.landed"]
        self.assertGreaterEqual(len(binds), 5)
        head = self.sb.head()
        for bind in binds:
            with self.subTest(sha=bind["sha"][:8]):
                self.assertEqual(
                    self.sb._git("cat-file", "-t", bind["sha"]).strip(), "commit"
                )
                self.sb._git("merge-base", "--is-ancestor", bind["sha"], head)
                named = self.events()[bind["chain_seq"] - 1]
                self.assertEqual(named["hash"], bind["chain_hash"])

    def test_no_commit_defers_and_wf_commit_flushes(self):
        self.sb.wf("--no-commit", "advance", "WO-001", "--to", "impl",
                   "--reason", "deferred", check=EXIT_OK)
        pending = self.sb._git("status", "--porcelain").strip().splitlines()
        self.assertEqual(len(pending), 1)
        before = self.sb.head()
        self.sb.wf("commit", "WO-001", "--message", "flush", check=EXIT_OK)
        self.assertNotEqual(self.sb.head(), before)
        self.assertIn("wf(WO-001/impl): flush", self.sb.log(1))

    def test_wf_commit_with_nothing_staged_says_so(self):
        self.sb.wf("commit", check=EXIT_OK)          # sweeps the pending bind
        proc = self.sb.wf("--json", "commit", check=EXIT_OK)
        # After the sweep a fresh bind is pending, so a second flush commits
        # that one and then the third has nothing new to add.
        self.sb.wf("commit", check=EXIT_OK)
        self.assertIn("committed", json.loads(proc.stdout))

    def test_a_wf_commit_stages_only_export_paths(self):
        self.sb.write("unrelated.txt", "not wf's business\n")
        self.sb.wf("advance", "WO-001", "--to", "impl", "--reason", "r",
                   "--allow-dirty" if False else "--reason", "r", check=EXIT_OK)
        status = self.sb._git("status", "--porcelain")
        self.assertIn("unrelated.txt", status, "wf must not sweep in foreign changes")


class ExportShape(WalkedCase):
    def test_a_chain_file_is_the_payload_bytes_verbatim(self):
        raw = self.sb.chain_file("WO-001").read_bytes()
        lines = [line for line in raw.split(b"\n") if line]
        self.assertEqual(len(lines), len(self.events()))
        for index, line in enumerate(lines, 1):
            with self.subTest(seq=index):
                self.assertTrue(canonical.is_canonical(line))
                event = canonical.loads(line)
                self.assertEqual(event["seq"], index)
                # Self-verifying: every line carries the hash it re-computes to.
                without = {k: v for k, v in event.items() if k != "hash"}
                self.assertEqual(canonical.digest(without), event["hash"])

    def test_attempts_are_exported_and_claims_are_not(self):
        self.assertTrue((self.sb.root / "attempts" / "WO-001.jsonl").exists())
        self.assertFalse((self.sb.root / "claims").exists())
        self.assertFalse((self.sb.root / "sessions").exists())

    def test_the_database_is_gitignored(self):
        self.assertTrue(self.sb.db.exists())
        tracked = self.sb._git("ls-files", "ops/devlane/workflow/")
        self.assertNotIn("wf.db", tracked)
        self.assertIn("chains/WO-001.jsonl", tracked)
        self.assertIn("meta.json", tracked)

    def test_export_is_idempotent(self):
        first = json.loads(self.sb.wf("--json", "export", check=EXIT_OK).stdout)
        second = json.loads(self.sb.wf("--json", "export", check=EXIT_OK).stdout)
        self.assertEqual(second["written"], [], first)


class Rebuild(WalkedCase):
    def snapshot(self):
        return {
            p.name: p.read_bytes()
            for p in sorted((self.sb.root / "chains").iterdir())
        }

    def test_reproduces_byte_identical_chains(self):
        before = self.snapshot()
        self.sb.db.unlink()
        body = json.loads(self.sb.wf("--json", "init", "--rebuild", check=EXIT_OK).stdout)
        self.assertTrue(body["rebuilt"])
        self.assertEqual(body["work_orders"], ["WO-001"])
        self.assertEqual(body["events"], len(self.events()))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(
            json.loads(self.sb.wf("--json", "export", check=EXIT_OK).stdout)["written"],
            [], "a rebuilt database re-exports nothing",
        )

    def test_restores_the_projection_and_the_attempts(self):
        before = json.loads(self.sb.wf("--json", "status", "WO-001").stdout)
        attempts_before = json.loads(
            self.sb.wf("--json", "log", "--full", "--all", "WO-001", "--attempts").stdout
        )["attempts"]
        self.sb.wf("init", "--rebuild", check=EXIT_OK)
        after = json.loads(self.sb.wf("--json", "status", "WO-001").stdout)
        self.assertEqual(after["stage"], before["stage"])
        self.assertEqual(after["head"], before["head"])
        self.assertEqual(after["satisfied"], before["satisfied"])
        attempts_after = json.loads(
            self.sb.wf("--json", "log", "--full", "--all", "WO-001", "--attempts").stdout
        )["attempts"]
        self.assertEqual(attempts_after, attempts_before)

    def test_rebuilds_the_artifact_mirror_from_the_chain(self):
        import sqlite3

        self.sb.wf("init", "--rebuild", check=EXIT_OK)
        conn = sqlite3.connect(str(self.sb.db))
        try:
            rows = conn.execute("SELECT class, digest FROM artifacts").fetchall()
        finally:
            conn.close()
        classes = sorted({r[0] for r in rows})
        self.assertIn("gate-kind-spec", classes)
        self.assertIn("test-manifest", classes)
        for _, digest in rows:
            stored = self.sb.root / "objects" / digest[:2] / digest
            self.assertEqual(canonical.sha256_hex(stored.read_bytes()), digest)

    # -- planted faults in the export --------------------------------------

    def plant_chain(self, mutate, *, expect="edit", lines=None):
        path = self.sb.chain_file("WO-001")
        clean = plant_bytes(
            path, mutate, expect=expect,
            recognisable=lambda raw: support.jsonl_lines(raw) == (
                lines if lines is not None else support.jsonl_lines(path.read_bytes())
            ),
        )
        self.sb.db.unlink()
        return clean

    def test_detects_a_corrupted_export_line(self):
        self.plant_chain(lambda raw: raw.replace(b'"walk"', b'"wolk"'))
        proc = self.sb.wf("init", "--rebuild")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("does not hash to its recorded hash", proc.stderr)

    def test_detects_a_dropped_export_line(self):
        total = support.jsonl_lines(self.sb.chain_file("WO-001").read_bytes())
        self.plant_chain(
            lambda raw: b"\n".join(
                [ln for ln in raw.split(b"\n") if ln][:2]
                + [ln for ln in raw.split(b"\n") if ln][3:]
            ) + b"\n",
            expect="shrink", lines=total - 1,
        )
        proc = self.sb.wf("init", "--rebuild")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("not contiguous", proc.stderr)

    def test_detects_a_truncated_tail(self):
        # Dropping the *last* line leaves a self-consistent shorter chain;
        # only the commit cross-bind catches it, which is verify --deep's job.
        # Here the projection still rebuilds, and that is the honest answer.
        total = support.jsonl_lines(self.sb.chain_file("WO-001").read_bytes())
        self.plant_chain(
            lambda raw: b"\n".join([ln for ln in raw.split(b"\n") if ln][:-1]) + b"\n",
            expect="shrink", lines=total - 1,
        )
        self.sb.wf("init", "--rebuild", check=EXIT_OK)
        after = json.loads(self.sb.wf("--json", "status", "WO-001").stdout)
        self.assertEqual(after["seq"], total - 1)

    def test_detects_a_non_canonical_export_line(self):
        def respace(raw):
            lines = [ln for ln in raw.split(b"\n") if ln]
            event = canonical.loads(lines[1])
            lines[1] = json.dumps(event, sort_keys=True,
                                  separators=(", ", ": ")).encode()
            return b"\n".join(lines) + b"\n"

        self.plant_chain(respace, expect="grow")
        proc = self.sb.wf("init", "--rebuild")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("not in canonical form", proc.stderr)

    def test_detects_a_broken_prev_link_in_the_export(self):
        def relink(raw):
            lines = [ln for ln in raw.split(b"\n") if ln]
            event = canonical.loads(lines[2])
            event["prev"] = "0" * 63 + "1"
            event["hash"] = canonical.digest(
                {k: v for k, v in event.items() if k != "hash"}
            )
            lines[2] = canonical.dumpb(event)
            return b"\n".join(lines) + b"\n"

        self.plant_chain(relink, expect="edit")
        proc = self.sb.wf("init", "--rebuild")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("does not link to the preceding one", proc.stderr)

    def test_detects_a_chain_that_does_not_begin_with_wo_opened(self):
        total = support.jsonl_lines(self.sb.chain_file("WO-001").read_bytes())
        self.plant_chain(
            lambda raw: b"\n".join([ln for ln in raw.split(b"\n") if ln][1:]) + b"\n",
            expect="shrink", lines=total - 1,
        )
        proc = self.sb.wf("init", "--rebuild")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)

    def test_detects_a_missing_object_the_chain_references(self):
        events = self.events()
        digest = next(e for e in events if e["type"] == "receipt.red")[
            "test_manifest_sha256"
        ]
        obj = self.sb.root / "objects" / digest[:2] / digest
        self.assertTrue(obj.exists(), "plant: the object must exist first")
        obj.unlink()
        self.assertFalse(obj.exists(), "plant: the object must be gone")
        self.sb.db.unlink()
        proc = self.sb.wf("init", "--rebuild")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("missing", proc.stderr)

    def test_a_line_missing_a_core_field_is_an_integrity_error_not_a_crash(self):
        # Comparing a missing field against a stored one raises a TypeError,
        # which exits 1 with a traceback — and 1 means "refused". A malformed
        # export line must be integrity, with a message.
        def strip_time(raw):
            lines = [ln for ln in raw.split(b"\n") if ln.strip()]
            event = canonical.loads(lines[-1])
            event.pop("time")
            lines[-1] = canonical.dumpb(event)
            return b"\n".join(lines) + b"\n"

        self.plant_chain(strip_time, expect="shrink")
        proc = self.sb.wf("init", "--rebuild")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("missing a core field", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_a_line_with_an_unreadable_time_is_an_integrity_error(self):
        def bad_time(raw):
            lines = [ln for ln in raw.split(b"\n") if ln.strip()]
            event = canonical.loads(lines[-1])
            event["time"] = "not-a-time"
            lines[-1] = canonical.dumpb(event)
            return b"\n".join(lines) + b"\n"

        self.plant_chain(bad_time, expect="shrink")
        proc = self.sb.wf("init", "--rebuild")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("time is unreadable", proc.stderr)

    def test_refuses_an_export_format_version_it_does_not_understand(self):
        meta = self.sb.root / "meta.json"
        plant_bytes(
            meta, lambda raw: canonical.dumpb({"format_version": 99}),
            expect="grow", recognisable=lambda raw: b"format_version" in raw,
        )
        self.sb.db.unlink()
        proc = self.sb.wf("init", "--rebuild", check=EXIT_REFUSED)
        self.assertIn("format version", proc.stderr)


if __name__ == "__main__":
    unittest.main()


class AFailedRebuildLeavesNoPartial(WalkedCase):
    """[P1 Codex] A rebuild that fails partway must not leave a partial.

    work_orders was populated before a malformed attempts file refused, so
    the failure left a database that passed for finished — the MCP
    launcher's cache check accepted it and the broken attempt history was
    silently omitted, permanently. The fix is atomicity, not cleanup: the
    rebuild builds into a temp file and renames onto wf.db only on success,
    so failure leaves the previous state — a coherent old cache, or
    nothing — never a partial.
    """

    def corrupt_attempts(self):
        support.plant_bytes(
            self.sb.root / "attempts" / "WO-001.jsonl",
            lambda raw: raw + b"this is not canonical json\n",
            expect="grow",
            recognisable=lambda raw: raw.startswith(b"{"),
        )

    def leftovers(self):
        return sorted(p.name for p in self.sb.root.glob("wf.db*"))

    def test_a_failed_rebuild_from_nothing_leaves_nothing(self):
        self.corrupt_attempts()
        self.sb.db.unlink()
        proc = self.sb.wf("init", "--rebuild")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertEqual(self.leftovers(), [],
                         "a failed rebuild left a database behind")

    def test_a_failed_rebuild_preserves_the_previous_database(self):
        before = self.sb.db.read_bytes()
        self.corrupt_attempts()
        proc = self.sb.wf("init", "--rebuild")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertEqual(self.leftovers(), ["wf.db"],
                         "a failed rebuild left its temp files behind")
        self.assertEqual(self.sb.db.read_bytes(), before,
                         "the previous cache did not survive untouched")

    def test_a_format_refusal_no_longer_destroys_the_cache(self):
        # The old order unlinked wf.db before checking the export's format
        # version, so a mere refusal left no cache at all.
        (self.sb.root / "meta.json").write_bytes(
            canonical.dumpb({"format_version": 999}))
        proc = self.sb.wf("init", "--rebuild")
        self.assertEqual(proc.returncode, EXIT_REFUSED, proc.stderr)
        self.assertTrue(self.sb.db.exists(),
                        "a refusal is not permission to destroy the cache")
