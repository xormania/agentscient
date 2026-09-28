"""Laneconf defaults-verb acceptance tests, written from the contract.

Contracts (only): the defaults verb in the slice-1 plan (PLAN.md §Verb
and the named cases under Slice 1) and the inherited
`ops/conductor/instrument-conventions.md`. The instrument
`ops/conductor/tools/laneconf.py` is the subject and is not read here.

Tests plant a scratch git tree and a scratch conf through `LANE_CONF`.
The tracked `ops/lane.conf` is never written. The tool is copied by
bytes to a runner directory outside the scanned tree so a planted
exception table can sit beside the reader without entering `ops/`.

At this ref the verb is absent (`defaults` exits 2 class `arguments`).
Each case below asserts the contracted exit and named output, so that
absence is the red, not a skip or a collection error.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "laneconf.py"
EXCEPTIONS_REL = "ops/conductor/tools/defaults-exceptions.json"
EXCEPTIONS_LIVE = REPO / "ops" / "conductor" / "tools" / "defaults-exceptions.json"
CONF_ENV = "LANE_CONF"
RUN_CAP = 60

ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)

# Distinctive values so a clean scratch tree cannot match the named
# identity tokens (dev, master, agentscient, ../wt, 900, 1024).
SCRATCH_DEFAULTS = {
    "LANE_NAME": "lanetest",
    "TRUNK_BRANCH": "trunktest",
    "RELEASE_BRANCH": "reltest",
    "REPO_SLUG": "org/proj",
    "CHECK_NAMES": "lane app",
    "WF_AGENT_DEFAULT": "Conf Agent <conf@example.invalid>",
    "LANE_AUTHOR": "Lane Owner <lane-owner@example.invalid>",
    "WORKTREE_ROOT": "/tmp/wt-scratch",
    "ADDRESS_GROK": "addr-grok@example.invalid",
    "ADDRESS_CODEX": "addr-codex@example.invalid",
    "ADDRESS_CLAUDE": "addr-claude@example.invalid",
    "MODEL_GROK": "model-grok",
    "MODEL_CODEX": "model-codex",
    "MODEL_CODEX_SECURITY_AUDIT": "model-codex-sec",
    "MODEL_CLAUDE_READ": "model-claude-read",
    "MODEL_CLAUDE_PLAN": "model-claude-plan",
    "EFFORT_GROK": "effort-grok",
    "EFFORT_CODEX": "effort-codex",
    "EFFORT_CLAUDE": "effort-claude",
    "WALL_DEFAULT": "4242",
    "SCOPE_CAP": "4243",
}

CONF_VALUE_KEYS = (
    "LANE_NAME",
    "WORKTREE_ROOT",
    "ADDRESS_GROK",
    "MODEL_GROK",
    "EFFORT_GROK",
    "LANE_AUTHOR",
    "WALL_DEFAULT",
    "SCOPE_CAP",
    "MODEL_CODEX_SECURITY_AUDIT",
)

SKIP_DIRS = ("tests", "fixtures", "archive", "infra")

# PIN_NAMED_TOKENS: short `dev` is a token as '"dev"' and "'dev'" and
# as a compare == "dev" / == 'dev'. The len>=4 filter is gone.
NAMED_TOKEN_PLANTS = (
    ("ops/bin/double_dev.py", 'marker = "dev"\n', '"dev"'),
    ("ops/bin/single_dev.py", "marker = 'dev'\n", "'dev'"),
    (
        "ops/bin/eq_double_dev.py",
        'if branch == "dev":\n    pass\n',
        '== "dev"',
    ),
    (
        "ops/bin/eq_single_dev.py",
        "if branch == 'dev':\n    pass\n",
        "== 'dev'",
    ),
    ("ops/bin/master.py", 'marker = "master"\n', '"master"'),
    (
        "ops/bin/lane_name.py",
        'marker = "agentscient"\n',
        '"agentscient"',
    ),
    (
        "ops/bin/slug.py",
        'marker = "uscient/agentscient"\n',
        "uscient/agentscient",
    ),
    ("ops/bin/wt.py", 'marker = "../wt"\n', "../wt"),
)

EMPTY_EXCEPTIONS = {"exceptions": []}

LOCATE_REL = "ops/conductor/tools/locate.py"
LOCATE_LINE = 'os.environ.get("LANE_CONF", DEFAULT_CONF)'
LOCATE_BODY = f"DEFAULT_CONF = 'x'\n{LOCATE_LINE}\n"

SKIP_DIR_PLANTS = (
    "ops/conductor/tests/dirty.py",
    "ops/devlane/fixtures/dirty.py",
    "ops/archive/dirty.py",
    "ops/devlane/infra/dirty.py",
)

LIVE_IDENTITY_FILES = (
    "ops/conductor/tools/hand.py",
    "ops/conductor/tools/findings.py",
    "ops/conductor/tools/onboard.py",
    "ops/conductor/tools/decisions.py",
)


def conf_text(**overrides: object) -> str:
    omit = tuple(overrides.pop("omit", ()) or ())
    keys = dict(SCRATCH_DEFAULTS)
    for name, value in overrides.items():
        keys[name] = str(value)
    for name in omit:
        keys.pop(name, None)
    lines = ["# scratch lane conf\n"]
    for name, value in keys.items():
        lines.append(f"{name}='{value}'\n")
    return "".join(lines)


def reader_source(keys: tuple[str, ...] | None = None) -> str:
    names = keys or tuple(SCRATCH_DEFAULTS)
    return "".join(f'get("{name}")\n' for name in names)


def py_hit(stmt: str) -> str:
    body = stmt if stmt.endswith("\n") else f"{stmt}\n"
    return "print('ok')\nprint('still-ok')\n" + body


def sh_hit(stmt: str) -> str:
    body = stmt if stmt.endswith("\n") else f"{stmt}\n"
    return "echo ok\necho still-ok\n" + body


def exception_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "lane-conf-locate",
        "kind": "conf-locate",
        "key": "LANE_CONF",
        "fallback": "DEFAULT_CONF",
        "path": LOCATE_REL,
        "line_match": LOCATE_LINE,
        "why": "locates the tracked conf; does not invent a key value",
        "owner": "standing",
    }
    for name, value in overrides.items():
        if value is None:
            row.pop(name, None)
        else:
            row[name] = value
    return row


class _DefaultsFixture(unittest.TestCase):
    """Scratch HOME, scratch git tree, tool copy outside the scan root."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="laneconf-defaults-")
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.scratch = root / "scratch"
        self.xdg = root / "xdg"
        self.runner = root / "runner"
        for path in (self.home, self.scratch, self.xdg, self.runner):
            path.mkdir()
        self.staged = self.runner / "laneconf.py"
        self._stage_tool_bytes()
        self.plant_exceptions_payload(EMPTY_EXCEPTIONS, repo=None)
        self.assertFalse(
            (self.home / ".local" / "state").exists(),
            "plant: isolated HOME has no state dir",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertEqual(len(landed), len(data))

    def _stage_tool_bytes(self) -> None:
        if TOOL.is_file():
            data = TOOL.read_bytes()
            self._plant_bytes(self.staged, data)
            self.assertNotEqual(data, ABSENT_STUB)
        else:
            self._plant_bytes(self.staged, ABSENT_STUB)
        self.assertTrue(self.staged.is_file())

    def plant_exceptions_payload(
        self,
        payload: dict[str, object],
        *,
        repo: Path | None,
    ) -> None:
        text = json.dumps(payload, indent=2) + "\n"
        data = text.encode("utf-8")
        self._plant_bytes(self.runner / "defaults-exceptions.json", data)
        if repo is not None:
            self._plant_bytes(repo / EXCEPTIONS_REL, data)

    def env(
        self,
        extra: dict[str, str | None] | None = None,
        *,
        lane_conf: Path | str | None = "default",
    ) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "XDG_STATE_HOME": str(self.xdg),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if lane_conf == "default":
            pass
        elif lane_conf is not None:
            env[CONF_ENV] = str(lane_conf)
        if extra:
            for name, value in extra.items():
                if value is None:
                    env.pop(name, None)
                else:
                    env[name] = value
        return env

    def invoke(
        self,
        argv: list[str],
        *,
        repo: Path,
        extra: dict[str, str | None] | None = None,
        timeout: float = RUN_CAP,
    ):
        conf = repo / "ops" / "lane.conf"
        env = self.env(extra, lane_conf=conf)
        cmd = [sys.executable, str(self.staged), *argv]
        try:
            return subprocess.run(
                cmd,
                cwd=str(repo),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(
                f"defaults exceeded {timeout}s; stdout={exc.stdout!r} "
                f"stderr={exc.stderr!r}"
            )

    def invoke_live(
        self,
        argv: list[str],
        extra: dict[str, str | None] | None = None,
        timeout: float = RUN_CAP,
    ):
        env = self.env(extra, lane_conf=None)
        cmd = [sys.executable, str(TOOL), *argv]
        try:
            return subprocess.run(
                cmd,
                cwd=str(REPO),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(
                f"defaults exceeded {timeout}s; stdout={exc.stdout!r} "
                f"stderr={exc.stderr!r}"
            )

    def combined(self, proc: subprocess.CompletedProcess) -> str:
        return f"{proc.stdout or ''}{proc.stderr or ''}"

    def assert_wire_refusal(
        self,
        proc: subprocess.CompletedProcess,
        *,
        class_name: str | None = None,
        named: tuple[str, ...] = (),
        not_class: str = "arguments",
    ) -> str:
        err = proc.stderr or ""
        self.assertEqual(proc.returncode, 2, err or proc.stdout)
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        lower = lines[0].lower()
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, lines[0])
        self.assertLess(lower.index("expected"), lower.index("found"), lines[0])
        self.assertLess(lower.index("found"), lower.index("needed"), lines[0])
        self.assertEqual(
            (proc.stdout or "").strip(),
            "",
            "refusal text belongs on stderr, not stdout",
        )
        if not_class:
            self.assertFalse(
                lower.startswith(not_class.lower() + ":"),
                lines[0],
            )
        if class_name is not None:
            prefix = class_name.lower().replace("_", "-") + ":"
            self.assertTrue(lower.startswith(prefix), lines[0])
        for item in named:
            self.assertIn(item, lines[0], lines[0])
        return lines[0]

    def assert_hit(
        self,
        proc: subprocess.CompletedProcess,
        rel: str,
        line_no: int,
        *needles: str,
    ) -> str:
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 1, text)
        self.assertIn(rel, text)
        self.assertIn(f"{rel}:{line_no}:", text)
        for needle in needles:
            self.assertIn(needle, text)
        return text

    def plant_scratch_repo(
        self,
        files: dict[str, str],
        *,
        conf_overrides: dict[str, object] | None = None,
        exceptions: dict[str, object] | None = None,
    ) -> Path:
        n = getattr(self, "_tree_n", 0) + 1
        self._tree_n = n
        repo = self.scratch / f"tree-{n}"
        repo.mkdir()
        init = subprocess.run(
            ["git", "init", "-b", "work"],
            cwd=str(repo),
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": str(self.home),
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
            },
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(init.returncode, 0, init.stderr)
        conf = repo / "ops" / "lane.conf"
        text = conf_text(**(conf_overrides or {}))
        self._plant_bytes(conf, text.encode("utf-8"))
        landed = conf.read_text(encoding="utf-8")
        self.assertEqual(landed, text, f"conf plant did not land: {conf}")
        for rel, content in files.items():
            self._plant_bytes(repo / rel, content.encode("utf-8"))
        payload = exceptions if exceptions is not None else EMPTY_EXCEPTIONS
        self.plant_exceptions_payload(payload, repo=repo)
        return repo

    def clean_files(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        files = {
            "ops/conductor/tools/reads.py": reader_source(),
            "ops/bin/clean.sh": "echo ok\n",
            "ops/conductor/tools/clean.py": "print('ok')\n",
        }
        if extra:
            files.update(extra)
        return files


class ExceptionsFilePresence(_DefaultsFixture):
    """Slice 1 lands the exception table beside the reader."""

    def test_the_exceptions_file_is_present(self):
        self.assertTrue(
            EXCEPTIONS_LIVE.is_file(),
            f"RED: exceptions table is absent: {EXCEPTIONS_LIVE}",
        )


class CleanScratchTree(_DefaultsFixture):
    """`defaults` on a scratch tree that only calls laneconf.get exits 0."""

    def test_defaults_on_a_scratch_tree_with_only_get_reads_exits_0(self):
        repo = self.plant_scratch_repo(self.clean_files())
        proc = self.invoke(["defaults"], repo=repo)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_defaults_does_not_need_identity(self):
        repo = self.plant_scratch_repo(self.clean_files())
        env = self.env(lane_conf=repo / "ops" / "lane.conf")
        self.assertNotIn("WF_AGENT", env)
        proc = self.invoke(["defaults"], repo=repo)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_strict_on_a_clean_tree_exits_0(self):
        repo = self.plant_scratch_repo(self.clean_files())
        proc = self.invoke(["defaults", "--strict"], repo=repo)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual((proc.stderr or "").strip(), "")


class DefaultedReadHits(_DefaultsFixture):
    """Family 2: a defaulted conf/env read is a Finding naming file:line."""

    def test_environ_get_with_fallback_exits_1_naming_file_and_line(self):
        rel = "ops/bin/fallback_get.py"
        body = py_hit('os.environ.get("LANE_NAME", "agentscient")')
        repo = self.plant_scratch_repo(self.clean_files({rel: body}))
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertIn('os.environ.get("LANE_NAME", "agentscient")', landed)
        line_no = 3
        self.assertEqual(landed.splitlines()[line_no - 1], landed.splitlines()[2])
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_hit(
            proc, rel, line_no, "key=LANE_NAME", "fallback=", "agentscient",
        )

    def test_return_agentscient_exits_1(self):
        rel = "ops/conductor/tools/ident.py"
        body = py_hit('return "agentscient"')
        repo = self.plant_scratch_repo(self.clean_files({rel: body}))
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertIn('return "agentscient"', landed)
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_hit(proc, rel, 3, "agentscient")

    def test_shell_parameter_default_exits_1(self):
        rel = "ops/bin/fallback.sh"
        body = sh_hit('echo "${LANE_NAME:-agentscient}"')
        repo = self.plant_scratch_repo(self.clean_files({rel: body}))
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertIn("${LANE_NAME:-agentscient}", landed)
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_hit(
            proc, rel, 3, "key=LANE_NAME", "fallback=", "agentscient",
        )

    def test_environ_get_or_fallback_exits_1(self):
        rel = "ops/bin/or_fallback.py"
        body = py_hit('os.environ.get("LANE_NAME") or "agentscient"')
        repo = self.plant_scratch_repo(self.clean_files({rel: body}))
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertIn('os.environ.get("LANE_NAME") or "agentscient"', landed)
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_hit(
            proc, rel, 3, "key=LANE_NAME", "fallback=", "agentscient",
        )

    def test_conf_get_with_fallback_exits_1(self):
        rel = "ops/bin/conf_get.py"
        body = py_hit('conf.get("LANE_NAME", "agentscient")')
        repo = self.plant_scratch_repo(self.clean_files({rel: body}))
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertIn('conf.get("LANE_NAME", "agentscient")', landed)
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_hit(
            proc, rel, 3, "key=LANE_NAME", "fallback=", "agentscient",
        )

    def test_runtime_get_timeout_equal_to_wall_default_exits_1(self):
        rel = "ops/bin/wall.py"
        body = py_hit('runtime.get("timeout", 900)')
        repo = self.plant_scratch_repo(
            self.clean_files({rel: body}),
            conf_overrides={"WALL_DEFAULT": "900"},
        )
        conf = (repo / "ops" / "lane.conf").read_text(encoding="utf-8")
        self.assertIn("WALL_DEFAULT='900'", conf)
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertIn('runtime.get("timeout", 900)', landed)
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_hit(proc, rel, 3, "900")

    def test_generic_environ_get_with_fallback_exits_1(self):
        rel = "ops/bin/tmpdir.py"
        body = py_hit('os.environ.get("TMPDIR", "/tmp")')
        repo = self.plant_scratch_repo(self.clean_files({rel: body}))
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertIn('os.environ.get("TMPDIR", "/tmp")', landed)
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_hit(proc, rel, 3, "key=TMPDIR", "fallback=", "/tmp")


class HardcodedLaneValueHits(_DefaultsFixture):
    """Family 1: a hardcoded lane value is a Finding naming file:line."""

    def test_named_identity_tokens_exit_1(self):
        self.assertEqual(len(NAMED_TOKEN_PLANTS), 8, NAMED_TOKEN_PLANTS)
        for rel, stmt, token in NAMED_TOKEN_PLANTS:
            with self.subTest(rel=rel, token=token):
                body = py_hit(stmt)
                repo = self.plant_scratch_repo(self.clean_files({rel: body}))
                landed = (repo / rel).read_text(encoding="utf-8")
                self.assertIn(token, landed)
                self.assertGreaterEqual(len(landed.splitlines()), 3)
                line_no = 3
                self.assertIn(token, landed.splitlines()[line_no - 1])
                proc = self.invoke(["defaults"], repo=repo)
                self.assert_hit(proc, rel, line_no, token)

    def test_a_literal_equal_to_a_conf_value_exits_1(self):
        self.assertEqual(len(CONF_VALUE_KEYS), 9, CONF_VALUE_KEYS)
        for key in CONF_VALUE_KEYS:
            with self.subTest(key=key):
                value = SCRATCH_DEFAULTS[key]
                self.assertGreaterEqual(len(value), 1)
                rel = f"ops/bin/cfg_{key.lower()}.py"
                body = py_hit(f"marker = {value!r}")
                repo = self.plant_scratch_repo(self.clean_files({rel: body}))
                landed = (repo / rel).read_text(encoding="utf-8")
                self.assertIn(value, landed)
                proc = self.invoke(["defaults"], repo=repo)
                self.assert_hit(proc, rel, 3, value)

    def test_scope_cap_integer_literal_exits_1(self):
        rel = "ops/bin/scope.py"
        body = py_hit("cap = 1024")
        repo = self.plant_scratch_repo(
            self.clean_files({rel: body}),
            conf_overrides={"SCOPE_CAP": "1024"},
        )
        conf = (repo / "ops" / "lane.conf").read_text(encoding="utf-8")
        self.assertIn("SCOPE_CAP='1024'", conf)
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertIn("1024", landed.splitlines()[2])
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_hit(proc, rel, 3, "1024")


class PathsAndSkipSet(_DefaultsFixture):
    """`--paths` limits the scan; the four directory names stay skipped."""

    def test_paths_on_a_clean_file_next_to_a_dirty_file_exits_0(self):
        dirty = "ops/bin/dirty.py"
        clean = "ops/bin/clean_only.py"
        files = self.clean_files({
            dirty: py_hit('return "agentscient"'),
            clean: "print('ok')\n",
        })
        repo = self.plant_scratch_repo(files)
        planted = (repo / dirty).read_text(encoding="utf-8")
        self.assertIn('return "agentscient"', planted)
        self.assertNotIn(
            "agentscient",
            (repo / clean).read_text(encoding="utf-8"),
        )
        proc = self.invoke(["defaults", "--paths", clean], repo=repo)
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 0, text)
        self.assertNotIn(dirty, text)

    def test_paths_on_the_dirty_file_exits_1(self):
        dirty = "ops/bin/dirty.py"
        clean = "ops/bin/clean_only.py"
        files = self.clean_files({
            dirty: py_hit('return "agentscient"'),
            clean: "print('ok')\n",
        })
        repo = self.plant_scratch_repo(files)
        proc = self.invoke(["defaults", "--paths", dirty], repo=repo)
        self.assert_hit(proc, dirty, 3, "agentscient")

    def test_paths_with_no_hits_exits_0(self):
        rel = "ops/bin/clean_only.py"
        repo = self.plant_scratch_repo(
            self.clean_files({rel: "print('ok')\n"}),
        )
        proc = self.invoke(["defaults", "--paths", rel], repo=repo)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_paths_still_skips_tests_fixtures_archive_infra(self):
        self.assertEqual(len(SKIP_DIR_PLANTS), 4, SKIP_DIR_PLANTS)
        self.assertEqual(len(SKIP_DIRS), 4, SKIP_DIRS)
        files = self.clean_files({
            rel: py_hit('return "agentscient"') for rel in SKIP_DIR_PLANTS
        })
        repo = self.plant_scratch_repo(files)
        for rel in SKIP_DIR_PLANTS:
            landed = (repo / rel).read_text(encoding="utf-8")
            self.assertIn('return "agentscient"', landed)
        proc = self.invoke(
            ["defaults", "--paths", *SKIP_DIR_PLANTS], repo=repo,
        )
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 0, text)
        for rel in SKIP_DIR_PLANTS:
            self.assertNotIn(f"{rel}:", text)

    def test_whole_scan_skips_tests_fixtures_archive_infra(self):
        files = self.clean_files({
            rel: py_hit('return "agentscient"') for rel in SKIP_DIR_PLANTS
        })
        repo = self.plant_scratch_repo(files)
        proc = self.invoke(["defaults"], repo=repo)
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 0, text)
        for rel in SKIP_DIR_PLANTS:
            self.assertNotIn(f"{rel}:", text)

    def test_claude_tree_is_scanned(self):
        rel = ".claude/bin/hook.py"
        repo = self.plant_scratch_repo(
            self.clean_files({rel: py_hit('return "agentscient"')}),
        )
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertIn('return "agentscient"', landed)
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_hit(proc, rel, 3, "agentscient")

    def test_non_py_sh_suffix_is_not_scanned(self):
        rel = "ops/bin/note.md"
        repo = self.plant_scratch_repo(
            self.clean_files({rel: 'return "agentscient"\n'}),
        )
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertIn('return "agentscient"', landed)
        proc = self.invoke(["defaults"], repo=repo)
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 0, text)
        self.assertNotIn(rel, text)

    def test_a_hit_under_hand_py_is_still_a_hit(self):
        rel = "ops/conductor/tools/hand.py"
        repo = self.plant_scratch_repo(
            self.clean_files({rel: py_hit('return "agentscient"')}),
        )
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertIn('return "agentscient"', landed)
        proc = self.invoke(["defaults", "--paths", rel], repo=repo)
        self.assert_hit(proc, rel, 3, "agentscient")


