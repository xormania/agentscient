"""Findings from Codex's review of the dev→main promotion PR (#16).

Written red before any fix, per ops/process/tdd.md. The fourth finding
(the promotion must be a merge commit, not a squash) is about repository
mechanics, not code, and is answered in the PR thread with measurements.
"""

import json
import shutil
import subprocess
import sys
import unittest

import support
from support import SandboxCase
from errors import EXIT_OK, EXIT_REFUSED


class AStaleCacheIsCaughtUpNotServed(SandboxCase):
    """[P1 Codex] A pull that advanced an existing chain left the cache
    stale forever: the file count still matched, so usable_cache() said yes
    and the launcher served the old world with isError: false.
    """

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "stale",
                   check=EXIT_OK)
        self.sb.wf("claim", "WO-001", "--ttl", "2h", check=EXIT_OK)
        # The world before the "pull": cache and export agree.
        self.stale = self.sb.root / "wf.db.testcopy"
        shutil.copy(self.sb.db, self.stale)
        # The "pull": the chain advances (spec -> red) and the export moves.
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        # The stale cache comes back — same number of chain files, fewer
        # events, and it is the copy that holds the live claim.
        shutil.copy(self.stale, self.sb.db)
        self.stale.unlink()

    def launch_status(self):
        proc = subprocess.run(
            [sys.executable, str(support.WF_DIR / "mcp_launch.py"),
             "--root", str(self.sb.root)],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": "wf_status",
                                         "arguments": {"wo": "WO-001"}}}) + "\n",
            capture_output=True, text=True, cwd=str(self.sb.dir))
        reply = json.loads(proc.stdout.strip().splitlines()[0])
        self.assertFalse(reply["result"]["isError"],
                         reply["result"]["content"][0]["text"][:200])
        return json.loads(reply["result"]["content"][0]["text"])

    def test_the_launcher_serves_the_export_not_the_stale_cache(self):
        body = self.launch_status()
        self.assertEqual(body["stage"], "red",
                         "the launcher served pre-pull evidence as current")

    def test_catching_up_does_not_destroy_the_live_claim(self):
        body = self.launch_status()
        self.assertIsNotNone(body["claim"],
                             "freshening the cache freed claimed work")
        self.assertEqual(body["claim"]["agent"], support.Sandbox.AGENT)


class MarkerContentRequiresProvenance(SandboxCase):
    """[P1 Codex] `wf marker` stored a caller-authored id and note with an
    empty sources list — findings entered the tracked chain with no origin,
    while `open` and `outcome` refuse exactly that."""

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)

    def test_a_marker_without_a_source_is_refused(self):
        proc = self.sb.wf("marker", "WO-001", "open", "F1",
                          "--note", "authored text", raw=True)
        self.assertEqual(proc.returncode, EXIT_REFUSED, proc.stderr)
        self.assertIn("source", (proc.stderr + proc.stdout).lower())

    def test_a_marker_with_a_source_is_recorded(self):
        self.sb.wf("marker", "WO-001", "open", "F1", "--note", "found it",
                   "--source", "original", raw=True, check=EXIT_OK)
        body = json.loads(
            self.sb.wf("--json", "status", "WO-001", check=EXIT_OK).stdout)
        self.assertIn("F1", body["open_markers"])


class DiagnosticsFailWhenTheProducerDies(unittest.TestCase):
    """[P2 Codex] A producer that failed before emitting recognizable
    diagnostic JSON scored failing=0, and the wrapper exited 0 — a broken
    `cargo check` would have recorded a satisfying diagnostics receipt."""

    CHECK = support.WF_DIR / "checks" / "diagnostics.py"

    def run_check(self, *producer):
        return subprocess.run(
            [sys.executable, str(self.CHECK), "--", *producer],
            capture_output=True, text=True)

    def test_a_producer_that_dies_without_json_fails_the_check(self):
        proc = self.run_check("sh", "-c", "echo manifest broken >&2; exit 3")
        self.assertNotEqual(proc.returncode, 0,
                            "a dead producer was reported as clean")

    def test_a_clean_producer_still_passes(self):
        proc = self.run_check("sh", "-c", "true")
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
