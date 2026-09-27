"""Independent hostile-file boundary oracle: one job cannot silence later jobs.

Synthetic files only. No vendor or real dispatch-store access; subprocess
deadline is an outer guard so a FIFO regression cannot hang the suite.
The implementation producer neither authored nor approved this oracle.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "watchdog.py"
BAD = "20260904T100000Z-tests-grok-bad001"
GOOD = "20260904T200000Z-tests-grok-good01"


class HeldFileIsolation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="watchdog-files-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "dispatch"
        self.store.mkdir()
        self.bad = self.plant(BAD)
        good = self.plant(GOOD)
        (good / "raw.out").write_text("errors=2\n", encoding="utf-8")

    def plant(self, ident):
        job = self.store / ident
        job.mkdir()
        (job / "record.json").write_text(json.dumps({
            "id": ident, "job": "author-tests", "status": "closed",
            "harness": {"name": "grok"}, "caps": {"timeout": 600},
            "at": {"launched": "2026-09-04T10:00:00Z",
                   "closed": "2026-09-04T10:05:00Z"},
            "result": {"envelope": {"status": "ok", "findings": []},
                       "changed_paths": []},
        }), encoding="utf-8")
        (job / "state.json").write_text("{}", encoding="utf-8")
        return job

    def observe(self):
        env = dict(os.environ, HOME=str(self.root), XDG_STATE_HOME=str(self.root),
                   DISPATCH_JOBS=str(self.store), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, str(TOOL), "--store", str(self.store),
             "--once", "--no-forge", "--report-existing",
             "--heartbeat-every", "1"],
            cwd=self.root, env=env, capture_output=True, text=True,
            timeout=4, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deviation errors " + GOOD, result.stdout)
        self.assertIn("heartbeat:", result.stdout)
        self.assertIn("watchdog error:", result.stdout)
        return result.stdout

    def test_directory_is_unavailable_without_abandoning_later_jobs(self):
        (self.bad / "raw.out").mkdir()
        self.observe()

    def test_fifo_cannot_block_a_tick(self):
        os.mkfifo(self.bad / "raw.out")
        self.observe()

    def test_symlink_outside_job_is_not_read_as_held_output(self):
        outside = self.root / "outside.txt"
        outside.write_text("scope-cap: SYNTHETIC-PRIVATE-MARKER\n", encoding="utf-8")
        (self.bad / "raw.out").symlink_to(outside)
        output = self.observe()
        self.assertNotIn("deviation refused " + BAD, output)
        self.assertNotIn("SYNTHETIC-PRIVATE-MARKER", output)

    def test_record_fifo_cannot_block_startup_or_later_jobs(self):
        record = self.bad / "record.json"
        record.unlink()
        os.mkfifo(record)
        self.observe()


if __name__ == "__main__":
    unittest.main()

