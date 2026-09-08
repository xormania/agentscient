"""Bounded agy isolation tests, from the public isolation contract.

Pinned from isolation.py's module contract, dispatch/CONTRACT.md's
isolation seam, and the 2026-09-08 host observation: HOME isolation,
`.gemini/antigravity-cli` credential base, `brain` session root, only
the `antigravity-oauth-token` leaf, no settings/history copy, no
real-HOME fallback. Synthetic fixtures only.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

import support  # noqa: F401  (puts the harness dir on sys.path)

import isolation


AUTH_REL = ".gemini/antigravity-cli/antigravity-oauth-token"
SETTINGS_REL = ".gemini/antigravity-cli/settings.json"
HISTORY_REL = ".gemini/antigravity-cli/history"
SESSION_REL = ".gemini/antigravity-cli/brain"
SYNTHETIC_TOKEN = "synthetic-agy-oauth-token\n"
SETTINGS_CANARY = "settings-canary\n"
HISTORY_CANARY = "history-canary\n"


def _file_leaves(root: Path) -> list[str]:
    leaves = []
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            path = Path(dirpath) / name
            leaves.append(path.relative_to(root).as_posix())
    leaves.sort()
    return leaves


def _plant_operator_home(base: Path, *, token: bool) -> Path:
    home = base / "operator-home"
    cli = home / ".gemini" / "antigravity-cli"
    cli.mkdir(parents=True)
    settings = home / SETTINGS_REL
    history = home / HISTORY_REL
    settings.write_text(SETTINGS_CANARY, encoding="utf-8")
    history.write_text(HISTORY_CANARY, encoding="utf-8")
    if token:
        auth = home / AUTH_REL
        auth.write_text(SYNTHETIC_TOKEN, encoding="utf-8")
        planted = auth.read_text(encoding="utf-8")
        if planted != SYNTHETIC_TOKEN:
            raise AssertionError("token plant did not land")
    if settings.read_text(encoding="utf-8") != SETTINGS_CANARY:
        raise AssertionError("settings canary plant did not land")
    if history.read_text(encoding="utf-8") != HISTORY_CANARY:
        raise AssertionError("history canary plant did not land")
    return home


class AgyIsolationTests(unittest.TestCase):
    def test_agy_registry_declares_measured_home_isolation(self):
        self.assertIn("agy", isolation.HARNESSES)
        agy = isolation.HARNESSES["agy"]
        self.assertEqual("home", agy.get("mechanism"))
        self.assertEqual("HOME", agy.get("home_env"))
        self.assertEqual([], agy.get("flags"))
        auth_files = agy.get("auth_files")
        self.assertEqual(1, len(auth_files))
        self.assertEqual([AUTH_REL], auth_files)
        self.assertEqual(
            {"under": "minimal", "path": SESSION_REL},
            agy.get("sessions"),
        )
        measured = agy.get("measured") or {}
        self.assertEqual("2026-09-08", measured.get("on"))
        self.assertEqual("1.1.27", measured.get("version"))

    def test_build_home_copies_only_the_oauth_token_and_excludes_canaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            operator = _plant_operator_home(base, token=True)
            root = base / "scratch"
            root.mkdir()
            self.assertEqual(SYNTHETIC_TOKEN, (operator / AUTH_REL).read_text(encoding="utf-8"))
            self.assertEqual(SETTINGS_CANARY, (operator / SETTINGS_REL).read_text(encoding="utf-8"))
            self.assertEqual(HISTORY_CANARY, (operator / HISTORY_REL).read_text(encoding="utf-8"))

            try:
                home = Path(
                    isolation.build_home("agy", root, env={"HOME": str(operator)})
                )
            except isolation.NotIsolated as exc:
                self.fail(f"expected an isolated agy home, refused: {exc}")

            leaves = _file_leaves(home)
            self.assertEqual(1, len(leaves))
            self.assertEqual([AUTH_REL], leaves)
            linked = home / AUTH_REL
            self.assertTrue(linked.is_symlink())
            self.assertEqual((operator / AUTH_REL).resolve(), linked.resolve())
            self.assertEqual(SYNTHETIC_TOKEN, linked.read_text(encoding="utf-8"))
            self.assertFalse((home / SETTINGS_REL).exists())
            self.assertFalse((home / HISTORY_REL).exists())
            self.assertEqual(SETTINGS_CANARY, (operator / SETTINGS_REL).read_text(encoding="utf-8"))
            self.assertEqual(HISTORY_CANARY, (operator / HISTORY_REL).read_text(encoding="utf-8"))

    def test_isolated_homes_for_two_jobs_are_fresh_and_independent(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            operator = _plant_operator_home(base, token=True)
            env = {"HOME": str(operator)}
            root_a = base / "job-a"
            root_b = base / "job-b"
            root_a.mkdir()
            root_b.mkdir()

            try:
                env_a, flags_a = isolation.isolated("agy", root_a, env=env)
                env_b, flags_b = isolation.isolated("agy", root_b, env=env)
            except isolation.NotIsolated as exc:
                self.fail(f"expected two isolated agy homes, refused: {exc}")

            self.assertEqual([], flags_a)
            self.assertEqual([], flags_b)
            self.assertEqual({"HOME"}, set(env_a))
            self.assertEqual({"HOME"}, set(env_b))
            home_a = Path(env_a["HOME"])
            home_b = Path(env_b["HOME"])
            self.assertNotEqual(home_a.resolve(), home_b.resolve())
            self.assertEqual([AUTH_REL], _file_leaves(home_a))
            self.assertEqual([AUTH_REL], _file_leaves(home_b))
            marker = home_a / "job-marker"
            marker.write_text("job-a-only\n", encoding="utf-8")
            self.assertEqual("job-a-only\n", marker.read_text(encoding="utf-8"))
            self.assertFalse((home_b / "job-marker").exists())
            self.assertEqual([AUTH_REL], _file_leaves(home_b))

    def test_build_home_refuses_missing_auth_without_leaving_a_home(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            operator = _plant_operator_home(base, token=False)
            root = base / "scratch"
            root.mkdir()
            before = list(root.iterdir())
            self.assertEqual(0, len(before))
            self.assertFalse((operator / AUTH_REL).exists())
            self.assertEqual(
                SETTINGS_CANARY,
                (operator / SETTINGS_REL).read_text(encoding="utf-8"),
            )

            with self.assertRaises(isolation.NotIsolated) as raised:
                isolation.build_home("agy", root, env={"HOME": str(operator)})

            self.assertIn("antigravity-oauth-token", str(raised.exception))
            self.assertEqual(before, list(root.iterdir()))
            self.assertEqual(
                SETTINGS_CANARY,
                (operator / SETTINGS_REL).read_text(encoding="utf-8"),
            )

    def test_explicit_env_does_not_fall_back_to_the_real_home(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "scratch"
            root.mkdir()
            with self.assertRaises(isolation.NotIsolated) as raised:
                isolation.build_home("agy", root, env={"PATH": "/usr/bin"})
            reason = str(raised.exception)
            self.assertIn("HOME", reason)
            self.assertNotIn("antigravity-oauth-token", reason)
            self.assertEqual(0, len(list(root.iterdir())))

            with self.assertRaises(isolation.NotIsolated):
                isolation.build_home("agy", root, env={"HOME": ""})
            with self.assertRaises(isolation.NotIsolated):
                isolation.dispatch_env("agy", home="", env={})
            with self.assertRaises(isolation.NotIsolated):
                isolation.dispatch_env("agy", home=None, env={})

    def test_dispatch_env_sets_home_and_nothing_else(self):
        home = "/tmp/recognisable-agy-minimal-home"
        try:
            actual = isolation.dispatch_env(
                "agy", home=home, env={"KEEP": "caller"}
            )
        except isolation.NotIsolated as exc:
            self.fail(f"expected agy dispatch_env overrides, refused: {exc}")
        self.assertEqual({"HOME": home}, actual)

    def test_isolated_returns_home_env_and_empty_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            operator = _plant_operator_home(base, token=True)
            root = base / "scratch"
            root.mkdir()
            try:
                env, flags = isolation.isolated(
                    "agy", root, env={"HOME": str(operator)}
                )
            except isolation.NotIsolated as exc:
                self.fail(f"expected isolated agy configuration, refused: {exc}")
            self.assertEqual([], flags)
            self.assertEqual({"HOME"}, set(env))
            home = Path(env["HOME"])
            self.assertTrue(home == root or root in home.parents)
            leaves = _file_leaves(home)
            self.assertEqual(1, len(leaves))
            self.assertEqual([AUTH_REL], leaves)
            linked = home / AUTH_REL
            self.assertTrue(linked.is_symlink())
            self.assertEqual((operator / AUTH_REL).resolve(), linked.resolve())


if __name__ == "__main__":
    unittest.main()
