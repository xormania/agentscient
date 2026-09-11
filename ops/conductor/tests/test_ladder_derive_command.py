"""LD-15 (2026-09-11): the frozen test command names the tree, never a
tests worker's snapshot.

Measured: ladder 20260911T025531Z-ladder-a9343f stopped at its code
stage with an invalid envelope. Its tests record 5a362c had written the
artifact as an absolute path into its own snapshot
(`<state>/dispatch/<id>/snapshot/ops/conductor/tests/…py`), and
`derive_command` used that path verbatim, so the implementer's named
command ran the tests worker's unchanged tree and failed. Slice 2's
tests record wrote relative paths and its command was relative.

Contract (LD-15): each test artifact path is recorded relative to the
tree. An absolute path is accepted only when it lies under a dispatch
snapshot (a `snapshot` directory component), and is rewritten to the
part after it; any other absolute path, or a path with `..`, is an
`artifacts` stop that names the path, never a command that tests
another tree.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LADDER = ROOT / "ops" / "conductor" / "tools" / "ladder.py"


def _load():
    spec = importlib.util.spec_from_file_location("ladder_under_test", LADDER)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve postponed annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Stub:
    """Just enough of Driver for derive_command: conf and make_input."""

    conf = {"SCOPE_CAP": "4096"}

    def __init__(self):
        self.body = None

    def make_input(self, name, body):
        self.body = body
        return Path("/dev/null")


class DerivedCommandNamesTheTree(unittest.TestCase):
    def setUp(self):
        self.ladder = _load()
        self.stub = _Stub()

    def derive(self, artifacts):
        return self.ladder.Driver.derive_command(self.stub, {"artifacts": artifacts})

    def test_relative_artifact_is_used_as_is(self):
        self.derive({"t": "ops/conductor/tests/test_x.py"})
        self.assertEqual(
            self.stub.body,
            "python3 -m unittest discover -s ops/conductor/tests -p test_x.py",
        )

    def test_absolute_snapshot_path_is_rewritten_relative_to_the_tree(self):
        snap = "/home/u/.local/state/agentscient/dispatch/20260911T025531Z-tests-grok-5a362c/snapshot"
        self.derive({"tests": f"{snap}/ops/conductor/tests/test_dispatch_wrapper_answers.py"})
        self.assertEqual(
            self.stub.body,
            "python3 -m unittest discover -s ops/conductor/tests -p test_dispatch_wrapper_answers.py",
        )
        self.assertNotIn("/snapshot", self.stub.body)

    def test_absolute_path_outside_any_snapshot_is_an_artifacts_stop(self):
        with self.assertRaises(self.ladder.Stopped) as caught:
            self.derive({"tests": "/tmp/elsewhere/ops/conductor/tests/test_x.py"})
        self.assertEqual(caught.exception.reason, "artifacts")
        self.assertIn("/tmp/elsewhere/ops/conductor/tests/test_x.py", caught.exception.detail or "")

    def test_parent_traversal_is_an_artifacts_stop(self):
        with self.assertRaises(self.ladder.Stopped) as caught:
            self.derive({"tests": "ops/conductor/tests/../../x/tests/test_x.py"})
        self.assertEqual(caught.exception.reason, "artifacts")

    def test_non_test_artifacts_are_still_ignored(self):
        self.derive({
            "reds": "/home/u/.local/state/agentscient/dispatch/x/out/reds.log",
            "t": "ops/conductor/tests/test_x.py",
        })
        self.assertEqual(
            self.stub.body,
            "python3 -m unittest discover -s ops/conductor/tests -p test_x.py",
        )


if __name__ == "__main__":
    unittest.main()
