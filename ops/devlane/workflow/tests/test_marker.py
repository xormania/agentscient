"""marker — findings and blockers, and the stage they hold shut (PLAN §3.5).

Written before the verb exists. "Review findings open markers; fix cannot be
left while markers from the current review cycle are open" — mechanical
again, so it is a spec flag rather than a rule the engine knows by name.
"""

import json
import unittest

import support
from support import SandboxCase
import canonical
from errors import EXIT_OK, EXIT_REFUSED


class MarkerCase(SandboxCase):
    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-009", "--kind", "artifact", "--objective", "doc",
                   check=EXIT_OK)

    def state(self):
        return json.loads(self.sb.wf("--json", "status", "WO-009", check=EXIT_OK).stdout)

    def events(self):
        raw = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-009", check=EXIT_OK).stdout)
        return support.without_binds(raw["events"])


class OpenAndClose(MarkerCase):
    def test_opening_a_marker_records_it_in_the_projection(self):
        body = json.loads(
            self.sb.wf("--json", "marker", "WO-009", "open", "F1",
                       "--note", "objective is vague", check=EXIT_OK).stdout
        )
        self.assertEqual(body["open_markers"], ["F1"])
        event = self.events()[-1]
        self.assertEqual(event["type"], "marker.open")
        self.assertEqual(event["id"], "F1")
        self.assertEqual(event["note"], "objective is vague")
        self.assertEqual(event["agent"], support.Sandbox.AGENT)

    def test_closing_removes_it(self):
        self.sb.wf("marker", "WO-009", "open", "F1", check=EXIT_OK)
        self.sb.wf("marker", "WO-009", "open", "F2", check=EXIT_OK)
        self.assertEqual(self.state()["open_markers"], ["F1", "F2"])
        self.sb.wf("marker", "WO-009", "close", "F1", check=EXIT_OK)
        self.assertEqual(self.state()["open_markers"], ["F2"])
        self.assertEqual(self.events()[-1]["type"], "marker.close")

    def test_nothing_is_rewritten_when_a_marker_closes(self):
        self.sb.wf("marker", "WO-009", "open", "F1", check=EXIT_OK)
        self.sb.wf("marker", "WO-009", "close", "F1", check=EXIT_OK)
        kinds = [e["type"] for e in self.events() if e["type"].startswith("marker.")]
        self.assertEqual(kinds, ["marker.open", "marker.close"],
                         "the open stays in the chain; the close is appended")

    def test_reopening_an_open_marker_refuses(self):
        self.sb.wf("marker", "WO-009", "open", "F1", check=EXIT_OK)
        proc = self.sb.wf("marker", "WO-009", "open", "F1", check=EXIT_REFUSED)
        self.assertIn("not already open", proc.stderr)

    def test_closing_a_marker_that_is_not_open_refuses(self):
        proc = self.sb.wf("marker", "WO-009", "close", "F9", check=EXIT_REFUSED)
        self.assertIn("is open", proc.stderr)

    def test_a_marker_id_must_be_given(self):
        self.assertEqual(self.sb.wf("marker", "WO-009", "open").returncode, 64)

    def test_an_unknown_action_is_a_usage_error(self):
        self.assertEqual(
            self.sb.wf("marker", "WO-009", "sideways", "F1").returncode, 64
        )

    def test_a_marker_can_be_reopened_after_being_closed(self):
        self.sb.wf("marker", "WO-009", "open", "F1", check=EXIT_OK)
        self.sb.wf("marker", "WO-009", "close", "F1", check=EXIT_OK)
        self.sb.wf("marker", "WO-009", "open", "F1", check=EXIT_OK)
        self.assertEqual(self.state()["open_markers"], ["F1"])


class MarkersHoldFixShut(MarkerCase):
    """The artifact kind's fix stage cannot be left with findings open."""

    def to_fix(self):
        self.sb.wf("advance", "WO-009", check=EXIT_OK)                   # review
        self.sb.wf("outcome", "WO-009", "finding", "--by", "reviewer",
                   check=EXIT_OK)                                        # -> fix
        self.assertEqual(self.state()["stage"], "fix")

    def test_fix_refuses_to_advance_while_a_marker_is_open(self):
        self.to_fix()
        self.sb.wf("marker", "WO-009", "open", "F1", "--note", "unfixed",
                   check=EXIT_OK)
        proc = self.sb.wf("advance", "WO-009", check=EXIT_REFUSED)
        self.assertIn("marker", proc.stderr.lower())
        self.assertIn("F1", proc.stderr)

    def test_closing_the_marker_releases_the_stage(self):
        self.to_fix()
        self.sb.wf("marker", "WO-009", "open", "F1", check=EXIT_OK)
        self.sb.wf("advance", "WO-009", check=EXIT_REFUSED)
        self.sb.wf("marker", "WO-009", "close", "F1", check=EXIT_OK)
        self.sb.wf("advance", "WO-009", check=EXIT_OK)
        self.assertEqual(self.state()["stage"], "review")

    def test_other_stages_are_not_held_by_open_markers(self):
        # Only stages the spec marks are blocked; a marker is a record
        # everywhere else, not a gate.
        self.sb.wf("marker", "WO-009", "open", "F1", check=EXIT_OK)
        self.sb.wf("advance", "WO-009", check=EXIT_OK)
        self.assertEqual(self.state()["stage"], "review")

    def test_the_flag_is_spec_data_not_an_engine_rule(self):
        spec = canonical.loads(
            (support.WF_DIR / "gate-kinds" / "artifact.json").read_bytes()
        )
        fix = next(s for s in spec["stages"] if s["name"] == "fix")
        self.assertTrue(fix.get("blocked_by_open_markers"))
        for other in spec["stages"]:
            if other["name"] != "fix":
                self.assertFalse(other.get("blocked_by_open_markers", False))


class MarkersAndClaims(MarkerCase):
    def test_a_marker_is_evidence_and_therefore_auto_commits(self):
        before = self.sb.head()
        self.sb.wf("marker", "WO-009", "open", "F1", check=EXIT_OK)
        self.assertNotEqual(self.sb.head(), before)
        self.assertIn("marker.open F1", self.sb.log(1))


if __name__ == "__main__":
    unittest.main()
