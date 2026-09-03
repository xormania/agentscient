"""verify and verify --deep — the checks that need the repository (PLAN §7).

Each planted fault proves it landed before the assertion runs, and each
check is only credited here if removing it would make one of these tests
fail — a verifier proven on clean data alone converts "nobody looked" into
"we checked", which is worse than having none.
"""

import json
import unittest

import support
from support import SandboxCase, plant_bytes, plant_sql
import canonical
from errors import EXIT_OK, EXIT_REFUSED, EXIT_INTEGRITY


class VerifyCase(SandboxCase):
    def setUp(self):
        super().setUp()
        self.sb.seed_project()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "verify",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.make_green()
        self.sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=EXIT_OK)

    def verify(self, *extra, check=EXIT_OK):
        return self.sb.wf("--json", "verify", *extra, check=check)

    def deep(self, check=EXIT_OK):
        return self.verify("--deep", check=check)

    def chain(self):
        return self.sb.chain_file("WO-001")

    def events(self):
        return json.loads(
            self.sb.wf("--json", "log", "--full", "--all", "WO-001", check=EXIT_OK).stdout
        )["events"]


class Clean(VerifyCase):
    def test_a_clean_tree_verifies_shallow_and_deep(self):
        shallow = json.loads(self.verify().stdout)
        self.assertFalse(shallow["deep"])
        self.assertEqual(len(shallow["work_orders"]), 1)
        self.assertGreater(shallow["objects"], 0)

        deep = json.loads(self.deep().stdout)
        entry = deep["work_orders"][0]
        self.assertEqual(entry["receipts"]["checked"], 2, "one red and one green")
        self.assertEqual(entry["receipts"]["skipped_dirty"], 0)
        self.assertGreater(entry["cross_binds"]["bound"], 0)
        self.assertGreater(entry["append_only"]["versions"], 0)

    def test_reports_exactly_one_pending_bind(self):
        # PLAN §5's steady state, measured rather than asserted from memory.
        entry = json.loads(self.deep().stdout)["work_orders"][0]
        self.assertEqual(entry["unbound_tip"]["pending_events"], 1)
        self.assertEqual(
            self.sb._git("cat-file", "-t",
                         entry["unbound_tip"]["last_bound_commit"]).strip(),
            "commit",
        )

    def test_a_dirty_receipt_is_reported_as_unverifiable_not_as_a_pass(self):
        # D3's trade-off, stated: a tree_dirty receipt can only be checked
        # against its own output hashes, so deep verification counts it as
        # skipped rather than quietly calling it verified.
        self.sb.wf("advance", "WO-001", "--to", "red", "--reason", "again",
                   check=EXIT_OK)
        self.sb.make_red()
        self.sb.write("scratch.txt", "uncommitted\n")
        self.sb.wf("red", "WO-001", "--allow-dirty", "--",
                   *support.Sandbox.GATE_ARGV, check=EXIT_OK)
        entry = json.loads(self.deep().stdout)["work_orders"][0]
        self.assertEqual(entry["receipts"]["skipped_dirty"], 1)


class ExportCurrency(VerifyCase):
    def test_an_export_behind_the_chain_refuses_rather_than_blocks(self):
        # Recoverable by running wf export, so it is a refusal, not evidence
        # corruption.
        self.sb.wf("--no-commit", "advance", "WO-001", "--to", "red",
                   "--reason", "deferred", check=EXIT_OK)
        # The deferred verb wrote the chain but never exported it.
        proc = self.verify(check=EXIT_REFUSED)
        self.assertIn("the export is current", proc.stderr)
        self.sb.wf("export", check=EXIT_OK)
        self.verify(check=EXIT_OK)

    def test_a_divergent_export_is_an_integrity_failure(self):
        plant_bytes(
            self.chain(),
            lambda raw: raw.replace(b'"verify"', b'"verifz"'),
            expect="edit",
            recognisable=lambda raw: support.jsonl_lines(raw) > 3,
        )
        proc = self.verify(check=EXIT_INTEGRITY)
        self.assertIn("diverges from the recorded payload bytes", proc.stderr)


