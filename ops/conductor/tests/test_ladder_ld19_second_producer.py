"""LD-19 regression from a second producer.

Contract (only): the two LD-19 sentences in ops/conductor/ladder-lever.md.

  each test module (`test*.py`, unittest's default pattern) under a
  `tests/` directory becomes a `python3 -m unittest discover` invocation,
  joined in order with `&&`; another `.py` there is a support module,
  carried as an artifact and never run

  `resume LADDER_ID --retry STAGE --because TEXT` grants that stage one
  further attempt ... written on the stage row (`retry`: because, at, by,
  `from_attempt`) and is spent once

Subjects, loaded with importlib and registered in sys.modules before
executing: Driver.derive_command on a stub with conf SCOPE_CAP 4096 and
a make_input that records the body; Driver.retry_granted(name) on a stub
with retry, agent and row(name); resume_options(args) which returns
(rescope, retry) or raises Refused. The driver is not read here.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DRIVER_PATH = REPO / "ops" / "conductor" / "tools" / "ladder.py"
DRIVER_NAME = "ladder_ld19_second_producer_subject"

HELPER = "ops/conductor/tests/helper.py"
TEST_X = "ops/conductor/tests/test_x.py"
TEST_Y = "ops/conductor/tests/test_y.py"
OUTSIDE = "ops/conductor/tools/test_x.py"
DISCOVER_X = (
    "python3 -m unittest discover -s ops/conductor/tests -p test_x.py"
)
DISCOVER_Y = (
    "python3 -m unittest discover -s ops/conductor/tests -p test_y.py"
)
BECAUSE = "the derived command discovered a support module"
AGENT = "Lane Tester <lane-tester@example.invalid>"
RESUME = ["resume", "ladder-ld19"]


def load_ladder(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    sys.modules.pop(name, None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _DeriveStub:
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


class _RetryStub:
    """retry, agent and row(name), as the brief requires."""

    def __init__(self, retry, *, agent=AGENT, attempt=2):
        self.retry = retry
        self.agent = agent
        self._rows = {}
        self._attempt = attempt

    def row(self, name):
        if name not in self._rows:
            self._rows[name] = {"attempt": self._attempt}
        return self._rows[name]


class LadderLd19SecondProducer(unittest.TestCase):
    """Pins LD-19: test modules only; resume --retry spent once."""

    @classmethod
    def setUpClass(cls):
        if not DRIVER_PATH.is_file():
            raise AssertionError(f"missing driver {DRIVER_PATH}")
        cls.ladder = load_ladder(DRIVER_PATH, DRIVER_NAME)

    def derive(self, artifacts):
        stub = _DeriveStub()
        result = self.ladder.Driver.derive_command(
            stub, {"artifacts": artifacts}
        )
        return stub, result

    def command_for(self, artifacts):
        stub, _result = self.derive(artifacts)
        self.assertEqual(len(stub.bodies), 1, stub.bodies)
        return stub.bodies[0]

    def stop_for(self, artifacts):
        with self.assertRaises(self.ladder.Stopped) as caught:
            self.derive(artifacts)
        return caught.exception

    def retry_stub(self, retry):
        return _RetryStub(retry)

    def parsed_retry(self, stage="code", because=BECAUSE):
        _rescope, retry = self.ladder.resume_options(
            [*RESUME, "--retry", stage, "--because", because]
        )
        return retry

    def test_helper_beside_a_test_module_yields_one_discover_for_the_test_module(self):
        command = self.command_for({"helper": HELPER, "tests": TEST_X})
        self.assertEqual(command, DISCOVER_X)
        self.assertNotIn("helper.py", command)
        self.assertNotIn(" && ", command)

    def test_a_helper_alone_is_an_artifacts_stop(self):
        stopped = self.stop_for({"helper": HELPER})
        self.assertEqual(stopped.reason, "artifacts")

    def test_a_test_star_file_outside_any_tests_directory_is_ignored(self):
        command = self.command_for({"outside": OUTSIDE, "tests": TEST_Y})
        self.assertEqual(command, DISCOVER_Y)
        self.assertNotIn("test_x.py", command)
        self.assertNotIn("conductor/tools", command)
        stopped = self.stop_for({"outside": OUTSIDE})
        self.assertEqual(stopped.reason, "artifacts")

    def test_retry_granted_is_false_when_there_is_no_retry(self):
        stub = self.retry_stub(None)
        self.assertFalse(self.ladder.Driver.retry_granted(stub, "code"))
        self.assertNotIn("retry", stub.row("code"))

    def test_retry_granted_is_false_for_another_stage(self):
        stub = self.retry_stub(self.parsed_retry("code"))
        self.assertFalse(self.ladder.Driver.retry_granted(stub, "tests-fix"))
        self.assertNotIn("retry", stub.row("tests-fix"))
        self.assertNotIn("retry", stub.row("code"))

    def test_retry_granted_is_true_once_for_the_named_stage_and_writes_the_grant(self):
        stub = self.retry_stub(self.parsed_retry("code", BECAUSE))
        self.assertTrue(self.ladder.Driver.retry_granted(stub, "code"))
        grant = stub.row("code").get("retry")
        self.assertIsInstance(grant, dict, grant)
        self.assertEqual(grant.get("because"), BECAUSE)
        self.assertTrue(grant.get("at"), grant)
        self.assertEqual(grant.get("by"), AGENT)
        self.assertEqual(grant.get("from_attempt"), stub.row("code")["attempt"])

    def test_retry_granted_is_false_on_the_second_call(self):
        stub = self.retry_stub(self.parsed_retry("code"))
        self.assertTrue(self.ladder.Driver.retry_granted(stub, "code"))
        self.assertFalse(self.ladder.Driver.retry_granted(stub, "code"))
        self.assertEqual(stub.row("code")["retry"]["because"], BECAUSE)

    def test_resume_options_plain(self):
        self.assertEqual(
            self.ladder.resume_options(list(RESUME)),
            (False, None),
        )

    def test_resume_options_rescope(self):
        self.assertEqual(
            self.ladder.resume_options([*RESUME, "--rescope"]),
            (True, None),
        )

    def test_resume_options_retry_with_because(self):
        self.assertEqual(
            self.ladder.resume_options(
                [*RESUME, "--retry", "code", "--because", BECAUSE]
            ),
            (False, ("code", BECAUSE)),
        )

    def test_resume_options_refuses_a_retry_without_a_reason(self):
        with self.assertRaises(self.ladder.Refused):
            self.ladder.resume_options([*RESUME, "--retry", "code"])

    def test_resume_options_refuses_a_reason_without_a_stage(self):
        with self.assertRaises(self.ladder.Refused):
            self.ladder.resume_options([*RESUME, "--because", BECAUSE])

    def test_resume_options_refuses_an_unknown_stage(self):
        with self.assertRaises(self.ladder.Refused):
            self.ladder.resume_options(
                [*RESUME, "--retry", "not-a-stage", "--because", BECAUSE]
            )

    def test_resume_options_refuses_an_empty_reason(self):
        with self.assertRaises(self.ladder.Refused):
            self.ladder.resume_options(
                [*RESUME, "--retry", "code", "--because", ""]
            )

    def test_resume_options_refuses_an_unknown_flag(self):
        with self.assertRaises(self.ladder.Refused):
            self.ladder.resume_options([*RESUME, "--nope"])


if __name__ == "__main__":
    unittest.main()
