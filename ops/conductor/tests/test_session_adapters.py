"""Managed sessions slice 1: framing parser and the claude adapter.

Contract: `ops/conductor/sessions-lever.md` §The adapter boundary.
`ops/conductor/tools/session_adapters/framing.py` is the real parser;
`session_adapters/claude.py` is the one live adapter. Loaded from their
files and exercised in-process. A missing file is red on the presence
assertion of each test, so the row fails for its own claim rather than
an import error.

The one command that reads this file is
`python3 -m unittest discover -s ops/conductor/tests -p test_session_adapters.py`.
"""

from __future__ import annotations

import importlib.util
import inspect
import subprocess
import sys
import unittest
from pathlib import Path

from ops.testkit import World

REPO = Path(__file__).resolve().parents[3]
ADAPTERS = REPO / "ops" / "conductor" / "tools" / "session_adapters"
FRAMING = ADAPTERS / "framing.py"
CLAUDE = ADAPTERS / "claude.py"
ORIGIN = "sessions-lever.md"
METHODS = ("argv", "observe_identity", "probe", "stop", "diagnostics")
LAUNCH_ID = "11111111-1111-4111-8111-111111111111"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reading_of(exc: BaseException) -> str:
    return str(getattr(exc, "reading", None) or exc)


class TheFramingParser(unittest.TestCase):
    """Each framing fault through the real parser, a row with origin."""

    def parser(self):
        self.assertTrue(FRAMING.is_file(), f"RED: framing is absent: {FRAMING}")
        module = load_module(FRAMING, "session_adapters_framing")
        self.assertTrue(hasattr(module, "Parser"), "framing.Parser is the real parser")
        self.assertTrue(hasattr(module, "Refused"), "framing.Refused names the reading")
        return module.Parser(), module

    def refuse_line(self, parser, module, line: str) -> str:
        with self.assertRaises(module.Refused) as caught:
            parser.feed(line)
        text = reading_of(caught.exception)
        self.assertIn(line, text)
        return text

    def test_a_non_json_line_is_refused_naming_the_line(self):
        with self.subTest(id="framing-non-json", origin=ORIGIN):
            parser, module = self.parser()
            line = "this is not json"
            self.refuse_line(parser, module, line)

    def test_a_response_whose_id_matches_no_request_is_refused_naming_the_line(self):
        with self.subTest(id="framing-unknown-response", origin=ORIGIN):
            parser, module = self.parser()
            line = '{"id":"no-such-request","result":{}}'
            self.refuse_line(parser, module, line)

    def test_two_requests_with_one_id_are_refused_naming_the_line(self):
        with self.subTest(id="framing-duplicate-id", origin=ORIGIN):
            parser, module = self.parser()
            first = '{"id":"1","method":"ping"}'
            parser.feed(first)
            line = '{"id":"1","method":"ping-again"}'
            self.refuse_line(parser, module, line)

    def test_a_result_missing_its_id_is_refused_naming_the_line(self):
        with self.subTest(id="framing-result-missing-id", origin=ORIGIN):
            parser, module = self.parser()
            line = '{"result":{"ok":true}}'
            self.refuse_line(parser, module, line)


class TheClaudeAdapter(unittest.TestCase):
    """The five methods, argv carrying the launch id, probe channel unmeasured."""

    def setUp(self):
        self.world = World(prefix="session-adapter-")
        self.addCleanup(self.world.close)

    def adapter(self):
        self.assertTrue(CLAUDE.is_file(), f"RED: claude adapter is absent: {CLAUDE}")
        module = load_module(CLAUDE, "session_adapters_claude")
        self.assertTrue(hasattr(module, "Adapter"), "claude.Adapter is the live adapter")
        return module.Adapter()

    def test_the_adapter_exposes_the_five_methods_and_no_others_the_supervisor_calls(self):
        with self.subTest(id="adapter-five-methods", origin=ORIGIN):
            adapter = self.adapter()
            for name in METHODS:
                self.assertTrue(
                    callable(getattr(adapter, name, None)),
                    f"adapter.{name} is missing",
                )
            public = [
                name for name, _ in inspect.getmembers(adapter, predicate=callable)
                if not name.startswith("_")
            ]
            extra = sorted(set(public) - set(METHODS) - {"Adapter"})
            for name in extra:
                self.assertNotIn(
                    name,
                    METHODS,
                    f"supervisor-called method set drifted: {public}",
                )

    def test_argv_carries_the_launch_id_as_claude_session_id(self):
        with self.subTest(id="claude-argv-launch-id", origin=ORIGIN):
            adapter = self.adapter()
            member = {"name": "co", "harness": "claude"}
            binding = {"executable": str(self.world.bin / "claude")}
            argv = adapter.argv(member, binding, LAUNCH_ID)
            joined = argv if isinstance(argv, str) else " ".join(str(part) for part in argv)
            self.assertIn("--session-id", joined)
            self.assertIn(LAUNCH_ID, joined)
            self.assertNotIn("operator text", joined)

    def test_probe_reads_unmeasured_slice_2_for_the_channel(self):
        with self.subTest(id="claude-probe-channel", origin=ORIGIN):
            adapter = self.adapter()
            exe = self.world.tools.plant("claude", stdout="Claude 9.9.9\n")
            reading = adapter.probe(str(exe))
            self.assertIsInstance(reading, dict)
            self.assertIn("channel", reading)
            self.assertEqual(reading["channel"], "unmeasured slice 2")

    def test_stop_does_not_signal_a_pid_whose_start_ticks_do_not_match(self):
        with self.subTest(id="adapter-stop-stale-pid", origin=ORIGIN):
            adapter = self.adapter()
            child = self.world.own(
                subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(3600)"],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
            handle = {"pid": child.pid, "start": 0}
            outcome = adapter.stop(handle, True)
            self.assertIsNone(child.poll(), "the world-owned pid was signalled")
            self.assertTrue(str(outcome).startswith("unresolved"), outcome)
            self.assertIn("stale pid", str(outcome))

    def test_diagnostics_returns_the_evidence_paths_it_retained(self):
        with self.subTest(id="adapter-diagnostics", origin=ORIGIN):
            adapter = self.adapter()
            member_dir = self.world.root / "member"
            member_dir.mkdir()
            (member_dir / "pane.log").write_text("pane\n", encoding="utf-8")
            paths = adapter.diagnostics(member_dir)
            self.assertIsInstance(paths, list)


if __name__ == "__main__":
    unittest.main()
