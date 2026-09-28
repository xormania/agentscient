"""Round two of Codex's promotion review (PR #16, head 34aaaf7).

Written red before any fix. The cache finding has a subtlety the fix must
honour: chains are append-only, so "cache ahead of the export" is also what
legitimate un-flushed --no-commit work looks like — an exact-match-then-
rebuild would silently destroy recorded events. Ahead therefore REFUSES
while naming the two ways out; only behind or divergent rebuilds.
"""

import json
import sqlite3
import subprocess
import sys
import unittest

import support
from support import SandboxCase
from errors import EXIT_OK, EXIT_USAGE


def launch_status(sb, wo="WO-001"):
    proc = subprocess.run(
        [sys.executable, str(support.WF_DIR / "mcp_launch.py"),
         "--root", str(sb.root)],
        input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "wf_status",
                                     "arguments": {"wo": wo}}}) + "\n",
        capture_output=True, text=True, cwd=str(sb.dir))
    return json.loads(proc.stdout.strip().splitlines()[0])["result"]


class ACacheAheadOfTheExportRefusesInsteadOfLying(SandboxCase):
    """[P1 Codex] usable_cache was a lower bound: a tracked chain shorter
    than the cache (branch switch, truncation) still served the cache, so
    the server reported events absent from the current evidence.

    The fix must not swing to the other failure: rebuilding on "ahead"
    destroys legitimately recorded, not-yet-flushed events. Ahead refuses.
    """

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)

    def db_events(self):
        conn = sqlite3.connect(str(self.sb.db))
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM events WHERE wo_id='WO-001'"
            ).fetchone()[0]
        finally:
            conn.close()

    def test_a_shorter_tracked_chain_is_not_served_from_the_cache(self):
        # Codex's reproduction: the tracked file loses its tail while the
        # cache keeps it. The cache "leads", and serving it reports events
        # the current evidence does not contain.
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        lines = support.jsonl_lines(self.sb.chain_file("WO-001").read_bytes())
        support.plant_bytes(
            self.sb.chain_file("WO-001"),
            lambda raw: raw.strip().rsplit(b"\n", 1)[0] + b"\n",
            expect="shrink",
            recognisable=lambda raw: support.jsonl_lines(raw) == lines - 1,
        )
        result = launch_status(self.sb)
        self.assertTrue(result["isError"],
                        "a cache ahead of the evidence was served as truth")
        text = result["content"][0]["text"]
        self.assertIn("commit", text, "it must name the flush that reconciles")
        self.assertIn("--rebuild", text, "and the discard that reconciles")

    def test_refusing_ahead_destroys_nothing(self):
        self.sb.wf("advance", "WO-001", "--no-commit", check=EXIT_OK)
        before = self.db_events()
        exported = support.jsonl_lines(
            self.sb.chain_file("WO-001").read_bytes())
        self.assertGreater(before, exported,
                           "fixture: the cache must lead the export")
        launch_status(self.sb)
        self.assertEqual(self.db_events(), before,
                         "starting a reader destroyed pending events")

    def test_a_divergent_cache_is_rebuilt_to_the_export(self):
        # Same length, different content: the cached tail hash does not
        # match the tracked line. That is never pending work — rebuild.
        conn = sqlite3.connect(str(self.sb.db))
        try:
            conn.execute("UPDATE events SET hash = 'not-the-exported-hash'"
                         " WHERE wo_id='WO-001' AND seq=1")
            conn.commit()
        finally:
            conn.close()
        result = launch_status(self.sb)
        self.assertFalse(result["isError"],
                         result["content"][0]["text"][:200])
        conn = sqlite3.connect(str(self.sb.db))
        try:
            stored = conn.execute(
                "SELECT hash FROM events WHERE wo_id='WO-001' AND seq=1"
            ).fetchone()[0]
        finally:
            conn.close()
        line = json.loads(
            self.sb.chain_file("WO-001").read_bytes().splitlines()[0])
        self.assertEqual(stored, line["hash"],
                         "the divergent cache must be rebuilt to the export")


class NextDoesNotInventAnOutcome(SandboxCase):
    """[P1 Codex] At an outcome stage, next picked the alphabetically first
    verdict (for a review that is `aborted`), stamped the literal actor
    `<agent>`, omitted the mandatory --source, and called the argv complete.
    A complete-looking command that records an invented terminal decision is
    the most dangerous shape a suggestion can take."""

    def setUp(self):
        super().setUp()
        self.sb.seed_project()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV,
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.make_green()
        self.sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV,
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)  # -> review

    def next_body(self):
        return json.loads(
            self.sb.wf("--json", "next", "WO-001", check=EXIT_OK).stdout)

    def test_no_verdict_is_invented(self):
        body = self.next_body()
        for verdict in ("accepted", "finding", "denied"):
            self.assertNotIn(verdict, body["advances"],
                             "next invented a verdict on the caller's behalf")
        self.assertFalse(body["advances_complete"],
                         "an argv missing the decision is not complete")

    def test_the_choices_are_in_the_note(self):
        body = self.next_body()
        for verdict in ("accepted", "finding", "denied"):
            self.assertIn(verdict, body["note"])

    def test_no_placeholder_actor_is_emitted(self):
        body = self.next_body()
        self.assertNotIn("<agent>", body["advances"],
                         "a literal placeholder is not an argv")


class ALeadingDashTtlIsAUsageErrorOnEveryInterpreter(unittest.TestCase):
    """[P2 Codex] Python 3.14's argparse accepts `-5m` as a value, so the
    usage answer moved from argparse to parse_duration — which gave the
    refusal answer instead. The parser itself now gives 64's answer for any
    leading-dash duration, so the CLI behaves the same on 3.12 and 3.14."""

    def test_parse_duration_calls_a_leading_dash_a_usage_error(self):
        import coord
        from errors import Usage

        with self.assertRaises(Usage):
            coord.parse_duration("-5m")

    def test_the_cli_answer_is_64_either_way(self):
        # On 3.12 argparse refuses it; on 3.14 parse_duration does. Both 64.
        sb = support.Sandbox()
        sb.wf("init", check=EXIT_OK)
        sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
              check=EXIT_OK)
        self.assertEqual(
            sb.wf("claim", "WO-001", "--ttl", "-5m").returncode, EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
