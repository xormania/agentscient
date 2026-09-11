"""LD-18 (2026-09-11): a grok credential older than its refresh lifetime.

The CLI refreshes the token inside each isolated job home and writes the
new refresh token there; the host file keeps the one from the login, and
that one aged out about 30 hours after `create_time` (a refresh from it
was accepted at 29.4 h, records 3ab0c7; two dispatches died `Not signed
in` at 30.1 h, records dddd49 and 70b92e). The launcher now refuses such
a credential before the mint, naming the login command, instead of
running a worker that fails in a way that looks like a model refusal.
"""

import datetime
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]


def _isolation():
    spec = importlib.util.spec_from_file_location(
        "isolation_under_test", HARNESS / "isolation.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _stamp(hours_ago):
    at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)
    return at.strftime("%Y-%m-%dT%H:%M:%S.%f") + "000Z"  # the CLI writes nanoseconds


class ACredentialPastItsRefreshLifetimeIsRefused(unittest.TestCase):
    def setUp(self):
        self.iso = _isolation()
        self.tmp = Path(tempfile.mkdtemp(prefix="cred-age-"))
        self.home = self.tmp / "home"
        self.env = {"HOME": str(self.home)}

    def plant(self, harness, body):
        path = self.home / f".{harness}" / "auth.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def credential(self, hours_ago):
        return json.dumps({"https://auth.x.ai::client": {
            "key": "k", "refresh_token": "r", "create_time": _stamp(hours_ago)}})

    def build(self, harness, name):
        return Path(self.iso.build_home(harness, self.tmp / name, env=self.env))

    def test_a_grok_credential_older_than_the_lifetime_is_refused_naming_the_login(self):
        self.plant("grok", self.credential(31))
        with self.assertRaises(self.iso.NotIsolated) as caught:
            self.build("grok", "old")
        text = str(caught.exception)
        self.assertIn("create_time", text)
        self.assertIn("grok login --device-code", text)
        self.assertFalse((self.tmp / "old" / "auth.json").exists(),
                         "no credential link is left in a refused home")

    def test_a_fresh_grok_credential_builds_the_home(self):
        self.plant("grok", self.credential(1))
        home = self.build("grok", "fresh")
        self.assertEqual(sorted(p.name for p in home.iterdir()), ["auth.json"])

    def test_a_credential_without_create_time_is_not_aged(self):
        # Test fixtures across the lane plant "{}" for grok; the check reads
        # only what the CLI wrote and has no opinion on a file without it.
        self.plant("grok", "{}\n")
        home = self.build("grok", "blank")
        self.assertEqual(sorted(p.name for p in home.iterdir()), ["auth.json"])

    def test_the_rule_is_declared_per_harness_and_codex_carries_none(self):
        self.assertIn("credential_age", self.iso.HARNESSES["grok"])
        self.assertNotIn("credential_age", self.iso.HARNESSES["codex"])
        self.plant("codex", self.credential(31))
        home = self.build("codex", "codex")
        self.assertEqual(sorted(p.name for p in home.iterdir()), ["auth.json"])


if __name__ == "__main__":
    unittest.main()
