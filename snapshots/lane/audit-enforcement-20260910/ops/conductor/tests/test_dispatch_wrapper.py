"""Dispatch wrapper acceptance tests, written from the spec.

Contract: `ops/docs/scratch/dispatch-wrapper-spec.md` Acceptance rows
1-7. The wrapper and its conf do not exist yet. Tests invoke

    bash <repo>/ops/conductor/tools/dispatch.sh <flags>

with a scratch conf and scratch scope file per case. They never write
`ops/lane.conf` and never add or remove worktrees.

Argv assertions compare exact lists, never a substring of a joined
command line.

Pins that the spec left unnamed (reported as findings, not silently
assumed) live in PIN_* comments below. Callee flag names come from
`ops/devlane/dispatch/CONTRACT.md` §Verbs, not from launch.py source.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import worker_conf

REPO = Path(__file__).resolve().parents[3]
WRAPPER = REPO / "ops" / "conductor" / "tools" / "dispatch.sh"
REAL_CONF = REPO / "ops" / "lane.conf"
OLD_CONF = REPO / "ops" / "conductor" / "tools" / "dispatch.conf"
TOOLS_DIR = WRAPPER.parent
NAME_KEYS = (
    "LANE_NAME",
    "TRUNK_BRANCH",
    "RELEASE_BRANCH",
    "REPO_SLUG",
    "CHECK_NAMES",
)

SCOPE_CAP = 1024
FLAG_AGENT = "Wrap Agent <noreply@example.invalid>"
CONF_AGENT = "Conf Agent <noreply@example.invalid>"
ENV_AGENT = "Grok 4.6 <noreply@x.ai>"
MALFORMED_AGENT = "Grok 4.6"
FABLE_AGENT = "Claude Fable 5.1 <noreply@anthropic.com>"
NO_WORKTREE_BRANCH = "no-wt-dispatch-wrapper-9f3c1e2a"

# PIN_CONF_OVERRIDE: spec names only the real conf path. Tests point at a
# scratch conf through LANE_CONF so the real file is never touched.
# DISPATCH_CONF retires with the file it named.
CONF_ENV = "LANE_CONF"

# PIN_DRY_RUN_SHAPE: spec says dry-run prints argv and env deltas, not
# how. Tests parse one JSON object {"argv": [str, ...], "env": {k: v}}.
# PIN_ARGV_MAP: wrapper --job X → launch.py positional X; --scope-file
# contents → --scope TEXT; --worktree/--branch resolve to --ref (HEAD of
# that tree) and --lineage (symbolic-ref if attached); --agent and
# --timeout are env deltas, not callee flags. Order follows CONTRACT.md
# §Verbs. argv[0] is LAUNCHER_PIN with no python3 prefix.
# PIN_ENV_KEYS: env overrides use the conf key names. Winning timeout
# is env delta DISPATCH_TIMEOUT when --timeout is given; neither
# DISPATCH_TIMEOUT nor DEFAULT_TIMEOUT is in the delta when it is not.
# DEFAULT_TIMEOUT is retired: a conf that still sets it is a refusal.
# Winning agent is env delta WF_AGENT: --agent if passed, else the
# invoking WF_AGENT when it matches Name <address>, else
# WF_AGENT_DEFAULT. A well-formed invoking WF_AGENT does not require
# WF_AGENT_DEFAULT to be present in conf or local conf.


def _porcelain(cwd: Path) -> bytes:
    return subprocess.check_output(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(cwd),
    )


def _head_sha(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _lineage(path: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(path), "symbolic-ref", "--quiet", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    name = (proc.stdout or "").strip()
    return name or None


def _bash_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _jobs_roots_to_guard() -> list[Path]:
    roots: list[Path] = []
    snap = REPO.resolve()
    if snap.name == "snapshot":
        jobs_root = snap.parent.parent
        if jobs_root.name == "dispatch":
            roots.append(jobs_root)
    home_default = Path.home() / ".local" / "state" / "agentscient" / "dispatch"
    if home_default not in roots:
        roots.append(home_default)
    return roots


def expected_launch_argv(
    *,
    pin: Path | str,
    job: str,
    harness: str,
    model: str,
    effort: str | None = None,
    ref: str,
    lineage: str | None = None,
    unit: str | None = None,
    stage: str | None = None,
    scope: str | None = None,
    input_path: Path | str | None = None,
    input_paths: list[Path | str] | None = None,
    follows: str | None = None,
) -> list[str]:
    argv = [
        str(pin),
        job,
        "--harness",
        harness,
        "--model",
        model,
    ]
    if effort:
        argv.extend(["--effort", effort])
    argv.extend(["--ref", ref])
    if lineage:
        argv.extend(["--lineage", lineage])
    if unit:
        argv.extend(["--unit", unit])
    if stage:
        argv.extend(["--stage", stage])
    if scope is not None:
        argv.extend(["--scope", scope])
    if input_paths is not None:
        for one in input_paths:
            argv.extend(["--input", str(one)])
    elif input_path is not None:
        argv.extend(["--input", str(input_path)])
    if follows:
        argv.extend(["--follows", follows])
    return argv


class _WrapperFixture(unittest.TestCase):
    """Scratch conf, scratch scope, isolated HOME/jobs, no host mutation."""

    def setUp(self):
        self._porcelain_before = _porcelain(REPO)
        self._tools_existed = TOOLS_DIR.exists()
        self._conf_existed = REAL_CONF.exists()
        self._conf_bytes = REAL_CONF.read_bytes() if self._conf_existed else None
        self._old_existed = OLD_CONF.exists()
        self._old_bytes = OLD_CONF.read_bytes() if self._old_existed else None
        self._guarded = []
        for root in _jobs_roots_to_guard():
            if root.is_dir():
                self._guarded.append((root, frozenset(os.listdir(root))))

        self._tmp = tempfile.TemporaryDirectory(prefix="dispatch-wrapper-")
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.xdg = root / "xdg"
        self.jobs_root = root / "jobs"
        self.scratch = root / "scratch"
        for path in (self.home, self.xdg, self.jobs_root, self.scratch):
            path.mkdir()

        self.marker = self.scratch / "launched.marker"
        self.pin = self.scratch / "sentinel-launch"
        self.pin_env = self.scratch / "sentinel-launch-env"
        self._plant_sentinel(self.pin, self.marker)
        self._plant_sentinel(self.pin_env, self.marker)

        self.scope_text = "scope-pointer-body-v1"
        self.scope_path = self.scratch / "scope.txt"
        self._plant_bytes(self.scope_path, self.scope_text.encode("utf-8"))

        self.input_path = self.scratch / "input.txt"
        self._plant_bytes(self.input_path, b"input-bytes-v1\n")

        self.conf_path = self.scratch / "dispatch.conf"
        self.conf_timeout = "120"
        self.conf_model_grok = "wrap-model-conf-grok"
        self.conf_effort_grok = "wrap-effort-conf-grok"
        self._plant_conf(self.conf_path, **self._conf_kwargs())

        self.job = "wrap-job"
        self.harness = "grok"
        self.model_flag = "wrap-model-flag"
        self.unit = "wrap-unit"
        self.stage = "tests"
        self.follows = "20260831T000000Z-plan-grok-aaaaaa"
        self.flag_timeout = "9"
        self.worktree = REPO
        self.ref = _head_sha(self.worktree)
        self.lineage = _lineage(self.worktree)

        self.assertEqual(
            list(self.jobs_root.iterdir()),
            [],
            "plant: isolated jobs root starts empty",
        )
        self.assertFalse(self.marker.exists(), "plant: sentinel has not run")
        self.assertFalse(
            REAL_CONF.exists() and not self._conf_existed,
            "plant must not create the real conf",
        )

    def tearDown(self):
        try:
            self.assertEqual(
                _porcelain(REPO),
                self._porcelain_before,
                "tests must not mutate worktree state",
            )
            self.assertEqual(
                TOOLS_DIR.exists(),
                self._tools_existed,
                "tests must not create or delete ops/conductor/tools",
            )
            self.assertEqual(REAL_CONF.exists(), self._conf_existed)
            if self._conf_existed:
                self.assertEqual(REAL_CONF.read_bytes(), self._conf_bytes)
            self.assertEqual(OLD_CONF.exists(), self._old_existed)
            if self._old_existed:
                self.assertEqual(OLD_CONF.read_bytes(), self._old_bytes)
            for root, before in self._guarded:
                after = frozenset(os.listdir(root))
                self.assertEqual(
                    after,
                    before,
                    f"host dispatch directory changed: {root}",
                )
        finally:
            self._tmp.cleanup()

    def _plant_bytes(self, path: Path, data: bytes) -> None:
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertEqual(len(landed), len(data))

    def _plant_executable(self, path: Path, body: str) -> None:
        path.write_text(body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        landed = path.read_text(encoding="utf-8")
        self.assertEqual(landed, body, f"sentinel plant did not land: {path}")
        self.assertTrue(os.access(path, os.X_OK), f"sentinel not executable: {path}")

    def _plant_sentinel(self, path: Path, marker: Path) -> None:
        body = (
            "#!/bin/sh\n"
            f"printf launched > '{marker}'\n"
            "exit 0\n"
        )
        self._plant_executable(path, body)
        self.assertFalse(marker.exists(), "plant: marker must not pre-exist")

    def _plant_python_sentinel(self, path: Path, script: str) -> None:
        body = "#!/usr/bin/env python3\n" + script
        self._plant_executable(path, body)

    def _reap_reported_pid(self, proc: subprocess.CompletedProcess) -> None:
        for line in (proc.stdout or "").splitlines():
            if not line.startswith("launcher-pid:"):
                continue
            raw = line.split(":", 1)[1].strip()
            try:
                pid = int(raw)
            except ValueError:
                continue
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGTERM)

    def _conf_kwargs(self, **overrides: str) -> dict[str, str]:
        keys = {
            "LAUNCHER_PIN": str(self.pin),
            "WF_AGENT_DEFAULT": CONF_AGENT,
            "LANE_AUTHOR": "Lane Owner <lane-owner@example.invalid>",
            "MODEL_GROK": self.conf_model_grok,
            "MODEL_CODEX": "wrap-model-conf-codex",
            "MODEL_CLAUDE_READ": "wrap-model-conf-claude-read",
            "MODEL_CLAUDE_PLAN": "wrap-model-conf-claude-plan",
            "EFFORT_GROK": self.conf_effort_grok,
            "EFFORT_CODEX": "wrap-effort-conf-codex",
            "EFFORT_CLAUDE": "wrap-effort-conf-claude",
            "LANE_NAME": "agentscient",
            "TRUNK_BRANCH": "dev",
            "RELEASE_BRANCH": "master",
            "REPO_SLUG": "uscient/agentscient",
            "CHECK_NAMES": "lane app",
            "SCOPE_CAP": str(SCOPE_CAP),
        }
        keys.update(overrides)
        return keys

    def _plant_conf(self, path: Path, **keys: str) -> None:
        lines = [
            f"{name}={_bash_single_quote(value)}\n" for name, value in keys.items()
        ]
        text = "".join(lines)
        path.write_text(text, encoding="utf-8")
        landed = path.read_text(encoding="utf-8")
        self.assertEqual(landed, text, f"conf plant did not land: {path}")
        for name, value in keys.items():
            self.assertIn(name, landed)
            self.assertIn(value, landed)

    def env(self, extra: dict[str, str | None] | None = None) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "XDG_STATE_HOME": str(self.xdg),
            "DISPATCH_JOBS": str(self.jobs_root),
            CONF_ENV: str(self.conf_path),
            "LC_ALL": "C",
            "LANG": "C",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        if extra:
            for name, value in extra.items():
                if value is None:
                    env.pop(name, None)
                else:
                    env[name] = value
        return env

    def invoke(
        self,
        flags: list[str],
        *,
        extra_env: dict[str, str | None] | None = None,
        timeout: float | None = 30,
    ):
        argv = ["bash", str(WRAPPER), *flags]
        # Absent wrapper is not a collection error and not bash 127: that
        # would make every case fail for the same reason. Return an empty
        # payload so the contracted assertion (exact argv, named refusal
        # text, exit 3) is what goes red.
        if not WRAPPER.is_file():
            return subprocess.CompletedProcess(
                args=argv, returncode=0, stdout="", stderr="",
            )
        try:
            return subprocess.run(
                argv,
                cwd=str(REPO),
                env=self.env(extra_env),
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(
                f"wrapper exceeded {timeout}s; stdout={exc.stdout!r} "
                f"stderr={exc.stderr!r}"
            )

    def combined(self, proc: subprocess.CompletedProcess) -> str:
        return f"{proc.stdout or ''}{proc.stderr or ''}"

    def full_flags(self, *extra: str, dry_run: bool = True, **kw) -> list[str]:
        omit = set(kw.pop("omit", ()))
        input_paths = kw.pop("input_paths", None)
        pairs = [
            ("worktree", "--worktree", str(kw.get("worktree", self.worktree))),
            ("branch", "--branch", kw.get("branch")),
            ("job", "--job", kw.get("job", self.job)),
            ("harness", "--harness", kw.get("harness", self.harness)),
            ("model", "--model", kw.get("model", self.model_flag)),
            ("effort", "--effort", kw.get("effort")),
            ("unit", "--unit", kw.get("unit", self.unit)),
            ("stage", "--stage", kw.get("stage", self.stage)),
            ("scope-file", "--scope-file", str(kw.get("scope_file", self.scope_path))),
            ("input", "--input", str(kw.get("input_path", self.input_path))),
            ("follows", "--follows", kw.get("follows", self.follows)),
            ("timeout", "--timeout", str(kw.get("timeout", self.flag_timeout))),
            ("agent", "--agent", kw.get("agent", FLAG_AGENT)),
        ]
        flags: list[str] = []
        for name, flag, value in pairs:
            if name in omit or value is None:
                continue
            if name == "input" and input_paths is not None:
                for one in input_paths:
                    flags.extend(["--input", str(one)])
                continue
            flags.extend([flag, value])
        flags.extend(extra)
        if dry_run:
            flags.append("--dry-run")
        return flags

    def expected_argv(self, **kw) -> list[str]:
        input_paths = kw.get("input_paths")
        if input_paths is not None:
            input_path = None
        else:
            input_path = kw.get("input_path", self.input_path)
        return expected_launch_argv(
            pin=kw.get("pin", self.pin),
            job=kw.get("job", self.job),
            harness=kw.get("harness", self.harness),
            model=kw.get("model", self.model_flag),
            effort=kw.get("effort", self.conf_effort_grok),
            ref=kw.get("ref", self.ref),
            lineage=kw.get("lineage", self.lineage),
            unit=kw.get("unit", self.unit),
            stage=kw.get("stage", self.stage),
            scope=kw.get("scope", self.scope_text),
            input_path=input_path,
            input_paths=input_paths,
            follows=kw.get("follows", self.follows),
        )

    def parse_dry_run_object(
        self, proc: subprocess.CompletedProcess
    ) -> dict:
        if not WRAPPER.is_file():
            return {}
        text = self.combined(proc)
        start = text.find("{")
        end = text.rfind("}")
        self.assertGreaterEqual(
            start,
            0,
            f"dry-run must print a JSON object with argv and env; got {text!r}",
        )
        self.assertGreater(
            end,
            start,
            f"dry-run JSON object is not closed; got {text!r}",
        )
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            self.fail(f"dry-run JSON is not parseable ({exc}); got {text!r}")
        self.assertIsInstance(payload, dict, payload)
        return payload

    def parse_dry_run(
        self, proc: subprocess.CompletedProcess
    ) -> tuple[list[str], dict[str, str]]:
        if not WRAPPER.is_file():
            return [], {}
        payload = self.parse_dry_run_object(proc)
        self.assertIn("argv", payload)
        self.assertIn("env", payload)
        argv = payload["argv"]
        env = payload["env"]
        self.assertIsInstance(argv, list, argv)
        self.assertTrue(
            all(isinstance(item, str) for item in argv),
            f"argv is not an exact list of strings: {argv!r}",
        )
        self.assertIsInstance(env, dict, env)
        return argv, env

    def assert_no_launch(self) -> None:
        self.assertFalse(
            self.marker.exists(),
            "LAUNCHER_PIN was invoked; this path must not launch",
        )
        self.assertEqual(
            list(self.jobs_root.iterdir()),
            [],
            "isolated jobs root must stay empty when there is no launch",
        )

    def assert_wire_abort(
        self,
        proc: subprocess.CompletedProcess,
        class_name: str,
        *,
        named: tuple[str, ...] = (),
    ) -> str:
        """Unit-1 wrapper abort: class token, expected/found/needed in
        order, one stderr line, empty stdout, exit 3, no launch.
        """
        err = proc.stderr or ""
        self.assertEqual(proc.returncode, 3, self.combined(proc))
        self.assertEqual(
            (proc.stdout or "").strip(),
            "",
            f"refusal text belongs on stderr, not stdout: {proc.stdout!r}",
        )
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        line = lines[0]
        lower = line.lower()
        token = class_name.lower().replace("_", "-")
        self.assertIn(token, lower, line)
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, line)
        self.assertLess(lower.index("expected"), lower.index("found"), line)
        self.assertLess(lower.index("found"), lower.index("needed"), line)
        for item in named:
            self.assertIn(item, line, line)
        self.assert_no_launch()
        return line


class Row1FullFlagSetArgv(_WrapperFixture):
    """Acceptance 1: full flags → exact launch.py argv; conf vs flag."""

    def test_full_flag_set_produces_exactly_the_expected_launch_argv(self):
        proc = self.invoke(self.full_flags())
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(argv, self.expected_argv())
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(env.get("WF_AGENT"), FLAG_AGENT)
        self.assertEqual(env.get("DISPATCH_TIMEOUT"), self.flag_timeout)
        self.assertNotIn("DEFAULT_TIMEOUT", env)
        self.assert_no_launch()

    def test_omitted_model_and_agent_use_conf_defaults(self):
        proc = self.invoke(self.full_flags(omit=("model", "agent")))
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(
            argv,
            self.expected_argv(model=self.conf_model_grok),
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(env.get("WF_AGENT"), CONF_AGENT)
        self.assert_no_launch()


class Row2ScopeByteGuard(_WrapperFixture):
    """Acceptance 2: 1025 bytes → exit 3, count in the message, no launch."""

    def test_scope_file_of_1025_bytes_exits_3_with_count_and_does_not_launch(self):
        data = b"S" * (SCOPE_CAP + 1)
        self._plant_bytes(self.scope_path, data)
        self.assertEqual(self.scope_path.stat().st_size, SCOPE_CAP + 1)
        proc = self.invoke(self.full_flags(dry_run=False))
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 3, text)
        self.assertIn("1025", text)
        self.assert_no_launch()

    def test_scope_file_of_1024_bytes_is_not_a_byte_guard_refusal(self):
        data = b"K" * SCOPE_CAP
        self._plant_bytes(self.scope_path, data)
        self.assertEqual(self.scope_path.stat().st_size, SCOPE_CAP)
        proc = self.invoke(self.full_flags(dry_run=True))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(
            argv,
            self.expected_argv(scope=data.decode("ascii")),
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertNotEqual(proc.returncode, 3)
        self.assert_no_launch()

    def test_1025_bytes_of_multibyte_text_is_over_the_cap(self):
        # 512 x U+00E9 is 1024 bytes; one ASCII byte more is 1025.
        text = "é" * 512 + "x"
        data = text.encode("utf-8")
        self.assertEqual(len(data), SCOPE_CAP + 1)
        self.assertEqual(len(text), 513)
        self._plant_bytes(self.scope_path, data)
        self.assertEqual(self.scope_path.stat().st_size, SCOPE_CAP + 1)
        proc = self.invoke(self.full_flags(dry_run=False))
        combined = self.combined(proc)
        self.assertEqual(proc.returncode, 3, combined)
        self.assertIn("1025", combined)
        self.assert_no_launch()


class Row3BranchWithoutWorktree(_WrapperFixture):
    """Acceptance 3: --branch with no worktree names `git worktree add`."""

    def test_branch_with_no_worktree_refuses_naming_git_worktree_add(self):
        flags = self.full_flags(
            omit=("worktree",),
            branch=NO_WORKTREE_BRANCH,
            dry_run=False,
        )
        proc = self.invoke(flags)
        text = self.combined(proc)
        self.assertIn("git worktree add", text)
        self.assertIn(NO_WORKTREE_BRANCH, text)
        self.assertNotEqual(proc.returncode, 0, text)
        self.assert_no_launch()


class Row4UnknownFlag(_WrapperFixture):
    """Acceptance 4: unknown flag is a refusal, exit nonzero."""

    def test_unknown_flag_is_a_refusal_with_nonzero_exit(self):
        unknown = "--not-a-real-flag"
        proc = self.invoke(self.full_flags(unknown, dry_run=False))
        text = self.combined(proc)
        self.assertIn(unknown, text)
        self.assertNotEqual(proc.returncode, 0, text)
        self.assert_no_launch()


class Row5MissingRequired(_WrapperFixture):
    """Acceptance 5: missing job, harness, or scope-file is named."""

    def test_missing_job_is_a_refusal_naming_job(self):
        proc = self.invoke(self.full_flags(omit=("job",), dry_run=False))
        text = self.combined(proc)
        self.assertIn("--job", text)
        self.assertNotEqual(proc.returncode, 0, text)
        self.assert_no_launch()

    def test_missing_harness_is_a_refusal_naming_harness(self):
        proc = self.invoke(self.full_flags(omit=("harness",), dry_run=False))
        text = self.combined(proc)
        self.assertIn("--harness", text)
        self.assertNotEqual(proc.returncode, 0, text)
        self.assert_no_launch()

    def test_missing_scope_file_is_a_refusal_naming_scope_file(self):
        proc = self.invoke(self.full_flags(omit=("scope-file",), dry_run=False))
        text = self.combined(proc)
        self.assertIn("--scope-file", text)
        self.assertNotEqual(proc.returncode, 0, text)
        self.assert_no_launch()


class Row6DryRunCreatesNoDispatchDir(_WrapperFixture):
    """Acceptance 6: --dry-run never creates a dispatch directory."""

    def test_dry_run_exits_0_and_creates_no_dispatch_directory(self):
        before = list(self.jobs_root.iterdir())
        self.assertEqual(before, [])
        xdg_dispatch = self.xdg / "agentscient" / "dispatch"
        home_dispatch = self.home / ".local" / "state" / "agentscient" / "dispatch"
        proc = self.invoke(self.full_flags(dry_run=True))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(argv, self.expected_argv())
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(list(self.jobs_root.iterdir()), [])
        self.assertFalse(xdg_dispatch.exists())
        self.assertFalse(home_dispatch.exists())
        self.assert_no_launch()


class Row7ConfEnvFlagPrecedence(_WrapperFixture):
    """Acceptance 7: --timeout exports DISPATCH_TIMEOUT; conf must not set
    DEFAULT_TIMEOUT; an invoking DISPATCH_TIMEOUT passes through unless
    the flag wins."""

    def test_timeout_flag_exports_dispatch_timeout(self):
        proc = self.invoke(self.full_flags())
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(env.get("DISPATCH_TIMEOUT"), self.flag_timeout)
        self.assertNotIn("DEFAULT_TIMEOUT", env)
        self.assertEqual(argv, self.expected_argv())
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_no_timeout_exports_no_wall(self):
        proc = self.invoke(self.full_flags(omit=("timeout",)))
        argv, env = self.parse_dry_run(proc)
        self.assertNotIn("DISPATCH_TIMEOUT", env)
        self.assertNotIn("DEFAULT_TIMEOUT", env)
        self.assertEqual(argv, self.expected_argv())
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_invoking_dispatch_timeout_passes_through(self):
        invoked = "77"
        proc = self.invoke(
            self.full_flags(omit=("timeout",)),
            extra_env={"DISPATCH_TIMEOUT": invoked},
        )
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(env.get("DISPATCH_TIMEOUT"), invoked)
        self.assertNotIn("DEFAULT_TIMEOUT", env)
        self.assertEqual(argv, self.expected_argv())
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_flag_beats_invoking_dispatch_timeout(self):
        proc = self.invoke(
            self.full_flags(timeout="33"),
            extra_env={"DISPATCH_TIMEOUT": "45"},
        )
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(env.get("DISPATCH_TIMEOUT"), "33")
        self.assertNotEqual(env.get("DISPATCH_TIMEOUT"), "45")
        self.assertNotIn("DEFAULT_TIMEOUT", env)
        self.assertEqual(argv, self.expected_argv())
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_a_conf_that_sets_default_timeout_is_refused(self):
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(DEFAULT_TIMEOUT=self.conf_timeout),
        )
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn("DEFAULT_TIMEOUT", landed)
        self.assertIn(self.conf_timeout, landed)
        proc = self.invoke(self.full_flags(dry_run=False))
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 3, text)
        self.assertIn("DEFAULT_TIMEOUT", text)
        self.assertIn(self.conf_timeout, text)
        self.assertIn(str(self.conf_path), text)
        lower = text.lower()
        self.assertIn("expected", lower, text)
        self.assertIn("found", lower, text)
        self.assertIn("needed", lower, text)
        self.assert_no_launch()


class Row8EffortResolution(_WrapperFixture):
    """Acceptance 8: flag, conf, per-job suffix, env, empty, missing key."""

    def test_effort_flag_reaches_argv_after_the_model(self):
        proc = self.invoke(self.full_flags(effort="high"))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(argv, self.expected_argv(effort="high"))
        model_at = argv.index("--model")
        self.assertEqual(argv[model_at:model_at + 4],
                         ["--model", self.model_flag, "--effort", "high"])
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_omitted_effort_uses_conf_effort_grok(self):
        proc = self.invoke(self.full_flags())
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(argv, self.expected_argv())
        self.assertIn("--effort", argv)
        self.assertEqual(
            argv[argv.index("--effort") + 1], self.conf_effort_grok,
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_effort_harness_job_suffix_beats_harness_effort(self):
        job_effort = "wrap-effort-job"
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(EFFORT_GROK_WRAP_JOB=job_effort),
        )
        proc = self.invoke(self.full_flags())
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(argv, self.expected_argv(effort=job_effort))
        self.assertEqual(argv[argv.index("--effort") + 1], job_effort)
        self.assertNotEqual(job_effort, self.conf_effort_grok)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_env_effort_harness_job_beats_conf(self):
        env_effort = "wrap-effort-env-job"
        conf_effort = "wrap-effort-conf-job"
        self.assertNotEqual(env_effort, conf_effort)
        self.assertNotEqual(env_effort, self.conf_effort_grok)
        self.assertNotEqual(conf_effort, self.conf_effort_grok)
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(EFFORT_GROK_WRAP_JOB=conf_effort),
        )
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn("EFFORT_GROK_WRAP_JOB=", landed)
        self.assertIn(conf_effort, landed)
        self.assertNotIn(env_effort, landed)
        extra = {"EFFORT_GROK_WRAP_JOB": env_effort}
        proc = self.invoke(self.full_flags(), extra_env=extra)
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(argv, self.expected_argv(effort=env_effort))
        self.assertEqual(argv[argv.index("--effort") + 1], env_effort)
        self.assertNotEqual(argv[argv.index("--effort") + 1], conf_effort)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_empty_effort_grok_omits_the_effort_token(self):
        self._plant_conf(self.conf_path, **self._conf_kwargs(EFFORT_GROK=""))
        proc = self.invoke(self.full_flags())
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(argv, self.expected_argv(effort=""))
        self.assertNotIn("--effort", argv)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_conf_missing_effort_codex_refuses_naming_it(self):
        keys = self._conf_kwargs()
        del keys["EFFORT_CODEX"]
        self.assertNotIn("EFFORT_CODEX", keys)
        self._plant_conf(self.conf_path, **keys)
        proc = self.invoke(self.full_flags(dry_run=False))
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 3, text)
        self.assertIn("EFFORT_CODEX", text)
        self.assert_no_launch()


class Row9ModelByJob(_WrapperFixture):
    """Acceptance 9: MODEL_<HARNESS>_<JOB> beats the harness model;
    --model still beats both."""

    def test_model_harness_job_suffix_beats_harness_model(self):
        job_model = "wrap-model-job-grok"
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(MODEL_GROK_WRAP_JOB=job_model),
        )
        proc = self.invoke(self.full_flags(omit=("model",)))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(argv[argv.index("--model") + 1], job_model)
        self.assertNotEqual(job_model, self.conf_model_grok)
        self.assertEqual(argv, self.expected_argv(model=job_model))
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_model_flag_beats_job_and_harness_model(self):
        job_model = "wrap-model-job-grok"
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(MODEL_GROK_WRAP_JOB=job_model),
        )
        proc = self.invoke(self.full_flags())
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(argv[argv.index("--model") + 1], self.model_flag)
        self.assertNotEqual(self.model_flag, job_model)
        self.assertNotEqual(self.model_flag, self.conf_model_grok)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()


class Row10JobNameMatchesCatalogueShape(_WrapperFixture):
    """Job names match the catalogue shape ^[a-z][a-z0-9-]*$ before any
    indirect expansion. A dry-run of a bad name is the same refusal.
    Finding D1: an unvalidated job name entered Bash indirect expansion,
    so array-subscript command substitutions ran even under --dry-run.
    """

    def _assert_job_name_wire_refusal(self, proc, *, found):
        text = self.combined(proc)
        self.assertNotEqual(proc.returncode, 0, text)
        lower = text.lower()
        self.assertIn("expected", lower, text)
        self.assertIn("found", lower, text)
        self.assertIn("needed", lower, text)
        self.assertIn(found, text)
        self.assert_no_launch()
        return text

    def test_an_underscore_job_name_is_a_wire_refusal_on_dry_run(self):
        bad = "wrap_job"
        self.assertNotRegex(bad, r"^[a-z][a-z0-9-]*$")
        proc = self.invoke(self.full_flags(job=bad, dry_run=True))
        self._assert_job_name_wire_refusal(proc, found=bad)

    def test_array_subscript_job_name_does_not_execute_on_dry_run(self):
        marker = self.scratch / "indirect-executed"
        self.assertFalse(marker.exists(), "plant: marker must not pre-exist")
        payload = f'printf INDIRECT_EXECUTED > "{marker}"'
        job = 'x[$(${BASH} ${C} "${PAYLOAD}")]'
        self.assertNotRegex(job, r"^[a-z][a-z0-9-]*$")
        proc = self.invoke(
            self.full_flags(job=job, harness="codex", dry_run=True),
            extra_env={"C": "-c", "PAYLOAD": payload},
        )
        self.assertFalse(
            marker.exists(),
            "job-name command substitution must not run; "
            f"marker={marker.read_text(encoding='utf-8') if marker.exists() else ''!r}",
        )
        text = self.combined(proc)
        self.assertNotIn("INDIRECT_EXECUTED", text)
        self._assert_job_name_wire_refusal(proc, found=job)


class Row10TwoInputsBothReachArgv(_WrapperFixture):
    """Two --input flags both reach the launcher argv, in the order given."""

    def test_two_input_flags_land_in_order(self):
        first = self.scratch / "input-a.txt"
        second = self.scratch / "input-b.txt"
        self._plant_bytes(first, b"bytes-a\n")
        self._plant_bytes(second, b"bytes-b\n")
        self.assertNotEqual(first, second)
        proc = self.invoke(self.full_flags(input_paths=[first, second]))
        argv, _env = self.parse_dry_run(proc)
        input_at = [i for i, tok in enumerate(argv) if tok == "--input"]
        self.assertEqual(len(input_at), 2, argv)
        self.assertEqual(argv[input_at[0] + 1], str(first))
        self.assertEqual(argv[input_at[1] + 1], str(second))
        self.assertLess(input_at[0], input_at[1])
        self.assertEqual(argv, self.expected_argv(input_paths=[first, second]))
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_two_input_flags_reach_the_foreground_launcher_in_order(self):
        first = self.scratch / "input-a.txt"
        second = self.scratch / "input-b.txt"
        self._plant_bytes(first, b"bytes-a\n")
        self._plant_bytes(second, b"bytes-b\n")
        argv_log = self.scratch / "launcher-argv.json"
        self._plant_python_sentinel(
            self.pin,
            "import json, pathlib, sys\n"
            f"pathlib.Path({str(argv_log)!r}).write_text("
            "json.dumps(sys.argv))\n"
            f"pathlib.Path({str(self.marker)!r}).write_text('launched')\n",
        )
        proc = self.invoke(
            self.full_flags(input_paths=[first, second], dry_run=False),
            timeout=8,
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertTrue(self.marker.exists(), "foreground path must launch")
        self.assertTrue(argv_log.is_file(), "sentinel recorded argv")
        launched = json.loads(argv_log.read_text(encoding="utf-8"))
        self.assertIsInstance(launched, list, launched)
        input_at = [i for i, tok in enumerate(launched) if tok == "--input"]
        self.assertEqual(len(input_at), 2, launched)
        self.assertEqual(launched[input_at[0] + 1], str(first))
        self.assertEqual(launched[input_at[1] + 1], str(second))
        self.assertLess(input_at[0], input_at[1])

    def test_a_missing_input_file_refuses_before_launch(self):
        missing = Path("/no/such")
        self.assertFalse(missing.exists(), "plant: missing path must not exist")
        self._plant_python_sentinel(
            self.pin,
            "from pathlib import Path\n"
            f"Path({str(self.marker)!r}).write_text('launched')\n",
        )
        proc = self.invoke(self.full_flags(input_path=missing, dry_run=False))
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 3, text)
        self.assertIn(str(missing), text)
        lower = text.lower()
        self.assertIn("expected", lower, text)
        self.assertIn("found", lower, text)
        self.assertIn("needed", lower, text)
        self.assert_no_launch()


class Row11LauncherSource(_WrapperFixture):
    """Dry-run names where the launcher path came from: env, conf, or sibling."""

    def _assert_launcher_source(self, proc, *, source: str, pin: Path) -> None:
        payload = self.parse_dry_run_object(proc)
        self.assertIn("launcher", payload)
        launcher = payload["launcher"]
        self.assertIsInstance(launcher, dict, launcher)
        self.assertEqual(launcher.get("source"), source, payload)
        argv = payload["argv"]
        self.assertIsInstance(argv, list, argv)
        self.assertGreaterEqual(len(argv), 1, argv)
        self.assertEqual(argv[0], str(pin))
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_conf_without_pin_resolves_the_sibling_launcher(self):
        keys = self._conf_kwargs()
        self.assertIn("LAUNCHER_PIN", keys)
        del keys["LAUNCHER_PIN"]
        self.assertNotIn("LAUNCHER_PIN", keys)
        self._plant_conf(self.conf_path, **keys)
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertNotIn("LAUNCHER_PIN", landed)
        sibling = (REPO / "ops" / "devlane" / "dispatch" / "launch.py").resolve()
        self.assertTrue(sibling.is_file(), f"plant: sibling launcher at {sibling}")
        proc = self.invoke(self.full_flags())
        self._assert_launcher_source(proc, source="sibling", pin=sibling)

    def test_env_pin_reports_source_env(self):
        proc = self.invoke(
            self.full_flags(),
            extra_env={"LAUNCHER_PIN": str(self.pin_env)},
        )
        self._assert_launcher_source(proc, source="env", pin=self.pin_env)

    def test_conf_pin_reports_source_conf(self):
        proc = self.invoke(self.full_flags())
        self._assert_launcher_source(proc, source="conf", pin=self.pin)

    def test_foreground_prints_launcher_provenance(self):
        proc = self.invoke(self.full_flags(dry_run=False), timeout=8)
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 0, text)
        self.assertIn(f"launcher: {self.pin} (conf)", text)
        self.assertTrue(self.marker.exists(), "foreground path must launch")

    def test_the_sibling_launcher_in_the_tree_is_executable(self):
        """Adversarial finding 2: the wrapper execs argv[0] without
        python3, so the real sibling launch.py must stay mode 100755."""
        sibling = (
            REPO / "ops" / "devlane" / "dispatch" / "launch.py"
        ).resolve()
        self.assertTrue(sibling.is_file(), f"plant: sibling at {sibling}")
        self.assertTrue(
            os.access(sibling, os.X_OK),
            f"sibling launch.py must be executable for exec: "
            f"mode={oct(sibling.stat().st_mode)}",
        )
        listed = subprocess.check_output(
            ["git", "ls-files", "-s", "--", "ops/devlane/dispatch/launch.py"],
            cwd=str(REPO),
            text=True,
        )
        self.assertTrue(
            listed.startswith("100755"),
            f"git index mode must be 100755, not a 644 regression: {listed!r}",
        )


class Row12Detach(_WrapperFixture):
    """--detach returns the record id without waiting for the launcher."""

    RECORD_ID = "20260901T000000Z-plan-grok-abcdef"

    def test_detach_returns_the_record_id_before_the_launcher_exits(self):
        record_id = self.RECORD_ID
        job_dir = self.jobs_root / record_id
        self._plant_python_sentinel(
            self.pin,
            "import pathlib, sys, time\n"
            f"pathlib.Path({str(job_dir)!r}).mkdir(parents=True, exist_ok=True)\n"
            f"sys.stdout.write('record: {record_id}\\n')\n"
            "sys.stdout.flush()\n"
            "time.sleep(5)\n",
        )
        started = time.monotonic()
        proc = self.invoke(self.full_flags("--detach", dry_run=False), timeout=8)
        elapsed = time.monotonic() - started
        try:
            self.assertEqual(proc.returncode, 0, self.combined(proc))
            self.assertLess(
                elapsed,
                3,
                f"detach returned after {elapsed:.2f}s; must not wait for the launcher",
            )
            self.assertIn(f"record: {record_id}", proc.stdout or "")
            pid_lines = [
                ln for ln in (proc.stdout or "").splitlines()
                if ln.startswith("launcher-pid:")
            ]
            self.assertEqual(
                len(pid_lines), 1,
                f"detach prints launcher-pid: got {pid_lines!r} from "
                f"{proc.stdout!r}",
            )
            raw_pid = pid_lines[0].split(":", 1)[1].strip()
            self.assertTrue(raw_pid.isdigit(), pid_lines[0])
            log_path = job_dir / "launcher.log"
            self.assertTrue(log_path.is_file(), f"missing launcher.log at {log_path}")
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn(
                f"record: {record_id}", log_text,
                f"launcher.log must carry the launcher stdout, not be empty: "
                f"{log_text!r}",
            )
        finally:
            self._reap_reported_pid(proc)

    def test_detach_surfaces_a_launcher_refusal(self):
        refusal = (
            "expected a harness job in jobs.json; found wrap-job; "
            "satisfy by name a dispatchable job"
        )
        self._plant_python_sentinel(
            self.pin,
            "import sys\n"
            f"sys.stderr.write({refusal!r} + '\\n')\n"
            "sys.exit(3)\n",
        )
        proc = self.invoke(self.full_flags("--detach", dry_run=False), timeout=8)
        text = self.combined(proc)
        self.assertIn(refusal, proc.stderr or "")
        self.assertEqual(proc.returncode, 3, text)

    def test_foreground_record_line_comes_from_the_launcher(self):
        record_id = self.RECORD_ID
        decoy = "20260902T000000Z-plan-grok-zzzzzz"
        self.assertNotEqual(record_id, decoy)
        decoy_dir = self.jobs_root / decoy
        decoy_dir.mkdir()
        self.assertTrue(decoy_dir.is_dir(), "plant: newer jobs-root directory")
        os.utime(decoy_dir, None)
        self._plant_python_sentinel(
            self.pin,
            "import sys\n"
            f"sys.stdout.write('record: {record_id}\\n')\n"
            "sys.stdout.flush()\n",
        )
        proc = self.invoke(self.full_flags(dry_run=False), timeout=8)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
        self.assertTrue(lines, proc.stdout)
        self.assertEqual(lines[-1], f"record: {record_id}")
        self.assertNotIn(decoy, proc.stdout or "")

    def test_dry_run_with_detach_declares_detach_in_the_plan(self):
        """Adversarial finding 3: --dry-run --detach must not silently
        become a foreground plan."""
        proc = self.invoke(self.full_flags("--detach", dry_run=True))
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        payload = self.parse_dry_run_object(proc)
        self.assertIn("detach", payload, payload)
        self.assertTrue(payload["detach"], payload)
        self.assert_no_launch()

    def test_dry_run_names_that_argv0_is_executed_directly(self):
        """Adversarial finding 3: dry-run JSON names that argv[0] is
        exec'd, with no python3 interpreter prefix."""
        proc = self.invoke(self.full_flags(dry_run=True))
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        payload = self.parse_dry_run_object(proc)
        argv = payload.get("argv")
        self.assertIsInstance(argv, list, payload)
        self.assertTrue(argv, payload)
        self.assertFalse(
            argv[0].rstrip("/").endswith("python3"),
            f"argv[0] is the launcher path, not python3: {argv!r}",
        )
        launcher = payload.get("launcher")
        self.assertIsInstance(launcher, dict, payload)
        self.assertTrue(
            payload.get("exec") is True or launcher.get("exec") is True,
            f"dry-run JSON must name that argv[0] is exec'd: {payload!r}",
        )
        self.assert_no_launch()