class VacuousPass(VerifyCase):
    """A verifier that reports success because it found nothing to check."""

    def test_an_empty_database_beside_a_populated_export_is_an_integrity_failure(self):
        # A rebuild that failed part-way used to leave a database that
        # verified perfectly — "0 work orders, ok" — over an export full of
        # evidence it never read.
        self.assertTrue(self.sb.chain_file("WO-001").exists())
        self.sb.db.unlink()
        self.sb.wf("init", check=EXIT_OK)      # fresh, empty, migrated
        proc = self.verify(check=EXIT_INTEGRITY)
        self.assertIn("missing a work order the export records", proc.stderr)

    def test_a_failed_rebuild_does_not_leave_a_passing_verifier_behind(self):
        total = support.jsonl_lines(self.sb.chain_file("WO-001").read_bytes())
        plant_bytes(
            self.sb.chain_file("WO-001"),
            lambda raw: b"\n".join(
                [ln for ln in raw.split(b"\n") if ln.strip()][:1]
                + [ln for ln in raw.split(b"\n") if ln.strip()][2:]
            ) + b"\n",
            expect="shrink",
            recognisable=lambda raw: support.jsonl_lines(raw) == total - 1,
        )
        self.sb.db.unlink()
        rebuild = self.sb.wf("init", "--rebuild")
        self.assertEqual(rebuild.returncode, EXIT_INTEGRITY, rebuild.stderr)
        self.assertIn("not contiguous", rebuild.stderr)
        after = self.verify(check=EXIT_INTEGRITY)
        self.assertIn("missing a work order the export records", after.stderr)


class Deletion(VerifyCase):
    """Deleting the record must not also delete the check that notices."""

    def test_deleting_a_chain_file_is_an_integrity_failure(self):
        path = self.sb.chain_file("WO-001")
        self.assertTrue(path.exists(), "plant: the chain file must exist first")
        rel = "ops/devlane/workflow/chains/WO-001.jsonl"
        # -f because the pending bind leaves the file modified; the point is
        # to delete the tracked record, not to test git's safety net.
        self.sb._git("rm", "-f", "-q", rel)
        self.sb._git("commit", "-qm", "sandbox: delete the record")
        self.assertFalse(path.exists(), "plant: the file must be gone")
        self.sb.db.unlink()
        self.sb.wf("init", "--rebuild", check=EXIT_OK)

        # Nothing imports, so no work order exists and every per-work-order
        # check has nothing to say. Only history remembers the file was there.
        shallow = self.sb.wf("verify")
        self.assertEqual(shallow.returncode, EXIT_OK,
                         "the shallow pass genuinely has nothing to check")
        proc = self.deep(check=EXIT_INTEGRITY)
        self.assertIn("recorded in history is gone", proc.stderr)

    def test_emptying_a_chain_file_is_an_integrity_failure(self):
        path = self.sb.chain_file("WO-001")
        before = path.read_bytes()
        self.assertGreater(len(before), 0, "plant: the fixture must be non-empty")
        path.write_bytes(b"")
        self.assertEqual(path.read_bytes(), b"", "plant: the file must be empty")
        self.sb.commit_all("sandbox: empty the record")
        self.sb.db.unlink()
        self.sb.wf("init", "--rebuild", check=EXIT_OK)
        # An empty file imports nothing, so the export/database completeness
        # check reaches it before the prefix walk does. Both are integrity;
        # this is the one that actually fires, so this is what is asserted.
        proc = self.verify(check=EXIT_INTEGRITY)
        self.assertIn("missing a work order the export records", proc.stderr)
        self.assertIn("holds 0 event(s)", proc.stderr)


