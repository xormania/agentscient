"""Onboard-lever acceptance tests, written from the contracts.

Contracts (only): `ops/conductor/onboard-lever.md` and the inherited
`ops/conductor/instrument-conventions.md`. The tool
`ops/conductor/tools/onboard.py` is the subject and is not read here.
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
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "onboard.py"

BRANCH = "onboard-lineage"
REPO_USER = "Repo Config"
REPO_EMAIL = "repo-config@example.invalid"
RUN_CAP = 30

# Contract table, verbatim one-liners, em dash as written there.
LAW = (
    ("AGENTS.md", "the operating contract"),
    ("CONTRIB.md", "naming, PR bodies, fix commits, the review wire"),
    (
        "ops/conductor/instrument-conventions.md",
        "the lane's base contract: wire, identity, exits",
    ),
    (
        "ops/conductor/stack.md",
        "the stack: layers, incumbents, open seats",
    ),
    ("ops/conductor/coverage-zones.md", "what gates what"),
)
EM = "—"

# PIN_REGISTER_SHAPE: one labelled line; stub counts and blocked ids
# survive compaction.
# Adjudicated at reconciliation: the sibling is a landed instrument
# whose report is deterministic JSON by its own contract; the stub
# speaks that shape, not an invented one.
REGISTER_STDOUT = (
    '{"blocked":[{"blocked_on":"a PR","id":"D-OPS-9"}],'
    '"counts":{"proposed":3,"ratified":8,"rejected":0,"superseded":1},'
    '"oldest_open":[]}\n'
)
# PIN_LEDGER_SHAPE: the sibling's status line plus an open-grant count.
HAND_STDOUT = (
    "status: open=2, settled=4\nrecurrence by class:\n  other=2\n"
    "debt: open=2, settled-unverified=0, settled-late=0\n"
)
PR_NUMBER = "42"
PR_TITLE = "Onboard the lever"
RUNNING_ID = "20260901T120000Z-run-alpha"
CLOSED_OLD = "20260901T100000Z-closed-old"
CLOSED_NEW = "20260901T110000Z-closed-new"
CLOSED_NEW_EXIT = "7"
AAR_OLD = "AAR-2026-08-01.md"
AAR_NEW = "AAR-2026-09-02.md"
AAR_BARE = "AAR-2026-09-01.md"
DECOY_NAME = "note.md"
CAL_NEW = "NEW_AAR_CALIBRATION_UNIQUE_aa31"
CAL_OLD = "OLD_AAR_CALIBRATION_UNIQUE_aa30"
CAL_BODY = "CALIBRATION_BODY_UNIQUE_i008_7f3c"
AFTER_BODY = "AFTER_SECTION_UNIQUE_9a1b"
DECOY_CAL = "DECOY_CALIBRATION_MUST_NOT_APPEAR"
GH_FAIL = "GH_STUB_FAIL_MARKER: pr list failed"
SIBLING_REFUSAL = (
    "id-shape: expected D-WO-N; found bad-id; needed a well-formed id"
)

ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)

# PIN_SECTION_HEADERS: the contract writes `== law`, `== state`,
# `== thread` and prints them in that order on stdout.
# PIN_OK_ABSENT: `OK <path> — <one-liner>` / `ABSENT <path> — <one-liner>`.
# PIN_FINAL: last non-empty stdout line is `brief complete` or
# `brief complete, N absence(s)` with the (s) as written.
# PIN_AAR_ORDER: newest AAR-*.md by filename, not mtime.
# PIN_CALIBRATION_SECTION: text under a heading containing
# `calibration`, not the following heading's body.
# PIN_STORE: record dir named by id; running = no `exit` file; closed
# `exit` file holds the code; newest closed by id filename order.
# PIN_ABSENT_STORE: naming the missing store is a measurement, not an
# unmeasured source — exit 0 when law and the other sources are OK.
# PIN_GH: `gh pr list --state open` (not `pr checks`); number and title
# each on the prs line.


def _store_snap(path: Path) -> tuple[str, tuple[str, ...]]:
    if not path.exists():
        return ("absent", ())
    if not path.is_dir():
        return ("other", ())
    return ("dir", tuple(sorted(p.name for p in path.iterdir())))


# A launcher's job directory: <stamp>-<stage>-<harness>-<hash>. The CI
# runners share the operator's live store, so a dispatch launched while a
# test runs adds one of these; the guard below tolerates exactly that
# addition and nothing else (a store file the tool under test wrote to
# the live path is still a mutation).
_JOB_DIR = re.compile(r"^\d{8}T\d{6}Z-[a-z-]+-[a-z]+-[0-9a-f]{6}$")


def _without_new_job_dirs(before, after):
    """Drop from ``after`` the job directories absent from ``before``."""
    kept = {}
    for key, (kind, names) in after.items():
        if kind == "dir" and key in before and before[key][0] == "dir":
            previous = set(before[key][1])
            names = tuple(n for n in names if n in previous or not _JOB_DIR.match(n))
        kept[key] = (kind, names)
    return kept


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


def _tree_files(root: Path) -> tuple[str, ...]:
    if not root.exists():
        return ()
    names: list[str] = []
    for path in root.rglob("*"):
        if path.is_file():
            names.append(str(path.relative_to(root)))
    return tuple(sorted(names))


def _aar_with_calibration(body: str, after: str | None = None) -> str:
    text = f"# After-action\n\n## The calibration clause\n\n{body}\n"
    if after is not None:
        text += f"\n## After\n\n{after}\n"
    return text


def _aar_without_calibration() -> str:
    return "# After-action\n\n## Failures\n\nno clause here\n"


def ok_line(path: str, one_liner: str) -> str:
    return f"OK {path} {EM} {one_liner}"


def absent_line(path: str, one_liner: str) -> str:
    return f"ABSENT {path} {EM} {one_liner}"


class _OnboardFixture(unittest.TestCase):
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
        self._tmp = tempfile.TemporaryDirectory(prefix="onboard-lever-")
        root = Path(self._tmp.name)
        self.root = root
        self.home = root / "home"
        self.scratch = root / "scratch"
        self.bin = root / "bin"
        self.repo = root / "repo"
        self.xdg = root / "xdg"
        for path in (self.home, self.scratch, self.bin, self.repo, self.xdg):
            path.mkdir()
        self.store = self.home / ".local" / "state" / "agentscient" / "dispatch"
        self.xdg_store = self.xdg / "agentscient" / "dispatch"
        self.assertFalse(
            self.store.exists(),
            "plant: isolated store must start absent",
        )
        self.gh = self.bin / "gh"
        self.argv_log = self.scratch / "gh-argv.jsonl"
        self.staged = self.scratch / "onboard.py"
        self._stage_tool_bytes()
        self.assertFalse(self.argv_log.exists(), "plant: argv log must start absent")
        self.assertFalse(self.gh.exists(), "plant: gh stub is not planted yet")

    def tearDown(self):
        try:
            self.assertEqual(
                _without_new_job_dirs(
                    self._live_before,
                    {str(p): _store_snap(p) for p in _live_store_paths()},
                ),
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

    def _plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertEqual(len(landed), len(data))

    def _make_executable(self, path: Path) -> None:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.assertTrue(os.access(path, os.X_OK), f"not executable: {path}")

    def git_env(self) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": REPO_USER,
            "GIT_AUTHOR_EMAIL": REPO_EMAIL,
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

    def ensure_git(self) -> None:
        if (self.repo / ".git").exists():
            return
        init = self.git("init", "-b", BRANCH, cwd=self.repo, check=False)
        self.assertEqual(init.returncode, 0, init.stderr)
        self.git("config", "user.name", REPO_USER)
        self.git("config", "user.email", REPO_EMAIL)
        name = self.git("config", "--get", "user.name").stdout.strip()
        email = self.git("config", "--get", "user.email").stdout.strip()
        self.assertEqual(name, REPO_USER)
        self.assertEqual(email, REPO_EMAIL)
        seed = self.repo / "README"
        self._plant_bytes(seed, b"scratch onboard repo\n")
        self.git("add", "README")
        self.git("commit", "-m", "seed\n")
        head_branch = self.git("symbolic-ref", "--short", "HEAD").stdout.strip()
        self.assertEqual(head_branch, BRANCH)
        self.assertEqual(self.git("status", "--porcelain").stdout, "")

    def plant_law(self, *, omit: tuple[str, ...] = (), empty: tuple[str, ...] = ()):
        omit_set = set(omit)
        empty_set = set(empty)
        for path, _one in LAW:
            dest = self.repo / path
            if path in omit_set:
                self.assertFalse(dest.exists(), f"omit did not leave {path} absent")
                continue
            if path in empty_set:
                self._plant_bytes(dest, b"")
                self.assertEqual(dest.stat().st_size, 0, f"{path} is not empty")
                continue
            payload = f"law body for {path}\n".encode()
            self._plant_bytes(dest, payload)
            self.assertGreater(dest.stat().st_size, 0, f"{path} stayed empty")
        for path in omit:
            self.assertFalse(
                (self.repo / path).exists(),
                f"INVALID: omitted law file landed: {path}",
            )

    def _plant_py_stub(
        self,
        path: Path,
        *,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
    ) -> None:
        body = (
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"sys.stdout.write({stdout!r})\n"
            f"sys.stderr.write({stderr!r})\n"
            f"raise SystemExit({exit_code})\n"
        )
        self._plant_bytes(path, body.encode("utf-8"))
        self._make_executable(path)

    def plant_siblings(
        self,
        *,
        register_stdout: str = REGISTER_STDOUT,
        register_stderr: str = "",
        register_exit: int = 0,
        ledger_stdout: str = HAND_STDOUT,
        ledger_stderr: str = "",
        ledger_exit: int = 0,
    ) -> None:
        locations = (
            self.scratch,
            self.repo / "ops" / "conductor" / "tools",
        )
        for folder in locations:
            folder.mkdir(parents=True, exist_ok=True)
            self._plant_py_stub(
                folder / "decisions.py",
                stdout=register_stdout,
                stderr=register_stderr,
                exit_code=register_exit,
            )
            self._plant_py_stub(
                folder / "hand.py",
                stdout=ledger_stdout,
                stderr=ledger_stderr,
                exit_code=ledger_exit,
            )

    def _gh_preamble(self) -> str:
        return (
            "#!/usr/bin/env python3\n"
            "from __future__ import annotations\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            f"log = Path({str(self.argv_log)!r})\n"
            "prev = log.read_text(encoding='utf-8') if log.is_file() else ''\n"
            "log.write_text(prev + json.dumps(sys.argv[1:]) + '\\n', encoding='utf-8')\n"
        )

    def plant_gh(
        self,
        *,
        number: str = PR_NUMBER,
        title: str = PR_TITLE,
        exit_code: int = 0,
        stderr: str = "",
        rows: list | None = None,
    ) -> None:
        table = f"{number}\t{title}\t{BRANCH}\tOPEN\n"
        payload = json.dumps(
            rows if rows is not None
            else [{"number": int(number), "title": title}]
        )
        body = (
            self._gh_preamble()
            + f"stderr_text = {stderr!r}\n"
            + "sys.stderr.write(stderr_text)\n"
            + f"code = {exit_code}\n"
            + "if code != 0:\n"
            + "    raise SystemExit(code)\n"
            + "argv = sys.argv[1:]\n"
            + "joined = ' '.join(argv)\n"
            + "if '--json' in joined or any(a.startswith('--json') for a in argv):\n"
            + f"    sys.stdout.write({payload!r} + '\\n')\n"
            + "else:\n"
            + f"    sys.stdout.write({table!r})\n"
            + "raise SystemExit(0)\n"
        )
        self._plant_bytes(self.gh, body.encode("utf-8"))
        self._make_executable(self.gh)
        self.assertEqual(
            self.gh.read_text(encoding="utf-8"),
            body,
            "gh stub plant did not land intact",
        )

    def plant_dispatch(
        self,
        *,
        store: Path | None = None,
        running: tuple[str, ...] = (),
        closed: tuple[tuple[str, str], ...] = (),
    ) -> Path:
        dest = store if store is not None else self.store
        dest.mkdir(parents=True, exist_ok=True)
        self.assertTrue(dest.is_dir(), "INVALID: dispatch store plant did not land")
        for rec_id in running:
            rec = dest / rec_id
            rec.mkdir(parents=True)
            marker = rec / "launched"
            self._plant_bytes(marker, b"running\n")
            self.assertFalse(
                (rec / "exit").exists(),
                f"INVALID: running record has an exit file: {rec_id}",
            )
        for rec_id, code in closed:
            rec = dest / rec_id
            rec.mkdir(parents=True)
            self._plant_bytes(rec / "exit", f"{code}\n".encode("utf-8"))
            self.assertTrue((rec / "exit").is_file())
        return dest

    def plant_aars(self, files: dict[str, str], *, mtimes: dict[str, int] | None = None):
        folder = self.repo / "ops" / "conductor"
        folder.mkdir(parents=True, exist_ok=True)
        for name, body in files.items():
            path = folder / name
            self._plant_bytes(path, body.encode("utf-8"))
        if mtimes:
            for name, stamp in mtimes.items():
                path = folder / name
                os.utime(path, (stamp, stamp))
                self.assertAlmostEqual(
                    path.stat().st_mtime, stamp, delta=2, msg=str(path)
                )

    def commit_plant(self) -> None:
        self.git("add", "-A")
        porcelain = self.git("status", "--porcelain").stdout
        if porcelain.strip():
            self.git("commit", "-m", "plant\n")

    def ready(
        self,
        *,
        omit_law: tuple[str, ...] = (),
        empty_law: tuple[str, ...] = (),
        aars: dict[str, str] | None = None,
        aar_mtimes: dict[str, int] | None = None,
        running: tuple[str, ...] | None = (RUNNING_ID,),
        closed: tuple[tuple[str, str], ...] | None = (
            (CLOSED_OLD, "0"),
            (CLOSED_NEW, CLOSED_NEW_EXIT),
        ),
        store: Path | None = None,
        plant_store: bool = True,
        gh_exit: int = 0,
        gh_stderr: str = "",
        register_stderr: str = "",
        register_exit: int = 0,
        ledger_stderr: str = "",
        ledger_exit: int = 0,
    ) -> None:
        self.ensure_git()
        self.plant_law(omit=omit_law, empty=empty_law)
        self.plant_siblings(
            register_stderr=register_stderr,
            register_exit=register_exit,
            ledger_stderr=ledger_stderr,
            ledger_exit=ledger_exit,
        )
        self.plant_gh(exit_code=gh_exit, stderr=gh_stderr)
        handwork = self.store.parent / "handwork.db"
        handwork.parent.mkdir(parents=True, exist_ok=True)
        if not handwork.exists():
            self._plant_bytes(handwork, b"")
        if plant_store:
            run = () if running is None else running
            close = () if closed is None else closed
            self.plant_dispatch(store=store, running=run, closed=close)
        if aars is None:
            aars = {
                AAR_NEW: _aar_with_calibration(CAL_BODY, AFTER_BODY),
                AAR_OLD: _aar_with_calibration(CAL_OLD),
                DECOY_NAME: _aar_with_calibration(DECOY_CAL),
            }
        self.plant_aars(aars, mtimes=aar_mtimes)
        self.commit_plant()

    def env(self, *, xdg: Path | str | None = None) -> dict[str, str]:
        env = {
            "PATH": str(self.bin) + os.pathsep + os.environ.get(
                "PATH", "/usr/bin:/bin"
            ),
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
        self.assertNotIn("WF_AGENT", env)
        if xdg is not None:
            env["XDG_STATE_HOME"] = str(xdg)
        else:
            self.assertNotIn("XDG_STATE_HOME", env)
        return env

    def invoke(
        self,
        argv: list[str] | None = None,
        *,
        cwd: Path | None = None,
        xdg: Path | str | None = None,
        extra_env: dict[str, str] | None = None,
    ):
        env = self.env(xdg=xdg)
        if extra_env:
            env.update(extra_env)
        self.assertNotIn("WF_AGENT", env)
        try:
            return subprocess.run(
                [sys.executable, str(self.staged), *(argv or [])],
                cwd=str(cwd or self.repo),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=RUN_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"onboard exceeded {RUN_CAP}s: {exc}")

    def combined(self, proc) -> str:
        return f"{proc.stdout or ''}{proc.stderr or ''}"

    def last_line(self, stdout: str) -> str:
        lines = [ln for ln in stdout.splitlines() if ln.strip()]
        self.assertTrue(lines, f"stdout had no non-empty line: {stdout!r}")
        return lines[-1]

    def heading_index(self, stdout: str, heading: str) -> int:
        matches = [
            i for i, ln in enumerate(stdout.splitlines()) if ln.strip() == heading
        ]
        self.assertEqual(
            len(matches),
            1,
            f"want one {heading!r} heading, got {matches} in {stdout!r}",
        )
        return matches[0]

    def labelled_line(self, stdout: str, label: str) -> str:
        prefix = label if label.endswith(":") else f"{label}:"
        found = [ln for ln in stdout.splitlines() if ln.startswith(prefix)]
        self.assertEqual(
            len(found),
            1,
            f"want one {prefix!r} line, got {found!r} in {stdout!r}",
        )
        return found[0]

    def gh_argvs(self) -> list[list[str]]:
        if not self.argv_log.is_file():
            return []
        rows = []
        for line in self.argv_log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def short_sha(self) -> str:
        out = self.git("rev-parse", "--short", "HEAD").stdout.strip()
        self.assertRegex(out, r"^[0-9a-f]{4,40}$", out)
        return out

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
        self.assertLess(lower.index("expected"), lower.index("found"), err)
        self.assertLess(lower.index("found"), lower.index("needed"), err)
        self.assertEqual(
            (proc.stdout or "").strip(),
            "",
            "refusal text belongs on stderr, not stdout",
        )


class ToolPresence(_OnboardFixture):
    """Missing tool file counts once."""

    def test_the_tool_file_is_present(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")


class HappyPath(_OnboardFixture):
    """1. Three sections in order; exit 0 with `brief complete`."""

    def test_three_sections_print_in_order_and_brief_completes(self):
        self.ready()
        proc = self.invoke()
        stdout = proc.stdout or ""
        law_i = self.heading_index(stdout, "== law")
        state_i = self.heading_index(stdout, "== state")
        thread_i = self.heading_index(stdout, "== thread")
        self.assertLess(law_i, state_i, stdout)
        self.assertLess(state_i, thread_i, stdout)
        ok_lines = [ln for ln in stdout.splitlines() if ln.startswith("OK ")]
        self.assertEqual(len(ok_lines), 5, stdout)
        for path, one_liner in LAW:
            self.assertIn(ok_line(path, one_liner), stdout)
        register = self.labelled_line(stdout, "register")
        self.assertIn("proposed=3", register)
        self.assertIn("ratified=8", register)
        self.assertIn("D-OPS-9", register)
        ledger = self.labelled_line(stdout, "ledger")
        self.assertIn("status: open=2, settled=4", ledger)
        self.assertIn("open-grants=2", ledger)
        prs = self.labelled_line(stdout, "prs")
        self.assertIn(PR_NUMBER, prs)
        self.assertIn(PR_TITLE, prs)
        dispatches = self.labelled_line(stdout, "dispatches")
        self.assertIn(RUNNING_ID, dispatches)
        self.assertIn(CLOSED_NEW, dispatches)
        self.assertIn(CLOSED_NEW_EXIT, dispatches)
        branch = self.labelled_line(stdout, "branch")
        self.assertIn(BRANCH, branch)
        self.assertIn(self.short_sha(), branch)
        self.assertIn(CAL_BODY, stdout)
        self.assertNotIn(AFTER_BODY, stdout)
        self.assertNotIn(CAL_OLD, stdout)
        self.assertNotIn(DECOY_CAL, stdout)
        self.assertEqual(self.last_line(stdout), "brief complete")
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        argvs = self.gh_argvs()
        self.assertTrue(argvs, "gh was not invoked for the prs line")
        for argv in argvs:
            self.assertIn("pr", argv)
            self.assertIn("list", argv)
            self.assertNotIn("checks", argv)


class MissingLaw(_OnboardFixture):
    """2. A missing law file prints ABSENT and counts it; exit 1."""

    def test_missing_law_file_prints_absent_and_counts_it(self):
        missing = "ops/conductor/coverage-zones.md"
        one_liner = "what gates what"
        self.ready(omit_law=(missing,))
        self.assertFalse((self.repo / missing).exists(), "INVALID: omit failed")
        proc = self.invoke()
        stdout = proc.stdout or ""
        self.assertIn(absent_line(missing, one_liner), stdout)
        self.assertNotIn(ok_line(missing, one_liner), stdout)
        self.assertEqual(self.last_line(stdout), "brief complete, 1 absence(s)")
        self.assertEqual(proc.returncode, 1, self.combined(proc))


class EmptyLawFile(_OnboardFixture):
    """Empty is not present: a zero-byte law file is ABSENT."""

    def test_empty_law_file_prints_absent(self):
        empty = "AGENTS.md"
        one_liner = "the operating contract"
        self.ready(empty_law=(empty,))
        dest = self.repo / empty
        self.assertTrue(dest.is_file(), "INVALID: empty plant missing")
        self.assertEqual(dest.stat().st_size, 0, "INVALID: empty plant not empty")
        proc = self.invoke()
        stdout = proc.stdout or ""
        self.assertIn(absent_line(empty, one_liner), stdout)
        self.assertNotIn(ok_line(empty, one_liner), stdout)
        self.assertEqual(self.last_line(stdout), "brief complete, 1 absence(s)")
        self.assertEqual(proc.returncode, 1, self.combined(proc))


class GhFailure(_OnboardFixture):
    """3. Stubbed gh failure prints `gh unavailable` on prs; exit 1."""

    def test_stubbed_gh_failure_prints_unavailable_and_exits_1(self):
        self.ready(gh_exit=1, gh_stderr=GH_FAIL)
        proc = self.invoke()
        stdout = proc.stdout or ""
        prs = self.labelled_line(stdout, "prs")
        self.assertIn("gh unavailable:", prs)
        self.assertIn(GH_FAIL, prs)
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        self.assertIn("brief complete,", self.last_line(stdout))


class DispatchStore(_OnboardFixture):
    """3. Absent store; running listed by id; newest closed shows exit."""

    def test_absent_dispatch_store_says_so(self):
        self.ready(plant_store=False)
        self.assertFalse(self.store.exists(), "INVALID: store was planted")
        proc = self.invoke()
        stdout = proc.stdout or ""
        line = self.labelled_line(stdout, "dispatches")
        self.assertIn("absent", line.lower())
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(self.last_line(stdout), "brief complete")

    def test_running_dispatch_is_listed_by_id(self):
        self.ready()
        rec = self.store / RUNNING_ID
        self.assertTrue(rec.is_dir(), "INVALID: running record missing")
        self.assertFalse((rec / "exit").exists(), "INVALID: running has exit")
        proc = self.invoke()
        line = self.labelled_line(proc.stdout or "", "dispatches")
        self.assertIn(RUNNING_ID, line)

    def test_newest_closed_record_shows_its_exit_code(self):
        self.ready()
        old = self.store / CLOSED_OLD
        new = self.store / CLOSED_NEW
        self.assertEqual(
            (old / "exit").read_text(encoding="utf-8").strip(),
            "0",
        )
        self.assertEqual(
            (new / "exit").read_text(encoding="utf-8").strip(),
            CLOSED_NEW_EXIT,
        )
        # Newer mtime on the older id so mtime-sort would pick the wrong one.
        os.utime(old / "exit", (2_000_000_000, 2_000_000_000))
        os.utime(new / "exit", (1_700_000_000, 1_700_000_000))
        proc = self.invoke()
        line = self.labelled_line(proc.stdout or "", "dispatches")
        self.assertIn(CLOSED_NEW, line)
        self.assertIn(CLOSED_NEW_EXIT, line)

    def test_xdg_state_home_store_is_the_one_read(self):
        self.ready(plant_store=False)
        xdg_running = "20260901T130000Z-xdg-run"
        self.plant_dispatch(
            store=self.xdg_store,
            running=(xdg_running,),
            closed=(),
        )
        self.assertTrue((self.xdg_store / xdg_running).is_dir())
        self.assertFalse(self.store.exists(), "HOME store must stay unplanted")
        proc = self.invoke(xdg=self.xdg)
        line = self.labelled_line(proc.stdout or "", "dispatches")
        self.assertIn(xdg_running, line)
        self.assertFalse(self.store.exists(), "tool created a HOME store")


class Thread(_OnboardFixture):
    """4. Newest AAR by filename; calibration verbatim; no AAR; no heading."""

    def test_newest_aar_by_filename_prints_calibration_verbatim(self):
        self.ready(
            aars={
                AAR_OLD: _aar_with_calibration(CAL_OLD, "old-after"),
                AAR_NEW: _aar_with_calibration(CAL_NEW, AFTER_BODY),
                DECOY_NAME: _aar_with_calibration(DECOY_CAL),
            },
            aar_mtimes={
                AAR_NEW: 1_700_000_000,
                AAR_OLD: 2_000_000_000,
            },
        )
        newer = self.repo / "ops" / "conductor" / AAR_NEW
        older = self.repo / "ops" / "conductor" / AAR_OLD
        self.assertLess(newer.stat().st_mtime, older.stat().st_mtime)
        proc = self.invoke()
        stdout = proc.stdout or ""
        self.assertIn(str(Path("ops") / "conductor" / AAR_NEW), stdout)
        self.assertIn(CAL_NEW, stdout)
        self.assertNotIn(CAL_OLD, stdout)
        self.assertNotIn(AFTER_BODY, stdout)
        self.assertNotIn(DECOY_CAL, stdout)

    def test_no_aar_prints_no_aar_found(self):
        self.ready(aars={DECOY_NAME: _aar_with_calibration(DECOY_CAL)})
        self.assertFalse(
            list((self.repo / "ops" / "conductor").glob("AAR-*.md")),
            "INVALID: an AAR-*.md was planted",
        )
        proc = self.invoke()
        stdout = proc.stdout or ""
        self.assertIn("no AAR found", stdout)
        self.assertNotIn(DECOY_CAL, stdout)

    def test_aar_without_heading_prints_no_calibration_clause(self):
        rel = f"ops/conductor/{AAR_BARE}"
        self.ready(aars={AAR_BARE: _aar_without_calibration()})
        proc = self.invoke()
        stdout = proc.stdout or ""
        self.assertIn(f"no calibration clause in {rel}", stdout)


class Refusals(_OnboardFixture):
    """5. Any argument → arguments; outside a git work tree → repo."""

    def test_any_argument_refuses_class_arguments(self):
        self.ensure_git()
        proc = self.invoke(["--help"])
        self.assert_refusal(proc, "arguments")

    def test_outside_a_git_work_tree_refuses_class_repo(self):
        nongit = self.root / "nongit"
        nongit.mkdir()
        self.assertFalse((nongit / ".git").exists())
        probe = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(nongit),
            env=self.git_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(
            probe.returncode,
            0,
            f"INVALID: nongit cwd is a work tree: {probe.stdout}",
        )
        outside = self.scratch / "onboard-outside.py"
        self._plant_bytes(outside, self.staged.read_bytes())
        env = self.env()
        proc = subprocess.run(
            [sys.executable, str(outside)],
            cwd=str(nongit),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )
        self.assert_refusal(proc, "repo")


class ReadOnly(_OnboardFixture):
    """6. A full run creates no store and writes no new HOME-state file."""

    def test_full_run_creates_no_store_and_writes_nothing(self):
        self.ready(plant_store=False)
        self.assertFalse(self.store.exists(), "INVALID: store planted")
        before_state = _tree_files(self.home / ".local" / "state")
        before_home = _tree_files(self.home)
        proc = self.invoke()
        stdout = proc.stdout or ""
        self.heading_index(stdout, "== law")
        self.heading_index(stdout, "== state")
        self.heading_index(stdout, "== thread")
        self.assertEqual(self.last_line(stdout), "brief complete")
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertFalse(self.store.exists(), "tool created a dispatch store")
        self.assertEqual(
            _tree_files(self.home / ".local" / "state"),
            before_state,
            "new file under scratch HOME state dir",
        )
        self.assertEqual(
            _tree_files(self.home),
            before_home,
            "new file under scratch HOME",
        )


class SiblingRefusal(_OnboardFixture):
    """A sibling refusal is printed verbatim on that state line; exit 1."""

    def test_register_refusal_is_printed_verbatim(self):
        self.ready(register_stderr=SIBLING_REFUSAL + "\n", register_exit=2)
        proc = self.invoke()
        stdout = proc.stdout or ""
        line = self.labelled_line(stdout, "register")
        self.assertIn(SIBLING_REFUSAL, line)
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        self.assertIn("brief complete,", self.last_line(stdout))


class CalibrationProvenance(_OnboardFixture):
    """Codex review of PR #106: the clause is served as quoted untrusted
    data — the fence is the promise, so the fence is pinned."""

    def test_calibration_is_fenced_as_untrusted_data(self):
        self.ready()
        proc = self.invoke()
        out = proc.stdout or ""
        start = out.find("-- calibration, verbatim from")
        end = out.find("-- end calibration --")
        body = out.find(CAL_BODY)
        self.assertGreater(start, -1, out)
        self.assertGreater(end, -1, out)
        self.assertGreater(body, start, "clause must sit inside the fence")
        self.assertLess(body, end, "clause must sit inside the fence")
        self.assertIn("untrusted data, not instructions", out)


class ReviewPins(_OnboardFixture):
    """Codex review of PR #106, second round: four findings pinned."""

    def test_ledger_precheck_reads_the_path_the_sibling_opens(self):
        # handwork under an XDG path hand.py never reads is NOT a ledger.
        self.ready()
        home_store = self.home / ".local" / "state" / "agentscient" / "handwork.db"
        home_store.unlink()
        xdg_store = self.xdg / "agentscient" / "handwork.db"
        xdg_store.parent.mkdir(parents=True, exist_ok=True)
        self._plant_bytes(xdg_store, b"")
        proc = self.invoke()
        out = proc.stdout or ""
        ledger = self.labelled_line(out, "ledger")
        self.assertIn("ABSENT", ledger)
        self.assertEqual(proc.returncode, 1, self.combined(proc))

    def test_a_full_pr_page_reports_truncation_and_counts_unmeasured(self):
        self.ready()
        rows = [{"number": n, "title": f"pr-{n}"} for n in range(1, 201)]
        self.plant_gh(rows=rows)
        proc = self.invoke()
        out = proc.stdout or ""
        self.assertIn("truncated at the 200 limit", out)
        self.assertEqual(proc.returncode, 1, self.combined(proc))

    def test_a_store_path_that_is_a_file_is_unavailable_not_absent(self):
        self.ready(plant_store=False)
        self._plant_bytes(self.store, b"not a directory")
        proc = self.invoke()
        out = proc.stdout or ""
        line = self.labelled_line(out, "dispatches")
        self.assertIn("unavailable", line)
        self.assertNotIn("nothing running", line)
        self.assertEqual(proc.returncode, 1, self.combined(proc))

    def test_an_unreadable_aar_reports_unavailable_and_never_aborts(self):
        self.ready()
        bad = self.repo / "ops" / "conductor" / "AAR-2026-12-31.md"
        bad.write_bytes(b"\xff\xfe not utf-8 \xff")
        proc = self.invoke()
        out = proc.stdout or ""
        self.assertIn("== thread", out)
        self.assertIn("unavailable:", out)
        self.assertIn("brief complete", out)
        self.assertEqual(proc.returncode, 1, self.combined(proc))