class RowScopeCapFromConf(_WrapperFixture):
    """SCOPE_CAP='10' in the scratch conf and an 11-byte scope refuse
    exit 3 naming 11."""

    def test_scope_cap_from_conf_refuses_eleven_bytes_naming_the_count(self):
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(SCOPE_CAP="10"),
        )
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn("SCOPE_CAP='10'", landed)
        data = b"S" * 11
        self._plant_bytes(self.scope_path, data)
        self.assertEqual(self.scope_path.stat().st_size, 11)
        proc = self.invoke(self.full_flags(dry_run=False))
        line = self.assert_wire_abort(proc, "scope-cap", named=("11",))
        self.assertRegex(
            line,
            r"\b11\b",
            f"must name the byte count 11 as a token: {line!r}",
        )
        self.assertNotIn("record-target", line.lower())


class RowLaneNameJobsRoot(_WrapperFixture):
    """A detached launch with LANE_NAME='lanex' creates the job
    directory under <xdg>/lanex/dispatch."""

    RECORD_ID = "20260901T000000Z-plan-grok-lanex1"

    def test_lane_name_from_conf_creates_the_job_dir_under_xdg(self):
        record_id = self.RECORD_ID
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(LANE_NAME="lanex"),
        )
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn("LANE_NAME='lanex'", landed)
        expected = self.xdg / "lanex" / "dispatch" / record_id
        self._plant_python_sentinel(
            self.pin,
            "import os, pathlib, sys\n"
            "jobs = os.environ.get('DISPATCH_JOBS') or ''\n"
            "if jobs:\n"
            f"    pathlib.Path(jobs).joinpath({record_id!r})"
            ".mkdir(parents=True, exist_ok=True)\n"
            f"sys.stdout.write('record: {record_id}\\n')\n"
            "sys.stdout.flush()\n",
        )
        proc = self.invoke(
            self.full_flags("--detach", dry_run=False),
            extra_env={"DISPATCH_JOBS": None},
            timeout=8,
        )
        try:
            self.assertEqual(proc.returncode, 0, self.combined(proc))
            self.assertTrue(
                expected.is_dir(),
                f"job dir missing under lanex: {expected}",
            )
            agentscient = (
                self.xdg / "agentscient" / "dispatch" / record_id
            )
            self.assertFalse(
                agentscient.exists(),
                f"job dir used the literal lane name: {agentscient}",
            )
        finally:
            self._reap_reported_pid(proc)