class ShallowClone(VerifyCase):
    def test_deep_refuses_a_shallow_clone_rather_than_passing_it(self):
        # With history truncated the prefix walk sees one version of each file
        # and would call a rewritten chain append-only. The check did not run,
        # so it must not report a pass.
        clone = self.sb.dir.parent / (self.sb.dir.name + "-shallow")
        self.sb._git("clone", "-q", "--depth", "1", "file://" + str(self.sb.dir),
                     str(clone))
        try:
            import subprocess
            import sys as _sys

            root = clone / "ops" / "devlane" / "workflow"
            self.assertEqual(
                subprocess.run(["git", "-C", str(clone), "rev-parse",
                                "--is-shallow-repository"],
                               capture_output=True, text=True).stdout.strip(),
                "true", "fixture: the clone must actually be shallow",
            )
            env = dict(__import__("os").environ, WF_AGENT="test-agent")
            base = [_sys.executable, str(support.WF_PY), "--root", str(root)]
            subprocess.run(base + ["init", "--rebuild"], cwd=str(clone), env=env,
                           capture_output=True, text=True, check=True)
            proc = subprocess.run(base + ["verify", "--deep"], cwd=str(clone),
                                  env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, EXIT_REFUSED, proc.stderr)
            self.assertIn("full history", proc.stderr)
            shallow_ok = subprocess.run(base + ["verify"], cwd=str(clone), env=env,
                                        capture_output=True, text=True)
            self.assertEqual(shallow_ok.returncode, EXIT_OK, shallow_ok.stderr)
        finally:
            import shutil

            shutil.rmtree(clone, ignore_errors=True)


class MetaVersion(VerifyCase):
    def test_rebuild_refuses_to_mint_the_meta_it_would_then_accept(self):
        # Otherwise a change that deletes meta.json rebuilds green, because
        # the format check is reading a file the same command just wrote.
        meta = self.sb.root / "meta.json"
        self.assertTrue(meta.exists(), "plant: meta.json must exist first")
        meta.unlink()
        self.assertFalse(meta.exists(), "plant: meta.json must be gone")
        self.sb.db.unlink()
        proc = self.sb.wf("init", "--rebuild", check=EXIT_REFUSED)
        self.assertIn("declares its format version", proc.stderr)
        self.assertFalse(meta.exists(), "a refusal must not have written it")


class Registry(VerifyCase):
    def test_detects_a_registered_version_edited_in_place(self):
        # PLAN §6: new versions are new entries; old ones are never edited.
        plant_bytes(
            self.sb.root / "gate-kinds" / "tdd.json",
            lambda raw: raw.replace(
                b'"leave_requires": ["receipt.red"]', b'"leave_requires": []'
            ),
            expect="shrink",
            recognisable=lambda raw: canonical.loads(raw).get("kind") == "tdd",
        )
        self.sb.commit_all("sandbox: edit tdd@1 in place")
        self.sb.wf("init", check=EXIT_OK)
        proc = self.verify(check=EXIT_INTEGRITY)
        self.assertIn("edited in place", proc.stderr)
        self.assertIn("register a new version", proc.stderr)

    def test_refuses_when_the_database_has_not_been_synced(self):
        plant_sql(
            self.sb.db,
            "UPDATE gate_kinds SET spec_sha256 = ? WHERE kind='tdd'",
            ("f" * 64,),
            check=lambda c: c.execute("SELECT COUNT(*) FROM gate_kinds").fetchone()[0] == 2,
        )
        proc = self.verify(check=EXIT_REFUSED)
        self.assertIn("mirrors the registry", proc.stderr)


