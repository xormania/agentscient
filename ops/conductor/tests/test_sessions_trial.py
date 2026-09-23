"""Slice 4 rows: the trial verbs, the owner's terminals, stop accounting,
the run export, the trial record.

Contract: ops/conductor/sessions-lever.md section "Slice 4 — operational
trial and closure", read at 293d4d25 (the gaps closed at 26c94c5a). Run
from the repository root:
python3 -m unittest discover -s ops/conductor/tests -p test_sessions_trial.py

The section names this module as slice 4's one suite. Its rows: the four
refusals (`objective`, `acceptance`, `evidence`, `export`) on the verbs the
section names, the trial record's shape, step 8's accounting, the ninth
`enforcement` line, and the owner's-terminal clause. The owner's-terminal
rows stay red until the wall session lands the `bind` minting in
instrument.py (a wall path, LD-125). The controlled cases' readings are
the verifier's; these rows carry their fixture shape.

Planted faults: sessions_trial_faults.py beside this module, anchored on
sessions.py; its docstring names the calibrate command. A declared gap
until calibrated: every row is red on the subject, so the clean run is
red and calibrate reports ok false.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from ops.testkit import RefusalCase, World, refusal_wire, run, run_table

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "ops" / "conductor" / "tools"
TOOL = TOOLS / "sessions.py"
COORD = TOOLS / "coordination.py"
FAKES = Path(__file__).resolve().parent / "fakes"
HANDOFF = REPO / "ops" / "conductor" / "handoff"
LANE = "agentscient"
TIMEOUT = 45.0
READY = 15
DRAIN = 12
AGENT = "Sessions Tester <noreply@example.test>"
LEAD_SESSION = "lead-already-bound"
OWNER_SESSION = "owner-plain-terminal"
SHORT_ROOT = "/tmp"
SOCKET_LIMIT = 108
HOST_TMUX = shutil.which("tmux")
READINESS = (
    "process", "profile", "identity", "participant",
    "role", "tools", "ingress", "response",
)
IDS = tuple(f"I-{n:02d}" for n in range(1, 15))
ISO_UTC = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)"
VERIFIED = "a" * 40
MOVED = "b" * 40
CLAUSE = "ops/conductor/tools/coordination.py:100"
RECORD_ID = "20260923T090000Z-trial-claude-5a4e01"


def origin(part: str) -> str:
    return f"sessions-lever.md#slice-4 {part}"


def shebang(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("#!"):
        text = text.split("\n", 1)[1]
    return f"#!{sys.executable}\n" + text


def substitute(text: str, anchor: str, value: str, *, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise AssertionError(f"INVALID: {label} {anchor} count is {count}")
    return text.replace(anchor, value)


def a_team(*names: str) -> dict:
    return {
        "schema": "agentscient-team/1",
        "run": {"name": "lane", "tmux": "agentscient"},
        "members": [{"name": name, "harness": "claude", "roles": ["worker"]} for name in names],
    }


def member_block(status: str, name: str) -> str:
    """The status lines of one member: its header and the indented lines under it."""
    lines = status.splitlines()
    for index, line in enumerate(lines):
        if re.match(rf"R-\d+ {re.escape(name)} SM-\d+ ", line):
            block = [line]
            for more in lines[index + 1:]:
                if not more.startswith("  "):
                    break
                block.append(more)
            return "\n".join(block)
    raise AssertionError(f"no status block for {name}:\n{status}")


def stop_line(text: str, name: str) -> str:
    """The accounting line `stop` prints for one member, never its inform line."""
    found = [line for line in text.splitlines()
             if re.match(rf"R-\d+ {re.escape(name)} SM-\d+ ", line)
             and "stop requested" not in line]
    if len(found) != 1:
        raise AssertionError(f"expected one stop line for {name}, found {len(found)}:\n{text}")
    return found[0]


def trial_table(rows: dict[str, tuple[str, str, str]] | None = None) -> str:
    """A trial record: fourteen rows, each read, I-10 and I-14 naming the
    verified sha and reading refused for both controlled cases. `rows`
    replaces a row's (required, evidence, reading) by id."""
    cells = {key: (f"the {key} requirement", f"P-sessions4-{key}", f"measured {key} exit 0")
             for key in IDS}
    for key in ("I-10", "I-14"):
        cells[key] = (f"the {key} requirement",
                      f"ops/conductor/handoff/verifier.md@{VERIFIED}",
                      "refused acceptance omitted; refused acceptance changed")
    cells.update(rows or {})
    lines = ["# Slice 4 trial", "", "| id | required result | evidence | reading |",
             "|---|---|---|---|"]
    lines += [f"| {key} | {req} | {ev} | {rd} |" for key, (req, ev, rd) in cells.items()]
    return "\n".join(lines) + "\n"


