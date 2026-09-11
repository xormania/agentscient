"""LD-19 (2026-09-11): only test modules become test commands.

Measured: ladder 20260911T040533Z-ladder-fd103b's tests envelope listed
``ops/devlane/dispatch/tests/launch_support.py`` among its artifacts; the
driver turned every ``.py`` under a ``tests/`` directory into a
``python3 -m unittest discover -p <file>`` run, and discovery over a
support module found zero tests and exited 5. Both code attempts were
stopped by that command (records 532808 and 3122df), never by the worker.

Contract: a test artifact becomes a command only when its file name
matches unittest's default pattern ``test*.py``; other files under
``tests/`` ride as artifacts and are not run.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LADDER = ROOT / "ops" / "conductor" / "tools" / "ladder.py"


def _load():
    spec = importlib.util.spec_from_file_location("ladder_support_under_test", LADDER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Stub:
    def __init__(self):
        self.conf = {"SCOPE_CAP": "4096"}
        self.written = {}

    def make_input(self, name, body):
        self.written[name] = body
        return Path(f"/dev/null/{name}")


class OnlyTestModulesBecomeCommands(unittest.TestCase):
    def setUp(self):
        self.mod = _load()
        self.stub = _Stub()

    def derive(self, artifacts):
        self.mod.Driver.derive_command(self.stub, {"artifacts": artifacts})
        return self.stub.written["test-command"]

    def test_a_support_module_under_tests_is_not_run(self):
        command = self.derive({
            "test": "ops/devlane/dispatch/tests/test_gate.py",
            "support": "ops/devlane/dispatch/tests/launch_support.py",
        })
        self.assertIn("-p test_gate.py", command)
        self.assertNotIn("launch_support", command)
        self.assertNotIn("&&", command)

    def test_two_test_modules_join_in_order(self):
        command = self.derive({
            "a": "ops/x/tests/test_a.py",
            "b": "ops/x/tests/test_b.py",
        })
        self.assertEqual(
            command,
            "python3 -m unittest discover -s ops/x/tests -p test_a.py && "
            "python3 -m unittest discover -s ops/x/tests -p test_b.py",
        )

    def test_only_support_modules_is_an_artifacts_stop(self):
        with self.assertRaises(self.mod.Stopped) as caught:
            self.derive({"support": "ops/x/tests/launch_support.py"})
        self.assertEqual(caught.exception.reason, "artifacts")


if __name__ == "__main__":
    unittest.main()