class Uncommitted(SandboxCase):
    """A walk recorded with --no-commit, exported once, committed once.

    With no commit.landed events in the chain, the deep pass has nothing to
    cross-bind, which is what isolates the *receipt* checks below: a failure
    there can only have come from re-hashing a manifest.
    """

    def setUp(self):
        super().setUp()
        self.sb.seed_project()
        self.sb.wf("init", check=EXIT_OK)
        for argv in (
            ["open", "WO-001", "--kind", "tdd", "--objective", "verify"],
            ["advance", "WO-001"],
            ["red", "WO-001", "--", *support.Sandbox.GATE_ARGV],
            ["advance", "WO-001"],
        ):
            self.sb.wf("--no-commit", *argv, check=EXIT_OK)
        self.sb.make_green()
        self.sb.wf("--no-commit", "green", "WO-001", "--",
                   *support.Sandbox.GATE_ARGV, check=EXIT_OK)
        self.sb.wf("export", check=EXIT_OK)
        self.sb.commit_all("sandbox: land the export")

    def events(self):
        return json.loads(
            self.sb.wf("--json", "log", "--full", "--all", "WO-001", check=EXIT_OK).stdout
        )["events"]

    def land(self, forged, expected_lines):
        payload = support.chain_bytes_for(forged)
        current = self.sb.chain_file("WO-001").read_bytes()
        plant_bytes(
            self.sb.chain_file("WO-001"),
            lambda raw: payload,
            expect="edit" if len(payload) == len(current)
                   else ("grow" if len(payload) > len(current) else "shrink"),
            recognisable=lambda raw: support.jsonl_lines(raw) == expected_lines,
        )
        self.sb.commit_all("sandbox: land the forged chain")
        self.sb.db.unlink()
        self.sb.wf("init", "--rebuild", check=EXIT_OK)

    def forge(self, mutate):
        """Rewrite one event, re-link the whole chain, and rebuild from it."""
        events = self.events()
        self.assertEqual([e for e in events if e["type"] == "commit.landed"], [],
                         "fixture: this walk must carry no binds")
        forged = support.relink_chain("WO-001", [mutate(dict(e)) for e in events])
        self.land(forged, len(events))

    def test_the_fixture_verifies_before_anything_is_forged(self):
        # Without this, a later "deep verify failed" proves nothing about the
        # forgery — the fixture might never have been sound to begin with.
        self.sb.wf("verify", check=EXIT_OK)
        self.sb.wf("verify", "--deep", check=EXIT_OK)

    def test_a_forged_chain_still_passes_every_per_row_check(self):
        # The premise of the tests below: re-linking really does restore
        # internal consistency, so what catches a forgery is the
        # repository-side check and nothing else.
        self.forge(lambda e: {**e, "objective": "forged"}
                   if e["type"] == "wo.opened" else e)
        self.sb.wf("verify", check=EXIT_OK)

    def test_detects_a_red_manifest_that_does_not_re_hash_from_its_tree(self):
        # Forged to another digest that *is* in the object store, so the CAS
        # check cannot fire first: what catches this can only be the re-hash.
        red = next(e for e in self.events() if e["type"] == "receipt.red")
        decoy = red["stdout_sha256"]
        self.assertNotEqual(decoy, red["test_manifest_sha256"])
        self.forge(lambda e: {**e, "test_manifest_sha256": decoy}
                   if e["type"] == "receipt.red" else e)
        self.sb.wf("verify", check=EXIT_OK)      # every per-row check passes
        proc = self.sb.wf("verify", "--deep")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("does not re-hash from the tree it names", proc.stderr)

    def test_detects_a_green_claiming_a_seal_the_chain_never_recorded(self):
        # A green receipt reporting its own frozen digest proves nothing; the
        # seal in stage.entered is what the chain actually recorded.
        self.forge(lambda e: {**e, "frozen_manifest_sha256": "c" * 64}
                   if e["type"] == "receipt.green" else e)
        self.sb.wf("verify", check=EXIT_OK)
        proc = self.sb.wf("verify", "--deep")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("never sealed for its stage", proc.stderr)

    def test_detects_a_green_whose_sealed_set_does_not_match_the_tree(self):
        # The other branch: seal and receipt agree with each other, and both
        # are wrong about the tree. Forging them together is what gets past
        # the check above and onto the re-hash.
        def mutate(event):
            if event["type"] == "stage.entered" and (event.get("frozen") or {}):
                frozen = dict(event["frozen"])
                frozen["manifest_sha256"] = "d" * 64
                return {**event, "frozen": frozen}
            if event["type"] == "receipt.green":
                return {**event, "frozen_manifest_sha256": "d" * 64}
            return event

        self.forge(mutate)
        self.sb.wf("verify", check=EXIT_OK)
        proc = self.sb.wf("verify", "--deep")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("not verified against its frozen set", proc.stderr)

    def test_detects_a_receipt_naming_a_commit_the_repository_lost(self):
        self.forge(lambda e: {**e, "head_sha": "b" * 40}
                   if e["type"] == "receipt.red" else e)
        self.sb.wf("verify", check=EXIT_OK)
        proc = self.sb.wf("verify", "--deep")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("no longer has", proc.stderr)

    def test_detects_a_bind_naming_a_commit_that_is_not_in_the_repository(self):
        events = self.events()
        bind = {
            "type": "commit.landed", "sha": "b" * 40,
            "chain_seq": len(events), "chain_hash": events[-1]["hash"],
            "time": events[-1]["time"], "agent": "test-agent",
        }
        self.land(support.relink_chain("WO-001", events + [bind]), len(events) + 1)
        self.sb.wf("verify", check=EXIT_OK)
        proc = self.sb.wf("verify", "--deep")
        self.assertEqual(proc.returncode, EXIT_INTEGRITY, proc.stderr)
        self.assertIn("not in this repository", proc.stderr)


