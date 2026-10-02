"""Operator entry-point behavior; all command execution is isolated in temp state."""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SENTINEL = "acceptance-test-secret-must-not-be-printed-19d88a"


class AcceptanceScriptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="acceptance-script-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.cwd = self.root / "unrelated working directory"
        self.cwd.mkdir()
        self.checkouts = self.root / "project checkouts"
        self.source = self.checkouts / "agentscient"
        scripts = self.source / "devtools" / "scripts"
        scripts.mkdir(parents=True)
        for name in ("acceptance.sh", "acceptance.py"):
            shutil.copyfile(SCRIPTS / name, scripts / name)
        self.script = scripts / "acceptance.sh"
        self.fixture = self.checkouts / "fixture-ag"
        (self.fixture / "acceptance").mkdir(parents=True)
        (self.fixture / "acceptance" / "run.py").write_text("# fixture marker\n")
        workflow = self.fixture / ".github" / "workflows" / "acceptance.yml"
        workflow.parent.mkdir(parents=True)
        self.workflow = workflow
        self.runtime = self.root / "pinned runtime with spaces"
        self.runtime.mkdir()
        (self.runtime / "README.md").write_text("Temporary pinned runtime\n")
        self.pin = self.initialize_repository(self.runtime, "agentscient")
        self.write_workflow(self.pin)
        self.initialize_repository(self.fixture, "agentscient-test-repo")
        self.run = self.root / "fresh run directory"
        self.config = self.home / ".config" / "agentscient" / "configuration.json"
        self.config.parent.mkdir(parents=True)
        self.config.write_text(json.dumps({
            "version": 1,
            "project": {"connection": {"credential": {"env": "TYPESAFE_API_KEY"}}},
        }))
        probes = self.root / "external command sentinels"
        probes.mkdir()
        for name in ("gh", "codex", "claude", "grok", "docker", "tmux", "php", "composer", "curl", "wget"):
            command = probes / name
            command.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$0" >> "$TEST_COMMAND_LOG"\n'
                f'printf "%s\\n" "{SENTINEL}"\nexit 97\n'
            )
            command.chmod(0o755)
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": str(probes) + os.pathsep + os.environ["PATH"],
            "TEST_COMMAND_LOG": str(self.root / "external-command-calls.log"),
            "XDG_STATE_HOME": str(self.home / ".local" / "state"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "TYPESAFE_API_KEY": SENTINEL,
            "XAI_API_KEY": SENTINEL,
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    @staticmethod
    def git(root, *args):
        result = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=True)
        return result.stdout.strip()

    def initialize_repository(self, root, name):
        self.git(root, "init", "--quiet", "--initial-branch=main")
        self.git(root, "config", "user.name", "Acceptance script tests")
        self.git(root, "config", "user.email", "acceptance-tests@example.invalid")
        self.git(root, "remote", "add", "origin", "https://github.com/uscient/" + name + ".git")
        self.git(root, "add", ".")
        self.git(root, "commit", "--quiet", "-m", "Temporary test fixture")
        self.git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
        return self.git(root, "rev-parse", "HEAD")

    def write_workflow(self, pin):
        self.workflow.write_text(json.dumps({"jobs": {"acceptance": {"steps": [{
            "uses": "actions/checkout@" + "a" * 40,
            "with": {"repository": "uscient/agentscient", "ref": pin},
        }]}}}))

    def module(self):
        spec = importlib.util.spec_from_file_location("acceptance_operator_test", self.script.with_suffix(".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def invoke(self, *args):
        return subprocess.run(
            ["bash", str(self.script), *map(str, args)],
            cwd=self.cwd, env=self.env, text=True, capture_output=True, timeout=15,
        )

    def snapshot(self):
        return {
            str(path.relative_to(self.root)): ("directory" if path.is_dir() else path.read_bytes())
            for path in self.root.rglob("*")
            if not path.is_symlink()
        }

    def test_default_preview_discovers_sibling_from_script_location_without_writing(self):
        before = self.snapshot()
        result = self.invoke()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(str(self.fixture), result.stdout)
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_explicit_paths_with_spaces_are_preserved_in_preview(self):
        result = self.invoke(
            "preview", "--fixture", self.fixture,
            "--configuration", self.config, "--run-dir", self.run,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(str(self.fixture), result.stdout)
        self.assertIn(str(self.run), result.stdout)
        self.assertIn(str(self.config), result.stdout)
        self.assertFalse(self.run.exists())
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)

    def test_sourcing_under_errexit_preserves_calling_shell(self):
        result = subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", 'set -eu; source "$1"; printf "CALLER_SURVIVED\\n"',
             "test-shell", str(self.script)],
            cwd=self.cwd, env=self.env, text=True, capture_output=True, timeout=15,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("CALLER_SURVIVED", result.stdout)
        self.assertFalse(self.run.exists())

    def test_unknown_command_reports_usage_without_traceback_or_secret(self):
        result = self.invoke("not-a-command")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("usage:", result.stderr.lower())
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)

    def test_existing_run_is_preserved(self):
        self.run.mkdir()
        evidence = self.run / "existing-evidence.txt"
        evidence.write_text("keep me\n")
        result = self.invoke("prepare", "--fixture", self.fixture, "--runtime", self.runtime, "--run-dir", self.run)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--run-dir must be new", result.stdout + result.stderr)
        self.assertEqual("keep me\n", evidence.read_text())
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)

    def test_ambiguous_fixture_discovery_requires_explicit_choice(self):
        alternative = self.checkouts / "agentscient-test-repo" / "acceptance"
        alternative.mkdir(parents=True)
        (alternative / "run.py").write_text("# second fixture marker\n")
        result = self.invoke()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--fixture", result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_dirty_or_nonmain_update_stops_before_credentials_or_fetch(self):
        original = self.git(self.fixture, "rev-parse", "HEAD")
        (self.fixture / "local-change.txt").write_text("owner's unfinished work\n")
        dirty = self.invoke("update", "--fixture", self.fixture)
        self.assertNotEqual(0, dirty.returncode)
        self.assertIn("local changes", dirty.stderr)
        self.assertFalse((self.root / "external-command-calls.log").exists())
        (self.fixture / "local-change.txt").unlink()
        self.git(self.fixture, "switch", "--quiet", "-c", "owner-work")
        nonmain = self.invoke("update", "--fixture", self.fixture)
        self.assertNotEqual(0, nonmain.returncode)
        self.assertIn("requires main", nonmain.stderr)
        self.assertEqual("owner-work", self.git(self.fixture, "branch", "--show-current"))
        self.assertEqual(original, self.git(self.fixture, "rev-parse", "HEAD"))
        self.assertFalse((self.root / "external-command-calls.log").exists())

    def test_wrong_runtime_pin_stops_before_readiness_or_provider_calls(self):
        self.write_workflow("2" * 40)
        self.git(self.fixture, "add", ".github/workflows/acceptance.yml")
        self.git(self.fixture, "commit", "--quiet", "-m", "Select another runtime")
        self.git(self.fixture, "update-ref", "refs/remotes/origin/main", "HEAD")
        result = self.invoke("check", "--fixture", self.fixture, "--runtime", self.runtime, "--online")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("does not match fixture pin", result.stderr)
        self.assertFalse((self.root / "external-command-calls.log").exists())
        self.assertEqual(self.pin, self.git(self.runtime, "rev-parse", "HEAD"))

    def test_failed_preflight_cannot_prepare_or_create_run(self):
        helper = self.module()
        args = helper.parser().parse_args(["prepare", "--run-dir", str(self.run)])
        with patch.object(helper, "preflight", return_value=False) as preflight, \
                patch.object(helper.subprocess, "call") as execute:
            self.assertEqual(1, helper.prepare(args, self.fixture, self.runtime, object()))
        preflight.assert_called_once()
        self.assertTrue(preflight.call_args.kwargs["online"])
        execute.assert_not_called()
        self.assertFalse(self.run.exists())

    def test_successful_preflight_forwards_paths_to_fixture_without_launching_models(self):
        helper = self.module()
        entry = self.fixture / "acceptance" / "run.py"
        entry.write_text(
            "import json, pathlib, sys\n"
            "args = sys.argv[1:]\n"
            "root = pathlib.Path(args[args.index('--run-dir') + 1])\n"
            "root.mkdir()\n"
            "(root / 'forwarded.json').write_text(json.dumps(args))\n"
        )
        args = helper.parser().parse_args([
            "prepare", "--run-dir", str(self.run), "--configuration", str(self.config),
            "--harness", "codex", "--harness", "grok", "--php", "/owned php/bin/php",
        ])
        with patch.object(helper, "preflight", return_value=True), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, helper.prepare(args, self.fixture, self.runtime, object()))
        forwarded = json.loads((self.run / "forwarded.json").read_text())
        self.assertEqual("prepare", forwarded[0])
        for name, expected in (("--run-dir", self.run), ("--agentscient", self.runtime),
                               ("--configuration", self.config), ("--php", "/owned php/bin/php")):
            self.assertEqual(str(expected), forwarded[forwarded.index(name) + 1])
        self.assertEqual(["codex", "grok"], [forwarded[index + 1] for index, value in enumerate(forwarded)
                                              if value == "--harness"])
        self.assertFalse((self.root / "external-command-calls.log").exists())

    def frozen_run(self, body):
        self.run.mkdir()
        runner = self.run / "verifier" / "acceptance" / "run.py"
        runner.parent.mkdir(parents=True)
        runner.write_text(body)
        run_id = "9" * 32
        manifest = {
            "version": 1, "repository": "uscient/agentscient-test-repo", "run_id": run_id,
            "run_root": str(self.run), "target": "acceptance/" + run_id, "status": "prepared",
            "agentscient_root": str(self.runtime), "agentscient_sha": self.pin,
        }
        (self.run / "run.json").write_text(json.dumps(manifest))

    def test_status_only_reads_manifest_even_if_frozen_runner_would_execute(self):
        marker = self.run / "UNEXPECTED_EXECUTION"
        self.frozen_run("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n")
        self.workflow.write_text("Invalid live fixture workflow must not matter for existing runs\n")
        before = self.snapshot()
        result = self.invoke("status", "--run-dir", self.run / "run.json")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('"status": "prepared"', result.stdout)
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(marker.exists())

    def test_existing_run_uses_its_frozen_cli_and_cannot_select_another_fixture(self):
        self.frozen_run("import json, sys\nprint(json.dumps(sys.argv[1:]))\n")
        self.workflow.write_text("Invalid live fixture workflow must not matter for existing runs\n")
        result = self.invoke("doctor", "--run-dir", self.run, "--online")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(["doctor", "--run-dir", str(self.run), "--online"], json.loads(result.stdout))
        rejected = self.invoke("doctor", "--run-dir", self.run, "--fixture", self.fixture)
        self.assertNotEqual(0, rejected.returncode)
        self.assertIn("unrecognized arguments", rejected.stderr)
        self.assertNotIn(SENTINEL, result.stdout + result.stderr + rejected.stdout + rejected.stderr)

    def test_owned_toolchain_defaults_are_forwarded_and_explicit_overrides_win(self):
        helper = self.module()
        tag = "ci-toolchain-selected-runtime-1"
        manifest = self.runtime / ".github" / "actions" / "php-runtime" / "toolchain.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"tag": tag}))
        owned = Path(self.env["XDG_STATE_HOME"]) / "agentscient" / "toolchains" / tag
        owned.mkdir(parents=True)
        for name in ("php", "composer"):
            (owned / name).write_text("owned executable placeholder\n")
        entry = self.fixture / "acceptance" / "run.py"
        entry.write_text(
            "import json, pathlib, sys\n"
            "args = sys.argv[1:]\n"
            "root = pathlib.Path(args[args.index('--run-dir') + 1])\n"
            "root.mkdir()\n"
            "(root / 'forwarded.json').write_text(json.dumps(args))\n"
        )
        args = helper.parser().parse_args(["prepare", "--run-dir", str(self.run)])
        observed = []

        def checked(options, _fixture, runtime, _runner, *, online):
            self.assertTrue(online)
            observed.append(helper.development_commands(options, runtime))
            return True

        with patch.dict(os.environ, self.env, clear=True), \
                patch.object(helper, "preflight", side_effect=checked), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, helper.prepare(args, self.fixture, self.runtime, object()))
            explicit = helper.parser().parse_args([
                "prepare", "--run-dir", str(self.root / "another run"),
                "--php", "/explicit php/bin/php", "--composer", "/explicit composer/bin/composer",
            ])
            self.assertEqual(("/explicit php/bin/php", "/explicit composer/bin/composer"),
                             helper.development_commands(explicit, self.runtime))
            explicit.composer = "composer"
            self.assertEqual(("/explicit php/bin/php", "composer"), helper.development_commands(explicit, self.runtime))
        expected = (str(owned / "php"), str(owned / "composer"))
        self.assertEqual([expected], observed)
        forwarded = json.loads((self.run / "forwarded.json").read_text())
        self.assertEqual(expected, tuple(forwarded[forwarded.index(name) + 1] for name in ("--php", "--composer")))
        self.assertFalse((self.root / "external-command-calls.log").exists())

    def test_nonobject_run_manifest_fails_without_executing_frozen_code(self):
        marker = self.run / "UNEXPECTED_EXECUTION"
        self.frozen_run("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n")
        for value in ([], None, 17, SENTINEL):
            with self.subTest(value_type=type(value).__name__):
                (self.run / "run.json").write_text(json.dumps(value))
                result = self.invoke("status", "--run-dir", self.run)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("Invalid run manifest", result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)
                self.assertNotIn(SENTINEL, result.stdout + result.stderr)
                self.assertFalse(marker.exists())

    def test_failed_credential_probe_does_not_echo_secret_output(self):
        helper = self.module()
        output = io.StringIO()
        with patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stdout(output):
            self.assertFalse(helper.native_credentials(["codex", "claude"]))
            with self.assertRaises(helper.SetupError) as caught:
                helper.github_access()
        self.assertNotIn(SENTINEL, output.getvalue() + str(caught.exception))
        self.assertIn("FAIL codex", output.getvalue())
        self.assertIn("FAIL claude", output.getvalue())
        self.assertIn("GitHub login is unavailable", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
