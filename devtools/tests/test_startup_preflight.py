"""The initial roll call reuses doctor under one bounded child-process budget."""

import json
import time
import unittest
from unittest.mock import patch

from fixtures.commands import CommandFixture

from devtools.readiness import doctor, startup_preflight


class StartupPreflightTests(CommandFixture, unittest.TestCase):
    def script(self, source):
        path = self.root / "doctor_fixture.py"
        path.write_text(source)
        return patch("devtools.readiness.ENTRY", path)

    def test_command_only_team_does_not_require_unconfigured_php_or_project(self):
        result = doctor(self.state, startup=True)
        self.assertEqual("preflight_passed", result["status"], result)
        checks = {row["name"]: row for row in result["checks"]}
        self.assertEqual("not_checked", checks["project"]["status"])
        self.assertNotIn("locked PHP platform", checks)
        self.assertNotIn("Serena image", checks)
        self.assertEqual("not established by preflight", result["authenticated_acceptance"])
        wrapped = startup_preflight(self.state, 5)
        self.assertEqual(result, wrapped)

    def test_keeps_failed_checks_and_rejects_malformed_or_failed_worker_output(self):
        failure = {"status": "blocked", "checks": [{"name": "dependency", "status": "failed", "detail": "Unavailable"}]}
        with self.script("import sys\nprint(" + repr(json.dumps(failure)) + ")\nsys.exit(2)\n"):
            self.assertEqual(failure, startup_preflight(self.state, 2))
        for source in ("print('not JSON')", "print('{}')", "import sys\nsys.exit(1)",
                       "print('{\"status\":\"blocked\",\"checks\":[]}')"):
            with self.subTest(source=source), self.script(source):
                result = startup_preflight(self.state, 2)
                self.assertEqual("blocked", result["status"])
                self.assertIn("valid bounded result", result["checks"][0]["detail"])

    def test_deadline_kills_probe_descendants_and_reaps_the_worker(self):
        # The descendant inherits stdout. communicate() cannot finish until
        # both it and the parent close that pipe, proving group cleanup.
        with self.script("import subprocess,sys,time\n"
                         "subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
                         "time.sleep(30)\n"):
            started = time.monotonic()
            result = startup_preflight(self.state, 0.2)
            self.assertLess(time.monotonic() - started, 3)
            self.assertEqual("blocked", result["status"])
            self.assertIn("exceeded", result["checks"][0]["detail"])

    def test_invalid_budget_does_not_start_a_process(self):
        with patch("devtools.readiness.subprocess.Popen") as launch:
            for timeout in (0, -1, True, float("inf"), float("nan")):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    startup_preflight(self.state, timeout)
            launch.assert_not_called()