class RowLocalConf(_WrapperFixture):
    """A sibling lane.local.conf overriding MODEL_GROK wins in the
    dry-run argv; one setting LANE_NAME refuses naming local-key."""

    def test_local_conf_model_grok_wins_in_the_dry_run_argv(self):
        local = self.conf_path.parent / "lane.local.conf"
        self._plant_bytes(local, b"MODEL_GROK='from-local'\n")
        self.assertEqual(
            local.read_text(encoding="utf-8"), "MODEL_GROK='from-local'\n",
        )
        proc = self.invoke(self.full_flags(omit=("model",)))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(argv[argv.index("--model") + 1], "from-local")
        self.assertNotEqual(
            argv[argv.index("--model") + 1], self.conf_model_grok,
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()

    def test_local_conf_setting_a_name_key_refuses_local_key(self):
        self.assertEqual(len(NAME_KEYS), 5, NAME_KEYS)
        for key in NAME_KEYS:
            with self.subTest(key=key):
                local = self.conf_path.parent / "lane.local.conf"
                self._plant_bytes(local, f"{key}='from-local'\n".encode())
                self.assertIn(key, local.read_text(encoding="utf-8"))
                proc = self.invoke(self.full_flags(dry_run=False))
                self.assert_wire_abort(
                    proc, "local-key", named=(key, str(local)),
                )


class RowMissingScopeCap(_WrapperFixture):
    """A conf missing SCOPE_CAP refuses naming the key and the file."""

    def test_a_conf_missing_scope_cap_refuses_naming_the_key_and_file(self):
        keys = self._conf_kwargs()
        self.assertIn("SCOPE_CAP", keys)
        del keys["SCOPE_CAP"]
        self.assertNotIn("SCOPE_CAP", keys)
        self._plant_conf(self.conf_path, **keys)
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertNotIn("SCOPE_CAP", landed)
        proc = self.invoke(self.full_flags(dry_run=False))
        self.assert_wire_abort(
            proc, "conf-key",
            named=("SCOPE_CAP", str(self.conf_path)),
        )


class RowCheckNames(_WrapperFixture):
    """The wrapper exports CHECK_NAMES and refuses a conf that still
    says CHECK_NAME.

    The exported value is not the production literal 'lane app', so a
    wrapper that writes that literal without reading the key cannot
    pass.
    """

    EXPORT_VALUE = "audit lint"

    def test_wrapper_exports_check_names(self):
        self.assertNotEqual(self.EXPORT_VALUE, "lane app")
        keys = self._conf_kwargs(CHECK_NAMES=self.EXPORT_VALUE)
        self.assertIn("CHECK_NAMES", keys)
        self.assertNotIn("CHECK_NAME", keys)
        self.assertEqual(keys["CHECK_NAMES"], self.EXPORT_VALUE)
        self._plant_conf(self.conf_path, **keys)
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn("CHECK_NAMES=", landed)
        self.assertIn(self.EXPORT_VALUE, landed)
        self.assertNotIn("lane app", landed)
        self.assertNotIn("CHECK_NAME=", landed)
        proc = self.invoke(self.full_flags())
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        _argv, env = self.parse_dry_run(proc)
        self.assertEqual(env.get("CHECK_NAMES"), self.EXPORT_VALUE)
        self.assertNotEqual(env.get("CHECK_NAMES"), "lane app")
        self.assertNotIn("CHECK_NAME", env)
        self.assert_no_launch()

    def test_a_conf_that_still_says_check_name_is_refused(self):
        keys = self._conf_kwargs()
        keys["CHECK_NAME"] = "ci"
        self.assertIn("CHECK_NAMES", keys)
        self.assertIn("CHECK_NAME", keys)
        self._plant_conf(self.conf_path, **keys)
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn("CHECK_NAME=", landed)
        self.assertIn("CHECK_NAMES=", landed)
        proc = self.invoke(self.full_flags(dry_run=False))
        self.assert_wire_abort(
            proc, "conf-key",
            named=("CHECK_NAME", str(self.conf_path)),
        )

    def test_a_conf_missing_check_names_refuses_naming_the_key_and_file(self):
        keys = self._conf_kwargs()
        self.assertIn("CHECK_NAMES", keys)
        del keys["CHECK_NAMES"]
        self.assertNotIn("CHECK_NAMES", keys)
        self._plant_conf(self.conf_path, **keys)
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertNotIn("CHECK_NAMES", landed)
        proc = self.invoke(self.full_flags(dry_run=False))
        self.assert_wire_abort(
            proc, "conf-key",
            named=("CHECK_NAMES", str(self.conf_path)),
        )


class RowHarnessModelEffortTable(_WrapperFixture):
    """Grok, Codex, Claude-read, and Claude-plan each resolve their own
    model and effort keys. Env beats conf; the flag beats env; a
    MODEL_<HARNESS>_<JOB> suffix beats the harness key. A wrapper that
    routes every harness through MODEL_GROK fails."""

    CASES = (
        ("grok", "wrap-job", "MODEL_GROK", "EFFORT_GROK",
         "wrap-model-conf-grok", "wrap-effort-conf-grok"),
        ("codex", "wrap-job", "MODEL_CODEX", "EFFORT_CODEX",
         "wrap-model-conf-codex", "wrap-effort-conf-codex"),
        ("claude", "review", "MODEL_CLAUDE_READ", "EFFORT_CLAUDE",
         "wrap-model-conf-claude-read", "wrap-effort-conf-claude"),
        ("claude", "plan", "MODEL_CLAUDE_PLAN", "EFFORT_CLAUDE",
         "wrap-model-conf-claude-plan", "wrap-effort-conf-claude"),
    )

    def test_conf_model_and_effort_by_harness_and_job_class(self):
        self.assertEqual(len(self.CASES), 4, self.CASES)
        for harness, job, model_key, effort_key, model, effort in self.CASES:
            with self.subTest(harness=harness, job=job, layer="conf"):
                self._plant_conf(self.conf_path, **self._conf_kwargs())
                proc = self.invoke(self.full_flags(
                    harness=harness, job=job, omit=("model", "effort"),
                ))
                argv, _env = self.parse_dry_run(proc)
                self.assertEqual(proc.returncode, 0, self.combined(proc))
                self.assertEqual(argv[argv.index("--harness") + 1], harness)
                self.assertEqual(argv[argv.index("--model") + 1], model)
                self.assertEqual(argv[argv.index("--effort") + 1], effort)
                if harness != "grok":
                    self.assertNotEqual(
                        argv[argv.index("--model") + 1],
                        self.conf_model_grok,
                    )
                    self.assertNotEqual(
                        argv[argv.index("--effort") + 1],
                        self.conf_effort_grok,
                    )
                self.assert_no_launch()

    def test_env_beats_conf_for_each_harness_model(self):
        self.assertEqual(len(self.CASES), 4, self.CASES)
        for harness, job, model_key, _effort_key, _model, _effort in self.CASES:
            with self.subTest(harness=harness, job=job, layer="env"):
                env_model = f"env-{harness}-{job}"
                self.assertNotEqual(env_model, _model)
                proc = self.invoke(
                    self.full_flags(
                        harness=harness, job=job, omit=("model",),
                    ),
                    extra_env={model_key: env_model},
                )
                argv, _env = self.parse_dry_run(proc)
                self.assertEqual(proc.returncode, 0, self.combined(proc))
                self.assertEqual(argv[argv.index("--model") + 1], env_model)
                self.assert_no_launch()

    def test_flag_beats_env_for_each_harness_model(self):
        self.assertEqual(len(self.CASES), 4, self.CASES)
        for harness, job, model_key, _effort_key, _model, _effort in self.CASES:
            with self.subTest(harness=harness, job=job, layer="flag"):
                env_model = f"env-{harness}-{job}"
                flag_model = f"flag-{harness}-{job}"
                self.assertNotEqual(flag_model, env_model)
                proc = self.invoke(
                    self.full_flags(
                        harness=harness, job=job, model=flag_model,
                    ),
                    extra_env={model_key: env_model},
                )
                argv, _env = self.parse_dry_run(proc)
                self.assertEqual(proc.returncode, 0, self.combined(proc))
                self.assertEqual(argv[argv.index("--model") + 1], flag_model)
                self.assertNotEqual(
                    argv[argv.index("--model") + 1], env_model,
                )
                self.assert_no_launch()

    def test_job_suffix_beats_harness_model_except_when_keys_collide(self):
        cases = [c for c in self.CASES if c[1] != "plan"]
        self.assertGreaterEqual(len(cases), 3, cases)
        for harness, job, _model_key, _effort_key, _model, _effort in cases:
            with self.subTest(harness=harness, job=job, layer="suffix"):
                suffix = (
                    f"MODEL_{harness.upper()}_"
                    f"{job.upper().replace('-', '_')}"
                )
                suffix_model = f"job-{harness}-{job}"
                self._plant_conf(
                    self.conf_path,
                    **self._conf_kwargs(**{suffix: suffix_model}),
                )
                landed = self.conf_path.read_text(encoding="utf-8")
                self.assertIn(suffix, landed)
                proc = self.invoke(self.full_flags(
                    harness=harness, job=job, omit=("model",),
                ))
                argv, _env = self.parse_dry_run(proc)
                self.assertEqual(proc.returncode, 0, self.combined(proc))
                self.assertEqual(
                    argv[argv.index("--model") + 1], suffix_model,
                )
                self.assert_no_launch()


class RowThreeLayer(_WrapperFixture):
    """Environment beats local file beats conf, for an allowed key."""

    def test_env_beats_local_file_beats_conf_for_model_grok(self):
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(MODEL_GROK="from-conf"),
        )
        local = self.conf_path.parent / "lane.local.conf"
        self._plant_bytes(local, b"MODEL_GROK='from-local'\n")
        self.assertTrue(local.is_file())
        proc = self.invoke(
            self.full_flags(omit=("model",)),
            extra_env={"MODEL_GROK": "from-env"},
        )
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(argv[argv.index("--model") + 1], "from-env")
        self.assertNotEqual(argv[argv.index("--model") + 1], "from-local")
        self.assertNotEqual(argv[argv.index("--model") + 1], "from-conf")
        self.assert_no_launch()