class _Trial(unittest.TestCase):
    """A private world with a planted claude harness and tmux; rows start
    one managed member and join a bound participant beside it."""

    def setUp(self):
        saved = tempfile.tempdir
        tempfile.tempdir = SHORT_ROOT
        try:
            self.world = World(prefix="s4trial-")
        finally:
            tempfile.tempdir = saved
        self.addCleanup(self.world.close)
        self.addCleanup(self.stop_server)
        self.conf = self.world.plant_text("lane.conf", f"LANE_NAME='{LANE}'\n")
        self.state = self.world.xdg_state / LANE
        self.socket = self.world.tmp / "tmux.sock"
        if len(os.fsencode(str(self.socket))) >= SOCKET_LIMIT:
            raise AssertionError(f"INVALID: private tmux socket must be under {SOCKET_LIMIT} bytes")
        self.plant_team("co")
        text = substitute(shebang(FAKES / "session_harness.py"), "@@REPO@@", str(REPO), label="harness")
        self.world.tools.plant("claude", script=text)
        if HOST_TMUX:
            log = self.world.root / "fakes" / "tmux.calls.jsonl"
            text = shebang(FAKES / "session_tmux.py")
            text = substitute(text, "@@TMUX@@", HOST_TMUX, label="tmux")
            text = substitute(text, "@@LOG@@", str(log), label="tmux")
            text = substitute(text, "@@REPO@@", str(REPO), label="tmux")
            self.world.tools.plant("tmux", script=text)

    def stop_server(self) -> None:
        if HOST_TMUX and self.socket.exists():
            run([HOST_TMUX, "-S", str(self.socket), "kill-server"],
                cwd=self.world.cwd, env=self.world.env(), timeout=TIMEOUT)

    def skip_without_tmux(self) -> None:
        if not HOST_TMUX:
            raise unittest.SkipTest("tmux is absent; private-socket rows need it")

    def plant_team(self, *names: str) -> None:
        team = a_team(*names)
        self.team_path = self.world.plant_text(
            "team.json", json.dumps(team) + "\n", recognisable=team["schema"])

    def env(self, *, identity: str | None = AGENT, session: str | None = None,
            capability: str | None = None, extra: dict | None = None) -> dict:
        """No capability unless one is named: a plain terminal carries none."""
        payload = {
            "LANE_CONF": str(self.conf),
            "AGENTSCIENT_TMUX_SOCKET": str(self.socket),
            "TESTKIT_FAKE_SPEC": str(self.world.tools.spec_path("claude")),
        }
        if identity:
            payload["WF_AGENT"] = identity
        if session:
            payload["CLAUDE_CODE_SESSION_ID"] = session
        if capability:
            payload["COORDINATION_CAPABILITY"] = capability
        if extra:
            payload.update(extra)
        built = self.world.env(extra=payload)
        self.assertEqual(built["HOME"], str(self.world.home))
        self.assertEqual(built["XDG_STATE_HOME"], str(self.world.xdg_state))
        if not capability:
            self.assertNotIn("COORDINATION_CAPABILITY", built)
        self.assertNotIn("AGENTSCIENT_HOOK_PROFILE", built)
        return built

    @staticmethod
    def capability_of(session: str) -> str:
        return hashlib.sha256(session.encode()).hexdigest()

    def sessions(self, *argv: str, session: str | None = None, identity: str | None = AGENT,
                 timeout: float = TIMEOUT):
        capability = self.capability_of(session) if session else None
        return run([sys.executable, str(TOOL), *argv], cwd=self.world.cwd,
                   env=self.env(identity=identity, session=session, capability=capability),
                   timeout=timeout)

    def coord(self, *argv: str, session: str, capability: str | None):
        return run([sys.executable, str(COORD), *argv], cwd=self.world.cwd,
                   env=self.env(session=session, capability=capability), timeout=TIMEOUT)

    def bind(self, session: str, roles: str, *, capability: str | None) -> str:
        bound = self.coord("bind", "--roles", roles, session=session, capability=capability)
        self.assertEqual(bound.exit, 0, bound.stderr)
        participant = re.search(r"\b(PT-\d+)\b", bound.stdout)
        self.assertIsNotNone(participant, bound.stdout)
        return participant.group(1)

    def bind_lead(self) -> str:
        return self.bind(LEAD_SESSION, "lead,coordinator", capability=self.capability_of(LEAD_SESSION))

    def start_co(self) -> str:
        started = self.sessions("start", "--member", "co", "--team", str(self.team_path),
                                "--ready-timeout", str(READY), session=LEAD_SESSION)
        match = re.search(r"\b(R-\d+)\b", started.stdout)
        self.assertIsNotNone(match, started.stdout + started.stderr)
        return match.group(1)

    def join_owner(self, run_id: str, participant: str) -> None:
        joined = self.sessions("join", "--run", run_id, "--member", "owner",
                               "--participant", participant, "--team", str(self.team_path))
        self.assertEqual(joined.exit, 0, joined.stderr)

    def run_dir(self, run_id: str) -> Path:
        return self.state / "runs" / run_id


