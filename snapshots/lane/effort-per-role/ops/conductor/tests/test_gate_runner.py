"""D-GATE-3: the gate runner's seven scenarios ARE the tests.

Contract: `ops/docs/scratch/gate-runner-spec.md` at the tree this
suite was authored against. The runner is
`ops/conductor/tools/gate.sh` and does not exist yet.

House style matches the sibling wrapper suite: each test writes its
own scratch conf and scratch command, subprocess is the subject,
assertions are exact. Conf keys named by the spec (`GATE_LOG_DIR`,
`GATE_TAIL`) are exported into the child environment from that file.
"""

from __future__ import annotations

import contextlib
import json
import os
import shlex
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RUNNER = REPO / "ops" / "conductor" / "tools" / "gate.sh"
GATE_KINDS = REPO / "ops" / "devlane" / "workflow" / "gate-kinds"

FAILURE_WORDS = "GATE-RUNNER-FAILURE-WORDS"
ABSENT_CHECK = "not-a-registered-check"
DEFAULT_TAIL = 15  # D-GATE-1: conf GATE_TAIL, default 15


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
        self.tmp = tempfile.TemporaryDirectory(prefix="gate-runner-")
        self.scratch = Path(self.tmp.name)
        self.log_dir = self.scratch / "log"
        self.cmd_dir = self.scratch / "cmd"
        self.log_dir.mkdir()
        self.cmd_dir.mkdir()
        self.conf_path = self.scratch / "gate.conf"
        self.write_conf(GATE_LOG_DIR=str(self.log_dir))

    def tearDown(self):
        with contextlib.suppress(FileNotFoundError):
            self.log_dir.chmod(0o755)
        self.tmp.cleanup()

    def write_conf(self, **keys):
        body = "".join(f"{key}={value}\n" for key, value in keys.items())
        self.conf_path.write_text(body, encoding="utf-8")
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertEqual(landed, body, "scratch conf did not land intact")
        for key, value in keys.items():
            self.assertIn(f"{key}={value}", landed)
        self.conf = dict(keys)

    def env(self):
        env = os.environ.copy()
        env.pop("GATE_TAIL", None)
        env.pop("GATE_LOG_DIR", None)
        env.update(self.conf)
        return env

    def command(self, name, script):
        path = self.cmd_dir / name
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        landed = path.read_text(encoding="utf-8")
        self.assertEqual(landed, script, f"{name}: scratch command did not land")
        self.assertTrue(os.access(path, os.X_OK), f"{name}: not executable")
        return path

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
        self.assertTrue(
            RUNNER.is_file(), f"RED: runner is absent: {RUNNER}")
        return subprocess.run(
            [str(RUNNER), "run", "--", str(command)],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            env=self.env(),
            check=False,
        )

    def invoke_check(self, name):
        self.assertTrue(
            RUNNER.is_file(), f"RED: runner is absent: {RUNNER}")
        return subprocess.run(
            [str(RUNNER), "check", name],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            env=self.env(),
            check=False,
        )

    def test_exit_1_in_a_chain_does_not_run_b_and_keeps_the_failure_words(self):
        """1. Given a command that exits 1, When invoked via the runner
        inside an `a && b` chain, Then `b` does not run, And the full
        log file exists And contains the failure's words."""
        failing = self.command(
            "fail.sh",
            "#!/bin/sh\n"
            f"printf '%s\\n' '{FAILURE_WORDS}'\n"
            "exit 1\n",
        )
        direct = subprocess.run(
            [str(failing)], capture_output=True, text=True, check=False,
        )
        self.assertEqual(direct.returncode, 1)
        self.assertIn(FAILURE_WORDS, direct.stdout)

        marker_path = self.scratch / "marker-ran"
        marker = self.command(
            "mark.sh",
            "#!/bin/sh\n"
            f"exec touch {shlex.quote(str(marker_path))}\n",
        )
        probe = subprocess.run([str(marker)], check=False)
        self.assertEqual(probe.returncode, 0)
        self.assertTrue(
            marker_path.is_file(), "INVALID: marker plant did not land")
        marker_path.unlink()
        self.assertFalse(marker_path.exists())
        self.assertTrue(
            RUNNER.is_file(), f"RED: runner is absent: {RUNNER}")

        line = (
            f"{shlex.quote(str(RUNNER))} run -- {shlex.quote(str(failing))}"
            f" && {shlex.quote(str(marker))}"
        )
        proc = subprocess.run(
            ["/bin/sh", "-c", line],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            env=self.env(),
            check=False,
        )
        self.assertFalse(
            marker_path.exists(),
            "b ran; the runner's exit was swallowed",
        )
        logs = self.log_files()
        self.assertEqual(len(logs), 1, f"expected one log file, got {logs!r}")
        self.assertIn(FAILURE_WORDS, logs[0].read_text(encoding="utf-8"))
        self.assertEqual(proc.returncode, 1)

    def test_exit_0_prints_tail_log_path_and_exit_0(self):
        """2. Given a command that exits 0, Then the runner prints the
        tail, the log path, and `exit: 0`, And exits 0."""
        command = self.command(
            "ok.sh",
            "#!/bin/sh\n"
            "printf '%s\\n' 'OK-LINE-A'\n"
            "printf '%s\\n' 'OK-LINE-B'\n"
            "exit 0\n",
        )
        proc = self.invoke_run(command)
        self.assertEqual(proc.returncode, 0, self.printed(proc))
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
        command = self.command(
            "many.py",
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "for i in range(1, 10001):\n"
            "    sys.stdout.write(f'LINE-{i:05d}\\n')\n",
        )
        direct = subprocess.run(
            [str(command)], capture_output=True, text=True, check=False,
        )
        self.assertEqual(direct.returncode, 0, direct.stderr)
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
        self.assertEqual(
            len(line_rows), DEFAULT_TAIL,
            "default GATE_TAIL is 15 (D-GATE-1); shown LINE-* rows "
            f"were {len(line_rows)}",
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
        command = self.command("silent.sh", "#!/bin/sh\nexit 0\n")
        direct = subprocess.run(
            [str(command)], capture_output=True, text=True, check=False,
        )
        self.assertEqual(direct.returncode, 0)
        self.assertEqual(direct.stdout, "")
        self.assertEqual(direct.stderr, "")

        proc = self.invoke_run(command)
        self.assertEqual(proc.returncode, 0, self.printed(proc))
        transcript = self.printed(proc)
        self.assertTrue(transcript.strip(), "runner was silent")
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
        self.assertNotEqual(proc.returncode, 0, self.printed(proc))
        transcript = self.printed(proc)
        self.assertTrue(transcript.strip(), "refusal was silent")
        for name in known:
            self.assertIn(name, transcript)

    def test_gate_tail_3_in_scratch_conf_shows_exactly_3_tail_lines(self):
        """6. Given GATE_TAIL=3 in a scratch conf, Then exactly 3 tail
        lines show."""
        self.write_conf(GATE_LOG_DIR=str(self.log_dir), GATE_TAIL="3")
        self.assertIn("GATE_TAIL=3", self.conf_path.read_text(encoding="utf-8"))

        lines = [f"TAIL-{i:02d}" for i in range(1, 11)]
        body = "#!/bin/sh\n" + "".join(
            f"printf '%s\\n' '{row}'\n" for row in lines
        ) + "exit 0\n"
        command = self.command("ten.sh", body)
        direct = subprocess.run(
            [str(command)], capture_output=True, text=True, check=False,
        )
        self.assertEqual(direct.stdout.splitlines(), lines)

        proc = self.invoke_run(command)
        logs = self.log_files()
        self.assertEqual(len(logs), 1, f"expected one log file, got {logs!r}")
        shown = self.chrome_stripped(proc, logs[0])
        tail_rows = [row for row in shown if row.startswith("TAIL-")]
        self.assertEqual(len(tail_rows), 3, shown)
        self.assertEqual(tail_rows, ["TAIL-08", "TAIL-09", "TAIL-10"])

    def test_unwritable_log_dir_is_a_loud_refusal(self):
        """7. Given the runner's own log directory is unwritable, Then
        a loud refusal — never a silent fallback to lossy output."""
        payload = "UNWRITABLE-DIR-PAYLOAD"
        command = self.command(
            "ok.sh",
            "#!/bin/sh\n"
            f"printf '%s\\n' '{payload}'\n"
            "exit 0\n",
        )
        self.log_dir.chmod(0o555)
        mode = stat.S_IMODE(self.log_dir.stat().st_mode)
        self.assertEqual(mode, 0o555, "INVALID: unwritable plant did not land")
        self.assertFalse(
            os.access(self.log_dir, os.W_OK),
            "INVALID: log dir is still writable",
        )

        proc = self.invoke_run(command)
        transcript = self.printed(proc)
        self.assertNotEqual(
            proc.returncode, 0,
            "unwritable log dir was not refused: " + transcript,
        )
        self.assertTrue(
            transcript.strip(),
            "refusal was silent; lossy fallback is the defect",
        )
        self.assertEqual(
            self.log_files(), [],
            "a log file appeared in an unwritable directory",
        )
