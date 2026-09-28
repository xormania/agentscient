"""no-subagents.py: refuse Agent/Workflow/Task on the wire; let everything else through.

The hook is run as a real subprocess, the way Claude Code runs it: JSON
payload on stdin, decision by exit code, reason on stderr.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "claude" / "no-subagents.py"


def run(stdin: str):
    return subprocess.run(
        [sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, timeout=30
    )


class Refuses(unittest.TestCase):
    def test_each_delegating_tool_is_refused_with_the_path_named(self):
        for tool in ("Agent", "Workflow", "Task"):
            with self.subTest(tool=tool):
                r = run(json.dumps({"tool_name": tool, "tool_input": {}}))
                self.assertEqual(r.returncode, 2)
                self.assertEqual(r.stdout, "")
                self.assertIn("ops/devlane/dispatch/launch.py", r.stderr)
                self.assertIn("ops/bin/dispatch.sh", r.stderr)
                self.assertEqual(r.stderr.count("\n"), 1, "one line on stderr")


class LetsThrough(unittest.TestCase):
    def test_other_tools_are_silent_and_allowed(self):
        for tool in ("Bash", "Read", "Edit", "Skill", "SendMessage"):
            with self.subTest(tool=tool):
                r = run(json.dumps({"tool_name": tool, "tool_input": {}}))
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_junk_and_non_object_payloads_are_allowed(self):
        for stdin in ("", "not json", "[1,2]", "null", '"Agent"'):
            with self.subTest(stdin=stdin):
                r = run(stdin)
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
