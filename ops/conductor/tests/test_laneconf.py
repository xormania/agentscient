"""Lane-conf acceptance tests, written from the unit 1 contract.

Contracts (only): the unit 1 contract in the dispatch input
(`contract-laneconf.md` §2) and the inherited
`ops/conductor/instrument-conventions.md`. The instrument
`ops/conductor/tools/laneconf.py` and the tracked `ops/lane.conf` are
the subject and are not read here. Tests plant a scratch conf through
`LANE_CONF` and never write the tracked file.

The implementation lands in a later run. A missing tool file is one
red (`test_the_tool_file_is_present`); a missing tracked conf is one
red (`test_the_tracked_conf_is_present`). Every other case invokes the
real tool path so the contracted assertion is the red, not a skip.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "laneconf.py"
TRACKED_CONF = REPO / "ops" / "lane.conf"
RUN_CAP = 60

# PIN_CONF_OVERRIDE: tests point at a scratch conf through LANE_CONF.
# The tracked file is never written.
CONF_ENV = "LANE_CONF"
LOCAL_NAME = "lane.local.conf"

# PIN_GET_STDOUT: `get KEY` prints the value and a single trailing
# newline on stdout; stderr is empty on success.
# PIN_SCAN_ROOT: `closure` and `literals` scan the git toplevel of the
# file named by LANE_CONF (else the repository that holds the tracked
# conf). Tests plant a scratch git repo with ops/lane.conf.
# PIN_UNDECLARED_READ: a `get("KEY")` call in lane code outside tests/
# is a read. The finding names the key and the file.
# PIN_EXEMPTION: `ops/devlane/dispatch/record.py` may carry the lane
# kind `lane = "dev"`; a second `"dev"` in that file is a hit.
# PIN_INFRA_SKIP: `ops/devlane/infra/` is skipped and the skip is
# printed, naming that path.

REQUIRED_KEYS = (
    "LANE_NAME",
    "TRUNK_BRANCH",
    "RELEASE_BRANCH",
    "REPO_SLUG",
    "CHECK_NAME",
    "WF_AGENT_DEFAULT",
    "LANE_AUTHOR",
    "MODEL_GROK",
    "MODEL_CODEX",
    "MODEL_CLAUDE_READ",
    "MODEL_CLAUDE_PLAN",
    "EFFORT_GROK",
    "EFFORT_CODEX",
    "EFFORT_CLAUDE",
    "WALL_DEFAULT",
    "SCOPE_CAP",
)

NAME_KEYS = (
    "LANE_NAME",
    "TRUNK_BRANCH",
    "RELEASE_BRANCH",
    "REPO_SLUG",
    "CHECK_NAME",
)

REQUIRED_DEFAULTS = {
    "LANE_NAME": "lanetest",
    "TRUNK_BRANCH": "trunktest",
    "RELEASE_BRANCH": "reltest",
    "REPO_SLUG": "org/proj",
    "CHECK_NAME": "ci",
    "WF_AGENT_DEFAULT": "Conf Agent <conf@example.invalid>",
    "LANE_AUTHOR": "Lane Owner <lane-owner@example.invalid>",
    "MODEL_GROK": "model-grok",
    "MODEL_CODEX": "model-codex",
    "MODEL_CLAUDE_READ": "model-claude-read",
    "MODEL_CLAUDE_PLAN": "model-claude-plan",
    "EFFORT_GROK": "high",
    "EFFORT_CODEX": "high",
    "EFFORT_CLAUDE": "high",
    "WALL_DEFAULT": "900",
    "SCOPE_CAP": "1024",
}

DECL_RE = re.compile(r"^([A-Z][A-Z0-9_]*)='([^']*)'\s*$")


def conf_text(**overrides: object) -> str:
    omit = tuple(overrides.pop("omit", ()) or ())
    keys = dict(REQUIRED_DEFAULTS)
    for name, value in overrides.items():
        keys[name] = str(value)
    for name in omit:
        keys.pop(name, None)
    lines = ["# scratch lane conf\n"]
    for name, value in keys.items():
        lines.append(f"{name}='{value}'\n")
    return "".join(lines)


def declared_keys(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = DECL_RE.match(line)
        if match:
            found[match.group(1)] = match.group(2)
    return found


def reader_source(keys: tuple[str, ...] = REQUIRED_KEYS) -> str:
    return "".join(f'get("{name}")\n' for name in keys)


class _LaneconfFixture(unittest.TestCase):
    """Scratch HOME, scratch conf via LANE_CONF, isolated from the tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="laneconf-")
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.scratch = root / "scratch"
        self.xdg = root / "xdg"
        for path in (self.home, self.scratch, self.xdg):
            path.mkdir()
        self.conf_path = self.scratch / "lane.conf"
        self._plant_bytes(self.conf_path, conf_text().encode("utf-8"))
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

    def plant_conf(self, path: Path | None = None, **overrides: object) -> Path:
        path = path or self.conf_path
        text = conf_text(**overrides)
        self._plant_bytes(path, text.encode("utf-8"))
        landed = path.read_text(encoding="utf-8")
        self.assertEqual(landed, text, f"conf plant did not land: {path}")
        return path

    def plant_local(self, text: str, *, beside: Path | None = None) -> Path:
        parent = (beside or self.conf_path).parent
        path = parent / LOCAL_NAME
        self._plant_bytes(path, text.encode("utf-8"))
        self.assertEqual(path.read_text(encoding="utf-8"), text)
        return path

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
            env[CONF_ENV] = str(self.conf_path)
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
        extra: dict[str, str | None] | None = None,
        lane_conf: Path | str | None = "default",
        cwd: Path | None = None,
        timeout: float = RUN_CAP,
    ):
        env = self.env(extra, lane_conf=lane_conf)
        cmd = [sys.executable, str(TOOL), *argv]
        try:
            return subprocess.run(
                cmd,
                cwd=str(cwd or self.home),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(
                f"laneconf exceeded {timeout}s; stdout={exc.stdout!r} "
                f"stderr={exc.stderr!r}"
            )

    def combined(self, proc: subprocess.CompletedProcess) -> str:
        return f"{proc.stdout or ''}{proc.stderr or ''}"

    def assert_refusal(
        self,
        proc: subprocess.CompletedProcess,
        class_name: str,
        *,
        named: tuple[str, ...] = (),
    ) -> str:
        err = proc.stderr or ""
        self.assertEqual(proc.returncode, 2, err or proc.stdout)
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        lower = lines[0].lower()
        token = class_name.lower().replace("_", "-")
        self.assertIn(token, lower, lines[0])
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, lines[0])
        self.assertLess(lower.index("expected"), lower.index("found"), lines[0])
        self.assertLess(lower.index("found"), lower.index("needed"), lines[0])
        self.assertEqual(
            (proc.stdout or "").strip(),
            "",
            "refusal text belongs on stderr, not stdout",
        )
        for item in named:
            self.assertIn(item, lines[0], lines[0])
        return lines[0]

    def assert_get(self, proc: subprocess.CompletedProcess, value: str) -> None:
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual((proc.stderr or "").strip(), "")
        self.assertEqual((proc.stdout or "").splitlines(), [value])

    def plant_scratch_repo(
        self,
        files: dict[str, str],
        *,
        conf_overrides: dict[str, object] | None = None,
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
        self.plant_conf(conf, **(conf_overrides or {}))
        for rel, content in files.items():
            self._plant_bytes(
                repo / rel, content.encode("utf-8"),
            )
        return repo


class ToolAndTrackedConfPresence(_LaneconfFixture):
    """Missing tool and missing tracked conf each count once."""

    def test_the_tool_file_is_present(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")

    def test_the_tracked_conf_is_present(self):
        self.assertTrue(
            TRACKED_CONF.is_file(),
            f"RED: tracked conf is absent: {TRACKED_CONF}",
        )


class GetVerb(_LaneconfFixture):
    """`get KEY` prints the value and exits 0; a missing key refuses
    class `key` naming the key and the file."""

    def test_get_prints_the_value_and_exits_0(self):
        value = "planted-lane"
        self.plant_conf(LANE_NAME=value)
        proc = self.invoke(["get", "LANE_NAME"])
        self.assert_get(proc, value)

    def test_get_prints_lane_author(self):
        value = "Owner Name <owner@example.invalid>"
        self.assertNotEqual(value, REQUIRED_DEFAULTS["LANE_AUTHOR"])
        self.plant_conf(LANE_AUTHOR=value)
        proc = self.invoke(["get", "LANE_AUTHOR"])
        self.assert_get(proc, value)

    def test_get_does_not_need_identity(self):
        proc = self.invoke(["get", "LANE_NAME"])
        env = self.env()
        self.assertNotIn("WF_AGENT", env)
        self.assert_get(proc, REQUIRED_DEFAULTS["LANE_NAME"])

    def test_a_missing_key_refuses_class_key_naming_the_key_and_file(self):
        missing = "NO_SUCH_KEY"
        self.assertNotIn(missing, declared_keys(
            self.conf_path.read_text(encoding="utf-8"),
        ))
        proc = self.invoke(["get", missing])
        self.assert_refusal(
            proc, "key", named=(missing, str(self.conf_path)),
        )

    def test_absent_local_file_is_not_a_refusal(self):
        local = self.conf_path.parent / LOCAL_NAME
        self.assertFalse(local.exists(), "plant: local file must be absent")
        proc = self.invoke(["get", "LANE_NAME"])
        self.assert_get(proc, REQUIRED_DEFAULTS["LANE_NAME"])


class EnvironmentBeatsConf(_LaneconfFixture):
    """`KEY=env` in the invoking environment wins over the file."""

    def test_environment_beats_conf_for_the_same_key(self):
        self.plant_conf(LANE_NAME="from-conf")
        self.assertNotEqual("from-env", "from-conf")
        proc = self.invoke(
            ["get", "LANE_NAME"],
            extra={"LANE_NAME": "from-env"},
        )
        self.assert_get(proc, "from-env")
        self.assertNotEqual(
            (proc.stdout or "").strip(), "from-conf",
        )


class LocalFile(_LaneconfFixture):
    """The local file beside the conf is sourced after it and wins for
    an allowed key; a name key in the local file refuses `local-key`."""

    def test_local_file_wins_for_an_allowed_key(self):
        self.plant_conf(MODEL_GROK="from-conf")
        local = self.plant_local("MODEL_GROK='from-local'\n")
        self.assertTrue(local.is_file())
        self.assertEqual(local.name, LOCAL_NAME)
        proc = self.invoke(["get", "MODEL_GROK"])
        self.assert_get(proc, "from-local")
        self.assertNotEqual((proc.stdout or "").strip(), "from-conf")

    def test_local_file_setting_a_name_key_refuses_local_key(self):
        for key in NAME_KEYS:
            with self.subTest(key=key):
                self.plant_conf()
                local = self.plant_local(f"{key}='from-local'\n")
                proc = self.invoke(["get", "MODEL_GROK"])
                self.assert_refusal(
                    proc, "local-key", named=(key, str(local)),
                )


class ThreeLayerPrecedence(_LaneconfFixture):
    """Environment beats the local file, which beats the tracked conf."""

    def test_environment_beats_local_file_beats_conf(self):
        self.plant_conf(MODEL_GROK="from-conf")
        local = self.plant_local("MODEL_GROK='from-local'\n")
        self.assertTrue(local.is_file())
        self.assertNotEqual("from-env", "from-local")
        self.assertNotEqual("from-env", "from-conf")
        self.assertNotEqual("from-local", "from-conf")
        proc = self.invoke(
            ["get", "MODEL_GROK"],
            extra={"MODEL_GROK": "from-env"},
        )
        self.assert_get(proc, "from-env")
        self.assertNotEqual((proc.stdout or "").strip(), "from-local")
        self.assertNotEqual((proc.stdout or "").strip(), "from-conf")


class SyntaxRefusal(_LaneconfFixture):
    """A line that is not KEY='literal' or a comment refuses class
    `syntax` naming the line number. Double-quoted, unquoted, export,
    and command-substitution forms are syntax, and must not execute."""

    def test_a_non_key_line_refuses_syntax_naming_the_line_number(self):
        text = (
            "# header\n"
            "LANE_NAME='ok'\n"
            "this is not a key line\n"
        )
        self._plant_bytes(self.conf_path, text.encode("utf-8"))
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertEqual(landed.splitlines()[2], "this is not a key line")
        proc = self.invoke(["get", "LANE_NAME"])
        line = self.assert_refusal(proc, "syntax")
        self.assertIn("3", line)

    def test_double_quoted_assignment_refuses_syntax(self):
        text = "# header\nMODEL_GROK=\"double-quoted\"\n"
        self._plant_bytes(self.conf_path, text.encode("utf-8"))
        self.assertIn('MODEL_GROK="double-quoted"', self.conf_path.read_text())
        proc = self.invoke(["get", "MODEL_GROK"])
        line = self.assert_refusal(proc, "syntax")
        self.assertIn("2", line)

    def test_unquoted_assignment_refuses_syntax(self):
        text = "# header\nMODEL_GROK=unquoted\n"
        self._plant_bytes(self.conf_path, text.encode("utf-8"))
        self.assertIn("MODEL_GROK=unquoted", self.conf_path.read_text())
        proc = self.invoke(["get", "MODEL_GROK"])
        line = self.assert_refusal(proc, "syntax")
        self.assertIn("2", line)

    def test_export_assignment_refuses_syntax(self):
        text = "# header\nexport MODEL_GROK='from-export'\n"
        self._plant_bytes(self.conf_path, text.encode("utf-8"))
        self.assertIn("export MODEL_GROK=", self.conf_path.read_text())
        proc = self.invoke(["get", "MODEL_GROK"])
        line = self.assert_refusal(proc, "syntax")
        self.assertIn("2", line)

    def test_command_substitution_does_not_run_and_refuses_syntax(self):
        witness = self.scratch / "pwned-syntax"
        self.assertFalse(witness.exists(), "plant: witness must start absent")
        text = (
            "# header\n"
            f'MODEL_GROK="$(printf PWNED > {witness})"\n'
        )
        self._plant_bytes(self.conf_path, text.encode("utf-8"))
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertIn("$(printf PWNED", landed)
        proc = self.invoke(["get", "MODEL_GROK"])
        self.assert_refusal(proc, "syntax")
        self.assertFalse(
            witness.exists(),
            "command substitution must not execute; "
            f"witness="
            f"{witness.read_text(encoding='utf-8') if witness.exists() else ''!r}",
        )

    def test_get_does_not_need_bash_on_path(self):
        nobash = self.scratch / "nobash-bin"
        nobash.mkdir()
        path = str(nobash)
        self.assertIsNone(shutil.which("bash", path=path))
        self.assertIsNone(shutil.which("sh", path=path))
        proc = self.invoke(["get", "LANE_NAME"], extra={"PATH": path})
        self.assert_get(proc, REQUIRED_DEFAULTS["LANE_NAME"])


class BashPythonParity(_LaneconfFixture):
    """For the tracked ops/lane.conf, bash source and `get KEY` agree
    for every declared key. Count is asserted first."""

    def test_bash_source_and_get_agree_for_every_declared_key(self):
        self.assertTrue(
            TRACKED_CONF.is_file(),
            f"RED: tracked conf is absent: {TRACKED_CONF}",
        )
        text = TRACKED_CONF.read_text(encoding="utf-8")
        keys = declared_keys(text)
        self.assertGreater(len(keys), 0, "tracked conf declares no keys")
        self.assertGreaterEqual(len(keys), len(REQUIRED_KEYS), keys)
        for name, value in keys.items():
            with self.subTest(key=name):
                bash = subprocess.run(
                    [
                        "bash", "-c",
                        "source "
                        + shlex.quote(str(TRACKED_CONF))
                        + f'; printf %s "${{{name}}}"',
                    ],
                    cwd=str(self.home),
                    env=self.env(lane_conf=None),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=RUN_CAP,
                )
                self.assertEqual(bash.returncode, 0, bash.stderr)
                self.assertEqual(bash.stdout, value, name)
                proc = self.invoke(
                    ["get", name], lane_conf=TRACKED_CONF,
                )
                self.assert_get(proc, value)
                self.assertEqual((proc.stdout or "").strip(), bash.stdout)


class TrackedConfRequiredKeys(_LaneconfFixture):
    """The tracked ops/lane.conf declares every required key of unit 1
    and no DEFAULT_TIMEOUT."""

    def test_tracked_conf_declares_every_required_key_and_no_default_timeout(
            self):
        self.assertTrue(
            TRACKED_CONF.is_file(),
            f"RED: tracked conf is absent: {TRACKED_CONF}",
        )
        text = TRACKED_CONF.read_text(encoding="utf-8")
        keys = declared_keys(text)
        self.assertGreater(len(keys), 0, "tracked conf declares no keys")
        for name in REQUIRED_KEYS:
            with self.subTest(key=name):
                self.assertIn(name, keys)
        self.assertNotIn("DEFAULT_TIMEOUT", keys)
        for line in text.splitlines():
            if DECL_RE.match(line):
                self.assertFalse(
                    line.startswith("DEFAULT_TIMEOUT="),
                    line,
                )


class ClosureVerb(_LaneconfFixture):
    """`closure` exits 0 on the tree; unread and undeclared keys and a
    CHECK_NAME mismatch each exit 1 naming what they found."""

    def test_closure_exits_0_on_the_tree(self):
        proc = self.invoke(["closure"], lane_conf=None, cwd=REPO)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_a_declared_key_no_code_reads_exits_1_naming_it(self):
        orphan = "ORPHAN_KEY"
        repo = self.plant_scratch_repo(
            {"ops/conductor/tools/reads.py": reader_source()},
            conf_overrides={orphan: "orphan-value"},
        )
        conf = repo / "ops" / "lane.conf"
        planted = declared_keys(conf.read_text(encoding="utf-8"))
        self.assertIn(orphan, planted)
        reader = (repo / "ops/conductor/tools/reads.py").read_text(
            encoding="utf-8",
        )
        self.assertNotIn(orphan, reader)
        proc = self.invoke(["closure"], lane_conf=conf, cwd=repo)
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 1, text)
        self.assertIn(orphan, text)

    def test_code_reading_an_undeclared_key_exits_1_naming_key_and_file(self):
        ghost = "GHOST_KEY"
        rel = "ops/bin/ghost.py"
        repo = self.plant_scratch_repo(
            {
                "ops/conductor/tools/reads.py": reader_source(),
                rel: f'get("{ghost}")\n',
            },
        )
        conf = repo / "ops" / "lane.conf"
        planted = declared_keys(conf.read_text(encoding="utf-8"))
        self.assertNotIn(ghost, planted)
        ghost_file = repo / rel
        self.assertIn(ghost, ghost_file.read_text(encoding="utf-8"))
        proc = self.invoke(["closure"], lane_conf=conf, cwd=repo)
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 1, text)
        self.assertIn(ghost, text)
        self.assertIn(rel, text)

    def test_undeclared_shell_and_env_reads_name_each_key_and_file(self):
        ghost_shell = "GHOST_SHELL"
        ghost_env = "GHOST_ENV"
        ghost_get = "GHOST_GET"
        rel_shell = "ops/bin/ghost.sh"
        rel_env = "ops/bin/ghost_env.py"
        rel_get = "ops/bin/ghost_get.py"
        rel_clean_sh = "ops/bin/clean.sh"
        rel_clean_py = "ops/bin/clean.py"
        repo = self.plant_scratch_repo(
            {
                "ops/conductor/tools/reads.py": reader_source(),
                rel_clean_sh: "echo ok\n",
                rel_clean_py: "print('ok')\n",
                rel_shell: 'echo "${' + ghost_shell + '}"\n',
                rel_env: (
                    "import os\n"
                    f"os.environ[{ghost_env!r}]\n"
                ),
                rel_get: (
                    "import os\n"
                    f"os.environ.get({ghost_get!r})\n"
                ),
            },
        )
        conf = repo / "ops" / "lane.conf"
        planted = declared_keys(conf.read_text(encoding="utf-8"))
        for ghost in (ghost_shell, ghost_env, ghost_get):
            self.assertNotIn(ghost, planted)
        self.assertIn(
            ghost_shell,
            (repo / rel_shell).read_text(encoding="utf-8"),
        )
        self.assertIn(
            ghost_env,
            (repo / rel_env).read_text(encoding="utf-8"),
        )
        self.assertIn(
            ghost_get,
            (repo / rel_get).read_text(encoding="utf-8"),
        )
        proc = self.invoke(["closure"], lane_conf=conf, cwd=repo)
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 1, text)
        self.assertIn(ghost_shell, text)
        self.assertIn(rel_shell, text)
        self.assertIn(ghost_env, text)
        self.assertIn(rel_env, text)
        self.assertIn(ghost_get, text)
        self.assertIn(rel_get, text)

    def test_check_name_not_equal_to_the_workflow_name_exits_1_naming_both(
            self):
        workflow_name = "other-check"
        check_name = "ci"
        self.assertNotEqual(workflow_name, check_name)
        repo = self.plant_scratch_repo(
            {
                "ops/conductor/tools/reads.py": reader_source(),
                ".github/workflows/ci.yml": f"name: {workflow_name}\n",
            },
            conf_overrides={"CHECK_NAME": check_name},
        )
        conf = repo / "ops" / "lane.conf"
        keys = declared_keys(conf.read_text(encoding="utf-8"))
        self.assertEqual(keys["CHECK_NAME"], check_name)
        yml = (repo / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn(workflow_name, yml)
        proc = self.invoke(["closure"], lane_conf=conf, cwd=repo)
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 1, text)
        self.assertIn(check_name, text)
        self.assertIn(workflow_name, text)


