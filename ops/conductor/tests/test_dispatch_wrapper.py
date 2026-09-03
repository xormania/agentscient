"""Dispatch wrapper acceptance tests, written from the spec.

Contract: `ops/docs/scratch/dispatch-wrapper-spec.md` Acceptance rows
1-7. The wrapper and its conf do not exist yet. Tests invoke

    bash <repo>/ops/conductor/tools/dispatch.sh <flags>

with a scratch conf and scratch scope file per case. They never write
`ops/conductor/tools/dispatch.conf` and never add or remove worktrees.

Argv assertions compare exact lists, never a substring of a joined
command line.

Pins that the spec left unnamed (reported as findings, not silently
assumed) live in PIN_* comments below. Callee flag names come from
`ops/devlane/dispatch/CONTRACT.md` §Verbs, not from launch.py source.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WRAPPER = REPO / "ops" / "conductor" / "tools" / "dispatch.sh"
REAL_CONF = REPO / "ops" / "conductor" / "tools" / "dispatch.conf"
TOOLS_DIR = WRAPPER.parent

SCOPE_CAP = 1024
FLAG_AGENT = "Wrap Agent <noreply@example.invalid>"
CONF_AGENT = "Conf Agent <noreply@example.invalid>"
ENV_AGENT = "Env Agent <noreply@example.invalid>"
NO_WORKTREE_BRANCH = "no-wt-dispatch-wrapper-9f3c1e2a"

# PIN_CONF_OVERRIDE: spec names only the real conf path. Tests point at a
# scratch conf through DISPATCH_CONF so the real file is never touched.
CONF_ENV = "DISPATCH_CONF"

# PIN_DRY_RUN_SHAPE: spec says dry-run prints argv and env deltas, not
# how. Tests parse one JSON object {"argv": [str, ...], "env": {k: v}}.
# PIN_ARGV_MAP: wrapper --job X → launch.py positional X; --scope-file
# contents → --scope TEXT; --worktree/--branch resolve to --ref (HEAD of
# that tree) and --lineage (symbolic-ref if attached); --agent and
# --timeout are env deltas, not callee flags. Order follows CONTRACT.md
# §Verbs. argv[0] is LAUNCHER_PIN with no python3 prefix.
# PIN_ENV_KEYS: env overrides use the conf key names. Winning timeout
# is env delta DEFAULT_TIMEOUT. Winning agent is env delta WF_AGENT.


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
    ref: str,
    lineage: str | None = None,
    unit: str | None = None,
    stage: str | None = None,
    scope: str | None = None,
    input_path: Path | str | None = None,
    follows: str | None = None,
) -> list[str]:
    argv = [
        str(pin),
        job,
        "--harness",
        harness,
        "--model",
        model,
        "--ref",
        ref,
    ]
    if lineage:
        argv.extend(["--lineage", lineage])
    if unit:
        argv.extend(["--unit", unit])
    if stage:
        argv.extend(["--stage", stage])
    if scope is not None:
        argv.extend(["--scope", scope])
    if input_path is not None:
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
        self._plant_conf(
            self.conf_path,
            LAUNCHER_PIN=str(self.pin),
            DEFAULT_TIMEOUT=self.conf_timeout,
            WF_AGENT_DEFAULT=CONF_AGENT,
            MODEL_GROK=self.conf_model_grok,
            MODEL_CODEX="wrap-model-conf-codex",
            MODEL_CLAUDE_READ="wrap-model-conf-claude-read",
            MODEL_CLAUDE_PLAN="wrap-model-conf-claude-plan",
        )

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

    def _plant_sentinel(self, path: Path, marker: Path) -> None:
        body = (
            "#!/bin/sh\n"
            f"printf launched > '{marker}'\n"
            "exit 0\n"
        )
        path.write_text(body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        landed = path.read_text(encoding="utf-8")
        self.assertEqual(landed, body, f"sentinel plant did not land: {path}")
        self.assertTrue(os.access(path, os.X_OK), f"sentinel not executable: {path}")
        self.assertFalse(marker.exists(), "plant: marker must not pre-exist")

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

    def env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
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
            env.update(extra)
        return env

    def invoke(self, flags: list[str], *, extra_env: dict[str, str] | None = None):
        argv = ["bash", str(WRAPPER), *flags]
        # Absent wrapper is not a collection error and not bash 127: that
        # would make every case fail for the same reason. Return an empty
        # payload so the contracted assertion (exact argv, named refusal
        # text, exit 3) is what goes red.
        if not WRAPPER.is_file():
            return subprocess.CompletedProcess(
                args=argv, returncode=0, stdout="", stderr="",
            )
        return subprocess.run(
            argv,
            cwd=str(REPO),
            env=self.env(extra_env),
            capture_output=True,
            text=True,
            check=False,
        )

    def combined(self, proc: subprocess.CompletedProcess) -> str:
        return f"{proc.stdout or ''}{proc.stderr or ''}"

    def full_flags(self, *extra: str, dry_run: bool = True, **kw) -> list[str]:
        omit = set(kw.pop("omit", ()))
        pairs = [
            ("worktree", "--worktree", str(kw.get("worktree", self.worktree))),
            ("branch", "--branch", kw.get("branch")),
            ("job", "--job", kw.get("job", self.job)),
            ("harness", "--harness", kw.get("harness", self.harness)),
            ("model", "--model", kw.get("model", self.model_flag)),
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
            flags.extend([flag, value])
        flags.extend(extra)
        if dry_run:
            flags.append("--dry-run")
        return flags

    def expected_argv(self, **kw) -> list[str]:
        return expected_launch_argv(
            pin=kw.get("pin", self.pin),
            job=kw.get("job", self.job),
            harness=kw.get("harness", self.harness),
            model=kw.get("model", self.model_flag),
            ref=kw.get("ref", self.ref),
            lineage=kw.get("lineage", self.lineage),
            unit=kw.get("unit", self.unit),
            stage=kw.get("stage", self.stage),
            scope=kw.get("scope", self.scope_text),
            input_path=kw.get("input_path", self.input_path),
            follows=kw.get("follows", self.follows),
        )

    def parse_dry_run(
        self, proc: subprocess.CompletedProcess
    ) -> tuple[list[str], dict[str, str]]:
        if not WRAPPER.is_file():
            return [], {}
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


class Row1FullFlagSetArgv(_WrapperFixture):
    """Acceptance 1: full flags → exact launch.py argv; conf vs flag."""

    def test_full_flag_set_produces_exactly_the_expected_launch_argv(self):
        proc = self.invoke(self.full_flags())
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(argv, self.expected_argv())
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(env.get("WF_AGENT"), FLAG_AGENT)
        self.assertEqual(env.get("DEFAULT_TIMEOUT"), self.flag_timeout)
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
    """Acceptance 7: scratch conf; env beats conf; flag beats both."""

    def test_scratch_conf_launcher_pin_and_timeout_are_honoured(self):
        proc = self.invoke(self.full_flags(omit=("timeout", "model", "agent")))
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(argv[:1], [str(self.pin)])
        self.assertEqual(env.get("DEFAULT_TIMEOUT"), self.conf_timeout)
        self.assertEqual(
            argv,
            self.expected_argv(pin=self.pin, model=self.conf_model_grok),
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(env.get("WF_AGENT"), CONF_AGENT)
        self.assert_no_launch()

    def test_environment_override_beats_conf(self):
        env_timeout = "45"
        extra = {
            "LAUNCHER_PIN": str(self.pin_env),
            "DEFAULT_TIMEOUT": env_timeout,
            "WF_AGENT_DEFAULT": ENV_AGENT,
            "MODEL_GROK": "wrap-model-env-grok",
        }
        proc = self.invoke(
            self.full_flags(omit=("timeout", "model", "agent")),
            extra_env=extra,
        )
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(argv[:1], [str(self.pin_env)])
        self.assertEqual(env.get("DEFAULT_TIMEOUT"), env_timeout)
        self.assertEqual(
            argv,
            self.expected_argv(pin=self.pin_env, model="wrap-model-env-grok"),
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(env.get("WF_AGENT"), ENV_AGENT)
        self.assert_no_launch()

    def test_timeout_flag_beats_environment_and_conf(self):
        extra = {"DEFAULT_TIMEOUT": "45"}
        proc = self.invoke(
            self.full_flags(timeout="33", omit=("model", "agent")),
            extra_env=extra,
        )
        argv, env = self.parse_dry_run(proc)
        self.assertEqual(env.get("DEFAULT_TIMEOUT"), "33")
        self.assertNotEqual(env.get("DEFAULT_TIMEOUT"), "45")
        self.assertNotEqual(env.get("DEFAULT_TIMEOUT"), self.conf_timeout)
        self.assertEqual(
            argv,
            self.expected_argv(model=self.conf_model_grok),
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_no_launch()


if __name__ == "__main__":
    unittest.main()