class RowInvalidForm(_WrapperFixture):
    """Double-quoted, unquoted, export, and command-substitution lines
    refuse syntax through the Bash reader; substitution must not run."""

    def test_double_quoted_assignment_refuses_syntax(self):
        text = "MODEL_GROK=\"double-quoted\"\n"
        self._plant_bytes(self.conf_path, text.encode("utf-8"))
        proc = self.invoke(self.full_flags(dry_run=False))
        self.assert_wire_abort(proc, "syntax")

    def test_unquoted_assignment_refuses_syntax(self):
        text = "MODEL_GROK=unquoted\n"
        self._plant_bytes(self.conf_path, text.encode("utf-8"))
        proc = self.invoke(self.full_flags(dry_run=False))
        self.assert_wire_abort(proc, "syntax")

    def test_export_assignment_refuses_syntax(self):
        text = "export MODEL_GROK='from-export'\n"
        self._plant_bytes(self.conf_path, text.encode("utf-8"))
        proc = self.invoke(self.full_flags(dry_run=False))
        self.assert_wire_abort(proc, "syntax")

    def test_command_substitution_does_not_run_and_refuses_syntax(self):
        witness = self.scratch / "pwned-wrapper"
        self.assertFalse(witness.exists(), "plant: witness must start absent")
        text = f'MODEL_GROK="$(printf PWNED > {witness})"\n'
        self._plant_bytes(self.conf_path, text.encode("utf-8"))
        proc = self.invoke(self.full_flags(dry_run=False))
        self.assert_wire_abort(proc, "syntax")
        self.assertFalse(
            witness.exists(),
            "command substitution must not execute; "
            f"witness="
            f"{witness.read_text(encoding='utf-8') if witness.exists() else ''!r}",
        )


