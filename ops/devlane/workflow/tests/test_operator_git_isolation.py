"""Isolation from operator Git state — four findings from Codex's sweep.

Contract: `.dev/records/dispatches/20260828T210617Z-review-codex-d413bf.json`
`result.envelope.findings`. Written red against
`deb679ce5eeed1ad082965ab6a3dcf636978aa20` before any fix, per
`ops/process/tdd.md`. One test per finding; each is red for that
finding's stated reason, not for another finding's surface.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import support
import test_commit_trailers as commit_trailers
import test_secret_signatures as secret_signatures

CHECK = commit_trailers.CHECK

UNRESOLVABLE_REF = "refs/heads/no-such-ref"
VALID_TRAILERS = "Source: original\nCo-Authored-By: A <a@x>\n"


@contextmanager
def overlay_env(**updates):
    """Set process env for fixtures that inherit `os.environ`, then restore."""
    saved = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def operator_git_global(body: str):
    """Point Git at a throwaway global config — the operator channel, not
    GIT_CONFIG_COUNT, so a local override in the fixture can still win."""
    with tempfile.TemporaryDirectory(prefix="wf-op-git-") as raw:
        config = Path(raw) / "gitconfig"
        config.write_text(body)
        landed = config.read_text(encoding="utf-8")
        if landed != body:
            raise AssertionError("INVALID fixture: global gitconfig did not land intact")
        with overlay_env(GIT_CONFIG_GLOBAL=str(config)):
            yield config


def git(root, *args, check=True, extra_env=None):
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=check,
        env=env,
    )


def run_checker(root, *args, extra_env=None):
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, str(CHECK), *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr, proc


class AnUnresolvableBaseIsNotOverriddenByAReachableEvent(unittest.TestCase):
    """[high, Codex] A reachable Actions event silently overrides an
    explicitly unresolvable --base-ref.

    For --since-base, range_from_event() is consulted before --base-ref.
    If GITHUB_EVENT_PATH names reachable before/after commits, that event
    range wins and refs/heads/no-such-ref is never resolved.
    """

    def test_an_unresolvable_base_stays_invalid_when_the_event_range_is_reachable(self):
        with tempfile.TemporaryDirectory(prefix="wf-event-base-") as raw:
            root = Path(raw)
            git(root, "init", "-q", "-b", "main")
            git(root, "config", "user.email", "t@x")
            git(root, "config", "user.name", "T")
            git(root, "config", "commit.gpgsign", "false")
            (root / "f").write_text("a\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "--no-verify", "-m",
                f"one\n\n{VALID_TRAILERS}")
            before = git(root, "rev-parse", "HEAD").stdout.strip()
            (root / "f").write_text("b\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "--no-verify", "-m",
                f"two\n\n{VALID_TRAILERS}")
            after = git(root, "rev-parse", "HEAD").stdout.strip()

            git(root, "cat-file", "-e", f"{before}^{{commit}}")
            git(root, "cat-file", "-e", f"{after}^{{commit}}")
            missing = git(root, "rev-parse", "--verify", UNRESOLVABLE_REF,
                          check=False)
            self.assertNotEqual(
                missing.returncode, 0,
                "INVALID fixture: the planted base-ref resolved",
            )

            event = root / "event.json"
            payload = json.dumps({"before": before, "after": after}) + "\n"
            event.write_text(payload)
            self.assertEqual(event.read_text(encoding="utf-8"), payload)
            self.assertEqual(json.loads(event.read_text())["before"], before)
            self.assertEqual(json.loads(event.read_text())["after"], after)

            event_env = {"GITHUB_EVENT_PATH": str(event)}
            event_only, event_out, _ = run_checker(
                root, "--since-base", extra_env=event_env,
            )
            self.assertEqual(
                event_only, 0,
                "INVALID fixture: the event range was not usable in this "
                f"repo\n{event_out}",
            )
            self.assertIn("checked 1 message", event_out)

            code, out, _ = run_checker(
                root, "--since-base", "--base-ref", UNRESOLVABLE_REF,
                extra_env=event_env,
            )
            self.assertEqual(
                code, 1,
                "an explicit unresolvable --base-ref must stay INVALID even "
                "when a reachable Actions event exists; the event range won "
                f"and the checker exited {code}:\n{out}",
            )
            self.assertIn("INVALID", out)


class SandboxCommitsIgnoreOperatorGlobalHooks(unittest.TestCase):
    """[high, Codex] The shared Sandbox executes operator-global Git hooks.

    Sandbox sets identity and disables signing, but it neither clears
    core.hooksPath nor uses --no-verify for its seed and later direct
    commits. An operator-global pre-commit hook can reject those fixtures.
    """

    def test_sandbox_seed_and_later_commits_ignore_a_rejecting_global_hook(self):
        with tempfile.TemporaryDirectory(prefix="wf-hooks-") as raw:
            hookdir = Path(raw) / "hooks"
            hookdir.mkdir()
            hook = hookdir / "pre-commit"
            hook.write_text("#!/bin/sh\necho operator-global-pre-commit >&2\nexit 1\n")
            hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            self.assertTrue(os.access(hook, os.X_OK),
                            "INVALID fixture: hook is not executable")
            self.assertIn("exit 1", hook.read_text(encoding="utf-8"))

            config_body = f'[core]\n\thooksPath = "{hookdir}"\n'
            with operator_git_global(config_body):
                probe = Path(raw) / "probe"
                probe.mkdir()
                git(probe, "init", "-q", "-b", "main")
                git(probe, "config", "user.email", "t@x")
                git(probe, "config", "user.name", "T")
                git(probe, "config", "commit.gpgsign", "false")
                (probe / "f").write_text("probe\n")
                git(probe, "add", "-A")
                declined = git(probe, "commit", "-q", "-m", "probe", check=False)
                self.assertNotEqual(
                    declined.returncode, 0,
                    "INVALID fixture: the planted pre-commit hook did not fire",
                )
                self.assertIn("operator-global-pre-commit", declined.stderr)

                sb = None
                try:
                    try:
                        sb = support.Sandbox()
                    except subprocess.CalledProcessError as err:
                        self.fail(
                            "Sandbox seed must not run operator-global hooks: "
                            f"{err.stderr}"
                        )
                    sb.write("later.txt", "later\n")
                    try:
                        sb.commit_all("sandbox: later commit")
                    except subprocess.CalledProcessError as err:
                        self.fail(
                            "Sandbox later commits must not run operator-global "
                            f"hooks: {err.stderr}"
                        )
                    self.assertTrue((sb.dir / "later.txt").is_file())
                finally:
                    if sb is not None:
                        sb.destroy()


class ThrowawayReposDoNotInheritTheOperatorExcludesFile(unittest.TestCase):
    """[medium, Codex] Throwaway repositories inherit the operator's global
    excludes file.

    Fixtures initialize repositories and add untracked files without
    disabling core.excludesFile. A matching operator rule causes git add
    to omit the planted file, so the assertion afterwards answers a
    question about a different fileset.
    """

    def test_a_global_excludes_rule_does_not_drop_a_planted_candidate(self):
        with tempfile.TemporaryDirectory(prefix="wf-excludes-") as raw:
            base = Path(raw)
            ignore = base / "ignore"
            ignore.write_text("candidate.txt\n")
            self.assertEqual(ignore.read_text(encoding="utf-8"), "candidate.txt\n")

            config_body = f'[core]\n\texcludesFile = "{ignore}"\n'
            with operator_git_global(config_body):
                probe = base / "probe"
                probe.mkdir()
                git(probe, "init", "-q", "-b", "main")
                (probe / "candidate.txt").write_bytes(b"recognisable clean fixture\n")
                self.assertEqual(
                    (probe / "candidate.txt").read_bytes(),
                    b"recognisable clean fixture\n",
                    "INVALID fixture: probe candidate did not land intact",
                )
                git(probe, "add", "candidate.txt", check=False)
                ignored = git(probe, "check-ignore", "-q", "candidate.txt",
                              check=False)
                self.assertEqual(
                    ignored.returncode, 0,
                    "INVALID fixture: excludesFile did not match candidate.txt",
                )
                listed = git(probe, "ls-files", "--error-unmatch", "candidate.txt",
                             check=False)
                self.assertNotEqual(
                    listed.returncode, 0,
                    "INVALID fixture: the excludesFile did not drop the add",
                )

                root = base / "fixture"
                root.mkdir()
                case = secret_signatures.EverySecretSignatureFires()
                case.initialise_repo(root)
                relative = Path("candidate.txt")
                candidate = root / relative
                candidate.write_bytes(b"recognisable clean fixture\n")
                self.assertEqual(
                    candidate.read_bytes(),
                    b"recognisable clean fixture\n",
                    "INVALID fixture: planted candidate did not land intact",
                )
                added = git(root, "add", relative.as_posix(), check=False)
                self.assertEqual(added.returncode, 0, added.stderr)
                case.assert_indexed(root, relative)


class DirectCommitFixturesDoNotInheritGlobalSigning(unittest.TestCase):
    """[medium, Codex] Direct commit fixtures inherit global commit signing
    policy.

    These fixtures configure user identity but do not set
    commit.gpgsign=false. --no-verify bypasses hooks, not signing. With
    a global commit.gpgsign=true and no usable signing key, fixture
    construction fails.
    """

    def test_throwaway_history_constructs_when_the_operator_requires_signing(self):
        with tempfile.TemporaryDirectory(prefix="wf-gpgsign-") as raw:
            refuse = Path(raw) / "refuse-sign"
            refuse.write_text("#!/bin/sh\necho operator-global-signer >&2\nexit 1\n")
            refuse.chmod(
                refuse.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            )
            self.assertTrue(os.access(refuse, os.X_OK),
                            "INVALID fixture: signer is not executable")

            config_body = (
                "[commit]\n"
                "\tgpgsign = true\n"
                "[gpg]\n"
                f'\tprogram = "{refuse}"\n'
            )
            with operator_git_global(config_body):
                probe = Path(raw) / "probe"
                probe.mkdir()
                git(probe, "init", "-q", "-b", "main")
                git(probe, "config", "user.email", "t@x")
                git(probe, "config", "user.name", "T")
                (probe / "f").write_text("probe\n")
                git(probe, "add", "-A")
                declined = git(
                    probe, "commit", "-q", "--no-verify", "-m", "probe",
                    check=False,
                )
                self.assertNotEqual(
                    declined.returncode, 0,
                    "INVALID fixture: commit.gpgsign did not engage",
                )
                self.assertIn("operator-global-signer", declined.stderr)

                try:
                    code, out = commit_trailers.on_range(
                        "subject\n\njust a body, no trailers here.\n"
                    )
                except subprocess.CalledProcessError as err:
                    self.fail(
                        "throwaway history must not inherit commit.gpgsign; "
                        f"fixture construction failed: {err.stderr}"
                    )
                self.assertEqual(code, 1, out)
                self.assertIn("Source", out)
