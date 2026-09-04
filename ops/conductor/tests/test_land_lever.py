"""Land-lever acceptance tests, written from the contracts.

Contracts (only): `ops/conductor/land-lever.md` and the inherited
`ops/conductor/instrument-conventions.md`. The tool
`ops/conductor/tools/land.py` is the subject and is not read here.
Tests invoke it as a subprocess inside a scratch git repository.

The live dispatch store and this repo must stay untouched — asserted
in tearDown.

The implementation lands in parallel. A missing tool file is one red
(`test_the_tool_file_is_present`). Every other case stages a
copy-tool-bytes stand-in so a missing file is not every test's failure:
when the tool exists its bytes are copied and run; when it does not, a
no-op stub (exit 0, no output) is planted so each assertion goes red on
the contract promise rather than Python's missing-file exit 2.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "land.py"

BRANCH = "land-lineage"
REC = "land-rec-1"
REF = f"refs/dispatch/{REC}"
AGENT = "Land Lever Tester <land-tester@example.invalid>"
MALFORMED_AGENT = "JustAName"
PRODUCER = "Producer Author"
PRODUCER_EMAIL = "producer@example.invalid"
REPO_USER = "Repo Config"
REPO_EMAIL = "repo-config@example.invalid"
LANE_AUTHOR_NAME = "Lane Owner"
LANE_AUTHOR_EMAIL = "lane-owner@example.invalid"
LANE_AUTHOR = f"{LANE_AUTHOR_NAME} <{LANE_AUTHOR_EMAIL}>"
CO_AUTHOR = "Worker Model <noreply@vendor.example>"
TRAILER = f"Source: original\nCo-Authored-By: {CO_AUTHOR}"
SUBJECT = "producer-one"
RUN_CAP = 30

ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)

LANDED_RE = re.compile(r"^LANDED\t([0-9a-f]{7,40})\t(.*)$")
SUMMARY_RE = re.compile(r"^landed n=(\d+) ref=(refs/dispatch/.+)$")

# PIN_LANDED_STREAM: success prints LANDED lines and the summary on
# stdout (refusals already own stderr; the act's reading is the result).
# PIN_N0_LINE: empty range prints exactly `landed n=0`, no ref= field
# (the contract names that shape separately from the n>=1 summary).
# PIN_ABORT_LINE: conflict Abort's last stdout line names the conflicted
# producer sha and remainder=N, N = commits not landed (conflicted plus
# any after it).
# PIN_SHA: LANDED sha is a git object name that rev-parse's to HEAD
# after a one-commit land (the cherry-pick's new sha, not the producer
# object).
# PIN_COMMITTER: WF_AGENT `Name <addr>` becomes committer name/email;
# repo local user.name is a third identity so forgetting WF_AGENT is a
# red, not a lucky pass.


def _store_snap(path: Path) -> tuple[str, tuple[str, ...]]:
    if not path.exists():
        return ("absent", ())
    if not path.is_dir():
        return ("other", ())
    return ("dir", tuple(sorted(p.name for p in path.iterdir())))


def _live_store_paths() -> list[Path]:
    paths: list[Path] = []
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        paths.append(Path(xdg) / "agentscient" / "dispatch")
    paths.append(Path.home() / ".local" / "state" / "agentscient" / "dispatch")
    snap = REPO.resolve()
    if snap.name == "snapshot":
        job = snap.parent
        if job.parent.name == "dispatch":
            paths.append(job.parent)
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path if not path.exists() else path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _git_out(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"{args} in {cwd}: {proc.stderr}")
    return proc.stdout


class _LandFixture(unittest.TestCase):
    """Scratch HOME + git repo, staged tool copy, live store frozen."""

    def setUp(self):
        self.assertIsNotNone(shutil.which("git"), "INVALID: git not on PATH")
        self._live_before = {str(p): _store_snap(p) for p in _live_store_paths()}
        self._head_before = _git_out(["git", "rev-parse", "HEAD"], REPO).strip()
        self._diff_before = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            check=False,
        ).stdout
        self._dispatch_refs_before = subprocess.run(
            ["git", "for-each-ref", "refs/dispatch"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        self._tmp = tempfile.TemporaryDirectory(prefix="land-lever-")
        root = Path(self._tmp.name)
        self.root = root
        self.home = root / "home"
        self.scratch = root / "scratch"
        self.repo = root / "repo"
        self.home.mkdir()
        self.scratch.mkdir()
        self.store = (
            self.home / ".local" / "state" / "agentscient" / "dispatch"
        )
        self.assertFalse(
            self.store.exists(),
            "plant: isolated store must start absent",
        )
        self.staged = self.scratch / "land.py"
        self._stage_tool_bytes()
        self.conf_path = self.scratch / "lane.conf"
        self.plant_lane_conf()
        self.base = ""
        self.origin: Path | None = None

    def tearDown(self):
        try:
            self.assertEqual(
                {str(p): _store_snap(p) for p in _live_store_paths()},
                self._live_before,
                "live dispatch store mutated",
            )
            self.assertEqual(
                _git_out(["git", "rev-parse", "HEAD"], REPO).strip(),
                self._head_before,
                "real repo HEAD moved",
            )
            diff_after = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=str(REPO),
                capture_output=True,
                check=False,
            ).stdout
            self.assertEqual(
                diff_after,
                self._diff_before,
                "real repo tracked files mutated",
            )
            refs_after = subprocess.run(
                ["git", "for-each-ref", "refs/dispatch"],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                check=False,
            ).stdout
            self.assertEqual(
                refs_after,
                self._dispatch_refs_before,
                "real repo gained a dispatch ref",
            )
            self.assertFalse(
                (self.store / REC).exists()
                and str(self.store).startswith(str(Path.home())),
                "isolated record leaked into live HOME",
            )
        finally:
            self._tmp.cleanup()

    def _stage_tool_bytes(self) -> None:
        if TOOL.is_file():
            data = TOOL.read_bytes()
            self.staged.write_bytes(data)
            landed = self.staged.read_bytes()
            self.assertEqual(landed, data, "copy-tool-bytes did not land intact")
            self.assertEqual(len(landed), len(data))
            self.assertNotEqual(landed, ABSENT_STUB)
        else:
            self.staged.write_bytes(ABSENT_STUB)
            landed = self.staged.read_bytes()
            self.assertEqual(landed, ABSENT_STUB, "stub plant did not land intact")
            self.assertEqual(len(landed), len(ABSENT_STUB))
        self.assertTrue(self.staged.is_file())

    def _lane_conf_text(self, **overrides: object) -> str:
        omit = tuple(overrides.pop("omit", ()) or ())
        keys = {
            "LANE_NAME": "agentscient",
            "TRUNK_BRANCH": "dev",
            "RELEASE_BRANCH": "master",
            "REPO_SLUG": "uscient/agentscient",
            "CHECK_NAME": "ci",
            "WF_AGENT_DEFAULT": AGENT,
            "LANE_AUTHOR": LANE_AUTHOR,
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
        for name, value in overrides.items():
            keys[name] = str(value)
        for name in omit:
            keys.pop(name, None)
        lines = ["# scratch lane conf\n"]
        for name, value in keys.items():
            lines.append(f"{name}='{value}'\n")
        return "".join(lines)

    def plant_lane_conf(self, **overrides: object) -> Path:
        text = self._lane_conf_text(**overrides)
        self._plant_bytes(self.conf_path, text.encode("utf-8"))
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertEqual(landed, text, "conf plant did not land intact")
        return self.conf_path

    def _plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertEqual(len(landed), len(data))

    def git_env(
        self,
        *,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": author_name or REPO_USER,
            "GIT_AUTHOR_EMAIL": author_email or REPO_EMAIL,
            "GIT_COMMITTER_NAME": REPO_USER,
            "GIT_COMMITTER_EMAIL": REPO_EMAIL,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }

    def git(self, *args: str, check: bool = True, cwd: Path | None = None):
        proc = subprocess.run(
            [
                "git",
                "-c",
                f"user.name={REPO_USER}",
                "-c",
                f"user.email={REPO_EMAIL}",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=str(cwd or self.repo),
            env=self.git_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        if check:
            self.assertEqual(
                proc.returncode,
                0,
                f"git {args}: {proc.stderr or proc.stdout}",
            )
        return proc

    def sha(self, rev: str, cwd: Path | None = None) -> str:
        out = self.git("rev-parse", rev, cwd=cwd).stdout.strip()
        self.assertRegex(out, r"^[0-9a-f]{40}$", out)
        return out

    def porcelain(self) -> str:
        return self.git("status", "--porcelain").stdout

    def message(self, rev: str) -> str:
        return self.git("log", "-1", "--format=%B", rev).stdout

    def author(self, rev: str) -> str:
        return self.git("log", "-1", "--format=%an <%ae>", rev).stdout.strip()

    def committer(self, rev: str) -> str:
        return self.git("log", "-1", "--format=%cn <%ce>", rev).stdout.strip()

    def subject(self, rev: str) -> str:
        return self.git("log", "-1", "--format=%s", rev).stdout.strip()

    def parsed_trailers(self, rev: str) -> str:
        msg = self.message(rev)
        proc = subprocess.run(
            ["git", "interpret-trailers", "--parse"],
            input=msg,
            capture_output=True,
            text=True,
            check=False,
            env=self.git_env(),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def range_shas(self, left: str, right: str) -> list[str]:
        out = self.git("rev-list", "--reverse", f"{left}..{right}").stdout
        shas = [ln.strip() for ln in out.splitlines() if ln.strip()]
        return shas

    def env(
        self,
        *,
        agent: str | None = AGENT,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }
        self.assertNotIn("XDG_STATE_HOME", env)
        env["LANE_CONF"] = str(self.conf_path)
        if agent is not None:
            env["WF_AGENT"] = agent
        if extra:
            env.update(extra)
        return env

    def invoke(
        self,
        argv: list[str],
        *,
        agent: str | None = AGENT,
        extra_env: dict[str, str] | None = None,
    ):
        env = self.env(agent=agent, extra=extra_env)
        if agent is None:
            self.assertNotIn("WF_AGENT", env)
        else:
            self.assertEqual(env.get("WF_AGENT"), agent)
        try:
            return subprocess.run(
                [sys.executable, str(self.staged), *argv],
                cwd=str(self.repo),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=RUN_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"land exceeded {RUN_CAP}s: {exc}")

    def land(
        self,
        record: str = REC,
        extra: list[str] | None = None,
        *,
        agent: str | None = AGENT,
        extra_env: dict[str, str] | None = None,
    ):
        argv = [record]
        if extra:
            argv.extend(extra)
        return self.invoke(argv, agent=agent, extra_env=extra_env)

    def combined(self, proc) -> str:
        return f"{proc.stdout or ''}{proc.stderr or ''}"

    def landed_rows(self, stdout: str) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for line in stdout.splitlines():
            match = LANDED_RE.match(line)
            if match:
                rows.append((match.group(1), match.group(2)))
        return rows

    def summary_line(self, stdout: str) -> str | None:
        lines = [ln for ln in stdout.splitlines() if ln.strip()]
        if not lines:
            return None
        last = lines[-1]
        if SUMMARY_RE.match(last) or last == "landed n=0":
            return last
        return None

    def assert_refusal(self, proc, class_name: str) -> None:
        err = proc.stderr or ""
        compact = err.lower().replace("_", "-")
        token = class_name.lower().replace("_", "-")
        spaced = token.replace("-", " ")
        self.assertTrue(
            token in compact or spaced in err.lower(),
            f"refusal class {class_name!r} not named in stderr: {err!r}",
        )
        self.assertEqual(proc.returncode, 2, err)
        self.assertTrue(err.strip(), "refusal was silent")
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        lower = err.lower()
        self.assertIn("expected", lower)
        self.assertIn("found", lower)
        self.assertIn("needed", lower)
        self.assertEqual(
            (proc.stdout or "").strip(),
            "",
            "refusal text belongs on stderr, not stdout",
        )

    def seed_repo(self, *, branch: str = BRANCH, record: str = REC) -> str:
        self.repo.mkdir()
        init = self.git("init", "-b", branch, cwd=self.repo, check=False)
        self.assertEqual(init.returncode, 0, init.stderr)
        self.git("config", "user.name", REPO_USER)
        self.git("config", "user.email", REPO_EMAIL)
        name = self.git("config", "--get", "user.name").stdout.strip()
        email = self.git("config", "--get", "user.email").stdout.strip()
        self.assertEqual(name, REPO_USER)
        self.assertEqual(email, REPO_EMAIL)
        tracked = self.repo / "tracked.txt"
        shared = self.repo / "shared.txt"
        self._plant_bytes(tracked, b"seed\n")
        self._plant_bytes(shared, b"base\n")
        envelope = (
            self.repo / ".dev" / "records" / "dispatches" / f"{record}.json"
        )
        payload = json.dumps(
            {
                "lineage": {"branch": branch},
                "result": {"envelope": {"status": "ok"}},
            },
            indent=2,
        ) + "\n"
        self._plant_bytes(envelope, payload.encode("utf-8"))
        loaded = json.loads(envelope.read_text(encoding="utf-8"))
        self.assertEqual(loaded["lineage"]["branch"], branch)
        self.git("add", "tracked.txt", "shared.txt", str(
            envelope.relative_to(self.repo)
        ))
        self.git("commit", "-m", f"seed envelope\n\n{TRAILER}")
        self.base = self.sha("HEAD")
        head_branch = self.git(
            "symbolic-ref", "--short", "HEAD"
        ).stdout.strip()
        self.assertEqual(head_branch, branch)
        self.assertEqual(self.porcelain(), "")
        return self.base

    def plant_producers(
        self,
        commits: list[tuple[str, str, str, bool]],
        *,
        record: str = REC,
        author_name: str = PRODUCER,
        author_email: str = PRODUCER_EMAIL,
    ) -> list[str]:
        """commits: (relpath, content, subject, with_trailer).

        Point refs/dispatch/<id> at the tip and reset the lineage
        branch back to the seed.
        """
        self.assertTrue(self.base, "INVALID: seed_repo before producers")
        shas: list[str] = []
        for relpath, content, subject, with_trailer in commits:
            path = self.repo / relpath
            self._plant_bytes(path, content.encode("utf-8"))
            self.git("add", relpath)
            body = f"{subject}\n\n{TRAILER}\n" if with_trailer else f"{subject}\n"
            proc = subprocess.run(
                [
                    "git",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "-m",
                    body,
                ],
                cwd=str(self.repo),
                env=self.git_env(
                    author_name=author_name,
                    author_email=author_email,
                ),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            sha = self.sha("HEAD")
            self.assertEqual(
                self.author(sha), f"{author_name} <{author_email}>",
            )
            trailers = self.parsed_trailers(sha)
            if with_trailer:
                self.assertIn("Source:", trailers)
            else:
                self.assertEqual(trailers.strip(), "")
            shas.append(sha)
        tip = self.sha("HEAD")
        self.git("update-ref", f"refs/dispatch/{record}", tip)
        self.git("reset", "--hard", self.base)
        self.assertEqual(self.sha(f"refs/dispatch/{record}"), tip)
        self.assertEqual(self.sha("HEAD"), self.base)
        self.assertNotEqual(tip, self.base)
        for sha in shas:
            probe = self.git("cat-file", "-e", sha, check=False)
            self.assertEqual(
                probe.returncode,
                0,
                f"INVALID: producer {sha} not reachable",
            )
        return shas

    def plant_record(self, *, exit_code: str = "0", record: str = REC) -> Path:
        path = self.store / record
        path.mkdir(parents=True)
        exit_path = path / "exit"
        data = f"{exit_code}\n".encode("utf-8")
        self._plant_bytes(exit_path, data)
        self.assertTrue(path.is_dir(), "INVALID: record dir plant did not land")
        self.assertEqual(exit_path.read_bytes(), data)
        self.assertNotEqual(
            self.store.resolve(),
            (Path.home() / ".local" / "state" / "agentscient" / "dispatch"),
        )
        return path

    def ready(self, *, producers: int = 1) -> list[str]:
        self.seed_repo()
        commits: list[tuple[str, str, str, bool]] = []
        for i in range(producers):
            commits.append(
                (f"landed-{i}.txt", f"body-{i}\n", f"producer-{i}", True)
            )
        if producers == 1:
            commits = [("landed.txt", "landed-body\n", SUBJECT, True)]
        shas = self.plant_producers(commits)
        self.plant_record()
        self.assertEqual(self.porcelain(), "")
        return shas

    def plant_bare_origin(self) -> str:
        origin = self.root / "origin.git"
        origin.mkdir()
        init = subprocess.run(
            ["git", "init", "--bare", "-b", BRANCH],
            cwd=str(origin),
            env=self.git_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(init.returncode, 0, init.stderr)
        self.origin = origin
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "origin", f"{BRANCH}:{BRANCH}")
        remote = self.git(
            "rev-parse", BRANCH, cwd=origin
        ).stdout.strip()
        self.assertEqual(remote, self.sha("HEAD"))
        return remote

    def origin_sha(self) -> str:
        self.assertIsNotNone(self.origin, "INVALID: origin not planted")
        return self.git("rev-parse", BRANCH, cwd=self.origin).stdout.strip()


class ToolPresence(_LandFixture):
    """Missing tool file counts once."""

    def test_the_tool_file_is_present(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")


class HappyPath(_LandFixture):
    """1. One producer commit lands: LANDED line, n=1 summary, exit 0."""

    def test_one_producer_commit_lands_verbatim_with_author_and_committer(self):
        producers = self.ready()
        self.assertEqual(len(producers), 1)
        producer = producers[0]
        original = self.message(producer)
        self.assertIn(TRAILER, original)
        self.assertNotIn("cherry picked from commit", original)
        proc = self.land()
        stdout = proc.stdout or ""
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        rows = self.landed_rows(stdout)
        self.assertEqual(len(rows), 1, stdout)
        sha, subject = rows[0]
        self.assertEqual(subject, SUBJECT)
        self.assertEqual(self.sha(sha), self.sha("HEAD"))
        self.assertEqual(
            self.summary_line(stdout),
            f"landed n=1 ref={REF}",
            stdout,
        )
        self.assertEqual(self.message("HEAD"), original)
        self.assertNotIn("cherry picked from commit", self.message("HEAD"))
        self.assertIn("Source:", original)
        self.assertIn("Co-Authored-By:", original)
        self.assertIn(CO_AUTHOR, original)
        self.assertEqual(self.author("HEAD"), LANE_AUTHOR)
        self.assertNotEqual(
            self.author("HEAD"),
            f"{PRODUCER} <{PRODUCER_EMAIL}>",
        )
        self.assertEqual(self.committer("HEAD"), AGENT)
        self.assertNotEqual(
            self.committer("HEAD"),
            f"{REPO_USER} <{REPO_EMAIL}>",
        )
        landed_body = (self.repo / "landed.txt").read_text(encoding="utf-8")
        self.assertEqual(landed_body, "landed-body\n")


class Idempotence(_LandFixture):
    """2. A second run prints landed n=0, exit 0."""

    def test_a_second_run_prints_landed_n0(self):
        self.ready()
        first = self.land()
        self.assertNotIn(
            "landed n=0",
            first.stdout or "",
            f"first run was already n=0: {first.stdout!r}",
        )
        head_after = self.sha("HEAD") if first.returncode == 0 else self.base
        second = self.land()
        stdout = second.stdout or ""
        self.assertEqual(second.returncode, 0, self.combined(second))
        self.assertEqual(
            self.summary_line(stdout),
            "landed n=0",
            stdout,
        )
        if first.returncode == 0:
            self.assertEqual(self.sha("HEAD"), head_after)


class EmptyRange(_LandFixture):
    """Nothing to land (HEAD..ref empty) is n=0, not an error."""

    def test_empty_range_prints_landed_n0(self):
        self.seed_repo()
        self.git("update-ref", REF, self.sha("HEAD"))
        self.assertEqual(self.sha(REF), self.sha("HEAD"))
        self.assertEqual(self.range_shas("HEAD", REF), [])
        self.plant_record()
        proc = self.land()
        stdout = proc.stdout or ""
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(self.summary_line(stdout), "landed n=0", stdout)
        self.assertEqual(self.sha("HEAD"), self.base)


class IdentityRefusal(_LandFixture):
    """identity: WF_AGENT unset or malformed, checked first."""

    def test_unset_wf_agent_refuses_identity_before_anything_else(self):
        self.seed_repo()
        self.assertFalse(self.store.exists(), "plant: no record dir")
        proc = self.land(agent=None)
        self.assert_refusal(proc, "identity")
        err = (proc.stderr or "").lower()
        self.assertNotIn("record", err.split(":", 1)[0])

    def test_malformed_wf_agent_refuses_identity(self):
        self.ready()
        proc = self.land(agent=MALFORMED_AGENT)
        self.assert_refusal(proc, "identity")
        self.assertEqual(self.sha("HEAD"), self.base)


class RecordRefusal(_LandFixture):
    """record: no record directory named RECORD_ID in the store."""

    def test_missing_record_directory_refuses_record(self):
        self.seed_repo()
        self.plant_producers([("landed.txt", "x\n", SUBJECT, True)])
        self.assertFalse(self.store.exists(), "plant: store dir absent")
        proc = self.land()
        self.assert_refusal(proc, "record")
        self.assertEqual(self.sha("HEAD"), self.base)


class ExitStatusRefusal(_LandFixture):
    """exit-status: exit file missing or nonzero — 137 is the briefed case."""

    def test_nonzero_exit_file_refuses_exit_status(self):
        self.seed_repo()
        self.plant_producers([("landed.txt", "x\n", SUBJECT, True)])
        self.plant_record(exit_code="137")
        planted = (self.store / REC / "exit").read_text(encoding="utf-8")
        self.assertEqual(planted.strip(), "137")
        self.assertNotEqual(planted.strip(), "0")
        proc = self.land()
        self.assert_refusal(proc, "exit-status")
        self.assertEqual(self.sha("HEAD"), self.base)


class RefRefusal(_LandFixture):
    """ref: record present, refs/dispatch/RECORD_ID does not resolve."""

    def test_absent_dispatch_ref_refuses_ref(self):
        self.seed_repo()
        self.plant_record()
        missing = self.git("rev-parse", "--verify", REF, check=False)
        self.assertNotEqual(missing.returncode, 0, "plant: ref must be absent")
        proc = self.land()
        self.assert_refusal(proc, "ref")
        self.assertEqual(self.sha("HEAD"), self.base)


class EnvelopeRefusal(_LandFixture):
    """envelope: ref present, envelope absent from the working tree."""

    def test_absent_envelope_refuses_envelope(self):
        self.seed_repo()
        self.plant_producers([("landed.txt", "x\n", SUBJECT, True)])
        self.plant_record()
        envelope = (
            self.repo / ".dev" / "records" / "dispatches" / f"{REC}.json"
        )
        self.assertTrue(envelope.is_file(), "plant: envelope present before rm")
        envelope.unlink()
        self.assertFalse(envelope.exists(), "plant: envelope still present")
        self.git("add", "-A")
        self.git("commit", "-m", f"drop envelope\n\n{TRAILER}")
        self.assertFalse(envelope.exists())
        self.assertEqual(self.porcelain(), "")
        before = self.sha("HEAD")
        proc = self.land()
        self.assert_refusal(proc, "envelope")
        self.assertEqual(self.sha("HEAD"), before)


class LineageRefusal(_LandFixture):
    """lineage: current branch is not the envelope's lineage.branch."""

    def test_wrong_branch_refuses_lineage(self):
        self.ready()
        self.git("checkout", "-b", "other-lineage")
        current = self.git("symbolic-ref", "--short", "HEAD").stdout.strip()
        self.assertEqual(current, "other-lineage")
        self.assertNotEqual(current, BRANCH)
        proc = self.land()
        self.assert_refusal(proc, "lineage")
        self.assertEqual(self.sha("HEAD"), self.base)