class RowDispatchConfRetired(_WrapperFixture):
    """DISPATCH_CONF is retired; a decoy on that name must not win."""

    def test_dispatch_conf_env_does_not_affect_dispatch(self):
        decoy = self.scratch / "old-dispatch.conf"
        self._plant_conf(
            decoy, **self._conf_kwargs(MODEL_GROK="from-dispatch-conf"),
        )
        self._plant_conf(
            self.conf_path, **self._conf_kwargs(MODEL_GROK="from-lane-conf"),
        )
        self.assertNotEqual("from-lane-conf", "from-dispatch-conf")
        proc = self.invoke(
            self.full_flags(omit=("model",)),
            extra_env={"DISPATCH_CONF": str(decoy)},
        )
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(
            argv[argv.index("--model") + 1], "from-lane-conf",
        )
        self.assertNotEqual(
            argv[argv.index("--model") + 1], "from-dispatch-conf",
        )
        self.assert_no_launch()


class RowAgentIdentity(_WrapperFixture):
    """Identity for the launched env: --agent if passed; else WF_AGENT
    when it matches Name <address>; else WF_AGENT_DEFAULT. A Grok-led
    session that already exports a well-formed WF_AGENT does not need
    WF_AGENT_DEFAULT in conf or local conf.
    """

    def _assert_dry_run_identity(self, proc, identity: str) -> None:
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(env.get("WF_AGENT"), identity, self.combined(proc))
        self.assertNotEqual(env.get("WF_AGENT"), CONF_AGENT)
        self.assertNotIn("--agent", argv)
        self.assert_no_launch()

    def test_exported_name_address_wf_agent_is_the_launched_identity(self):
        self.assertRegex(ENV_AGENT, r".+ <.+>")
        self.assertNotEqual(ENV_AGENT, CONF_AGENT)
        self.assertNotEqual(ENV_AGENT, FLAG_AGENT)
        proc = self.invoke(
            self.full_flags(omit=("agent",)),
            extra_env={"WF_AGENT": ENV_AGENT},
        )
        self._assert_dry_run_identity(proc, ENV_AGENT)

    def test_exported_name_address_wf_agent_reaches_the_foreground_launcher(self):
        self.assertRegex(ENV_AGENT, r".+ <.+>")
        self.assertNotEqual(ENV_AGENT, CONF_AGENT)
        self.assertNotEqual(ENV_AGENT, FLAG_AGENT)
        env_log = self.scratch / "launcher-env.json"
        self._plant_python_sentinel(
            self.pin,
            "import json, os, pathlib\n"
            f"pathlib.Path({str(env_log)!r}).write_text("
            "json.dumps({'WF_AGENT': os.environ.get('WF_AGENT')}))\n"
            f"pathlib.Path({str(self.marker)!r}).write_text('launched')\n",
        )
        proc = self.invoke(
            self.full_flags(omit=("agent",), dry_run=False),
            extra_env={"WF_AGENT": ENV_AGENT},
            timeout=8,
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertTrue(self.marker.exists(), "foreground path must launch")
        self.assertTrue(env_log.is_file(), "sentinel recorded env")
        launched = json.loads(env_log.read_text(encoding="utf-8"))
        self.assertEqual(launched.get("WF_AGENT"), ENV_AGENT)
        self.assertNotEqual(launched.get("WF_AGENT"), CONF_AGENT)
        self.assertNotEqual(launched.get("WF_AGENT"), FLAG_AGENT)

    def test_agent_flag_beats_exported_wf_agent(self):
        self.assertRegex(FLAG_AGENT, r".+ <.+>")
        self.assertRegex(ENV_AGENT, r".+ <.+>")
        self.assertNotEqual(FLAG_AGENT, ENV_AGENT)
        self.assertNotEqual(FLAG_AGENT, CONF_AGENT)
        proc = self.invoke(
            self.full_flags(agent=FLAG_AGENT),
            extra_env={"WF_AGENT": ENV_AGENT},
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(env.get("WF_AGENT"), FLAG_AGENT)
        self.assertNotEqual(env.get("WF_AGENT"), ENV_AGENT)
        self.assertNotEqual(env.get("WF_AGENT"), CONF_AGENT)
        self.assertNotIn("--agent", argv)
        self.assert_no_launch()

    def test_malformed_exported_wf_agent_falls_through_to_conf_default(self):
        self.assertNotEqual(MALFORMED_AGENT, CONF_AGENT)
        self.assertNotRegex(MALFORMED_AGENT, r".+ <.+>")
        proc = self.invoke(
            self.full_flags(omit=("agent",)),
            extra_env={"WF_AGENT": MALFORMED_AGENT},
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(env.get("WF_AGENT"), CONF_AGENT)
        self.assertNotEqual(env.get("WF_AGENT"), MALFORMED_AGENT)
        self.assertNotEqual(env.get("WF_AGENT"), ENV_AGENT)
        self.assertNotIn("--agent", argv)
        self.assert_no_launch()

    def test_exported_wf_agent_does_not_need_conf_wf_agent_default(self):
        self.assertRegex(ENV_AGENT, r".+ <.+>")
        keys = self._conf_kwargs()
        self.assertIn("WF_AGENT_DEFAULT", keys)
        del keys["WF_AGENT_DEFAULT"]
        self.assertNotIn("WF_AGENT_DEFAULT", keys)
        self._plant_conf(self.conf_path, **keys)
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertNotIn("WF_AGENT_DEFAULT", landed)
        self.assertNotEqual(ENV_AGENT, CONF_AGENT)
        proc = self.invoke(
            self.full_flags(omit=("agent",)),
            extra_env={"WF_AGENT": ENV_AGENT},
        )
        self._assert_dry_run_identity(proc, ENV_AGENT)

    def test_local_conf_wf_agent_default_does_not_override_exported_wf_agent(self):
        self.assertRegex(ENV_AGENT, r".+ <.+>")
        self.assertRegex(FABLE_AGENT, r".+ <.+>")
        self.assertNotEqual(ENV_AGENT, FABLE_AGENT)
        self.assertNotEqual(ENV_AGENT, CONF_AGENT)
        self.assertNotEqual(FABLE_AGENT, CONF_AGENT)
        local = self.conf_path.parent / "lane.local.conf"
        self._plant_bytes(
            local,
            f"WF_AGENT_DEFAULT={_bash_single_quote(FABLE_AGENT)}\n".encode(),
        )
        self.assertIn(FABLE_AGENT, local.read_text(encoding="utf-8"))
        proc = self.invoke(
            self.full_flags(omit=("agent",)),
            extra_env={"WF_AGENT": ENV_AGENT},
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(env.get("WF_AGENT"), ENV_AGENT)
        self.assertNotEqual(env.get("WF_AGENT"), FABLE_AGENT)
        self.assertNotEqual(env.get("WF_AGENT"), CONF_AGENT)
        self.assertNotIn("--agent", argv)
        self.assert_no_launch()


class _WorkerWrapperFixture(_WrapperFixture):
    """Scratch PATH bins for the provisional worker-selection tests."""

    def setUp(self):
        super().setUp()
        self.bindir, self.bins = worker_conf.plant_named_bins(
            self,
            self.scratch,
            worker_conf.DEFAULT_WORKERS + ("agy",),
        )
        self.worker_path = worker_conf.path_with(self.bindir)

    def env(self, extra: dict[str, str | None] | None = None) -> dict[str, str]:
        extra = dict(extra or {})
        extra.setdefault("PATH", self.worker_path)
        return super().env(extra)

    def assert_class_abort(
        self,
        proc,
        class_name: str,
        *,
        named: tuple[str, ...] = (),
    ) -> str:
        line = self.assert_wire_abort(proc, class_name, named=named)
        token = class_name.lower().replace("_", "-")
        self.assertTrue(
            line.lower().startswith(token + ":")
            or f" {token}:" in line.lower()
            or line.lower().startswith(f"{token} "),
            f"class {token} must name the refusal, not a later word: {line!r}",
        )
        return line

    def record_child_env(self, log: Path, keys: tuple[str, ...]) -> None:
        """Plant the existing python sentinel to dump selected child env keys."""
        self.assertGreater(len(keys), 0, keys)
        self._plant_python_sentinel(
            self.pin,
            "import json, os, pathlib\n"
            f"pathlib.Path({str(log)!r}).write_text("
            "json.dumps({k: os.environ.get(k) for k in "
            f"{list(keys)!r}"
            "}))\n"
            f"pathlib.Path({str(self.marker)!r}).write_text('launched')\n",
        )


class ProvisionalWrapperWorkerSelection(_WorkerWrapperFixture):
    """PROVISIONAL: wrapper checks WORKER_HARNESSES through the loader.

    Omitted list keeps the three names and refuses agy. An explicit empty
    list disables every worker. Listing agy makes --harness agy selectable.
    Worker-object sources are pinned on the laneconf CLI. Wrapper
    provenance of exported keys is observed in the child environment
    through the existing python sentinel.
    """

    def test_omitted_list_refuses_agy_as_worker_without_launch(self):
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertNotIn("WORKER_HARNESSES", landed)
        proc = self.invoke(self.full_flags(harness="agy", dry_run=False))
        self.assert_class_abort(proc, "worker", named=("agy",))

    def test_listed_agy_reaches_harness_argv(self):
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(WORKER_HARNESSES="claude codex grok agy"),
        )
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn("WORKER_HARNESSES='claude codex grok agy'", landed)
        proc = self.invoke(self.full_flags(harness="agy"))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(argv[argv.index("--harness") + 1], "agy")
        self.assert_no_launch()

    def test_empty_list_refuses_grok_as_worker_without_launch(self):
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(WORKER_HARNESSES=""),
        )
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn("WORKER_HARNESSES=''", landed)
        proc = self.invoke(self.full_flags(harness="grok", dry_run=False))
        self.assert_class_abort(proc, "worker", named=("grok",))

    def test_malformed_harness_name_refuses_worker(self):
        bad = "agy-cli"
        self.assertNotRegex(bad, worker_conf.WORKER_NAME_RE)
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(WORKER_HARNESSES="claude codex grok agy"),
        )
        proc = self.invoke(self.full_flags(harness=bad, dry_run=False))
        self.assert_class_abort(proc, "worker", named=(bad,))

    def test_duplicate_list_refuses_worker_without_launch(self):
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(WORKER_HARNESSES="claude grok grok"),
        )
        proc = self.invoke(self.full_flags(harness="claude", dry_run=False))
        self.assert_class_abort(proc, "worker")

    def test_exported_worker_harnesses_beats_conf(self):
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(WORKER_HARNESSES="claude codex grok"),
        )
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn("WORKER_HARNESSES='claude codex grok'", landed)
        self.assertNotIn("WORKER_HARNESSES='agy'", landed)
        proc = self.invoke(
            self.full_flags(harness="grok", dry_run=False),
            extra_env={"WORKER_HARNESSES": "agy"},
        )
        self.assert_class_abort(proc, "worker", named=("grok",))


