"""Reports commit only under the binding that authorized the request."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import initialize

from devtools.api import API


class ReportBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        workspace = root / "workspace"
        workspace.mkdir()
        state = root / "state"
        initialize(state, workspace, ["owner:external", "xo:external", "coder:external"])
        self.operator = API(state, "owner", operator=True)
        self.store = self.operator.store
        self.order = self.operator.work.work_order_create(
            title="Report custody", objective="Retain current work", done_when="No stale messages"
        )["work_order"]["id"]
        self.jobs = [self.operator.work.job_create(
            title=title, objective=title, done_when="Evidence retained", work_order=self.order
        )["job"]["id"] for title in ("First", "Second")]
        self.operator.control.bind("owner", "co", self.order)
        self.operator.control.bind("xo", "xo", self.order, reports_to="owner")
        self.rebind(self.jobs[0])
        self.coder = API(state, "coder")

    def rebind(self, job):
        self.operator.control.bind("coder", "coder", self.order, job=job, reports_to="xo")

    def assert_no_publication(self):
        with self.store.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM work_updates").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM messages").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM work_links WHERE artifact IS NOT NULL").fetchone()[0])

    def test_rebind_after_request_capture_rejects_result_and_guidance(self):
        for tool in ("work_report", "guidance_request"):
            with self.subTest(tool=tool):
                self.rebind(self.jobs[0])
                with self.assertRaisesRegex(ValueError, "changed during this report"):
                    self.coder.call(tool, {"text": "Stale first-job report"},
                                    on_context=lambda: self.rebind(self.jobs[1]))
                self.assert_no_publication()

    def test_rebind_while_saving_evidence_does_not_publish_stale_artifact(self):
        original = self.coder.control.artifacts.save

        def save_then_rebind(**kwargs):
            retained = original(**kwargs)
            self.rebind(self.jobs[1])
            return retained

        with patch.object(self.coder.control.artifacts, "save", side_effect=save_then_rebind):
            with self.assertRaisesRegex(ValueError, "changed during this report"):
                self.coder.call("work_report", {"text": "First-job result", "kind": "result",
                                               "evidence": {"name": "proof.txt", "content": "First-job proof"}})
        self.assert_no_publication()
        with self.store.connect() as db:
            # The private bytes may be retained, but no work context gains access.
            self.assertEqual(1, db.execute("SELECT count(*) FROM artifacts").fetchone()[0])

    def test_same_binding_retry_reuses_report_but_stale_retry_is_rejected(self):
        args = {"text": "Current progress"}
        first = self.coder.call("work_report", args)
        second = self.coder.call("work_report", args)
        self.assertEqual(first["reference"], second["reference"])
        self.assertTrue(second["reused"])
        with self.assertRaisesRegex(ValueError, "changed during this report"):
            self.coder.call("work_report", args, on_context=lambda: self.rebind(self.jobs[1]))
        with self.store.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM work_updates").fetchone()[0])
            self.assertEqual(1, db.execute("SELECT count(*) FROM messages").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