class TheObjective(_Trial):
    """`trial objective` writes the objective record or refuses `objective`."""

    def full(self, run_id: str) -> list[str]:
        return ["trial", "objective", run_id, "--deliverable", "LD-123", "--clause", CLAUSE,
                "--candidate", "dev", "--case", f"omitted:{CLAUSE}", "--case", f"changed:{MOVED}"]

    @staticmethod
    def without(argv: list[str], *flag_value: str) -> tuple[str, ...]:
        out = list(argv)
        for index in range(len(out) - 1):
            if tuple(out[index:index + len(flag_value)]) == flag_value:
                del out[index:index + len(flag_value)]
                return tuple(out)
        raise AssertionError(f"INVALID: {flag_value} not in {argv}")

    def test_an_objective_missing_a_part_refuses_objective(self):
        """origin: sessions-lever.md#slice-4 the shapes

        A call missing the deliverable, a clause, the candidate or either
        case refuses ``objective``, and writes no objective record.
        """
        self.skip_without_tmux()
        self.bind_lead()
        run_id = self.start_co()
        full = self.full(run_id)
        at = origin("the shapes")
        rows = (
            RefusalCase(id="objective-no-deliverable", cls="objective", origin=at,
                        argv=self.without(full, "--deliverable", "LD-123")),
            RefusalCase(id="objective-no-clause", cls="objective", origin=at,
                        argv=self.without(full, "--clause", CLAUSE)),
            RefusalCase(id="objective-no-candidate", cls="objective", origin=at,
                        argv=self.without(full, "--candidate", "dev")),
            RefusalCase(id="objective-no-omitted-case", cls="objective", origin=at,
                        argv=self.without(full, "--case", f"omitted:{CLAUSE}")),
            RefusalCase(id="objective-no-changed-case", cls="objective", origin=at,
                        argv=self.without(full, "--case", f"changed:{MOVED}")),
        )
        run_table(self, rows, lambda row: self.sessions(*row.argv, session=LEAD_SESSION))
        self.assertFalse((self.run_dir(run_id) / "objective.json").exists())

    def test_a_whole_objective_is_written_into_the_run(self):
        """origin: sessions-lever.md#slice-4 the shapes

        A whole call exits 0 and writes ``<state dir>/runs/R-n/objective.json``
        carrying the deliverable, the clause, the candidate and both cases.
        """
        self.skip_without_tmux()
        with self.subTest(id="objective-written", origin=origin("the shapes")):
            self.bind_lead()
            run_id = self.start_co()
            done = self.sessions(*self.full(run_id), session=LEAD_SESSION)
            self.assertEqual(done.exit, 0, done.stderr)
            path = self.run_dir(run_id) / "objective.json"
            self.assertTrue(path.is_file(), f"no {path}")
            text = path.read_text(encoding="utf-8")
            for part in ("LD-123", CLAUSE, "dev", f"omitted:{CLAUSE}", f"changed:{MOVED}"):
                self.assertIn(part, text)


