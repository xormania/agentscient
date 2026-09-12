"""no-subagents.py: refuse Agent/Workflow/Task on the wire; let everything else through.

The hook is run as a real subprocess, the way Claude Code runs it: JSON
payload on stdin, decision by exit code, reason on stderr.

LD-22 (2026-09-11): since PR 135 a refusal logs a miss into the skills
registry under HOME, so this suite ran with the operator's HOME and wrote
three fixture rows into the live registry per run. The hook now runs
under a temporary HOME, and the live registry is proved untouched.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

HOOK = Path(__file__).resolve().parents[1] / "claude" / "no-subagents.py"
LIVE_REGISTRY = Path.home() / ".local" / "state" / "agentscient" / "skills.db"


class _Isolated(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="no-subagents-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.env = support.isolated_env(self.home)
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

    def run(self, *args, **kwargs):  # unittest's own run; the hook runner is `hook`
        return super().run(*args, **kwargs)

    def hook(self, stdin: str):
        return subprocess.run(
            [sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True,
            timeout=30, env=self.env,
        )


class Refuses(_Isolated):
    def test_each_delegating_tool_is_refused_with_the_path_named(self):
        for tool in ("Agent", "Workflow", "Task"):
            with self.subTest(tool=tool):
                r = self.hook(json.dumps({"tool_name": tool, "tool_input": {}}))
                self.assertEqual(r.returncode, 2)
                self.assertEqual(r.stdout, "")
                self.assertIn("ops/devlane/dispatch/launch.py", r.stderr)
                self.assertIn("ops/bin/dispatch.sh", r.stderr)
                self.assertEqual(r.stderr.count("\n"), 1, "one line on stderr")


class LetsThrough(_Isolated):
    def test_other_tools_are_silent_and_allowed(self):
        for tool in ("Bash", "Read", "Edit", "Skill", "SendMessage"):
            with self.subTest(tool=tool):
                r = self.hook(json.dumps({"tool_name": tool, "tool_input": {}}))
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_junk_and_non_object_payloads_are_allowed(self):
        for stdin in ("", "not json", "[1,2]", "null", '"Agent"'):
            with self.subTest(stdin=stdin):
                r = self.hook(stdin)
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