class LiteralsVerb(_LaneconfFixture):
    """`literals` exits 0 on the tree; a scratch lane file carrying a
    forbidden token exits 1 naming file and line. The record.py lane
    kind is exempt; a second `"dev"` in that file is not. Infra is
    skipped and the skip is printed."""

    def test_literals_exits_0_on_the_tree(self):
        proc = self.invoke(["literals"], lane_conf=None, cwd=REPO)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_a_benign_scratch_tree_exits_0(self):
        repo = self.plant_scratch_repo(
            {
                "ops/conductor/tools/reads.py": reader_source(),
                "ops/bin/clean.sh": "echo ok\n",
                "ops/conductor/tools/clean.py": "print('ok')\n",
            },
        )
        conf = repo / "ops" / "lane.conf"
        proc = self.invoke(["literals"], lane_conf=conf, cwd=repo)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_a_scratch_lane_file_carrying_a_forbidden_token_exits_1(self):
        configured = {
            "LANE_NAME": "lanex",
            "TRUNK_BRANCH": "trunkx",
            "RELEASE_BRANCH": "relx",
            "REPO_SLUG": "org/projx",
            "CHECK_NAME": "checkx",
        }
        plants = (
            ("ops/bin/legacy-dev.sh", '"dev"'),
            ("ops/conductor/tools/legacy_dev.py", '"dev"'),
            ("ops/bin/legacy-origin.sh", "origin/dev"),
            ("ops/conductor/tools/legacy_origin.py", "origin/dev"),
            ("ops/bin/legacy-lane.sh", "'agentscient'"),
            ("ops/conductor/tools/legacy_lane.py", "'agentscient'"),
            ("ops/bin/legacy-slug.sh", "uscient/agentscient"),
            ("ops/conductor/tools/legacy_slug.py", "uscient/agentscient"),
            ("ops/bin/legacy-home.sh", "/home/work/"),
            ("ops/conductor/tools/legacy_home.py", "/home/work/"),
            ("ops/bin/cfg-lane.sh", configured["LANE_NAME"]),
            ("ops/conductor/tools/cfg_lane.py", configured["LANE_NAME"]),
            ("ops/bin/cfg-trunk.sh", configured["TRUNK_BRANCH"]),
            ("ops/conductor/tools/cfg_trunk.py", configured["TRUNK_BRANCH"]),
            ("ops/bin/cfg-rel.sh", configured["RELEASE_BRANCH"]),
            ("ops/conductor/tools/cfg_rel.py", configured["RELEASE_BRANCH"]),
            ("ops/bin/cfg-slug.sh", configured["REPO_SLUG"]),
            ("ops/conductor/tools/cfg_slug.py", configured["REPO_SLUG"]),
            ("ops/bin/cfg-check.sh", configured["CHECK_NAME"]),
            ("ops/conductor/tools/cfg_check.py", configured["CHECK_NAME"]),
        )
        self.assertEqual(len(plants), 20, plants)
        for rel, token in plants:
            with self.subTest(rel=rel, token=token):
                if rel.endswith(".py"):
                    body = (
                        "print('ok')\n"
                        "print('still-ok')\n"
                        f"marker = {token!r}\n"
                    )
                else:
                    body = (
                        "echo ok\n"
                        "echo still-ok\n"
                        f"echo {token}\n"
                    )
                repo = self.plant_scratch_repo(
                    {
                        "ops/conductor/tools/reads.py": reader_source(),
                        rel: body,
                    },
                    conf_overrides=configured,
                )
                conf = repo / "ops" / "lane.conf"
                spread = repo / rel
                landed = spread.read_text(encoding="utf-8")
                self.assertIn(token, landed)
                self.assertGreaterEqual(len(landed.splitlines()), 3)
                line_no = 3
                self.assertIn(token, landed.splitlines()[line_no - 1])
                proc = self.invoke(["literals"], lane_conf=conf, cwd=repo)
                text = self.combined(proc)
                self.assertEqual(proc.returncode, 1, text)
                self.assertIn(rel, text)
                self.assertIn(str(line_no), text)
                self.assertIn(token, text)

    def test_record_py_lane_kind_is_exempt_and_a_second_dev_fails(self):
        rel = "ops/devlane/dispatch/record.py"
        repo = self.plant_scratch_repo(
            {
                "ops/conductor/tools/reads.py": reader_source(),
                rel: 'lane = "dev"\n',
            },
        )
        conf = repo / "ops" / "lane.conf"
        planted = (repo / rel).read_text(encoding="utf-8")
        self.assertEqual(planted.count('"dev"'), 1)
        proc = self.invoke(["literals"], lane_conf=conf, cwd=repo)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

        second = 'lane = "dev"\nother = "dev"\n'
        self._plant_bytes((repo / rel), second.encode("utf-8"))
        landed = (repo / rel).read_text(encoding="utf-8")
        self.assertEqual(landed.count('"dev"'), 2)
        proc = self.invoke(["literals"], lane_conf=conf, cwd=repo)
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 1, text)
        self.assertIn(rel, text)

    def test_infra_is_skipped_and_the_skip_is_printed(self):
        rel = "ops/devlane/infra/gitea/bootstrap.sh"
        repo = self.plant_scratch_repo(
            {
                "ops/conductor/tools/reads.py": reader_source(),
                rel: "user=agentscient\n",
            },
        )
        conf = repo / "ops" / "lane.conf"
        planted = (repo / rel).read_text(encoding="utf-8")
        self.assertIn("agentscient", planted)
        proc = self.invoke(["literals"], lane_conf=conf, cwd=repo)
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 0, text)
        self.assertIn("ops/devlane/infra", text)


