"""Native courier routes, attempts, the send key, and the additive schema.

Contract: ``ops/conductor/sessions-lever.md``, "Slice 2 — persistent
native conversation". Coordination and the courier run as subprocesses
through ``ops.testkit.run``. A planted ``submit`` is the registry's
data-driven fake, so each call is one JSON line. Slice 2's verbs are
not in the tree; each row fails on the reading it names.

The one command that reads this file is
``python3 -m unittest discover -s ops/conductor/tests -p test_courier_native.py``.
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

from ops.testkit import RefusalCase, World, refusal_wire, run

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "ops" / "conductor" / "tools"
CORE = TOOLS / "coordination.py"
COURIER = TOOLS / "courier.py"
SESSIONS = TOOLS / "sessions.py"
FAKES = Path(__file__).resolve().parent / "fakes"
HARNESS_SRC = FAKES / "session_harness.py"
TMUX_SRC = FAKES / "session_tmux.py"
HOLDER_SRC = FAKES / "session_holder.py"

AGENT = "Courier Native <noreply@example.test>"
LANE = "agentscient"
LEAD = "sess-courier-native-lead"
WORKER = "sess-courier-native-worker"
TIMEOUT = 60.0
READY = 15
BODY = "the worker's in-progress question"
OTHER = "a different body for the same key"
KEY = "k-repeat"
REF = "turn-9"
LATER = "later-ref"
ORIGIN = "sessions-lever.md#slice-2"
HOST_TMUX = shutil.which("tmux")
NEW_TABLES = ("delivery_routes", "delivery_attempts", "send_requests")


def origin(number: int | None = None) -> str:
    if number is None:
        return ORIGIN
    return f"{ORIGIN} {number}"


def _fake_text(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"INVALID: planted program missing: {path}")
    text = path.read_text(encoding="utf-8")
    if text.startswith("#!"):
        text = text.split("\n", 1)[1]
    return f"#!{sys.executable}\n" + text


def _anchored(text: str, needle: str, value: str) -> str:
    count = text.count(needle)
    if count != 1:
        raise AssertionError(
            f"INVALID: anchor {needle!r} matches {count} times, not once"
        )
    updated = text.replace(needle, value, 1)
    if needle in updated:
        raise AssertionError(f"INVALID: anchor {needle!r} survived")
    return updated


def ticks_of(pid: int) -> str:
    """Field 22 of ``/proc/<pid>/stat``, the process start ticks."""
    text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    return text.rsplit(")", 1)[1].split()[19]


def open_world(prefix: str) -> World:
    """A world under ``/tmp``, so a private tmux socket stays short."""
    saved = tempfile.tempdir
    tempfile.tempdir = "/tmp"
    try:
        return World(prefix=prefix)
    finally:
        tempfile.tempdir = saved


def attempt_id(stdout: str) -> str:
    match = re.search(r"AT-\d+", stdout)
    if match is None:
        raise AssertionError(f"no AT-n in {stdout!r}")
    return match.group(0)


def delivered_line(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("delivered"):
            return line
    return None


class CoreCase(unittest.TestCase):
    """A hermetic store and the coordination core's own verbs."""

    def setUp(self):
        self.world = World(prefix="courier-native-")
        self.addCleanup(self.world.close)
        self.conf = self.world.plant_text(
            "lane.conf", f"LANE_NAME='{LANE}'\n"
        )
        self.db = self.world.xdg_state / LANE / "state.db"

    def env(self, session: str | None, *, capability: str | None = None):
        extra = {"LANE_CONF": str(self.conf), "WF_AGENT": AGENT}
        if session:
            extra["CLAUDE_CODE_SESSION_ID"] = session
            digest = hashlib.sha256(session.encode()).hexdigest()
            extra["COORDINATION_CAPABILITY"] = capability or digest
        return self.world.env(extra=extra)

    def core(self, *argv: str, session: str | None = LEAD,
             capability: str | None = None, expect: int | None = None):
        return run(
            [sys.executable, str(CORE), *argv],
            cwd=self.world.cwd,
            env=self.env(session, capability=capability),
            timeout=TIMEOUT,
            expect=expect,
        )

    def courier(self, *argv: str, session: str = LEAD):
        return run(
            [sys.executable, "-B", str(COURIER), *argv],
            cwd=self.world.cwd,
            env=self.env(session),
            timeout=TIMEOUT,
        )

    def bind(self) -> None:
        self.core("bind", "--roles", "lead,coordinator", expect=0)
        self.core("bind", "--roles", "worker", session=WORKER, expect=0)

    def send(self, body: str, *, key: str | None = None,
             session: str = WORKER):
        argv = [
            "send", "--to", "PT-1", "--purpose", "request", "--body", body,
        ]
        if key is not None:
            argv[1:1] = ["--key", key]
        return self.core(*argv, session=session)

    def show(self, message: str, session: str = LEAD) -> str:
        shown = self.core("show", message, session=session, expect=0)
        return shown.stdout

    def table_rows(self, table: str) -> list[tuple] | None:
        if not self.db.is_file():
            return None
        with sqlite3.connect(self.db) as conn:
            found = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if found is None:
                return None
            return conn.execute(
                f"SELECT * FROM {table} ORDER BY 1"
            ).fetchall()

    def snapshot(self) -> dict[str, list[tuple]]:
        self.assertTrue(self.db.is_file(), "the store was not created")
        found: dict[str, list[tuple]] = {}
        with sqlite3.connect(self.db) as conn:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            for table in tables:
                found[table] = conn.execute(
                    f"SELECT * FROM {table} ORDER BY 1"
                ).fetchall()
        return found

    def plant_submit(self) -> None:
        """The native ``submit`` callable, logged by the registry."""
        self.world.tools.plant("submit", stdout="submitted\n")

    def submissions(self) -> list[dict]:
        return self.world.tools.calls("submit")

    def seed_evidence(self, message: str, body: str) -> None:
        """One logged call whose argv carries the message body."""
        seeded = run(
            [str(self.world.bin / "submit"), message, body],
            cwd=self.world.cwd,
            env=self.world.env(),
            timeout=TIMEOUT,
        )
        self.assertEqual(seeded.exit, 0, seeded.stderr)
        logged = self.submissions()
        self.assertTrue(logged, "the registry logged no submission")
        self.assertIn(body, json.dumps(logged[-1]))

    def reserve(self, message: str) -> str:
        reserved = self.core(
            "attempt", message, "--route", "native", "--generation", "1",
            session=LEAD,
        )
        self.assertEqual(reserved.exit, 0, reserved.stderr)
        return attempt_id(reserved.stdout)

    def age(self, attempt: str) -> None:
        """Plant a crash: the reservation is older than ``ATTEMPT_TTL``."""
        number = int(attempt.split("-", 1)[1])
        with sqlite3.connect(self.db) as conn:
            changed = conn.execute(
                "UPDATE delivery_attempts SET reserved_at = ? WHERE id = ?",
                ("2020-01-01T00:00:00Z", number),
            ).rowcount
        self.assertEqual(changed, 1, "the unsettled attempt was not aged")

    def attempt_outcomes(self, message: str) -> list[tuple]:
        number = int(message.split("-", 1)[1])
        with sqlite3.connect(self.db) as conn:
            return conn.execute(
                "SELECT id, outcome FROM delivery_attempts "
                "WHERE message = ? ORDER BY id",
                (number,),
            ).fetchall()


