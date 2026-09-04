"""Red tests for the check matrix PreToolUse hook (matrix.py).

Contract: the input brief's check-matrix contract. The module is run as a
subprocess with a PreToolUse JSON payload on stdin. Fixtures are a temporary
git repository, a temporary HOME holding a planted handwork.db, and a fake
cue on PATH. The hook path is invoked even when the file is absent so each
case goes red on its contract assertion, not as an invalid fixture.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

HOOK = support.CLAUDE_DIR / "matrix.py"

LANE_NAME = "testlane"
SCOPE_CAP = 64
SESSION_TURNS_CEILING = 100
SESSION_AVG_CONTEXT_CEILING = 200000
SESSION_REFUSALS_CEILING = 10
GRANT_SCOPED = 11
GRANT_OPEN = 22
GRANT_SETTLED = 33

SESSION_BUDGET_REFUSAL_MARKERS = (
    "[matrix:hand-write]",
    "[clipped-sweep]",
    "[clipped-runner]",
    "[unguarded-replace]",
    'permissionDecision": "deny"',
)

HANDWORK_DDL = """CREATE TABLE handwork(
    id INTEGER PRIMARY KEY, ts TEXT NOT NULL, session TEXT NOT NULL,
    agent TEXT NOT NULL, action TEXT NOT NULL, why_by_hand TEXT NOT NULL,
    missing_lever TEXT, evidence TEXT, lever_class TEXT, scope TEXT,
    ttl_s INTEGER, status TEXT DEFAULT 'settled', settled_ts TEXT,
    verified INTEGER, late INTEGER DEFAULT 0, settle_note TEXT)"""

LANE_CONF = """\
LANE_NAME='testlane'
TRUNK_BRANCH='dev'
RELEASE_BRANCH='master'
REPO_SLUG='test/repo'
CHECK_NAMES='lane'
WF_AGENT_DEFAULT='Test Agent <test@example.invalid>'
LANE_AUTHOR='Test Author <test@example.invalid>'
WORKTREE_ROOT='../wt'
ADDRESS_GROK='noreply@x.ai'
ADDRESS_CODEX='noreply@openai.com'
ADDRESS_CLAUDE='noreply@anthropic.com'
MODEL_GROK='grok-4.6'
MODEL_CODEX='gpt-5.6-sol'
MODEL_CODEX_SECURITY_AUDIT='gpt-daybreak-blue-latest'
MODEL_CLAUDE_READ='claude-opus-5'
MODEL_CLAUDE_PLAN='claude-fable-5-1'
EFFORT_GROK='xhigh'
EFFORT_CODEX='xhigh'
EFFORT_CLAUDE='high'
WALL_DEFAULT='900'
SCOPE_CAP='64'
SESSION_TURNS_CEILING='100'
SESSION_AVG_CONTEXT_CEILING='200000'
SESSION_REFUSALS_CEILING='10'
"""

CUE_OK = """\
package harness

ok: true
"""

WALKTHROUGH_OK = """\
## First-run walkthrough

- assumption: git is on PATH — measured: the fixture commits with git.
"""

WALKTHROUGH_NO_HEADING = """\
# Notes

- assumption: git is on PATH — measured: the fixture commits with git.
"""

WALKTHROUGH_NO_ASSUMPTION = """\
## First-run walkthrough