class GetWithoutLaneConfUsesTrackedFile(_LaneconfFixture):
    """Readers locate the tracked conf relative to the tool, never cwd."""

    def test_get_without_lane_conf_reads_the_tracked_file_from_any_cwd(self):
        self.assertTrue(
            TRACKED_CONF.is_file(),
            f"RED: tracked conf is absent: {TRACKED_CONF}",
        )
        keys = declared_keys(TRACKED_CONF.read_text(encoding="utf-8"))
        self.assertIn("LANE_NAME", keys)
        proc = self.invoke(
            ["get", "LANE_NAME"],
            lane_conf=None,
            cwd=self.home,
        )
        self.assert_get(proc, keys["LANE_NAME"])


class TrackedConfMove(_LaneconfFixture):
    """dispatch.conf moved to ops/lane.conf; the local file is gitignored."""

    def test_lane_conf_is_tracked_and_dispatch_conf_is_not(self):
        listed_new = subprocess.run(
            ["git", "ls-files", "--", "ops/lane.conf"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        listed_old = subprocess.run(
            ["git", "ls-files", "--", "ops/conductor/tools/dispatch.conf"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(listed_new.returncode, 0, listed_new.stderr)
        self.assertEqual(listed_old.returncode, 0, listed_old.stderr)
        self.assertEqual(listed_new.stdout.strip(), "ops/lane.conf")
        self.assertEqual(
            listed_old.stdout.strip(),
            "",
            "dispatch.conf must be moved, not copied: "
            f"ls-files={listed_old.stdout!r}",
        )

    def test_lane_local_conf_is_gitignored(self):
        proc = subprocess.run(
            ["git", "check-ignore", "-v", "--", "ops/lane.local.conf"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            proc.returncode, 0,
            proc.stderr or proc.stdout or "check-ignore did not match",
        )
        self.assertIn("lane.local.conf", proc.stdout)


class Unit2DriverKeys(_LaneconfFixture):
    """Unit 2 required keys: the tracked conf declares them and closure
    finds the ladder driver as their reader.
    """

    DRIVER_KEYS = (
        "WORKTREE_ROOT",
        "ADDRESS_GROK",
        "ADDRESS_CODEX",
        "ADDRESS_CLAUDE",
    )
    DRIVER = REPO / "ops" / "conductor" / "tools" / "ladder.py"

    def test_tracked_conf_declares_the_driver_keys(self):
        self.assertTrue(
            TRACKED_CONF.is_file(),
            f"RED: tracked conf is absent: {TRACKED_CONF}",
        )
        keys = declared_keys(TRACKED_CONF.read_text(encoding="utf-8"))
        self.assertGreater(len(keys), 0, "tracked conf declares no keys")
        for name in self.DRIVER_KEYS:
            with self.subTest(key=name):
                self.assertIn(name, keys)

    def test_closure_finds_the_driver_as_their_reader(self):
        self.assertTrue(
            TRACKED_CONF.is_file(),
            f"RED: tracked conf is absent: {TRACKED_CONF}",
        )
        keys = declared_keys(TRACKED_CONF.read_text(encoding="utf-8"))
        for name in self.DRIVER_KEYS:
            self.assertIn(name, keys)
        self.assertTrue(
            self.DRIVER.is_file(),
            f"RED: driver is absent: {self.DRIVER}",
        )
        src = self.DRIVER.read_text(encoding="utf-8")
        for name in self.DRIVER_KEYS:
            with self.subTest(key=name):
                self.assertIn(name, src)
        proc = self.invoke(["closure"], lane_conf=None, cwd=REPO)
        self.assertEqual(proc.returncode, 0, self.combined(proc))


if __name__ == "__main__":
    unittest.main()