class TheSendKey(CoreCase):
    """origin: sessions-lever.md#slice-2 3

    ``send --key`` twice with one body returns one ``M-n`` as
    ``repeated``. A third with another body refuses ``idempotency``
    and writes no row.
    """

    def message_id(self, stdout: str) -> str:
        match = re.search(r"message (M-\d+) queued", stdout)
        self.assertIsNotNone(match, stdout)
        return match.group(1)

    def test_the_same_key_and_body_returns_one_message_repeated(self):
        self.bind()
        first = self.send(BODY, key=KEY)
        self.assertEqual(first.exit, 0, first.stderr)
        message = self.message_id(first.stdout)
        self.assertEqual(first.stdout.strip(), f"message {message} queued")
        second = self.send(BODY, key=KEY)
        self.assertEqual(second.exit, 0, second.stderr)
        repeated = f"message {message} queued (repeated)"
        self.assertEqual(second.stdout.strip(), repeated)
        self.assertEqual(self.message_id(second.stdout), message)
        rows = self.table_rows("messages")
        self.assertIsNotNone(rows)
        self.assertEqual(len(rows), 1, rows)

    def test_another_body_refuses_idempotency_and_writes_nothing(self):
        self.bind()
        first = self.send(BODY, key=KEY)
        self.assertEqual(first.exit, 0, first.stderr)
        message = self.message_id(first.stdout)
        again = self.send(BODY, key=KEY)
        self.assertEqual(again.exit, 0, again.stderr)
        before = self.table_rows("messages")
        refused = self.send(OTHER, key=KEY)
        refusal_wire(
            RefusalCase(
                id="idempotency-other-body",
                argv=("send", "--key", KEY),
                cls="idempotency",
                named=(message,),
                origin=origin(3),
            ),
            refused,
        )
        self.assertEqual(self.table_rows("messages"), before)
        shown = self.show(message)
        self.assertIn(BODY, shown)
        self.assertNotIn(OTHER, shown)