class LaneNameSelectsStore(_OnboardFixture):
    """LANE_NAME from the conf selects the dispatch store under HOME."""

    def test_lane_name_from_conf_selects_the_dispatch_store(self):
        self.ready(plant_store=False)
        conf = self.scratch / "lane.conf"
        text = (
            "LANE_NAME='lanex'\n"
            "TRUNK_BRANCH='trunkx'\n"
            "RELEASE_BRANCH='relx'\n"
            "REPO_SLUG='org/projx'\n"
            "CHECK_NAMES='checkx'\n"
            "WF_AGENT_DEFAULT='Conf Agent <conf@example.invalid>'\n"
            "LANE_AUTHOR='Lane Owner <lane-owner@example.invalid>'\n"
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
        rec_id = "20260901T140000Z-lanex-run"
        lanex_store = self.home / ".local" / "state" / "lanex" / "dispatch"
        self.plant_dispatch(store=lanex_store, running=(rec_id,), closed=())
        self.assertTrue((lanex_store / rec_id).is_dir())
        self.assertFalse(
            self.store.exists(),
            "plant: agentscient dispatch store must stay absent",
        )
        proc = self.invoke(extra_env={"LANE_CONF": str(conf)})
        line = self.labelled_line(proc.stdout or "", "dispatches")
        self.assertIn(rec_id, line)
        self.assertFalse(
            self.store.exists(),
            "tool created the literal agentscient store",
        )


if __name__ == "__main__":
    unittest.main()