class TheAcceptance(_Trial):
    """`trial accept` refuses `acceptance` on a stale sha or a mock written live."""

    def accept(self, run_id: str, candidate: str, table: str):
        record = self.world.plant_text("trial.md", table)
        return self.sessions("trial", "accept", run_id, "--candidate", candidate,
                             "--record", str(record), session=LEAD_SESSION)

    def test_acceptance_refuses_a_stale_sha_and_a_mock_written_live(self):
        """origin: sessions-lever.md#slice-4 refusals added

        A candidate sha that is not the sha the verifier's row names, and an
        evidence cell reading ``live`` for a row whose command ran a planted
        fake, each refuse ``acceptance``; the stale sha names both shas.
        """
        self.skip_without_tmux()
        self.bind_lead()
        run_id = self.start_co()
        at = origin("refusals added")
        live_mock = trial_table({"I-05": ("the I-05 requirement", "live mock session_codex",
                                          "measured I-05 exit 0")})
        tables = {"acceptance-stale-sha": trial_table(), "acceptance-mock-as-live": live_mock}
        rows = (
            RefusalCase(id="acceptance-stale-sha", argv=("trial", "accept", run_id, "--candidate", MOVED),
                        cls="acceptance", origin=at, named=(VERIFIED, MOVED), note=MOVED),
            RefusalCase(id="acceptance-mock-as-live", argv=("trial", "accept", run_id, "--candidate", VERIFIED),
                        cls="acceptance", origin=at, named=("I-05",), note=VERIFIED),
        )
        run_table(self, rows, lambda row: self.accept(run_id, row.note, tables[row.id]))

    def test_the_verified_sha_on_a_complete_record_is_accepted(self):
        """origin: sessions-lever.md#slice-4 the shapes

        The clean neighbour: the verified sha on a record with no mock
        written live exits 0.
        """
        self.skip_without_tmux()
        with self.subTest(id="acceptance-verified", origin=origin("the shapes")):
            self.bind_lead()
            run_id = self.start_co()
            done = self.accept(run_id, VERIFIED, trial_table())
            self.assertEqual(done.exit, 0, done.stderr)


class TheRecordCheck(_Trial):
    """`trial record <path>` refuses `evidence` on the first unread row."""

    def check(self, table: str):
        record = self.world.plant_text("trial.md", table)
        return self.sessions("trial", "record", str(record), identity=None)

    def test_a_row_without_a_reading_refuses_evidence(self):
        """origin: sessions-lever.md#slice-4 refusals added

        A row with neither a reading nor ``not measured <why>`` refuses
        ``evidence`` naming the first such row; ``not measured`` with no why
        is not a declaration.
        """
        at = origin("refusals added")
        tables = {
            "evidence-empty-reading": trial_table({"I-07": ("the I-07 requirement", "P-sessions4-I-07", ""),
                                                   "I-09": ("the I-09 requirement", "P-sessions4-I-09", "")}),
            "evidence-not-measured-without-why": trial_table(
                {"I-03": ("the I-03 requirement", "P-sessions4-I-03", "not measured")}),
        }
        rows = (
            RefusalCase(id="evidence-empty-reading", argv=("trial", "record"), cls="evidence",
                        origin=at, named=("I-07",)),
            RefusalCase(id="evidence-not-measured-without-why", argv=("trial", "record"),
                        cls="evidence", origin=at, named=("I-03",)),
        )
        run_table(self, rows, lambda row: self.check(tables[row.id]))

    def test_a_complete_record_exits_0(self):
        """origin: sessions-lever.md#slice-4 the shapes

        The clean neighbour: fourteen rows, each read or declared
        ``not measured <why>``, exit 0.
        """
        with self.subTest(id="evidence-complete", origin=origin("the shapes")):
            table = trial_table({"I-08": ("the I-08 requirement", "P-sessions4-I-08",
                                          "not measured the harness exposes no usage")})
            done = self.check(table)
            self.assertEqual(done.exit, 0, done.stderr)