class DirtyRefusal(_LandFixture):
    """dirty: staged or unstaged changes."""

    def test_uncommitted_change_refuses_dirty(self):
        self.ready()
        tracked = self.repo / "tracked.txt"
        before = tracked.read_bytes()
        self._plant_bytes(tracked, b"dirty-uncommitted\n")
        self.assertNotEqual(tracked.read_bytes(), before)
        self.assertTrue(self.porcelain().strip(), "plant: tree still clean")
        proc = self.land()
        self.assert_refusal(proc, "dirty")
        self.assertEqual(self.sha("HEAD"), self.base)


class StaleRefusal(_LandFixture):
    """stale: branch behind origin; --no-fetch still refuses."""

    def test_origin_ahead_with_no_fetch_refuses_stale(self):
        self.ready()
        self._plant_bytes(self.repo / "ahead.txt", b"origin-ahead\n")
        self.git("add", "ahead.txt")
        self.git("commit", "-m", f"origin moved on\n\n{TRAILER}")
        ahead = self.sha("HEAD")
        self.assertNotEqual(ahead, self.base)
        self.git("remote", "add", "origin", "https://example.invalid/land.git")
        self.git("update-ref", f"refs/remotes/origin/{BRANCH}", ahead)
        self.git("reset", "--hard", self.base)
        self.assertEqual(self.sha("HEAD"), self.base)
        self.assertEqual(self.sha(f"origin/{BRANCH}"), ahead)
        count = self.git(
            "rev-list", "--count", f"HEAD..origin/{BRANCH}"
        ).stdout.strip()
        self.assertGreaterEqual(int(count), 1, "plant: origin is not ahead")
        proc = self.land(extra=["--no-fetch"])
        self.assert_refusal(proc, "stale")
        self.assertEqual(self.sha("HEAD"), self.base)


