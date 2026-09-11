"""The frozen test command names the tree (LD-15).

Contract: ops/conductor/ladder-lever.md, the sentence "The command names
the tree" and the sentence before it. Test commands come only from test
artifacts in the first test envelope: each path under a tests/ directory
becomes a python3 -m unittest discover invocation, joined in order with
&&. No such artifact is an artifacts stop, never an invented command.
An artifact given as an absolute path is accepted only when it lies
under a dispatch snapshot and is recorded as the part after snapshot/;
any other absolute path, or a .. component, is an artifacts stop naming
the path.

The subject is Driver.derive_command(tests_envelope) in
ops/conductor/tools/ladder.py. The driver is not read here. The call is
made on a stub with conf SCOPE_CAP 4096 and a make_input that records
the body.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DRIVER_PATH = REPO / "ops" / "conductor" / "tools" / "ladder.py"
DRIVER_NAME = "ladder_command_names_subject"

REL = "ops/conductor/tests/test_command_tree.py"
REL_A = "ops/conductor/tests/test_command_tree_a.py"
REL_B = "packages/relay/tests/test_command_tree_b.py"
NON_PY = "ops/conductor/tests/notes.md"
OUTSIDE = "ops/conductor/tools/helper.py"
DOTDOT = "ops/conductor/tests/../tests/test_command_tree.py"
ABS_SNAP = (
    "/var/tmp/dispatch/20260911T042054Z-job-ld15/snapshot/"
    "ops/conductor/tests/test_command_tree.py"
)
ABS_SNAP_DIR = (
    "/var/tmp/dispatch/20260911T042054Z-job-ld15/snapshot/"
    "ops/conductor/tests"
)
ABS_OTHER = "/var/tmp/worker-tree/ops/conductor/tests/test_command_tree.py"

DISCOVER_REL = (
    "python3 -m unittest discover -s ops/conductor/tests "
    "-p test_command_tree.py"
)
DISCOVER_A = (
    "python3 -m unittest discover -s ops/conductor/tests "
    "-p test_command_tree_a.py"
)
DISCOVER_B = (
    "python3 -m unittest discover -s packages/relay/tests "
    "-p test_command_tree_b.py"
)


def load_ladder(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    sys.modules.pop(name, None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _Stub:
    """conf and a make_input that records the body, as the brief requires."""

    conf = {"SCOPE_CAP": "4096"}

    def __init__(self):
        self.names = []
        self.bodies = []

    def make_input(self, name, body):
        self.names.append(name)
        self.bodies.append(body)
        return Path(name)

    def stop(self, stopped):
        raise stopped


class LadderCommandNamesTheTree(unittest.TestCase):
    """derive_command records a tree-relative discover command, or stops."""

    @classmethod
    def setUpClass(cls):
        if not DRIVER_PATH.is_file():
            raise AssertionError(f"missing driver {DRIVER_PATH}")
        cls.ladder = load_ladder(DRIVER_PATH, DRIVER_NAME)

    def derive(self, artifacts):
        stub = _Stub()
        envelope = {"artifacts": artifacts}
        result = self.ladder.Driver.derive_command(stub, envelope)
        return stub, result

    def command_for(self, artifacts):
        stub, _result = self.derive(artifacts)
        self.assertEqual(len(stub.bodies), 1, stub.bodies)
        return stub.bodies[0]

    def stop_for(self, artifacts):
        with self.assertRaises(self.ladder.Stopped) as caught:
            self.derive(artifacts)
        return caught.exception

    def test_relative_artifact_under_tests_is_discover(self):
        command = self.command_for({"tree": REL})
        self.assertEqual(command, DISCOVER_REL)

    def test_absolute_artifact_under_snapshot_uses_path_after_snapshot(self):
        command = self.command_for({"tree": ABS_SNAP})
        self.assertEqual(command, DISCOVER_REL)
        self.assertNotIn(ABS_SNAP_DIR, command)
        self.assertNotIn(ABS_SNAP, command)

    def test_absolute_artifact_without_snapshot_is_an_artifacts_stop(self):
        stopped = self.stop_for({"tree": ABS_OTHER})
        self.assertEqual(stopped.reason, "artifacts")
        self.assertIsNotNone(stopped.detail)
        self.assertIn(ABS_OTHER, stopped.detail)

    def test_dotdot_component_is_an_artifacts_stop(self):
        stopped = self.stop_for({"tree": DOTDOT})
        self.assertEqual(stopped.reason, "artifacts")
        self.assertIsNotNone(stopped.detail)
        self.assertIn(DOTDOT, stopped.detail)

    def test_two_artifacts_join_in_order_with_and(self):
        command = self.command_for({"first": REL_A, "second": REL_B})
        self.assertEqual(command, f"{DISCOVER_A} && {DISCOVER_B}")
        self.assertEqual(len(command.split(" && ")), 2, command)

    def test_non_py_artifact_is_ignored(self):
        command = self.command_for({"notes": NON_PY, "tree": REL})
        self.assertEqual(command, DISCOVER_REL)
        self.assertNotIn("notes.md", command)

    def test_artifact_outside_tests_is_ignored(self):
        command = self.command_for({"tool": OUTSIDE, "tree": REL})
        self.assertEqual(command, DISCOVER_REL)
        self.assertNotIn("helper.py", command)
        self.assertNotIn("conductor/tools", command)

    def test_no_artifact_is_an_artifacts_stop(self):
        stopped = self.stop_for({})
        self.assertEqual(stopped.reason, "artifacts")
