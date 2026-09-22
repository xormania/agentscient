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
import re
import shutil
import signal
import sys
import threading
import time
import unittest
from pathlib import Path

from ops.testkit import RefusalCase, Watch, World, refusal_wire, run, run_table

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
    def test_the_tool_executes_status_on_an_absent_store(self):
        """origin: 20260922T215604Z-review-codex-f6777b#2

        The case runs the subject. An empty file exits 0 with no reading;
        status on an absent store says ``no runs`` and creates nothing.
        """
        world = World(prefix="sessions-presence-")
        self.addCleanup(world.close)
        conf = world.plant_text("lane.conf", f"LANE_NAME='{LANE}'\n")
        argv = (
            [sys.executable, str(TOOL)]
            if TOOL.is_file()
            else [sys.executable, str(world.stage(TOOL))]
        )
        proc = run(
            [*argv, "status"],
            cwd=world.cwd,
            env=world.env(extra={"LANE_CONF": str(conf)}),
            timeout=TIMEOUT,
        )
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertIn("no runs", proc.stdout)
        state = world.xdg_state / LANE
        self.assertFalse(state.exists(), f"status created {state}")


class _Scratch(unittest.TestCase):
    """Hermetic world, planted fake harness, private tmux socket."""

    def open_world(self, prefix: str) -> World:
        """A world rooted under /tmp, so the private tmux socket it owns
        stays under 108 bytes. origin: 20260922T215604Z-review-codex-f6777b#10
        """
        saved = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = "/tmp"
        try:
            return World(prefix=prefix)
        finally:
            if saved is None:
                os.environ.pop("TMPDIR", None)
            else:
                os.environ["TMPDIR"] = saved

    def setUp(self):
        self.world = self.open_world("sessions-")
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
        text = _fake_text(HARNESS_SRC).replace("@@REPO@@", str(REPO))
        planted = self.world.tools.plant("claude", script=text)
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
            .replace("@@REPO@@", str(REPO))
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

    def _alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def owned_holder(self) -> tuple[int, object]:
        """A sleeper started through ops.testkit.run with a timeout.

        origin: 20260922T215604Z-review-codex-f6777b#18
        origin: 20260922T215604Z-review-codex-f6777b#19
        """
        nonce = str(time.time_ns())
        ready = self.world.tmp / f"holder-{nonce}.ready"
        stop = self.world.tmp / f"holder-{nonce}.stop"
        script = (
            f"#!{sys.executable}\n"
            "import os, time, pathlib\n"
            f"pathlib.Path({str(ready)!r}).write_text(str(os.getpid()))\n"
            f"stop = pathlib.Path({str(stop)!r})\n"
            "while not stop.exists():\n"
            "    time.sleep(0.05)\n"
        )
        self.world.tools.plant("holder", script=script)
        box: dict = {}

        def invoke() -> None:
            try:
                box["result"] = run(
                    [str(self.world.bin / "holder")],
                    cwd=self.world.cwd,
                    env=self.world.env(),
                    timeout=120,
                )
            except Exception as exc:
                box["error"] = exc

        thread = threading.Thread(target=invoke)
        thread.start()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not ready.is_file():
            time.sleep(0.02)
        self.assertTrue(
            ready.is_file(),
            f"holder was not started through ops.testkit.run: {box!r}",
        )
        pid = int(ready.read_text(encoding="utf-8"))

        def release() -> None:
            if not stop.exists():
                stop.write_text("stop\n", encoding="utf-8")
            thread.join(timeout=15)
            if self._alive(pid):
                with contextlib.suppress(OSError):
                    os.kill(pid, signal.SIGTERM)

        self.addCleanup(release)
        return pid, release

    def skip_without_tmux(self) -> None:
        if not HOST_TMUX:
            raise unittest.SkipTest(
                "tmux is absent; private-socket rows need it"
            )

    def assert_refusal(self, proc, klass: str, *, case_id: str) -> str:
        case = RefusalCase(id=case_id, argv=proc.argv[2:], cls=klass, origin=ORIGIN)
        return refusal_wire(case, proc).line

    def assert_readiness(self, text: str) -> None:
        """origin: 20260922T215604Z-review-codex-f6777b#11

        ``ready`` requires process, profile, identity, participant and
        role to read ok, never waiting or refused. Slice 2 reads
        unmeasured and never ok.
        """
        found = {dim: [] for dim in READINESS}
        pattern = re.compile(
            "(?:^|\\s)(process|profile|identity|participant|role|tools|ingress|response)"
            "\\s*:?\\s*(ok|waiting|refused|unmeasured)\\b"
        )
        for line in text.splitlines():
            for match in pattern.finditer(line):
                found[match.group(1)].append(match.group(2))
        for dim in ("process", "profile", "identity", "participant", "role"):
            states = found[dim]
            self.assertIn("ok", states, f"{dim} must read ok, found {states!r} in {text!r}")
            self.assertNotIn("waiting", states, f"{dim} reads waiting: {text!r}")
            self.assertNotIn("refused", states, f"{dim} reads refused: {text!r}")
        for dim in SLICE2:
            states = found[dim]
            self.assertIn("unmeasured", states, f"{dim} must read unmeasured: {text!r}")
            self.assertNotIn("ok", states, f"{dim} is slice 2 and never reads ok: {text!r}")

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
        """Declared gap: planted faults follow the implementation; no mutants file.

        origin: 20260922T215604Z-review-codex-f6777b#3
        A writing verb whose WF_AGENT is absent, or present but not
        ``Name <address>``, refuses identity.
        """
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
            RefusalCase(id="start-bare-name", argv=self.start_argv(),
                        cls="identity", origin=origin_finding(3),
                        note="JustAName"),
            RefusalCase(id="stop-address-without-domain", argv=("stop",),
                        cls="identity", origin=origin_finding(3),
                        note="Name <noreply>"),
            RefusalCase(id="attach-name-without-brackets",
                        argv=("attach", "--member", "grunt"),
                        cls="identity", origin=origin_finding(3),
                        note="Sessions Tester noreply@example.test"),
        )

        def invoke(row):
            return self.sessions(*row.argv, identity=row.note)

        run_table(self, rows, invoke)

    def test_unknown_and_slice2_verbs_refuse_arguments(self):
        """Declared gap: planted faults follow the implementation; no mutants file.

        origin: 20260922T215604Z-review-codex-f6777b#4
        An undeclared verb and option, neither of them the four examples
        frobnicate, join, recover and --nope, refuse arguments.
        """
        extra_verb = "v" + hashlib.sha256(b"sessions-lever arguments").hexdigest()[:12]
        extra_option = "--" + hashlib.sha256(b"sessions-lever option").hexdigest()[:12]
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
            RefusalCase(id="undeclared-verb", argv=(extra_verb,),
                        cls="arguments", origin=origin_finding(4),
                        named=(extra_verb,)),
            RefusalCase(id="undeclared-option", argv=("doctor", extra_option),
                        cls="arguments", origin=origin_finding(4),
                        named=(extra_option,)),
        )
        run_table(self, rows, lambda row: self.sessions(*row.argv))

    def test_malformed_team_files_refuse_team(self):
        """origin: 20260922T215604Z-review-codex-f6777b#5

        Duplicate names, empty roles, a relative executable and an
        undeclared key refuse team, with the shapes the contract already
        names.
        """
        cases = (
            ("team-unknown-harness", ORIGIN,
             a_team({"name": "co", "harness": "gemini", "roles": ["worker"]})),
            ("team-unknown-role", ORIGIN,
             a_team({"name": "co", "harness": "claude", "roles": ["emperor"]})),
            ("team-bad-name", ORIGIN,
             a_team({"name": "CO", "harness": "claude", "roles": ["worker"]})),
            ("team-empty-members", ORIGIN,
             {"schema": "agentscient-team/1",
              "run": {"name": "lane", "tmux": "agentscient"},
              "members": []}),
            ("team-duplicate-name", origin_finding(5),
             a_team(claude_member("co", ["worker"]),
                    claude_member("co", ["worker"]))),
            ("team-empty-roles", origin_finding(5),
             a_team({"name": "co", "harness": "claude", "roles": []})),
            ("team-relative-executable", origin_finding(5),
             a_team({"name": "co", "harness": "claude", "roles": ["worker"],
                     "executable": "claude"})),
            ("team-undeclared-key", origin_finding(5),
             a_team({"name": "co", "harness": "claude", "roles": ["worker"],
                     "model": "unwanted"})),
        )
        rows = []
        for case_id, origin, team in cases:
            path = self.world.plant_text(
                f"{case_id}.json", json.dumps(team) + "\n"
            )
            rows.append(
                RefusalCase(
                    id=case_id,
                    argv=("start", "--member", "co", "--team", str(path),
                          "--ready-timeout", str(READY)),
                    cls="team",
                    origin=origin,
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
        """origin: 20260922T215604Z-review-codex-f6777b#7

        A read says ``no runs`` and creates no state directory, sessions
        directory, database, or any other artifact under the state root.
        While the subject is absent the row runs a stand-in that prints
        the reading and creates those artifacts, so the watch is what
        goes red.
        """
        if TOOL.is_file():
            argv = [sys.executable, str(TOOL)]
        else:
            stand = self.world.plant_text(
                "status-creates.py",
                "import os, pathlib, sys\n"
                f"root = pathlib.Path(os.environ['XDG_STATE_HOME']) / {LANE!r}\n"
                "root.mkdir(parents=True)\n"
                "(root / 'sessions').mkdir()\n"
                "sys.stdout.write('no runs\\n')\n",
            )
            argv = [sys.executable, str(stand)]
        watch = Watch([self.xdg])
        proc = run(
            [*argv, "status"],
            cwd=self.world.cwd,
            env=self.env(identity=None),
            timeout=TIMEOUT,
        )
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertIn("no runs", proc.stdout)
        with self.subTest(id="status-creates-nothing", origin=origin_finding(7)):
            watch.assert_unchanged(self, "status created a store artifact")
            self.assertFalse(self.state.exists())
            self.assertFalse((self.state / "sessions").exists())
            self.assertFalse((self.state / "state.db").exists())

    def test_a_corrupt_store_refuses_store(self):
        store = self.state / "state.db"
        store.parent.mkdir(parents=True)
        store.write_text("not a sqlite database\n", encoding="utf-8")
        with self.subTest(id="store-corrupt", origin=ORIGIN):
            proc = self.sessions("status", identity=None)
            self.assert_refusal(proc, "store", case_id="store-corrupt")

    def test_a_worktree_that_is_not_of_this_repository_refuses_worktree(self):
        """origin: 20260922T215604Z-review-codex-f6777b#8

        A plain directory refuses worktree, and so does a git worktree
        whose common directory is another repository.
        """
        other = self.world.root / "not-a-worktree"
        other.mkdir()
        with self.subTest(id="worktree-plain-dir", origin=ORIGIN):
            proc = self.sessions(*self.start_argv("grunt", "--worktree", str(other)))
            self.assert_refusal(proc, "worktree", case_id="worktree-plain-dir")
        repo = self.world.root / "other-repo"
        repo.mkdir()
        env = self.world.env()
        run(["git", "init", "-b", "main"], cwd=repo, env=env, timeout=TIMEOUT, expect=0)
        run(["git", "commit", "--allow-empty", "-m", "other"], cwd=repo, env=env, timeout=TIMEOUT, expect=0)
        wt = self.world.root / "other-wt"
        run(["git", "worktree", "add", "--detach", str(wt), "HEAD"], cwd=repo, env=env, timeout=TIMEOUT, expect=0)
        inside = run(
            ["git", "-C", str(wt), "rev-parse", "--is-inside-work-tree"],
            cwd=self.world.cwd, env=env, timeout=TIMEOUT, expect=0,
        )
        self.assertEqual(inside.stdout.strip(), "true")
        other_common = run(
            ["git", "-C", str(wt), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=self.world.cwd, env=env, timeout=TIMEOUT, expect=0,
        )
        this_common = run(
            ["git", "-C", str(REPO), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=self.world.cwd, env=env, timeout=TIMEOUT, expect=0,
        )
        self.assertNotEqual(other_common.stdout.strip(), this_common.stdout.strip())
        with self.subTest(id="worktree-other-repository", origin=origin_finding(8)):
            proc = self.sessions(*self.start_argv("grunt", "--worktree", str(wt)))
            self.assert_refusal(proc, "worktree", case_id="worktree-other-repository")

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

    def test_a_missing_member_or_pane_of_an_existing_run_refuses_absent(self):
        """origin: 20260922T215604Z-review-codex-f6777b#6

        A run that exists still refuses absent for a member it does not
        contain, and for a member whose pane is gone.
        """
        self.skip_without_tmux()
        self.sessions(*self.start_argv())
        with self.subTest(id="absent-member-existing-run", origin=origin_finding(6)):
            proc = self.sessions("attach", "--member", "nosuch", "--run", "R-1")
            refusal_wire(
                RefusalCase(
                    id="absent-member-existing-run",
                    argv=("attach", "--member", "nosuch", "--run", "R-1"),
                    cls="absent",
                    origin=origin_finding(6),
                    named=("nosuch",),
                ),
                proc,
            )
        with self.subTest(id="absent-pane-existing-run", origin=origin_finding(6)):
            self.drop_owned_pane("grunt")
            proc = self.sessions("attach", "--member", "grunt", "--run", "R-1")
            refusal_wire(
                RefusalCase(
                    id="absent-pane-existing-run",
                    argv=("attach", "--member", "grunt", "--run", "R-1"),
                    cls="absent",
                    origin=origin_finding(6),
                    named=("grunt",),
                ),
                proc,
            )

    def drop_owned_pane(self, member: str) -> None:
        """Kill the member's pane when the private server has one."""
        listed = run(
            ["tmux", "-S", str(self.socket), "list-panes", "-a",
             "-F", "#{window_name} #{pane_id}"],
            cwd=self.world.cwd,
            env=self.world.env(),
            timeout=TIMEOUT,
        )
        if listed.exit != 0:
            return
        for line in listed.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] == member:
                run(
                    ["tmux", "-S", str(self.socket), "kill-pane", "-t", parts[1]],
                    cwd=self.world.cwd,
                    env=self.world.env(),
                    timeout=TIMEOUT,
                )

    def test_an_unowned_session_of_the_run_name_refuses_ownership(self):
        self.skip_without_tmux()
        with self.subTest(id="unowned-session", origin=origin_finding(10)):
            self.assertLess(
                len(os.fsencode(str(self.socket))),
                108,
                f"private tmux socket must be under 108 bytes: {self.socket}",
            )
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

    def test_ready_while_process_is_not_ok_refuses_readiness(self):
        """origin: 20260922T215604Z-review-codex-f6777b#9

        The planted harness exits after bind, so process is not ok.
        start must refuse readiness rather than report ready.
        """
        self.skip_without_tmux()
        text = _fake_text(HARNESS_SRC)
        marker = "@@REPO@@"
        if text.count(marker) != 1:
            raise AssertionError("INVALID: harness repo anchor")
        at = text.index(marker)
        text = text[:at] + str(REPO) + text[at + len(marker):]
        hold = "    hold()\n"
        if text.count(hold) != 1:
            raise AssertionError("INVALID: harness hold anchor")
        at = text.index(hold)
        text = text[:at] + "    return 0\n" + text[at + len(hold):]
        self.world.tools.plant("claude", script=text)
        proc = self.sessions(*self.start_argv())
        refusal_wire(
            RefusalCase(
                id="readiness-process-not-ok",
                argv=self.start_argv(),
                cls="readiness",
                origin=origin_finding(9),
                named=("process",),
            ),
            proc,
        )

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
        with self.subTest(id="cold-start", origin=origin_finding(11)):
            proc = self.sessions(*self.start_argv("co"))
            self.assertEqual(proc.exit, 0, proc.stderr)
            self.assert_readiness(proc.stdout)
            self.assertRegex(
                proc.stdout,
                r"started co SM-\d+ as PT-\d+ in R-\d+ pane %\d+ gen \d+",
            )
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

    def identity_oks(self, text: str) -> list[str]:
        """Session ids from ``identity ok <id>`` lines."""
        found = []
        for line in text.splitlines():
            match = re.search(r"\bidentity\s*:?\s*ok\s+(\S+)", line)
            if match:
                found.append(match.group(1))
        return found

    def launch_ids(self, run: str) -> list[str]:
        """Launch identities recorded under the run, one per member."""
        root = self.state / "sessions" / run
        found = []
        if not root.is_dir():
            return found
        for path in sorted(root.glob("*/launch.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            for key in ("launch_id", "launch-id", "launch id"):
                value = data.get(key)
                if value:
                    found.append(str(value))
                    break
        return found

    def test_a_second_member_of_the_same_harness_has_distinct_profile_identity_pane(self):
        """origin: 20260922T215604Z-review-codex-f6777b#12

        The second member's launch identity and native identity differ
        from the first member's.
        """
        self.skip_without_tmux()
        self.plant_team(a_team(
            claude_member("co", ["worker"]),
            claude_member("xo", ["worker"]),
        ))
        with self.subTest(id="second-member", origin=origin_finding(12)):
            first = self.sessions(*self.start_argv("co"))
            self.assertEqual(first.exit, 0, first.stderr)
            second = self.sessions(*self.start_argv("xo", "--run", "R-1"))
            self.assertEqual(second.exit, 0, second.stderr)
            first_native = self.identity_oks(first.stdout)
            second_native = self.identity_oks(second.stdout)
            self.assertEqual(len(first_native), 1, f"first identity: {first.stdout!r}")
            self.assertEqual(len(second_native), 1, f"second identity: {second.stdout!r}")
            self.assertNotEqual(first_native[0], second_native[0])
            launches = self.launch_ids("R-1")
            self.assertEqual(len(launches), 2, f"launch identities: {launches!r}")
            self.assertNotEqual(launches[0], launches[1])
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
        """origin: 20260922T215604Z-review-codex-f6777b#13

        attach-session uses the run's socket, the run's session name,
        and the member's window.
        """
        self.skip_without_tmux()
        with self.subTest(id="attach", origin=origin_finding(13)):
            started = self.sessions(*self.start_argv())
            self.assertEqual(started.exit, 0, started.stderr)
            proc = self.sessions("attach", "--member", "grunt")
            self.assertEqual(proc.exit, 0, proc.stderr)
            run_id = "R-1"
            match = re.search(r"\b(R-\d+)\b", started.stdout)
            if match:
                run_id = match.group(1)
            session = f"agentscient-{run_id}"
            window = "grunt"
            log = self.world.root / "fakes" / "tmux.calls.jsonl"
            calls = []
            if log.is_file():
                calls = [
                    json.loads(line)["argv"]
                    for line in log.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            matched = []
            for argv in calls:
                if "attach-session" not in argv and not (argv and argv[0] == "attach"):
                    continue
                if str(self.socket) not in argv:
                    continue
                if not any(session in part for part in argv):
                    continue
                if not any(window in part for part in argv):
                    continue
                matched.append(argv)
            self.assertTrue(
                matched,
                f"attach-session on {self.socket} at {session} window {window}: {calls}",
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

    def _plant_export_canaries(self, member: str) -> list[str]:
        """origin: 20260922T215604Z-review-codex-f6777b#15

        The binding's coordination_capability and every
        credential_environment value, with a canary planted before export.
        """
        bindings = list((self.state / "sessions").glob(f"*/{member}/profile/binding.json"))
        if not bindings:
            return []
        binding = json.loads(bindings[0].read_text(encoding="utf-8"))
        if not isinstance(binding, dict):
            return []
        capability = binding.get("coordination_capability")
        if not isinstance(capability, str) or not capability:
            capability = "capability-canary-a8b48e-not-for-export"
            binding["coordination_capability"] = capability
        raw = binding.get("credential_environment")
        if not isinstance(raw, dict):
            raw = {}
        raw["TEST_CREDENTIAL"] = "credential-canary-a8b48e-not-for-export"
        binding["credential_environment"] = raw
        bindings[0].write_text(json.dumps(binding), encoding="utf-8")
        values = [capability]
        for value in raw.values():
            if value is None:
                continue
            rendered = str(value)
            if rendered:
                values.append(rendered)
        return values

    def test_a_full_export_omits_capability_and_credential_values(self):
        """origin: 20260922T215604Z-review-codex-f6777b#15"""
        self.skip_without_tmux()
        dest = self.world.root / "export"
        with self.subTest(id="full-export", origin=origin_finding(15)):
            started = self.sessions(*self.start_argv())
            self.assertEqual(started.exit, 0, started.stderr)
            secrets = self._plant_export_canaries("grunt")
            proc = self.sessions("export", "--to", str(dest))
            self.assertEqual(proc.exit, 0, proc.stderr)
            self.assertTrue(
                any(item.is_file() for item in dest.rglob("pane.log")),
                "pane capture is present",
            )
            self.assertTrue(
                any(item.is_file() for item in dest.rglob("launch.json")),
                "launch.json is present",
            )
            diags = [item for item in dest.rglob("diagnostics.json") if item.is_file()]
            self.assertTrue(diags, "adapter diagnostics are present")
            for diag in diags:
                listed = json.loads(diag.read_text(encoding="utf-8"))
                self.assertIsInstance(listed, list)
                self.assertTrue(listed, f"adapter diagnostics empty: {diag}")
                for item in listed:
                    name = Path(str(item)).name
                    self.assertTrue(
                        any(found.is_file() and found.name == name for found in dest.rglob(name)),
                        f"retained diagnostic missing from export: {item}",
                    )
            self.assertRegex(proc.stdout, r"exported .+ \(\d+ members, \d+ files\)")
            self.assertTrue((dest / "run.json").is_file(), "run.json is present")
            self.assertTrue(
                secrets,
                "coordination_capability and credential_environment values are known",
            )
            pieces = []
            for exported in dest.rglob("*"):
                pieces.append(str(exported))
                if exported.is_file():
                    pieces.append(exported.read_text(encoding="utf-8", errors="replace"))
            blob = "\n".join(pieces)
            for secret in secrets:
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
        with self.subTest(id="stale-pid-stop", origin=origin_finding(18)):
            started = self.sessions(*self.start_argv())
            self.assertIn(started.exit, (0, 1), started.stderr)
            status = self.sessions("status", identity=None)
            recorded = None
            for token in status.stdout.replace("=", " ").split():
                if token.isdigit() and int(token) > 1:
                    recorded = int(token)
                    break
            canary_pid, _release_canary = self.owned_holder()
            if recorded:
                with contextlib.suppress(OSError):
                    os.kill(recorded, signal.SIGKILL)
            holder: object = canary_pid
            if recorded and canary_pid != recorded:
                for _ in range(64):
                    child_pid, release_child = self.owned_holder()
                    if child_pid == recorded:
                        holder = child_pid
                        break
                    release_child()
            proc = self.sessions("stop", "--terminate")
            self.assertTrue(self._alive(int(holder)), "the world-owned pid was signalled")
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
