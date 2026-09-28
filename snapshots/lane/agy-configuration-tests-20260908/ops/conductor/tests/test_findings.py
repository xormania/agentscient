"""Findings ledger reads LANE_NAME from the lane conf.

Contract (only): the unit 1 lane-conf edge — every state-root reader
reads LANE_NAME through the reader. findings.py is the subject and is
not read here. Tests plant a scratch conf through LANE_CONF and never
write the tracked file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "findings.py"
LIVE_STORE = Path.home() / ".local" / "state" / "agentscient" / "findings.db"
AGENT = "Findings Tester <findings-tester@example.invalid>"
REC = "20260901T000000Z-review-grok-aaaaaa"

ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)


def _live_snapshot() -> tuple[str, bytes | None]:
    if LIVE_STORE.is_file():
        return ("file", LIVE_STORE.read_bytes())
    if LIVE_STORE.exists():
        return ("other", None)
    return ("absent", None)


class _FindingsFixture(unittest.TestCase):
    def setUp(self):
        self._live_before = _live_snapshot()
        self._tmp = tempfile.TemporaryDirectory(prefix="findings-laneconf-")
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.scratch = root / "scratch"
        self.records = root / "repo" / ".dev" / "records" / "dispatches"
        self.home.mkdir()
        self.scratch.mkdir()
        self.records.mkdir(parents=True)
        self.staged = self.scratch / "findings.py"
        self._stage_tool_bytes()
        self.assertFalse(
            (self.home / ".local" / "state" / "agentscient" / "findings.db")
            .exists(),
            "plant: default store must start absent",
        )

    def tearDown(self):
        try:
            self.assertEqual(
                _live_snapshot(),
                self._live_before,
                f"live store mutated: {LIVE_STORE}",
            )
        finally:
            self._tmp.cleanup()

    def _stage_tool_bytes(self) -> None:
        if TOOL.is_file():
            data = TOOL.read_bytes()
            self.staged.write_bytes(data)
            landed = self.staged.read_bytes()
            self.assertEqual(landed, data, "copy-tool-bytes did not land intact")
            self.assertNotEqual(landed, ABSENT_STUB)
        else:
            self.staged.write_bytes(ABSENT_STUB)
            landed = self.staged.read_bytes()
            self.assertEqual(landed, ABSENT_STUB, "stub plant did not land intact")
        self.assertTrue(self.staged.is_file())

    def _plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")

    def env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "WF_AGENT": AGENT,
        }
        if extra:
            env.update(extra)
        return env

    def invoke(self, argv: list[str], *, extra_env: dict[str, str] | None = None):
        return subprocess.run(
            [sys.executable, str(self.staged), *argv],
            cwd=str(self.records.parents[2]),
            env=self.env(extra_env),
            capture_output=True,
            text=True,
            check=False,
        )


class LaneNameSelectsStore(_FindingsFixture):
    """LANE_NAME from the conf selects findings.db under HOME."""

    def test_lane_name_from_conf_selects_the_store(self):
        conf = self.scratch / "lane.conf"
        text = (
            "LANE_NAME='lanex'\n"
            "TRUNK_BRANCH='trunkx'\n"
            "RELEASE_BRANCH='relx'\n"
            "REPO_SLUG='org/projx'\n"
            "CHECK_NAMES='checkx'\n"
            "WF_AGENT_DEFAULT='Conf Agent <conf@example.invalid>'\n"
            "LANE_AUTHOR='Lane Owner <lane-owner@example.invalid>'\n"
            "MODEL_GROK='model-grok'\n"
            "MODEL_CODEX='model-codex'\n"
            "MODEL_CLAUDE_READ='model-claude-read'\n"
            "MODEL_CLAUDE_PLAN='model-claude-plan'\n"
            "EFFORT_GROK='high'\n"
            "EFFORT_CODEX='high'\n"
            "EFFORT_CLAUDE='high'\n"
            "WALL_DEFAULT='900'\n"
            "SCOPE_CAP='1024'\n"
        )
        self._plant_bytes(conf, text.encode("utf-8"))
        marker = "laneconf-findings-store-marker"
        envelope = {
            "id": REC,
            "lane": "dev",
            "stage": "review",
            "unit": "lane/lane-conf",
            "job": "adversarial-review",
            "role": "read",
            "status": "closed",
            "harness": {"name": "grok"},
            "model": {"ran": "grok-4.6"},
            "result": {
                "envelope": {
                    "status": "ok",
                    "verdict": "changes",
                    "findings": [
                        {
                            "severity": "p1",
                            "where": "ops/x.py",
                            "claim": marker,
                            "reproduce": None,
                        }
                    ],
                }
            },
        }
        rec_path = self.records / f"{REC}.json"
        payload = json.dumps(envelope, indent=2) + "\n"
        self._plant_bytes(rec_path, payload.encode("utf-8"))
        self.assertIn(marker, rec_path.read_text(encoding="utf-8"))
        lanex = self.home / ".local" / "state" / "lanex" / "findings.db"
        default = (
            self.home / ".local" / "state" / "agentscient" / "findings.db"
        )
        self.assertFalse(lanex.exists())
        self.assertFalse(default.exists())
        proc = self.invoke(["import"], extra_env={"LANE_CONF": str(conf)})
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertTrue(lanex.is_file(), f"store missing under lanex: {lanex}")
        self.assertFalse(
            default.exists(),
            f"store used the literal lane name: {default}",
        )


if __name__ == "__main__":
    unittest.main()
