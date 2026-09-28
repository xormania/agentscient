"""A-218: shared policy transport faults and clean neighbors.

Single dev-lane producer under owner WALL grant; independent verifier is root.
"""
import hashlib
import io
import json
import os
import shutil
import sqlite3
import unittest
from contextlib import redirect_stdout
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import support

from ops.devlane.hooks import enforcement, native, profiles
from ops.testkit import World, run


class ManagedSkills(unittest.TestCase):
    """Owner 2026-09-19: shared skills, existing owners, no native activation.

    The API double declares the non-wall skills.py coupling while that owner's
    implementation is developed independently. Source pages are read only.
    """

    def setUp(self):
        self.world = World(prefix="managed-skill-hooks-")
        self.addCleanup(self.world.close)
        self.repo = self.world.root / "repo"
        self.repo.mkdir()
        self.env = support.isolated_env(self.world.home)
        support.git(self.repo, self.env, "init", "-q", "-b", "dev")
        support.configure_identity(self.repo, self.env)
        self.world.plant_text(self.repo / "README.txt", "read control\n")
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.rows = {}
        for name in ("onboard", "refused", "deliverable"):
            path = enforcement.SOURCE / ".claude/skills" / name / "SKILL.md"
            self.rows[name] = {"name": name, "description": name + " procedure", "path": str(path),
                               "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "status": "active", "content": path.read_text()}
        self.owner = SimpleNamespace(
            managed_catalog=lambda: [{k: v for k, v in row.items() if k != "content"}
                                     for row in self.rows.values()],
            load_skill=lambda name: dict(self.rows[name]), record_event=Mock())
        self.owner_patch = patch.object(enforcement, "skills", self.owner, create=True)
        self.owner_patch.start()
        self.addCleanup(self.owner_patch.stop)

    def payload(self, tool="Bash", **args):
        return {"hook_event_name": "PreToolUse", "cwd": str(self.repo),
                "session_id": "fixture-session", "native_harness": "claude",
                "tool_name": tool, "tool_input": args}

    def invoke(self, harness, event, mode="interactive", *, pins=None):
        payload = {"session_id": "fixture-session", "cwd": str(self.repo)}
        if harness == "agy":
            payload = {"conversationId": "fixture-session", "workspacePaths": [str(self.repo)],
                       "invocationNum": 1, "initialNumSteps": 0}
        binding = {"harness": harness, "mode": mode, "cwd": str(self.repo),
                   "home": str(self.world.home), "source": str(enforcement.SOURCE),
                   "pins": profiles.source_pins(enforcement.SOURCE) if pins is None else pins}
        projection = SimpleNamespace(read_binding=lambda _: binding, validate=lambda _: binding,
                                     initialize=lambda *a, **k: None)
        actual_load = enforcement.load
        def loader(name, path):
            return projection if name == "shared_hook_profiles" else actual_load(name, path)
        output = io.StringIO()
        with patch.object(enforcement, "load", side_effect=loader), redirect_stdout(output), patch.object(
                enforcement.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode()))):
            self.assertEqual(enforcement.main(["--harness", harness, "--event", event,
                                               "--binding", "/synthetic/binding.json"]), 0)
        return json.loads(output.getvalue())

    def test_each_policy_refusal_records_one_miss_and_keeps_its_remedy(self):
        for tool, args in [("Bash", {"command": "git commit -m blocked"}),
                           ("Bash", {"command": "python3 -m pytest | tail -2"}),
                           ("Agent", {"prompt": "blocked"})]:
            with self.subTest(tool=tool, args=args):
                self.owner.record_event.reset_mock()
                result = enforcement.evaluate(self.payload(tool, **args), mode="interactive")
                self.assertEqual(result["outcome"], "deny")
                self.assertIn("skills.py use refused", result["reason"])
                self.owner.record_event.assert_called_once()
                self.assertEqual(self.owner.record_event.call_args.args[:2], ("miss", "refused"))

    def test_event_failure_never_replaces_a_denial_or_pending_owner_decision(self):
        self.owner.record_event.side_effect = OSError("unwritable synthetic registry")
        for command, outcome in [("git commit -m blocked", "deny"), ("git push --force origin topic", "ask")]:
            result = enforcement.evaluate(self.payload(command=command), mode="interactive")
            self.assertEqual(result["outcome"], outcome)
            self.assertIn("skills.py use refused", result["reason"])
            self.assertNotIn("unwritable", result["reason"])

    def test_clean_read_and_cli_use_are_not_hook_invocations(self):
        for command in ("cat README.txt", "python3 ops/conductor/tools/skills.py use onboard"):
            self.assertEqual(enforcement.evaluate(self.payload(command=command))["outcome"], "allow")
        self.owner.record_event.assert_not_called()

    def test_deliverable_uses_existing_miss_mapping_and_pinned_owner(self):
        self.world.plant_text(self.repo / "ops/conductor/tools/skills.py", "raise RuntimeError('counterfeit')\n")
        refusal = {"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason":
                   "[matrix:deliverable] deliverable: expected a lock; found unnamed branch; needed add it"}}
        with patch.object(enforcement.matrix, "decide", return_value=refusal):
            result = enforcement.evaluate(self.payload(command="touch ops/new.py"), mode="interactive")
        self.assertIn("skills.py use deliverable", result["reason"])
        self.owner.record_event.assert_called_once()
        self.assertEqual(self.owner.record_event.call_args.args[:2], ("miss", "deliverable"))

    def test_name_only_native_skill_gets_canonical_fallback_without_invoked_credit(self):
        item = native.normalize("claude", self.payload("Skill", skill="onboard", args="session start"))[0]
        result = enforcement.evaluate(item, mode="interactive", pins=profiles.source_pins(enforcement.SOURCE))
        self.assertEqual(result["outcome"], "deny")
        self.assertIn("skills.py use onboard", result["reason"])
        self.assertFalse(any(call.args[0] == "invoked" for call in self.owner.record_event.call_args_list))

    def test_unknown_retired_or_foreign_native_skill_is_not_admitted(self):
        for name, change in [("unknown", None), ("onboard", {"status": "retired"}),
                             ("onboard", {"path": str(self.repo / "SKILL.md")}),
                             ("onboard", {"sha256": "0" * 64})]:
            with self.subTest(name=name, change=change):
                original = dict(self.rows["onboard"])
                if change:
                    self.rows["onboard"].update(change)
                result = enforcement.evaluate(self.payload("Skill", skill=name), mode="interactive",
                                              pins=profiles.source_pins(enforcement.SOURCE))
                self.assertEqual(result["outcome"], "deny")
                self.rows["onboard"] = original

    def test_only_observed_skill_spelling_is_normalized(self):
        for args in ({"skill": []}, {"skill": "../refused"}, {"name": "onboard"},
                     {"skill": "onboard", "args": {}}, {"skill": "user:onboard"}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                native.normalize("claude", self.payload("Skill", **args))
        for harness in ("codex", "grok", "agy"):
            payload = {**self.payload("Skill", skill="onboard"), "native_harness": harness}
            self.assertEqual(enforcement.evaluate(payload)["outcome"], "deny")

    def test_worker_native_skill_never_loads_operator_source(self):
        self.owner.load_skill = Mock(side_effect=AssertionError("operator source reached"))
        result = enforcement.evaluate(self.payload("Skill", skill="onboard"), mode="worker")
        self.assertEqual(result["outcome"], "deny")
        self.assertIn("assigned job instructions", result["reason"])
        self.owner.load_skill.assert_not_called()
        self.owner.record_event.assert_not_called()

    def test_interactive_startup_serves_bounded_catalogue_workers_do_not(self):
        for harness in native.HARNESSES:
            event = "PreInvocation" if harness == "agy" else "SessionStart"
            with self.subTest(harness=harness):
                interactive = self.invoke(harness, event)
                text = json.dumps(interactive)
                self.assertIn("skills.py use", text)
                self.assertIn("onboard procedure", text)
                self.assertLess(len(text), 8500)
                worker = json.dumps(self.invoke(harness, event, "worker"))
                self.assertNotIn("onboard procedure", worker)
                self.assertNotIn("skills.py use", worker)
        self.owner.record_event.assert_not_called()

    def test_agy_preinvocation_uses_only_ephemeral_context_and_retains_stop_limits(self):
        out = self.invoke("agy", "PreInvocation")
        self.assertIn("injectSteps", out)
        self.assertTrue(all(set(step) == {"ephemeralMessage"} for step in out["injectSteps"]))
        result = {"outcome": "deny", "reason": "hook-input: unavailable", "context": ""}
        self.assertEqual(native.respond("agy", result, "Stop")["decision"], "continue")
        self.assertEqual(native.respond("agy", result, "PostToolUse"), {})

    def test_catalogue_failure_is_declared_without_changing_startup_policy(self):
        self.owner.managed_catalog = Mock(side_effect=OSError("unreadable"))
        response = self.invoke("claude", "SessionStart")
        self.assertIn("unavailable", json.dumps(response).lower())
        self.assertNotIn("block", response)

    def test_profile_pins_skill_sources_only_for_interactive_guidance(self):
        for mode in ("interactive", "worker"):
            binding = profiles.generate("agy", self.world.root / mode, source=enforcement.SOURCE,
                                        cwd=self.repo, mode=mode, session="issued" if mode == "worker" else None)
            page = self.rows["onboard"]["path"]
            if mode == "interactive":
                self.assertEqual(binding["pins"].get(page), self.rows["onboard"]["sha256"])
                self.assertIn("PreInvocation", Path(binding["helper"]).read_text())
            else:
                self.assertNotIn(page, binding["pins"])

    def test_done_gate_cap_uses_pinned_telemetry_without_a_snapshot_script(self):
        self.world.plant_text(self.repo / "ops/conductor/tools/skills.py", "raise RuntimeError('counterfeit')\n")
        payload = {"hook_event_name": "Stop", "cwd": str(self.repo),
                   "session_id": "fixture-session", "last_assistant_message": "The task is done."}
        with patch.object(enforcement.engine, "_done_gate_count", return_value=enforcement.engine.DONE_GATE_CAP), patch.object(
                enforcement.engine, "_lock_reading", return_value="the lock reads: synthetic outstanding target"):
            result = enforcement.evaluate(payload, mode="interactive")
        self.assertEqual(result["outcome"], "allow")
        self.owner.record_event.assert_called_once()
        self.assertEqual(self.owner.record_event.call_args.args[:2], ("miss", "refused"))
        self.assertIn("cap", self.owner.record_event.call_args.args[2])

    def test_modified_added_or_redirected_skill_invalidates_interactive_profile(self):
        source = self.world.root / "source"
        for original in profiles.source_pins(enforcement.SOURCE):
            self.world.plant_bytes(source / Path(original).relative_to(enforcement.SOURCE), Path(original).read_bytes())
        page = source / ".claude/skills/onboard/SKILL.md"
        content = page.read_bytes()
        with patch.object(profiles, "__file__", str(source / "ops/devlane/hooks/profiles.py")):
            for change in ("edit", "add", "symlink"):
                with self.subTest(change=change):
                    binding = profiles.generate("claude", self.world.root / ("pins-" + change),
                                                source=source, cwd=self.repo, mode="interactive")
                    profiles.validate(binding)
                    if change == "edit":
                        self.world.plant_bytes(page, content + b"\nchanged instructions\n")
                    elif change == "add":
                        self.world.plant_text(source / ".claude/skills/new-skill/SKILL.md", "new skill\n")
                    else:
                        other = self.world.plant_bytes(self.world.root / "foreign-page", content)
                        page.unlink()
                        page.symlink_to(other)
                    with self.assertRaises(ValueError):
                        profiles.validate(binding)
                    if change == "symlink":
                        page.unlink()
                    self.world.plant_bytes(page, content)

    def test_only_active_catalogue_rows_are_injected_with_bounded_description(self):
        self.rows["refused"]["status"] = "retired"
        self.rows["onboard"]["description"] = "long description " * 10000
        result = json.dumps(self.invoke("agy", "PreInvocation"))
        self.assertIn("long description", result)
        self.assertNotIn("refused procedure", result)
        self.assertLess(len(result), 8500)

    def test_retarget_after_profile_validation_cannot_enter_startup_context(self):
        source = self.world.root / "retarget-source"
        for original in profiles.source_pins(enforcement.SOURCE):
            self.world.plant_bytes(source / Path(original).relative_to(enforcement.SOURCE), Path(original).read_bytes())
        page = source / ".claude/skills/onboard/SKILL.md"
        content = page.read_bytes()
        with patch.object(profiles, "__file__", str(source / "ops/devlane/hooks/profiles.py")):
            binding = profiles.generate("claude", self.world.root / "retarget-profile",
                                        source=source, cwd=self.repo, mode="interactive")
            profiles.validate(binding)
            # The swap is deliberately scheduled after successful validation.
            target = self.world.plant_bytes(source / "elsewhere/SKILL.md", content)
            page.unlink()
            page.symlink_to(target)
            row = {**self.rows["onboard"], "path": str(target), "description": "UNPINNED_RETARGET"}
            owner = SimpleNamespace(managed_catalog=lambda: [row])
            result = enforcement.skill_use.startup(owner, source, pins=binding["pins"])
            self.assertIn("unavailable", result)
            self.assertNotIn("UNPINNED_RETARGET", result)

    def test_owner_resolved_repository_aliases_are_served_and_pinned(self):
        name = "mate-system-information"
        path = (enforcement.SOURCE / ".claude/skills" / name / "SKILL.md").resolve(strict=True)
        self.rows[name] = {"name": name, "description": "repository alias control", "path": str(path),
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "status": "active", "content": path.read_text()}
        response = self.invoke("claude", "SessionStart")
        self.assertIn("repository alias control", json.dumps(response))
        self.assertEqual(profiles.source_pins(enforcement.SOURCE).get(str(path)), self.rows[name]["sha256"])

    def test_worker_policy_retains_remedy_without_operator_source_or_event(self):
        result = enforcement.evaluate(self.payload(command="git commit -m blocked"), mode="worker")
        self.assertEqual(result["outcome"], "deny")
        self.assertNotIn("skills.py use", result["reason"])
        self.assertIn("needed", result["reason"])
        self.owner.record_event.assert_not_called()

    def test_worker_done_cap_never_reaches_operator_event_source(self):
        payload = {"hook_event_name": "Stop", "cwd": str(self.repo),
                   "session_id": "fixture-session", "last_assistant_message": "The task is done."}
        with patch.object(enforcement.engine, "_done_gate_count", return_value=enforcement.engine.DONE_GATE_CAP), patch.object(
                enforcement.engine, "_lock_reading", return_value="the lock reads: synthetic outstanding target"):
            result = enforcement.evaluate(payload, mode="worker")
        self.assertEqual(result["outcome"], "allow")
        self.owner.record_event.assert_not_called()

    def test_catalogue_text_cannot_inject_control_characters(self):
        self.rows["onboard"]["description"] = "visible\x1b[31m red\x00 nul\u202e hidden\x7f"
        output = json.dumps(self.invoke("agy", "PreInvocation"), ensure_ascii=False)
        for character in ("\\u001b", "\\u0000", "\u202e", "\x7f"):
            self.assertNotIn(character, output)
        self.assertIn("visible", output)

    def test_catalogue_page_must_belong_to_supplied_pinned_closure(self):
        output = json.dumps(self.invoke("claude", "SessionStart", pins={}))
        self.assertIn("unavailable", output)
        self.assertNotIn("onboard procedure", output)


class SharedEnforcement(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="shared-enforcement-")
        self.addCleanup(self.world.close)
        self.repo = self.world.root / "repo"
        self.repo.mkdir()
        self.env = support.isolated_env(self.world.home)
        support.git(self.repo, self.env, "init", "-q", "-b", "dev")
        support.configure_identity(self.repo, self.env)
        (self.repo / "ops").mkdir()
        (self.repo / "ops/lane.conf").write_text(
            "LANE_NAME='agentscient'\nTRUNK_BRANCH='dev'\nRELEASE_BRANCH='master'\n")
        (self.repo / "README.txt").write_text("read control\n")
        support.git(self.repo, self.env, "add", ".")
        support.git(self.repo, self.env, "commit", "-qm", "fixture")
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def canonical(self, tool="Bash", **args):
        return {"hook_event_name": "PreToolUse", "cwd": str(self.repo),
                "session_id": "fixture-session", "tool_name": tool, "tool_input": args}

    def evaluate(self, tool="Bash", **args):
        return enforcement.evaluate(self.canonical(tool, **args))

    def test_existing_matrix_engine_and_unsafe_faults_have_clean_neighbors(self):
        for command, expected in [("git commit -m fixture", "deny"),
                                  ("python3 -m pytest | tail -2", "deny"),
                                  ("git push --force origin topic", "ask"),
                                  ("touch ops/new.py", "deny"),
                                  ("touch scratch.txt", "allow"),
                                  ("git status --porcelain", "allow"),
                                  ("cat README.txt", "allow")]:
            with self.subTest(command=command):
                self.assertEqual(self.evaluate(command=command)["outcome"], expected)
        self.assertEqual(self.evaluate("Write", file_path=str(self.repo / "ops/a.py"), content="x")["outcome"], "deny")
        self.assertEqual(self.evaluate("Write", file_path=str(self.repo / "scratch.txt"), content="x")["outcome"], "allow")
        self.assertEqual(self.evaluate("Agent", prompt="synthetic")["outcome"], "deny")
        self.assertEqual(self.evaluate("Read", file_path=str(self.repo / "README.txt"))["outcome"], "allow")
        self.assertEqual(self.evaluate("Read", file_path=str(self.repo / "ops/lane.conf"))["outcome"], "allow")

    def test_missing_malformed_and_unknown_inputs_never_allow(self):
        for payload in [None, [], {}, self.canonical("MysteryWrite", path="x"),
                        self.canonical("Bash", command=[]), self.canonical("Edit")]:
            with self.subTest(payload=payload):
                self.assertEqual(enforcement.evaluate(payload)["outcome"], "deny")
        with patch.object(enforcement.matrix, "decide", side_effect=OSError("unavailable")):
            self.assertEqual(self.evaluate(command="touch scratch.txt")["outcome"], "deny")

    def test_snapshot_registry_override_cannot_disable_hard_rows(self):
        registry = self.world.root / "fake-boundaries.json"
        registry.write_text('{"schema":"agentscient.boundaries/2","rows":[]}')
        with patch.dict(os.environ, {"BOUNDARIES_PATH": str(registry)}):
            self.assertEqual(self.evaluate(command="git commit -m bypass")["outcome"], "deny")

    def test_each_adapter_reaches_the_same_hard_row_and_preserves_reads(self):
        for harness in ("claude", "codex", "grok", "agy"):
            for command, outcome in [("git commit -m blocked", "deny"), ("git status", "allow")]:
                canonical = self.canonical(command=command)
                payload = canonical if harness != "agy" else {
                    "conversationId": "fixture-session", "workspacePaths": [str(self.repo)],
                    "toolCall": {"name": "run_command", "args": {"CommandLine": command, "Cwd": str(self.repo)}}}
                if harness == "grok":
                    payload = {**canonical, "tool_name": "run_terminal_command"}
                with self.subTest(harness=harness, command=command):
                    items = native.normalize(harness, payload, event="PreToolUse")
                    self.assertEqual(enforcement.evaluate(items[0])["outcome"], outcome)
            blocked = native.respond(harness, {"outcome": "ask", "reason": "owner decision required", "context": ""}, "PreToolUse")
            self.assertIn("deny", json.dumps(blocked))
            self.assertIn("owner", json.dumps(blocked))

    def test_patch_targets_and_moves_all_reach_policy_before_effect(self):
        payload = self.canonical("apply_patch", command="*** Begin Patch\n*** Add File: scratch.txt\n+ok\n*** Update File: ops/a.py\n*** Move to: ops/b.py\n@@\n-x\n+y\n*** Delete File: .github/workflows/ci.yml\n*** End Patch")
        items = native.normalize("codex", payload)
        self.assertEqual({x["tool_input"]["file_path"] for x in items},
                         {"scratch.txt", "ops/a.py", "ops/b.py", ".github/workflows/ci.yml"})
        self.assertTrue(any(enforcement.evaluate(x)["outcome"] == "deny" for x in items))
        for broken in ("", "*** Begin Patch\n*** Mystery: x\n*** End Patch", "*** Begin Patch\n*** Add File: a\n+x"):
            with self.subTest(patch=broken), self.assertRaises(ValueError):
                native.normalize("codex", self.canonical("apply_patch", command=broken))

    def test_direct_multi_edit_cannot_hide_second_target(self):
        payload = self.canonical("MultiEdit", edits=[{"file_path": "scratch.txt", "old_string": "x", "new_string": "y"},
                                                    {"file_path": "ops/a.py", "old_string": "x", "new_string": "y"}])
        items = native.normalize("claude", payload)
        self.assertEqual(len(items), 2)
        self.assertEqual(enforcement.evaluate(items[1])["outcome"], "deny")

    def test_continuation_poll_is_read_but_unbound_input_refuses(self):
        for harness, tool, args in [("codex", "write_stdin", {"session_id": 1, "chars": "touch x\n"}),
                                    ("agy", "manage_task", {"Action": "send_input", "TaskId": "s/task-2", "Input": "x"})]:
            payload = self.canonical(tool, **args)
            if harness == "agy":
                payload = {"conversationId": "fixture-session", "workspacePaths": [str(self.repo)], "toolCall": {"name": tool, "args": args}}
            self.assertEqual(enforcement.evaluate(native.normalize(harness, payload, event="PreToolUse")[0])["outcome"], "deny")
        payload = self.canonical("write_stdin", session_id=1, chars="")
        self.assertEqual(enforcement.evaluate(native.normalize("codex", payload)[0])["outcome"], "allow")

    def test_duplicate_native_fields_are_not_last_key_wins(self):
        with self.assertRaises(ValueError):
            native.loads('{"tool_name":"Read","tool_name":"Write"}')

    def test_profile_missing_or_changed_helper_is_rejected(self):
        root = Path(__file__).resolve().parents[4]
        for harness in ("claude", "codex", "grok", "agy"):
            with self.subTest(harness=harness):
                dest = self.world.root / ("profile-" + harness)
                binding = profiles.generate(harness, dest, source=root, cwd=self.repo, mode="interactive")
                profiles.validate(profiles.read_binding(binding["binding"]))
                helper = Path(binding["helper"])
                helper.write_text("#!/bin/sh\nexit 0\n")
                with self.assertRaises(ValueError):
                    profiles.validate(binding)

    def test_coordination_capability_is_private_and_survives_all_harness_resumes(self):
        root = Path(__file__).resolve().parents[4]
        isolation = profiles.isolation_owner()
        seen = set()
        inherited = "f" * 64
        for harness in profiles.HARNESSES:
            with self.subTest(harness=harness):
                old = self.world.root / ("capability-" + harness)
                home, cwd = old / "home", old / "snapshot"
                home.mkdir(parents=True)
                cwd.mkdir()
                kwargs = {"source": root, "cwd": cwd, "home": home, "session": "issued-" + harness,
                          "agent": "Fixture <f@invalid>", "executable": "/usr/bin/true"}
                _, binding = isolation.install_enforcement(harness, old / "enforcement", **kwargs)
                capability = binding.get("coordination_capability")
                self.assertIsInstance(capability, str)
                self.assertRegex(capability, r"^[0-9a-f]{64}$")
                self.assertNotIn(capability, seen)
                seen.add(capability)
                self.assertEqual(Path(binding["binding"]).stat().st_mode & 0o777, 0o600)
                command, env = profiles.native_launch(binding, ["/usr/bin/true"], {**self.env, "COORDINATION_CAPABILITY": inherited})
                self.assertEqual(env["COORDINATION_CAPABILITY"], capability)
                self.assertNotIn(capability, str(command))
                for path in (binding["helper"], *binding["config_pins"]):
                    self.assertNotIn(capability, Path(path).read_text())
                _, resumed = isolation.install_enforcement(harness, old / "enforcement", **kwargs)
                self.assertEqual(resumed["coordination_capability"], capability)
                new = old.with_name(old.name + "-moved")
                shutil.move(old, new)
                kwargs.update(home=new / "home", cwd=new / "snapshot", relocated_from=old)
                _, moved = isolation.install_enforcement(harness, new / "enforcement", **kwargs)
                self.assertEqual(moved["coordination_capability"], capability)
                profiles.validate(moved)

    def test_coordination_capability_missing_or_malformed_refuses_profile(self):
        root = Path(__file__).resolve().parents[4]
        binding = profiles.generate("codex", self.world.root / "capability-invalid", source=root,
                                    cwd=self.repo, mode="interactive", executable="/usr/bin/true")
        for value in (None, "", "x" * 64, "A" * 64, "0" * 63, 123):
            altered = {**binding}
            if value is None:
                altered.pop("coordination_capability", None)
            else:
                altered["coordination_capability"] = value
            Path(binding["binding"]).write_text(profiles.canonical(altered))
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "capability"):
                profiles.validate(altered)

    def test_preserved_mcp_environment_drops_inherited_coordination_capability(self):
        root = Path(__file__).resolve().parents[4]
        inherited = "e" * 64
        settings = {"model": "fixture-model", "mcp_servers": {"coordination": {
            "command": "python3", "args": ["fixture.py"],
            "env": {"COORDINATION_CAPABILITY": inherited, "CODEX_THREAD_ID": "parent-session",
                    "AGENTSCIENT_HOOK_PROFILE": "/parent/binding.json", "SAFE_SETTING": "retained"}}}}
        original = profiles.canonical(settings)
        for harness in profiles.HARNESSES:
            with self.subTest(harness=harness):
                binding = profiles.generate(harness, self.world.root / ("mcp-capability-" + harness), source=root,
                                            cwd=self.repo, mode="interactive", executable="/usr/bin/true",
                                            native_settings=settings)
                self.assertEqual(profiles.canonical(settings), original)
                for path in (binding["binding"], binding["helper"], *binding["config_pins"]):
                    self.assertFalse(inherited in Path(path).read_text(), f"parent capability retained in {path}")
                self.assertNotIn(inherited, profiles.canonical(binding))
                server = binding["native_settings"]["mcp_servers"]["coordination"]
                self.assertEqual(server, {"command": "python3", "args": ["fixture.py"],
                                         "env": {"SAFE_SETTING": "retained", "AGENTSCIENT_HOOK_PROFILE": binding["binding"]}})
                self.assertEqual(binding["native_settings"]["model"], "fixture-model")
                self.assertRegex(binding["coordination_capability"], r"^[0-9a-f]{64}$")
                self.assertNotEqual(binding["coordination_capability"], inherited)
                for path in (binding["helper"], *binding["config_pins"]):
                    self.assertNotIn(binding["coordination_capability"], Path(path).read_text())
                projected = "".join(Path(path).read_text() for path in binding["config_pins"])
                for safe in ("SAFE_SETTING", "retained", "fixture.py"):
                    self.assertIn(safe, projected)
                profiles.validate(profiles.read_binding(binding["binding"]))
                command, environment = profiles.native_launch(binding, ["/usr/bin/true"],
                                                               {**self.env, "COORDINATION_CAPABILITY": inherited})
                self.assertNotIn(inherited, str(command))
                self.assertNotIn(binding["coordination_capability"], str(command))
                self.assertNotIn(inherited, str(environment))
                self.assertEqual(environment["COORDINATION_CAPABILITY"], binding["coordination_capability"])

    def test_grant_ownership_expiry_and_malformed_authority(self):
        instrument = enforcement.instrument
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "own", "WF_AGENT_OVERRIDE": "Fixture <fixture@example.invalid>"}):
            db = enforcement.hand.database_path()
            db.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(db)
            self.addCleanup(conn.close)
            conn.execute(enforcement.hand.SCHEMA)
            stamp = instrument.stamp(instrument.now())
            conn.execute("INSERT INTO handwork(id,ts,session,agent,action,why_by_hand,lever_class,scope,ttl_s,status) VALUES(1,?,?,?,?,?,'other','',3600,'open')",
                         (stamp, "own", instrument.identity(), "fixture", "synthetic authority test"))
            conn.commit()
            command = "HAND_GRANT=1 printf x > ops/new.py"
            self.assertEqual(self.evaluate(command=command)["outcome"], "allow")
            self.assertEqual(self.evaluate(command="HAND_GRANT=1 git commit -m blocked")["outcome"], "deny")
            for field, value in [("session", "foreign"), ("agent", "Foreign <foreign@example.invalid>"),
                                 ("ttl_s", 0), ("ttl_s", "invalid"), ("ts", "invalid"),
                                 ("ts", instrument.stamp(instrument.now() - timedelta(days=1))),
                                 ("ts", instrument.stamp(instrument.now() + timedelta(days=1)))]:
                with self.subTest(field=field, value=value):
                    previous = conn.execute("SELECT " + field + " FROM handwork WHERE id=1").fetchone()[0]
                    conn.execute("UPDATE handwork SET " + field + "=? WHERE id=1", (value,))
                    conn.commit()
                    self.assertEqual(self.evaluate(command=command)["outcome"], "deny")
                    conn.execute("UPDATE handwork SET " + field + "=? WHERE id=1", (previous,))
                    conn.commit()

    def test_profiles_cannot_relabel_modified_configuration(self):
        root = Path(__file__).resolve().parents[4]
        binding = profiles.generate("codex", self.world.root / "config-case", source=root, cwd=self.repo, mode="interactive")
        config = Path(binding["home"]) / "config.toml"
        config.write_text("[features]\nhooks=false\n")
        binding["config_pins"][str(config)] = profiles.digest(config)
        with self.assertRaisesRegex(ValueError, "does not project"):
            profiles.validate(binding)

    def test_missing_config_emits_native_block_without_python(self):
        root = Path(__file__).resolve().parents[4]
        binding = profiles.generate("agy", self.world.root / "missing-case", source=root, cwd=self.repo, mode="interactive")
        Path(next(iter(binding["config_pins"]))).unlink()
        proc = run(["/bin/sh", binding["helper"], "PreToolUse"], cwd=self.repo, env=self.env, stdin="{}")
        self.assertEqual(proc.exit, 0)
        self.assertEqual(json.loads(proc.stdout)["decision"], "deny")

    def test_native_grok_aliases_agree_after_event_translation(self):
        payload = {**self.canonical(command="cat README.txt"), "hookEventName": "pre_tool_use",
                   "toolName": "Bash", "toolInput": {"command": "cat README.txt"}}
        self.assertEqual(enforcement.evaluate(native.normalize("grok", payload)[0])["outcome"], "allow")
        payload["hookEventName"] = "post_tool_use"
        with self.assertRaises(ValueError):
            native.normalize("grok", payload)

    def test_existing_mcp_catalogue_is_required_and_foreign_mutation_refuses(self):
        common = {"server": "coordination", "name": "coord_brief", "arguments": {}}
        payload = self.canonical("MCP", **common)
        self.assertEqual(enforcement.evaluate(payload)["outcome"], "deny")
        self.assertEqual(enforcement.evaluate(payload, servers=("coordination",))["outcome"], "allow")
        payload["tool_input"]["arguments"] = {"unknown": True}
        self.assertEqual(enforcement.evaluate(payload, servers=("coordination",))["outcome"], "deny")
        self.assertTrue(enforcement.mcp_allowed({"server": "agentscient-lane", "name": "lane_start", "arguments": {"profile": "dev"}}, ("agentscient-lane",)))

    def test_required_context_read_failure_refuses_consequential_work(self):
        support.git(self.repo, self.env, "checkout", "-qb", "lane/session-fixture")
        with patch.object(enforcement.context, "tracked_refs", side_effect=OSError("unavailable refs")):
            result = self.evaluate(command="git push origin lane/session-fixture")
        self.assertEqual(result["outcome"], "deny")
        self.assertIn("unavailable refs", result["reason"])

    def test_transcript_reading_is_native_bound_and_missing_is_not_empty(self):
        session = "native-fixture"
        transcript = self.world.home / session / "transcript.jsonl"
        transcript.parent.mkdir()
        transcript.write_text(json.dumps({"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE", "content": "Fixture response."}) + "\n")
        payload = {"conversationId": session, "workspacePaths": [str(self.repo)], "transcriptPath": str(transcript)}
        item = native.normalize("agy", payload, event="Stop", cwd=str(self.repo), home=self.world.home)[0]
        self.assertEqual(item["last_assistant_message"], "Fixture response.")
        transcript.write_text("{}\n")
        with self.assertRaises(ValueError):
            native.normalize("agy", payload, event="Stop", cwd=str(self.repo), home=self.world.home)

    def test_worker_projection_is_distinct_and_relocation_preserves_authority(self):
        import shutil
        root = Path(__file__).resolve().parents[4]
        old = self.world.root / "job-old"
        snapshot = old / "snapshot"
        snapshot.mkdir(parents=True)
        binding = profiles.generate("codex", old / "enforcement", source=root, cwd=snapshot,
                                    mode="worker", session="issued-worker")
        new = self.world.root / "job-new"
        shutil.move(old, new)
        revised = profiles.relocate(binding, old, new)
        self.assertEqual(revised["session"], "issued-worker")
        self.assertEqual(revised["authority_environment"], binding["authority_environment"])
        self.assertEqual(revised["cwd"], str(new / "snapshot"))
        profiles.validate(revised)
        helper = Path(revised["helper"])
        helper.write_text("#!/bin/sh\nexit 0\n")
        with self.assertRaises(ValueError):
            profiles.validate(revised)

    def test_interactive_identity_registers_without_a_dispatch_assignment(self):
        root = Path(__file__).resolve().parents[4]
        core = enforcement.load("test_hook_coordination", root / "ops/conductor/tools/coordination.py")
        with patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "stale-parent", "COORDINATION_CAPABILITY": "a" * 64,
                                     "WF_AGENT_OVERRIDE": "Fixture <fixture@example.invalid>"}):
            with core.writer() as conn:
                core.core_bind(conn, None, agent="Fixture <fixture@example.invalid>", roles="lead", harness="claude")
            binding = profiles.generate("codex", self.world.root / "interactive-native", source=root, cwd=self.repo, mode="interactive")
            session = profiles.initialize(binding, {"session_id": "actual-native"}, instrument=enforcement.instrument)
            self.assertEqual(session, "actual-native")
            self.assertEqual(os.environ["COORDINATION_CAPABILITY"], binding["coordination_capability"])
            conn = core.reader()
            self.addCleanup(conn.close)
            participant = core.maybe_participant(conn)
            self.assertEqual(participant["session_id"], "actual-native")
            self.assertEqual(participant["roles"], "worker")
            self.assertEqual(participant["harness"], "codex")
            self.assertEqual(conn.execute("SELECT count(*) FROM assignments").fetchone()[0], 0)
            self.assertNotIn("CLAUDE_CODE_SESSION_ID", os.environ)

    def test_interactive_resume_preserves_native_endpoint_and_cli_identity(self):
        root = Path(__file__).resolve().parents[4]
        core = enforcement.load("test_native_endpoint_coordination", root / "ops/conductor/tools/coordination.py")
        for harness in profiles.HARNESSES:
            for existing in (False, True):
                caller = World(prefix="native-endpoint-caller-")
                self.addCleanup(caller.close)
                session = f"native-{harness}-{existing}"
                endpoint = "native-message:" + session if existing else None
                with self.subTest(harness=harness, endpoint=endpoint), patch.dict(os.environ, self.env, clear=True):
                    binding = profiles.generate(harness, self.world.root / session, source=root, cwd=self.repo,
                                                mode="interactive", home=caller.home, agent="Fixture <f@invalid>")
                    os.environ.update(CLAUDE_SESSION_ID=session, COORDINATION_CAPABILITY=binding["coordination_capability"],
                                      WF_AGENT_OVERRIDE="Fixture <f@invalid>")
                    with core.writer() as conn:
                        part = core.core_bind(conn, None, agent="Fixture <f@invalid>", roles="worker",
                                              harness=harness, endpoint=endpoint)
                    payload = {"conversationId" if harness == "agy" else "session_id": session}
                    for _ in range(2):
                        self.assertEqual(profiles.initialize(binding, payload, instrument=enforcement.instrument), session)
                        with core.reader() as conn:
                            current = core.maybe_participant(conn)
                            self.assertEqual(f"PT-{current['id']}", part["participant"])
                            self.assertEqual(current["endpoint"], endpoint or "hook-profile:" + binding["binding"])
                            self.assertEqual(conn.execute("SELECT count(*) FROM assignments").fetchone()[0], 0)
                        with patch.dict(os.environ, caller.env({"AGENTSCIENT_HOOK_PROFILE": binding["binding"]}), clear=True):
                            self.assertEqual(enforcement.instrument.session(), session)

    def test_interactive_resume_capability_cannot_bind_a_second_native_session(self):
        root = Path(__file__).resolve().parents[4]
        core = enforcement.load("test_profile_reuse_coordination", root / "ops/conductor/tools/coordination.py")
        binding = profiles.generate("codex", self.world.root / "reused-native", source=root, cwd=self.repo, mode="interactive")
        os.environ.update(CLAUDE_SESSION_ID="original-native", COORDINATION_CAPABILITY=binding["coordination_capability"],
                          WF_AGENT_OVERRIDE="Fixture <f@invalid>")
        with core.writer() as conn:
            core.core_bind(conn, None, agent="Fixture <f@invalid>", roles="worker", harness="codex", endpoint="native-message:original")
        with self.assertRaisesRegex(ValueError, "another native terminal"):
            profiles.initialize(binding, {"session_id": "different-native"}, instrument=enforcement.instrument)
        with core.reader() as conn:
            self.assertEqual([tuple(row) for row in conn.execute("SELECT session_id, endpoint FROM participants")],
                             [("original-native", "native-message:original")])

    def test_interactive_profile_reaches_cli_identity_and_original_stores(self):
        root = Path(__file__).resolve().parents[4]
        core = enforcement.load("test_profile_coordination", root / "ops/conductor/tools/coordination.py")
        with core.writer():
            pass
        caller = World(prefix="shared-native-caller-")
        self.addCleanup(caller.close)
        binding = profiles.generate("agy", self.world.root / "interactive-agy", source=root, cwd=self.repo,
                                    mode="interactive", home=caller.home, agent="Fixture <fixture@example.invalid>")
        os.environ["WF_AGENT_OVERRIDE"] = "Fixture <fixture@example.invalid>"
        profiles.initialize(binding, {"conversationId": "actual-agy"}, instrument=enforcement.instrument)
        with patch.dict(os.environ, caller.env({"AGENTSCIENT_HOOK_PROFILE": binding["binding"]}), clear=True):
            self.assertEqual(enforcement.instrument.session(), "actual-agy")
            self.assertEqual(enforcement.instrument.state_root(), Path(binding["authority_environment"]["XDG_STATE_HOME"]))
            self.assertEqual(enforcement.hand.database_path(), self.world.home / ".local/state/agentscient/handwork.db")
            with patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "foreign-parent"}):
                with self.assertRaises(enforcement.instrument.Refusal):
                    enforcement.instrument.session()

    def test_native_cli_verb_first_and_bounded_stop_failure(self):
        with patch.object(profiles, "prepare_interactive", return_value={"binding": "fixture"}) as generate:
            self.assertEqual(profiles.main(["prepare-interactive", "--harness", "codex", "--destination", "new",
                                           "--cwd", str(self.repo), "--executable", "/usr/bin/true", "--agent", "Fixture <f@invalid>"]), 0)
            generate.assert_called_once()
        self.assertFalse(profiles.fallback("codex", "Stop")["continue"])

    def test_codex_config_spellings_and_malformed_overrides_refuse(self):
        root = Path(__file__).resolve().parents[4]
        binding = profiles.generate("codex", self.world.root / "argv-config", source=root,
                                    cwd=self.repo, mode="worker", session="issued", executable="/usr/bin/true")
        for value in ("features.hooks=false", "features={hooks=false}", '"features".hooks=false',
                      " hooks.enabled=false", "shell_environment_policy.inherit=all", "unknown=true",
                      "model_reasoning_effort", "model_reasoning_effort=", 'model_reasoning_effort="high"\nfeatures.hooks=false'):
            for args in (["-c", value], ["--config", value], ["-c" + value], ["-c=" + value], ["--config=" + value]):
                with self.subTest(args=args), self.assertRaises(ValueError):
                    profiles.native_launch(binding, ["/usr/bin/true", *args], self.env)
        for args in (["-c"], ["--config"], ["-c="], ["--config="], ["-c", "--model", "fixture"]):
            with self.subTest(args=args), self.assertRaises(ValueError):
                profiles.native_launch(binding, ["/usr/bin/true", *args], self.env)
        for args in (["-c", 'model_reasoning_effort="high"'], ["--config", 'model_reasoning_effort="high"'],
                     ['-cmodel_reasoning_effort="high"'], ['-c=model_reasoning_effort="high"'],
                     ['--config=model_reasoning_effort="high"']):
            with self.subTest(args=args):
                command, _ = profiles.native_launch(binding, ["/usr/bin/true", *args], self.env)
                self.assertEqual(command[-2:], ["-c", 'model_reasoning_effort="high"'])

    def test_interactive_argv_refuses_authority_overlays_and_unknown_grammar(self):
        root = Path(__file__).resolve().parents[4]
        attacks = {
            "codex": [["--dangerously-bypass-approvals-and-sandbox"], ["-C", "/tmp"], ["-C/tmp"],
                      ["--cd=/tmp"], ["--add-dir", "/"], ["-pother"], ["--profile=other"],
                      ["-s", "danger-full-access"], ["--ask-for-approval=never"],
                      ["-c", 'model_reasoning_effort="high"'], ["--ignore-user-config"],
                      ["resume", "same", "--remote=unix:///tmp/server"], ["exec", "--model", "fixture"]],
            "claude": [["--permission-mode=bypassPermissions"], ["--dangerously-skip-permissions"],
                       ["--agent=other"], ["--agents", "{}"], ["--plugin-url=url"], ["-wother"],
                       ["--setting-sources", "project,local"], ["--mcp-config={}"], ["--bare"]],
            "grok": [["--sandbox=none"], ["--always-approve"], ["--cwd=/tmp"], ["--allow=*"],
                     ["--agent=other"], ["--session-id=foreign"], ["--worktree"], ["--fork-session"]],
            "agy": [["--dangerously-skip-permissions"], ["--add-dir=/"], ["--agent=other"],
                    ["--project=other"], ["--new-project=x"], ["--mode=accept-edits"], ["--remote-control"]],
        }
        for harness in profiles.HARNESSES:
            binding = profiles.generate(harness, self.world.root / ("interactive-args-" + harness), source=root,
                                        cwd=self.repo, mode="interactive", executable="/usr/bin/true")
            for args in [*attacks[harness], ["--unknown"], ["--model"], ["--model="],
                         ["--model", "--help"], ["mcp"], ["--help=true"], ["-hm"], ["--", "one", "two"]]:
                with self.subTest(harness=harness, args=args), self.assertRaises(ValueError):
                    profiles.native_launch(binding, ["/usr/bin/true", *args], self.env)
            resume = {"codex": ["resume", "same"], "claude": ["--resume", "same"],
                      "grok": ["-r", "same"], "agy": ["--conversation", "same"]}[harness]
            for args in (["--model", "fixture"], ["--model=fixture"], resume, ["--", "A plain prompt"]):
                with self.subTest(harness=harness, args=args):
                    command, _ = profiles.native_launch(binding, ["/usr/bin/true", *args], self.env)
                    self.assertIn("/usr/bin/true", command)

    def test_worker_argv_preserves_launcher_sandbox_identity_and_mcp(self):
        root = Path(__file__).resolve().parents[4]
        arguments = {
            "codex": ["exec", "--sandbox", "workspace-write", "--model", "fixture", "-c",
                      'sandbox_workspace_write.writable_roots=["/out"]', "-c", 'mcp_servers.coordination.required=true',
                      "-c", 'mcp_servers.coordination.tools.coord_claim.approval_mode="approve"', "--json", "-"],
            "claude": ["--setting-sources", "project,local", "--session-id", "issued", "--permission-mode",
                       "acceptEdits", "--add-dir", "/out", "--mcp-config", "server.json", "--print"],
            "grok": ["--always-approve", "--model", "fixture", "--prompt-file", "prompt.txt"],
            "agy": ["--print=", "--dangerously-skip-permissions", "--add-dir", "/out", "--conversation", "issued"],
        }
        for harness, args in arguments.items():
            binding = profiles.generate(harness, self.world.root / ("worker-args-" + harness), source=root,
                                        cwd=self.repo, mode="worker", session="issued", executable="/usr/bin/true")
            command, env = profiles.native_launch(binding, ["/usr/bin/true", *args], self.env)
            self.assertEqual(env["CLAUDE_SESSION_ID"], "issued")
            for arg in args:
                if arg != "project,local":
                    self.assertIn(arg, command)

    def test_custody_source_is_pinned_protected_and_checked_after_child(self):
        root = Path(__file__).resolve().parents[4]
        source = self.world.root / "source"
        owner_path = "ops/devlane/harness/isolation.py"
        for original in {*profiles.source_pins(root), str(root / owner_path)}:
            target = source / Path(original).relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
        canary = self.world.root / "unvalidated-import"
        profiles.isolation_owner.cache_clear()
        self.addCleanup(profiles.isolation_owner.cache_clear)
        with patch.object(profiles, "__file__", str(source / "ops/devlane/hooks/profiles.py")):
            binding = profiles.generate("codex", self.world.root / "custody-profile", source=source,
                                        cwd=self.repo, mode="interactive", executable="/usr/bin/true",
                                        credential_environment=self.world.env())
            command, _ = profiles.native_launch(binding, ["/usr/bin/true"], self.env)
            owner = source / owner_path
            with self.subTest(closure=True):
                self.assertIn(str(owner), binding["pins"])
            with self.subTest(protection=True):
                self.assertIn(["--ro-bind", str(owner), str(owner)],
                              [command[i:i + 3] for i in range(len(command))])

            def child_exits(*args, **kwargs):
                owner.write_text(owner.read_text() + f"\nPath({str(canary)!r}).touch()\n")
                return 0

            with patch.object(profiles.subprocess, "call", side_effect=child_exits):
                self.assertEqual(profiles.main(["run-interactive", "--binding", binding["binding"]]), 2)
            self.assertFalse(canary.exists(), "changed custody code executed after the child")
            with self.assertRaisesRegex(ValueError, "closure changed"):
                profiles.validate(binding)

    def test_unchanged_interactive_custody_carries_renewal_to_original_home(self):
        root = Path(__file__).resolve().parents[4]
        host = self.world.home / ".codex/auth.json"
        host.parent.mkdir()
        host.write_text('{"synthetic":"original"}')
        os.utime(host, ns=(1, 1))
        binding = profiles.generate("codex", self.world.root / "renewal-profile", source=root,
                                    cwd=self.repo, mode="interactive", executable="/usr/bin/true",
                                    credential_environment=self.world.env())
        renewed = Path(binding["home"]) / "auth.json"
        renewed.write_text('{"synthetic":"renewed"}')
        profiles.isolation_owner.cache_clear()
        self.addCleanup(profiles.isolation_owner.cache_clear)
        with patch.object(profiles.subprocess, "call", return_value=0):
            self.assertEqual(profiles.main(["run-interactive", "--binding", binding["binding"]]), 0)
        self.assertEqual(json.loads(host.read_text()), {"synthetic": "renewed"})
        self.assertTrue(renewed.is_symlink())

    def test_native_protected_set_home_replacement_refuses_interactive_carryback(self):
        root = Path(__file__).resolve().parents[4]
        host = self.world.home / ".codex/auth.json"
        host.parent.mkdir()
        for changed_config in (False, True):
            with self.subTest(changed_config=changed_config):
                host.write_text('{"synthetic":"original"}')
                os.utime(host, ns=(1, 1))
                home = self.world.root / ("native-home-" + str(changed_config))
                home.mkdir()
                saved = home.with_name(home.name + ".before")
                (home / "auth.json").write_text('{"synthetic":"renewed"}')
                binding = profiles.generate("codex", self.world.root / ("native-profile-" + str(changed_config)),
                                            source=root, cwd=self.repo, home=home, mode="interactive",
                                            executable="/usr/bin/true", credential_environment=self.world.env())
                original_inode = home.stat().st_ino

                def child(command, *, changed_config=changed_config, home=home, saved=saved,
                          original_inode=original_inode, binding=binding, **kwargs):
                    # M-332: use exactly the generated protected mounts, with
                    # an inert shell in place of the installed model client.
                    prefix = command[:command.index("--") + 1]
                    script = ('mv "$1" "$2"; mkdir "$1"; '
                              'for name in hooks.json config.toml; do cat "$2/$name" > "$1/$name"; done; '
                              'printf %s "$3" > "$1/auth.json"')
                    if changed_config:
                        script += '; printf "\\n# changed\\n" >> "$1/config.toml"'
                    result = run([*prefix, "/bin/sh", "-ec", script, "fixture", str(home), str(saved),
                                  '{"synthetic":"substituted"}'], cwd=self.repo, env=self.env)
                    self.assertEqual(result.exit, 0, result.stderr)
                    self.assertNotEqual(home.stat().st_ino, original_inode)
                    if not changed_config:
                        profiles.validate(binding)  # Same bytes alone still match.
                    return result.exit

                with patch.object(profiles.subprocess, "call", side_effect=child):
                    self.assertEqual(profiles.main(["run-interactive", "--binding", binding["binding"]]), 2)
                self.assertEqual(json.loads(host.read_text()), {"synthetic": "original"})
                self.assertEqual(json.loads((saved / "auth.json").read_text()), {"synthetic": "renewed"})
                self.assertFalse((home / "auth.json").is_symlink())

    def test_nested_credential_parent_identity_refuses_substitution_but_allows_renewal(self):
        root = Path(__file__).resolve().parents[4]
        leaf = Path(".gemini/antigravity-cli/antigravity-oauth-token")
        host = self.world.home / leaf
        host.parent.mkdir(parents=True)
        for fault in ("replaced", "missing", "symlink", None):
            with self.subTest(fault=fault):
                host.write_text('{"synthetic":"original"}')
                os.utime(host, ns=(1, 1))
                home = self.world.root / ("agy-home-" + str(fault))
                job = home / leaf
                job.parent.mkdir(parents=True)
                job.write_text('{"synthetic":"renewed"}')
                binding = profiles.generate("agy", self.world.root / ("agy-profile-" + str(fault)), source=root,
                                            cwd=self.repo, home=home, mode="interactive", executable="/usr/bin/true",
                                            credential_environment=self.world.env())

                def child(*args, fault=fault, job=job, binding=binding, **kwargs):
                    if fault:
                        saved = job.parent.with_name("auth.before")
                        job.parent.rename(saved)
                        if fault == "symlink":
                            job.parent.symlink_to(saved, target_is_directory=True)
                        elif fault == "replaced":
                            job.parent.mkdir()
                            job.write_text('{"synthetic":"substituted"}')
                        profiles.validate(binding)
                    else:
                        staged = job.with_suffix(".renewed")
                        staged.write_text('{"synthetic":"renewed-again"}')
                        staged.replace(job)
                    return 7

                with patch.object(profiles.subprocess, "call", side_effect=child):
                    self.assertEqual(profiles.main(["run-interactive", "--binding", binding["binding"]]), 2 if fault else 7)
                self.assertEqual(json.loads(host.read_text()), {"synthetic": "original" if fault else "renewed-again"})
                if fault:
                    self.assertEqual(json.loads((job.parent.with_name("auth.before") / leaf.name).read_text()),
                                     {"synthetic": "renewed"})
                else:
                    self.assertTrue(job.is_symlink())

    def test_codex_bound_command_preserves_comments_heredocs_and_explicit_cd(self):
        original = "pwd # trailing comment\ncat <<'END'\nsynthetic\nEND\n"
        command = native.bind_command(original, str(self.repo))
        proc = run(["/bin/sh", "-c", command], cwd=self.world.home, env=self.env)
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertEqual(proc.stdout, str(self.repo) + "\nsynthetic\n")
        self.assertEqual(self.evaluate(command=native.bind_command("git commit -m blocked", str(self.repo)))["outcome"], "deny")

    def test_interactive_preparation_preserves_auth_and_registered_mcp(self):
        import tomllib
        root = Path(__file__).resolve().parents[4]
        original = self.world.home / ".codex"
        original.mkdir()
        (original / "auth.json").write_text('{"synthetic":true}')
        (original / "config.toml").write_text('model = "fixture"\n[features]\nhooks=false\n[mcp_servers.agentscient_lane]\ncommand="python3"\nargs=["stable.py"]\n[mcp_servers.agentscient_lane.env]\nCLAUDE_SESSION_ID="old-parent"\n')
        binding = profiles.prepare_interactive("codex", self.world.root / "prepared", source=root, cwd=self.repo,
                                               agent="Fixture <f@invalid>", executable="/usr/bin/true")
        profiles.validate(profiles.read_binding(binding["binding"]))
        self.assertEqual((Path(binding["home"]) / "auth.json").resolve(), original / "auth.json")
        config = tomllib.loads((Path(binding["home"]) / "config.toml").read_text())
        self.assertTrue(config["features"]["hooks"])
        self.assertFalse(config["features"]["unified_exec_tty"])
        self.assertEqual(config["model"], "fixture")
        server = config["mcp_servers"]["agentscient_lane"]
        self.assertEqual(server["args"], ["stable.py"])
        self.assertEqual(server["env"], {"AGENTSCIENT_HOOK_PROFILE": binding["binding"]})
        self.assertEqual(binding["servers"], ["agentscient_lane"])
        self.assertIn('hooks=false', (original / "config.toml").read_text())