class TheAttempts(CoreCase):
    """``attempt`` then ``attempted`` through each outcome.

    origin: sessions-lever.md#slice-2. The first ``written`` or
    ``accepted`` records ``deliver`` once, ``delivery_ref``
    ``native:AT-n:<ref>``, and leaves ``acked_at`` NULL.
    """

    def queued(self, body: str) -> str:
        sent = self.send(body)
        self.assertEqual(sent.exit, 0, sent.stderr)
        return self._message_id(sent.stdout)

    def _message_id(self, stdout: str) -> str:
        match = re.search(r"message (M-\d+) queued", stdout)
        self.assertIsNotNone(match, stdout)
        return match.group(1)

    def settle(self, attempt: str, *argv: str):
        settled = self.core("attempted", attempt, *argv, session=LEAD)
        self.assertEqual(settled.exit, 0, settled.stderr)
        return settled

    def assert_ack_unset(self, text: str) -> None:
        acked = [
            line for line in text.splitlines()
            if line.startswith("acknowledged")
        ]
        self.assertEqual(acked, [], text)

    def test_written_and_accepted_deliver_once_with_the_native_ref(self):
        self.bind()
        cases = (
            ("written", ("--outcome", "written"), None),
            ("accepted", ("--outcome", "accepted", "--ref", REF), REF),
        )
        for case_id, argv, ref in cases:
            with self.subTest(id=case_id, origin=origin()):
                message = self.queued(f"{case_id} {BODY}")
                attempt = self.reserve(message)
                self.settle(attempt, *argv)
                shown = self.show(message)
                line = delivered_line(shown)
                self.assertIsNotNone(line, shown)
                self.assertIn(f"native:{attempt}", line)
                if ref is not None:
                    self.assertIn(f"native:{attempt}:{ref}", line)
                self.assert_ack_unset(shown)

    def test_a_later_outcome_does_not_deliver_again(self):
        self.bind()
        with self.subTest(id="recorded-once", origin=origin()):
            message = self.queued(BODY)
            first = self.reserve(message)
            self.settle(first, "--outcome", "written")
            before = delivered_line(self.show(message))
            self.assertIsNotNone(before)
            self.assertIn(f"native:{first}", before)
            second = self.reserve(message)
            self.settle(second, "--outcome", "accepted", "--ref", LATER)
            after = self.show(message)
            self.assertEqual(delivered_line(after), before)
            self.assertNotIn(LATER, delivered_line(after) or "")
            self.assert_ack_unset(after)

    def test_other_outcomes_leave_the_message_undelivered(self):
        self.bind()
        cases = (
            (
                "unsupported",
                ("--outcome", "unsupported", "--error", "turn/start"),
                ("unsupported", "turn/start"),
            ),
            (
                "failed",
                ("--outcome", "failed", "--error", "broke"),
                ("failed", "broke"),
            ),
            (
                "uncertain",
                ("--outcome", "uncertain", "--error", "lost"),
                ("uncertain", "lost"),
            ),
        )
        for case_id, argv, tokens in cases:
            with self.subTest(id=case_id, origin=origin()):
                message = self.queued(f"{case_id} {BODY}")
                attempt = self.reserve(message)
                self.settle(attempt, *argv)
                shown = self.show(message)
                self.assertIsNone(delivered_line(shown), shown)
                self.assert_ack_unset(shown)
                listing = self.core("attempts", message, session=LEAD)
                self.assertEqual(listing.exit, 0, listing.stderr)
                for token in tokens:
                    self.assertIn(token, listing.stdout, listing.stdout)

    def test_a_fifth_reservation_refuses_attempt(self):
        """At most ``ATTEMPTS_OUTSTANDING`` (4) stay reserved."""
        self.bind()
        for index in range(4):
            message = self.queued(f"outstanding {index} {BODY}")
            with self.subTest(id=f"reserved-{index}", origin=origin()):
                self.reserve(message)
        fifth = self.queued(f"outstanding cap {BODY}")
        before = self.table_rows("delivery_attempts")
        refused = self.core(
            "attempt", fifth, "--route", "native", "--generation", "1",
            session=LEAD,
        )
        refusal_wire(
            RefusalCase(
                id="outstanding-cap",
                argv=("attempt", fifth),
                cls="attempt",
                named=("4",),
                origin=origin(),
            ),
            refused,
        )
        self.assertEqual(self.table_rows("delivery_attempts"), before)