class StrictRejection(_DefaultsFixture):
    """`--strict` is Rejection: exit 2, one stderr line, empty stdout."""

    def test_strict_on_a_defaulted_read_exits_2_stdout_empty(self):
        rel = "ops/bin/fallback_get.py"
        body = py_hit('os.environ.get("LANE_NAME", "agentscient")')
        repo = self.plant_scratch_repo(self.clean_files({rel: body}))
        proc = self.invoke(["defaults", "--strict"], repo=repo)
        line = self.assert_wire_refusal(
            proc, class_name="defaults", named=(rel,),
        )
        self.assertIn("expected no hardcoded lane value", line.lower())
        self.assertIn("no defaulted conf/env read", line.lower())

    def test_strict_names_path_line_and_the_remedy(self):
        rel = "ops/bin/fallback_get.py"
        body = py_hit('os.environ.get("LANE_NAME", "agentscient")')
        repo = self.plant_scratch_repo(self.clean_files({rel: body}))
        proc = self.invoke(
            ["defaults", "--strict", "--paths", rel], repo=repo,
        )
        line = self.assert_wire_refusal(
            proc, class_name="defaults", named=(rel, f"{rel}:3"),
        )
        lower = line.lower()
        self.assertIn("laneconf.get", lower)
        self.assertIn("exception table", lower)


