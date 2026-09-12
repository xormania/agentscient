"""Every hook refusal logs a miss against the skill it names.

The registry (ops/conductor/tools/skills.py) records uses, failures and
misses per skill; until now no miss was ever logged, so the report said
zero for every skill and meant nothing (measured 2026-09-11: 13 of 17
skills with zero events). A refusal is the one moment the lane knows a
skill was not followed: the matrix rows, the command-shape hook and the
sub-agent hook each log one miss, best effort, without changing the
refusal. The `deliverable` row names the `deliverable` skill; every
other class names `refused`.

Hermetic: a temporary HOME holds the registry the hook writes into, a
fake repository holds the lane conf and a copy of the real skills tool,
and the real hooks run as subprocesses. The live registry is never
touched; the store path is found by glob, never spelled.

Written by hand by the conductor with the code it tests (owner,
2026-09-11: "hand grant given - add the logging into hooks to a new
PR"); the second producer is absent and this docstring says so.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

MATRIX = support.CLAUDE_DIR / "matrix.py"
UNSAFE = support.CLAUDE_DIR / "unsafe-command.py"
NO_SUBAGENTS = support.CLAUDE_DIR / "no-subagents.py"
REPO = Path(__file__).resolve().parents[4]
SKILLS_TOOL = REPO / "ops" / "conductor" / "tools" / "skills.py"
LANE_NAME = "testlane"
AGENT = "Miss Tester <miss@example.invalid>"


class _MissFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="miss-log-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.repo = self.tmp / "repo"
        self.home.mkdir()
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "ops").mkdir()
        (self.repo / "ops" / "lane.conf").write_text(
            f"LANE_NAME='{LANE_NAME}'\nTRUNK_BRANCH='dev'\n", encoding="utf-8"
        )
        self.lever = self.repo / "ops" / "conductor" / "tools" / "skills.py"
        self.lever.parent.mkdir(parents=True)
        self.lever.write_bytes(SKILLS_TOOL.read_bytes())
        self.env = support.isolated_env(self.home, extra={"WF_AGENT": AGENT})
        for name in ("refused", "deliverable"):
            self.skills("add", name, f"planted {name}")
        self.assertEqual(self.events(), [], "plant: the registry starts with no events")

    def skills(self, *argv):
        proc = subprocess.run(
            [sys.executable, str(self.lever), *argv],
            cwd=str(self.repo), env=self.env, capture_output=True, text=True,
            check=False, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc

    def store(self):
        found = list(self.home.glob(".local/state/*/skills.db"))
        self.assertEqual(len(found), 1, f"one planted registry, found {found}")
        return found[0]

    def events(self):
        con = sqlite3.connect(self.store())
        try:
            return con.execute(
                "SELECT skill, event, agent, detail FROM skill_events ORDER BY id"
            ).fetchall()
        finally:
            con.close()

    def run_hook(self, hook, payload, env=None):
        return subprocess.run(
            [sys.executable, str(hook)],
            cwd=str(self.repo), env=env or self.env, input=json.dumps(payload),
            capture_output=True, text=True, check=False, timeout=30,
        )

    def bash(self, command):
        return {"tool_name": "Bash", "cwd": str(self.repo),
                "tool_input": {"command": command}}

    def assert_denied(self, proc, klass):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        reason = data["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertEqual(data["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(f"[matrix:{klass}]", reason)
        return reason


class MatrixRefusalsLogAMiss(_MissFixture):
    def test_hand_write_on_the_write_tool_logs_a_miss_against_refused(self):
        proc = self.run_hook(MATRIX, {
            "tool_name": "Write", "cwd": str(self.repo),
            "tool_input": {"file_path": str(self.repo / "ops" / "x.py"), "content": "x"},
        })
        self.assert_denied(proc, "hand-write")
        rows = self.events()
        self.assertEqual(len(rows), 1, rows)
        skill, event, agent, detail = rows[0]
        self.assertEqual((skill, event, agent), ("refused", "miss", AGENT))
        self.assertTrue(detail.startswith("hand-write: "), detail)
        self.assertIn("ops/x.py", detail)

    def test_a_deliverable_refusal_logs_against_the_deliverable_skill(self):
        lock = self.home / ".local" / "state" / LANE_NAME / "deliverable.json"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({
            "branches": ["lane/one"], "why": "w", "by": "Owner <o@x>",
            "at": "2026-09-11T07:00:00Z"}) + "\n", encoding="utf-8")
        proc = self.run_hook(MATRIX, self.bash("git checkout -b lane/other"))
        self.assert_denied(proc, "deliverable")
        rows = self.events()
        self.assertEqual([(r[0], r[1]) for r in rows], [("deliverable", "miss")], rows)
        self.assertTrue(rows[0][3].startswith("deliverable: "), rows[0][3])

    def test_an_allowed_command_logs_nothing(self):
        proc = self.run_hook(MATRIX, self.bash("ls"))
        self.assertEqual((proc.returncode, proc.stdout.strip()), (0, ""), proc.stderr)
        self.assertEqual(self.events(), [])

    def test_without_an_identity_the_hook_signs_as_itself(self):
        env = dict(self.env)
        env.pop("WF_AGENT")
        proc = self.run_hook(MATRIX, self.bash("python3 -m unittest ops/tests/test_x.py"), env=env)
        self.assert_denied(proc, "test-form")
        rows = self.events()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0][0], "refused")
        self.assertIn(LANE_NAME, rows[0][2], "the hook's own identity names the lane")
        self.assertNotIn("<>", rows[0][2])

    def test_the_refusal_stands_when_the_registry_cannot_be_written(self):
        self.lever.unlink()
        proc = self.run_hook(MATRIX, self.bash("python3 -m unittest ops/tests/test_x.py"))
        self.assert_denied(proc, "test-form")
        self.assertEqual(self.events(), [])

    def test_a_skill_missing_from_the_registry_does_not_break_the_refusal(self):
        con = sqlite3.connect(self.store())
        con.execute("DELETE FROM skills")
        con.commit()
        con.close()
        proc = self.run_hook(MATRIX, self.bash("python3 -m unittest ops/tests/test_x.py"))
        self.assert_denied(proc, "test-form")
        self.assertEqual(self.events(), [])


class TheOtherHooksLogToo(_MissFixture):
    def test_a_clipped_sweep_logs_a_miss_against_refused(self):
        proc = self.run_hook(UNSAFE, self.bash("grep -E 'alpha|beta|gamma' ops/x.py | head -5"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        reason = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("[clipped-sweep]", reason)
        rows = self.events()
        self.assertEqual([(r[0], r[1]) for r in rows], [("refused", "miss")], rows)
        self.assertTrue(rows[0][3].startswith("clipped-sweep: "), rows[0][3])

    def test_a_refused_subagent_logs_a_miss_against_refused(self):
        proc = self.run_hook(NO_SUBAGENTS, {"tool_name": "Agent", "cwd": str(self.repo),
                                            "tool_input": {"prompt": "x"}})
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("in-session sub-agents are off", proc.stderr)
        rows = self.events()
        self.assertEqual([(r[0], r[1]) for r in rows], [("refused", "miss")], rows)
        self.assertTrue(rows[0][3].startswith("no-subagents: "), rows[0][3])

    def test_an_allowed_tool_logs_nothing_in_either_hook(self):
        self.run_hook(UNSAFE, self.bash("grep -c alpha ops/x.py"))
        self.run_hook(NO_SUBAGENTS, {"tool_name": "Read", "cwd": str(self.repo),
                                     "tool_input": {"file_path": "x"}})
        self.assertEqual(self.events(), [])


if __name__ == "__main__":
    unittest.main()
