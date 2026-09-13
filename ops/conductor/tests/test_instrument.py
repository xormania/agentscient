"""The shared instrument module: one wire, one identity, one clock, one
bounded call, and the gate that keeps the tools from growing copies.

Contract: `ops/conductor/instrument-conventions.md` §The shared
implementation. The module `ops/conductor/tools/instrument.py` is the
subject. Its functions are loaded from the file and exercised directly;
its CLI verbs are run as a subprocess under a scratch HOME.

Written by hand under grant 176 (owner, 2026-09-12: "agreed - hand grant
ok'd for #1, #2, #3, and #4"), one producer (Claude Fable 5.1), the
second producer absent by the owner's word (AGENTS.md §Ground rules).
Red: this file against a tree with no `instrument.py` fails
`test_the_module_file_is_present` and errors every load; green with the
same command once the module lands.

The consolidation gate at the end is the measured red of every later
migration: a tool joins MIGRATED before its private helpers go, and the
gate fails until they are gone. A tool is in exactly one of MIGRATED or
PENDING, so a tool nobody has placed is a failure naming it, never a
silent pass.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "ops" / "conductor" / "tools"
MODULE = TOOLS / "instrument.py"
AGENT = "Claude Fable 5.1 <noreply@anthropic.com>"

# Tools that import the shared module and carry none of its helpers.
MIGRATED: tuple[str, ...] = (
    "branches.py",
    "ci.py",
    "decisions.py",
    "deliverable.py",
    "findings.py",
    "hand.py",
    "land.py",
    "onboard.py",
    "watch.py",
)

# Tools still carrying private copies, named so their absence from
# MIGRATED is a declaration and not an oversight. Each one leaves this
# tuple in the commit that migrates it.
PENDING: tuple[str, ...] = (
    "co_doc.py",
    "control.py",
    "correction.py",
    "ladder.py",
    "lane_mcp.py",
    "lane_read.py",
    "lane_refs.py",
    "laneconf.py",
    "monitor.py",
    "probes.py",
    "skills.py",
    "watchdog.py",
)

# A migrated tool defines none of these at module level.
PRIVATE_NAMES = frozenset({
    "refuse", "Refused", "Refusal", "identity", "IDENTITY", "IDENTITY_RE",
    "AGENT_FORM", "now", "stamp", "parse_stamp", "lane_name", "conf_value",
    "state_root",
})


def load():
    spec = importlib.util.spec_from_file_location("instrument_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheModuleIsPresent(unittest.TestCase):
    def test_the_module_file_is_present(self):
        self.assertTrue(MODULE.is_file(), f"absent: {MODULE}")


class TheRefusalWire(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), f"absent: {MODULE}")
        self.m = load()

    def test_refuse_raises_a_refusal_whose_text_is_the_wire_line(self):
        with self.assertRaises(self.m.Refusal) as caught:
            self.m.refuse("store", "a store at X", "ABSENT", "seed it")
        self.assertEqual(
            str(caught.exception), "store: expected a store at X; found ABSENT; needed seed it"
        )
        self.assertEqual(caught.exception.kind, "store")
        self.assertEqual(caught.exception.line(), str(caught.exception))

    def test_multi_line_fields_collapse_to_one_line(self):
        with self.assertRaises(self.m.Refusal) as caught:
            self.m.refuse("git-error", "a clean\n  tree", "two\nlines\n", "  fix  it ")
        line = str(caught.exception)
        self.assertNotIn("\n", line)
        self.assertEqual(
            line, "git-error: expected a clean tree; found two lines; needed fix it"
        )

    def test_emit_prints_one_stderr_line_and_returns_the_rejection_code(self):
        err = io.StringIO()
        with self.assertRaises(self.m.Refusal) as caught:
            self.m.refuse("identity", "x", "y", "z")
        with redirect_stderr(err):
            code = self.m.emit(caught.exception)
        self.assertEqual(code, 2)
        self.assertEqual(code, self.m.EXIT_REJECTION)
        self.assertEqual(err.getvalue(), "identity: expected x; found y; needed z\n")

    def test_the_four_classes_are_the_wire_table(self):
        self.assertEqual(
            (self.m.EXIT_DONE, self.m.EXIT_FINDING, self.m.EXIT_REJECTION, self.m.EXIT_ABORT),
            (0, 1, 2, 3),
        )


class Identity(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), f"absent: {MODULE}")
        self.m = load()

    def refusal_for(self, value):
        env = {k: v for k, v in os.environ.items() if k != "WF_AGENT"}
        if value is not None:
            env["WF_AGENT"] = value
        with (
            mock.patch.dict(os.environ, env, clear=True),
            self.assertRaises(self.m.Refusal) as caught,
        ):
            self.m.identity()
        return caught.exception

    def test_unset_refuses_identity_and_says_unset(self):
        refusal = self.refusal_for(None)
        self.assertEqual(refusal.kind, "identity")
        self.assertIn("found unset", str(refusal))

    def test_a_bare_name_refuses_identity(self):
        self.assertEqual(self.refusal_for("JustAName").kind, "identity")

    def test_an_address_without_a_domain_refuses_identity(self):
        self.assertEqual(self.refusal_for("Name <noreply>").kind, "identity")

    def test_the_forms_in_use_pass_and_are_returned_whole(self):
        for value in (
            AGENT,
            "Grok 4.6 <noreply@x.ai>",
            "GPT-5 Codex <noreply@openai.com>",
            "Lane Owner <lane-owner@example.invalid>",
        ):
            with self.subTest(value=value), mock.patch.dict(os.environ, {"WF_AGENT": value}):
                self.assertEqual(self.m.identity(), value)

    def test_identity_parts_splits_name_and_address(self):
        with mock.patch.dict(os.environ, {"WF_AGENT": AGENT}):
            self.assertEqual(
                self.m.identity_parts(), ("Claude Fable 5.1", "noreply@anthropic.com")
            )


class TheClock(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), f"absent: {MODULE}")
        self.m = load()

    def test_now_is_aware_utc(self):
        value = self.m.now()
        self.assertIsNotNone(value.tzinfo)
        self.assertEqual(value.utcoffset().total_seconds(), 0)

    def test_stamp_ends_in_z_and_round_trips(self):
        moment = datetime(2026, 9, 12, 3, 4, 5, 678901, tzinfo=timezone.utc)
        text = self.m.stamp(moment)
        self.assertEqual(text, "2026-09-12T03:04:05.678901Z")
        self.assertEqual(self.m.parse_stamp(text), moment)

    def test_stamp_without_an_argument_is_now(self):
        before = self.m.now()
        parsed = self.m.parse_stamp(self.m.stamp())
        self.assertGreaterEqual(parsed, before.replace(microsecond=0))

    def test_a_naive_stamp_is_read_as_utc(self):
        parsed = self.m.parse_stamp("2026-09-12T03:04:05")
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_a_malformed_stamp_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.m.parse_stamp("yesterday")


class TheStateRootAndTheConf(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), f"absent: {MODULE}")
        self.m = load()
        self.tmp = Path(tempfile.mkdtemp(prefix="instrument-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def test_state_root_honors_xdg_state_home(self):
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.tmp / "xdg")}):
            self.assertEqual(self.m.state_root(), self.tmp / "xdg")

    def test_state_root_falls_back_to_home_local_state(self):
        env = {k: v for k, v in os.environ.items() if k != "XDG_STATE_HOME"}
        env["HOME"] = str(self.tmp / "home")
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(self.m.state_root(), self.tmp / "home" / ".local" / "state")

    def test_conf_reads_the_lane_conf_named_by_lane_conf(self):
        conf = self.tmp / "lane.conf"
        conf.write_text("LANE_NAME='testlane'\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"LANE_CONF": str(conf)}):
            self.assertEqual(self.m.conf("LANE_NAME"), "testlane")
            self.assertEqual(self.m.lane_name(), "testlane")

    def test_state_dir_is_the_lane_under_the_state_root(self):
        conf = self.tmp / "lane.conf"
        conf.write_text("LANE_NAME='testlane'\n", encoding="utf-8")
        env = {"LANE_CONF": str(conf), "XDG_STATE_HOME": str(self.tmp / "xdg")}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(self.m.state_dir(), self.tmp / "xdg" / "testlane")

    def test_a_staged_copy_names_its_conf_or_refuses_conf_file(self):
        """A copy of the module staged beside a copy of a tool has no
        tracked conf beside it. No name stands in: with nothing named
        it refuses conf-file, and a LANE_CONF names the conf it reads.
        The module itself carries no lane-name literal."""
        staged = self.tmp / "staged"
        staged.mkdir()
        for name in ("instrument.py", "laneconf.py"):
            (staged / name).write_bytes((TOOLS / name).read_bytes())
        spec = importlib.util.spec_from_file_location("instrument_staged", staged / "instrument.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        env = {k: v for k, v in os.environ.items() if k not in ("LANE_CONF", "LANE_NAME")}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            self.assertRaises(module.Refusal) as caught,
        ):
            module.lane_name()
        self.assertEqual(caught.exception.kind, "conf-file")
        conf = self.tmp / "named.conf"
        conf.write_text("LANE_NAME='namedlane'\n", encoding="utf-8")
        env["LANE_CONF"] = str(conf)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(module.lane_name(), "namedlane")
        source = MODULE.read_text(encoding="utf-8")
        self.assertNotIn("'agentscient'", source)
        self.assertNotIn('"agentscient"', source)

    def test_a_missing_key_refuses_conf_key(self):
        conf = self.tmp / "lane.conf"
        conf.write_text("LANE_NAME='testlane'\n", encoding="utf-8")
        with (
            mock.patch.dict(os.environ, {"LANE_CONF": str(conf)}),
            self.assertRaises(self.m.Refusal) as caught,
        ):
            self.m.conf("NO_SUCH_KEY")
        self.assertEqual(caught.exception.kind, "conf-key")
        self.assertIn("NO_SUCH_KEY", str(caught.exception))

    def test_a_missing_file_refuses_conf_file(self):
        with (
            mock.patch.dict(os.environ, {"LANE_CONF": str(self.tmp / "absent.conf")}),
            self.assertRaises(self.m.Refusal) as caught,
        ):
            self.m.conf("LANE_NAME")
        self.assertEqual(caught.exception.kind, "conf-file")


class TheBoundedCall(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), f"absent: {MODULE}")
        self.m = load()

    def test_run_returns_the_completed_process_without_a_shell(self):
        result = self.m.run([sys.executable, "-c", "print('ok')"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok\n")

    def test_a_timeout_refuses_with_the_executable_named(self):
        with self.assertRaises(self.m.Refusal) as caught:
            self.m.run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2)
        name = Path(sys.executable).name
        self.assertEqual(caught.exception.kind, f"{name}-error")
        self.assertIn("timeout", str(caught.exception))

    def test_a_missing_executable_refuses_with_the_executable_named(self):
        with self.assertRaises(self.m.Refusal) as caught:
            self.m.run(["no-such-binary-instrument-test", "x"])
        self.assertEqual(caught.exception.kind, "no-such-binary-instrument-test-error")

    def test_git_runs_git_in_the_given_directory(self):
        result = self.m.git("rev-parse", "--is-inside-work-tree", cwd=REPO)
        self.assertEqual(result.stdout.strip(), "true")


class TheCommandLine(unittest.TestCase):
    """The two verbs shell levers may call for the same wire."""

    def setUp(self):
        self.assertTrue(MODULE.is_file(), f"absent: {MODULE}")
        self.home = tempfile.mkdtemp(prefix="instrument-home-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.home, ignore_errors=True))

    def invoke(self, *argv, agent=None):
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.home,
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if agent is not None:
            env["WF_AGENT"] = agent
        return subprocess.run(
            [sys.executable, str(MODULE), *argv],
            cwd=self.home, env=env, capture_output=True, text=True, check=False, timeout=60,
        )

    def test_identity_without_wf_agent_refuses_on_the_wire(self):
        proc = self.invoke("identity")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        lines = proc.stderr.splitlines()
        self.assertEqual(len(lines), 1, proc.stderr)
        self.assertRegex(lines[0], r"^identity: expected .*; found unset; needed .*$")

    def test_identity_with_wf_agent_prints_it(self):
        proc = self.invoke("identity", agent=AGENT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, AGENT + "\n")
        self.assertEqual(proc.stderr, "")

    def test_refuse_emits_the_given_refusal(self):
        proc = self.invoke("refuse", "scope", "one job", "two jobs", "split them")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(
            proc.stderr, "scope: expected one job; found two jobs; needed split them\n"
        )

    def test_an_unknown_verb_refuses_arguments(self):
        proc = self.invoke("dance")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertRegex(proc.stderr, r"^arguments: expected .*; found dance; needed .*\n$")


class TheConsolidationGate(unittest.TestCase):
    """Every tool is placed; a migrated tool carries no private copy."""

    def tools(self) -> list[str]:
        return sorted(
            p.name for p in TOOLS.glob("*.py") if p.name != "instrument.py"
        )

    def test_every_tool_is_migrated_or_declared_pending(self):
        placed = set(MIGRATED) | set(PENDING)
        self.assertEqual(set(MIGRATED) & set(PENDING), set(), "a tool in both lists")
        self.assertEqual(
            sorted(placed), self.tools(),
            "each tool under ops/conductor/tools/ is named in exactly one list",
        )

    def test_a_migrated_tool_imports_the_module_and_defines_no_private_copy(self):
        for name in MIGRATED:
            with self.subTest(tool=name):
                tree = ast.parse((TOOLS / name).read_text(encoding="utf-8"))
                defined = {
                    node.name
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                } | {
                    target.id
                    for node in tree.body if isinstance(node, ast.Assign)
                    for target in node.targets if isinstance(target, ast.Name)
                }
                self.assertEqual(
                    sorted(defined & PRIVATE_NAMES), [],
                    f"{name} still defines a private copy",
                )
                imported = {
                    alias.name
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Import)
                    for alias in node.names
                } | {
                    node.module
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom)
                }
                self.assertIn("instrument", imported, f"{name} does not import instrument")


if __name__ == "__main__":
    unittest.main()
