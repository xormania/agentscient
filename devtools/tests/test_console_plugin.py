import json
import shlex
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from support import fixture_environment

from devtools.api import SERVER
from devtools.console_plugin import GENERATION_ENV, grok_plugin


class ConsolePluginTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.private = self.root / "private" / uuid.uuid4().hex
        self.private.mkdir(parents=True)
        self.server_name = SERVER + "_" + self.private.name
        self.output = self.root / "observed"
        self.original = [sys.executable, "-c", "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('ran')",
                         str(self.output)]
        self.server = {"command": self.original[0], "args": self.original[1:]}
        self.hooks = {"SessionStart": [{"hooks": [{"type": "command", "timeout": 10,
                        "command": shlex.join(self.original)}]}]}
        (self.private / "observer-hooks.json").write_text(json.dumps(self.hooks))

    def test_additive_manifest_preserves_configuration_and_concurrent_native_edits(self):
        grok = self.workspace / ".grok"
        grok.mkdir()
        config = grok / "config.toml"
        original = '# native formatting stays intact\n[models]\ndefault="owner-model"\n'
        config.write_text(original)
        with grok_plugin(self.private, self.server, self.workspace) as plugin:
            self.assertEqual(original, config.read_text())
            manifest = json.loads((plugin / "plugin.json").read_text())
            self.assertEqual({self.server_name}, set(manifest["mcpServers"]))
            self.assertEqual("stdio", manifest["mcpServers"][self.server_name]["type"])
            self.assertEqual({"SessionStart"}, set(manifest["hooks"]["hooks"]))
            self.assertNotIn(GENERATION_ENV, manifest["mcpServers"][self.server_name].get("env", {}))
            config.write_text(original + '[ui]\ntheme="native-choice"\n')
        self.assertEqual(original + '[ui]\ntheme="native-choice"\n', config.read_text())
        self.assertFalse(plugin.exists())
        self.assertFalse((grok / "plugins").exists())

    def test_cleanup_on_native_exit_error_removes_only_own_files(self):
        with self.assertRaisesRegex(RuntimeError, "native exited"):
            with grok_plugin(self.private, self.server, self.workspace):
                raise RuntimeError("native exited")
        self.assertFalse((self.workspace / ".grok").exists())

    def test_changed_manifest_and_added_files_survive_cleanup(self):
        with grok_plugin(self.private, self.server, self.workspace) as plugin:
            (plugin / "plugin.json").write_text('{"name":"operator-edited"}\n')
            (plugin / "notes.txt").write_text("operator notes")
        self.assertEqual('{"name":"operator-edited"}\n', (plugin / "plugin.json").read_text())
        self.assertEqual("operator notes", (plugin / "notes.txt").read_text())

    def test_existing_plugin_collision_is_never_overwritten(self):
        plugin = self.workspace / ".grok" / "plugins" / ("agentscient-co-" + self.private.name)
        plugin.mkdir(parents=True)
        (plugin / "plugin.json").write_text("existing")
        with self.assertRaises(FileExistsError):
            with grok_plugin(self.private, self.server, self.workspace):
                self.fail("Existing plugin must not be entered")
        self.assertEqual("existing", (plugin / "plugin.json").read_text())

    def test_mcp_and_hooks_run_only_in_matching_operator_environment(self):
        with grok_plugin(self.private, self.server, self.workspace) as plugin:
            manifest = json.loads((plugin / "plugin.json").read_text())
            server = manifest["mcpServers"][self.server_name]
            commands = ([server["command"], *server["args"]],
                        shlex.split(manifest["hooks"]["hooks"]["SessionStart"][0]["hooks"][0]["command"]))
            for command in commands:
                for marker in (None, uuid.uuid4().hex, self.private.name):
                    with self.subTest(kind=command[-1], generation=marker):
                        self.output.unlink(missing_ok=True)
                        environment = fixture_environment(self.root)
                        if marker is not None:
                            environment[GENERATION_ENV] = marker
                        subprocess.run(command, env=environment, capture_output=True, check=True, timeout=5)
                        self.assertEqual(marker == self.private.name, self.output.exists())

    def test_concurrent_console_plugins_have_distinct_server_names(self):
        other = self.private.parent / uuid.uuid4().hex
        other.mkdir()
        (other / "observer-hooks.json").write_text(json.dumps(self.hooks))
        with grok_plugin(self.private, self.server, self.workspace) as first:
            with grok_plugin(other, self.server, self.workspace) as second:
                first_servers = json.loads((first / "plugin.json").read_text())["mcpServers"]
                second_servers = json.loads((second / "plugin.json").read_text())["mcpServers"]
                self.assertFalse(set(first_servers) & set(second_servers))
            self.assertTrue(first.is_dir())
            self.assertFalse(second.exists())

    def test_generated_permission_hook_is_rejected_before_touching_workspace(self):
        (self.private / "observer-hooks.json").write_text(json.dumps({"PreToolUse": []}))
        with self.assertRaisesRegex(ValueError, "observe"):
            with grok_plugin(self.private, self.server, self.workspace):
                self.fail("Permission hook must not be registered")
        self.assertFalse((self.workspace / ".grok").exists())


if __name__ == "__main__":
    unittest.main()
