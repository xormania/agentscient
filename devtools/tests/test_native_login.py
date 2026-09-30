import json
import os
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from devtools.harnesses import get
from devtools.launch import initialize
from devtools.profiles import prepare, retain_login
from devtools.store import Store


class NativeLoginTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "login"
        self.source.mkdir()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.state = self.root / "state"
        initialize(self.state, self.workspace, ["owner:external"], co="owner")
        self.store = Store(self.state)
        self.generation = self.store.begin_session("owner", os.getpid())
        self.private = self.state / "profiles" / "owner" / self.generation
        environment = patch.dict(os.environ, {"CODEX_HOME": str(self.source)})
        environment.start()
        self.addCleanup(environment.stop)

    def test_file_login_preserves_native_account_constraints_and_private_isolation(self):
        source = 'cli_auth_credentials_store="file"\nforced_login_method="chatgpt"\nforced_chatgpt_workspace_id="workspace-id"\nfeatures={shell_tool=true}\n'
        (self.source / "config.toml").write_text(source)
        (self.source / "auth.json").write_text('{"refresh_token":"fixture-login"}')
        private, env, _ = prepare(self.state, "owner", "codex")
        settings = tomllib.loads((private / "config.toml").read_text())
        self.assertEqual("file", settings["cli_auth_credentials_store"])
        self.assertEqual("chatgpt", settings["forced_login_method"])
        self.assertEqual("workspace-id", settings["forced_chatgpt_workspace_id"])
        self.assertFalse(settings["features"]["shell_tool"])
        self.assertEqual(str(private), env["CODEX_HOME"])
        self.assertEqual(source, (self.source / "config.toml").read_text())
        self.assertEqual(0o600, (private / "auth.json").stat().st_mode & 0o777)

    def test_ambiguous_keyring_stores_never_copy_a_stale_auth_file(self):
        (self.source / "auth.json").write_text('{"refresh_token":"stale-file-account"}')
        for mode in ("keyring", "auto"):
            with self.subTest(mode=mode):
                (self.source / "config.toml").write_text(f'cli_auth_credentials_store="{mode}"\n')
                with self.assertRaisesRegex(ValueError, "dedicated CODEX_HOME"):
                    prepare(self.state, "owner", "codex")
                self.assertFalse((self.private / "auth.json").exists())
                self.assertFalse((self.private / "login-origin.json").exists())

    def test_readiness_reports_storage_setup_before_any_native_probe(self):
        (self.source / "config.toml").write_text('cli_auth_credentials_store="keyring"\n')
        with patch("devtools.compat.codex_capability") as probe:
            with self.assertRaisesRegex(ValueError, "native-login-storage"):
                get("codex").readiness("codex", None)
        probe.assert_not_called()

    def test_independent_provider_uses_its_credentials_despite_native_keyring_setting(self):
        for selected in ("external", "openai"):
            with self.subTest(native_provider=selected):
                (self.source / "config.toml").write_text(
                    f'model_provider="{selected}"\ncli_auth_credentials_store="keyring"\n'
                    '[model_providers.external]\nname="Fixture"\nbase_url="https://provider.invalid"\n'
                    'env_key="FIXTURE_PROVIDER_KEY"\nrequires_openai_auth=false\n'
                )
                (self.source / "auth.json").write_text('{"refresh_token":"unrelated-account"}')
                config = {"provider": "external"} if selected == "openai" else {}
                private, _, _ = prepare(self.state, "owner", "codex", config=config)
                settings = tomllib.loads((private / "config.toml").read_text())
                self.assertEqual("FIXTURE_PROVIDER_KEY", settings["model_providers"]["external"]["env_key"])
                self.assertEqual("ephemeral", settings["cli_auth_credentials_store"])
                self.assertFalse((private / "auth.json").exists())
                with patch("devtools.compat.codex_capability", return_value={"status": "supported"}):
                    self.assertEqual("ephemeral", get("codex").readiness("codex", None, config=config)["login_storage"])

    def test_provider_override_requiring_native_account_does_not_skip_storage_check(self):
        (self.source / "config.toml").write_text(
            'model_provider="external"\ncli_auth_credentials_store="keyring"\n'
            '[model_providers.external]\nrequires_openai_auth=false\n'
        )
        with self.assertRaisesRegex(ValueError, "dedicated CODEX_HOME"):
            prepare(self.state, "owner", "codex", config={"provider": "openai"})

    def test_ephemeral_mode_does_not_import_or_cache_file_authentication(self):
        (self.source / "auth.json").write_text('{"refresh_token":"fixture-login"}')
        prepare(self.state, "owner", "codex")
        (self.source / "config.toml").write_text('cli_auth_credentials_store="ephemeral"\n')
        private, _, _ = prepare(self.state, "owner", "codex")
        self.assertEqual("ephemeral", tomllib.loads((private / "config.toml").read_text())["cli_auth_credentials_store"])
        self.assertFalse((private / "auth.json").exists())
        self.assertFalse((private / "login-origin.json").exists())
        (private / "auth.json").write_text('{"refresh_token":"must-not-be-retained"}')
        retain_login(self.state, "owner", "codex", self.generation)
        self.assertFalse((private.parent / "codex-login.json").exists())

    def test_removed_source_login_does_not_leave_previous_profile_credentials(self):
        source = self.source / "auth.json"
        source.write_text('{"refresh_token":"fixture-login"}')
        private, _, _ = prepare(self.state, "owner", "codex")
        retain_login(self.state, "owner", "codex", self.generation)
        source.unlink()
        prepare(self.state, "owner", "codex")
        self.assertFalse((private / "auth.json").exists())
        self.assertIsNone(json.loads((private / "login-origin.json").read_text())["source_sha256"])

    def test_login_cache_is_scoped_to_source_home_even_when_contents_match(self):
        other = self.root / "other-login"
        other.mkdir()
        for harness, variable in (("codex", "CODEX_HOME"), ("grok", "GROK_HOME")):
            for contents in (None, '{"refresh_token":"original-login"}'):
                with self.subTest(harness=harness, source_contents=contents):
                    for home in (self.source, other):
                        source = home / "auth.json"
                        source.unlink(missing_ok=True)
                        if contents is not None:
                            source.write_text(contents)
                    with patch.dict(os.environ, {variable: str(self.source)}):
                        private, _, _ = prepare(self.state, "owner", harness)
                        refreshed = '{"refresh_token":"refreshed-private-login"}'
                        (private / "auth.json").write_text(refreshed)
                        retain_login(self.state, "owner", harness, self.generation)
                        prepare(self.state, "owner", harness)
                        self.assertEqual(refreshed, (private / "auth.json").read_text())
                    with patch.dict(os.environ, {variable: str(other)}):
                        prepare(self.state, "owner", harness)
                        if contents is None:
                            self.assertFalse((private / "auth.json").exists())
                        else:
                            self.assertEqual(contents, (private / "auth.json").read_text())

    def test_legacy_login_cache_without_source_identity_is_not_reused(self):
        self.private.parent.mkdir(parents=True, exist_ok=True)
        (self.private.parent / "codex-login.json").write_text(json.dumps(
            {"source_sha256": None, "auth": '{"refresh_token":"unknown-source"}'}
        ))
        private, _, _ = prepare(self.state, "owner", "codex")
        self.assertFalse((private / "auth.json").exists())


if __name__ == "__main__":
    unittest.main()