class TheOwnersTerminal(_Trial):
    """The owner's terminals: bind mints, join reads, the refusal names which."""

    def test_a_plain_terminal_binds_joins_and_reads_unmeasured(self):
        """origin: sessions-lever.md#slice-4 the owner's terminals

        A world with no profile and no environment capability binds, joins,
        and reads ``enforcement unmeasured`` beside the eight readiness
        lines; the minted capability lives under
        ``<state dir>/runs/R-n/terminals/PT-n/home`` and nowhere shared. Red
        until the wall lands the minting in instrument.py.
        """
        self.skip_without_tmux()
        with self.subTest(id="owner-terminal-unminted", origin=origin("the owner's terminals")):
            self.plant_team("co", "owner")
            self.bind_lead()
            run_id = self.start_co()
            bound = self.coord("bind", "--roles", "worker", session=OWNER_SESSION, capability=None)
            self.assertEqual(bound.exit, 0, "a plain terminal did not bind: " + bound.stderr)
            participant = re.search(r"\b(PT-\d+)\b", bound.stdout)
            self.assertIsNotNone(participant, bound.stdout)
            self.join_owner(run_id, participant.group(1))
            home = self.run_dir(run_id) / "terminals" / participant.group(1) / "home"
            minted = [match for path in home.rglob("*") if path.is_file()
                      for match in re.findall(r"\b[0-9a-f]{64}\b",
                                              path.read_text(encoding="utf-8", errors="replace"))]
            self.assertEqual(len(set(minted)), 1, f"one minted capability under {home}: {minted}")
            for path in self.world.root.rglob("*"):
                if path.is_file() and home not in path.parents:
                    self.assertNotIn(minted[0], path.read_text(encoding="utf-8", errors="replace"),
                                     f"the capability is shared in {path}")
            status = self.sessions("status", identity=None)
            self.assertEqual(status.exit, 0, status.stderr)
            block = member_block(status.stdout, "owner")
            for dimension in READINESS:
                self.assertRegex(block, rf"(?m)^  {dimension} \S", block)
            self.assertRegex(block, r"(?m)^  enforcement unmeasured$", block)

    def test_a_malformed_capability_refuses_capability_naming_it(self):
        """origin: sessions-lever.md#slice-4 the owner's terminals

        The same world with a malformed capability refuses ``capability``,
        found ``malformed <what>``, never "missing or malformed".
        """
        with self.subTest(id="owner-terminal-malformed", origin=origin("the owner's terminals")):
            result = self.coord("bind", "--roles", "worker", session=OWNER_SESSION,
                                capability="not-a-capability")
            refusal = refusal_wire(
                RefusalCase(id="owner-terminal-malformed", argv=("bind", "--roles", "worker"),
                            cls="capability", origin=origin("the owner's terminals"),
                            named=("malformed",)),
                result,
            )
            self.assertRegex(refusal.found, r"^malformed \S", refusal.line)
            self.assertNotIn("missing or malformed", refusal.found)


class TheEnforcementLine(_Trial):
    """`status` prints a ninth line for every member."""

    def test_a_managed_member_reads_an_enforcement_line(self):
        """origin: sessions-lever.md#slice-4 the owner's terminals

        ``status`` prints ``enforcement unmeasured`` or ``enforcement ok
        <profile id>`` for every member, never a bare ``ok``.
        """
        self.skip_without_tmux()
        with self.subTest(id="enforcement-managed", origin=origin("the owner's terminals")):
            self.bind_lead()
            self.start_co()
            status = self.sessions("status", identity=None)
            self.assertEqual(status.exit, 0, status.stderr)
            block = member_block(status.stdout, "co")
            lines = re.findall(r"(?m)^  enforcement .*$", block)
            self.assertEqual(len(lines), 1, block)
            self.assertRegex(lines[0], r"^  enforcement (unmeasured|ok \S+)$", block)