class ProvisionalWrapperExecutableSourceAndPath(_WorkerWrapperFixture):
    """PROVISIONAL: EXECUTABLE_<NAME> path, provenance and precedence.

    A file value must not be relabelled as an operator environment
    override. Invalid overrides refuse executable before launch.
    """

    def test_file_executable_agy_is_not_relabelled_as_env(self):
        override = worker_conf.plant_executable(
            self, self.scratch / "override" / "agy",
        )
        key = worker_conf.executable_key("agy")
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(
                WORKER_HARNESSES="claude codex grok agy",
                **{key: str(override)},
            ),
        )
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn(str(override), landed)
        proc = self.invoke(self.full_flags(harness="agy"))
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(argv[argv.index("--harness") + 1], "agy")
        self.assertNotIn(key, env)
        self.assertNotIn("WORKER_HARNESSES", env)
        self.assert_no_launch()

    def test_exported_executable_reaches_the_child_not_the_file_value(self):
        grok_key = worker_conf.executable_key("grok")
        grok_file = worker_conf.plant_executable(
            self, self.scratch / "grok-from-file" / "grok",
        )
        grok_env = worker_conf.plant_executable(
            self, self.scratch / "grok-from-env" / "grok",
        )
        self.assertNotEqual(grok_file, grok_env)
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(**{grok_key: str(grok_file)}),
        )
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn(str(grok_file), landed)
        self.assertNotIn(str(grok_env), landed)
        env_log = self.scratch / "launcher-env.json"
        self.record_child_env(env_log, (grok_key,))
        launched = self.invoke(
            self.full_flags(harness="grok", dry_run=False),
            extra_env={grok_key: str(grok_env)},
            timeout=8,
        )
        self.assertEqual(launched.returncode, 0, self.combined(launched))
        self.assertTrue(self.marker.exists(), "foreground path must launch")
        self.assertTrue(env_log.is_file(), "sentinel recorded env")
        child = json.loads(env_log.read_text(encoding="utf-8"))
        self.assertEqual(child.get(grok_key), str(grok_env))
        self.assertNotEqual(child.get(grok_key), str(grok_file))

    def test_relative_executable_agy_refuses_executable_without_launch(self):
        relative = "./agy"
        self.assertFalse(Path(relative).is_absolute())
        key = worker_conf.executable_key("agy")
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(
                WORKER_HARNESSES="claude codex grok agy",
                **{key: relative},
            ),
        )
        proc = self.invoke(self.full_flags(harness="agy", dry_run=False))
        self.assert_class_abort(proc, "executable", named=(relative,))

    def test_empty_executable_agy_refuses_executable_without_launch(self):
        key = worker_conf.executable_key("agy")
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(
                WORKER_HARNESSES="claude codex grok agy",
                **{key: ""},
            ),
        )
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn(f"{key}=''", landed)
        proc = self.invoke(self.full_flags(harness="agy", dry_run=False))
        self.assert_class_abort(proc, "executable")


