"""Slice 4 rows: the owner's terminals, stop accounting, the run export,
the trial record.

Contract: ops/conductor/sessions-lever.md section "Slice 4 — operational
trial and closure", read at da3e5e06. Run from the repository root:
python3 -m unittest discover -s ops/conductor/tests -p test_sessions_trial.py

The section's Tests subsection reads "Slice 4 owns no new suite"; these
rows are written at the Lead's order through the XO (2026-09-23), and the
conflict is reported to the XO. The section names no command that refuses
`objective` or `acceptance`, or that refuses `evidence` on the wire, so
those classes have no row here; the trial record's shape is read from the
record itself.

The two owner's-terminal rows stay red until the wall session lands the
`bind` minting in instrument.py (a wall path, LD-125).

Planted faults: sessions_trial_faults.py beside this module, anchored on
sessions.py at da3e5e06; its docstring names the calibrate command. A
declared gap until calibrated: every row is red on the subject, so the
clean run is red and calibrate reports ok false.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from ops.testkit import RefusalCase, World, refusal_wire, run

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
STAMP = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"


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


class TheOwnersTerminal(_Trial):
    """The owner's terminals: bind mints, join reads, the refusal names which."""

    def test_a_plain_terminal_binds_joins_and_reads_unmeasured(self):
        """origin: sessions-lever.md#slice-4 the owner's terminals

        A world with no profile and no environment capability binds, joins,
        and reads ``unmeasured`` on enforcement, beside the same eight
        readiness lines as a managed member. Red until the wall lands the
        minting in instrument.py.
        """
        self.skip_without_tmux()
        with self.subTest(id="owner-terminal-unminted", origin=origin("the owner's terminals")):
            self.plant_team("co", "owner")
            self.bind(LEAD_SESSION, "lead,coordinator", capability=self.capability_of(LEAD_SESSION))
            bound = self.coord("bind", "--roles", "worker", session=OWNER_SESSION, capability=None)
            self.assertEqual(bound.exit, 0, "a plain terminal did not bind: " + bound.stderr)
            participant = re.search(r"\b(PT-\d+)\b", bound.stdout)
            self.assertIsNotNone(participant, bound.stdout)
            run_id = self.start_co()
            self.join_owner(run_id, participant.group(1))
            status = self.sessions("status", identity=None)
            self.assertEqual(status.exit, 0, status.stderr)
            block = member_block(status.stdout, "owner")
            for dimension in READINESS:
                self.assertRegex(block, rf"(?m)^  {dimension} \S", block)
            self.assertRegex(block, r"(?m)^  enforcement unmeasured\b", block)
            self.assertNotRegex(block, r"(?m)^  enforcement ok\b", block)

    def test_a_malformed_capability_refuses_capability_naming_it(self):
        """origin: sessions-lever.md#slice-4 the owner's terminals

        The same world with a malformed capability refuses ``capability``,
        and the refusal names the malformation, not "missing or malformed".
        """
        with self.subTest(id="owner-terminal-malformed", origin=origin("the owner's terminals")):
            malformed = "not-a-capability"
            result = self.coord("bind", "--roles", "worker", session=OWNER_SESSION,
                                capability=malformed)
            refusal = refusal_wire(
                RefusalCase(id="owner-terminal-malformed", argv=("bind", "--roles", "worker"),
                            cls="capability", origin=origin("the owner's terminals"),
                            named=("malformed",)),
                result,
            )
            self.assertNotIn("missing or malformed", result.stderr,
                             f"the refusal does not name which: {refusal}")