class TheStopAccounting(_Trial):
    """Step 8: per joined member, ``acknowledged <stamp>`` or ``unacknowledged``."""

    def owner_joined(self) -> tuple[str, str, str]:
        self.plant_team("co", "owner")
        lead = self.bind_lead()
        owner = self.bind(OWNER_SESSION, "worker", capability=self.capability_of(OWNER_SESSION))
        run_id = self.start_co()
        self.join_owner(run_id, owner)
        return run_id, lead, owner

    def test_a_joined_member_that_never_replied_reads_unacknowledged(self):
        """origin: sessions-lever.md#slice-4 step 8

        The inform "stop requested" asks for no ack; a joined member with no
        reply in the store reads ``unacknowledged``, never a default.
        """
        self.skip_without_tmux()
        with self.subTest(id="stop-unacknowledged", origin=origin("step 8")):
            run_id, _lead, _owner = self.owner_joined()
            stopped = self.sessions("stop", "--terminate", "--run", run_id, session=LEAD_SESSION)
            line = stop_line(stopped.stdout, "owner")
            self.assertRegex(line, r"\bunacknowledged$", stopped.stdout + stopped.stderr)

    def test_a_joined_member_that_replied_reads_acknowledged_with_its_stamp(self):
        """origin: sessions-lever.md#slice-4 step 8

        A joined member whose ``send --purpose inform --reply-to M-n`` answers
        "stop requested" reads ``acknowledged <stamp>``, the reply's stamp in
        ISO 8601 UTC as the store holds it.
        """
        self.skip_without_tmux()
        with self.subTest(id="stop-acknowledged", origin=origin("step 8")):
            run_id, lead, _owner = self.owner_joined()
            done: dict = {}

            def stop() -> None:
                done["result"] = self.sessions("stop", "--drain", str(DRAIN), "--run", run_id,
                                               session=LEAD_SESSION, timeout=TIMEOUT + DRAIN)

            thread = threading.Thread(target=stop)
            thread.start()
            owner_cap = self.capability_of(OWNER_SESSION)
            message = None
            deadline = time.monotonic() + DRAIN
            while message is None and time.monotonic() < deadline:
                inbox = self.coord("inbox", session=OWNER_SESSION, capability=owner_cap)
                found = re.search(r"\bM-(\d+)\b[^\n]*stop requested", inbox.stdout)
                message = found.group(1) if found else None
                if message is None:
                    time.sleep(0.2)
            replied = None
            if message is not None:
                replied = self.coord("send", "--to", lead, "--purpose", "inform",
                                     "--reply-to", f"M-{message}", "--body", "holding",
                                     session=OWNER_SESSION, capability=owner_cap)
            thread.join(timeout=TIMEOUT + DRAIN + 5)
            self.assertFalse(thread.is_alive(), "stop did not return")
            self.assertIsNotNone(message, "the owner never received stop requested")
            self.assertEqual(replied.exit, 0, replied.stderr)
            with sqlite3.connect((self.state / "state.db").as_uri() + "?mode=ro", uri=True) as conn:
                stamps = [row[0] for row in conn.execute(
                    "SELECT queued_at FROM messages WHERE reply_to = ?", (int(message),))]
            self.assertEqual(len(stamps), 1, stamps)
            line = stop_line(done["result"].stdout, "owner")
            self.assertRegex(line, rf"\backnowledged {ISO_UTC}$", done["result"].stdout)
            self.assertIn(f"acknowledged {stamps[0]}", line)


