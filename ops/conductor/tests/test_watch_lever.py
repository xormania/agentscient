"""Watch-lever acceptance tests, written from the contract.

Contract: `ops/conductor/watch-lever.md`. The tool
`ops/conductor/tools/watch.py` is the subject and is not read here.
Tests invoke it as a subprocess with a stub `gh` first on PATH.

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
TOOL = REPO / "ops" / "conductor" / "tools" / "watch.py"

PR = "91"
INTERVAL = "5"
TIMEOUT = "11"
WALL = ("--interval", INTERVAL, "--timeout", TIMEOUT)
REPO_SLUG = "owner/name"
# The wall aborts at the first poll past ~15s on the 5s grid and the
# settle check precedes the wall check, so green paths never race the
# wall — but a loaded runner stacks interpreter startup on every gh
# stub spawn, and the abort paths were measured within half of the
# old 30s cap. 60 keeps the hang guard while removing the flake edge.
RUN_CAP = 60

ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)

POLL_RE = re.compile(
    r"poll rows=(\d+) pass=(\d+) fail=(\d+) pending=(\d+) skip=(\d+) "
    r"elapsed=([0-9]+(?:\.[0-9]+)?)s"
)
SETTLED_RE = re.compile(
    r"^settled rows=(\d+) pass=(\d+) fail=(\d+) skip=(\d+)\s*$"
)
GH_ERROR_TEXT = "GH_ERROR_QUOTED_MARKER: pr checks failed"

# PIN_JSON_ROWS: `gh pr checks --json name,state` is an array of
# objects with `name` and `state` (gh's --json field list).
# PIN_GH_ARGV: each poll is `pr checks NUMBER --json name,state`;
# `--repo OWNER/NAME` is inserted when given. Tests assert membership
# (and `--repo` then its value) rather than a total argv order the
# contract does not pin.
# PIN_REFUSAL_CLASS: the refusals table's left column is the token on
# the one stderr line (number, interval, gh-missing, gh-error, json).
# PIN_ABORT_COUNTS: abort leaves the last observed counts in the poll
# field shape `rows=R pass=P fail=F pending=D skip=S`.
# PIN_ELAPSED: elapsed is a number immediately followed by `s`.


def check_line(kind: str, name: str) -> str:
    return f"{kind}\t{name}"


class _WatchFixture(unittest.TestCase):
    """Scratch HOME, staged tool copy, stub gh first on PATH."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="watch-lever-")
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.scratch = root / "scratch"
        self.bin = root / "bin"
        for path in (self.home, self.scratch, self.bin):
            path.mkdir()
        self.gh = self.bin / "gh"
        self.argv_log = self.scratch / "gh-argv.jsonl"
        self.counter = self.scratch / "gh-calls"
        self.staged = self.scratch / "watch.py"
        self._stage_tool_bytes()
        self.assertFalse(self.argv_log.exists(), "plant: argv log must start absent")
        self.assertFalse(self.counter.exists(), "plant: counter must start absent")
        self.assertFalse(self.gh.exists(), "plant: gh stub is not planted yet")

    def tearDown(self):
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
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertEqual(len(landed), len(data))

    def _plant_gh(self, body: str) -> None:
        self._plant_bytes(self.gh, body.encode("utf-8"))
        mode = self.gh.stat().st_mode
        self.gh.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        landed = self.gh.read_text(encoding="utf-8")
        self.assertEqual(landed, body, "gh stub plant did not land intact")
        self.assertTrue(os.access(self.gh, os.X_OK), "gh stub is not executable")

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

    def plant_gh_rows(self, rows: list[dict], *, exit_code: int = 0, stderr: str = "") -> None:
        payload = json.dumps(rows)
        body = (
            self._gh_preamble()
            + f"sys.stderr.write({stderr!r})\n"
            + f"sys.stdout.write({payload!r} + '\\n')\n"
            + f"raise SystemExit({exit_code})\n"
        )
        self._plant_gh(body)

    def plant_gh_raw(self, stdout: str, *, exit_code: int = 0, stderr: str = "") -> None:
        body = (
            self._gh_preamble()
            + f"sys.stderr.write({stderr!r})\n"
            + f"sys.stdout.write({stdout!r})\n"
            + f"raise SystemExit({exit_code})\n"
        )
        self._plant_gh(body)

    def plant_gh_sequence(self, sequence: list[list[dict]]) -> None:
        body = (
            self._gh_preamble()
            + f"counter = Path({str(self.counter)!r})\n"
            + "n = int(counter.read_text(encoding='utf-8')) if counter.is_file() else 0\n"
            + "n += 1\n"
            + "counter.write_text(str(n), encoding='utf-8')\n"
            + f"seq = {json.dumps(sequence)}\n"
            + "rows = seq[n - 1] if n <= len(seq) else seq[-1]\n"
            + "sys.stdout.write(json.dumps(rows) + '\\n')\n"
            + "raise SystemExit(0)\n"
        )
        self._plant_gh(body)
        self.assertFalse(self.counter.exists(), "plant: sequence counter still absent")

    def env(self, *, path: str | None = None, agent: str | None = None) -> dict[str, str]:
        env = {
            "PATH": path if path is not None else (
                str(self.bin) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
            ),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if agent is not None:
            env["WF_AGENT"] = agent
        return env

    def path_without_gh(self) -> str:
        empty = self.scratch / "no-gh"
        empty.mkdir(exist_ok=True)
        self.assertFalse((empty / "gh").exists(), "plant: empty PATH dir has a gh")
        parts = [str(empty)]
        for item in os.environ.get("PATH", "/usr/bin:/bin").split(os.pathsep):
            if not item:
                continue
            if (Path(item) / "gh").exists():
                continue
            parts.append(item)
        path = os.pathsep.join(parts)
        self.assertIsNone(
            shutil.which("gh", path=path),
            "INVALID: gh is still on PATH",
        )
        return path

    def invoke(
        self,
        argv: list[str],
        *,
        path: str | None = None,
        agent: str | None = None,
    ):
        env = self.env(path=path, agent=agent)
        if agent is None:
            self.assertNotIn("WF_AGENT", env)
        else:
            self.assertEqual(env.get("WF_AGENT"), agent)
        try:
            return subprocess.run(
                [sys.executable, str(self.staged), *argv],
                cwd=str(REPO),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=RUN_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"watch exceeded {RUN_CAP}s: {exc}")

    def watch(self, number: str = PR, extra: list[str] | None = None, **kw):
        argv = ["pr", number, *WALL]
        if extra:
            argv.extend(extra)
        return self.invoke(argv, **kw)

    def combined(self, proc) -> str:
        return f"{proc.stdout or ''}{proc.stderr or ''}"

    def gh_argvs(self) -> list[list[str]]:
        if not self.argv_log.is_file():
            return []
        rows = []
        for line in self.argv_log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def poll_matches(self, text: str) -> list[re.Match[str]]:
        return list(POLL_RE.finditer(text))

    def last_counts(self, proc) -> dict[str, int] | None:
        matches = self.poll_matches(self.combined(proc))
        if not matches:
            return None
        rows, passed, failed, pending, skip, _elapsed = matches[-1].groups()
        return {
            "rows": int(rows),
            "pass": int(passed),
            "fail": int(failed),
            "pending": int(pending),
            "skip": int(skip),
        }

    def settled_line(self, stdout: str) -> str | None:
        lines = [ln for ln in stdout.splitlines() if ln.strip()]
        if not lines:
            return None
        last = lines[-1]
        if SETTLED_RE.match(last):
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


class ToolPresence(_WatchFixture):
    """Missing tool file counts once."""

    def test_the_tool_file_is_present(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")


class SettledGreen(_WatchFixture):
    """1. All SUCCESS/SKIPPED → PASS/SKIP lines, settled summary, exit 0."""

    def test_success_and_skipped_settle_green(self):
        self.plant_gh_rows(
            [
                {"name": "lint", "state": "SUCCESS"},
                {"name": "docs", "state": "SKIPPED"},
            ]
        )
        proc = self.watch()
        stdout = proc.stdout or ""
        self.assertIn(
            check_line("PASS", "lint"),
            stdout,
            f"missing PASS<tab>lint on stdout: {stdout!r}",
        )
        self.assertIn(check_line("SKIP", "docs"), stdout)
        self.assertEqual(
            self.settled_line(stdout),
            "settled rows=2 pass=1 fail=0 skip=1",
            stdout,
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        counts = self.last_counts(proc)
        self.assertIsNotNone(counts, f"no poll line on stderr: {proc.stderr!r}")
        self.assertEqual(counts["rows"], 2)
        self.assertEqual(counts["pass"], 1)
        self.assertEqual(counts["fail"], 0)
        self.assertEqual(counts["pending"], 0)
        self.assertEqual(counts["skip"], 1)


class SettledFailure(_WatchFixture):
    """2. A FAILURE row settles with FAIL named and exit 1."""

    def test_failure_row_settles_exit_1_naming_fail(self):
        self.plant_gh_rows([{"name": "broken", "state": "FAILURE"}])
        proc = self.watch()
        stdout = proc.stdout or ""
        self.assertIn(
            check_line("FAIL", "broken"),
            stdout,
            f"missing FAIL<tab>broken on stdout: {stdout!r}",
        )
        self.assertEqual(
            self.settled_line(stdout),
            "settled rows=1 pass=0 fail=1 skip=0",
            stdout,
        )
        self.assertEqual(proc.returncode, 1, self.combined(proc))


class ZeroRowsAbort(_WatchFixture):
    """3. Zero rows is not settled: poll to the wall, exit 3, leave counts."""

    def test_empty_check_table_aborts_at_the_wall_with_last_counts(self):
        self.plant_gh_rows([])
        proc = self.watch()
        text = self.combined(proc)
        self.assertIn(
            "rows=0",
            text,
            f"abort must print last observed counts; got {text!r}",
        )
        counts = self.last_counts(proc)
        self.assertIsNotNone(counts, f"abort printed no poll counts: {text!r}")
        self.assertEqual(counts["rows"], 0, counts)
        self.assertEqual(counts["pass"], 0, counts)
        self.assertEqual(counts["fail"], 0, counts)
        self.assertEqual(counts["pending"], 0, counts)
        self.assertEqual(counts["skip"], 0, counts)
        self.assertEqual(proc.returncode, 3, text)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIsNone(self.settled_line(proc.stdout or ""))


class PendingThenSettled(_WatchFixture):
    """4. IN_PROGRESS keeps polling; a later settled poll re-reads and settles."""

    def test_in_progress_then_success_re_reads_and_settles(self):
        self.plant_gh_sequence(
            [
                [{"name": "progress-check", "state": "IN_PROGRESS"}],
                [{"name": "progress-check", "state": "SUCCESS"}],
            ]
        )
        proc = self.watch()
        self.assertTrue(
            self.counter.is_file(),
            "poll loop did not re-read gh (counter file missing)",
        )
        n = int(self.counter.read_text(encoding="utf-8"))
        self.assertGreaterEqual(
            n,
            2,
            f"poll loop did not re-read; gh calls={n}",
        )
        stdout = proc.stdout or ""
        self.assertIn(check_line("PASS", "progress-check"), stdout)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(
            self.settled_line(stdout),
            "settled rows=1 pass=1 fail=0 skip=0",
            stdout,
        )


class UnrecognizedNeverSettles(_WatchFixture):
    """5. An unrecognized state is pending and never settles: exit 3, not 0."""

    def test_unrecognized_state_aborts_at_the_wall_not_exit_0(self):
        self.plant_gh_rows(
            [{"name": "odd-check", "state": "NOT_A_REAL_GH_STATE"}]
        )
        proc = self.watch()
        text = self.combined(proc)
        counts = self.last_counts(proc)
        self.assertIsNotNone(
            counts,
            f"unrecognized state produced no pending count: {text!r}",
        )
        self.assertGreaterEqual(
            counts["pending"],
            1,
            f"unrecognized state must count as pending: {counts}",
        )
        self.assertEqual(proc.returncode, 3, text)
        self.assertNotEqual(proc.returncode, 0, "unrecognized state settled")
        self.assertNotIn(check_line("PASS", "odd-check"), proc.stdout or "")
        self.assertIsNone(self.settled_line(proc.stdout or ""))


class StateMapping(_WatchFixture):
    """6. CANCELLED/TIMED_OUT → fail; NEUTRAL → skip."""

    def test_cancelled_settles_as_fail(self):
        self.plant_gh_rows(
            [{"name": "cancelled-check", "state": "CANCELLED"}]
        )
        proc = self.watch()
        stdout = proc.stdout or ""
        self.assertIn(
            check_line("FAIL", "cancelled-check"),
            stdout,
            f"CANCELLED must map to FAIL: {stdout!r}",
        )
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        self.assertEqual(
            self.settled_line(stdout),
            "settled rows=1 pass=0 fail=1 skip=0",
            stdout,
        )

    def test_timed_out_settles_as_fail(self):
        self.plant_gh_rows(
            [{"name": "timed-out-check", "state": "TIMED_OUT"}]
        )
        proc = self.watch()
        stdout = proc.stdout or ""
        self.assertIn(
            check_line("FAIL", "timed-out-check"),
            stdout,
            f"TIMED_OUT must map to FAIL: {stdout!r}",
        )
        self.assertEqual(proc.returncode, 1, self.combined(proc))

    def test_neutral_settles_as_skip(self):
        self.plant_gh_rows(
            [{"name": "neutral-check", "state": "NEUTRAL"}]
        )
        proc = self.watch()
        stdout = proc.stdout or ""
        self.assertIn(
            check_line("SKIP", "neutral-check"),
            stdout,
            f"NEUTRAL must map to SKIP: {stdout!r}",
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(
            self.settled_line(stdout),
            "settled rows=1 pass=0 fail=0 skip=1",
            stdout,
        )


class Refusals(_WatchFixture):
    """7. Refusals exit 2, expected/found/needed, one line on stderr."""

    def test_number_not_a_positive_integer_refuses(self):
        self.plant_gh_rows([{"name": "lint", "state": "SUCCESS"}])
        for bad in ("0", "-1", "abc"):
            with self.subTest(number=bad):
                proc = self.watch(number=bad)
                self.assertIn(
                    bad,
                    proc.stderr or "",
                    f"NUMBER {bad!r} must appear in found: {proc.stderr!r}",
                )
                self.assert_refusal(proc, "number")

    def test_interval_under_5_refuses(self):
        self.plant_gh_rows([{"name": "lint", "state": "SUCCESS"}])
        proc = self.invoke(["pr", PR, "--interval", "4", "--timeout", TIMEOUT])
        err = proc.stderr or ""
        self.assertIn("4", err, f"found must name 4: {err!r}")
        self.assert_refusal(proc, "interval")

    def test_gh_missing_from_path_refuses(self):
        path = self.path_without_gh()
        proc = self.watch(path=path)
        self.assert_refusal(proc, "gh-missing")

    def test_gh_nonzero_exit_quotes_stderr_in_found(self):
        self.plant_gh_raw("", exit_code=1, stderr=GH_ERROR_TEXT + "\n")
        proc = self.watch()
        err = proc.stderr or ""
        self.assertIn(
            GH_ERROR_TEXT,
            err,
            f"gh stderr must be quoted in found: {err!r}",
        )
        self.assert_refusal(proc, "gh-error")

    def test_non_json_output_is_a_json_refusal(self):
        self.plant_gh_raw("this is not json\n")
        proc = self.watch()
        self.assert_refusal(proc, "json")


class ExpectMin(_WatchFixture):
    """8. --expect-min N: fewer than N rows do not settle even with none pending."""

    def test_rows_below_expect_min_do_not_settle(self):
        self.plant_gh_rows([{"name": "solo", "state": "SUCCESS"}])
        proc = self.watch(extra=["--expect-min", "2"])
        stdout = proc.stdout or ""
        self.assertNotIn(
            "settled rows=",
            stdout,
            f"rows < expect-min settled: {stdout!r}",
        )
        counts = self.last_counts(proc)
        self.assertIsNotNone(
            counts,
            f"expect-min abort printed no counts: {self.combined(proc)!r}",
        )
        self.assertEqual(counts["rows"], 1, counts)
        self.assertEqual(counts["pending"], 0, counts)
        self.assertEqual(proc.returncode, 3, self.combined(proc))
        self.assertNotEqual(proc.returncode, 0)


class NoIdentity(_WatchFixture):
    """9. Watching is a read: unset WF_AGENT, the watch still runs."""

    def test_unset_wf_agent_still_runs_a_settled_read(self):
        self.plant_gh_rows([{"name": "read-check", "state": "SUCCESS"}])
        proc = self.watch(agent=None)
        err = (proc.stderr or "").lower()
        self.assertNotIn("identity", err)
        stdout = proc.stdout or ""
        self.assertIn(
            check_line("PASS", "read-check"),
            stdout,
            f"read without WF_AGENT produced no PASS: {stdout!r}",
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))


class RepoPassthrough(_WatchFixture):
    """10. --repo OWNER/NAME is passed through to gh."""

    def test_repo_flag_is_passed_through_to_gh(self):
        self.plant_gh_rows([{"name": "repo-check", "state": "SUCCESS"}])
        proc = self.watch(extra=["--repo", REPO_SLUG])
        argvs = self.gh_argvs()
        self.assertTrue(
            argvs,
            "gh was not invoked; --repo cannot have been passed through",
        )
        found_repo = False
        found_value = False
        found_pair = False
        for argv in argvs:
            if "--repo" in argv:
                found_repo = True
                idx = argv.index("--repo")
                if idx + 1 < len(argv) and argv[idx + 1] == REPO_SLUG:
                    found_pair = True
            if REPO_SLUG in argv:
                found_value = True
            self.assertIn("pr", argv)
            self.assertIn("checks", argv)
            self.assertIn(PR, argv)
            self.assertTrue(
                "--json" in argv or any(item.startswith("--json=") for item in argv),
                f"gh argv missing --json: {argv!r}",
            )
            self.assertTrue(
                any("name" in item and "state" in item for item in argv),
                f"gh argv missing name,state: {argv!r}",
            )
        self.assertTrue(found_repo, f"--repo missing from gh argv: {argvs!r}")
        self.assertTrue(found_value, f"{REPO_SLUG!r} missing from gh argv: {argvs!r}")
        self.assertTrue(
            found_pair,
            f"--repo was not followed by {REPO_SLUG!r}: {argvs!r}",
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertIn(check_line("PASS", "repo-check"), proc.stdout or "")


class TableCompleteness(_WatchFixture):
    """Codex security review of PR #102: a table still filling in must
    never settle; the caller can inject the expected-name authority."""

    def test_a_filling_table_does_not_settle_on_its_first_shape(self):
        one = [{"name": "fast-lint", "state": "SUCCESS"}]
        three = one + [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "secret-scan", "state": "SUCCESS"},
        ]
        self.plant_gh_sequence([one, three, three])
        proc = self.watch()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertIn("settled rows=3", proc.stdout or "")
        self.assertNotIn("settled rows=1", proc.stdout or "")
        self.assertIn("confirming", proc.stderr or "")

    def test_expect_names_missing_check_never_settles(self):
        self.plant_gh_rows([{"name": "fast-lint", "state": "SUCCESS"}])
        proc = self.watch(extra=["--expect-names", "fast-lint,secret-scan"])
        self.assertEqual(proc.returncode, 3, self.combined(proc))
        self.assertIn("missing=1", proc.stderr or "")
        self.assertIn("abort", proc.stderr or "")

    def test_expect_names_all_reported_settles(self):
        self.plant_gh_rows([
            {"name": "fast-lint", "state": "SUCCESS"},
            {"name": "secret-scan", "state": "SUCCESS"},
        ])
        proc = self.watch(extra=["--expect-names", "fast-lint,secret-scan"])
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertIn("settled rows=2", proc.stdout or "")


if __name__ == "__main__":
    unittest.main()
