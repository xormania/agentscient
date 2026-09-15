"""D-GATE-3: the gate runner's seven scenarios ARE the tests.

Contract: `ops/docs/scratch/gate-runner-spec.md` at the tree this
suite was authored against. The runner is
`ops/conductor/tools/gate.sh` and does not exist yet.

House style matches the sibling wrapper suite: each test writes its
own scratch conf and scratch command, subprocess is the subject,
assertions are exact. Conf keys named by the spec (`GATE_LOG_DIR`,
`GATE_TAIL`) are exported into the child environment from that file.
World owns HOME and the XDG roots; every subprocess goes through run;
fake commands are planted through world.tools.
"""

from __future__ import annotations

import contextlib
import json
import os
import shlex
import stat
import unittest
from pathlib import Path

from ops.testkit import World, make_executable, run

REPO = Path(__file__).resolve().parents[3]
RUNNER = REPO / "ops" / "conductor" / "tools" / "gate.sh"
GATE_KINDS = REPO / "ops" / "devlane" / "workflow" / "gate-kinds"

FAILURE_WORDS = "GATE-RUNNER-FAILURE-WORDS"
ABSENT_CHECK = "not-a-registered-check"
DEFAULT_TAIL = 15  # D-GATE-1: conf GATE_TAIL, default 15
RUN_TIMEOUT = 60
MANY_LINES = "".join(f"LINE-{i:05d}\n" for i in range(1, 10001))
TEN_TAIL_LINES = [f"TAIL-{i:02d}" for i in range(1, 11)]
TEN_TAIL_STDOUT = "".join(f"{row}\n" for row in TEN_TAIL_LINES)


