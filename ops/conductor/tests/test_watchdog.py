"""Watchdog-lever acceptance tests, written from the contract.

Contracts (only): `ops/conductor/watchdog-lever.md` and the inherited
`ops/conductor/instrument-conventions.md`. The tool
`ops/conductor/tools/watchdog.py` is the subject and is not read here.
Tests invoke it as a subprocess with a planted store and, when the
forge is in play, a stub `gh` first on PATH.

The live dispatch store and this repo must stay untouched — asserted
in tearDown. Stores are planted under a temporary XDG_STATE_HOME (and
`--store` / `DISPATCH_JOBS` / HOME when the resolution order is the
pin); the operator's live store is never opened.

The implementation lands in parallel. A missing tool file is one red
(`test_the_tool_file_is_present`). Every other case stages a
copy-tool-bytes stand-in so a missing file is not every test's failure:
when the tool exists its bytes are copied and run; when it does not, a
no-op stub (exit 0, no output) is planted so each assertion goes red on
the contract promise rather than Python's missing-file exit 2.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "watchdog.py"
CATALOGUE = REPO / "ops" / "devlane" / "task" / "jobs.json"

HARNESS = "watchdog-harness-aa31"
OTHER_PROC = "watchdog-other-aa31"
RUN_CAP = 30
LOOP_CAP = 0.8

ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)

# Distinctive ids so a stray live job cannot satisfy a pin.
RUN_ID = "20260904T100000Z-code-grok-aa3101"
GONE_ID = "20260904T100100Z-code-grok-aa3102"
REUSE_ID = "20260904T100200Z-code-grok-aa3103"
SETTLE_ID = "20260904T100300Z-code-grok-aa3104"
CLOSE_OK_ID = "20260904T100400Z-code-grok-aa3105"
CLOSE_TRIP_ID = "20260904T100500Z-code-grok-aa3106"
CLOSE_UNK_ID = "20260904T100600Z-code-grok-aa3107"
CLOSE_LIVE_ID = "20260904T100700Z-code-grok-aa3108"
NOCOPY_ID = "20260904T100800Z-code-grok-aa3109"
LONG_REC_ID = "20260904T100900Z-code-grok-aa3110"
LONG_JOB_ID = "20260904T101000Z-code-grok-aa3111"
LONG_UNK_ID = "20260904T101100Z-code-grok-aa3112"
INCIDENT_ID = "20260904T102000Z-code-grok-aa3160"
INCIDENT_LONG_ID = "20260904T102100Z-code-grok-aa3161"
PREDATE_ID = "20260904T102200Z-code-grok-aa3162"
RECORD_WALL_S = 3600
RECORD_WALL_MIN = 60
CATALOGUE_WALL_MIN = 30
ERR_ID = "20260904T101200Z-code-grok-aa3113"
DIED_ID = "20260904T101300Z-code-grok-aa3114"
XDG_ID = "20260904T101400Z-code-grok-aa3115"
HOME_ID = "20260904T101500Z-code-grok-aa3116"
FLAG_ID = "20260904T101600Z-code-grok-aa3117"
JOBS_ID = "20260904T101700Z-code-grok-aa3118"
CATALOGUE_JOB = "author-tests"
UNKNOWN_JOB = "not-a-catalogue-job-aa31"

PR_FAIL = 401
PR_CANCEL = 402
PR_UNREACH = 403
SHA_FAIL = "aa31" + "a" * 36
SHA_CANCEL = "aa31" + "b" * 36
SHA_UNREACH = "aa31" + "c" * 36
CHECK_LINT = "watchdog-lint-aa31"
CHECK_TYPE = "watchdog-type-aa31"
CHECK_CANCEL = "watchdog-cancel-aa31"

OMIT = object()

# PIN_ARMED: first stdout line is always
# `watchdog armed: store <path>, <n> closed records ignored, tick <s>s`.
# PIN_ONCE: `--once` is one tick, exit 0, and does not sleep the tick.
# PIN_STORE_ORDER: `--store`, else DISPATCH_JOBS, else
# `$XDG_STATE_HOME/agentscient/dispatch`, else
# `$HOME/.local/state/agentscient/dispatch`.
# PIN_CLOSED: `closed <id> status=<s> env=<envelope status> changed=<n>
# after <m> min` — env is `result.envelope.status`; changed counts
# `result.changed_paths`, or `unknown` when that key is absent; m is
# from `at.launched` to `at.closed`. Already-closed records are omitted
# unless `--report-existing` or they close after start.
# PIN_GONE: `harness gone <id> after <m> min: pid <p> dead, no exit
# written`. A live pid whose cmdline does not carry the harness name
# is the same line (reused pid). The record is then not running.
# PIN_SETTLE: `exit written, not collected <id>: <k> min since exit,
# record still <status>` after two ticks of one process; silent on the
# first.
# PIN_LONG: `long <id>: <m> min running, wall <w> min` at
# `--warn-fraction` (default 2/3) of the wall. Wall is record
# `caps.timeout` seconds, else the job's `caps.timeout` in
# `ops/devlane/task/jobs.json` (cwd = repo root), else `wall unknown`
# with a 40-minute threshold.
# PIN_NOCOPY: `no record copy <id>: cannot judge` once per process.
# PIN_ERROR: `watchdog error: <type>: <message> (tick <t>; the loop
# continues)` and `--once` still exits 0.
# PIN_CI: `ci <fail|cancel> #<pr> at <sha>: <check>` once per pull
# request head and check name; every failing or cancelled check.
# PIN_HEARTBEAT: `heartbeat: running=<id m/wall, ...>; settling=<n>;
# launchers=<L|unreachable>; open PRs into dev=<n|unreachable|not
# watched>` every `--heartbeat-every` ticks (default 6). `--no-forge`
# makes the PR field `not watched`. A PR whose checks call fails is
# named as unreachable inside that count.
# PIN_GH_LIST: `gh pr list --base dev --state open` and `gh pr checks`
# per open PR. The ci line needs a sha; tests plant gh's `headRefOid`
# on list/view JSON when `--json` is asked.
# PIN_FRACTIONAL_TICK: a tick is a positive number, not necessarily an
# integer — two ticks must fit in one second.
# PIN_REFUSAL: classes store, tick, arguments; one stderr line, exit 2,
# empty stdout, expected / found / needed in that order.

_JOB_DIR = re.compile(r"^\d{8}T\d{6}Z-[a-z-]+-[a-z]+-[0-9a-f]{6}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def utc_ago(minutes: int) -> str:
    t = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return t.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_at(stamp: str, *, minutes: int) -> str:
    t = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    t = t + timedelta(minutes=minutes)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _store_snap(path: Path) -> tuple[str, tuple[str, ...]]:
    if not path.exists():
        return ("absent", ())
    if not path.is_dir():
        return ("other", ())
    return ("dir", tuple(sorted(p.name for p in path.iterdir())))


def _without_new_job_dirs(before, after):
    """Drop from ``after`` the job directories absent from ``before``."""
    kept = {}
    for key, (kind, names) in after.items():
        if kind == "dir" and key in before and before[key][0] == "dir":
            previous = set(before[key][1])
            names = tuple(
                n for n in names
                if n in previous or not _JOB_DIR.match(n)
            )
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


def _tree_files(root: Path) -> tuple[str, ...]:
    if not root.exists():
        return ()
    names: list[str] = []
    for path in root.rglob("*"):
        if path.is_file():
            names.append(str(path.relative_to(root)))
    return tuple(sorted(names))


class _WatchdogFixture(unittest.TestCase):
    """Scratch HOME + XDG_STATE_HOME, staged tool copy, live store frozen."""

    def setUp(self):
        self._live_before = {str(p): _store_snap(p) for p in _live_store_paths()}
        self._tmp = tempfile.TemporaryDirectory(prefix="watchdog-lever-")
        root = Path(self._tmp.name)
        self.root = root
        self.home = root / "home"
        self.xdg = root / "xdg"
        self.scratch = root / "scratch"
        self.bin = root / "bin"
        for path in (self.home, self.xdg, self.scratch, self.bin):
            path.mkdir()
        self.store = self.xdg / "agentscient" / "dispatch"
        self.home_store = (
            self.home / ".local" / "state" / "agentscient" / "dispatch"
        )
        self.assertFalse(
            self.store.exists(),
            "plant: isolated XDG store must start absent",
        )
        self.assertFalse(
            self.home_store.exists(),
            "plant: isolated HOME store must start absent",
        )
        self.gh = self.bin / "gh"
        self.argv_log = self.scratch / "gh-argv.jsonl"
        self.staged = self.scratch / "watchdog.py"
        self._workers: list[subprocess.Popen] = []
        self._stage_tool_bytes()
        self.assertFalse(
            self.argv_log.exists(), "plant: argv log must start absent"
        )
        self.assertFalse(self.gh.exists(), "plant: gh stub is not planted yet")

    def tearDown(self):
        try:
            for proc in self._workers:
                if proc.poll() is None:
                    proc.kill()
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        proc.wait(timeout=2)
            self.assertEqual(
                _without_new_job_dirs(
                    self._live_before,
                    {str(p): _store_snap(p) for p in _live_store_paths()},
                ),
                self._live_before,
                "live dispatch store mutated",
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

    def ensure_store(self, store: Path | None = None) -> Path:
        dest = store if store is not None else self.store
        dest.mkdir(parents=True, exist_ok=True)
        self.assertTrue(dest.is_dir(), "INVALID: store plant did not land")
        return dest

    def catalogue_timeout(self, job: str) -> int:
        self.assertTrue(
            CATALOGUE.is_file(), f"INVALID: catalogue missing: {CATALOGUE}"
        )
        data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
        self.assertIn(job, data, f"INVALID: {job} not in catalogue")
        timeout = data[job]["caps"]["timeout"]
        self.assertIsInstance(timeout, int)
        self.assertGreater(timeout, 0)
        return timeout

    def assert_unknown_job(self, job: str) -> None:
        self.assertTrue(CATALOGUE.is_file(), "INVALID: catalogue missing")
        data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
        self.assertNotIn(job, data, f"INVALID: {job} is in the catalogue")

    def record_dict(
        self,
        rec_id: str,
        *,
        status: str = "launched",
        job: str = CATALOGUE_JOB,
        harness: str = HARNESS,
        launched: str | None = None,
        closed: str | None = None,
        timeout: int | None = None,
        changed_paths=OMIT,
        env_status: str | None = None,
    ) -> dict:
        caps: dict = {"cap-out": 500000, "source": "test"}
        if timeout is not None:
            caps["timeout"] = timeout
        rec: dict = {
            "id": rec_id,
            "job": job,
            "status": status,
            "harness": {"name": harness},
            "at": {
                "launched": launched or utc_now(),
                "closed": closed,
            },
            "caps": caps,
            "result": None,
        }
        if env_status is not None or changed_paths is not OMIT:
            result: dict = {"envelope": {}}
            if env_status is not None:
                result["envelope"]["status"] = env_status
            if changed_paths is not OMIT:
                result["changed_paths"] = list(changed_paths)
            rec["result"] = result
        return rec

    def plant_job(
        self,
        rec_id: str,
        *,
        store: Path | None = None,
        status: str = "launched",
        job: str = CATALOGUE_JOB,
        harness: str = HARNESS,
        launched: str | None = None,
        closed: str | None = None,
        timeout: int | None = None,
        changed_paths=OMIT,
        env_status: str | None = None,
        pid: int | None = None,
        exit_text: str | None = None,
        record_as_dir: bool = False,
        state_bytes: bytes | None = None,
        record: dict | None = None,
    ) -> Path:
        dest = self.ensure_store(store)
        job_dir = dest / rec_id
        job_dir.mkdir(parents=True, exist_ok=True)
        rec_path = job_dir / "record.json"
        if record_as_dir:
            rec_path.mkdir()
            self.assertTrue(rec_path.is_dir(), "plant: record.json dir")
            self.assertFalse(rec_path.is_file())
        else:
            payload = record if record is not None else self.record_dict(
                rec_id,
                status=status,
                job=job,
                harness=harness,
                launched=launched,
                closed=closed,
                timeout=timeout,
                changed_paths=changed_paths,
                env_status=env_status,
            )
            raw = json.dumps(payload, indent=2) + "\n"
            self._plant_bytes(rec_path, raw.encode("utf-8"))
            landed = json.loads(rec_path.read_text(encoding="utf-8"))
            self.assertEqual(landed["id"], rec_id)
            self.assertEqual(landed["status"], payload["status"])
        if state_bytes is not None:
            self._plant_bytes(job_dir / "state.json", state_bytes)
        elif pid is not None:
            state = {"pid": pid, "pgid": pid}
            raw_state = json.dumps(state) + "\n"
            self._plant_bytes(
                job_dir / "state.json", raw_state.encode("utf-8")
            )
            landed_state = json.loads(
                (job_dir / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(landed_state["pid"], pid)
        if exit_text is not None:
            self._plant_bytes(
                job_dir / "exit", exit_text.encode("utf-8")
            )
            self.assertTrue((job_dir / "exit").is_file())
        else:
            self.assertFalse(
                (job_dir / "exit").exists(),
                f"INVALID: exit file present for {rec_id}",
            )
        return job_dir

    def plant_no_copy(self, rec_id: str, *, store: Path | None = None) -> Path:
        dest = self.ensure_store(store)
        job_dir = dest / rec_id
        job_dir.mkdir(parents=True, exist_ok=True)
        marker = job_dir / "note.txt"
        self._plant_bytes(marker, b"no record copy planted\n")
        self.assertFalse(
            (job_dir / "record.json").exists(),
            "INVALID: no-copy plant has a record.json",
        )
        return job_dir

    def spawn_named(self, token: str) -> int:
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(120)", token],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self._workers.append(proc)
        needle = token.encode("utf-8")
        cmdline = b""
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            self.assertIsNone(proc.poll(), "INVALID: named worker exited")
            path = Path(f"/proc/{proc.pid}/cmdline")
            if path.is_file():
                cmdline = path.read_bytes()
                if needle in cmdline:
                    return proc.pid
            time.sleep(0.02)
        self.assertIn(needle, cmdline, "INVALID: worker cmdline missing token")
        return proc.pid

    def dead_pid(self) -> int:
        proc = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.wait(timeout=5)
        self.assertIsNotNone(proc.poll(), "INVALID: dead pid still running")
        with self.assertRaises(ProcessLookupError):
            os.kill(proc.pid, 0)
        return proc.pid

    def _gh_preamble(self) -> str:
        return (
            "#!/usr/bin/env python3\n"
            "from __future__ import annotations\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            f"log = Path({str(self.argv_log)!r})\n"
            "prev = log.read_text(encoding='utf-8') if log.is_file() else ''\n"
            "log.write_text("
            "prev + json.dumps(sys.argv[1:]) + '\\n', encoding='utf-8')\n"
            "argv = sys.argv[1:]\n"
            "joined = ' '.join(argv)\n"
            "wants_json = '--json' in joined or any(\n"
            "    a.startswith('--json') for a in argv)\n"
            "def _num():\n"
            "    for a in argv:\n"
            "        s = a[1:] if a.startswith('#') else a\n"
            "        if s.isdigit():\n"
            "            return s\n"
            "    return ''\n"
        )

    def plant_gh(
        self,
        *,
        prs: list[dict] | None = None,
        checks: dict[str, list[dict]] | None = None,
        fail_checks: tuple[str, ...] = (),
        list_exit: int = 0,
        list_stderr: str = "",
    ) -> None:
        prs = list(prs or [])
        checks = dict(checks or {})
        fail_checks = tuple(fail_checks)
        body = (
            self._gh_preamble()
            + f"prs = json.loads({json.dumps(json.dumps(prs))})\n"
            + f"checks = json.loads({json.dumps(json.dumps(checks))})\n"
            + f"fail_checks = set({json.dumps(list(fail_checks))})\n"
            + f"list_exit = {list_exit}\n"
            + f"list_stderr = {list_stderr!r}\n"
            + "if 'list' in argv:\n"
            + "    sys.stderr.write(list_stderr)\n"
            + "    if list_exit != 0:\n"
            + "        raise SystemExit(list_exit)\n"
            + "    if wants_json:\n"
            + "        sys.stdout.write(json.dumps(prs) + '\\n')\n"
            + "    else:\n"
            + "        for row in prs:\n"
            + "            sys.stdout.write("
            "f\"{row.get('number')}\\t{row.get('title', '')}"
            "\\tbranch\\tOPEN\\n\")\n"
            + "    raise SystemExit(0)\n"
            + "if 'checks' in argv:\n"
            + "    num = _num()\n"
            + "    if num in fail_checks:\n"
            + "        sys.stderr.write('gh pr checks failed for ' + num)\n"
            + "        raise SystemExit(1)\n"
            + "    rows = checks.get(num, [])\n"
            + "    if wants_json:\n"
            + "        sys.stdout.write(json.dumps(rows) + '\\n')\n"
            + "    else:\n"
            + "        for row in rows:\n"
            + "            bucket = row.get('bucket', 'fail')\n"
            + "            sys.stdout.write("
            "f\"{row.get('name')}\\t{bucket}\\t0s\\turl\\n\")\n"
            + "    raise SystemExit(0)\n"
            + "if 'view' in argv:\n"
            + "    num = _num()\n"
            + "    match = next((p for p in prs "
            "if str(p.get('number')) == num), None)\n"
            + "    if match is None:\n"
            + "        raise SystemExit(1)\n"
            + "    sys.stdout.write(json.dumps("
            "{'number': match.get('number'), "
            "'headRefOid': match.get('headRefOid')}) + '\\n')\n"
            + "    raise SystemExit(0)\n"
            + "raise SystemExit(1)\n"
        )
        self._plant_bytes(self.gh, body.encode("utf-8"))
        self._make_executable(self.gh)
        self.assertEqual(
            self.gh.read_text(encoding="utf-8"),
            body,
            "gh stub plant did not land intact",
        )

    def plant_default_forge(self) -> None:
        self.plant_gh(
            prs=[
                {
                    "number": PR_FAIL,
                    "title": "failing checks",
                    "headRefOid": SHA_FAIL,
                },
                {
                    "number": PR_CANCEL,
                    "title": "cancelled check",
                    "headRefOid": SHA_CANCEL,
                },
                {
                    "number": PR_UNREACH,
                    "title": "checks unreachable",
                    "headRefOid": SHA_UNREACH,
                },
            ],
            checks={
                str(PR_FAIL): [
                    {
                        "name": CHECK_LINT,
                        "state": "FAILURE",
                        "bucket": "fail",
                    },
                    {
                        "name": CHECK_TYPE,
                        "state": "FAILURE",
                        "bucket": "fail",
                    },
                ],
                str(PR_CANCEL): [
                    {
                        "name": CHECK_CANCEL,
                        "state": "CANCELLED",
                        "bucket": "cancel",
                    },
                ],
            },
            fail_checks=(str(PR_UNREACH),),
        )

    def env(
        self,
        *,
        xdg: Path | str | None = False,
        extra: dict[str, str] | None = None,
        home: Path | None = None,
    ) -> dict[str, str]:
        env = {
            "PATH": str(self.bin) + os.pathsep + os.environ.get(
                "PATH", "/usr/bin:/bin"
            ),
            "HOME": str(home if home is not None else self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        self.assertNotIn("WF_AGENT", env)
        self.assertNotIn("DISPATCH_JOBS", env)
        if xdg is False:
            env["XDG_STATE_HOME"] = str(self.xdg)
        elif xdg is not None:
            env["XDG_STATE_HOME"] = str(xdg)
        else:
            self.assertNotIn("XDG_STATE_HOME", env)
        if extra:
            env.update(extra)
        return env

    def invoke(
        self,
        argv: list[str],
        *,
        extra_env: dict[str, str] | None = None,
        xdg: Path | str | None = False,
        timeout: float = RUN_CAP,
        home: Path | None = None,
    ):
        env = self.env(xdg=xdg, extra=extra_env, home=home)
        if extra_env is None or "WF_AGENT" not in extra_env:
            self.assertNotIn("WF_AGENT", env)
        try:
            return subprocess.run(
                [sys.executable, "-u", str(self.staged), *argv],
                cwd=str(REPO),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"watchdog exceeded {timeout}s: {exc}")

    def once(
        self,
        extra: list[str] | None = None,
        *,
        forge: bool = False,
        tick: str = "1",
        extra_env: dict[str, str] | None = None,
        xdg: Path | str | None = False,
        timeout: float = RUN_CAP,
        home: Path | None = None,
    ):
        argv = ["--once", "--tick", str(tick)]
        if not forge:
            argv.append("--no-forge")
        if extra:
            argv.extend(extra)
        return self.invoke(
            argv,
            extra_env=extra_env,
            xdg=xdg,
            timeout=timeout,
            home=home,
        )

    def loop(
        self,
        argv: list[str],
        *,
        seconds: float = LOOP_CAP,
        extra_env: dict[str, str] | None = None,
        xdg: Path | str | None = False,
        mutate=None,
        mutate_after: float = 0.2,
    ):
        env = self.env(xdg=xdg, extra=extra_env)
        proc = subprocess.Popen(
            [sys.executable, "-u", str(self.staged), *argv],
            cwd=str(REPO),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        mutator = None
        if mutate is not None:
            def _run_mutate():
                time.sleep(mutate_after)
                mutate()

            mutator = threading.Thread(target=_run_mutate)
            mutator.start()
        try:
            try:
                stdout, stderr = proc.communicate(timeout=seconds)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate(timeout=2)
        finally:
            if mutator is not None:
                mutator.join(timeout=2)
        return SimpleNamespace(
            returncode=proc.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
        )

    def combined(self, proc) -> str:
        return f"{proc.stdout or ''}{proc.stderr or ''}"

    def stdout_lines(self, proc) -> list[str]:
        return [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]

    def first_line(self, proc) -> str:
        lines = self.stdout_lines(proc)
        self.assertTrue(lines, f"stdout had no non-empty line: {proc.stdout!r}")
        return lines[0]

    def named_lines(self, proc, prefix: str) -> list[str]:
        return [
            ln for ln in (proc.stdout or "").splitlines()
            if ln.startswith(prefix)
        ]

    def heartbeat_lines(self, proc) -> list[str]:
        return self.named_lines(proc, "heartbeat:")

    def assert_armed(
        self,
        proc,
        *,
        store: Path,
        ignored: int | None = None,
        tick: str | None = None,
    ) -> str:
        first = self.first_line(proc)
        self.assertTrue(
            first.startswith("watchdog armed:"),
            f"first line is not armed: {first!r} in {proc.stdout!r}",
        )
        store_s = str(store)
        store_r = str(store.resolve())
        self.assertTrue(
            store_s in first or store_r in first,
            f"armed line does not name the store {store}: {first!r}",
        )
        self.assertIn("closed records ignored", first)
        if ignored is not None:
            self.assertIn(f"{ignored} closed records ignored", first)
        if tick is not None:
            self.assertIn(f"tick {tick}", first)
        return first

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

    def gh_argvs(self) -> list[list[str]]:
        if not self.argv_log.is_file():
            return []
        rows = []
        for line in self.argv_log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


class ToolPresence(_WatchdogFixture):
    """Missing tool file counts once."""

    def test_the_tool_file_is_present(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")


class ArmedAndOnce(_WatchdogFixture):
    """Armed is the first line; --once is one tick and does not sleep."""

    def test_armed_is_the_first_line_and_names_the_store(self):
        self.ensure_store()
        proc = self.once(tick="1")
        self.assert_armed(proc, store=self.store, ignored=0, tick="1")
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_once_exits_0_without_sleeping_the_tick(self):
        self.ensure_store()
        proc = self.once(tick="10", timeout=4)
        self.assert_armed(proc, store=self.store, tick="10")
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_watchdog_tick_env_is_used_when_flag_absent(self):
        self.ensure_store()
        proc = self.invoke(
            ["--once", "--no-forge"],
            extra_env={"WATCHDOG_TICK": "7"},
        )
        self.assert_armed(proc, store=self.store, tick="7")
        self.assertEqual(proc.returncode, 0, self.combined(proc))


class StoreResolution(_WatchdogFixture):
    """--store, else DISPATCH_JOBS, else XDG, else HOME."""

    def test_store_flag_wins_over_dispatch_jobs_and_xdg(self):
        flag_store = self.scratch / "flag-store"
        decoy_jobs = self.scratch / "jobs-store"
        self.plant_job(FLAG_ID, store=flag_store, pid=self.dead_pid())
        self.plant_job(JOBS_ID, store=decoy_jobs, pid=self.dead_pid())
        self.plant_job(XDG_ID, store=self.store, pid=self.dead_pid())
        proc = self.once(
            extra=["--store", str(flag_store)],
            extra_env={"DISPATCH_JOBS": str(decoy_jobs)},
        )
        self.assert_armed(proc, store=flag_store)
        out = proc.stdout or ""
        self.assertIn(FLAG_ID, out)
        self.assertNotIn(JOBS_ID, out)
        self.assertNotIn(XDG_ID, out)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_dispatch_jobs_wins_over_xdg(self):
        jobs_store = self.scratch / "jobs-store"
        self.plant_job(JOBS_ID, store=jobs_store, pid=self.dead_pid())
        self.plant_job(XDG_ID, store=self.store, pid=self.dead_pid())
        proc = self.once(extra_env={"DISPATCH_JOBS": str(jobs_store)})
        self.assert_armed(proc, store=jobs_store)
        out = proc.stdout or ""
        self.assertIn(JOBS_ID, out)
        self.assertNotIn(XDG_ID, out)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_xdg_state_home_wins_over_home(self):
        self.plant_job(XDG_ID, store=self.store, pid=self.dead_pid())
        self.plant_job(HOME_ID, store=self.home_store, pid=self.dead_pid())
        proc = self.once()
        self.assert_armed(proc, store=self.store)
        out = proc.stdout or ""
        self.assertIn(XDG_ID, out)
        self.assertNotIn(HOME_ID, out)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_home_state_is_read_when_xdg_is_unset(self):
        self.plant_job(HOME_ID, store=self.home_store, pid=self.dead_pid())
        proc = self.once(xdg=None)
        self.assert_armed(proc, store=self.home_store)
        self.assertIn(HOME_ID, proc.stdout or "")
        self.assertEqual(proc.returncode, 0, self.combined(proc))


class Refusals(_WatchdogFixture):
    """Three classes on the wire: store, tick, arguments."""

    def test_store_that_is_a_file_refuses_class_store(self):
        not_dir = self.scratch / "not-a-store"
        self._plant_bytes(not_dir, b"file, not a directory\n")
        self.assertTrue(not_dir.is_file())
        self.assertFalse(not_dir.is_dir())
        proc = self.once(extra=["--store", str(not_dir)])
        self.assertIn(str(not_dir), proc.stderr or "")
        self.assert_refusal(proc, "store")

    def test_missing_store_path_refuses_class_store(self):
        missing = self.scratch / "no-such-store-aa31"
        self.assertFalse(missing.exists())
        proc = self.once(extra=["--store", str(missing)])
        self.assert_refusal(proc, "store")

    def test_tick_not_a_positive_number_refuses_class_tick(self):
        self.ensure_store()
        for bad in ("0", "-1", "abc"):
            with self.subTest(tick=bad):
                proc = self.once(tick=bad)
                self.assertIn(bad, proc.stderr or "")
                self.assert_refusal(proc, "tick")

    def test_watchdog_tick_env_not_positive_refuses_class_tick(self):
        self.ensure_store()
        proc = self.invoke(
            ["--once", "--no-forge"],
            extra_env={"WATCHDOG_TICK": "0"},
        )
        self.assertIn("0", proc.stderr or "")
        self.assert_refusal(proc, "tick")

    def test_heartbeat_every_not_above_zero_refuses_class_arguments(self):
        self.ensure_store()
        for bad in ("0", "-1"):
            with self.subTest(every=bad):
                proc = self.once(extra=["--heartbeat-every", bad])
                self.assertIn(bad, proc.stderr or "")
                self.assert_refusal(proc, "arguments")

    def test_warn_fraction_outside_open_unit_interval_refuses(self):
        self.ensure_store()
        for bad in ("0", "-0.5", "1.1"):
            with self.subTest(fraction=bad):
                proc = self.once(extra=["--warn-fraction", bad])
                self.assertIn(bad, proc.stderr or "")
                self.assert_refusal(proc, "arguments")

    def test_warn_fraction_one_is_in_range(self):
        self.ensure_store()
        proc = self.once(extra=["--warn-fraction", "1"])
        self.assert_armed(proc, store=self.store)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertNotEqual(proc.returncode, 2)


class RunningAndGone(_WatchdogFixture):
    """Live cmdline-matching pid is running; dead or reused pid is gone."""

    def test_running_live_harness_is_not_gone_and_is_heartbeat_running(self):
        pid = self.spawn_named(HARNESS)
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        self.assertIn(HARNESS.encode("utf-8"), cmdline)
        self.plant_job(RUN_ID, pid=pid, launched=utc_ago(3))
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store, ignored=0)
        out = proc.stdout or ""
        self.assertNotIn(f"harness gone {RUN_ID}", out)
        beats = self.heartbeat_lines(proc)
        self.assertEqual(len(beats), 1, out)
        self.assertIn(RUN_ID, beats[0])
        self.assertIn("running=", beats[0])
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_dead_pid_without_exit_is_harness_gone_and_not_running(self):
        pid = self.dead_pid()
        self.plant_job(GONE_ID, pid=pid, launched=utc_ago(9))
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store)
        out = proc.stdout or ""
        gone = self.named_lines(proc, f"harness gone {GONE_ID}")
        self.assertEqual(len(gone), 1, out)
        self.assertIn(f"pid {pid} dead, no exit written", gone[0])
        self.assertRegex(gone[0], r"after \d+ min")
        beats = self.heartbeat_lines(proc)
        self.assertEqual(len(beats), 1, out)
        running = beats[0].split("settling=")[0]
        self.assertNotIn(GONE_ID, running)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_live_pid_without_harness_name_is_harness_gone(self):
        pid = self.spawn_named(OTHER_PROC)
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        self.assertNotIn(HARNESS.encode("utf-8"), cmdline)
        self.plant_job(REUSE_ID, pid=pid, launched=utc_ago(4))
        proc = self.once(extra=["--heartbeat-every", "1"])
        gone = self.named_lines(proc, f"harness gone {REUSE_ID}")
        self.assertEqual(len(gone), 1, proc.stdout)
        self.assertIn(f"pid {pid} dead, no exit written", gone[0])
        beats = self.heartbeat_lines(proc)
        self.assertEqual(len(beats), 1, proc.stdout)
        running = beats[0].split("settling=")[0]
        self.assertNotIn(REUSE_ID, running)
        self.assertEqual(proc.returncode, 0, self.combined(proc))


class Settling(_WatchdogFixture):
    """Exit present, record still launched: silent tick 1, line on tick 2."""

    def test_settling_is_silent_on_the_first_tick(self):
        pid = self.dead_pid()
        self.plant_job(
            SETTLE_ID,
            pid=pid,
            exit_text="0\n",
            launched=utc_ago(5),
        )
        self.assertTrue((self.store / SETTLE_ID / "exit").is_file())
        rec = json.loads(
            (self.store / SETTLE_ID / "record.json").read_text(encoding="utf-8")
        )
        self.assertEqual(rec["status"], "launched")
        proc = self.once()
        self.assert_armed(proc, store=self.store)
        self.assertFalse(
            self.named_lines(proc, f"exit written, not collected {SETTLE_ID}"),
            proc.stdout,
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_settling_line_prints_on_the_second_tick(self):
        pid = self.dead_pid()
        self.plant_job(
            SETTLE_ID,
            pid=pid,
            exit_text="0\n",
            launched=utc_ago(5),
        )
        proc = self.loop(
            ["--tick", "0.15", "--no-forge"],
            seconds=0.55,
        )
        self.assert_armed(proc, store=self.store)
        settle = self.named_lines(
            proc, f"exit written, not collected {SETTLE_ID}"
        )
        self.assertEqual(len(settle), 1, proc.stdout)
        self.assertIn("record still launched", settle[0])
        self.assertRegex(settle[0], r": \d+ min since exit")


class ClosedRecords(_WatchdogFixture):
    """Closed lines: envelope, changed_paths, report-existing, close after start."""

    def test_closed_at_start_is_ignored_without_report_existing(self):
        launched = "2026-09-04T10:00:00Z"
        self.plant_job(
            CLOSE_OK_ID,
            status="closed",
            launched=launched,
            closed=utc_at(launched, minutes=12),
            env_status="ok",
            changed_paths=[],
        )
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store, ignored=1)
        self.assertFalse(
            self.named_lines(proc, f"closed {CLOSE_OK_ID}"),
            proc.stdout,
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_closed_ok_empty_changed_with_report_existing(self):
        launched = "2026-09-04T10:00:00Z"
        self.plant_job(
            CLOSE_OK_ID,
            status="closed",
            launched=launched,
            closed=utc_at(launched, minutes=12),
            env_status="ok",
            changed_paths=[],
        )
        proc = self.once(extra=["--report-existing"])
        self.assert_armed(proc, store=self.store)
        lines = self.named_lines(proc, f"closed {CLOSE_OK_ID} ")
        self.assertEqual(len(lines), 1, proc.stdout)
        self.assertEqual(
            lines[0],
            f"closed {CLOSE_OK_ID} status=closed env=ok changed=0 after 12 min",
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_closed_tripped_nonempty_changed_with_report_existing(self):
        launched = "2026-09-04T11:00:00Z"
        self.plant_job(
            CLOSE_TRIP_ID,
            status="closed",
            launched=launched,
            closed=utc_at(launched, minutes=5),
            env_status="tripped",
            changed_paths=["ops/a.py", "ops/b.py"],
        )
        proc = self.once(extra=["--report-existing"])
        lines = self.named_lines(proc, f"closed {CLOSE_TRIP_ID} ")
        self.assertEqual(len(lines), 1, proc.stdout)
        self.assertEqual(
            lines[0],
            f"closed {CLOSE_TRIP_ID} status=closed env=tripped "
            "changed=2 after 5 min",
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_closed_missing_changed_paths_is_unknown(self):
        launched = "2026-09-04T12:00:00Z"
        self.plant_job(
            CLOSE_UNK_ID,
            status="closed",
            launched=launched,
            closed=utc_at(launched, minutes=8),
            env_status="ok",
        )
        rec = json.loads(
            (self.store / CLOSE_UNK_ID / "record.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIsNotNone(rec["result"])
        self.assertNotIn("changed_paths", rec["result"])
        proc = self.once(extra=["--report-existing"])
        lines = self.named_lines(proc, f"closed {CLOSE_UNK_ID} ")
        self.assertEqual(len(lines), 1, proc.stdout)
        self.assertEqual(
            lines[0],
            f"closed {CLOSE_UNK_ID} status=closed env=ok "
            "changed=unknown after 8 min",
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_died_is_closed_and_reported_with_report_existing(self):
        launched = "2026-09-04T13:00:00Z"
        self.plant_job(
            DIED_ID,
            status="died",
            launched=launched,
            closed=utc_at(launched, minutes=3),
            env_status="invalid",
            changed_paths=[],
        )
        proc = self.once(extra=["--report-existing"])
        lines = self.named_lines(proc, f"closed {DIED_ID} ")
        self.assertEqual(len(lines), 1, proc.stdout)
        self.assertEqual(
            lines[0],
            f"closed {DIED_ID} status=died env=invalid changed=0 after 3 min",
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_closed_after_start_is_reported_without_report_existing(self):
        pid = self.spawn_named(HARNESS)
        launched = utc_ago(6)
        job_dir = self.plant_job(CLOSE_LIVE_ID, pid=pid, launched=launched)
        rec_path = job_dir / "record.json"

        def close_it():
            payload = self.record_dict(
                CLOSE_LIVE_ID,
                status="closed",
                launched=launched,
                closed=utc_now(),
                env_status="ok",
                changed_paths=["ops/conductor/watchdog-lever.md"],
            )
            rec_path.write_text(json.dumps(payload, indent=2) + "\n")
            landed = json.loads(rec_path.read_text(encoding="utf-8"))
            self.assertEqual(landed["status"], "closed")

        proc = self.loop(
            ["--tick", "0.3", "--no-forge"],
            seconds=0.75,
            mutate=close_it,
            mutate_after=0.2,
        )
        self.assert_armed(proc, store=self.store, ignored=0)
        lines = self.named_lines(proc, f"closed {CLOSE_LIVE_ID} ")
        self.assertEqual(len(lines), 1, proc.stdout)
        self.assertIn("status=closed", lines[0])
        self.assertIn("env=ok", lines[0])
        self.assertIn("changed=1", lines[0])


class NoCopy(_WatchdogFixture):
    """A job directory with no record.json is said once, never inferred."""

    def test_no_record_copy_is_said_once(self):
        self.plant_no_copy(NOCOPY_ID)
        self.assertFalse((self.store / NOCOPY_ID / "record.json").exists())
        proc = self.loop(
            ["--tick", "0.15", "--no-forge"],
            seconds=0.55,
        )
        self.assert_armed(proc, store=self.store)
        lines = self.named_lines(proc, f"no record copy {NOCOPY_ID}:")
        self.assertEqual(len(lines), 1, proc.stdout)
        self.assertIn("cannot judge", lines[0])


class LongRunning(_WatchdogFixture):
    """Long at the warn fraction of record cap, catalogue cap, or 40 min."""

    def test_long_at_warn_fraction_of_record_timeout(self):
        pid = self.spawn_named(HARNESS)
        # 900s wall = 15 min; default 2/3 = 10 min; 13 min elapsed.
        self.plant_job(
            LONG_REC_ID,
            pid=pid,
            timeout=900,
            launched=utc_ago(13),
        )
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store)
        lines = self.named_lines(proc, f"long {LONG_REC_ID}:")
        self.assertEqual(len(lines), 1, proc.stdout)
        self.assertRegex(
            lines[0],
            rf"long {re.escape(LONG_REC_ID)}: \d+ min running, wall 15 min",
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_long_uses_job_catalogue_when_record_has_no_timeout(self):
        pid = self.spawn_named(HARNESS)
        timeout = self.catalogue_timeout(CATALOGUE_JOB)
        wall_min = timeout // 60
        warn_min = (timeout * 2) // 3 // 60
        elapsed = warn_min + 5
        rec = self.record_dict(
            LONG_JOB_ID,
            job=CATALOGUE_JOB,
            launched=utc_ago(elapsed),
        )
        self.assertNotIn("timeout", rec["caps"])
        self.plant_job(LONG_JOB_ID, pid=pid, record=rec)
        proc = self.once(extra=["--heartbeat-every", "1"])
        lines = self.named_lines(proc, f"long {LONG_JOB_ID}:")
        self.assertEqual(len(lines), 1, proc.stdout)
        self.assertIn(f"wall {wall_min} min", lines[0])
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_long_wall_unknown_uses_fixed_40_minutes(self):
        pid = self.spawn_named(HARNESS)
        self.assert_unknown_job(UNKNOWN_JOB)
        rec = self.record_dict(
            LONG_UNK_ID,
            job=UNKNOWN_JOB,
            launched=utc_ago(32),
        )
        self.assertNotIn("timeout", rec["caps"])
        self.plant_job(LONG_UNK_ID, pid=pid, record=rec)
        proc = self.once(extra=["--heartbeat-every", "1"])
        lines = self.named_lines(proc, f"long {LONG_UNK_ID}:")
        self.assertEqual(len(lines), 1, proc.stdout)
        self.assertIn("wall unknown", lines[0])
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_recent_running_is_not_long(self):
        pid = self.spawn_named(HARNESS)
        self.plant_job(
            RUN_ID,
            pid=pid,
            timeout=1800,
            launched=utc_ago(2),
        )
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store)
        self.assertFalse(
            self.named_lines(proc, f"long {RUN_ID}:"),
            proc.stdout,
        )
        beats = self.heartbeat_lines(proc)
        self.assertEqual(len(beats), 1, proc.stdout)
        self.assertIn(RUN_ID, beats[0])
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_long_respects_warn_fraction(self):
        pid = self.spawn_named(HARNESS)
        # 3600s = 60 min; 2/3 = 40; 0.5 = 30. 35 min elapsed.
        self.plant_job(
            LONG_REC_ID,
            pid=pid,
            timeout=3600,
            launched=utc_ago(35),
        )
        default = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(default, store=self.store)
        self.assertFalse(
            self.named_lines(default, f"long {LONG_REC_ID}:"),
            default.stdout,
        )
        self.assertIn(LONG_REC_ID, default.stdout or "")
        half = self.once(
            extra=["--heartbeat-every", "1", "--warn-fraction", "0.5"]
        )
        lines = self.named_lines(half, f"long {LONG_REC_ID}:")
        self.assertEqual(len(lines), 1, half.stdout)
        self.assertIn("wall 60 min", lines[0])
        self.assertEqual(half.returncode, 0, self.combined(half))


class TickError(_WatchdogFixture):
    """A tick that raises prints the error line; --once still exits 0."""

    def test_record_json_directory_prints_error_and_once_exits_0(self):
        job_dir = self.plant_job(ERR_ID, record_as_dir=True)
        rec_path = job_dir / "record.json"
        self.assertTrue(rec_path.is_dir(), "plant: record.json is a directory")
        self.assertFalse(rec_path.is_file())
        proc = self.once()
        text = self.combined(proc)
        err_lines = [
            ln for ln in text.splitlines() if ln.startswith("watchdog error:")
        ]
        self.assertEqual(len(err_lines), 1, text)
        self.assertIn("the loop continues", err_lines[0])
        self.assertRegex(err_lines[0], r"\(tick \d+")
        self.assertEqual(proc.returncode, 0, text)


class ForgeAndHeartbeat(_WatchdogFixture):
    """Forge fail/cancel lines, unreachable PR, heartbeat, --no-forge."""

    def test_heartbeat_every_1_prints_heartbeat_on_once(self):
        self.ensure_store()
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store)
        beats = self.heartbeat_lines(proc)
        self.assertEqual(len(beats), 1, proc.stdout)
        beat = beats[0]
        self.assertIn("running=", beat)
        self.assertIn("settling=", beat)
        self.assertIn("launchers=", beat)
        self.assertIn("open PRs into dev=", beat)
        self.assertIn("not watched", beat)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_default_heartbeat_every_does_not_print_on_the_first_tick(self):
        self.ensure_store()
        proc = self.once()
        self.assert_armed(proc, store=self.store)
        self.assertFalse(self.heartbeat_lines(proc), proc.stdout)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_no_forge_does_not_call_gh_and_heartbeat_says_not_watched(self):
        self.ensure_store()
        self.plant_default_forge()
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store)
        self.assertEqual(self.gh_argvs(), [])
        beats = self.heartbeat_lines(proc)
        self.assertEqual(len(beats), 1, proc.stdout)
        self.assertIn("not watched", beats[0])
        self.assertFalse(self.named_lines(proc, "ci "), proc.stdout)
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_forge_fail_and_cancel_every_check_and_unreachable_heartbeat(self):
        self.ensure_store()
        self.plant_default_forge()
        proc = self.once(forge=True, extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store)
        out = proc.stdout or ""
        fail_lint = (
            f"ci fail #{PR_FAIL} at {SHA_FAIL}: {CHECK_LINT}"
        )
        fail_type = (
            f"ci fail #{PR_FAIL} at {SHA_FAIL}: {CHECK_TYPE}"
        )
        cancel = (
            f"ci cancel #{PR_CANCEL} at {SHA_CANCEL}: {CHECK_CANCEL}"
        )
        self.assertIn(fail_lint, out)
        self.assertIn(fail_type, out)
        self.assertIn(cancel, out)
        self.assertEqual(out.count(fail_lint), 1, out)
        self.assertEqual(out.count(fail_type), 1, out)
        self.assertEqual(out.count(cancel), 1, out)
        beats = self.heartbeat_lines(proc)
        self.assertEqual(len(beats), 1, out)
        self.assertIn("open PRs into dev=", beats[0])
        self.assertIn("unreachable", beats[0])
        self.assertIn(str(PR_UNREACH), beats[0])
        self.assertNotIn("not watched", beats[0])
        argvs = self.gh_argvs()
        self.assertTrue(argvs, "gh was not invoked")
        listed = False
        checked = set()
        for argv in argvs:
            if "list" in argv:
                listed = True
                self.assertIn("--base", argv)
                self.assertIn("dev", argv)
                self.assertIn("--state", argv)
                self.assertIn("open", argv)
            if "checks" in argv:
                joined = " ".join(argv)
                for number in (PR_FAIL, PR_CANCEL, PR_UNREACH):
                    if str(number) in argv or f"#{number}" in joined:
                        checked.add(number)
        self.assertTrue(listed, f"gh pr list missing: {argvs!r}")
        self.assertEqual(
            checked,
            {PR_FAIL, PR_CANCEL, PR_UNREACH},
            f"gh pr checks not called per open PR: {argvs!r}",
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))


class NoIdentity(_WatchdogFixture):
    """A read: unset WF_AGENT still runs."""

    def test_unset_wf_agent_still_runs_a_tick(self):
        self.ensure_store()
        proc = self.once()
        self.assertNotIn("WF_AGENT", self.env())
        err = (proc.stderr or "").lower()
        self.assertNotIn("identity", err)
        self.assert_armed(proc, store=self.store)
        self.assertEqual(proc.returncode, 0, self.combined(proc))


class RecordWallNotCatalogue(_WatchdogFixture):
    """Plan item 36: a running record that carries caps.timeout is
    judged against that wall, never the job catalogue. Catalogue
    fallback stays only for records that predate the field.

    The measured incident: DISPATCH_TIMEOUT=3600 (60 min) against
    author-tests catalogue 1800 (30 min); at 20 min running the
    watchdog printed wall 30 because the mint copy had no field.
    """

    def test_twenty_minutes_of_a_sixty_minute_record_wall_is_not_long(self):
        pid = self.spawn_named(HARNESS)
        catalogue = self.catalogue_timeout(CATALOGUE_JOB)
        self.assertEqual(catalogue // 60, CATALOGUE_WALL_MIN)
        rec = self.record_dict(
            INCIDENT_ID,
            job=CATALOGUE_JOB,
            timeout=RECORD_WALL_S,
            launched=utc_ago(20),
        )
        rec["caps"]["timeout_source"] = "DISPATCH_TIMEOUT"
        self.assertEqual(rec["caps"]["timeout"], RECORD_WALL_S)
        self.assertNotEqual(rec["caps"]["timeout"], catalogue)
        self.assertIn("timeout", rec["caps"])
        self.plant_job(INCIDENT_ID, pid=pid, record=rec)
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store)
        self.assertFalse(
            self.named_lines(proc, f"long {INCIDENT_ID}:"),
            proc.stdout,
        )
        beats = self.heartbeat_lines(proc)
        self.assertEqual(len(beats), 1, proc.stdout)
        self.assertRegex(
            beats[0],
            rf"{re.escape(INCIDENT_ID)} \d+m/{RECORD_WALL_MIN}\b",
        )
        self.assertNotRegex(
            beats[0],
            rf"{re.escape(INCIDENT_ID)} \d+m/{CATALOGUE_WALL_MIN}\b",
        )
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_long_line_names_the_record_wall_not_the_catalogue(self):
        pid = self.spawn_named(HARNESS)
        catalogue = self.catalogue_timeout(CATALOGUE_JOB)
        self.assertEqual(catalogue // 60, CATALOGUE_WALL_MIN)
        rec = self.record_dict(
            INCIDENT_LONG_ID,
            job=CATALOGUE_JOB,
            timeout=RECORD_WALL_S,
            launched=utc_ago(45),
        )
        rec["caps"]["timeout_source"] = "DISPATCH_TIMEOUT"
        self.assertEqual(rec["caps"]["timeout"], RECORD_WALL_S)
        self.plant_job(INCIDENT_LONG_ID, pid=pid, record=rec)
        proc = self.once(extra=["--heartbeat-every", "1"])
        lines = self.named_lines(proc, f"long {INCIDENT_LONG_ID}:")
        self.assertEqual(len(lines), 1, proc.stdout)
        self.assertRegex(
            lines[0],
            rf"long {re.escape(INCIDENT_LONG_ID)}: \d+ min running, "
            rf"wall {RECORD_WALL_MIN} min",
        )
        self.assertNotIn(f"wall {CATALOGUE_WALL_MIN} min", lines[0])
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_predating_record_without_timeout_still_uses_catalogue(self):
        pid = self.spawn_named(HARNESS)
        catalogue = self.catalogue_timeout(CATALOGUE_JOB)
        self.assertEqual(catalogue // 60, CATALOGUE_WALL_MIN)
        rec = self.record_dict(
            PREDATE_ID,
            job=CATALOGUE_JOB,
            launched=utc_ago(20),
        )
        self.assertNotIn("timeout", rec["caps"])
        self.assertNotIn("timeout_source", rec["caps"])
        self.plant_job(PREDATE_ID, pid=pid, record=rec)
        proc = self.once(extra=["--heartbeat-every", "1"])
        lines = self.named_lines(proc, f"long {PREDATE_ID}:")
        self.assertEqual(len(lines), 1, proc.stdout)
        self.assertIn(f"wall {CATALOGUE_WALL_MIN} min", lines[0])
        self.assertNotIn(f"wall {RECORD_WALL_MIN} min", lines[0])
        self.assertEqual(proc.returncode, 0, self.combined(proc))


class ReadOnly(_WatchdogFixture):
    """A tick writes nothing under the planted store."""

    def test_a_tick_does_not_write_the_store(self):
        pid = self.spawn_named(HARNESS)
        self.plant_job(RUN_ID, pid=pid, launched=utc_ago(2))
        before = _tree_files(self.store)
        before_bytes = {
            p: (self.store / p).read_bytes()
            for p in before
        }
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        after = _tree_files(self.store)
        self.assertEqual(after, before, "watchdog wrote a new store file")
        for rel, data in before_bytes.items():
            self.assertEqual(
                (self.store / rel).read_bytes(),
                data,
                f"watchdog mutated {rel}",
            )
        self.assertFalse(self.home_store.exists(), "tool created a HOME store")


if __name__ == "__main__":
    unittest.main()
