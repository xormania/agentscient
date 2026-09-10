"""Independent TDD tests for onboard freshness lines.

Contracts (only): `ops/conductor/onboard-lever.md` §state freshness and
the git-refs adapter in `ops/conductor/monitor-lever.md`. The tools
`onboard.py` and `monitor.py` are subjects and are not read here.
Tests reuse `_OnboardFixture`, plant a default `branch_refs` registry
in the scratch checkout, and mock only `ls-remote` through a PATH git
shim. No network, no new public helper.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import unittest
from pathlib import Path

from test_onboard_lever import TOOL as ONBOARD_TOOL
from test_onboard_lever import _OnboardFixture, _tree_files

MONITOR_TOOL = Path(__file__).resolve().parents[3] / "ops" / "conductor" / "tools" / "monitor.py"
LANECONF = Path(__file__).resolve().parents[3] / "ops" / "conductor" / "tools" / "laneconf.py"
EXAMPLE = Path(__file__).resolve().parents[3] / "ops" / "conductor" / "monitor.example.json"

REPO_USER = "Onboard Freshness Tester"
REPO_EMAIL = "onboard-freshness@example.invalid"
GIT_SECRET = "GIT_RAW_STDERR_aa41_must_not_leak"
REMOTE_NAME = "origin"
DEV = "dev"
MASTER = "master"
DEV_REF = "refs/heads/dev"
MASTER_REF = "refs/heads/master"
OID_RE = r"[0-9a-f]{40}(?:[0-9a-f]{24})?"
LINE_RE = re.compile(
    r"^freshness: (?P<ref>refs/heads/(?:dev|master)) "
    r"local=(?P<local>null|" + OID_RE + r") "
    r"remote=(?P<remote>null|" + OID_RE + r") "
    r"status=(?P<status>equal|different|missing-local|missing-remote|"
    r"missing-both|remote-unavailable|local-unavailable) "
    r"observed_at=(?P<at>\S+)$"
)
WARN_RE = re.compile(
    r"^warning: expected equal local/live remote refs for new work; "
    r"found (?P<status>equal|different|missing-local|missing-remote|"
    r"missing-both|remote-unavailable|local-unavailable); "
    r"needed owner reconciliation or a verified baseline$"
)
UNAVAIL_CFG_RE = re.compile(
    r"^freshness: unavailable: expected .+; found .+; needed .+$"
)


class _FreshnessFixture(_OnboardFixture):
    """Scratch onboard repo with origin, default branch_refs, git shim."""

    def setUp(self):
        super().setUp()
        self._example_before = EXAMPLE.read_bytes() if EXAMPLE.is_file() else None
        self.real_git = shutil.which("git")
        self.assertIsNotNone(self.real_git, "INVALID: git not on PATH")
        self.git_argv_log = self.scratch / "git-argv.jsonl"
        self.git_control = self.scratch / "git-shim-control.json"
        self.origin = self.scratch / "origin.git"
        self.pusher = self.scratch / "pusher"
        self._plant_git_shim()
        self._stage_monitor_bytes()
        self._plant_lane_conf()
        self.assertFalse(self.git_argv_log.exists(), "plant: git argv log absent")

    def tearDown(self):
        try:
            if self._example_before is not None:
                self.assertEqual(
                    EXAMPLE.read_bytes(),
                    self._example_before,
                    "default monitor registry mutated",
                )
        finally:
            super().tearDown()

    def git_env(self) -> dict[str, str]:
        env = super().git_env()
        env["GIT_AUTHOR_NAME"] = REPO_USER
        env["GIT_AUTHOR_EMAIL"] = REPO_EMAIL
        env["GIT_COMMITTER_NAME"] = REPO_USER
        env["GIT_COMMITTER_EMAIL"] = REPO_EMAIL
        return env

    def env(self, *, xdg=None):
        env = super().env(xdg=xdg)
        env["LANE_CONF"] = str(self.lane_conf)
        return env

    def _plant_lane_conf(self) -> None:
        path = self.scratch / "lane.conf"
        text = (
            "LANE_NAME='agentscient'\n"
            "TRUNK_BRANCH='dev'\n"
            "RELEASE_BRANCH='master'\n"
            "REPO_SLUG='org/proj'\n"
            "CHECK_NAMES='lane app'\n"
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
        self._plant_bytes(path, text.encode("utf-8"))
        self.lane_conf = path
        self.assertEqual(path.read_text(encoding="utf-8"), text)

    def _stage_monitor_bytes(self) -> None:
        # Scratch only during setUp: planting into self.repo before
        # ensure_git leaves untracked ops/ and breaks the seed commit.
        copies = [self.scratch / "monitor.py"]
        if MONITOR_TOOL.is_file():
            data = MONITOR_TOOL.read_bytes()
            for dest in copies:
                self._plant_bytes(dest, data)
                self.assertEqual(dest.read_bytes(), data)
                self.assertNotEqual(dest.read_bytes(), b"")
        if LANECONF.is_file():
            payload = LANECONF.read_bytes()
            dest = self.scratch / LANECONF.name
            self._plant_bytes(dest, payload)
            self.assertEqual(dest.read_bytes(), payload)

    def _stage_monitor_into_repo(self) -> None:
        if MONITOR_TOOL.is_file():
            data = MONITOR_TOOL.read_bytes()
            dest = self.repo / "ops" / "conductor" / "tools" / "monitor.py"
            self._plant_bytes(dest, data)
            self.assertEqual(dest.read_bytes(), data)
        if LANECONF.is_file():
            payload = LANECONF.read_bytes()
            dest = self.repo / "ops" / "conductor" / "tools" / LANECONF.name
            self._plant_bytes(dest, payload)
            self.assertEqual(dest.read_bytes(), payload)

    def _plant_git_shim(self) -> None:
        control = {
            "mode": "passthrough",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "sleep_s": 0,
        }
        raw = (json.dumps(control) + "\n").encode("utf-8")
        self._plant_bytes(self.git_control, raw)
        body = (
            f"#!{sys.executable}\n"
            "from __future__ import annotations\n"
            "import json, subprocess, sys, time\n"
            "from pathlib import Path\n"
            f"log = Path({str(self.git_argv_log)!r})\n"
            f"control_path = Path({str(self.git_control)!r})\n"
            f"real = {self.real_git!r}\n"
            "argv = sys.argv[1:]\n"
            "prev = log.read_text(encoding='utf-8') if log.is_file() else ''\n"
            "log.write_text(prev + json.dumps(argv) + '\\n', encoding='utf-8')\n"
            "ctrl = json.loads(control_path.read_text(encoding='utf-8'))\n"
            "is_ls = 'ls-remote' in argv\n"
            "mode = ctrl.get('mode') or 'passthrough'\n"
            "if is_ls and mode != 'passthrough':\n"
            "    time.sleep(float(ctrl.get('sleep_s') or 0))\n"
            "    sys.stderr.write(str(ctrl.get('stderr') or ''))\n"
            "    sys.stdout.write(str(ctrl.get('stdout') or ''))\n"
            "    raise SystemExit(int(ctrl.get('exit_code') or 0))\n"
            "raise SystemExit(subprocess.call([real, *argv]))\n"
        )
        dest = self.bin / "git"
        self._plant_bytes(dest, body.encode("utf-8"))
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.assertTrue(os.access(dest, os.X_OK), dest)
        which = shutil.which("git", path=str(self.bin) + os.pathsep + os.environ.get("PATH", ""))
        self.assertEqual(Path(which).resolve(), dest.resolve(), which)

    def set_ls_remote(self, **ctrl) -> None:
        body = {
            "mode": "passthrough",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "sleep_s": 0,
        }
        body.update(ctrl)
        raw = (json.dumps(body) + "\n").encode("utf-8")
        self._plant_bytes(self.git_control, raw)
        landed = json.loads(self.git_control.read_text(encoding="utf-8"))
        self.assertEqual(landed["mode"], body["mode"], landed)

    def ls_remote_argvs(self) -> list[list[str]]:
        if not self.git_argv_log.is_file():
            return []
        rows = []
        for line in self.git_argv_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            argv = json.loads(line)
            if "ls-remote" in argv:
                rows.append(argv)
        return rows

    def oid(self, ref: str, *, repo: Path | None = None) -> str:
        out = self.git("rev-parse", "--verify", ref, cwd=repo or self.repo).stdout.strip()
        self.assertRegex(out, r"^" + OID_RE + r"$", out)
        return out

    def branch_refs_registry(self, *, enabled: bool = True, params=None, **monitor_over) -> dict:
        body = {
            "version": 1,
            "schedules": {"forge": {"enabled": True, "every_s": 300}},
            "monitors": {
                "branch_refs": {
                    "enabled": enabled,
                    "adapter": "git-refs",
                    "schedule": "forge",
                    "params": params
                    or {
                        "repo": "../..",
                        "remote": REMOTE_NAME,
                        "branches": [DEV, MASTER],
                        "timeout_s": 5,
                    },
                }
            },
            "conditions": {
                "refs_changed": {
                    "enabled": True,
                    "monitor": "branch_refs",
                    "op": "changed",
                    "field": "freshness",
                    "threshold": None,
                    "cooldown_s": 0,
                },
                "refs_unavailable": {
                    "enabled": True,
                    "monitor": "branch_refs",
                    "op": "unavailable",
                    "field": None,
                    "threshold": None,
                    "cooldown_s": 0,
                },
            },
            "routes": {
                "refs_changed": {
                    "enabled": True,
                    "condition": "refs_changed",
                    "adapter": "queue",
                    "consumer": "operator",
                },
                "refs_unavailable": {
                    "enabled": True,
                    "condition": "refs_unavailable",
                    "adapter": "queue",
                    "consumer": "operator",
                },
            },
        }
        body["monitors"]["branch_refs"].update(monitor_over)
        return body

    def plant_default_registry(self, data: dict | None = None) -> None:
        payload = json.dumps(data if data is not None else self.branch_refs_registry(), indent=2) + "\n"
        raw = payload.encode("utf-8")
        dests = [
            self.repo / "ops" / "conductor" / "monitor.example.json",
            self.scratch / "monitor.example.json",
            self.staged.parent.parent / "monitor.example.json",
        ]
        for dest in dests:
            self._plant_bytes(dest, raw)
            self.assertEqual(dest.read_bytes(), raw)

    def plant_origin_and_trunks(self) -> dict[str, str]:
        self.ensure_git()
        self._stage_monitor_into_repo()
        init_b = subprocess.run(
            [self.real_git, "init", "--bare", "-b", MASTER, str(self.origin)],
            env=self.git_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(init_b.returncode, 0, init_b.stderr)
        self.git("branch", MASTER)
        master_oid = self.oid("HEAD")
        self.git("branch", DEV)
        self.git("checkout", DEV)
        extra = self.repo / "DEV_ONLY"
        self._plant_bytes(extra, b"dev marker\n")
        self.assertEqual(extra.read_bytes(), b"dev marker\n")
        self.git("add", "DEV_ONLY")
        self.git("commit", "-m", "dev marker\n")
        dev_oid = self.oid("HEAD")
        self.assertNotEqual(dev_oid, master_oid)
        self.git("remote", "add", REMOTE_NAME, str(self.origin))
        self.git("push", REMOTE_NAME, DEV, MASTER)
        self.git("checkout", "onboard-lineage")
        self.assertEqual(self.oid(DEV_REF), dev_oid)
        self.assertEqual(self.oid(MASTER_REF), master_oid)
        return {"dev": dev_oid, "master": master_oid}

    def advance_origin(self, branch: str, payload: bytes) -> str:
        if self.pusher.exists():
            shutil.rmtree(self.pusher)
        clone = subprocess.run(
            [self.real_git, "clone", "--quiet", str(self.origin), str(self.pusher)],
            env=self.git_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(clone.returncode, 0, clone.stderr)
        self.git("checkout", branch, cwd=self.pusher)
        target = self.pusher / "README"
        if not target.exists():
            target = self.pusher / "DEV_ONLY"
        self._plant_bytes(target, payload)
        self.assertEqual(target.read_bytes(), payload)
        self.git("add", "-A", cwd=self.pusher)
        self.git("commit", "-m", f"advance {branch}\n", cwd=self.pusher)
        new_oid = self.oid("HEAD", repo=self.pusher)
        self.git("push", REMOTE_NAME, branch, cwd=self.pusher)
        return new_oid

    def delete_origin_branch(self, branch: str) -> None:
        proc = self.git(
            "update-ref", "-d", f"refs/heads/{branch}", cwd=self.origin, check=False
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def delete_local_branch(self, branch: str) -> None:
        current = self.git("symbolic-ref", "--short", "HEAD").stdout.strip()
        if current == branch:
            self.git("checkout", "onboard-lineage")
        self.git("branch", "-D", branch)
        miss = self.git("rev-parse", "--verify", f"refs/heads/{branch}", check=False)
        self.assertNotEqual(miss.returncode, 0, miss.stdout)

    def ready_fresh(self, **kw) -> dict[str, str]:
        self.ready(**kw)
        self._stage_monitor_into_repo()
        oids = self.plant_origin_and_trunks()
        self.plant_default_registry()
        return oids

    def fingerprint(self, repo: Path | None = None) -> dict[str, object]:
        root = repo or self.repo
        show = self.git("show-ref", "--head", cwd=root, check=False)
        status = self.git(
            "status", "--porcelain=v1", "--untracked-files=all", cwd=root
        )
        head = self.git("rev-parse", "HEAD", cwd=root, check=False)
        index = self.git("ls-files", "-s", cwd=root)
        cfg = root / ".git" / "config"
        config = cfg.read_bytes() if cfg.is_file() else b""
        return {
            "show-ref": show.stdout,
            "status": status.stdout,
            "head": head.stdout,
            "index": index.stdout,
            "config": config,
            "files": _tree_files(root),
        }

    def freshness_lines(self, stdout: str) -> list[str]:
        return [ln for ln in stdout.splitlines() if ln.startswith("freshness:")]

    def warning_lines(self, stdout: str) -> list[str]:
        return [ln for ln in stdout.splitlines() if ln.startswith("warning:")]

    def parse_freshness(self, line: str) -> dict[str, str]:
        match = LINE_RE.match(line)
        self.assertIsNotNone(match, line)
        return match.groupdict()

    def assert_freshness_line(
        self,
        line: str,
        *,
        ref: str,
        local: str,
        remote: str,
        status: str,
    ) -> dict[str, str]:
        parsed = self.parse_freshness(line)
        self.assertEqual(parsed["ref"], ref, line)
        self.assertEqual(parsed["local"], local, line)
        self.assertEqual(parsed["remote"], remote, line)
        self.assertEqual(parsed["status"], status, line)
        self.assertRegex(parsed["at"], r"Z$|\+00:00$", parsed["at"])
        return parsed

    def assert_warning(self, line: str, status: str) -> None:
        match = WARN_RE.match(line)
        self.assertIsNotNone(match, line)
        self.assertEqual(match.group("status"), status, line)

    def assert_one_ls_remote(self) -> list[str]:
        rows = self.ls_remote_argvs()
        self.assertEqual(len(rows), 1, rows)
        argv = rows[0]
        self.assertIn("ls-remote", argv)
        self.assertIn("--refs", argv)
        self.assertIn("--", argv)
        self.assertIn(REMOTE_NAME, argv)
        self.assertIn(DEV_REF, argv)
        self.assertIn(MASTER_REF, argv)
        self.assertLess(argv.index(DEV_REF), argv.index(MASTER_REF), argv)
        return argv

    def monitor_state_paths(self) -> list[Path]:
        return [
            self.xdg / "agentscient" / "monitor",
            self.xdg / "lanex" / "monitor",
            self.home / ".local" / "state" / "agentscient" / "monitor",
            self.repo / ".git" / "monitor",
        ]


class OnboardFreshnessEqualAndMismatch(_FreshnessFixture):
    """Exact lines and exits for equal and one-sided mismatch."""

    def test_both_equal_prints_two_lines_no_warning_exit_0(self):
        oids = self.ready_fresh()
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 2, stdout)
        self.assert_freshness_line(
            lines[0],
            ref=DEV_REF,
            local=oids["dev"],
            remote=oids["dev"],
            status="equal",
        )
        self.assert_freshness_line(
            lines[1],
            ref=MASTER_REF,
            local=oids["master"],
            remote=oids["master"],
            status="equal",
        )
        self.assertEqual(self.warning_lines(stdout), [])
        self.assertEqual(self.last_line(stdout), "brief complete")
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_one_ls_remote()
        self.assertNotIn(GIT_SECRET, self.combined(proc))

    def test_dev_only_mismatch_warns_and_exits_0(self):
        oids = self.ready_fresh()
        new_dev = self.advance_origin(DEV, b"live dev drift\n")
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 2, stdout)
        self.assert_freshness_line(
            lines[0],
            ref=DEV_REF,
            local=oids["dev"],
            remote=new_dev,
            status="different",
        )
        self.assert_freshness_line(
            lines[1],
            ref=MASTER_REF,
            local=oids["master"],
            remote=oids["master"],
            status="equal",
        )
        warns = self.warning_lines(stdout)
        self.assertEqual(len(warns), 1, stdout)
        self.assert_warning(warns[0], "different")
        self.assertEqual(self.last_line(stdout), "brief complete")
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_master_only_mismatch_warns_and_exits_0(self):
        oids = self.ready_fresh()
        new_master = self.advance_origin(MASTER, b"live master drift\n")
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 2, stdout)
        self.assert_freshness_line(
            lines[0],
            ref=DEV_REF,
            local=oids["dev"],
            remote=oids["dev"],
            status="equal",
        )
        self.assert_freshness_line(
            lines[1],
            ref=MASTER_REF,
            local=oids["master"],
            remote=new_master,
            status="different",
        )
        warns = self.warning_lines(stdout)
        self.assertEqual(len(warns), 1, stdout)
        self.assert_warning(warns[0], "different")
        self.assertEqual(self.last_line(stdout), "brief complete")
        self.assertEqual(proc.returncode, 0, self.combined(proc))


class OnboardFreshnessMissing(_FreshnessFixture):
    """Each missing-ref state is a warning, not an absence."""

    def test_missing_local_warns_exit_0(self):
        oids = self.ready_fresh()
        self.delete_local_branch(DEV)
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 2, stdout)
        self.assert_freshness_line(
            lines[0],
            ref=DEV_REF,
            local="null",
            remote=oids["dev"],
            status="missing-local",
        )
        warns = self.warning_lines(stdout)
        self.assertEqual(len(warns), 1, stdout)
        self.assert_warning(warns[0], "missing-local")
        self.assertEqual(self.last_line(stdout), "brief complete")
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_missing_remote_warns_exit_0(self):
        oids = self.ready_fresh()
        self.delete_origin_branch(MASTER)
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 2, stdout)
        self.assert_freshness_line(
            lines[1],
            ref=MASTER_REF,
            local=oids["master"],
            remote="null",
            status="missing-remote",
        )
        warns = self.warning_lines(stdout)
        self.assertEqual(len(warns), 1, stdout)
        self.assert_warning(warns[0], "missing-remote")
        self.assertEqual(self.last_line(stdout), "brief complete")
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_missing_both_warns_exit_0(self):
        self.ready_fresh()
        self.delete_local_branch(DEV)
        self.delete_origin_branch(DEV)
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 2, stdout)
        self.assert_freshness_line(
            lines[0],
            ref=DEV_REF,
            local="null",
            remote="null",
            status="missing-both",
        )
        warns = self.warning_lines(stdout)
        self.assertEqual(len(warns), 1, stdout)
        self.assert_warning(warns[0], "missing-both")
        self.assertEqual(self.last_line(stdout), "brief complete")
        self.assertEqual(proc.returncode, 0, self.combined(proc))


class OnboardFreshnessUnavailableAndConfig(_FreshnessFixture):
    """Unavailable branches count absences; bad config is one absence, no query."""

    def test_two_remote_unavailable_readings_are_two_absences_exit_1(self):
        self.ready_fresh()
        self.set_ls_remote(
            mode="exit",
            exit_code=128,
            stdout="",
            stderr=f"fatal: {GIT_SECRET}\n",
        )
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 2, stdout)
        self.assert_freshness_line(
            lines[0],
            ref=DEV_REF,
            local="null",
            remote="null",
            status="remote-unavailable",
        )
        self.assert_freshness_line(
            lines[1],
            ref=MASTER_REF,
            local="null",
            remote="null",
            status="remote-unavailable",
        )
        self.assertIn("remote-unavailable", stdout)
        self.assertEqual(self.last_line(stdout), "brief complete, 2 absence(s)")
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        self.assertNotIn(GIT_SECRET, self.combined(proc))
        self.assert_one_ls_remote()

    def test_missing_registry_is_one_absence_and_zero_queries(self):
        self.ready()
        self.plant_origin_and_trunks()
        for path in (
            self.repo / "ops" / "conductor" / "monitor.example.json",
            self.scratch / "monitor.example.json",
        ):
            self.assertFalse(path.exists(), path)
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 1, stdout)
        self.assertRegex(lines[0], UNAVAIL_CFG_RE)
        self.assertIn("expected", lines[0])
        self.assertIn("found", lines[0])
        self.assertIn("needed", lines[0])
        self.assertEqual(self.warning_lines(stdout), [])
        self.assertEqual(self.last_line(stdout), "brief complete, 1 absence(s)")
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        self.assertEqual(self.ls_remote_argvs(), [])

    def test_disabled_branch_refs_is_one_absence_and_zero_queries(self):
        self.ready()
        self.plant_origin_and_trunks()
        self.plant_default_registry(self.branch_refs_registry(enabled=False))
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 1, stdout)
        self.assertRegex(lines[0], UNAVAIL_CFG_RE)
        self.assertEqual(self.last_line(stdout), "brief complete, 1 absence(s)")
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        self.assertEqual(self.ls_remote_argvs(), [])

    def test_invalid_registry_is_one_absence_and_zero_queries(self):
        self.ready()
        self.plant_origin_and_trunks()
        self.plant_default_registry(
            self.branch_refs_registry(
                params={
                    "repo": "../..",
                    "remote": REMOTE_NAME,
                    "branches": [DEV],
                    "timeout_s": 5,
                }
            )
        )
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 1, stdout)
        self.assertRegex(lines[0], UNAVAIL_CFG_RE)
        self.assertEqual(self.last_line(stdout), "brief complete, 1 absence(s)")
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        self.assertEqual(self.ls_remote_argvs(), [])


class OnboardFreshnessStalePinnedAndIsolation(_FreshnessFixture):
    """Tracking refs, missing objects, detached HEAD, one query, no writes."""

    def test_stale_tracking_and_missing_remote_object_are_live_different(self):
        oids = self.ready_fresh()
        new_dev = self.advance_origin(DEV, b"unfetched live dev\n")
        tracking = self.oid(f"refs/remotes/{REMOTE_NAME}/{DEV}")
        self.assertEqual(tracking, oids["dev"])
        cat = self.git("cat-file", "-t", new_dev, check=False)
        self.assertNotEqual(cat.returncode, 0, cat.stdout)
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 2, stdout)
        self.assert_freshness_line(
            lines[0],
            ref=DEV_REF,
            local=oids["dev"],
            remote=new_dev,
            status="different",
        )
        warns = self.warning_lines(stdout)
        self.assertEqual(len(warns), 1, stdout)
        self.assert_warning(warns[0], "different")
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(self.last_line(stdout), "brief complete")

    def test_detached_head_and_pinned_history_still_print_freshness(self):
        oids = self.ready_fresh()
        pinned = self.oid("HEAD")
        self.git("checkout", "--detach", "HEAD")
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(head, pinned)
        proc = self.invoke()
        stdout = proc.stdout or ""
        lines = self.freshness_lines(stdout)
        self.assertEqual(len(lines), 2, stdout)
        self.assertNotEqual(proc.returncode, 2, self.combined(proc))
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_freshness_line(
            lines[0],
            ref=DEV_REF,
            local=oids["dev"],
            remote=oids["dev"],
            status="equal",
        )
        self.assert_freshness_line(
            lines[1],
            ref=MASTER_REF,
            local=oids["master"],
            remote=oids["master"],
            status="equal",
        )
        self.assertEqual(self.warning_lines(stdout), [])
        self.assertEqual(self.last_line(stdout), "brief complete")
        branch = self.labelled_line(stdout, "branch")
        self.assertIn(pinned[:7], branch)

    def test_one_query_no_monitor_state_byte_identical_repo(self):
        self.ready_fresh()
        extra = self.repo / "dirty-aa41.txt"
        self._plant_bytes(extra, b"dirty\n")
        self.assertEqual(extra.read_bytes(), b"dirty\n")
        before = self.fingerprint()
        before_xdg = _tree_files(self.xdg)
        before_home_state = _tree_files(self.home / ".local" / "state") if (
            self.home / ".local" / "state"
        ).exists() else ()
        proc = self.invoke()
        stdout = proc.stdout or ""
        self.assertEqual(len(self.freshness_lines(stdout)), 2, stdout)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assert_one_ls_remote()
        self.assertEqual(self.fingerprint(), before)
        self.assertEqual(extra.read_bytes(), b"dirty\n")
        self.assertEqual(_tree_files(self.xdg), before_xdg)
        after_home_state = _tree_files(self.home / ".local" / "state") if (
            self.home / ".local" / "state"
        ).exists() else ()
        self.assertEqual(after_home_state, before_home_state)
        for path in self.monitor_state_paths():
            self.assertFalse(path.exists(), f"monitor state created: {path}")
        self.assertTrue(ONBOARD_TOOL.is_file())


if __name__ == "__main__":
    unittest.main()
