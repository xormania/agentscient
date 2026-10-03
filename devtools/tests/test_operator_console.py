"""Operator console privileges do not leak into managed role profiles."""

import copy
import json
import os
import tomllib
import unittest
from unittest.mock import patch

from fixtures.native_boundaries import NativeBoundaryFixture
from support import runtime_policy

from devtools import role_packages, runtime
from devtools.api import API
from devtools.console import command
from devtools.profiles import hook, prepare


class OperatorConsoleTests(NativeBoundaryFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.team_file = self.directory / "team.json"
        self.team = json.loads(self.team_file.read_text())
        self.team["co"] = "owner"
        self.team_file.write_text(json.dumps(self.team))

    def config(self, harness):
        return {"binary": "fixture", "workspace": str(self.workspace), "harness": harness,
                "model": "initial-model", "reasoning": "high", "operator_console": True}

    def test_claude_owner_keeps_native_controls_and_observes_without_tool_denial(self):
        config = self.config("claude")
        native_environment = {"CLAUDE_CODE_SIMPLE": "1", "CLAUDE_CODE_SAFE_MODE": "1",
                              "CLAUDE_CONFIG_DIR": str(self.home / "custom-claude")}
        with patch.dict(os.environ, native_environment):
            private, environment, server = prepare(self.directory, "owner", "claude", config=config)
        argv, _ = command(self.directory, "owner", config, private, server)
        for flag in ("--disable-slash-commands", "--setting-sources", "--strict-mcp-config",
                     "--tools", "--disallowedTools", "--allowedTools"):
            self.assertNotIn(flag, argv)
        self.assertEqual("initial-model", argv[argv.index("--model") + 1])
        self.assertEqual("high", argv[argv.index("--effort") + 1])
        self.assertEqual(str(self.home), environment["HOME"])
        self.assertEqual(native_environment, {name: environment.get(name) for name in native_environment})
        self.assertEqual({"SessionStart", "PostToolUse", "Stop"},
                         set(json.loads((private / "settings.json").read_text())["hooks"]))
        self.assertNotIn("--operator", server["args"])
        self.assertEqual("owner", server["args"][server["args"].index("--member") + 1])
        api = API(self.directory, "owner")
        exposed = {row["name"] for row in api._tools(api.control.snapshot())}
        self.assertIn("work_report", exposed)
        self.assertNotIn("orchestrate", exposed)
        with self.assertRaisesRegex(ValueError, "not available"):
            api.call("orchestrate", {"work": []})

    def test_codex_owner_keeps_native_home_keyring_and_configuration(self):
        original = self.home / "codex"
        original.mkdir()
        settings = ('cli_auth_credentials_store = "keyring"\n'
                    'features = { multi_agent = true, shell_tool = true, plugins = true }\n'
                    'sandbox_mode = "workspace-write"\n'
                    'approval_policy = "never"\n'
                    'developer_instructions = "Owner instructions"\n'
                    'mcp_servers = { personal = { command = "personal-server" } }\n')
        (original / "config.toml").write_text(settings)
        config = self.config("codex") | {"provider": "chosen-provider"}
        private, environment, server = prepare(self.directory, "owner", "codex", config=config)
        argv, _ = command(self.directory, "owner", config, private, server)
        self.assertEqual(str(original), environment["CODEX_HOME"])
        self.assertEqual(str(self.home), environment["HOME"])
        self.assertEqual(settings, (original / "config.toml").read_text())
        self.assertFalse((private / "config.toml").exists())
        overrides = [argv[index + 1] for index, arg in enumerate(argv) if arg == "-c"]
        options = tomllib.loads("\n".join(overrides))
        self.assertTrue(any(row.startswith("mcp_servers.agentscient_dev=") for row in overrides))
        self.assertFalse(any(row.startswith("mcp_servers=") for row in overrides))
        self.assertEqual(server, options["mcp_servers"]["agentscient_dev"])
        self.assertEqual("initial-model", options["model"])
        self.assertEqual("high", options["model_reasoning_effort"])
        self.assertEqual("chosen-provider", options["model_provider"])
        for key in ("features", "sandbox_mode", "approval_policy", "developer_instructions"):
            self.assertNotIn(key, options)
        self.assertEqual({"SessionStart", "PostToolUse", "Stop"}, set(options["hooks"]))
        self.assertNotIn("--operator", server["args"])

    def test_operator_mode_requires_appointed_external_co_before_creating_profiles(self):
        scenarios = (("unappointed", "owner"), ("other-member", "worker"),
                     ("appointed-worker", "worker"), ("nonexternal", "owner"),
                     ("stored-managed", "owner"))
        for scenario, member in scenarios:
            with self.subTest(scenario=scenario):
                team = copy.deepcopy(self.team)
                if scenario == "unappointed":
                    del team["co"]
                elif scenario == "appointed-worker":
                    team["co"] = "worker"
                elif scenario == "nonexternal":
                    next(row for row in team["members"] if row["name"] == "owner")["harness"] = "claude"
                elif scenario == "stored-managed":
                    with self.store.connect() as db:
                        db.execute("UPDATE members SET harness='claude' WHERE name='owner'")
                self.team_file.write_text(json.dumps(team))
                with self.assertRaises(ValueError):
                    prepare(self.directory, member, "claude", config=self.config("claude"))
                self.assertFalse((self.directory / "profiles").exists())

    def test_grok_owner_keeps_native_settings_and_worker_drops_operator_marker(self):
        original = self.home / "grok"
        original.mkdir()
        settings = 'subagents = { enabled = true }\nworkflows = { enabled = true }\n'
        (original / "config.toml").write_text(settings)
        native = {"GROK_SUBAGENTS": "1", "GROK_WORKFLOWS": "1", "GROK_GOAL": "1",
                  "GROK_CONFIG_DIR": str(original), "AGENTSCIENT_CO_GENERATION": "inherited"}
        config = self.config("grok")
        with patch.dict(os.environ, native):
            private, environment, server = prepare(self.directory, "owner", "grok", config=config)
            _, worker_environment, _ = prepare(self.directory, "worker", "grok")
        argv, _ = command(self.directory, "owner", config, private, server)
        self.assertEqual(str(self.home), environment["HOME"])
        self.assertEqual(str(original), environment["GROK_HOME"])
        for key in ("GROK_SUBAGENTS", "GROK_WORKFLOWS", "GROK_GOAL", "GROK_CONFIG_DIR"):
            self.assertEqual(native[key], environment[key])
        self.assertEqual(private.name, environment["AGENTSCIENT_CO_GENERATION"])
        self.assertNotIn("AGENTSCIENT_CO_GENERATION", worker_environment)
        self.assertEqual(settings, (original / "config.toml").read_text())
        self.assertFalse((private / "config.toml").exists())
        self.assertNotIn("PreToolUse", json.loads((private / "observer-hooks.json").read_text()))
        for flag in ("--tools", "--no-subagents", "--no-memory", "--disable-web-search"):
            self.assertNotIn(flag, argv)
        self.assertEqual("initial-model", argv[argv.index("--model") + 1])
        self.assertEqual("high", argv[argv.index("--effort") + 1])

    def test_co_behavior_alias_and_initial_unbound_owner_can_use_operator_console(self):
        packages = copy.deepcopy(role_packages.catalog())
        packages["roles"]["liaison"] = packages["roles"]["co"]
        packages["defaults"]["co"] = "liaison"
        with patch.object(role_packages, "_catalog", return_value=packages):
            for bound in (True, False):
                with self.subTest(bound=bound):
                    with self.store.connect() as db:
                        if bound:
                            db.execute("UPDATE member_bindings SET role='liaison' WHERE member='owner'")
                        else:
                            db.execute("DELETE FROM member_bindings WHERE member='owner'")
                    config = self.config("claude")
                    private, _, server = prepare(self.directory, "owner", "claude", config=config)
                    argv, _ = command(self.directory, "owner", config, private, server)
                    self.assertNotIn("--disable-slash-commands", argv)
                    self.assertNotIn("PreToolUse", json.loads((private / "settings.json").read_text())["hooks"])

    def test_runtime_profiles_cannot_enable_internal_operator_mode(self):
        policy = runtime_policy()
        policy["profiles"]["claude"]["operator_console"] = True
        with self.assertRaisesRegex(ValueError, "Unknown runtime profile field"):
            runtime.validate(policy, runtime.vendor_defaults(policy))

    def test_native_session_change_updates_console_metadata_only(self):
        generation = self.store.begin_session("owner", os.getpid())
        self.store.session("owner", generation=generation, native_id="original",
                           detail={"transport": "interactive/pty"})
        payload = {"hook_event_name": "SessionStart", "session_id": "resumed", "model": "user-choice"}
        self.assertEqual({}, hook(self.directory, "owner", "claude", payload, generation=generation))
        self.assertEqual("resumed", self.store.member("owner")["native_id"])
        self.store.session("worker", generation=self.generation, native_id="worker-session",
                           detail={"transport": "interactive/pty"})
        hook(self.directory, "worker", "claude", payload, generation=self.generation)
        self.assertEqual("worker-session", self.store.member("worker")["native_id"])