class AttributionRefusal(_LandFixture):
    """attribution: a commit with no trailer, checked before any pick."""

    def test_commit_without_trailer_refuses_attribution_before_any_pick(self):
        self.seed_repo()
        shas = self.plant_producers(
            [
                ("ok.txt", "ok\n", "has-trailer", True),
                ("bad.txt", "bad\n", "no-trailer", False),
            ]
        )
        self.assertEqual(len(shas), 2)
        self.assertIn("Source:", self.parsed_trailers(shas[0]))
        self.assertEqual(self.parsed_trailers(shas[1]).strip(), "")
        self.plant_record()
        before = self.sha("HEAD")
        proc = self.land()
        self.assert_refusal(proc, "attribution")
        self.assertEqual(self.sha("HEAD"), before)
        self.assertFalse((self.repo / "ok.txt").exists())
        self.assertFalse((self.repo / "bad.txt").exists())
        self.assertEqual(self.porcelain(), "")


class ConflictAbort(_LandFixture):
    """5. Second commit conflicts: exit 3, first kept, tree clean."""

    def test_conflicting_second_commit_aborts_keeping_the_first(self):
        self.seed_repo()
        shas = self.plant_producers(
            [
                ("landed.txt", "first\n", "producer-one", True),
                ("shared.txt", "producer\n", "producer-two", True),
            ]
        )
        self.assertEqual(len(shas), 2)
        first, conflicted = shas
        self._plant_bytes(self.repo / "shared.txt", b"lineage\n")
        self.git("add", "shared.txt")
        self.git("commit", "-m", f"lineage moved shared.txt\n\n{TRAILER}")
        start = self.sha("HEAD")
        self.assertNotEqual(
            (self.repo / "shared.txt").read_bytes(),
            b"producer\n",
        )
        self.assertEqual(len(self.range_shas("HEAD", REF)), 2)
        self.plant_record()
        proc = self.land()
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 3, text)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.porcelain(), "", "abort left a dirty tree")
        cherry = self.repo / ".git" / "CHERRY_PICK_HEAD"
        self.assertFalse(cherry.exists(), "CHERRY_PICK_HEAD remains")
        self.assertTrue(
            (self.repo / "landed.txt").is_file(),
            "first commit was not kept",
        )
        self.assertEqual(
            (self.repo / "landed.txt").read_text(encoding="utf-8"),
            "first\n",
        )
        self.assertEqual(
            (self.repo / "shared.txt").read_text(encoding="utf-8"),
            "lineage\n",
        )
        kept = self.range_shas(start, "HEAD")
        self.assertEqual(len(kept), 1, kept)
        self.assertEqual(self.subject("HEAD"), "producer-one")
        self.assertEqual(self.author("HEAD"), LANE_AUTHOR)
        stdout_lines = [
            ln for ln in (proc.stdout or "").splitlines() if ln.strip()
        ]
        stderr_lines = [
            ln for ln in (proc.stderr or "").splitlines() if ln.strip()
        ]
        last = None
        if stdout_lines:
            last = stdout_lines[-1]
        elif stderr_lines:
            last = stderr_lines[-1]
        self.assertIsNotNone(last, f"abort printed no last line: {text!r}")
        self.assertIn(conflicted, last)
        self.assertRegex(last, r"remainder[=:\s]+1")
        rows = self.landed_rows(proc.stdout or "")
        self.assertTrue(
            any(subj == "producer-one" for _, subj in rows),
            f"first land not reported: {text!r}",
        )
        still = self.git("cat-file", "-e", first, check=False)
        self.assertEqual(still.returncode, 0, "first producer sha lost")