class DeepAppendOnly(VerifyCase):
    """The prefix walk — the only check that sees a dropped tail."""

    def test_detects_a_chain_file_rewritten_rather_than_appended_to(self):
        # Drop the last committed line and commit that. Every remaining line
        # still hashes and links, the projection still verifies, and no
        # per-row check can see it: the file is simply shorter than it was.
        committed = self.sb._git(
            "show", "HEAD:ops/devlane/workflow/chains/WO-001.jsonl"
        )
        total = len([ln for ln in committed.splitlines() if ln.strip()])
        plant_bytes(
            self.chain(),
            lambda raw: b"\n".join(
                [ln for ln in raw.split(b"\n") if ln.strip()][: total - 1]
            ) + b"\n",
            expect="shrink",
            recognisable=lambda raw: support.jsonl_lines(raw) == total - 1,
        )
        self.sb.commit_all("sandbox: truncate the chain")
        self.sb.db.unlink()
        self.sb.wf("init", "--rebuild", check=EXIT_OK)

        # The rebuilt database is internally consistent: a shallow verify
        # passes, which is exactly why the prefix walk has to exist.
        self.verify(check=EXIT_OK)
        proc = self.deep(check=EXIT_INTEGRITY)
        self.assertIn("rewritten rather than appended", proc.stderr)

    def test_detects_a_working_tree_file_that_is_not_an_extension(self):
        committed = self.sb._git(
            "show", "HEAD:ops/devlane/workflow/chains/WO-001.jsonl"
        ).encode()
        plant_bytes(
            self.chain(),
            lambda raw: raw.replace(b'"verify"', b'"verifz"'),
            expect="edit",
            recognisable=lambda raw: support.jsonl_lines(raw) > 3,
        )
        self.assertNotEqual(self.chain().read_bytes()[: len(committed)], committed)
        # The shallow export check reports it first; --deep would too.
        proc = self.verify(check=EXIT_INTEGRITY)
        self.assertIn("diverges", proc.stderr)


class DeepObjects(VerifyCase):
    def test_detects_a_missing_object(self):
        red = next(e for e in self.events() if e["type"] == "receipt.red")
        digest = red["stdout_sha256"]
        obj = self.sb.root / "objects" / digest[:2] / digest
        self.assertTrue(obj.exists(), "plant: the object must exist first")
        obj.unlink()
        self.assertFalse(obj.exists(), "plant: the object must be gone")
        proc = self.verify(check=EXIT_INTEGRITY)
        self.assertIn("missing", proc.stderr)

    def test_detects_an_object_that_does_not_hash_to_its_own_name(self):
        red = next(e for e in self.events() if e["type"] == "receipt.red")
        digest = red["test_manifest_sha256"]
        obj = self.sb.root / "objects" / digest[:2] / digest
        plant_bytes(
            obj, lambda raw: raw + b" ", expect="grow",
            recognisable=lambda raw: raw.strip().startswith(b"["),
        )
        proc = self.verify(check=EXIT_INTEGRITY)
        self.assertIn("does not hash to its own name", proc.stderr)


if __name__ == "__main__":
    unittest.main()
