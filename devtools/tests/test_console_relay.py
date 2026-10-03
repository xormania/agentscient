"""Exercise the CO terminal transport without a vendor CLI or account."""

import errno
import json
import os
import pty
import select
import signal
import subprocess
import sys
import tempfile
import termios
import time
import tty
import unittest
from pathlib import Path

from devtools.console import relay

MODULE = "devtools.tests.test_console_relay"
ROOT = Path(__file__).resolve().parents[2]


def native_fixture():
    # Raw mode prevents the PTY echo from masquerading as received commands.
    tty.setraw(sys.stdin.fileno())
    print("NATIVE READY", flush=True)
    pending = b""
    while True:
        pending += os.read(sys.stdin.fileno(), 4096)
        while b"\n" in pending:
            command, pending = pending.split(b"\n", 1)
            print("RECEIVED " + json.dumps(command.decode()), flush=True)
            if command == b"/quit":
                # Include an unterminated final line to check the exit drain.
                print("NATIVE EXIT", end="", flush=True)
                return


def relay_fixture(report):
    class Trace:
        def record(self, kind, data):
            if kind == "process_started":
                report.with_suffix(".pid").write_text(str(data["pid"]))

    signals = (signal.SIGWINCH, signal.SIGTERM, signal.SIGHUP)
    before = [signal.getsignal(sig) for sig in signals]
    code = relay([sys.executable, "-m", MODULE, "--native-fixture"],
                 os.environ.copy(), ROOT, Trace(), lambda: True)
    report.write_text(json.dumps({
        "exit_code": code,
        "handlers_restored": before == [signal.getsignal(sig) for sig in signals],
    }))


class ConsoleRelayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.report = Path(temporary.name) / "result.json"

    def start(self, **streams):
        process = subprocess.Popen(
            [sys.executable, "-m", MODULE, "--relay-fixture", str(self.report)],
            cwd=ROOT, **streams,
        )
        self.addCleanup(self.stop, process)
        return process

    def stop(self, process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=7)
            except subprocess.TimeoutExpired:
                pid_file = self.report.with_suffix(".pid")
                if pid_file.exists():
                    try:
                        os.killpg(int(pid_file.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.kill()
                process.wait(timeout=3)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def read_until(self, fd, marker):
        output = b""
        deadline = time.monotonic() + 10
        while marker not in output and time.monotonic() < deadline:
            if not select.select([fd], [], [], 0.1)[0]:
                continue
            try:
                chunk = os.read(fd, 65536)
            except OSError as error:
                if error.errno != errno.EIO:
                    raise
                break
            if not chunk:
                break
            output += chunk
        self.assertIn(marker, output, output.decode(errors="replace"))
        return output

    def result(self, process):
        self.assertEqual(0, process.wait(timeout=10))
        result = json.loads(self.report.read_text())
        self.assertTrue(result["handlers_restored"])
        pid = int(self.report.with_suffix(".pid").read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        return result

    def test_native_commands_and_quit_pass_through_and_restore_terminal(self):
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        original = termios.tcgetattr(slave)
        process = self.start(stdin=slave, stdout=slave, stderr=slave)
        self.read_until(master, b"NATIVE READY")
        commands = ["/model alternate-model", "/effort high", "/quit"]
        os.write(master, ("\n".join(commands) + "\n").encode())
        output = self.read_until(master, b"NATIVE EXIT").decode()
        received = [json.loads(line.removeprefix("RECEIVED "))
                    for line in output.splitlines() if line.startswith("RECEIVED ")]
        self.assertEqual(commands, received)
        self.assertEqual(0, self.result(process)["exit_code"])
        self.assertEqual(original, termios.tcgetattr(slave))

    def test_stdin_eof_terminates_native_child_and_returns(self):
        process = self.start(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.read_until(process.stdout.fileno(), b"NATIVE READY")
        process.stdin.close()
        self.assertEqual(-signal.SIGTERM, self.result(process)["exit_code"])


if __name__ == "__main__":
    if sys.argv[1:] == ["--native-fixture"]:
        native_fixture()
    elif len(sys.argv) == 3 and sys.argv[1] == "--relay-fixture":
        relay_fixture(Path(sys.argv[2]))
    else:
        unittest.main()