class Push(_LandFixture):
    """6. --push updates origin after n>=1; without it, origin stays."""

    def test_without_push_origin_is_unchanged(self):
        self.ready()
        pre = self.plant_bare_origin()
        proc = self.land()
        stdout = proc.stdout or ""
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(
            self.summary_line(stdout),
            f"landed n=1 ref={REF}",
            stdout,
        )
        self.assertNotEqual(self.sha("HEAD"), self.base)
        self.assertEqual(self.origin_sha(), pre)
        self.assertNotEqual(self.origin_sha(), self.sha("HEAD"))

    def test_push_updates_origin_after_a_successful_land(self):
        self.ready()
        pre = self.plant_bare_origin()
        proc = self.land(extra=["--push"])
        stdout = proc.stdout or ""
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(
            self.summary_line(stdout),
            f"landed n=1 ref={REF}",
            stdout,
        )
        self.assertNotEqual(self.sha("HEAD"), pre)
        self.assertEqual(self.origin_sha(), self.sha("HEAD"))

    def test_push_failure_is_a_finding_and_keeps_the_landing(self):
        self.ready()
        self.git("remote", "add", "origin", "/no/such/land-origin")
        # Adjudicated twice at review: --no-fetch presumes prior fetch
        # evidence, so the last-known origin ref is planted at HEAD; the
        # broken remote then breaks only the push.
        self.git("update-ref", f"refs/remotes/origin/{BRANCH}", "HEAD")
        proc = self.land(extra=["--push", "--no-fetch"])
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotEqual(proc.returncode, 2)
        self.assertNotEqual(proc.returncode, 3)
        self.assertNotEqual(self.sha("HEAD"), self.base)
        self.assertEqual(self.subject("HEAD"), SUBJECT)
        self.assertEqual(
            (self.repo / "landed.txt").read_text(encoding="utf-8"),
            "landed-body\n",
        )


