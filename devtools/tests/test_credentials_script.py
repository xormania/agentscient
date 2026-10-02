"""Credential tests never use real accounts, credential stores or API requests."""

import base64
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "credentials.py"
SPEC = importlib.util.spec_from_file_location("manual_credentials_script", SCRIPT)
credentials = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(credentials)
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
SENTINEL = "credential-secret-never-print"


def jwt(exp):
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp, "email": SENTINEL}).encode()).decode().rstrip("=")
    return "header." + payload + ".signature"


class CredentialScriptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="credential-check-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {"HOME": str(self.root), "PATH": os.environ["PATH"]}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        binaries = patch.object(credentials.shutil, "which", return_value="/fake/client")
        binaries.start()
        self.addCleanup(binaries.stop)

    def document(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        return path

    def check(self, service, online=False):
        row = credentials.check(service, online=online, repos=["uscient/agentscient"], now=NOW, days=7)
        self.assertNotIn(SENTINEL, json.dumps(row))
        return row

    def test_offline_inventory_never_launches_clients_or_network(self):
        self.document(".codex/auth.json", {"tokens": {"access_token": jwt((NOW + timedelta(days=2)).timestamp())}})
        with patch.object(credentials, "native", side_effect=AssertionError("native ran")), \
             patch.object(credentials, "request_json", side_effect=AssertionError("network ran")):
            row = self.check("codex")
        self.assertEqual((row["stored"], row["status"], row["expiry"]), ("present", "incomplete", "soon"))
        self.assertEqual(row["expires_at"], "2026-10-04T00:00:00Z")

    def test_expired_access_does_not_claim_subscription_expired(self):
        self.document(".claude/.credentials.json", {"claudeAiOauth": {
            "accessToken": SENTINEL, "refreshToken": SENTINEL, "expiresAt": (NOW.timestamp() - 60) * 1000,
        }})
        with patch.object(credentials, "native", return_value=SENTINEL):
            row = self.check("claude", online=True)
        self.assertEqual(row["expiry"], "expired")
        self.assertEqual(row["status"], "incomplete")
        self.assertIn("refresh may still work", row["expiry_note"])

    def test_bad_credential_files_are_redacted_and_not_followed(self):
        path = self.document(".grok/auth.json", {"access_token": SENTINEL})
        for broken in ("permissions", "malformed", "symlink"):
            with self.subTest(broken=broken):
                if broken == "permissions":
                    path.chmod(0o644)
                elif broken == "malformed":
                    path.chmod(0o600)
                    path.write_text(SENTINEL)
                else:
                    path.unlink()
                    path.symlink_to(self.document("outside.json", {"access_token": SENTINEL}))
                self.assertEqual(self.check("grok")["status"], "failed")

    def test_opaque_and_invalid_jwt_expiry_stays_unknown(self):
        for value in (SENTINEL, "x.!.y", jwt("not-a-date"), jwt(True), jwt(1e100)):
            with self.subTest(value=value[:8]):
                self.assertIsNone(credentials.jwt_expiry(value))
        self.assertEqual(credentials.expiry_report(None, NOW, 7)["expires_at"], None)

    def test_codex_subscription_does_not_probe_unrelated_env_api_key(self):
        os.environ["OPENAI_API_KEY"] = SENTINEL
        self.document(".codex/auth.json", {"auth_mode": "chatgpt", "tokens": {
            "access_token": jwt((NOW + timedelta(days=9)).timestamp()),
        }})
        with patch.object(credentials, "native", return_value=SENTINEL), \
             patch.object(credentials, "request_json") as api:
            row = self.check("codex", online=True)
        api.assert_not_called()
        self.assertEqual(row["status"], "incomplete")
        self.assertIn("no supported", row["live"])

    def test_codex_provider_override_and_inactive_token_do_not_mislead(self):
        self.document(".codex/auth.json", {"auth_mode": "apikey", "OPENAI_API_KEY": SENTINEL,
                                             "tokens": {"access_token": jwt(NOW.timestamp() - 60)}})
        with patch.object(credentials, "native", return_value=""), \
             patch.object(credentials, "request_json", return_value={"data": []}) as api:
            row = self.check("codex", online=True)
            self.assertEqual(row["status"], "verified")
            self.assertIsNone(row["expires_at"])
            api.reset_mock()
            (self.root / ".codex/config.toml").write_text('[model_providers.openai]\nbase_url="https://proxy.invalid/v1"\n')
            self.assertEqual(self.check("codex", online=True)["status"], "incomplete")
            api.assert_not_called()

    def test_malformed_settings_and_api_shapes_are_reported_as_failures(self):
        root = self.root / ".codex"
        root.mkdir()
        (root / "config.toml").write_text("cli_auth_credentials_store=[]\n")
        self.assertEqual(self.check("codex")["status"], "failed")
        with patch.object(credentials, "native", side_effect=["", 'HTTP/2 200\n\n{"id":42}',
                                                              '{"full_name":{"unexpected":"object"}}']):
            self.assertEqual(self.check("github", online=True)["status"], "failed")

    def test_api_key_checks_distinguish_authentication_from_native_selection(self):
        os.environ["ANTHROPIC_API_KEY"] = SENTINEL
        with patch.object(credentials, "native", return_value=""), \
             patch.object(credentials, "request_json", return_value={"data": []}) as api:
            row = self.check("claude", online=True)
        self.assertEqual(api.call_args.args[0], "https://api.anthropic.com/v1/models?limit=1")
        self.assertEqual(api.call_args.args[1]["x-api-key"], SENTINEL)
        self.assertEqual(row["status"], "incomplete")
        self.assertIn("selection unverified", row["live"])

    def test_grok_key_block_and_agy_provider_selection(self):
        os.environ.update(XAI_API_KEY=SENTINEL, GEMINI_API_KEY=SENTINEL)
        with patch.object(credentials, "request_json", return_value={
                "api_key_disabled": True, "api_key_blocked": False, "team_blocked": False}):
            self.assertEqual(self.check("grok", online=True)["status"], "failed")
        with patch.object(credentials, "request_json", return_value={"models": []}) as api:
            self.assertEqual(self.check("agy", online=True)["status"], "incomplete")
            api.assert_not_called()
            self.document(".gemini/antigravity-cli/settings.json", {"modelProvider": "gemini"})
            self.assertEqual(self.check("agy", online=True)["status"], "verified")

    def test_github_header_expiry_repo_reads_and_no_identity_leak(self):
        output = "HTTP/2.0 200 OK\r\nGitHub-Authentication-Token-Expiration: 2026-10-05 00:00:00 UTC\r\n\r\n"
        output += json.dumps({"id": 42, "login": SENTINEL})
        with patch.object(credentials, "native", side_effect=[SENTINEL, output, json.dumps({
                "full_name": "uscient/agentscient", "permissions": {"push": True}, "owner": SENTINEL})]):
            row = self.check("github", online=True)
        self.assertEqual(row["status"], "verified")
        self.assertEqual(row["expiry"], "soon")
        self.assertTrue(row["repositories"][0]["push"])
        with patch.object(credentials, "native", side_effect=["", "HTTP/2 200\n\n{\"id\":42}", json.dumps({
                "full_name": "uscient/agentscient"})]):
            row = self.check("github", online=True)
        self.assertIsNone(row["expires_at"])
        self.assertIsNone(row["repositories"][0]["push"])

    def test_native_and_http_failure_details_are_never_echoed(self):
        with patch.object(credentials.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, SENTINEL)):
            row = self.check("github", online=True)
        self.assertEqual(row["status"], "failed")
        opener = unittest.mock.Mock()
        opener.open.side_effect = HTTPError("https://api.x.ai/" + SENTINEL, 401, SENTINEL, {}, None)
        with patch.object(credentials, "build_opener", return_value=opener):
            with self.assertRaisesRegex(credentials.CheckError, "HTTP 401") as caught:
                credentials.request_json("https://api.x.ai/v1/api-key", {})
        self.assertNotIn(SENTINEL, str(caught.exception))
        self.assertIsNone(credentials.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))

    def test_json_report_exit_code_and_source_guard(self):
        os.environ["GEMINI_API_KEY"] = SENTINEL
        self.document(".gemini/antigravity-cli/settings.json", {"modelProvider": "gemini"})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = credentials.main(["--service", "agy", "--json"])
        self.assertEqual(code, 2)
        self.assertNotIn(SENTINEL, output.getvalue())
        self.assertFalse(json.loads(output.getvalue())["online"])
        source = subprocess.run(["bash", "-c", 'set -eu; source "$1"; printf "alive:%s" "$-"',
                                 "bash", str(SCRIPT.with_suffix(".sh"))], text=True, capture_output=True)
        self.assertEqual(source.returncode, 0)
        self.assertIn("alive:", source.stdout)
        self.assertIn("e", source.stdout.rsplit("alive:", 1)[1])


if __name__ == "__main__":
    unittest.main()
