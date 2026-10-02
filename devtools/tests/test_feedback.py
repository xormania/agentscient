import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import test_github
from support import Client, fixture_work

from devtools.api import API
from devtools.github import GitHub


class FeedbackTests(unittest.TestCase):
    base_setup = test_github.GitHubTests.setUp

    def setUp(self):
        self.base_setup()
        config = json.loads((self.directory / "team.json").read_text())
        config["co"] = "alpha"
        config["members"].extend(
            [
                {"name": "producer", "harness": "external", "workspace": str(self.workspace)},
                {"name": "other", "harness": "external", "workspace": str(self.workspace)},
            ]
        )
        config["project"].update(checkout=str(self.workspace), repository="example/project")
        (self.directory / "team.json").write_text(json.dumps(config))
        API(self.directory, "alpha").call(
            "direct",
            {
                "title": "Delivery",
                "objective": "Bounded work",
                "done_when": "Evidence",
                "constraints": "MCP only",
            },
        )
        fixture_work(API(self.directory, "beta"), [
            {"name": "Feature", "role": "coder", "objective": "Feature", "done_when": "Tested", "constraints": "Product"},
            {"name": "Separate", "role": "docs", "objective": "Docs", "done_when": "Documented", "constraints": "Docs"},
        ])
        self.api = API(self.directory, "producer")
        self.job = self.api.control.snapshot()["job"]
        self.order = self.api.control.snapshot()["work_order"]
        self.api.work.job_update(job=self.job, pull_request=self.provider.pr["html_url"])
        self.provider.exists = True

    def client(self, member="producer"):
        with patch("support.ENTRY", Path(__file__).with_name("github_fixture.py")):
            client = Client(self.directory, member, env={**os.environ, "FIXTURE_GITHUB_ROOT": self.provider.url})
        self.addCleanup(client.close)
        return client

    def test_normal_ci_inspection_retrieves_and_retains_diagnostics_with_hidden_provider_context(self):
        client = self.client()
        result = client.tool("work_inspect", {"section": "ci"})
        self.assertEqual("failed", result["ci"]["state"])
        self.assertIn("assertion failed", result["failures"][0]["log_excerpt"])
        self.assertNotIn("fixture-credential", json.dumps(result))
        retained = client.tool("work_context", {"reference": result["evidence"]})
        self.assertIn("assertion failed", retained["content"])
        self.assertEqual(result["evidence"], client.tool("work_inspect", {"section": "ci"})["evidence"])
        with self.assertRaises(ValueError):
            client.tool("work_inspect", {"section": "ci", "repository": "other/repository"})
        with self.assertRaises(ValueError):
            self.client("other").tool("work_context", {"reference": result["evidence"]})
        overview = self.client("beta").tool("monitor", {"work": "Feature", "section": "ci"})
        self.assertEqual("failed", overview["delivery"]["ci"]["state"])

    def test_failed_check_pages_and_missing_logs_are_explicit(self):
        self.provider.tasks += [
            dict(self.provider.tasks[0], id=102, name="second"),
            dict(self.provider.tasks[0], id=103, name="third"),
        ]
        client = self.client()
        first = client.tool("work_inspect", {"section": "ci"})
        self.assertEqual((2, 3), (first["next_page"], first["failed_check_count"]))
        second = client.tool("work_inspect", {"section": "ci", "page": 2, "offset": 0})
        self.assertEqual("third", second["failures"][0]["name"])
        self.assertIsNotNone(second["failures"][0]["log_error"])
        self.assertIsNone(second["next_page"])
        self.provider.logs_missing = True
        self.assertIn("expired", client.tool("work_inspect", {"section": "ci"})["failures"][0]["log_error"])

    def test_external_comments_are_bounded_but_full_text_is_retained_with_revision_and_location(self):
        full = "Review detail " * 300 + "final finding"
        self.provider.comments = [
            {"id": i, "body": full, "html_url": self.provider.pr["html_url"] + "#comment"} for i in range(11)
        ]
        self.provider.inline = [
            {
                "id": 42,
                "body": "Handle empty input",
                "path": "src/Example.php",
                "line": 12,
                "commit_id": test_github.HEAD,
            }
        ]
        client = self.client()
        result = client.tool("work_inspect", {"section": "feedback"})
        self.assertEqual(2, result["next_page"])
        self.assertEqual(500, len(result["comments"]["conversation"][0]["body"]))
        self.assertEqual("src/Example.php", result["comments"]["inline"][0]["path"])
        self.assertEqual(test_github.HEAD, result["comments"]["inline"][0]["revision"])
        self.assertIn("final finding", client.tool("work_context", {"reference": result["evidence"]})["content"])
        self.assertEqual(
            1, len(client.tool("work_inspect", {"section": "feedback", "page": 2})["comments"]["conversation"])
        )

    def test_ci_watch_routes_to_current_supervisor_with_original_job(self):
        service = GitHub(self.store, "producer", http=self.http)
        context = service._context(job=self.job)
        service.ci_watch(context)
        service.tick()
        rows = [r for r in self.store.inbox("beta")["messages"] if r["sender"] == "producer"]
        self.assertEqual(1, len(rows))
        self.assertEqual((self.order, self.job), (rows[0]["work_order"], rows[0]["job"]))
        self.assertIn("failed", rows[0]["body"])
        service.tick()
        self.assertEqual(1, len([r for r in self.store.inbox("beta")["messages"] if r["sender"] == "producer"]))


if __name__ == "__main__":
    unittest.main()