class TheCrash(CoreCase):
    """origin: sessions-lever.md#slice-2 4

    A NULL outcome older than ``ATTEMPT_TTL`` (60 s) is a crash between
    the two writes. The next pass is ``courier.py watch --route native
    --once``. Evidence is the planted ``submit`` registry log, one JSON
    line per call, under ``<world>/fakes/submit.calls.jsonl`` where
    ``HOME`` is ``<world>/home``. A line whose argv carries the message
    body reads ``accepted reconciled`` and does not submit again. No
    such line reads ``uncertain`` and reserves one new attempt.
    """

    def queued_request(self) -> str:
        sent = self.send(BODY)
        self.assertEqual(sent.exit, 0, sent.stderr)
        match = re.search(r"message (M-\d+) queued", sent.stdout)
        self.assertIsNotNone(match, sent.stdout)
        return match.group(1)

    def pass_over(self, message: str) -> tuple[str, list[tuple]]:
        passed = self.courier("watch", "--route", "native", "--once")
        self.assertEqual(passed.exit, 0, passed.stderr)
        listing = self.core("attempts", message, session=LEAD)
        self.assertEqual(listing.exit, 0, listing.stderr)
        return listing.stdout, self.attempt_outcomes(message)

    def test_evidence_reconciles_without_a_second_submission(self):
        self.bind()
        self.plant_submit()
        message = self.queued_request()
        attempt = self.reserve(message)
        self.age(attempt)
        self.seed_evidence(message, BODY)
        before = len(self.submissions())
        text, rows = self.pass_over(message)
        self.assertIn("accepted reconciled", text)
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0][1], "accepted reconciled", rows)
        self.assertEqual(len(self.submissions()), before)
        self.assertEqual(
            [call["argv"] for call in self.submissions()],
            [[message, BODY]],
        )

    def test_no_evidence_reads_uncertain_and_one_new_attempt(self):
        self.bind()
        self.plant_submit()
        message = self.queued_request()
        attempt = self.reserve(message)
        self.age(attempt)
        self.assertEqual(self.submissions(), [])
        text, rows = self.pass_over(message)
        self.assertIn("uncertain", text)
        self.assertEqual(len(rows), 2, rows)
        self.assertEqual(rows[0][0], int(attempt.split("-", 1)[1]))
        self.assertIsNotNone(rows[0][1], rows)
        self.assertTrue(str(rows[0][1]).startswith("uncertain"), rows)
        self.assertNotEqual(rows[1][0], rows[0][0])


