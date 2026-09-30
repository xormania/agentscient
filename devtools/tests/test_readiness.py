import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_workspaces

from devtools import readiness
from devtools.store import Store
from devtools.workspaces import git


class ReadinessTests(unittest.TestCase):
    setUp = test_workspaces.WorkspaceTests.setUp

    def test_operator_bootstrap_exports_exact_normal_co_connection(self):
        state = self.root / "fresh-state"
        result = subprocess.run(
            [
                sys.executable,
                str(readiness.ENTRY),
                "init",
                "--state",
                str(state),
                "--workspace",
                str(self.checkout),
                "--co",
                "owner",
                "--member",
                "owner:external",
                "--member",
                "chief:codex",
                "--member",
                "worker:codex",
                "--repository",
                "example/project",
                "--serena-image",
                "agentscient-serena:v2-beta",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        config = json.loads((state / "team.json").read_text())
        self.assertEqual({}, config["project"]["development"])
        self.assertEqual("dev", config["project"]["target"])
        connected = subprocess.run(
            [sys.executable, str(readiness.ENTRY), "connection", "--state", str(state)],
            capture_output=True,
            text=True,
            check=True,
        )
        server = json.loads(connected.stdout)["mcpServers"]["agentscient_dev"]
        self.assertEqual([str(readiness.ENTRY), "mcp", "--state", str(state), "--member", "owner"], server["args"])
        self.assertNotIn("--operator", server["args"])
        self.assertEqual([], Store(state).events(kind="launch_requested")["events"])

    def configured(self):
        config = json.loads((self.state / "team.json").read_text())
        config["project"].update(development={}, serena={"image": "agentscient-serena:v2-beta"})
        config["members"][1].update(harness="codex", binary="codex")
        (self.state / "team.json").write_text(json.dumps(config))
        git(self.checkout, "remote", "set-url", "origin", "https://github.com/example/project.git")

    def test_readonly_preflight_checks_protocol_without_claiming_authenticated_acceptance(self):
        self.configured()
        old_config = (self.state / "team.json").read_bytes()
        old_db = (self.state / "live.sqlite3").read_bytes()

        def probe(argv, **kwargs):
            if argv[1:3] == ["image", "inspect"]:
                return json.dumps({"org.opencontainers.image.revision": "b79e2a55f9d4072084977dd35bd07d31146d88b9"})
            return "Fixture 1.2.3"

        with (
            patch("devtools.readiness.probe", side_effect=probe),
            patch("devtools.readiness.platform", return_value="Locked platform satisfied"),
            patch("devtools.readiness.shutil.which", return_value="/fixture/codex"),
            patch("devtools.compat.codex_capability", return_value={"status": "supported"}),
        ):
            result = readiness.doctor(self.state)
            self.assertEqual("preflight_passed", result["status"], result)
            self.assertEqual("not established by preflight", result["authenticated_acceptance"])
            with patch("devtools.compat.codex_capability", return_value={"status": "unsupported"}):
                blocked = readiness.doctor(self.state)
            self.assertEqual("blocked", blocked["status"])
            self.assertEqual("failed", next(c for c in blocked["checks"] if c["name"] == "codex binary")["status"])
        self.assertEqual(old_config, (self.state / "team.json").read_bytes())
        self.assertEqual(old_db, (self.state / "live.sqlite3").read_bytes())

    def test_missing_project_and_mismatched_remote_fail_without_echoing_credentials(self):
        self.configured()
        git(self.checkout, "remote", "set-url", "origin", "https://user:secret-value@github.com/example/other.git")
        with (
            patch("devtools.readiness.platform", return_value="okay"),
            patch("devtools.readiness.probe", side_effect=FileNotFoundError("Dependency unavailable")),
            patch("devtools.readiness.shutil.which", return_value=None),
        ):
            result = readiness.doctor(self.state)
        self.assertEqual("blocked", result["status"])
        self.assertNotIn("secret-value", json.dumps(result))
        self.assertEqual("failed", next(c for c in result["checks"] if c["name"] == "Git remote")["status"])
        config = json.loads((self.state / "team.json").read_text())
        del config["project"]
        (self.state / "team.json").write_text(json.dumps(config))
        with patch("devtools.readiness.shutil.which", return_value=None):
            self.assertEqual("blocked", readiness.doctor(self.state)["status"])

    def assessment_configuration(self, overlay):
        team = json.loads((self.state / "team.json").read_text())
        team["project"]["configuration_file"] = "configuration.json"
        (self.state / "team.json").write_text(json.dumps(team))
        (self.state / "configuration.json").write_text(json.dumps({"version": 1, **overlay}))

    def quiet_doctor(self):
        with (
            patch("devtools.readiness.platform", return_value="Locked platform satisfied"),
            patch("devtools.readiness.probe", side_effect=FileNotFoundError("Dependency unavailable")),
            patch("devtools.readiness.shutil.which", return_value=None),
        ):
            return readiness.doctor(self.state)

    def test_config_inspection_is_readonly_scoped_and_never_reads_the_key(self):
        job = self.api.control.snapshot()["job"]
        self.assessment_configuration({
            "project": {"connection": {"credential": {"file": "unread-key"}},
                        "filtering": {"threshold": 0.1}},
            "roles": {"coder": {"filtering": {"threshold": 0.4}}},
            "jobs": {str(job): {"filtering": {"threshold": 0.7}}},
        })
        database = (self.state / "live.sqlite3").read_bytes()
        with (
            patch("devtools.readiness.read_credential", side_effect=AssertionError("Must not read key")),
            patch("devtools.store.Store.upgrade", side_effect=AssertionError("Must not upgrade state")),
        ):
            settings = readiness.config(self.state, role="coder", job=job)
        self.assertEqual(0.7, settings["filtering"]["threshold"])
        self.assertEqual({"role": "coder", "job": job}, settings["selection"])
        self.assertEqual({"file": str(self.state / "unread-key")}, settings["connection"]["credential"])
        self.assertEqual(64, len(settings["revision"]))
        self.assertEqual(database, (self.state / "live.sqlite3").read_bytes())

    def test_config_cli_reports_effective_settings_and_invalid_selectors(self):
        self.assessment_configuration({"project": {"connection": {"credential": {"file": "absent-key"}}}})
        command = [sys.executable, str(readiness.ENTRY), "config", "--state", str(self.state)]
        result = subprocess.run(command + ["--role", "coder"], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("coder", json.loads(result.stdout)["selection"]["role"])
        invalid = subprocess.run(command + ["--role", "missing_role"], capture_output=True, text=True)
        self.assertEqual(2, invalid.returncode)
        self.assertIn("Unknown configuration role", invalid.stderr)
        self.assertFalse((self.state / "absent-key").exists())

    def test_config_inspection_redacts_secret_text_but_preserves_source_reference(self):
        self.assessment_configuration({"project": {
            "filtering": {"failure_message": "Never expose fixture-secret-123456"},
            "connection": {"credential": {"env": "LOCAL_JEV_KEY"}},
        }})
        with patch.dict(os.environ, {"TEST_PASSWORD": "fixture-secret-123456"}):
            result = readiness.config(self.state)
        self.assertNotIn("fixture-secret-123456", json.dumps(result))
        self.assertEqual({"env": "LOCAL_JEV_KEY"}, result["connection"]["credential"])

    def test_doctor_checks_enabled_role_credentials_locally_without_provider_call(self):
        key = self.state / "local.key"
        key.write_text("fixture-local-key-123456\n")
        key.chmod(0o600)
        self.assessment_configuration({"roles": {"research": {
            "features": {"filtering": True}, "connection": {"credential": {"file": "local.key"}},
        }}})
        with patch("devtools.advice.Jev.evaluate") as provider:
            ready = self.quiet_doctor()
        provider.assert_not_called()
        credential = next(item for item in ready["checks"] if item["name"] == "Jev credential")
        self.assertEqual("passed", credential["status"], ready)
        self.assertEqual(1, credential["detail"]["sources_checked"])
        self.assertNotIn("fixture-local-key-123456", json.dumps(ready))
        key.unlink()
        missing = self.quiet_doctor()
        self.assertEqual("failed", next(item for item in missing["checks"] if item["name"] == "Jev credential")["status"])
        self.assertEqual("blocked", missing["status"])

    def test_doctor_disabled_features_do_not_require_or_read_a_key(self):
        self.assessment_configuration({"project": {"connection": {"credential": {"file": "absent-key"}}}})
        with patch("devtools.readiness.read_credential") as read:
            result = self.quiet_doctor()
        read.assert_not_called()
        self.assertEqual("not_checked", next(item for item in result["checks"] if item["name"] == "Jev credential")["status"])

    def test_doctor_reports_legacy_configuration_as_migration_error(self):
        team = json.loads((self.state / "team.json").read_text())
        team["project"]["jev"] = {}
        (self.state / "team.json").write_text(json.dumps(team))
        result = self.quiet_doctor()
        check = next(item for item in result["checks"] if item["name"] == "assessment configuration")
        self.assertEqual("failed", check["status"])
        self.assertIn("project.configuration_file", check["detail"])
        self.assertEqual("blocked", result["status"])

    def test_platform_probe_uses_locked_real_platform_and_reports_missing_extensions(self):
        result = subprocess.CompletedProcess([], 2, json.dumps([{"name": "ext-mbstring", "status": "missing"}]), "")
        with (
            patch.dict(os.environ, {"COMPOSER_IGNORE_PLATFORM_REQS": "1", "COMPOSER_NO_DEV": "1"}),
            patch("devtools.readiness.subprocess.run", return_value=result) as run,
        ):
            with self.assertRaisesRegex(ValueError, "ext-mbstring"):
                readiness.platform(self.checkout, {"php": "/configured/php", "composer": "composer"})
        self.assertIn("--lock", run.call_args.args[0])
        self.assertIn("--no-plugins", run.call_args.args[0])
        self.assertNotIn("COMPOSER_IGNORE_PLATFORM_REQS", run.call_args.kwargs["env"])
        self.assertNotIn("COMPOSER_NO_DEV", run.call_args.kwargs["env"])
        self.assertTrue(run.call_args.kwargs["env"]["PATH"].startswith("/configured" + os.pathsep))

    def test_evidence_keeps_actual_observations_without_manufacturing_acceptance(self):
        scope = self.api.control.snapshot()
        order, job = scope["work_order"], scope["job"]
        self.store.event("coder", "native_session", native_id="fixture-thread", work_order=order, job=job)
        self.store.event("coder", "serena_call", success=True, work_order=order, job=job)
        self.api.call(
            "work_report",
            {
                "kind": "result",
                "text": "Result evidence",
                "evidence": {"name": "result.txt", "content": "Observed behavior"},
            },
        )
        report = readiness.evidence(self.state, order)
        self.assertEqual({"coder": ["fixture-thread"]}, report["native_sessions"])
        self.assertEqual(1, report["successful_serena_calls"])
        self.assertEqual(1, report["artifact_count"])
        self.assertEqual(1, report["completed_tool_calls"]["work_report"])
        self.assertNotIn("passed", report)
        self.assertIn("does not certify", report["interpretation"])
        self.assertTrue(all(row["acknowledged"] == 0 for row in report["messages"]))
        with self.assertRaisesRegex(ValueError, "No recorded work order"):
            readiness.evidence(self.state, order + 99)


if __name__ == "__main__":
    unittest.main()
