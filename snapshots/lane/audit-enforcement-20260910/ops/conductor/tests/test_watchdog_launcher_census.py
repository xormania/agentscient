"""PR 66 item 1: launcher census pgrep ERE for absolute/versioned Python.

Contract: ops/conductor/pr66-fixes.md item 1. Reuses the watchdog
fixture; does not read the tool source. The pattern passed to pgrep
must be valid POSIX ERE, match python3 as a basename or absolute
versioned python3.N next to launch.py, and not count unrelated
commands. The census stays a named heuristic.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from test_watchdog import _WatchdogFixture  # noqa: E402

PGREP_LOG = "pgrep-argv.jsonl"

LAUNCH_CMDLINES = (
    "python3 ops/devlane/dispatch/launch.py --job author-tests",
    "/usr/bin/python3 ops/devlane/dispatch/launch.py --job author-tests",
    "python3.12 ops/devlane/dispatch/launch.py --job author-tests",
    "/usr/bin/python3.13 ops/devlane/dispatch/launch.py --job author-tests",
    "/usr/local/bin/python3.11 ops/devlane/dispatch/launch.py --once",
)

UNRELATED_CMDLINES = (
    "python2 ops/devlane/dispatch/launch.py --job author-tests",
    "/usr/bin/python ops/devlane/dispatch/launch.py --job author-tests",
    "bash ops/devlane/dispatch/launch.py --job author-tests",
    "python3 ops/devlane/dispatch/other.py --job author-tests",
    "python3.12-config --ldflags",
    "/usr/bin/python3.13-coverage run ops/devlane/dispatch/launch.py",
    "node ops/devlane/dispatch/launch.py",
)


def _pgrep_pattern(argv: list[str]) -> str:
    flags = {"-f", "-c", "-fc", "-cf", "-a", "-l"}
    tokens = [item for item in argv if item not in flags and not item.startswith("-")]
    if not tokens:
        raise AssertionError(f"pgrep argv has no pattern: {argv!r}")
    return tokens[-1]


def _ere_run(pattern: str, text: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["POSIXLY_CORRECT"] = "1"
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return subprocess.run(
        ["grep", "-E", "-e", pattern],
        input=text if text.endswith("\n") else text + "\n",
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


class LauncherCensusPgrep(_WatchdogFixture):
    """The census pattern is valid ERE and matches versioned/absolute python3."""

    def plant_pgrep(self) -> Path:
        log = self.scratch / PGREP_LOG
        self.assertFalse(log.exists(), "plant: pgrep argv log must start absent")
        body = (
            "#!/usr/bin/env python3\n"
            "from __future__ import annotations\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            f"log = Path({str(log)!r})\n"
            "prev = log.read_text(encoding='utf-8') if log.is_file() else ''\n"
            "log.write_text("
            "prev + json.dumps(sys.argv[1:]) + '\\n', encoding='utf-8')\n"
            "sys.stdout.write('0\\n')\n"
            "raise SystemExit(0)\n"
        )
        path = self.bin / "pgrep"
        self._plant_bytes(path, body.encode("utf-8"))
        self._make_executable(path)
        self.assertEqual(path.read_text(encoding="utf-8"), body)
        self.assertTrue(os.access(path, os.X_OK), f"not executable: {path}")
        return log

    def pgrep_argvs(self, log: Path) -> list[list[str]]:
        if not log.is_file():
            return []
        rows = []
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def captured_pattern(self, log: Path) -> str:
        argvs = self.pgrep_argvs(log)
        self.assertTrue(argvs, f"watchdog did not invoke pgrep: {log}")
        patterns = [_pgrep_pattern(argv) for argv in argvs]
        self.assertTrue(patterns, f"pgrep invocations had no pattern: {argvs!r}")
        first = patterns[0]
        self.assertTrue(
            all(item == first for item in patterns),
            f"pgrep pattern drifted across invocations: {patterns!r}",
        )
        return first

    def test_pgrep_pattern_is_valid_posix_ere(self):
        log = self.plant_pgrep()
        self.ensure_store()
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        beats = self.heartbeat_lines(proc)
        self.assertEqual(len(beats), 1, proc.stdout)
        self.assertIn("launchers=", beats[0])
        self.assertNotIn("launchers=unreachable", beats[0])
        pattern = self.captured_pattern(log)
        self.assertIsInstance(pattern, str)
        self.assertTrue(pattern, "pgrep pattern was empty")
        check = _ere_run(pattern, "python3 ops/devlane/dispatch/launch.py --once")
        self.assertNotEqual(
            check.returncode,
            2,
            f"pgrep pattern is not valid POSIX ERE: {pattern!r} stderr={check.stderr!r}",
        )

    def test_pgrep_pattern_matches_basename_absolute_and_versioned_python3(self):
        log = self.plant_pgrep()
        self.ensure_store()
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        pattern = self.captured_pattern(log)
        ere_ok = _ere_run(pattern, LAUNCH_CMDLINES[0])
        self.assertNotEqual(ere_ok.returncode, 2, ere_ok.stderr)
        missed = []
        for cmdline in LAUNCH_CMDLINES:
            matched = _ere_run(pattern, cmdline)
            self.assertNotEqual(
                matched.returncode,
                2,
                f"pattern {pattern!r} is not valid POSIX ERE on {cmdline!r}",
            )
            if matched.returncode != 0:
                missed.append(cmdline)
        self.assertEqual(
            missed,
            [],
            f"pattern {pattern!r} missed launch.py under python3 paths: {missed!r}",
        )

    def test_pgrep_pattern_does_not_count_unrelated_commands(self):
        log = self.plant_pgrep()
        self.ensure_store()
        proc = self.once(extra=["--heartbeat-every", "1"])
        self.assert_armed(proc, store=self.store)
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        pattern = self.captured_pattern(log)
        hits = []
        for cmdline in UNRELATED_CMDLINES:
            matched = _ere_run(pattern, cmdline)
            self.assertNotEqual(matched.returncode, 2, matched.stderr)
            if matched.returncode == 0:
                hits.append(cmdline)
        self.assertEqual(
            hits,
            [],
            f"pattern {pattern!r} counted unrelated commands: {hits!r}",
        )
        beats = self.heartbeat_lines(proc)
        self.assertEqual(len(beats), 1, proc.stdout)
        self.assertRegex(beats[0], r"launchers=(\d+|unreachable)")


if __name__ == "__main__":
    unittest.main()
