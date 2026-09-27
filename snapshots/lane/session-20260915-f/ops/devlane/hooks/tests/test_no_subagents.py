"""no-subagents.py: refuse Agent/Workflow/Task on the wire; let everything else through.

The hook is run as a real subprocess, the way Claude Code runs it: JSON
payload on stdin, decision by exit code, reason on stderr.

LD-22 (2026-09-11): since PR 135 a refusal logs a miss into the skills
registry under HOME, so this suite ran with the operator's HOME and wrote
three fixture rows into the live registry per run. The hook now runs
under a temporary HOME, and the live registry is proved untouched.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from ops.testkit import World, run

HOOK = Path(__file__).resolve().parents[1] / "claude" / "no-subagents.py"
LIVE_REGISTRY = Path.home() / ".local" / "state" / "agentscient" / "skills.db"
TIMEOUT = 30


class _Isolated(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.addCleanup(self.world.close)
        self.env = self.world.env()
        self.hook = self.world.stage(HOOK, siblings=("miss.py",))
        self._live = (
            (LIVE_REGISTRY.stat().st_size, LIVE_REGISTRY.stat().st_mtime_ns)
            if LIVE_REGISTRY.is_file() else None
        )

    def tearDown(self):
        after = (
            (LIVE_REGISTRY.stat().st_size, LIVE_REGISTRY.stat().st_mtime_ns)
            if LIVE_REGISTRY.is_file() else None
        )
        self.assertEqual(after, self._live, "the live skills registry must stay untouched")

    def hook_run(self, stdin: str):
        return run(
            [sys.executable, str(self.hook)],
            cwd=self.world.cwd,
            env=self.env,
            stdin=stdin,
            timeout=TIMEOUT,
        )


class Refuses(_Isolated):
    def test_each_delegating_tool_is_refused_with_the_path_named(self):
        for tool in ("Agent", "Workflow", "Task"):
            with self.subTest(tool=tool):
                r = self.hook_run(json.dumps({"tool_name": tool, "tool_input": {}}))
                self.assertEqual(r.exit, 2)
                self.assertEqual(r.stdout, "")
                self.assertIn("ops/devlane/dispatch/launch.py", r.stderr)
                self.assertIn("ops/bin/dispatch.sh", r.stderr)
                self.assertEqual(r.stderr.count("\n"), 1, "one line on stderr")


class LetsThrough(_Isolated):
    def test_other_tools_are_silent_and_allowed(self):
        for tool in ("Bash", "Read", "Edit", "Skill", "SendMessage"):
            with self.subTest(tool=tool):
                r = self.hook_run(json.dumps({"tool_name": tool, "tool_input": {}}))
                self.assertEqual((r.exit, r.stdout, r.stderr), (0, "", ""))

    def test_junk_and_non_object_payloads_are_allowed(self):
        for stdin in ("", "not json", "[1,2]", "null", '"Agent"'):
            with self.subTest(stdin=stdin):
                r = self.hook_run(stdin)
                self.assertEqual((r.exit, r.stdout, r.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