class ExceptionTable(_DefaultsFixture):
    """A matching exception row is quiet; a broken table is a refusal."""

    def test_exception_row_quiets_a_matching_locate(self):
        payload = {"exceptions": [exception_row()]}
        repo = self.plant_scratch_repo(
            self.clean_files({LOCATE_REL: LOCATE_BODY}),
            exceptions=payload,
        )
        landed = (repo / LOCATE_REL).read_text(encoding="utf-8")
        self.assertIn(LOCATE_LINE, landed)
        table = json.loads(
            (repo / EXCEPTIONS_REL).read_text(encoding="utf-8"),
        )
        self.assertEqual(len(table["exceptions"]), 1)
        self.assertEqual(table["exceptions"][0]["line_match"], LOCATE_LINE)
        proc = self.invoke(["defaults"], repo=repo)
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 0, text)
        self.assertNotIn(f"{LOCATE_REL}:", text)

    def test_exception_row_with_an_extra_key_refuses_syntax(self):
        row = exception_row(extra="nope")
        payload = {"exceptions": [row]}
        repo = self.plant_scratch_repo(
            self.clean_files({LOCATE_REL: LOCATE_BODY}),
            exceptions=payload,
        )
        raw = (repo / EXCEPTIONS_REL).read_text(encoding="utf-8")
        self.assertIn('"extra"', raw)
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_wire_refusal(
            proc, class_name="syntax", named=("extra",),
        )

    def test_exception_row_whose_line_match_is_absent_refuses(self):
        stale = "NOT_A_SUBSTRING_OF_THE_FILE_aa41"
        row = exception_row(line_match=stale)
        payload = {"exceptions": [row]}
        repo = self.plant_scratch_repo(
            self.clean_files({LOCATE_REL: LOCATE_BODY}),
            exceptions=payload,
        )
        landed = (repo / LOCATE_REL).read_text(encoding="utf-8")
        self.assertNotIn(stale, landed)
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_wire_refusal(proc, named=(stale, LOCATE_REL))

    def test_duplicate_path_line_match_refuses(self):
        payload = {"exceptions": [exception_row(), exception_row()]}
        repo = self.plant_scratch_repo(
            self.clean_files({LOCATE_REL: LOCATE_BODY}),
            exceptions=payload,
        )
        table = json.loads(
            (repo / EXCEPTIONS_REL).read_text(encoding="utf-8"),
        )
        self.assertEqual(len(table["exceptions"]), 2)
        self.assertEqual(
            table["exceptions"][0]["path"],
            table["exceptions"][1]["path"],
        )
        self.assertEqual(
            table["exceptions"][0]["line_match"],
            table["exceptions"][1]["line_match"],
        )
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_wire_refusal(proc, named=(LOCATE_REL,))

    def test_identity_key_with_optional_tune_kind_refuses(self):
        rel = "ops/bin/ident.py"
        body = py_hit('return "agentscient"')
        row = exception_row(
            id="identity-not-tune",
            kind="optional-tune",
            key="LANE_NAME",
            fallback="agentscient",
            path=rel,
            line_match='return "agentscient"',
            why="must not quiet an identity fallback as optional tune",
        )
        repo = self.plant_scratch_repo(
            self.clean_files({rel: body}),
            exceptions={"exceptions": [row]},
        )
        proc = self.invoke(["defaults"], repo=repo)
        self.assert_wire_refusal(proc, named=("LANE_NAME",))


class LiveTreeFindings(_DefaultsFixture):
    """The live tree still carries identity fallbacks; they are hits."""

    def test_live_tree_without_strict_names_hand_py(self):
        self.assertEqual(len(LIVE_IDENTITY_FILES), 4, LIVE_IDENTITY_FILES)
        proc = self.invoke_live(["defaults"])
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 1, text)
        for rel in LIVE_IDENTITY_FILES:
            with self.subTest(rel=rel):
                self.assertIn(rel, text)

    def test_seed_quiets_the_live_lane_conf_locate(self):
        rel = "ops/conductor/tools/laneconf.py"
        proc = self.invoke_live(["defaults", "--paths", rel])
        text = self.combined(proc)
        self.assertFalse(
            (proc.stderr or "").lower().lstrip().startswith("arguments:"),
            proc.stderr,
        )
        self.assertNotIn(LOCATE_LINE, text)


if __name__ == "__main__":
    unittest.main()
