"""Managed sessions slice 1: supervisor verbs, refusal classes, fixture set.

Contract: `ops/conductor/sessions-lever.md`. The subject
`ops/conductor/tools/sessions.py` is run as a subprocess through
`ops.testkit.run` with a timeout. A missing tool file is one red
(`test_the_tool_file_is_present`). Every other case runs the real file
when it exists and a no-op stub when it does not, so each assertion
goes red on the contract promise rather than Python's missing-file
exit 2.

The one command that reads this file is
`python3 -m unittest discover -s ops/conductor/tests -p test_sessions.py`.

Calibration gap: planted faults follow the implementation.
``ops/testkit/cases.py`` calibrate anchors each mutant on the subject's
text, and ``ops/conductor/tools/sessions.py`` is absent, so this module
has no mutants file.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import unittest
from pathlib import Path

from ops.testkit import RefusalCase, World, refusal_wire, run, run_table

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "ops" / "conductor" / "tools"
TOOL = TOOLS / "sessions.py"
COORD = TOOLS / "coordination.py"
FAKES = Path(__file__).resolve().parent / "fakes"
HARNESS_SRC = FAKES / "session_harness.py"
TMUX_SRC = FAKES / "session_tmux.py"
ORIGIN = "sessions-lever.md"
FINDING = "20260922T215604Z-review-codex-f6777b"


def origin_finding(number: int) -> str:
    return f"{FINDING}#{number}"
AGENT = "Sessions Tester <noreply@example.test>"
LANE = "sessionstest"
TIMEOUT = 60.0
READY = 15
LEAD_SESSION = "lead-already-bound"
WORKER_SESSION = "worker-already-bound"
HOST_TMUX = shutil.which("tmux")

READINESS = (
    "process",
    "profile",
    "identity",
    "participant",
    "role",
    "tools",
    "ingress",
    "response",
)
SLICE2 = ("tools", "ingress", "response")


def _fake_text(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"INVALID: planted program missing: {path}")
    text = path.read_text(encoding="utf-8")
    if text.startswith("#!"):
        text = text.split("\n", 1)[1]
    return f"#!{sys.executable}\n" + text


def a_team(*members, name: str = "lane", tmux: str = "agentscient") -> dict:
    return {
        "schema": "agentscient-team/1",
        "run": {"name": name, "tmux": tmux},
        "members": list(members),
    }


def claude_member(name: str, roles: list[str]) -> dict:
    return {"name": name, "harness": "claude", "roles": roles}


class ThePresence(unittest.TestCase):
    def test_the_tool_file_is_present(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")


class _Scratch(unittest.TestCase):
    """Hermetic world, planted fake harness, private tmux socket."""

    def setUp(self):
        self.world = World(prefix="sessions-")
        self.addCleanup(self.world.close)
        self.conf = self.world.plant_text("lane.conf", f"LANE_NAME='{LANE}'\n")
        self.xdg = self.world.xdg_state
        self.state = self.xdg / LANE
        self.socket = self.world.tmp / "tmux.sock"
        self.team_path = self.world.plant_text(
            "team.json",
            json.dumps(a_team(claude_member("grunt", ["worker"]))) + "\n",
        )
        self._plant_harness()
        if HOST_TMUX:
            self._plant_tmux()

    def _plant_harness(self, session_id=None) -> Path:
        planted = self.world.tools.plant("claude", script=_fake_text(HARNESS_SRC))
        spec_path = self.world.tools.spec_path("claude")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["session_id"] = session_id
        spec_path.write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
        landed = json.loads(spec_path.read_text(encoding="utf-8"))
        if landed.get("session_id") != session_id:
            raise AssertionError("INVALID: harness spec did not land intact")
        return planted

    def _plant_tmux(self) -> Path:
        log = self.world.root / "fakes" / "tmux.calls.jsonl"
        text = (
            _fake_text(TMUX_SRC)
            .replace("@@TMUX@@", HOST_TMUX)
            .replace("@@LOG@@", str(log))
        )
        return self.world.tools.plant("tmux", script=text)

    def assert_world_roots(self, built: dict[str, str]) -> None:
        """origin: 20260922T215604Z-review-codex-f6777b#1

        The world owns HOME, the XDG roots and the state root. Every row
        asserts on those.
        """
        self.assertEqual(built["HOME"], str(self.world.home))
        self.assertEqual(built["XDG_STATE_HOME"], str(self.world.xdg_state))
        self.assertEqual(built["XDG_CONFIG_HOME"], str(self.world.xdg_config))
        self.assertEqual(built["XDG_CACHE_HOME"], str(self.world.xdg_cache))
        self.assertEqual(self.xdg, self.world.xdg_state)
        self.assertEqual(self.state, self.world.xdg_state / LANE)

    def env(self, *, identity: str | None = AGENT, session: str | None = None,
            extra: dict[str, str] | None = None) -> dict[str, str]:
        payload = {
            "LANE_CONF": str(self.conf),
            "AGENTSCIENT_TMUX_SOCKET": str(self.socket),
            "TESTKIT_FAKE_SPEC": str(self.world.tools.spec_path("claude")),
        }
        if identity:
            payload["WF_AGENT"] = identity
        if session:
            payload["CLAUDE_CODE_SESSION_ID"] = session
            payload["COORDINATION_CAPABILITY"] = hashlib.sha256(
                session.encode()
            ).hexdigest()
        if extra:
            payload.update(extra)
        built = self.world.env(extra=payload)
        self.assert_world_roots(built)
        return built

    def tool_argv(self) -> list[str]:
        if TOOL.is_file():
            return [sys.executable, str(TOOL)]
        return [sys.executable, str(self.world.stage(TOOL))]

    def sessions(self, *argv: str, identity: str | None = AGENT,
                 session: str | None = None, timeout: float = TIMEOUT,
                 extra: dict[str, str] | None = None):
        return run(
            [*self.tool_argv(), *argv],
            cwd=self.world.cwd,
            env=self.env(identity=identity, session=session, extra=extra),
            timeout=timeout,
        )

    def coord(self, *argv: str, session: str = LEAD_SESSION, expect: int | None = 0):
        return run(
            [sys.executable, str(COORD), *argv],
            cwd=self.world.cwd,
            env=self.env(session=session),
            timeout=TIMEOUT,
            expect=expect,
        )

    def plant_team(self, team: dict) -> Path:
        path = self.world.plant_text(
            "team.json", json.dumps(team) + "\n", recognisable=team["schema"]
        )
        self.team_path = path
        return path

    def start_argv(self, member: str = "grunt", *more: str) -> tuple[str, ...]:
        return (
            "start",
            "--member",
            member,
            "--team",
            str(self.team_path),
            "--ready-timeout",
            str(READY),
            *more,
        )

    def skip_without_tmux(self) -> None:
        if not HOST_TMUX:
            raise unittest.SkipTest(
                "tmux is absent; private-socket rows need it"
            )

    def assert_refusal(self, proc, klass: str, *, case_id: str) -> str:
        case = RefusalCase(id=case_id, argv=proc.argv[2:], cls=klass, origin=ORIGIN)
        return refusal_wire(case, proc).line

    def assert_readiness(self, text: str) -> None:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        for dim in READINESS:
            self.assertTrue(
                any(dim in ln for ln in lines),
                f"readiness missing {dim}: {text!r}",
            )
        for dim in SLICE2:
            matching = [ln for ln in lines if dim in ln]
            self.assertTrue(
                any("unmeasured" in ln for ln in matching),
                f"{dim} must read unmeasured: {text!r}",
            )

    def bind_lead(self) -> None:
        self.coord("bind", "--roles", "lead,coordinator", session=LEAD_SESSION)

    def store_who(self, member: str = "grunt") -> str:
        """Roles the coordination store records, read through the core."""
        bindings = list((self.state / "sessions").glob(f"*/{member}/profile/binding.json"))
        self.assertTrue(bindings, f"no binding for {member} under {self.state}")
        binding = json.loads(bindings[0].read_text(encoding="utf-8"))
        cap = binding["coordination_capability"]
        result = run(
            [sys.executable, str(COORD), "who"],
            cwd=self.world.cwd,
            env=self.env(extra={"COORDINATION_CAPABILITY": cap}),
            timeout=TIMEOUT,
        )
        self.assertEqual(result.exit, 0, result.stderr)
        return result.stdout


class TheRefusalTable(_Scratch):
    """One row per refusal class the contract names, addressed by id."""

    def test_writing_without_identity_refuses_identity(self):
        rows = (
            RefusalCase(id="start-without-identity", argv=self.start_argv(),
                        cls="identity", origin=ORIGIN),
            RefusalCase(id="stop-without-identity", argv=("stop",),
                        cls="identity", origin=ORIGIN),
            RefusalCase(id="attach-without-identity",
                        argv=("attach", "--member", "grunt"),
                        cls="identity", origin=ORIGIN),
            RefusalCase(id="export-without-identity",
                        argv=("export", "--to", str(self.world.tmp / "out")),
                        cls="identity", origin=ORIGIN),
        )
        run_table(self, rows, lambda row: self.sessions(*row.argv, identity=None))

    def test_unknown_and_slice2_verbs_refuse_arguments(self):
        rows = (
            RefusalCase(id="unknown-verb", argv=("frobnicate",),
                        cls="arguments", origin=ORIGIN),
            RefusalCase(id="slice2-join", argv=("join",),
                        cls="arguments", origin=ORIGIN,
                        named=("join",)),
            RefusalCase(id="slice2-recover", argv=("recover",),
                        cls="arguments", origin=ORIGIN,
                        named=("recover",)),
            RefusalCase(id="unknown-option", argv=("status", "--nope"),
                        cls="arguments", origin=ORIGIN),
        )
        run_table(self, rows, lambda row: self.sessions(*row.argv))

    def test_malformed_team_files_refuse_team(self):
        cases = (
            ("team-unknown-harness",
             a_team({"name": "co", "harness": "gemini", "roles": ["worker"]})),
            ("team-unknown-role",
             a_team({"name": "co", "harness": "claude", "roles": ["emperor"]})),
            ("team-bad-name",
             a_team({"name": "CO", "harness": "claude", "roles": ["worker"]})),
            ("team-empty-members",
             {"schema": "agentscient-team/1",
              "run": {"name": "lane", "tmux": "agentscient"},
              "members": []}),
        )
        rows = []
        for case_id, team in cases:
            path = self.world.plant_text(
                f"{case_id}.json", json.dumps(team) + "\n"
            )
            rows.append(
                RefusalCase(
                    id=case_id,
                    argv=("start", "--member", "co", "--team", str(path),
                          "--ready-timeout", str(READY)),
                    cls="team",
                    origin=ORIGIN,
                )
            )
        rows.append(
            RefusalCase(
                id="team-unknown-member",
                argv=self.start_argv("nosuch"),
                cls="team",
                origin=ORIGIN,
                named=("nosuch",),
            )
        )
        run_table(self, rows, lambda row: self.sessions(*row.argv))

    def test_status_on_an_absent_store_says_no_runs_and_creates_nothing(self):
        with self.subTest(id="status-no-runs", origin=ORIGIN):
            proc = self.sessions("status", identity=None)
            self.assertEqual(proc.exit, 0, proc.stderr)
            self.assertIn("no runs", proc.stdout)
            self.assertFalse(self.state.exists() and (self.state / "state.db").exists())

    def test_a_corrupt_store_refuses_store(self):
        store = self.state / "state.db"
        store.parent.mkdir(parents=True)
        store.write_text("not a sqlite database\n", encoding="utf-8")
        with self.subTest(id="store-corrupt", origin=ORIGIN):
            proc = self.sessions("status", identity=None)
            self.assert_refusal(proc, "store", case_id="store-corrupt")

    def test_a_worktree_that_is_not_of_this_repository_refuses_worktree(self):
        other = self.world.root / "not-a-worktree"
        other.mkdir()
        with self.subTest(id="worktree-plain-dir", origin=ORIGIN):
            proc = self.sessions(*self.start_argv("grunt", "--worktree", str(other)))
            self.assert_refusal(proc, "worktree", case_id="worktree-plain-dir")

    def test_absent_run_member_and_pane_refuse_absent(self):
        rows = (
            RefusalCase(id="stop-absent-run", argv=("stop", "--run", "R-9"),
                        cls="absent", origin=ORIGIN, named=("R-9",)),
            RefusalCase(id="attach-absent-member",
                        argv=("attach", "--member", "grunt", "--run", "R-9"),
                        cls="absent", origin=ORIGIN),
            RefusalCase(id="export-absent-run",
                        argv=("export", "--run", "R-9", "--to",
                              str(self.world.tmp / "exp")),
                        cls="absent", origin=ORIGIN),
        )
        run_table(self, rows, lambda row: self.sessions(*row.argv))

    def test_doctor_when_tmux_is_absent_reports_missing_tmux(self):
        with self.subTest(id="doctor-tmux-absent", origin=ORIGIN):
            world = World(prefix="sessions-notmux-", host_path=False)
            self.addCleanup(world.close)
            conf = world.plant_text("lane.conf", f"LANE_NAME='{LANE}'\n")
            team = world.plant_text(
                "team.json",
                json.dumps(a_team(claude_member("grunt", ["worker"]))) + "\n",
            )
            argv = (
                [sys.executable, str(TOOL)]
                if TOOL.is_file()
                else [sys.executable, str(world.stage(TOOL))]
            )
            proc = run(
                [*argv, "doctor", "--team", str(team)],
                cwd=world.cwd,
                env=world.env(extra={"LANE_CONF": str(conf)}),
                timeout=TIMEOUT,
            )
            self.assertEqual(proc.exit, 1, proc.stdout + proc.stderr)
            lines = proc.stdout.splitlines()
            self.assertTrue(
                any(ln.startswith("missing tmux:") or ln.startswith("missing tmux ")
                    for ln in lines),
                proc.stdout,
            )


class TheTmuxAndLaunchRows(_Scratch):
    """Fixtures that own a private tmux socket or a launched member."""

    def test_an_unowned_session_of_the_run_name_refuses_ownership(self):
        self.skip_without_tmux()
        with self.subTest(id="unowned-session", origin=ORIGIN):
            name = "agentscient-R-1"
            create = run(
                ["tmux", "-S", str(self.socket), "new-session", "-d", "-s", name],
                cwd=self.world.cwd,
                env=self.world.env(),
                timeout=TIMEOUT,
            )
            self.assertEqual(create.exit, 0, create.stderr)
            proc = self.sessions(*self.start_argv())
            self.assert_refusal(proc, "ownership", case_id="unowned-session")

    def test_native_id_mismatch_refuses_native(self):
        self.skip_without_tmux()
        self._plant_harness(session_id="other-native-id")
        with self.subTest(id="native-mismatch", origin=ORIGIN):
            proc = self.sessions(*self.start_argv())
            self.assert_refusal(proc, "native", case_id="native-mismatch")

    def test_role_above_worker_without_lead_capability_refuses_authority(self):
        self.skip_without_tmux()
        self.plant_team(a_team(claude_member("co", ["lead"])))
        self.bind_lead()
        with self.subTest(id="authority-no-lead-cap", origin=ORIGIN):
            proc = self.sessions(
                *self.start_argv("co"),
                session=WORKER_SESSION,
            )
            line = self.assert_refusal(proc, "authority", case_id="authority-no-lead-cap")
            self.assertIn("coordination.py grant", line)

    def test_timeout_with_no_bind_exits_1_and_status_reads_launched(self):
        self.skip_without_tmux()
        self._plant_harness(session_id="")
        with self.subTest(id="timeout-no-bind", origin=ORIGIN):
            proc = self.sessions(
                "start", "--member", "grunt", "--team", str(self.team_path),
                "--ready-timeout", "1",
            )
            self.assertEqual(proc.exit, 1, proc.stdout + proc.stderr)
            status = self.sessions("status", identity=None)
            self.assertEqual(status.exit, 0, status.stderr)
            self.assertIn("launched", status.stdout)

    def test_a_member_already_launched_refuses_place(self):
        self.skip_without_tmux()
        with self.subTest(id="already-launched", origin=ORIGIN):
            first = self.sessions(*self.start_argv())
            self.assertIn(first.exit, (0, 1), first.stderr)
            proc = self.sessions(*self.start_argv())
            self.assert_refusal(proc, "place", case_id="already-launched")

    def test_prepare_failure_refuses_profile(self):
        with self.subTest(id="profile-prepare", origin=ORIGIN):
            self.plant_team(a_team({
                "name": "grunt",
                "harness": "claude",
                "roles": ["worker"],
                "executable": "/nonexistent/claude-binary",
            }))
            proc = self.sessions(*self.start_argv())
            self.assert_refusal(proc, "profile", case_id="profile-prepare")

    def test_start_without_tmux_on_path_refuses_tmux(self):
        with self.subTest(id="start-tmux-missing", origin=ORIGIN):
            world = World(prefix="sessions-notmux-start-", host_path=False)
            self.addCleanup(world.close)
            conf = world.plant_text("lane.conf", f"LANE_NAME='{LANE}'\n")
            team = world.plant_text(
                "team.json",
                json.dumps(a_team(claude_member("grunt", ["worker"]))) + "\n",
            )
            argv = (
                [sys.executable, str(TOOL)]
                if TOOL.is_file()
                else [sys.executable, str(world.stage(TOOL))]
            )
            proc = run(
                [*argv, "start", "--member", "grunt", "--team", str(team),
                 "--ready-timeout", str(READY)],
                cwd=world.cwd,
                env=world.env(extra={"LANE_CONF": str(conf), "WF_AGENT": AGENT}),
                timeout=TIMEOUT,
            )
            case = RefusalCase(
                id="start-tmux-missing", argv=("start",), cls="tmux", origin=ORIGIN
            )
            refusal_wire(case, proc)


class TheCleanNeighbours(_Scratch):
    """Cold start, populated store, second member, attach, stop, export."""

    def test_cold_start_on_an_empty_store_binds_lead(self):
        self.skip_without_tmux()
        self.plant_team(a_team(claude_member("co", ["lead"])))
        with self.subTest(id="cold-start", origin=ORIGIN):
            proc = self.sessions(*self.start_argv("co"))
            self.assertEqual(proc.exit, 0, proc.stderr)
            self.assertRegex(
                proc.stdout,
                r"started co SM-\d+ as PT-\d+ in R-\d+ pane %\d+ gen \d+",
            )
            self.assert_readiness(proc.stdout)
            who = self.store_who("co")
            self.assertIn("lead", who)

    def test_start_on_a_populated_store_keeps_the_lead_and_binds_worker(self):
        self.skip_without_tmux()
        self.bind_lead()
        with self.subTest(id="populated-store", origin=ORIGIN):
            proc = self.sessions(*self.start_argv("grunt"))
            self.assertEqual(proc.exit, 0, proc.stderr)
            self.assertRegex(
                proc.stdout,
                r"started grunt SM-\d+ as PT-\d+ in R-\d+",
            )
            who = self.store_who("grunt")
            self.assertIn("worker", who)
            lead = self.coord("who", session=LEAD_SESSION)
            self.assertIn("lead", lead.stdout)

    def test_a_second_member_of_the_same_harness_has_distinct_profile_identity_pane(self):
        self.skip_without_tmux()
        self.plant_team(a_team(
            claude_member("co", ["worker"]),
            claude_member("xo", ["worker"]),
        ))
        with self.subTest(id="second-member", origin=ORIGIN):
            first = self.sessions(*self.start_argv("co"))
            self.assertEqual(first.exit, 0, first.stderr)
            second = self.sessions(*self.start_argv("xo", "--run", "R-1"))
            self.assertEqual(second.exit, 0, second.stderr)
            status = self.sessions("status", "--run", "R-1", identity=None)
            self.assertIn("co", status.stdout)
            self.assertIn("xo", status.stdout)
            profiles = list((self.state / "sessions").glob("R-1/*/profile"))
            self.assertGreaterEqual(len(profiles), 2)
            self.assertEqual(len({p.resolve() for p in profiles}), len(profiles))
            panes = [
                ln for ln in status.stdout.splitlines()
                if "pane" in ln and ("co" in ln or "xo" in ln)
            ]
            self.assertGreaterEqual(len(panes), 2)
            self.assertNotEqual(panes[0], panes[1])

    def test_attach_execs_tmux_on_the_owned_window(self):
        self.skip_without_tmux()
        with self.subTest(id="attach", origin=ORIGIN):
            started = self.sessions(*self.start_argv())
            self.assertEqual(started.exit, 0, started.stderr)
            proc = self.sessions("attach", "--member", "grunt")
            self.assertEqual(proc.exit, 0, proc.stderr)
            log = self.world.root / "fakes" / "tmux.calls.jsonl"
            self.assertTrue(log.is_file(), "tmux shim did not log")
            calls = [
                json.loads(ln)["argv"]
                for ln in log.read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
            self.assertTrue(
                any("attach-session" in c or (c and c[0] == "attach") for c in calls),
                calls,
            )

    def test_a_clean_stop_terminates_the_owned_pid(self):
        self.skip_without_tmux()
        with self.subTest(id="clean-stop", origin=ORIGIN):
            started = self.sessions(*self.start_argv())
            self.assertEqual(started.exit, 0, started.stderr)
            proc = self.sessions("stop", "--terminate")
            self.assertEqual(proc.exit, 0, proc.stderr)
            self.assertIn("stopped", proc.stdout)
            status = self.sessions("status", identity=None)
            self.assertIn("stopped", status.stdout)

    def test_a_full_export_omits_capability_and_credential_values(self):
        self.skip_without_tmux()
        dest = self.world.root / "export"
        with self.subTest(id="full-export", origin=ORIGIN):
            started = self.sessions(*self.start_argv())
            self.assertEqual(started.exit, 0, started.stderr)
            secret = None
            bindings = list((self.state / "sessions").glob("*/grunt/profile/binding.json"))
            if bindings:
                secret = json.loads(bindings[0].read_text(encoding="utf-8")).get(
                    "coordination_capability"
                )
            proc = self.sessions("export", "--to", str(dest))
            self.assertEqual(proc.exit, 0, proc.stderr)
            self.assertRegex(proc.stdout, r"exported .+ \(\d+ members, \d+ files\)")
            self.assertTrue((dest / "run.json").is_file())
            blob = ""
            for path in dest.rglob("*"):
                if path.is_file():
                    blob += path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("coordination_capability", blob)
            if secret:
                self.assertNotIn(secret, blob)

    def test_unreadable_diagnostics_on_export_exits_1_and_names_the_failure(self):
        self.skip_without_tmux()
        dest = self.world.root / "export-partial"
        with self.subTest(id="export-unreadable-diagnostics", origin=ORIGIN):
            started = self.sessions(*self.start_argv())
            self.assertEqual(started.exit, 0, started.stderr)
            evidence = list((self.state / "sessions").glob("*/grunt"))
            self.assertTrue(evidence, "no member evidence directory")
            target = evidence[0] / "pane.log"
            target.write_text("capture\n", encoding="utf-8")
            target.chmod(0)
            proc = self.sessions("export", "--to", str(dest))
            target.chmod(0o644)
            self.assertEqual(proc.exit, 1, proc.stdout + proc.stderr)
            self.assertTrue(proc.stdout.strip() or proc.stderr.strip())

    def test_stop_terminate_does_not_signal_a_reused_pid(self):
        self.skip_without_tmux()
        with self.subTest(id="stale-pid-stop", origin=ORIGIN):
            started = self.sessions(*self.start_argv())
            self.assertIn(started.exit, (0, 1), started.stderr)
            status = self.sessions("status", identity=None)
            recorded = None
            for token in status.stdout.replace("=", " ").split():
                if token.isdigit() and int(token) > 1:
                    recorded = int(token)
                    break
            canary = self.world.own(
                subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(3600)"],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
            if recorded:
                with contextlib.suppress(OSError):
                    os.kill(recorded, signal.SIGKILL)
            holder = canary
            if recorded and canary.pid != recorded:
                for _ in range(64):
                    child = self.world.own(
                        subprocess.Popen(
                            [sys.executable, "-c", "import time; time.sleep(3600)"],
                            start_new_session=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    )
                    if child.pid == recorded:
                        holder = child
                        break
                    self.world.reap(child)
            proc = self.sessions("stop", "--terminate")
            self.assertIsNone(holder.poll(), "the world-owned pid was signalled")
            combined = proc.stdout + proc.stderr
            self.assertIn("stale pid", combined)
            self.assertIn("unresolved", combined)


class TheDoctorDefaultTeam(_Scratch):
    def test_doctor_reports_missing_adapter_for_codex_and_grok(self):
        with self.subTest(id="doctor-missing-adapter", origin=ORIGIN):
            team = a_team(
                claude_member("co", ["lead"]),
                {"name": "dispatcher", "harness": "codex", "roles": ["dispatcher"]},
                {"name": "grunt", "harness": "grok", "roles": ["worker"]},
            )
            path = self.plant_team(team)
            proc = self.sessions("doctor", "--team", str(path), identity=None)
            self.assertEqual(proc.exit, 1, proc.stdout)
            text = proc.stdout
            self.assertIn("adapter", text)
            self.assertTrue("codex" in text and "grok" in text, text)


if __name__ == "__main__":
    unittest.main()