class ProvisionalWrapperAgyModelEffort(_WorkerWrapperFixture):
    """PROVISIONAL: agy model/effort use the existing families.

    Nonempty --model wins over MODEL_AGY_<JOB> then MODEL_AGY. Effort
    likewise. agy has no coded model default; absent/empty effort omits
    the token. No supported effort is translated to another level.
    """

    def _agy_conf(self, **overrides: str) -> dict[str, str]:
        keys = self._conf_kwargs(
            WORKER_HARNESSES="claude codex grok agy",
            **overrides,
        )
        return keys

    def test_model_flag_for_agy_beats_conf(self):
        self._plant_conf(
            self.conf_path,
            **self._agy_conf(MODEL_AGY="wrap-model-conf-agy"),
        )
        proc = self.invoke(self.full_flags(harness="agy", model="flag-agy"))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(argv[argv.index("--harness") + 1], "agy")
        self.assertEqual(argv[argv.index("--model") + 1], "flag-agy")
        self.assertNotEqual(argv[argv.index("--model") + 1], "wrap-model-conf-agy")
        self.assert_no_launch()

    def test_omitted_model_uses_model_agy(self):
        conf_model = "wrap-model-conf-agy"
        self._plant_conf(
            self.conf_path,
            **self._agy_conf(MODEL_AGY=conf_model),
        )
        proc = self.invoke(self.full_flags(harness="agy", omit=("model",)))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(argv[argv.index("--model") + 1], conf_model)
        self.assertNotEqual(argv[argv.index("--model") + 1], self.conf_model_grok)
        self.assert_no_launch()

    def test_model_agy_job_suffix_beats_harness_model(self):
        job_model = "wrap-model-job-agy"
        self._plant_conf(
            self.conf_path,
            **self._agy_conf(
                MODEL_AGY="wrap-model-conf-agy",
                MODEL_AGY_WRAP_JOB=job_model,
            ),
        )
        proc = self.invoke(self.full_flags(harness="agy", omit=("model",)))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(argv[argv.index("--model") + 1], job_model)
        self.assertNotEqual(argv[argv.index("--model") + 1], "wrap-model-conf-agy")
        self.assert_no_launch()

    def test_effort_agy_job_suffix_beats_harness_effort(self):
        job_effort = "wrap-effort-job-agy"
        generic = "medium"
        self.assertNotEqual(job_effort, generic)
        self._plant_conf(
            self.conf_path,
            **self._agy_conf(
                EFFORT_AGY=generic,
                EFFORT_AGY_WRAP_JOB=job_effort,
            ),
        )
        proc = self.invoke(self.full_flags(harness="agy", effort=None))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(argv[argv.index("--effort") + 1], job_effort)
        self.assertNotEqual(argv[argv.index("--effort") + 1], generic)
        self.assert_no_launch()

    def test_env_model_agy_beats_conf(self):
        env_model = "wrap-model-env-agy"
        conf_model = "wrap-model-conf-agy"
        self.assertNotEqual(env_model, conf_model)
        self._plant_conf(
            self.conf_path,
            **self._agy_conf(MODEL_AGY=conf_model),
        )
        proc = self.invoke(
            self.full_flags(harness="agy", omit=("model",)),
            extra_env={"MODEL_AGY": env_model},
        )
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(argv[argv.index("--model") + 1], env_model)
        self.assertNotEqual(argv[argv.index("--model") + 1], conf_model)
        self.assert_no_launch()

    def test_absent_model_agy_without_flag_refuses_model(self):
        keys = self._agy_conf()
        self.assertNotIn("MODEL_AGY", keys)
        self._plant_conf(self.conf_path, **keys)
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertNotIn("MODEL_AGY", landed)
        proc = self.invoke(
            self.full_flags(harness="agy", omit=("model",), dry_run=False),
        )
        self.assert_class_abort(proc, "model")

    def test_effort_agy_from_conf_follows_model(self):
        self._plant_conf(
            self.conf_path,
            **self._agy_conf(EFFORT_AGY="high"),
        )
        proc = self.invoke(self.full_flags(harness="agy", effort=None))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertIn("--effort", argv)
        model_at = argv.index("--model")
        self.assertEqual(
            argv[model_at:model_at + 4],
            ["--model", self.model_flag, "--effort", "high"],
        )
        self.assert_no_launch()

    def test_empty_effort_agy_omits_effort_token(self):
        self._plant_conf(
            self.conf_path,
            **self._agy_conf(EFFORT_AGY=""),
        )
        proc = self.invoke(self.full_flags(harness="agy", effort=None))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertNotIn("--effort", argv)
        self.assert_no_launch()

    def test_absent_effort_agy_omits_effort_token(self):
        keys = self._agy_conf()
        self.assertNotIn("EFFORT_AGY", keys)
        self._plant_conf(self.conf_path, **keys)
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertNotIn("EFFORT_AGY", landed)
        proc = self.invoke(self.full_flags(harness="agy", effort=None))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertNotIn("--effort", argv)
        self.assert_no_launch()

    def test_effort_flag_for_agy_is_not_translated(self):
        self._plant_conf(
            self.conf_path,
            **self._agy_conf(EFFORT_AGY="medium"),
        )
        proc = self.invoke(self.full_flags(harness="agy", effort="high"))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(argv[argv.index("--effort") + 1], "high")
        self.assertNotEqual(argv[argv.index("--effort") + 1], "medium")
        self.assertNotEqual(argv[argv.index("--effort") + 1], "xhigh")
        self.assert_no_launch()