class TheRoutes(unittest.TestCase):
    """``route --take`` for stdout and for native.

    origin: sessions-lever.md#slice-2 5 for the live holder and the
    takeover. A take records the route. A second take names a holder
    the world owns: the sleeper from ``session_holder.py``, its pid and
    start ticks planted on the row the take wrote, because liveness is
    pid plus ticks and a missing tick is never alive. Reaping that
    holder makes the next take the new row, with a new ``since``.
    """

    def setUp(self):
        if not HOST_TMUX:
            self.skipTest("tmux is absent; a member route needs it")
        self.world = open_world("courier-route-")
        self.addCleanup(self.world.close)
        self.addCleanup(self.stop_server)
        self.conf = self.world.plant_text(
            "lane.conf", f"LANE_NAME='{LANE}'\n"
        )
        self.db = self.world.xdg_state / LANE / "state.db"
        self.state = self.world.xdg_state / LANE
        self.socket = self.world.tmp / "tmux.sock"
        encoded = os.fsencode(str(self.socket))
        if len(encoded) >= 108:
            raise AssertionError(
                f"INVALID: tmux socket is not under 108 bytes: {self.socket}"
            )
        self._plant_harness()
        self._plant_tmux()
        team = {
            "schema": "agentscient-team/1",
            "run": {"name": "lane", "tmux": "agentscient"},
            "members": [
                {"name": "grunt", "harness": "claude", "roles": ["worker"]},
            ],
        }
        self.team = self.world.plant_text(
            "team.json", json.dumps(team) + "\n", recognisable=team["schema"],
        )
        started = self.sessions(
            "start", "--member", "grunt", "--team", str(self.team),
            "--ready-timeout", str(READY),
        )
        self.assertEqual(started.exit, 0, started.stderr)
        match = re.search(
            r"started grunt (SM-\d+) as (PT-\d+)", started.stdout,
        )
        self.assertIsNotNone(match, started.stdout)
        self.member = match.group(1)
        self.participant = int(match.group(2).split("-", 1)[1])
        self.launch_id, self.capability = self._member_identity()

    def stop_server(self) -> None:
        """Kill this world's tmux server, if a row started one.

        Registered after ``world.close``, so it runs first: the world
        does not own a tmux server, and one left running outlives it.
        """
        if HOST_TMUX and self.socket.exists():
            run(
                [HOST_TMUX, "-S", str(self.socket), "kill-server"],
                cwd=self.world.cwd,
                env=self.world.env(),
                timeout=TIMEOUT,
            )

    def _plant_harness(self) -> None:
        text = _anchored(_fake_text(HARNESS_SRC), "@@REPO@@", str(REPO))
        self.world.tools.plant("claude", script=text)
        spec_path = self.world.tools.spec_path("claude")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["session_id"] = None
        rendered = json.dumps(spec, indent=1) + "\n"
        spec_path.write_text(rendered, encoding="utf-8")
        landed = json.loads(spec_path.read_text(encoding="utf-8"))
        if landed.get("session_id") is not None:
            raise AssertionError("INVALID: harness spec did not land intact")

    def _plant_tmux(self) -> None:
        log = self.world.root / "fakes" / "tmux.calls.jsonl"
        text = _fake_text(TMUX_SRC)
        text = _anchored(text, "@@TMUX@@", HOST_TMUX)
        text = _anchored(text, "@@LOG@@", str(log))
        text = _anchored(text, "@@REPO@@", str(REPO))
        self.world.tools.plant("tmux", script=text)

    def sessions(self, *argv: str):
        return run(
            [sys.executable, str(SESSIONS), *argv],
            cwd=self.world.cwd,
            env=self.world.env(extra={
                "LANE_CONF": str(self.conf),
                "WF_AGENT": AGENT,
                "AGENTSCIENT_TMUX_SOCKET": str(self.socket),
                "TESTKIT_FAKE_SPEC": str(
                    self.world.tools.spec_path("claude")
                ),
            }),
            timeout=TIMEOUT,
        )

    def _member_identity(self) -> tuple[str, str]:
        bindings = list(
            self.state.glob("sessions/*/grunt/profile/binding.json")
        )
        self.assertTrue(bindings, "the member recorded no binding")
        binding = json.loads(bindings[0].read_text(encoding="utf-8"))
        launch_path = bindings[0].parent.parent / "launch.json"
        launch = json.loads(launch_path.read_text(encoding="utf-8"))
        launch_id = str(launch["launch_id"])
        capability = str(binding["coordination_capability"])
        return launch_id, capability

    def route(self, *argv: str):
        return run(
            [sys.executable, str(CORE), *argv],
            cwd=self.world.cwd,
            env=self.world.env(extra={
                "LANE_CONF": str(self.conf),
                "WF_AGENT": AGENT,
                "CLAUDE_CODE_SESSION_ID": self.launch_id,
                "COORDINATION_CAPABILITY": self.capability,
            }),
            timeout=TIMEOUT,
        )

    def route_row(self) -> tuple:
        with sqlite3.connect(self.db) as conn:
            row = conn.execute(
                "SELECT route, pid, start_ticks, since FROM delivery_routes "
                "WHERE participant = ?",
                (self.participant,),
            ).fetchone()
        self.assertIsNotNone(row, "no delivery route for the member")
        return row

    def take(self, which: str) -> str:
        taken = self.route(
            "route", "--take", which, "--member", self.member,
        )
        self.assertEqual(taken.exit, 0, taken.stderr)
        route, _pid, ticks, since = self.route_row()
        self.assertEqual(route, which)
        self.assertTrue(ticks)
        self.assertTrue(since)
        return since

    def owned_holder(self) -> tuple[int, object]:
        """A sleeper started through ``ops.testkit.run``."""
        nonce = str(time.time_ns())
        ready = self.world.tmp / f"holder-{nonce}.ready"
        stop = self.world.tmp / f"holder-{nonce}.stop"
        self.world.tools.plant("holder", script=_fake_text(HOLDER_SRC))
        box: dict = {}

        def invoke() -> None:
            try:
                box["result"] = run(
                    [str(self.world.bin / "holder"), str(ready), str(stop)],
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
        self.assertTrue(ready.is_file(), f"holder did not start: {box!r}")
        pid = int(ready.read_text(encoding="utf-8"))

        def release() -> None:
            if not stop.exists():
                stop.write_text("stop\n", encoding="utf-8")
            thread.join(timeout=15)

        self.addCleanup(release)
        return pid, release

    def plant_holder(self, pid: int) -> None:
        with sqlite3.connect(self.db) as conn:
            changed = conn.execute(
                "UPDATE delivery_routes SET pid = ?, start_ticks = ? "
                "WHERE participant = ?",
                (pid, ticks_of(pid), self.participant),
            ).rowcount
        self.assertEqual(changed, 1, "the live holder was not planted")

    def alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def test_take_stdout_records_the_route(self):
        with self.subTest(id="take-stdout", origin=origin()):
            self.take("stdout")

    def test_take_native_records_the_route(self):
        with self.subTest(id="take-native", origin=origin()):
            self.take("native")

    def test_a_live_holder_refuses_route_naming_its_pid(self):
        with self.subTest(id="live-holder", origin=origin(5)):
            since = self.take("stdout")
            pid, _release = self.owned_holder()
            self.plant_holder(pid)
            self.assertTrue(self.alive(pid))
            refused = self.route(
                "route", "--take", "native", "--member", self.member,
            )
            refusal_wire(
                RefusalCase(
                    id="live-holder",
                    argv=(
                        "route", "--take", "native", "--member", self.member,
                    ),
                    cls="route",
                    named=(str(pid), "stdout"),
                    origin=origin(5),
                ),
                refused,
            )
            route, held, _ticks, still = self.route_row()
            self.assertEqual((route, held, still), ("stdout", pid, since))

    def test_a_reaped_holder_is_taken_over_with_a_new_since(self):
        with self.subTest(id="reaped-holder", origin=origin(5)):
            since = self.take("stdout")
            pid, release = self.owned_holder()
            self.plant_holder(pid)
            release()
            self.assertFalse(self.alive(pid), "the holder was not reaped")
            self.take("native")
            route, _pid, _ticks, renewed = self.route_row()
            self.assertEqual(route, "native")
            self.assertNotEqual(renewed, since)


class TheAdditiveSchema(CoreCase):
    """origin: sessions-lever.md#slice-2 12

    The three tables are additive. A store the current schema populated
    opens with every one of those rows still present.
    """

    def test_opening_keeps_every_row_and_gains_the_tables(self):
        self.bind()
        sent = self.send(BODY)
        self.assertEqual(sent.exit, 0, sent.stderr)
        before = self.snapshot()
        self.assertTrue(before.get("participants"))
        self.assertTrue(before.get("messages"))
        opened = self.core("who", expect=0)
        self.assertIn("PT-1", opened.stdout)
        after = self.snapshot()
        for table, rows in before.items():
            self.assertIn(table, after, table)
            for row in rows:
                self.assertIn(row, after[table], f"{table} lost a row")
        for name in NEW_TABLES:
            self.assertIn(name, after, name)


if __name__ == "__main__":
    unittest.main()