class TheStopAccounting(_Trial):
    """Step 8: per joined member, ``acknowledged <stamp>`` or ``unacknowledged``."""

    def owner_joined(self) -> tuple[str, str, str]:
        self.plant_team("co", "owner")
        lead = self.bind(LEAD_SESSION, "lead,coordinator", capability=self.capability_of(LEAD_SESSION))
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
            self.assertRegex(line, r"\bunacknowledged\b", stopped.stdout + stopped.stderr)
            self.assertNotRegex(line, r"(?<!un)acknowledged\b")

    def test_a_joined_member_that_replied_reads_acknowledged_with_its_stamp(self):
        """origin: sessions-lever.md#slice-4 step 8

        A joined member whose own reply to "stop requested" is in the store
        reads ``acknowledged <stamp>``.
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
                found = re.search(r"\b(M-\d+)\b[^\n]*stop requested", inbox.stdout)
                message = found.group(1) if found else None
                if message is None:
                    time.sleep(0.2)
            replied = None
            if message is not None:
                replied = self.coord("send", "--to", lead, "--purpose", "inform",
                                     "--reply-to", message, "--body", "holding",
                                     session=OWNER_SESSION, capability=owner_cap)
            thread.join(timeout=TIMEOUT + DRAIN + 5)
            self.assertFalse(thread.is_alive(), "stop did not return")
            self.assertIsNotNone(message, "the owner never received stop requested")
            self.assertEqual(replied.exit, 0, replied.stderr)
            stopped = done["result"]
            line = stop_line(stopped.stdout, "owner")
            self.assertRegex(line, rf"(?<!un)acknowledged {STAMP}", stopped.stdout + stopped.stderr)


class TheRunExport(_Trial):
    """The run export names every member's pane log, or refuses ``export``."""

    def stopped_run(self) -> str:
        self.bind(LEAD_SESSION, "lead,coordinator", capability=self.capability_of(LEAD_SESSION))
        run_id = self.start_co()
        stopped = self.sessions("stop", "--terminate", "--run", run_id, session=LEAD_SESSION)
        self.assertIn(stopped.exit, (0, 1), stopped.stderr)
        return run_id

    def test_a_complete_export_names_every_members_pane_log(self):
        """origin: sessions-lever.md#slice-4 the run export

        The export is complete when the export command exits 0 and names
        every member's pane log.
        """
        self.skip_without_tmux()
        with self.subTest(id="export-complete", origin=origin("the run export")):
            run_id = self.stopped_run()
            dest = self.world.tmp / "export"
            exported = self.sessions("export", "--run", run_id, "--to", str(dest))
            self.assertEqual(exported.exit, 0, exported.stderr)
            self.assertRegex(exported.stdout, r"\bco\b\S*pane\.log", exported.stdout)

    def test_an_export_missing_a_pane_log_refuses_export(self):
        """origin: sessions-lever.md#slice-4 refusals added

        An export missing a member's pane log refuses ``export``, naming the
        member and the log.
        """
        self.skip_without_tmux()
        with self.subTest(id="export-missing-pane-log", origin=origin("refusals added")):
            run_id = self.stopped_run()
            logs = [path for path in (self.state / "sessions").rglob("pane.log")
                    if "co" in path.relative_to(self.state).parts]
            self.assertEqual(len(logs), 1, logs)
            logs[0].unlink()
            dest = self.world.tmp / "export"
            result = self.sessions("export", "--run", run_id, "--to", str(dest))
            refusal_wire(
                RefusalCase(id="export-missing-pane-log", argv=("export", "--run", run_id),
                            cls="export", origin=origin("refusals added"),
                            named=("co", "pane.log")),
                result,
            )


class TheTrialRecord(unittest.TestCase):
    """The trial record, read from the repository: fourteen rows by id."""

    def rows(self) -> dict[str, list[str]]:
        records = sorted(HANDOFF.glob("*-slice4-trial.md"))
        self.assertEqual(len(records), 1, f"expected one trial record under {HANDOFF}, found {records}")
        rows: dict[str, list[str]] = {}
        for line in records[0].read_text(encoding="utf-8").splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if line.startswith("|") and cells and re.fullmatch(r"I-\d{2}", cells[0]):
                self.assertNotIn(cells[0], rows, f"{cells[0]} appears twice")
                rows[cells[0]] = cells
        return rows

    def test_the_record_has_fourteen_rows_each_read_or_declared(self):
        """origin: sessions-lever.md#slice-4 the shapes

        One row per acceptance id I-01 to I-14, ``id | required result |
        evidence | reading``; ``reading`` is a measured line or ``not
        measured`` with why; a mock's pass is ``mock <name>``, never ``live``.
        """
        with self.subTest(id="trial-record-shape", origin=origin("the shapes")):
            rows = self.rows()
            self.assertEqual(tuple(rows), IDS)
            for key, cells in rows.items():
                self.assertEqual(len(cells), 4, f"{key}: {cells}")
                _id, required, evidence, reading = cells
                self.assertTrue(required, f"{key}: no required result")
                self.assertTrue(evidence, f"{key}: no evidence")
                self.assertTrue(reading, f"{key}: neither a reading nor not measured <why>")
                if reading.startswith("not measured"):
                    self.assertRegex(reading, r"^not measured \S", f"{key}: not measured without why")
                if re.search(r"\bmock\b", evidence):
                    self.assertRegex(evidence, r"\bmock \S", f"{key}: a mock without its name")
                    self.assertNotRegex(evidence + " " + reading, r"\blive\b",
                                        f"{key}: a mock written as live")

    def test_both_controlled_cases_read_refused(self):
        """origin: sessions-lever.md#slice-4 closure 1

        Rows I-10 and I-14 read ``refused`` for both controlled cases.
        """
        with self.subTest(id="trial-record-closure", origin=origin("closure 1")):
            rows = self.rows()
            for key in ("I-10", "I-14"):
                self.assertIn(key, rows)
                self.assertRegex(rows[key][3], r"\brefused\b", f"{key}: {rows[key]}")


if __name__ == "__main__":
    unittest.main()