class TheRunExport(_Trial):
    """`sessions.py export <run>` names every pane log and record id, or refuses `export`."""

    def stopped_run(self, *names: str) -> str:
        self.plant_team(*(names or ("co",)))
        self.bind_lead()
        run_id = self.start_co()
        if "owner" in names:
            owner = self.bind(OWNER_SESSION, "worker", capability=self.capability_of(OWNER_SESSION))
            self.join_owner(run_id, owner)
        stopped = self.sessions("stop", "--terminate", "--run", run_id, session=LEAD_SESSION)
        self.assertIn(stopped.exit, (0, 1), stopped.stderr)
        return run_id

    def plant_launch(self) -> None:
        """One launched intent in the store's dispatch table, the shape slice 3's
        coord_launch writes, carrying RECORD_ID."""
        spec = importlib_spec(TOOLS / "dispatch_intents.py")
        with sqlite3.connect(self.state / "state.db") as conn:
            conn.executescript(spec.SCHEMA)
            conn.execute(
                "INSERT INTO dispatch_intents(key, digest, requester, dispatcher, assignment, generation,"
                " job, harness, branch, scope_ref, inputs, correlation, subject, phase, record,"
                " reserved_at, launched_at) VALUES ('k1', 'd1', 1, 1, 1, 1, 'review', 'claude',"
                " 'lane/trial', 'scope', '[]', 'corr-trial-1', 990001, 'launched', ?,"
                " '2026-09-23T09:00:00Z', '2026-09-23T09:00:01Z')", (RECORD_ID,))

    def test_a_complete_export_names_every_pane_log_and_record_id(self):
        """origin: sessions-lever.md#slice-4 the run export

        ``export <run>`` exits 0 naming the managed member's pane log and
        the launched record id; a joined member is listed ``joined <id> no
        pane log``, a declared absence.
        """
        self.skip_without_tmux()
        with self.subTest(id="export-complete", origin=origin("the run export")):
            run_id = self.stopped_run("co", "owner")
            self.plant_launch()
            exported = self.sessions("export", run_id)
            self.assertEqual(exported.exit, 0, exported.stderr)
            self.assertRegex(exported.stdout, r"\bco\b\S*pane\.log", exported.stdout)
            self.assertIn(RECORD_ID, exported.stdout)
            self.assertRegex(exported.stdout, r"\bjoined \S+ no pane log\b", exported.stdout)
            self.assertTrue((self.run_dir(run_id) / "export").is_dir())

    def test_an_export_missing_a_pane_log_refuses_export(self):
        """origin: sessions-lever.md#slice-4 refusals added

        An export missing a managed member's pane log refuses ``export``,
        naming the member and the log.
        """
        self.skip_without_tmux()
        with self.subTest(id="export-missing-pane-log", origin=origin("refusals added")):
            run_id = self.stopped_run("co")
            logs = [path for path in self.state.rglob("pane.log")
                    if "co" in path.relative_to(self.state).parts]
            self.assertEqual(len(logs), 1, logs)
            logs[0].unlink()
            result = self.sessions("export", run_id)
            refusal_wire(
                RefusalCase(id="export-missing-pane-log", argv=("export", run_id),
                            cls="export", origin=origin("refusals added"),
                            named=("co", "pane.log")),
                result,
            )


class TheTrialRecord(unittest.TestCase):
    """The trial record in the repository, checked by `trial record`."""

    def record(self) -> Path:
        records = [path for path in sorted(HANDOFF.glob("*-slice4-trial.md"))
                   if re.fullmatch(r"\d{4}-\d{2}-\d{2}-slice4-trial\.md", path.name)]
        self.assertEqual(len(records), 1, f"expected one dated trial record under {HANDOFF}, found {records}")
        return records[0]

    def test_the_record_checks_clean(self):
        """origin: sessions-lever.md#slice-4 the shapes

        ``trial record`` exits 0 on the repository's record: fourteen rows,
        each read or declared.
        """
        with self.subTest(id="trial-record-shape", origin=origin("the shapes")):
            path = self.record()
            done = run([sys.executable, str(TOOL), "trial", "record", str(path)],
                       cwd=REPO, env={"PATH": os.environ.get("PATH", "")}, timeout=TIMEOUT)
            self.assertEqual(done.exit, 0, done.stderr)

    def test_both_controlled_cases_read_refused(self):
        """origin: sessions-lever.md#slice-4 closure 1

        Rows I-10 and I-14 read ``refused`` for both controlled cases.
        """
        with self.subTest(id="trial-record-closure", origin=origin("closure 1")):
            rows: dict[str, list[str]] = {}
            for line in self.record().read_text(encoding="utf-8").splitlines():
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                if line.startswith("|") and re.fullmatch(r"I-\d{2}", cells[0]):
                    rows[cells[0]] = cells
            self.assertEqual(tuple(rows), IDS)
            for key in ("I-10", "I-14"):
                self.assertGreaterEqual(len(re.findall(r"\brefused\b", rows[key][3])), 2,
                                        f"{key}: {rows[key]}")


def importlib_spec(path: Path):
    """Load a tool module by path to read its schema text; nothing runs."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"s4_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