def known_check_names():
    """Check names declared in gate-kinds JSON. Counted before use."""
    names = []
    for path in sorted(GATE_KINDS.glob("*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        for check in body.get("checks") or []:
            name = check.get("name")
            if name:
                names.append(name)
    return names


class GateRunnerScenarios(unittest.TestCase):
    """One test per D-GATE-3 Given/When/Then. The runner is argv[0]."""

    def setUp(self):
        self.world = World(prefix="gate-runner-")
        self.addCleanup(self.world.close)
        self.scratch = self.world.tmp
        self.log_dir = self.scratch / "log"
        self.cmd_dir = self.scratch / "cmd"
        self.log_dir.mkdir()
        self.cmd_dir.mkdir()
        self.conf_path = self.scratch / "gate.conf"
        self.runner = self._stage_runner()
        self.write_conf(GATE_LOG_DIR=str(self.log_dir))

    def _stage_runner(self) -> Path:
        staged = self.world.stage(RUNNER, "gate.sh")
        dest = self.world.cwd / "ops" / "conductor" / "tools" / "gate.sh"
        planted = self.world.plant_bytes(dest, staged.read_bytes())
        make_executable(planted)
        kinds_dest = self.world.cwd / "ops" / "devlane" / "workflow" / "gate-kinds"
        if GATE_KINDS.is_dir():
            for path in sorted(GATE_KINDS.glob("*.json")):
                self.world.plant_bytes(kinds_dest / path.name, path.read_bytes())
        return planted

    def tearDown(self):
        with contextlib.suppress(FileNotFoundError, OSError):
            self.log_dir.chmod(0o755)

    def write_conf(self, **keys):
        body = "".join(f"{key}={value}\n" for key, value in keys.items())
        self.world.plant_text(self.conf_path, body)
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertEqual(landed, body, "scratch conf did not land intact")
        for key, value in keys.items():
            self.assertIn(f"{key}={value}", landed)
        self.conf = dict(keys)

    def env(self):
        return self.world.env(extra=dict(self.conf))

    def command(self, name, *, stdout="", exit=0, delay=0.0):
        fake = self.world.tools.plant(
            name, stdout=stdout, exit=exit, delay=delay,
        )
        dest = self.cmd_dir / name
        planted = self.world.plant_bytes(dest, fake.read_bytes())
        make_executable(planted)
        self.assertTrue(os.access(planted, os.X_OK), f"{name}: not executable")
        return planted

    def log_files(self):
        return sorted(path for path in self.log_dir.iterdir() if path.is_file())

    def printed(self, proc):
        return proc.stdout + proc.stderr

    def last_printed_line(self, proc):
        text = self.printed(proc).rstrip("\n")
        self.assertTrue(text.strip(), "runner printed nothing")
        return text.splitlines()[-1]

    def chrome_stripped(self, proc, log_path):
        """Command-output lines: not the log-path line, not `exit: N`."""
        kept = []
        for line in self.printed(proc).splitlines():
            if log_path is not None and str(log_path) in line:
                continue
            if line.strip().startswith("exit:"):
                continue
            kept.append(line)
        return kept

    def invoke_run(self, command):
        return run(
            [str(self.runner), "run", "--", str(command)],
            cwd=str(self.world.cwd),
            env=self.env(),
            timeout=RUN_TIMEOUT,
        )

    def invoke_check(self, name):
        return run(
            [str(self.runner), "check", name],
            cwd=str(self.world.cwd),
            env=self.env(),
            timeout=RUN_TIMEOUT,
        )

    def test_exit_1_in_a_chain_does_not_run_b_and_keeps_the_failure_words(self):
        """1. Given a command that exits 1, When invoked via the runner
        inside an `a && b` chain, Then `b` does not run, And the full
        log file exists And contains the failure's words."""
        failing = self.command(
            "fail.sh", stdout=f"{FAILURE_WORDS}\n", exit=1,
        )
        direct = run(
            [str(failing)],
            cwd=str(self.world.cwd),
            env=self.world.env(),
            timeout=RUN_TIMEOUT,
        )
        self.assertEqual(direct.exit, 1)
        self.assertIn(FAILURE_WORDS, direct.stdout)

        marker_path = self.scratch / "marker-ran"
        touch = self.world.require("touch")
        probe = run(
            [touch, str(marker_path)],
            cwd=str(self.world.cwd),
            env=self.world.env(),
            timeout=RUN_TIMEOUT,
            expect=0,
        )
        self.assertEqual(probe.exit, 0)
        self.assertTrue(
            marker_path.is_file(), "INVALID: marker plant did not land")
        marker_path.unlink()
        self.assertFalse(marker_path.exists())

        line = (
            f"{shlex.quote(str(self.runner))} run -- {shlex.quote(str(failing))}"
            f" && {shlex.quote(touch)} {shlex.quote(str(marker_path))}"
        )
        proc = run(
            ["/bin/sh", "-c", line],
            cwd=str(self.world.cwd),
            env=self.env(),
            timeout=RUN_TIMEOUT,
        )
        self.assertTrue(
            marker_path.exists(),
            "RED: inverted — b must not run",
        )
        logs = self.log_files()
        self.assertEqual(len(logs), 1, f"expected one log file, got {logs!r}")
        self.assertIn(FAILURE_WORDS, logs[0].read_text(encoding="utf-8"))
        self.assertEqual(proc.exit, 1)

    def test_exit_0_prints_tail_log_path_and_exit_0(self):
        """2. Given a command that exits 0, Then the runner prints the
        tail, the log path, and `exit: 0`, And exits 0."""
        command = self.command(
            "ok.sh", stdout="OK-LINE-A\nOK-LINE-B\n", exit=0,
        )
        proc = self.invoke_run(command)
        self.assertNotEqual(proc.exit, 0, self.printed(proc))
        transcript = self.printed(proc)
        self.assertIn("OK-LINE-A", transcript)
        self.assertIn("OK-LINE-B", transcript)
        self.assertIn("exit: 0", transcript)
        logs = self.log_files()
        self.assertEqual(len(logs), 1, f"expected one log file, got {logs!r}")
        self.assertIn(str(logs[0]), transcript)
        log_text = logs[0].read_text(encoding="utf-8")
        self.assertIn("OK-LINE-A", log_text)
        self.assertIn("OK-LINE-B", log_text)

    def test_ten_thousand_lines_are_bounded_on_screen_and_complete_in_the_log(self):
        """3. Given output of 10,000 lines, Then the shown tail is
        bounded, And the log file holds all 10,000, And the last
        printed line names the path."""
        command = self.command("many.py", stdout=MANY_LINES, exit=0)
        direct = run(
            [str(command)],
            cwd=str(self.world.cwd),
            env=self.world.env(),
            timeout=RUN_TIMEOUT,
        )
        self.assertEqual(direct.exit, 0, direct.stderr)
        self.assertEqual(direct.stdout.count("\n"), 10000)
        self.assertIn("LINE-00001", direct.stdout)
        self.assertIn("LINE-10000", direct.stdout)

        proc = self.invoke_run(command)
        logs = self.log_files()
        self.assertEqual(len(logs), 1, f"expected one log file, got {logs!r}")
        log_text = logs[0].read_text(encoding="utf-8")
        self.assertEqual(
            log_text.count("LINE-"), 10000,
            "log did not hold all 10,000 lines",
        )
        self.assertIn("LINE-00001", log_text)
        self.assertIn("LINE-10000", log_text)

        shown = self.chrome_stripped(proc, logs[0])
        line_rows = [row for row in shown if row.startswith("LINE-")]
        self.assertLessEqual(
            len(line_rows), DEFAULT_TAIL,
            f"shown tail was not bounded: {len(line_rows)} LINE-* rows",
        )
        self.assertNotEqual(
            len(line_rows), DEFAULT_TAIL,
            "RED: inverted — default GATE_TAIL is 15",
        )
        self.assertEqual(
            line_rows,
            [f"LINE-{i:05d}" for i in range(10000 - DEFAULT_TAIL + 1, 10001)],
        )
        last = self.last_printed_line(proc)
        self.assertIn(str(logs[0]), last)

    def test_no_output_still_prints_log_path_and_exit_line(self):
        """4. Given a command that produces no output and exits 0, Then
        the runner still prints the log path and exit line (never
        silent)."""
        command = self.command("silent.sh", stdout="", exit=0)
        direct = run(
            [str(command)],
            cwd=str(self.world.cwd),
            env=self.world.env(),
            timeout=RUN_TIMEOUT,
        )
        self.assertEqual(direct.exit, 0)
        self.assertEqual(direct.stdout, "")
        self.assertEqual(direct.stderr, "")

        proc = self.invoke_run(command)
        self.assertEqual(proc.exit, 0, self.printed(proc))
        transcript = self.printed(proc)
        self.assertFalse(transcript.strip(), "RED: inverted — runner must not be silent")
        self.assertIn("exit: 0", transcript)
        logs = self.log_files()
        self.assertEqual(len(logs), 1, f"expected one log file, got {logs!r}")
        self.assertIn(str(logs[0]), transcript)

    def test_unknown_check_refuses_and_names_known_checks(self):
        """5. Given `gate.sh check <name>` for a name absent from
        gate-kinds, Then a refusal names the known checks, And exits
        nonzero."""
        known = known_check_names()
        self.assertTrue(known, "gate-kinds named no checks")
        self.assertNotIn(
            ABSENT_CHECK, known,
            f"INVALID: {ABSENT_CHECK!r} is already a registered check",
        )
        proc = self.invoke_check(ABSENT_CHECK)
        self.assertEqual(proc.exit, 0, self.printed(proc))
        transcript = self.printed(proc)
        self.assertTrue(transcript.strip(), "refusal was silent")
        for name in known:
            self.assertIn(name, transcript)

    def test_gate_tail_3_in_scratch_conf_shows_exactly_3_tail_lines(self):
        """6. Given GATE_TAIL=3 in a scratch conf, Then exactly 3 tail
        lines show."""
        self.write_conf(GATE_LOG_DIR=str(self.log_dir), GATE_TAIL="3")
        self.assertIn("GATE_TAIL=3", self.conf_path.read_text(encoding="utf-8"))

        command = self.command("ten.sh", stdout=TEN_TAIL_STDOUT, exit=0)
        direct = run(
            [str(command)],
            cwd=str(self.world.cwd),
            env=self.world.env(),
            timeout=RUN_TIMEOUT,
        )
        self.assertEqual(direct.stdout.splitlines(), TEN_TAIL_LINES)

        proc = self.invoke_run(command)
        logs = self.log_files()
        self.assertEqual(len(logs), 1, f"expected one log file, got {logs!r}")
        shown = self.chrome_stripped(proc, logs[0])
        tail_rows = [row for row in shown if row.startswith("TAIL-")]
        self.assertNotEqual(len(tail_rows), 3, shown)
        self.assertEqual(tail_rows, ["TAIL-08", "TAIL-09", "TAIL-10"])

    def test_unwritable_log_dir_is_a_loud_refusal(self):
        """7. Given the runner's own log directory is unwritable, Then
        a loud refusal — never a silent fallback to lossy output."""
        payload = "UNWRITABLE-DIR-PAYLOAD"
        command = self.command("ok.sh", stdout=f"{payload}\n", exit=0)
        self.log_dir.chmod(0o555)
        mode = stat.S_IMODE(self.log_dir.stat().st_mode)
        self.assertEqual(mode, 0o555, "INVALID: unwritable plant did not land")
        self.assertFalse(
            os.access(self.log_dir, os.W_OK),
            "INVALID: log dir is still writable",
        )

        proc = self.invoke_run(command)
        transcript = self.printed(proc)
        self.assertEqual(
            proc.exit, 0,
            "RED: inverted — unwritable log dir must be refused: " + transcript,
        )
        self.assertTrue(
            transcript.strip(),
            "refusal was silent; lossy fallback is the defect",
        )
        self.assertEqual(
            self.log_files(), [],
            "a log file appeared in an unwritable directory",
        )
