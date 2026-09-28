"""The read surface, priced in tokens (all three harnesses pay it).

Measured before any change, on a walked work order: `wf --json log` emitted
5094 bytes for a six-event chain — ~850 bytes per event, full payloads,
unbounded — while status (1265), next (876) and tools/list (1506) were
already lean. Every harness pays the log price per call, via CLI and MCP
alike, and it grows linearly with the chain forever.
"""

import json
import unittest

import support
from support import SandboxCase
from errors import EXIT_OK

#: What a compact event line may carry. Everything else is payload, and
#: payload is what --full is for.
COMPACT_KEYS = {"seq", "type", "time", "agent", "class"}


class LogIsCompactByDefault(SandboxCase):
    def setUp(self):
        super().setUp()
        self.sb.seed_project()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "diet",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV,
                   check=EXIT_OK)

    def log(self, *args):
        return json.loads(
            self.sb.wf("--json", "log", "WO-001", *args, check=EXIT_OK).stdout)

    def test_default_events_carry_no_payload(self):
        for event in self.log()["events"]:
            extra = set(event) - COMPACT_KEYS
            self.assertEqual(extra, set(),
                             f"payload leaked into the compact line: {extra}")

    def test_full_restores_the_whole_event(self):
        events = self.log("--full")["events"]
        self.assertTrue(any(("hash" in e and "payload" not in e) or "prev" in e
                            or len(set(e) - COMPACT_KEYS) > 0 for e in events),
                        "--full must carry more than the compact keys")
        # And the receipt's substance is reachable there.
        red = [e for e in events if e["type"] == "receipt.red"]
        self.assertTrue(red)
        self.assertIn("test_manifest_sha256", red[0])

    def test_the_diet_is_measurable(self):
        compact = len(json.dumps(self.log()["events"]))
        full = len(json.dumps(self.log("--full")["events"]))
        self.assertLess(compact * 2, full,
                        f"compact ({compact}) must be well under half of "
                        f"full ({full}) — otherwise the diet is cosmetic")

    def test_the_default_is_bounded_and_announces_itself(self):
        body = self.log()
        self.assertLessEqual(len(body["events"]), 50)
        self.assertIn("considered", body,
                      "a bounded answer must say what it considered")
        self.assertEqual(body["considered"],
                         len(self.log("--all", "--full")["events"]))

    def test_filters_and_tail_still_work_on_the_compact_shape(self):
        body = self.log("-n", "2")
        self.assertEqual(len(body["events"]), 2)
        self.assertEqual(body["considered"], self.log()["considered"])


class TheEntryPointerStaysTiny(unittest.TestCase):
    """CLAUDE.md is auto-loaded into every Claude session's context, so it
    exists only to point at the real documents — and a size cap keeps it
    from quietly becoming a second AGENTS.md that drifts from the first."""

    PATH = support.WF_DIR.parents[2] / "CLAUDE.md"

    def test_it_exists_and_names_the_real_documents(self):
        text = self.PATH.read_text()
        for doc in ("AGENTS.md", "CONTRIB.md", "ops/process/"):
            self.assertIn(doc, text)

    def test_it_stays_under_the_cap(self):
        size = len(self.PATH.read_bytes())
        self.assertLessEqual(size, 800,
                             f"CLAUDE.md is {size} bytes — it is a pointer, "
                             f"not a document; move content to AGENTS.md")


if __name__ == "__main__":
    unittest.main()