class EnvelopeStatus(_LandFixture):
    def test_invalid_envelope_status_refuses_before_any_pick(self):
        # The live proof: record adec30 carried envelope.status invalid
        # (schema-invalid answer) while its exit read 0.
        self.ready()
        envelope = (
            self.repo / ".dev" / "records" / "dispatches" / f"{REC}.json"
        )
        payload = json.dumps(
            {
                "lineage": {"branch": BRANCH},
                "result": {"envelope": {"status": "invalid"}},
            },
            indent=2,
        ) + "\n"
        self._plant_bytes(envelope, payload.encode("utf-8"))
        self.git("add", str(envelope.relative_to(self.repo)))
        self.git("commit", "-m", f"invalid envelope\n\n{TRAILER}")
        pre = self.sha("HEAD")
        proc = self.land()
        self.assert_refusal(proc, "envelope-status")
        self.assertEqual(self.sha("HEAD"), pre, "nothing may land")


class FreshnessThreeWay(_LandFixture):
    def test_no_fetch_with_remote_but_no_ref_refuses_stale(self):
        self.ready()
        self.git("remote", "add", "origin", "/no/such/land-origin")
        proc = self.land(extra=["--no-fetch"])
        self.assert_refusal(proc, "stale")

    def test_upstream_without_the_branch_is_fresh_evidence(self):
        self.ready()
        bare = self.scratch / "fresh-origin.git"
        subprocess.run(
            ["git", "init", "--bare", "--quiet", str(bare)],
            check=True, capture_output=True, text=True,
        )
        self.git("remote", "add", "origin", str(bare))
        proc = self.land()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertIn("landed n=1", proc.stdout or "")

    def test_unreachable_remote_refusal_is_one_line(self):
        self.ready()
        self.git("remote", "add", "origin", "/no/such/land-origin")
        proc = self.land()
        self.assert_refusal(proc, "stale")


