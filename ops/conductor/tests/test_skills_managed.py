"""Managed skill transport; owner 2026-09-19, same framework on four harnesses.

Grant 311, dev-lane hand variant: second test producer absent. Reuses World
and run; all stores, source mutations and symlinks belong to the planted world.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from ops.testkit import World, run

SOURCE = Path(__file__).resolve().parents[1] / "tools"
AGENT = "Managed Skill Tester <tester@example.invalid>"


class ManagedSkills(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="managed-skills-")
        self.addCleanup(self.world.close)
        self.repo = self.world.cwd
        self.tools = self.repo / "ops/conductor/tools"
        for name in ("skills.py", "instrument.py", "laneconf.py"):
            self.world.plant_bytes(self.tools / name, (SOURCE / name).read_bytes())
        self.world.plant_text(self.repo / "ops/lane.conf", "LANE_NAME='skills-test'\n")
        self.skill_root = self.repo / ".claude/skills"
        self.body = "---\nname: sample\ndescription: A measured sample\n---\n\nRun the sample procedure.\n"
        self.page = self.world.plant_text(self.skill_root / "sample/SKILL.md", self.body)
        self.db = self.world.xdg_state / "skills-test/skills.db"

    def call(self, *args, identity=True, extra=None):
        env = {"CODEX_THREAD_ID": "fixture-session", **(extra or {})}
        if identity:
            env["WF_AGENT_OVERRIDE"] = AGENT
        return run([sys.executable, str(self.tools / "skills.py"), *args],
                   cwd=self.repo, env=self.world.env(env), timeout=20)

    def sync(self):
        result = self.call("sync")
        self.assertEqual(result.exit, 0, result.stdout + result.stderr)

    def events(self):
        with sqlite3.connect(self.db) as con:
            return con.execute("SELECT skill,event,agent,session,detail FROM skill_events ORDER BY id").fetchall()

    def event_sources(self):
        with sqlite3.connect(self.db) as con:
            return con.execute("SELECT source_path,source_sha256 FROM skill_events ORDER BY id").fetchall()

    def loaded_module(self):
        saved = sys.modules.pop("instrument", None)
        try:
            spec = importlib.util.spec_from_file_location("managed_skills_subject", self.tools / "skills.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        finally:
            sys.modules.pop("instrument", None)
            if saved is not None:
                sys.modules["instrument"] = saved

    def rejected(self, result, kind):
        self.assertEqual(result.exit, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.startswith(kind + ": expected "), result.stderr)
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)

    def test_fresh_catalogue_and_read_do_not_create_registry(self):
        result = self.call("catalog", identity=False)
        self.assertEqual(result.exit, 0, result.stderr)
        self.assertEqual([row["name"] for row in json.loads(result.stdout)], ["sample"])
        result = self.call("read", "sample", identity=False)
        self.assertEqual(result.exit, 0, result.stderr)
        self.assertEqual(result.stdout, self.body)
        self.assertFalse(self.db.exists())

    def test_fresh_use_registers_source_and_one_event(self):
        result = self.call("use", "sample")
        self.assertEqual(result.exit, 0, result.stderr)
        self.assertIn(self.body, result.stdout)
        self.assertEqual(len(self.events()), 1)
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT name,status,path FROM skills").fetchall(),
                             [("sample", "active", str(self.page.parent))])

    def test_fresh_use_requires_identity_before_creating_store(self):
        self.rejected(self.call("use", "sample", identity=False), "identity")
        self.assertFalse(self.db.exists())

    def test_native_event_can_register_only_a_valid_disk_skill(self):
        result = self.call("log-miss", "sample", "managed recovery")
        self.assertEqual(result.exit, 0, result.stderr)
        self.assertEqual(self.events()[0][:2], ("sample", "miss"))
        self.rejected(self.call("log-use", "unknown"), "skill")
        self.assertEqual(len(self.events()), 1)

    def test_catalogue_reads_current_source_and_never_writes_state(self):
        self.sync()
        before = self.db.read_bytes()
        result = self.call("catalog", identity=False)
        self.assertEqual(result.exit, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [{
            "name": "sample", "description": "A measured sample", "path": str(self.page),
            "sha256": hashlib.sha256(self.body.encode()).hexdigest(), "status": "active",
        }])
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.events(), [])

    def test_read_is_not_an_invocation(self):
        self.sync()
        result = self.call("read", "sample", identity=False)
        self.assertEqual(result.exit, 0, result.stderr)
        self.assertEqual(result.stdout, self.body)
        self.assertEqual(self.events(), [])

    def test_use_records_one_attributed_redacted_invocation_and_whole_page(self):
        self.sync()
        result = self.call("use", "sample", "password=private sample invocation")
        self.assertEqual(result.exit, 0, result.stderr)
        self.assertIn(self.body, result.stdout)
        self.assertIn("invoked: sample", result.stdout)
        self.assertIn(str(self.page), result.stdout)
        rows = self.events()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][:4], ("sample", "invoked", AGENT, "fixture-session"))
        self.assertNotIn("private", rows[0][4])
        self.assertIn("[redacted]", rows[0][4])

    def test_invocations_persist_the_served_source_path_and_digest(self):
        result = self.call("use", "sample")
        self.assertEqual(result.exit, 0, result.stderr)
        changed = self.body.replace("Run the sample procedure.", "Run the changed procedure.")
        self.world.plant_text(self.page, changed)
        result = self.call("use", "sample")
        self.assertEqual(result.exit, 0, result.stderr)
        self.assertEqual(self.event_sources(), [
            (str(self.page), hashlib.sha256(self.body.encode()).hexdigest()),
            (str(self.page), hashlib.sha256(changed.encode()).hexdigest()),
        ])

    def test_ordinary_cli_identity_remains_the_shared_instrument_observation(self):
        result = self.call("use", "sample", identity=False, extra={"WF_AGENT": AGENT})
        self.assertEqual(result.exit, 0, result.stderr)
        self.assertEqual(self.events()[0][2], AGENT)

    def test_inactive_and_unknown_skills_are_not_invocable(self):
        self.sync()
        for status in ("draft", "retired", "missing", "wished"):
            with self.subTest(status=status):
                with sqlite3.connect(self.db) as con:
                    con.execute("UPDATE skills SET status=? WHERE name='sample'", (status,))
                result = self.call("catalog")
                self.assertEqual(result.exit, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), [])
                self.rejected(self.call("use", "sample"), "skill")
        self.rejected(self.call("use", "unknown"), "skill")
        self.assertEqual(self.events(), [])

    def test_unsafe_or_qualified_names_refuse_without_events(self):
        self.sync()
        for name in ("../sample", "user:sample", "plugin:sample", "/sample", "sample\nother"):
            with self.subTest(name=name):
                self.rejected(self.call("use", name), "skill")
        self.assertEqual(self.events(), [])

    def test_use_without_identity_does_not_serve_page(self):
        self.sync()
        self.rejected(self.call("use", "sample", identity=False), "identity")
        self.assertEqual(self.events(), [])

    def test_registry_paths_cannot_redirect_canonical_source(self):
        self.sync()
        counterfeit = self.world.plant_text(self.world.root / "counterfeit.md", "not a skill")
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE skills SET path=? WHERE name='sample'", (str(counterfeit),))
        result = self.call("read", "sample")
        self.assertEqual(result.exit, 0, result.stderr)
        self.assertEqual(result.stdout, self.body)

    def test_escaped_source_refuses_and_internal_symlink_remains_supported(self):
        self.sync()
        self.page.unlink()
        external = self.world.plant_text(self.world.root / "outside.md", self.body)
        self.page.symlink_to(external)
        self.rejected(self.call("use", "sample"), "skill-source")
        self.page.unlink()
        internal = self.world.plant_text(self.repo / ".agents/skills/sample/SKILL.md", self.body)
        self.page.symlink_to(internal)
        result = self.call("read", "sample")
        self.assertEqual(result.exit, 0, result.stderr)
        self.assertEqual(result.stdout, self.body)

    def test_descriptor_reader_resists_a_resolve_then_open_symlink_swap(self):
        subject = self.loaded_module()
        subject.REPO = self.repo
        subject.SKILLS_DIR = self.skill_root
        external = self.world.plant_text(
            self.world.root / "outside.md",
            "---\nname: sample\ndescription: Escaped replacement\n---\n\nDo not serve this.\n",
        )
        real_resolve = Path.resolve

        def replace_after_resolve(path, *args, **kwargs):
            resolved = real_resolve(path, *args, **kwargs)
            if path == self.page:
                self.page.unlink()
                self.page.symlink_to(external)
            return resolved

        with patch.object(subject, "_statuses", return_value={}):
            with patch.object(Path, "resolve", new=replace_after_resolve):
                page = subject.load_skill("sample")
        self.assertEqual(page["content"], self.body)

    def test_duplicate_name_oversize_and_malformed_metadata_refuse(self):
        self.sync()
        duplicate = self.world.plant_text(self.skill_root / "another/SKILL.md", self.body)
        self.rejected(self.call("catalog"), "skill-source")
        duplicate.unlink()
        duplicate.parent.rmdir()
        self.world.plant_text(self.page, "x" * (256 * 1024 + 1))
        self.rejected(self.call("use", "sample"), "skill-source")
        self.world.plant_text(self.page, "not frontmatter\n")
        self.rejected(self.call("use", "sample"), "skill-source")
        self.assertEqual(self.events(), [])

    def test_corrupt_registry_is_not_empty_catalogue(self):
        self.world.plant_bytes(self.db, b"not sqlite")
        self.rejected(self.call("catalog", identity=False), "registry")


if __name__ == "__main__":
    unittest.main()