Prose with no assumption line.
"""

REASON_SHAPE = re.compile(
    r"^\[matrix:(?P<cls>[a-z-]+)\] (?P=cls): expected .+; found .+; needed .+$"
)

CODE_ROOT_TARGETS = (
    "ops/lane.conf",
    ".github/workflows/ci.yml",
    ".claude/settings.json",
    "docs/README.md",
    "packages/README.md",
    "src/app.py",
    "config/services.yaml",
    "bin/console",
    "tests/test_app.py",
    "templates/page.twig",
    "composer.json",
    "composer.lock",
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIB.md",
    "README.md",
    "pyproject.toml",
    "ruff.toml",
    "phpunit.xml",
    "phpunit.dist.xml",
)

HAND_WRITE_SPELLINGS = (
    "echo x > AGENTS.md",
    "echo x >AGENTS.md",
    "echo x >> AGENTS.md",
    "echo x 1> AGENTS.md",
    "sed -i s/a/b/ AGENTS.md",
    "perl -i -pe s/a/b/ AGENTS.md",
    "tee AGENTS.md",
    "cp /tmp/x AGENTS.md",
    "mv /tmp/x AGENTS.md",
    "install /tmp/x AGENTS.md",
    "rsync /tmp/x AGENTS.md",
    "ln -s /tmp/x AGENTS.md",
    "truncate -s 0 AGENTS.md",
    "git checkout HEAD -- AGENTS.md",
    "git restore AGENTS.md",
    "git apply changes.patch",
    "git am changes.patch",
    "git cherry-pick -n abcdef1",
    "patch -p1 < changes.patch",
    "python3 -c \"open('AGENTS.md','w').write('x')\"",
    "python3 -c \"open('AGENTS.md','a').write('x')\"",
    "python3 -c \"from pathlib import Path; Path('src/app.py').write_text('x')\"",
    "python3 -c \"from pathlib import Path; Path('src/app.py').write_bytes(b'x')\"",
    "python3 -c \"open('AGENTS.md','w').writelines(['x'])\"",
)

NOT_CODE_WRITES = (
    "echo x > .dev/out.txt",
    "echo x > ops/conductor/ideas/note.md",
    "echo x > ops/conductor/handoff/h.md",
    "echo x > ops/conductor/AAR-2026-09-04.md",
    "echo x > ops/conductor/probes/p.jsonl",
    "echo x > /tmp/matrix-hook-outside.txt",
    "cp AGENTS.md /tmp/matrix-hook-copied.txt",
    "echo hello",
)

WRITE_TOOLS = (
    "Write",
    "Edit",
    "MultiEdit",
    "mcp__serena__replace",
    "mcp__serena__insert",
    "mcp__serena__rename",
    "mcp__serena__safe_delete",
)

MALFORMED_STDIN = ("", "not json", "{", "[1,2]", "null", '"Bash"')

DRIVER_JOBS = (
    "author-tests",
    "check-tests",
    "implement",
    "security-audit",
    "adversarial-review",
)

ALLOWED_BY_HAND_JOBS = ("plan", "adjudicate", "sweep", "verify")

FIX_JOBS = ("implement-fix", "tests-fix", "any-fix")

PATH_FORM_UNITTEST_ARGS = (
    "ops/devlane/task/tests/test_check_tests_json.py",
    "ops/devlane/hooks/tests/test_matrix.py",
    "ops/devlane/hooks/tests/test_matrix",
    "tests/test_app.py",
    "test_matrix.py",
    "./tests/test_app.py",
    "ops.devlane.hooks.tests.test_matrix.py",
)

DOTTED_UNITTEST_NAMES = (
    "ops.devlane.hooks.tests.test_matrix",
    "tests.test_app",
    "test_matrix",
)

ALLOWED_BY_HAND_LINE = re.compile(
    r"^[ \t]*['\"]?(?P<name>plan|adjudicate|sweep|verify)['\"]?"
    r"[ \t]*[,:]?[ \t]*(?P<reason>#.+|.+)$"
)


class MatrixHookTests(unittest.TestCase):
    """One subprocess invocation of matrix.py per assertion."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="matrix-hook-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.bin = self.tmp / "bin"
        self.wt = self.tmp / "wt"
        self.repo = self.tmp / "repo"
        self.home.mkdir()
        self.bin.mkdir()
        self.wt.mkdir()
        self.repo.mkdir()
        support.plant_executable(
            self.bin / "cue", "#!/bin/sh\nexit ${CUE_FAKE_EXIT:-0}\n"
        )
        self.env = support.isolated_env(self.home, extra_path=self.bin)
        which_cue = shutil.which("cue", path=self.env["PATH"])
        self.assertIsNotNone(which_cue, "INVALID: fake cue not on PATH")
        self.assertEqual(
            Path(which_cue).resolve(),
            (self.bin / "cue").resolve(),
            "INVALID: PATH cue is not the planted fake",
        )
        self.store = (
            self.home / ".local" / "state" / LANE_NAME / "handwork.db"
        )
        self._plant_handwork()
        self._plant_tree()
        self._plant_git()
        self.assertGreater(self.store.stat().st_size, 0)
        self.assertLessEqual(self.scope_ok.stat().st_size, SCOPE_CAP)
        self.assertGreater(self.scope_big.stat().st_size, SCOPE_CAP)
        self.assertFalse(self.scope_missing.exists())
        ancestor = support.git(
            self.repo,
            self.env,
            "merge-base",
            "--is-ancestor",
            "origin/dev",
            "HEAD",
            expect=None,
        )
        self.assertEqual(
            ancestor.returncode,
            0,
            "INVALID: origin/dev is not an ancestor of HEAD in the fixture",
        )
        self.assertIn(
            f"SESSION_TURNS_CEILING='{SESSION_TURNS_CEILING}'",
            LANE_CONF,
        )
        self.assertIn(
            f"SESSION_AVG_CONTEXT_CEILING='{SESSION_AVG_CONTEXT_CEILING}'",
            LANE_CONF,
        )
        self.assertIn(
            f"SESSION_REFUSALS_CEILING='{SESSION_REFUSALS_CEILING}'",
            LANE_CONF,
        )
        self.transcript_under = self.tmp / "session-under.jsonl"
        self._plant_transcript(
            self.transcript_under, [self._usage_turn(n=0)]
        )

    def _plant_handwork(self):
        self.store.parent.mkdir(parents=True, exist_ok=True)
        rows = (
            (
                GRANT_SCOPED,
                "2026-09-04T00:00:00Z",
                "s1",
                "tester",
                "edit docs",
                "cannot wait for the lever",
                "other",
                None,
                "other",
                "docs/",
                1800,
                "open",
                None,
                None,
                0,
                None,
            ),
            (
                GRANT_OPEN,
                "2026-09-04T00:00:01Z",
                "s1",
                "tester",
                "edit anything",
                "cannot wait for the lever",
                "other",
                None,
                "other",
                None,
                1800,
                "open",
                None,
                None,
                0,
                None,
            ),
            (
                GRANT_SETTLED,
                "2026-09-04T00:00:02Z",
                "s1",
                "tester",
                "already done",
                "cannot wait for the lever",
                "other",
                "abc1234",
                "other",
                "docs/",
                1800,
                "settled",
                "2026-09-04T00:01:00Z",
                1,
                0,
                "done",
            ),
        )
        with sqlite3.connect(self.store) as conn:
            conn.execute(HANDWORK_DDL)
            conn.executemany(
                "INSERT INTO handwork (id, ts, session, agent, action, "
                "why_by_hand, missing_lever, evidence, lever_class, scope, "
                "ttl_s, status, settled_ts, verified, late, settle_note) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            conn.commit()
            landed = conn.execute(
                "SELECT id, status, scope FROM handwork ORDER BY id"
            ).fetchall()
        self.assertEqual(
            landed,
            [
                (GRANT_SCOPED, "open", "docs/"),
                (GRANT_OPEN, "open", None),
                (GRANT_SETTLED, "settled", "docs/"),
            ],
            "INVALID: planted handwork rows did not land",
        )

    def _plant_tree(self):
        files = {
            "ops/lane.conf": LANE_CONF,
            "ops/devlane/harness/ok.cue": CUE_OK,
            "ops/devlane/dispatch/launch.py": "#!/usr/bin/env python3\n",
            "ops/bin/dispatch.sh": "#!/bin/sh\n",
            "ops/bin/go.sh": "#!/bin/sh\n",
            "ops/bin/ladder.sh": "#!/bin/sh\n",
            "ops/conductor/ideas/note.md": "idea\n",
            "ops/conductor/handoff/h.md": "handoff\n",
            "ops/conductor/AAR-2026-09-04.md": "aar\n",
            "ops/conductor/probes/p.jsonl": "{}\n",
            ".dev/keep.txt": "keep\n",
            ".dev/out.txt": "out\n",
            ".github/workflows/ci.yml": "name: ci\n",
            ".claude/settings.json": "{}\n",
            "docs/README.md": "docs\n",
            "packages/README.md": "pkg\n",
            "src/app.py": "x = 1\n",
            "config/services.yaml": "services: {}\n",
            "bin/console": "#!/usr/bin/env php\n",
            "tests/test_app.py": "x = 1\n",
            "templates/page.twig": "{{ x }}\n",
            "composer.json": "{}\n",
            "composer.lock": "{}\n",
            "AGENTS.md": "agents\n",
            "CLAUDE.md": "claude\n",
            "CONTRIB.md": "contrib\n",
            "README.md": "readme\n",
            "pyproject.toml": "[tool]\n",
            "ruff.toml": "line-length = 88\n",
            "phpunit.xml": "<phpunit/>\n",
            "phpunit.dist.xml": "<phpunit/>\n",
        }
        for rel, body in files.items():
            support.plant_text(self.repo / rel, body, recognisable=body[:4])
        support.plant_text(self.wt / "ag-x" / "keep.txt", "wt\n", recognisable="wt")
        self.scope_ok = self.repo / ".dev" / "scope-ok.txt"
        self.scope_big = self.repo / ".dev" / "scope-big.txt"
        self.scope_suites = self.repo / ".dev" / "scope-suites.txt"
        self.scope_discover = self.repo / ".dev" / "scope-discover.txt"
        self.scope_discover_p = self.repo / ".dev" / "scope-discover-p.txt"
        self.scope_empty = self.repo / ".dev" / "scope-empty.txt"
        self.scope_dollar = self.repo / ".dev" / "scope-dollar.txt"
        self.scope_missing = self.repo / ".dev" / "no-such-scope.txt"
        self.input_ok = self.repo / ".dev" / "input-ok.md"
        self.input_no_heading = self.repo / ".dev" / "input-no-heading.md"
        self.input_no_assumption = self.repo / ".dev" / "input-no-assumption.md"
        self.input_missing = self.repo / ".dev" / "no-such-input.md"
        support.plant_text(
            self.scope_ok, "verify the matrix hook\n", recognisable="matrix hook"
        )
        support.plant_text(self.scope_big, "B" * 80, recognisable="BBBBB")
        support.plant_text(
            self.scope_suites, "run suites.sh please\n", recognisable="suites.sh"
        )
        support.plant_text(
            self.scope_discover,
            "unittest discover tests\n",
            recognisable="unittest discover",
        )
        support.plant_text(
            self.scope_discover_p,
            "unittest discover -p test_*.py\n",
            recognisable="unittest discover -p",
        )
        support.plant_text(self.scope_empty, "", recognisable="")
        support.plant_text(
            self.scope_dollar, "hello $WORLD\n", recognisable="$WORLD"
        )
        support.plant_text(
            self.input_ok, WALKTHROUGH_OK, recognisable="First-run walkthrough"
        )
        support.plant_text(
            self.input_no_heading,
            WALKTHROUGH_NO_HEADING,
            recognisable="# Notes",
        )
        support.plant_text(
            self.input_no_assumption,
            WALKTHROUGH_NO_ASSUMPTION,
            recognisable="no assumption line",
        )
        self.assertEqual(self.scope_empty.stat().st_size, 0)
        self.assertIn("$", self.scope_dollar.read_text(encoding="utf-8"))
        (self.repo / ".dev" / "records").mkdir()

    def _plant_git(self):
        support.git(
            self.repo, self.env, "-c", "init.defaultBranch=dev", "init", "-q"
        )
        support.configure_identity(self.repo, self.env)
        support.git(self.repo, self.env, "add", "-A")
        support.git(self.repo, self.env, "commit", "-q", "-m", "seed")
        sha = support.git(
            self.repo, self.env, "rev-parse", "HEAD"
        ).stdout.strip()
        self.assertGreaterEqual(len(sha), 7, "INVALID: seed commit SHA missing")
        support.git(
            self.repo, self.env, "update-ref", "refs/remotes/origin/dev", sha
        )
        origin = support.git(
            self.repo, self.env, "rev-parse", "origin/dev"
        ).stdout.strip()
        self.assertEqual(origin, sha, "INVALID: origin/dev was not planted")

    def payload_bash(self, command: str, cwd=None, *, transcript_path=None) -> str:
        cwd = str(cwd or self.repo)
        if transcript_path is None:
            transcript_path = str(self.transcript_under)
        return json.dumps(
            {
                "tool_name": "Bash",
                "cwd": cwd,
                "tool_input": {"command": command},
                "transcript_path": transcript_path,
            }
        )

    def payload_write(
        self, tool_name: str, *, transcript_path=None, **tool_input
    ) -> str:
        if transcript_path is None:
            transcript_path = str(self.transcript_under)
        return json.dumps(
            {
                "tool_name": tool_name,
                "cwd": str(self.repo),
                "tool_input": tool_input,
                "transcript_path": transcript_path,
            }
        )

    def _usage_turn(
        self,
        *,
        n=0,
        input_tokens=10,
        cache_creation=0,
        cache_read=0,
        output_tokens=1,
    ):
        return {
            "type": "assistant",
            "message": {
                "id": f"msg-{n}",
                "usage": {
                    "input_tokens": input_tokens,
                    "cache_creation_input_tokens": cache_creation,
                    "cache_read_input_tokens": cache_read,
                    "output_tokens": output_tokens,
                },
            },
        }

    def _tool_result(self, text: str):
        return {
            "type": "user",
            "message": {
                "content": [{"type": "tool_result", "content": text}],
            },
        }

    def _plant_transcript(self, path: Path, entries: list) -> str:
        self.assertGreater(len(entries), 0, "INVALID: empty transcript plant")
        body = "".join(json.dumps(entry) + "\n" for entry in entries)
        support.plant_text(path, body, recognisable='"type":')
        landed = path.read_text(encoding="utf-8")
        self.assertEqual(
            landed.count("\n"),
            len(entries),
            "INVALID: planted transcript line count drifted",
        )
        return landed

    def _plant_over_turns(self, name: str):
        n = SESSION_TURNS_CEILING + 1
        self.assertGreater(n, SESSION_TURNS_CEILING)
        path = self.tmp / name
        entries = [self._usage_turn(n=i) for i in range(n)]
        self._plant_transcript(path, entries)
        return path, n

    def run_hook(self, payload: str, *, env=None, cwd=None):
        return subprocess.run(
            [sys.executable, str(HOOK)],
            cwd=str(cwd or self.repo),
            env=env or self.env,
            input=payload,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    def run_bash(self, command: str, **kwargs):
        return self.run_hook(self.payload_bash(command), **kwargs)

    def dispatch(
        self,
        *,
        job="verify",
        wrapper="ops/bin/dispatch.sh",
        scope_file=None,
        input_file=False,
        worktree=None,
        extra="",
        pin=True,
    ) -> str:
        worktree = worktree or self.repo
        scope_file = scope_file or self.scope_ok
        if input_file is False and job in ("author-tests", "implement"):
            input_file = self.input_ok
        elif input_file is False:
            input_file = None
        parts = []
        if pin:
            parts.append(
                f"LAUNCHER_PIN={worktree}/ops/devlane/dispatch/launch.py"
            )
            parts.append("DISPATCH_TIMEOUT=30")
            parts.append("WF_AGENT=TestAgent")
        parts.append(wrapper)
        parts.append(f"--job {job}")
        parts.append(f"--worktree {worktree}")
        parts.append(f"--scope-file {scope_file}")
        if input_file is not None:
            parts.append(f"--input {input_file}")
        if extra:
            parts.append(extra)
        return " ".join(str(p) for p in parts)

    def allowed_by_hand_from_module(self) -> dict:
        self.assertTrue(
            HOOK.is_file(),
            "expected the allowed jobs as data at the top of the module; "
            f"found {HOOK} absent",
        )
        text = HOOK.read_text(encoding="utf-8")
        header = re.split(
            r"^(?:def |class )", text, maxsplit=1, flags=re.MULTILINE
        )[0]
        found = {}
        for raw in header.splitlines():
            match = ALLOWED_BY_HAND_LINE.match(raw)
            if match is None:
                continue
            name = match.group("name")
            reason = match.group("reason").lstrip("#").strip()
            found[name] = reason
        return found

    def env_without_cue(self):
        parts = []
        for item in self.env["PATH"].split(os.pathsep):
            if not item:
                continue
            if item == str(self.bin):
                continue
            if (Path(item) / "cue").exists():
                continue
            parts.append(item)
        env = dict(self.env)
        env["PATH"] = os.pathsep.join(parts)
        self.assertIsNone(
            shutil.which("cue", path=env["PATH"]),
            "INVALID: cue still visible on PATH",
        )
        return env

    def make_stale(self):
        support.git(
            self.repo, self.env, "commit", "-q", "--allow-empty", "-m", "ahead"
        )
        new = support.git(
            self.repo, self.env, "rev-parse", "HEAD"
        ).stdout.strip()
        support.git(
            self.repo, self.env, "update-ref", "refs/remotes/origin/dev", new
        )
        support.git(self.repo, self.env, "reset", "--hard", "HEAD~1")
        check = support.git(
            self.repo,
            self.env,
            "merge-base",
            "--is-ancestor",
            "origin/dev",
            "HEAD",
            expect=None,
        )
        self.assertNotEqual(
            check.returncode,
            0,
            "INVALID: origin/dev is still an ancestor of HEAD",
        )

    def assert_denied(self, proc, cls: str):
        self.assertTrue(
            proc.stdout and proc.stdout.strip(),
            f"expected deny of class {cls}; found empty stdout "
            f"(exit={proc.returncode} stderr={proc.stderr!r})",
        )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"expected deny of class {cls} as one JSON object; "
                f"found {proc.stdout!r} ({exc})"
            )
        hook = data.get("hookSpecificOutput") or {}
        self.assertEqual(
            hook.get("hookEventName"),
            "PreToolUse",
            f"expected PreToolUse hookEventName for {cls}; found {hook!r}",
        )
        self.assertEqual(
            hook.get("permissionDecision"),
            "deny",
            f"expected deny of class {cls}; found {hook!r}",
        )
        reason = hook.get("permissionDecisionReason") or ""
        self.assertRegex(
            reason.strip(),
            rf"^\[matrix:{re.escape(cls)}\] {re.escape(cls)}: "
            r"expected .+; found .+; needed .+$",
            f"reason for {cls} was {reason!r}",
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"hook must exit 0 on deny of {cls}; stderr={proc.stderr!r}",
        )

    def assert_allowed(self, proc):
        self.assertEqual(
            proc.returncode,
            0,
            f"expected allow (exit 0, empty stdout); found exit="
            f"{proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        self.assertEqual(
            proc.stdout,
            "",
            f"expected allow to print nothing; found {proc.stdout!r}",
        )

    # --- hand-write ---

    def test_hand_write_refuses_each_spelling_and_code_root(self):
        self.assertGreater(len(HAND_WRITE_SPELLINGS), 0)
        self.assertGreater(len(CODE_ROOT_TARGETS), 0)
        for cmd in HAND_WRITE_SPELLINGS:
            with self.subTest(spelling=cmd):
                self.assert_denied(self.run_bash(cmd), "hand-write")
        for target in CODE_ROOT_TARGETS:
            with self.subTest(target=target):
                self.assert_denied(
                    self.run_bash(f"echo x > {target}"), "hand-write"
                )

    def test_hand_write_allows_non_code_paths(self):
        self.assertGreater(len(NOT_CODE_WRITES), 0)
        for cmd in NOT_CODE_WRITES:
            with self.subTest(cmd=cmd):
                self.assert_allowed(self.run_bash(cmd))

    # --- direct-launch ---

    def test_direct_launch_refuses_launch_py_as_the_command(self):
        commands = (
            "ops/devlane/dispatch/launch.py",
            str(self.repo / "ops" / "devlane" / "dispatch" / "launch.py"),
            "./ops/devlane/dispatch/launch.py --job verify",
        )
        for cmd in commands:
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_bash(cmd), "direct-launch")

    def test_direct_launch_allows_dispatch_go_and_ladder_wrappers(self):
        commands = (
            self.dispatch(),
            self.dispatch(wrapper="ops/bin/go.sh"),
            self.dispatch(wrapper="ops/bin/ladder.sh"),
        )
        for cmd in commands:
            with self.subTest(cmd=cmd):
                self.assert_allowed(self.run_bash(cmd))

    # --- override ---

    def test_override_refuses_model_or_effort_on_dispatch_or_go(self):
        rows = (
            self.dispatch(extra="--model grok-4.6"),
            self.dispatch(extra="--effort xhigh"),
            self.dispatch(wrapper="ops/bin/go.sh", extra="--model grok-4.6"),
            self.dispatch(wrapper="ops/bin/go.sh", extra="--effort high"),
        )
        for cmd in rows:
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_bash(cmd), "override")

    def test_override_allows_dispatch_without_model_or_effort(self):
        self.assert_allowed(self.run_bash(self.dispatch()))

    # --- input-absent ---

    def test_input_absent_refuses_missing_empty_or_unresolved(self):
        rows = (
            self.dispatch(scope_file=self.scope_missing),
            self.dispatch(scope_file=self.scope_empty),
            self.dispatch(scope_file=self.scope_dollar),
            self.dispatch(scope_file=self.repo / ".dev" / "$UNRESOLVED"),
            self.dispatch(
                job="author-tests", input_file=self.input_missing
            ),
        )
        for cmd in rows:
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_bash(cmd), "input-absent")

    def test_input_absent_allows_existing_nonempty_resolved_files(self):
        self.assert_allowed(self.run_bash(self.dispatch()))

    # --- scope-cap ---

    def test_scope_cap_refuses_a_scope_file_over_the_cap(self):
        self.assert_denied(
            self.run_bash(self.dispatch(scope_file=self.scope_big)),
            "scope-cap",
        )

    def test_scope_cap_allows_a_scope_file_at_or_under_the_cap(self):
        self.assert_allowed(self.run_bash(self.dispatch()))

    # --- bucket-command ---

    def test_bucket_command_refuses_implement_scope_with_forbidden_runners(self):
        rows = (
            self.dispatch(job="implement", scope_file=self.scope_suites),
            self.dispatch(job="implement", scope_file=self.scope_discover),
        )
        for cmd in rows:
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_bash(cmd), "bucket-command")

    def test_bucket_command_allows_other_jobs_and_discover_with_p(self):
        allowed = (
            self.dispatch(job="verify", scope_file=self.scope_suites),
        )
        for cmd in allowed:
            with self.subTest(cmd=cmd):
                self.assert_allowed(self.run_bash(cmd))
        driver = (
            self.dispatch(job="implement", scope_file=self.scope_discover_p),
            self.dispatch(job="implement"),
        )
        for cmd in driver:
            with self.subTest(cmd=cmd):
                proc = self.run_bash(cmd)
                self.assert_denied(proc, "dispatch-by-hand")
                self.assertNotIn(
                    "[matrix:bucket-command]",
                    proc.stdout,
                    "content row bucket-command must pass on a good "
                    f"implement plant; found {proc.stdout!r}",
                )

    # --- walkthrough ---

    def test_walkthrough_refuses_author_tests_or_implement_without_the_heading_or_assumption(
        self,
    ):
        rows = (
            self.dispatch(
                job="author-tests", input_file=self.input_no_heading
            ),
            self.dispatch(
                job="author-tests", input_file=self.input_no_assumption
            ),
            self.dispatch(job="implement", input_file=self.input_no_heading),
            self.dispatch(
                job="implement", input_file=self.input_no_assumption
            ),
        )
        for cmd in rows:
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_bash(cmd), "walkthrough")

    def test_walkthrough_allows_when_heading_and_assumption_are_present(self):
        driver = (
            self.dispatch(job="author-tests", input_file=self.input_ok),
            self.dispatch(job="implement", input_file=self.input_ok),
        )
        for cmd in driver:
            with self.subTest(cmd=cmd):
                proc = self.run_bash(cmd)
                self.assert_denied(proc, "dispatch-by-hand")
                self.assertNotIn(
                    "[matrix:walkthrough]",
                    proc.stdout,
                    "content row walkthrough must pass when the heading "
                    f"and assumption are present; found {proc.stdout!r}",
                )
        self.assert_allowed(self.run_bash(self.dispatch(job="verify")))

    # --- stale-base ---

    def test_stale_base_refuses_when_origin_trunk_is_not_an_ancestor(self):
        self.make_stale()
        self.assert_denied(self.run_bash(self.dispatch()), "stale-base")

    def test_stale_base_allows_when_origin_trunk_is_an_ancestor(self):
        self.assert_allowed(self.run_bash(self.dispatch()))

    # --- contract-vet ---

    def test_contract_vet_refuses_when_cue_vet_fails(self):
        support.plant_executable(self.bin / "cue", "#!/bin/sh\nexit 1\n")
        support.plant_text(
            self.repo / "ops" / "devlane" / "harness" / "ok.cue",
            "this is not cue {\n",
            recognisable="not cue",
        )
        self.assert_denied(self.run_bash(self.dispatch()), "contract-vet")

    def test_contract_vet_refuses_when_cue_is_absent(self):
        self.assert_denied(
            self.run_bash(self.dispatch(), env=self.env_without_cue()),
            "contract-vet",
        )

    def test_contract_vet_allows_when_cue_vet_exits_zero(self):
        self.assert_allowed(self.run_bash(self.dispatch()))

    # --- dispatch-env ---

    def test_dispatch_env_refuses_when_pin_timeout_or_agent_is_missing(self):
        worktree = self.repo
        base = (
            f"ops/bin/dispatch.sh --job verify --worktree {worktree} "
            f"--scope-file {self.scope_ok}"
        )
        pin = f"LAUNCHER_PIN={worktree}/ops/devlane/dispatch/launch.py"
        rows = (
            base,
            f"{pin} DISPATCH_TIMEOUT=30 {base}",
            f"{pin} WF_AGENT=TestAgent {base}",
            f"DISPATCH_TIMEOUT=30 WF_AGENT=TestAgent {base}",
        )
        for cmd in rows:
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_bash(cmd), "dispatch-env")

    def test_dispatch_env_allows_when_pin_timeout_and_agent_are_in_the_text(self):
        self.assert_allowed(self.run_bash(self.dispatch()))

    # --- prune ---

    def test_prune_refuses_the_named_trees(self):
        rows = (
            "rm -rf .dev/records",
            "rm -r .git",
            "rm -rf ops/conductor/ideas",
            f"rm -rf {self.wt}/ag-x",
            "rm -rf ../wt/ag-x",
            f"rm -rf {self.home}/.local/state/{LANE_NAME}",
            f"rm -r ~/.local/state/{LANE_NAME}",
        )
        for cmd in rows:
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_bash(cmd), "prune")

    def test_prune_allows_other_removals(self):
        rows = (
            "rm -rf .dev/tmp",
            "rm AGENTS.md",
            "rm -r ops/devlane/hooks",
        )
        for cmd in rows:
            with self.subTest(cmd=cmd):
                self.assert_allowed(self.run_bash(cmd))

    # --- grant escape ---

    def test_grant_escape_allows_hand_write_inside_scope(self):
        self.assert_allowed(
            self.run_bash(
                f"HAND_GRANT={GRANT_SCOPED} echo x > docs/README.md"
            )
        )

    def test_grant_escape_allows_direct_launch_when_the_grant_is_open(self):
        self.assert_allowed(
            self.run_bash(
                f"HAND_GRANT={GRANT_OPEN} ops/devlane/dispatch/launch.py"
            )
        )

    def test_grant_escape_does_not_cover_paths_outside_its_scope(self):
        self.assert_denied(
            self.run_bash(f"HAND_GRANT={GRANT_SCOPED} echo x > AGENTS.md"),
            "hand-write",
        )

    def test_grant_escape_unscoped_open_grant_covers_any_hand_write(self):
        self.assert_allowed(
            self.run_bash(f"HAND_GRANT={GRANT_OPEN} echo x > AGENTS.md")
        )

    def test_grant_escape_ignores_settled_missing_and_malformed_grants(self):
        rows = (
            f"HAND_GRANT={GRANT_SETTLED} echo x > docs/README.md",
            "HAND_GRANT=999 echo x > docs/README.md",
            "HAND_GRANT= echo x > docs/README.md",
            "HAND_GRANT=not-an-id echo x > docs/README.md",
        )
        for cmd in rows:
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_bash(cmd), "hand-write")

    def test_grant_escape_does_not_cover_prune(self):
        self.assert_denied(
            self.run_bash(f"HAND_GRANT={GRANT_OPEN} rm -rf .git"),
            "prune",
        )

    # --- named extras ---

    def test_pipeline_tee_to_a_code_path_refuses_as_hand_write(self):
        self.assert_denied(
            self.run_bash("echo x | tee AGENTS.md"), "hand-write"
        )

    def test_leading_assignment_does_not_hide_the_command_word(self):
        self.assert_denied(
            self.run_bash("FOO=bar ops/devlane/dispatch/launch.py"),
            "direct-launch",
        )

    def test_export_of_launcher_pin_is_not_a_direct_launch(self):
        self.assert_allowed(
            self.run_bash(
                f"export LAUNCHER_PIN={self.repo}/ops/devlane/dispatch/launch.py"
            )
        )

    def test_untracked_run_script_is_read_and_checked(self):
        script = self.repo / ".dev" / "run-write.sh"
        support.plant_text(
            script,
            "#!/bin/sh\nDEST=AGENTS.md\necho x > $DEST\n",
            recognisable="DEST=AGENTS.md",
        )
        tracked = support.git(
            self.repo, self.env, "ls-files", ".dev/run-write.sh"
        ).stdout.strip()
        self.assertEqual(tracked, "", "INVALID: run script was tracked")
        for cmd in (
            "bash .dev/run-write.sh",
            "sh .dev/run-write.sh",
            "source .dev/run-write.sh",
        ):
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_bash(cmd), "hand-write")

    def test_bash_c_is_checked(self):
        self.assert_denied(
            self.run_bash("bash -c 'echo x > AGENTS.md'"),
            "hand-write",
        )
        self.assert_allowed(self.run_bash("bash -c 'echo hello'"))

    def test_malformed_stdin_allows(self):
        self.assertGreater(len(MALFORMED_STDIN), 0)
        for raw in MALFORMED_STDIN:
            with self.subTest(raw=raw):
                self.assert_allowed(self.run_hook(raw))

    def test_write_tool_payload_on_a_code_path_refuses(self):
        abs_agents = str(self.repo / "AGENTS.md")
        rows = []
        for tool in WRITE_TOOLS:
            rows.append((tool, {"file_path": abs_agents}))
            rows.append((tool, {"relative_path": "AGENTS.md"}))
        self.assertGreater(len(rows), 0)
        for tool, tool_input in rows:
            with self.subTest(tool=tool, tool_input=tool_input):
                self.assert_denied(
                    self.run_hook(self.payload_write(tool, **tool_input)),
                    "hand-write",
                )

    def test_write_tool_payload_on_dot_dev_allows(self):
        abs_dev = str(self.repo / ".dev" / "out.txt")
        rows = (
            ("Write", {"file_path": abs_dev}),
            ("Edit", {"relative_path": ".dev/out.txt"}),
            ("MultiEdit", {"file_path": abs_dev}),
        )
        for tool, tool_input in rows:
            with self.subTest(tool=tool, tool_input=tool_input):
                self.assert_allowed(
                    self.run_hook(self.payload_write(tool, **tool_input))
                )

    def test_reason_string_carries_the_class_and_the_three_clauses(self):
        proc = self.run_bash("echo x > AGENTS.md")
        self.assert_denied(proc, "hand-write")
        _decision, reason = support.permission_decision(proc.stdout)
        match = REASON_SHAPE.match(reason.strip())
        self.assertIsNotNone(
            match, f"reason {reason!r} does not match {REASON_SHAPE.pattern}"
        )
        self.assertEqual(match.group("cls"), "hand-write")
        self.assertIn("expected ", reason)
        self.assertIn("; found ", reason)
        self.assertIn("; needed ", reason)

    # --- dispatch-by-hand ---

    def test_dispatch_by_hand_refuses_driver_jobs_from_the_session(self):
        self.assertGreater(len(DRIVER_JOBS), 0)
        wrappers = ("ops/bin/dispatch.sh", "ops/bin/go.sh")
        for wrapper in wrappers:
            for job in DRIVER_JOBS:
                with self.subTest(wrapper=wrapper, job=job):
                    self.assert_denied(
                        self.run_bash(self.dispatch(job=job, wrapper=wrapper)),
                        "dispatch-by-hand",
                    )

    def test_dispatch_by_hand_refuses_jobs_whose_name_ends_in_fix(self):
        self.assertGreater(len(FIX_JOBS), 0)
        for job in FIX_JOBS:
            with self.subTest(job=job):
                self.assertTrue(job.endswith("-fix"), job)
                self.assert_denied(
                    self.run_bash(self.dispatch(job=job)),
                    "dispatch-by-hand",
                )

    def test_dispatch_by_hand_allows_jobs_named_as_data_at_the_top_of_the_module(
        self,
    ):
        self.assertGreater(len(ALLOWED_BY_HAND_JOBS), 0)
        for job in ALLOWED_BY_HAND_JOBS:
            with self.subTest(job=job, phase="dispatch"):
                self.assert_allowed(self.run_bash(self.dispatch(job=job)))
        found = self.allowed_by_hand_from_module()
        for name in ALLOWED_BY_HAND_JOBS:
            with self.subTest(job=name, phase="data"):
                self.assertIn(
                    name,
                    found,
                    "expected the allowed jobs as data at the top of the "
                    f"module, one name per line, with the reason; found "
                    f"{found!r}",
                )
                self.assertRegex(
                    found[name],
                    r"[A-Za-z]",
                    f"expected a reason on the data line for {name}; "
                    f"found {found[name]!r}",
                )

    def test_dispatch_by_hand_grant_escape_allows_a_driver_job(self):
        cmd = self.dispatch(job="implement")
        self.assert_allowed(
            self.run_bash(f"HAND_GRANT={GRANT_OPEN} {cmd}")
        )

    def test_dispatch_by_hand_grant_escape_ignores_scoped_settled_and_missing_grants(
        self,
    ):
        cmd = self.dispatch(job="implement")
        rows = (
            f"HAND_GRANT={GRANT_SCOPED} {cmd}",
            f"HAND_GRANT={GRANT_SETTLED} {cmd}",
            f"HAND_GRANT=999 {cmd}",
            "HAND_GRANT= " + cmd,
            f"HAND_GRANT=not-an-id {cmd}",
        )
        self.assertGreater(len(rows), 0)
        for granted in rows:
            with self.subTest(cmd=granted):
                self.assert_denied(
                    self.run_bash(granted), "dispatch-by-hand"
                )

    def test_dispatch_by_hand_does_not_refuse_ladder_sh(self):
        rows = (
            "ops/bin/ladder.sh some-scope some-branch",
            "ops/bin/ladder.sh some-scope some-branch some-plan",
            "ops/bin/ladder.sh resume 42",
            self.dispatch(wrapper="ops/bin/ladder.sh", job="author-tests"),
            self.dispatch(wrapper="ops/bin/ladder.sh", job="implement"),
            self.dispatch(wrapper="ops/bin/ladder.sh", job="implement-fix"),
        )
        self.assertGreater(len(rows), 0)
        for cmd in rows:
            with self.subTest(cmd=cmd):
                self.assert_allowed(self.run_bash(cmd))

    def test_dispatch_by_hand_reason_names_the_job_and_the_driver(self):
        job = "author-tests"
        proc = self.run_bash(self.dispatch(job=job))
        self.assert_denied(proc, "dispatch-by-hand")
        _decision, reason = support.permission_decision(proc.stdout)
        expected = (
            "[matrix:dispatch-by-hand] dispatch-by-hand: expected the "
            f"ladder driver to run {job} (ops/bin/ladder.sh); found "
            f"dispatch.sh --job {job} from the session; needed start or "
            "resume a ladder for the lane"
        )
        self.assertEqual(reason.strip(), expected)

    def test_dispatch_by_hand_refuses_when_every_content_row_passes(self):
        self.assertLessEqual(self.scope_ok.stat().st_size, SCOPE_CAP)
        self.assertGreater(self.scope_ok.stat().st_size, 0)
        scope_text = self.scope_ok.read_text(encoding="utf-8")
        self.assertNotIn("suites.sh", scope_text)
        self.assertNotIn("unittest discover", scope_text)
        walk = self.input_ok.read_text(encoding="utf-8")
        self.assertIn("First-run walkthrough", walk)
        self.assertRegex(walk, r"- assumption.+(measured|refusal)")
        rows = (
            self.dispatch(job="implement"),
            self.dispatch(job="author-tests"),
        )
        self.assertGreater(len(rows), 0)
        for cmd in rows:
            with self.subTest(cmd=cmd):
                self.assertIn("LAUNCHER_PIN=", cmd)
                self.assertIn("DISPATCH_TIMEOUT=", cmd)
                self.assertIn("WF_AGENT=", cmd)
                self.assertNotRegex(cmd, r"(^|\s)--model(\s|=)")
                self.assertNotRegex(cmd, r"(^|\s)--effort(\s|=)")
                self.assert_denied(
                    self.run_bash(cmd), "dispatch-by-hand"
                )

    def test_dispatch_by_hand_is_last_among_the_dispatch_rows(self):
        self.assertGreater(
            self.scope_big.stat().st_size,
            SCOPE_CAP,
            "INVALID: oversize plant is not over SCOPE_CAP",
        )
        self.assertLessEqual(
            self.scope_ok.stat().st_size,
            SCOPE_CAP,
            "INVALID: clean plant exceeded SCOPE_CAP",
        )
        walk = self.input_ok.read_text(encoding="utf-8")
        self.assertIn("First-run walkthrough", walk)
        self.assertRegex(walk, r"- assumption.+(measured|refusal)")
        oversize = self.dispatch(job="implement", scope_file=self.scope_big)
        self.assertIn("--job implement", oversize)
        self.assertIn("ops/bin/dispatch.sh", oversize)
        self.assertIn(str(self.scope_big), oversize)
        self.assertNotRegex(oversize, r"(^|\s)--model(\s|=)")
        self.assertNotRegex(oversize, r"(^|\s)--effort(\s|=)")
        self.assert_denied(self.run_bash(oversize), "scope-cap")
        clean = self.dispatch(job="implement")
        self.assertIn("--job implement", clean)
        self.assertIn("ops/bin/dispatch.sh", clean)
        self.assertIn(str(self.scope_ok), clean)
        self.assertNotIn(str(self.scope_big), clean)
        self.assertNotRegex(clean, r"(^|\s)--model(\s|=)")
        self.assertNotRegex(clean, r"(^|\s)--effort(\s|=)")
        self.assert_denied(self.run_bash(clean), "dispatch-by-hand")

    # --- test-form ---

    def test_test_form_refuses_a_path_form_unittest_argument(self):
        self.assertGreater(len(PATH_FORM_UNITTEST_ARGS), 0)
        commands = [
            f"python3 -m unittest {arg}" for arg in PATH_FORM_UNITTEST_ARGS
        ]
        commands.append("python3 -m unittest -q tests/test_app.py")
        for cmd in commands:
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_bash(cmd), "test-form")

    def test_test_form_allows_discover_form_and_suites_sh(self):
        rows = (
            "python3 -m unittest discover",
            "python3 -m unittest discover -s tests -p test_*.py",
            (
                "python3 -m unittest discover -s ops/devlane/hooks/tests "
                "-p test_matrix.py"
            ),
            "bash ops/bin/suites.sh",
            "ops/bin/suites.sh",
        )
        self.assertGreater(len(rows), 0)
        for cmd in rows:
            with self.subTest(cmd=cmd):
                self.assert_allowed(self.run_bash(cmd))

    def test_test_form_allows_a_dotted_module_name(self):
        self.assertGreater(len(DOTTED_UNITTEST_NAMES), 0)
        for name in DOTTED_UNITTEST_NAMES:
            with self.subTest(name=name):
                self.assert_allowed(
                    self.run_bash(f"python3 -m unittest {name}")
                )

    def test_test_form_path_in_implement_scope_is_bucket_command(self):
        fragment = "tests/test_app.py"
        scope = self.repo / ".dev" / "scope-path-form.txt"
        body = f"python3 -m unittest {fragment}\n"
        support.plant_text(scope, body, recognisable=fragment)
        self.assertLessEqual(
            scope.stat().st_size,
            SCOPE_CAP,
            "INVALID: path-form scope exceeded SCOPE_CAP",
        )
        cmd = self.dispatch(job="implement", scope_file=scope)
        proc = self.run_bash(f"HAND_GRANT={GRANT_OPEN} {cmd}")
        self.assert_denied(proc, "bucket-command")
        _decision, reason = support.permission_decision(proc.stdout)
        self.assertIn("; found ", reason)
        found_clause = reason.split("; found ", 1)[1].split("; needed ", 1)[0]
        self.assertIn(
            fragment,
            found_clause,
            f"expected the found clause to name {fragment!r}; "
            f"found {reason!r}",
        )

    def test_test_form_reason_names_the_path_form_argument(self):
        arg = "ops/devlane/task/tests/test_check_tests_json.py"
        proc = self.run_bash(f"python3 -m unittest {arg}")
        self.assert_denied(proc, "test-form")
        _decision, reason = support.permission_decision(proc.stdout)
        expected = (
            "[matrix:test-form] test-form: expected the discover form "
            "(python3 -m unittest discover -s <tests dir> -p <file>) "
            f"or ops/bin/suites.sh; found a path-form unittest argument "
            f"{arg}; needed the discover form"
        )
        self.assertEqual(reason.strip(), expected)

    def test_test_form_has_no_grant_escape(self):
        self.assert_denied(
            self.run_bash(
                f"HAND_GRANT={GRANT_OPEN} "
                "python3 -m unittest tests/test_app.py"
            ),
            "test-form",
        )

    # --- session-budget ---

    def test_session_budget_planted_ceilings_are_the_measured_production_set(
        self,
    ):
        self.assertEqual(SESSION_TURNS_CEILING, 500)
        self.assertEqual(SESSION_AVG_CONTEXT_CEILING, 400000)
        self.assertEqual(SESSION_REFUSALS_CEILING, 25)
        self.assertIn("SESSION_TURNS_CEILING='500'", LANE_CONF)
        self.assertIn("SESSION_AVG_CONTEXT_CEILING='400000'", LANE_CONF)
        self.assertIn("SESSION_REFUSALS_CEILING='25'", LANE_CONF)
        self.assertNotIn("SESSION_TURNS_CEILING='100'", LANE_CONF)
        self.assertNotIn("SESSION_AVG_CONTEXT_CEILING='200000'", LANE_CONF)
        self.assertNotIn("SESSION_REFUSALS_CEILING='10'", LANE_CONF)
        self.assertGreater(1377, SESSION_TURNS_CEILING)
        self.assertGreater(448000, SESSION_AVG_CONTEXT_CEILING)
        self.assertGreater(70, SESSION_REFUSALS_CEILING)

    def test_session_budget_refuses_when_transcript_path_is_missing(self):
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "cwd": str(self.repo),
                "tool_input": {"command": "echo hello"},
            }
        )
        self.assertNotIn("transcript_path", json.loads(payload))
        proc = self.run_hook(payload)
        self.assert_denied(proc, "session-budget")
        _decision, reason = support.permission_decision(proc.stdout)
        self.assertIn("could not look", reason)
        self.assertIn("missing transcript_path", reason)

    def test_session_budget_refuses_when_transcript_path_is_unreadable(self):
        path = self.tmp / "no-such-session.jsonl"
        self.assertFalse(path.exists(), "INVALID: unreadable plant exists")
        proc = self.run_hook(
            self.payload_bash("echo hello", transcript_path=str(path))
        )
        self.assert_denied(proc, "session-budget")
        _decision, reason = support.permission_decision(proc.stdout)
        self.assertIn("could not look", reason)
        self.assertIn(str(path), reason)

    def test_session_budget_refuses_when_a_ceiling_key_is_missing(self):
        keys = (
            "SESSION_TURNS_CEILING",
            "SESSION_AVG_CONTEXT_CEILING",
            "SESSION_REFUSALS_CEILING",
        )
        self.assertEqual(len(keys), 3)
        conf_path = self.repo / "ops" / "lane.conf"
        for key in keys:
            with self.subTest(key=key):
                self.assertIn(f"{key}=", LANE_CONF)
                body = "".join(
                    line + "\n"
                    for line in LANE_CONF.splitlines()
                    if not line.startswith(f"{key}=")
                )
                self.assertNotIn(f"{key}=", body)
                for other in keys:
                    if other != key:
                        self.assertIn(f"{other}=", body)
                support.plant_text(
                    conf_path, body, recognisable="LANE_NAME"
                )
                planted = conf_path.read_text(encoding="utf-8")
                self.assertNotIn(f"{key}=", planted)
                self.assertIn("LANE_NAME", planted)
                proc = self.run_bash("echo hello")
                self.assert_denied(proc, "conf-key")
                _decision, reason = support.permission_decision(proc.stdout)
                self.assertIn(key, reason)
                needed = reason.split("; needed ", 1)
                self.assertEqual(
                    len(needed),
                    2,
                    f"expected a needed clause; found {reason!r}",
                )
                self.assertIn("ops/lane.conf", needed[1])

    def test_session_budget_refuses_when_turns_pass_the_conf_ceiling(self):
        path, n = self._plant_over_turns("session-over-turns.jsonl")
        self.assertEqual(n, SESSION_TURNS_CEILING + 1)
        proc = self.run_hook(
            self.payload_bash("echo hello", transcript_path=str(path))
        )
        self.assert_denied(proc, "session-budget")
        _decision, reason = support.permission_decision(proc.stdout)
        found = reason.split("; found ", 1)
        self.assertEqual(
            len(found), 2, f"expected a found clause; found {reason!r}"
        )
        found_clause = found[1].split("; needed ", 1)[0]
        self.assertIn(str(n), found_clause)

    def test_session_budget_refuses_when_average_context_passes_the_conf_ceiling(
        self,
    ):
        usage = self._usage_turn(
            n=0,
            input_tokens=100000,
            cache_creation=50000,
            cache_read=50001,
        )
        mean = (
            usage["message"]["usage"]["input_tokens"]
            + usage["message"]["usage"]["cache_creation_input_tokens"]
            + usage["message"]["usage"]["cache_read_input_tokens"]
        )
        self.assertGreater(mean, SESSION_AVG_CONTEXT_CEILING)
        self.assertLess(
            usage["message"]["usage"]["input_tokens"],
            SESSION_AVG_CONTEXT_CEILING,
        )
        self.assertLess(
            usage["message"]["usage"]["cache_creation_input_tokens"],
            SESSION_AVG_CONTEXT_CEILING,
        )
        self.assertLess(
            usage["message"]["usage"]["cache_read_input_tokens"],
            SESSION_AVG_CONTEXT_CEILING,
        )
        path = self.tmp / "session-over-avg.jsonl"
        self._plant_transcript(path, [usage])
        proc = self.run_hook(
            self.payload_bash("echo hello", transcript_path=str(path))
        )
        self.assert_denied(proc, "session-budget")
        _decision, reason = support.permission_decision(proc.stdout)
        found = reason.split("; found ", 1)
        self.assertEqual(
            len(found), 2, f"expected a found clause; found {reason!r}"
        )
        found_clause = found[1].split("; needed ", 1)[0]
        self.assertIn(str(mean), found_clause)

    def test_session_budget_refuses_when_refusals_pass_the_conf_ceiling(self):
        markers = SESSION_BUDGET_REFUSAL_MARKERS
        self.assertGreater(len(markers), 0)
        n = SESSION_REFUSALS_CEILING + 1
        self.assertGreater(n, SESSION_REFUSALS_CEILING)
        entries = [self._usage_turn(n=0)]
        for i in range(n):
            entries.append(self._tool_result(markers[i % len(markers)]))
        path = self.tmp / "session-over-refusals.jsonl"
        body = self._plant_transcript(path, entries)
        contents = []
        for line in body.splitlines():
            row = json.loads(line)
            blocks = (row.get("message") or {}).get("content") or []
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_result"
                ):
                    contents.append(block.get("content") or "")
        self.assertEqual(len(contents), n)
        for marker in markers:
            self.assertTrue(
                any(marker in text for text in contents),
                f"INVALID: marker {marker!r} missing from planted results",
            )
        proc = self.run_hook(
            self.payload_bash("echo hello", transcript_path=str(path))
        )
        self.assert_denied(proc, "session-budget")
        _decision, reason = support.permission_decision(proc.stdout)
        found = reason.split("; found ", 1)
        self.assertEqual(
            len(found), 2, f"expected a found clause; found {reason!r}"
        )
        found_clause = found[1].split("; needed ", 1)[0]
        self.assertIn(str(n), found_clause)

    def test_session_budget_reason_names_the_hand_off(self):
        path, n = self._plant_over_turns("session-reason.jsonl")
        proc = self.run_hook(
            self.payload_bash("echo hello", transcript_path=str(path))
        )
        self.assert_denied(proc, "session-budget")
        _decision, reason = support.permission_decision(proc.stdout)
        match = REASON_SHAPE.match(reason.strip())
        self.assertIsNotNone(
            match, f"reason {reason!r} does not match {REASON_SHAPE.pattern}"
        )
        self.assertEqual(match.group("cls"), "session-budget")
        self.assertIn("expected ", reason)
        self.assertIn("; found ", reason)
        self.assertIn("; needed ", reason)
        needed = reason.split("; needed ", 1)[1].strip()
        self.assertEqual(needed, "close the session with the hand-off")
        found_clause = reason.split("; found ", 1)[1].split("; needed ", 1)[0]
        self.assertIn(str(n), found_clause)

    def test_session_budget_refuses_a_write_tool_past_a_ceiling(self):
        path, _n = self._plant_over_turns("session-write.jsonl")
        target = self.repo / ".dev" / "out.txt"
        self.assertTrue(target.is_file(), "INVALID: .dev write target missing")
        proc = self.run_hook(
            self.payload_write(
                "Write",
                file_path=str(target),
                transcript_path=str(path),
            )
        )
        self.assert_denied(proc, "session-budget")
        self.assertNotIn("[matrix:hand-write]", proc.stdout)

    def test_session_budget_allows_under_all_three_ceilings(self):
        raw = self.payload_bash("echo hello")
        data = json.loads(raw)
        self.assertEqual(
            data.get("transcript_path"), str(self.transcript_under)
        )
        body = self.transcript_under.read_text(encoding="utf-8")
        self.assertTrue(body.strip(), "INVALID: under-ceiling transcript empty")
        rows = [json.loads(line) for line in body.splitlines() if line]
        usage_rows = [
            row
            for row in rows
            if row.get("type") == "assistant"
            and isinstance((row.get("message") or {}).get("usage"), dict)
        ]
        self.assertGreater(len(usage_rows), 0)
        self.assertLessEqual(len(usage_rows), SESSION_TURNS_CEILING)
        totals = []
        for row in usage_rows:
            usage = row["message"]["usage"]
            totals.append(
                int(usage.get("input_tokens") or 0)
                + int(usage.get("cache_creation_input_tokens") or 0)
                + int(usage.get("cache_read_input_tokens") or 0)
            )
        mean = sum(totals) / len(totals)
        self.assertLessEqual(mean, SESSION_AVG_CONTEXT_CEILING)
        self.assert_allowed(self.run_bash("echo hello"))

    def test_session_budget_has_no_grant_escape(self):
        path, _n = self._plant_over_turns("session-grant.jsonl")
        proc = self.run_hook(
            self.payload_bash(
                f"HAND_GRANT={GRANT_OPEN} echo x > AGENTS.md",
                transcript_path=str(path),
            )
        )
        self.assert_denied(proc, "session-budget")
        self.assertNotIn("[matrix:hand-write]", proc.stdout)


if __name__ == "__main__":
    unittest.main()