class CollectedTrip(_LandFixture):
    """A tripped dispatch whose tree was collected lands; others refuse.

    Defect 12: exit-status and envelope-status accept a result.collected
    mark whose verify.exit is 0 and whose head is the dispatch ref.
    Uncollected trips, a mismatched collected head, and a failing
    verify still refuse. Existing ExitStatusRefusal and EnvelopeStatus
    cases stay the pin for records with no collection.
    """

    COLLECTED_AT = "2026-09-03T22:56:29Z"
    VERIFY_CMD = "test -f landed.txt"

    def collected_payload(
        self,
        *,
        head: str,
        verify_exit,
        status: str = "invalid",
        reason: str | None = "tripped before commit",
    ) -> dict:
        return {
            "lineage": {"branch": BRANCH},
            "result": {
                "envelope": {"status": status},
                "collected": {
                    "at": self.COLLECTED_AT,
                    "by": AGENT,
                    "head": head,
                    "verify": {"command": self.VERIFY_CMD, "exit": verify_exit},
                    "reason": reason,
                },
            },
        }

    def commit_working_tree_envelope(self, payload: dict) -> Path:
        envelope = (
            self.repo / ".dev" / "records" / "dispatches" / f"{REC}.json"
        )
        data = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
        self._plant_bytes(envelope, data)
        loaded = json.loads(envelope.read_text(encoding="utf-8"))
        self.assertEqual(loaded, json.loads(data.decode("utf-8")))
        self.git("add", str(envelope.relative_to(self.repo)))
        self.git("commit", "-m", f"plant collected envelope\n\n{TRAILER}")
        self.assertEqual(self.porcelain(), "")
        self.assertTrue(envelope.is_file())
        return envelope

    def seed_tripped_producers(self) -> list[str]:
        self.seed_repo()
        shas = self.plant_producers(
            [("landed.txt", "landed-body\n", SUBJECT, True)]
        )
        self.plant_record(exit_code="137")
        planted = (self.store / REC / "exit").read_text(encoding="utf-8")
        self.assertEqual(planted.strip(), "137")
        self.assertNotEqual(planted.strip(), "0")
        self.assertEqual(len(shas), 1)
        return shas

    def test_a_tripped_record_with_a_collected_result_lands(self):
        producers = self.seed_tripped_producers()
        producer = producers[0]
        original = self.message(producer)
        self.assertIn(TRAILER, original)
        self.assertNotIn("cherry picked from commit", original)
        tip = self.sha(REF)
        self.assertEqual(tip, producer)
        envelope = self.commit_working_tree_envelope(
            self.collected_payload(head=tip, verify_exit=0)
        )
        loaded = json.loads(envelope.read_text(encoding="utf-8"))
        collected = loaded["result"]["collected"]
        self.assertEqual(collected["verify"]["exit"], 0)
        self.assertEqual(collected["head"], tip)
        self.assertEqual(loaded["result"]["envelope"]["status"], "invalid")
        self.assertEqual(self.sha(REF), tip)

        proc = self.land()
        stdout = proc.stdout or ""
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        rows = self.landed_rows(stdout)
        self.assertEqual(len(rows), 1, stdout)
        sha, subject = rows[0]
        self.assertEqual(subject, SUBJECT)
        self.assertEqual(self.sha(sha), self.sha("HEAD"))
        self.assertEqual(self.message("HEAD"), original)
        self.assertNotIn("cherry picked from commit", self.message("HEAD"))

    def test_a_tripped_record_without_a_collection_names_the_collect_verb(self):
        self.seed_tripped_producers()
        envelope = (
            self.repo / ".dev" / "records" / "dispatches" / f"{REC}.json"
        )
        loaded = json.loads(envelope.read_text(encoding="utf-8"))
        self.assertNotIn("collected", loaded.get("result", {}))
        proc = self.land()
        self.assert_refusal(proc, "exit-status")
        err = proc.stderr or ""
        self.assertIn("launch.py collect", err)
        self.assertEqual(self.sha("HEAD"), self.base)

    def test_a_collected_head_that_is_not_the_ref_refuses_ref(self):
        self.seed_tripped_producers()
        tip = self.sha(REF)
        wrong = self.base
        self.assertNotEqual(wrong, tip)
        envelope = self.commit_working_tree_envelope(
            self.collected_payload(head=wrong, verify_exit=0)
        )
        loaded = json.loads(envelope.read_text(encoding="utf-8"))
        self.assertEqual(loaded["result"]["collected"]["head"], wrong)
        self.assertEqual(loaded["result"]["collected"]["verify"]["exit"], 0)
        self.assertEqual(self.sha(REF), tip)
        pre = self.sha("HEAD")
        proc = self.land()
        self.assert_refusal(proc, "ref")
        err = proc.stderr or ""
        self.assertIn(wrong, err)
        self.assertIn(tip, err)
        self.assertEqual(self.sha("HEAD"), pre)
        self.assertFalse((self.repo / "landed.txt").exists())

    def test_a_collected_result_with_a_failing_verify_still_refuses(self):
        self.seed_tripped_producers()
        tip = self.sha(REF)
        envelope = self.commit_working_tree_envelope(
            self.collected_payload(head=tip, verify_exit=1)
        )
        loaded = json.loads(envelope.read_text(encoding="utf-8"))
        self.assertEqual(loaded["result"]["collected"]["head"], tip)
        self.assertEqual(loaded["result"]["collected"]["verify"]["exit"], 1)
        self.assertNotEqual(loaded["result"]["collected"]["verify"]["exit"], 0)
        pre = self.sha("HEAD")
        proc = self.land()
        self.assert_refusal(proc, "exit-status")
        err = (proc.stderr or "").lower()
        self.assertRegex(err, r"collect|verify")
        self.assertEqual(self.sha("HEAD"), pre)
        self.assertEqual(self.landed_rows(proc.stdout or ""), [])
        self.assertFalse((self.repo / "landed.txt").exists())

    def test_a_collected_result_with_json_false_verify_exit_is_not_green(self):
        """Security finding 5: JSON false == 0 must not satisfy
        verify.exit is 0."""
        self.seed_tripped_producers()
        tip = self.sha(REF)
        envelope = self.commit_working_tree_envelope(
            self.collected_payload(head=tip, verify_exit=False)
        )
        loaded = json.loads(envelope.read_text(encoding="utf-8"))
        exit_value = loaded["result"]["collected"]["verify"]["exit"]
        self.assertIs(exit_value, False)
        self.assertEqual(exit_value, 0)
        raw = envelope.read_text(encoding="utf-8")
        self.assertRegex(raw, r'"exit":\s*false')
        self.assertNotRegex(raw, r'"exit":\s*0\b')
        pre = self.sha("HEAD")
        proc = self.land()
        self.assertNotEqual(
            proc.returncode, 0,
            "JSON false must not land as a verified collection: "
            f"{self.combined(proc)!r}",
        )
        self.assert_refusal(proc, "exit-status")
        self.assertEqual(self.sha("HEAD"), pre)
        self.assertEqual(self.landed_rows(proc.stdout or ""), [])
        self.assertFalse((self.repo / "landed.txt").exists())