class ProvisionalWrapperThreeHarnessUnchanged(_WorkerWrapperFixture):
    """PROVISIONAL: listing agy must not change grok, codex or Claude
    model/effort resolution. Omitted WORKER_HARNESSES keeps the default
    three. Worker-object sources stay on the laneconf CLI.
    """

    CASES = RowHarnessModelEffortTable.CASES

    def test_agy_listed_leaves_grok_codex_claude_model_effort_unchanged(self):
        self.assertEqual(len(self.CASES), 4, self.CASES)
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(WORKER_HARNESSES="claude codex grok agy"),
        )
        for harness, job, _model_key, _effort_key, model, effort in self.CASES:
            with self.subTest(harness=harness, job=job):
                proc = self.invoke(self.full_flags(
                    harness=harness, job=job, omit=("model", "effort"),
                ))
                argv, _env = self.parse_dry_run(proc)
                self.assertEqual(proc.returncode, 0, self.combined(proc))
                self.assertEqual(argv[argv.index("--harness") + 1], harness)
                self.assertEqual(argv[argv.index("--model") + 1], model)
                self.assertEqual(argv[argv.index("--effort") + 1], effort)
                self.assert_no_launch()

    def test_omitted_list_grok_keeps_argv_and_default_worker_source(self):
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertNotIn("WORKER_HARNESSES", landed)
        proc = self.invoke(self.full_flags())
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(argv, self.expected_argv())
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(env.get("WF_AGENT"), FLAG_AGENT)
        self.assert_no_launch()

    def test_claude_plan_fallback_still_uses_model_claude_plan(self):
        self._plant_conf(
            self.conf_path,
            **self._conf_kwargs(WORKER_HARNESSES="claude codex grok agy"),
        )
        proc = self.invoke(self.full_flags(
            harness="claude", job="plan", omit=("model", "effort"),
        ))
        argv, _env = self.parse_dry_run(proc)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(
            argv[argv.index("--model") + 1],
            "wrap-model-conf-claude-plan",
        )
        self.assertNotEqual(
            argv[argv.index("--model") + 1],
            "wrap-model-conf-claude-read",
        )
        self.assert_no_launch()


if __name__ == "__main__":
    unittest.main()