class EnvelopeStatusNamesCollect(_LandFixture):
    """Adversarial finding 5: envelope-status needed text names
    launch.py collect, never a by-hand adjudication."""

    def test_an_invalid_envelope_with_exit_zero_names_the_collect_verb(self):
        self.ready()
        envelope = (
            self.repo / ".dev" / "records" / "dispatches" / f"{REC}.json"
        )
        payload = json.dumps(
            {
                "lineage": {"branch": BRANCH},
                "result": {"envelope": {"status": "invalid"}},
            },
            indent=2,
        ) + "\n"
        self._plant_bytes(envelope, payload.encode("utf-8"))
        loaded = json.loads(envelope.read_text(encoding="utf-8"))
        self.assertEqual(loaded["result"]["envelope"]["status"], "invalid")
        self.assertNotIn("collected", loaded.get("result", {}))
        exit_text = (self.store / REC / "exit").read_text(encoding="utf-8")
        self.assertEqual(exit_text.strip(), "0")
        self.git("add", str(envelope.relative_to(self.repo)))
        self.git("commit", "-m", f"invalid envelope names collect\n\n{TRAILER}")
        pre = self.sha("HEAD")
        proc = self.land()
        self.assert_refusal(proc, "envelope-status")
        err = proc.stderr or ""
        self.assertIn("launch.py collect", err)
        self.assertNotIn("adjudicate the rejected dispatch by hand", err)
        self.assertEqual(self.sha("HEAD"), pre, "nothing may land")


class LaneNameSelectsStore(_LandFixture):
    """LANE_NAME from the conf selects the store under HOME.

    Unit 1 contract: every state-root reader reads LANE_NAME through
    the reader. Tests plant LANE_CONF and never write the tracked file.
    """

    def test_lane_name_from_conf_selects_the_store(self):
        self.seed_repo()
        self.plant_producers(
            [("landed.txt", "landed-body\n", SUBJECT, True)]
        )
        conf = self.scratch / "lane.conf"
        text = (
            "# scratch lane conf\n"
            "LANE_NAME='lanex'\n"
            "TRUNK_BRANCH='dev'\n"
            "RELEASE_BRANCH='master'\n"
            "REPO_SLUG='uscient/agentscient'\n"
            "CHECK_NAME='ci'\n"
            "WF_AGENT_DEFAULT='Conf Agent <conf@example.invalid>'\n"
            f"LANE_AUTHOR='{LANE_AUTHOR}'\n"
            "MODEL_GROK='model-grok'\n"
            "MODEL_CODEX='model-codex'\n"
            "MODEL_CLAUDE_READ='model-claude-read'\n"
            "MODEL_CLAUDE_PLAN='model-claude-plan'\n"
            "EFFORT_GROK='high'\n"
            "EFFORT_CODEX='high'\n"
            "EFFORT_CLAUDE='high'\n"
            "WALL_DEFAULT='900'\n"
            "SCOPE_CAP='1024'\n"
        )
        self._plant_bytes(conf, text.encode("utf-8"))
        landed = conf.read_text(encoding="utf-8")
        self.assertIn("LANE_NAME='lanex'", landed)
        store = self.home / ".local" / "state" / "lanex" / "dispatch"
        rec_dir = store / REC
        rec_dir.mkdir(parents=True)
        self._plant_bytes(rec_dir / "exit", b"0\n")
        self.assertTrue((store / REC / "exit").is_file())
        self.assertFalse(
            (self.store / REC).exists(),
            "plant: agentscient record dir must be absent",
        )
        proc = self.land(extra_env={"LANE_CONF": str(conf)})
        stdout = proc.stdout or ""
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(
            self.summary_line(stdout),
            f"landed n=1 ref={REF}",
            stdout,
        )
        self.assertEqual(
            (self.repo / "landed.txt").read_text(encoding="utf-8"),
            "landed-body\n",
        )
        self.assertEqual(self.author("HEAD"), LANE_AUTHOR)


class LaneAuthor(_LandFixture):
    """LANE_AUTHOR is the author of every landed commit. The worker's
    message, including Source and Co-Authored-By trailers, is kept
    verbatim. A commit already authored as LANE_AUTHOR is landed
    unchanged. Missing LANE_AUTHOR or LANE_NAME is conf-key before any
    pick.
    """

    def test_already_correct_author_is_landed_unchanged(self):
        self.assertNotEqual(LANE_AUTHOR, f"{PRODUCER} <{PRODUCER_EMAIL}>")
        self.seed_repo()
        shas = self.plant_producers(
            [("landed.txt", "landed-body\n", SUBJECT, True)],
            author_name=LANE_AUTHOR_NAME,
            author_email=LANE_AUTHOR_EMAIL,
        )
        self.assertEqual(len(shas), 1)
        producer = shas[0]
        self.assertEqual(self.author(producer), LANE_AUTHOR)
        original = self.message(producer)
        self.assertIn("Source:", original)
        self.assertIn("Co-Authored-By:", original)
        self.plant_record()
        proc = self.land()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(self.message("HEAD"), original)
        self.assertEqual(self.author("HEAD"), LANE_AUTHOR)

    def test_missing_lane_author_refuses_conf_key_before_any_pick(self):
        self.plant_lane_conf(omit=("LANE_AUTHOR",))
        planted = self.conf_path.read_text(encoding="utf-8")
        self.assertNotIn("LANE_AUTHOR=", planted)
        self.ready()
        pre = self.sha("HEAD")
        proc = self.land()
        self.assert_refusal(proc, "conf-key")
        err = proc.stderr or ""
        self.assertIn("LANE_AUTHOR", err)
        self.assertIn(str(self.conf_path), err)
        self.assertEqual(self.sha("HEAD"), pre, "nothing may land")
        self.assertEqual(self.landed_rows(proc.stdout or ""), [])

    def test_missing_lane_name_refuses_conf_key_before_any_pick(self):
        self.plant_lane_conf(omit=("LANE_NAME",))
        planted = self.conf_path.read_text(encoding="utf-8")
        self.assertNotIn("LANE_NAME=", planted)
        self.ready()
        pre = self.sha("HEAD")
        proc = self.land()
        self.assert_refusal(proc, "conf-key")
        err = proc.stderr or ""
        self.assertIn("LANE_NAME", err)
        self.assertIn(str(self.conf_path), err)
        self.assertEqual(self.sha("HEAD"), pre, "nothing may land")
        self.assertEqual(self.landed_rows(proc.stdout or ""), [])


if __name__ == "__main__":
    unittest.main()

