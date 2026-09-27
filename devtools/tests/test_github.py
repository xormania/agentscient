import copy
import hashlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from support import Client, until

from devtools.github import GitHub
from devtools.github_http import GitHubError, GitHubHTTP
from devtools.launch import initialize
from devtools.store import Store

HEAD, MERGE = "a" * 40, "b" * 40


class Provider:
    """HTTP fixture for the documented REST and GraphQL shapes; not a live GitHub acceptance run."""

    def __init__(self):
        self.requests, self.comments, self.reviews = [], [], []
        self.inline = []
        self.exists = False
        self.logs_missing = False
        self.pr = {
            "number": 7,
            "node_id": "PR_7",
            "html_url": "https://github.com/example/project/pull/7",
            "title": "Test PR",
            "body": "Description",
            "head": {"ref": "feature", "sha": HEAD},
            "base": {"ref": "dev"},
            "state": "open",
            "draft": True,
            "mergeable": True,
            "mergeable_state": "clean",
            "merge_commit_sha": MERGE,
            "merged": False,
            "changed_files": 1,
        }
        self.run = {
            "id": 10,
            "html_url": "https://github.com/example/project/actions/runs/10",
            "name": "CI",
            "head_sha": HEAD,
            "head_branch": "feature",
            "event": "pull_request",
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "failure",
            "run_started_at": "2026-09-26T10:00:00Z",
        }
        self.checks = {HEAD: [self.check("success")], MERGE: [self.check("failure")]}
        self.tasks = [
            {
                "id": 101,
                "name": "storage",
                "status": "completed",
                "conclusion": "failure",
                "check_run_url": "https://api.github.com/repos/example/project/check-runs/201",
                "html_url": self.run["html_url"] + "/job/101",
                "steps": [{"name": "Run tests", "number": 3, "status": "completed", "conclusion": "failure"}],
            }
        ]
        self.files = [
            {
                "filename": "devtools/example.py",
                "status": "modified",
                "additions": 1,
                "deletions": 1,
                "changes": 2,
                "patch": "@@ -1 +1 @@\n-old\n+new",
            }
        ]
        self.thread = {
            "id": "THREAD_1",
            "isResolved": False,
            "isOutdated": False,
            "path": "devtools/example.py",
            "line": 1,
            "pullRequest": {"number": 7, "repository": {"nameWithOwner": "example/project"}},
            "comments": {
                "nodes": [
                    {
                        "databaseId": 12,
                        "body": "Please fix this",
                        "url": self.pr["html_url"] + "#discussion_r12",
                        "author": {"login": "reviewer"},
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        }
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("test-results.xml", "<testsuite tests='12' failures='0'/>")
            zipped.writestr("../evidence.txt", "Names in ZIP files must never become write paths")
        self.archive = archive.getvalue()
        self.artifact = {
            "id": 90,
            "name": "test-results",
            "size_in_bytes": len(self.archive),
            "expired": False,
            "created_at": "2026-09-26T10:01:00Z",
            "expires_at": "2026-12-25T10:01:00Z",
            "digest": "sha256:" + hashlib.sha256(self.archive).hexdigest(),
            "workflow_run": {"id": 10, "head_sha": HEAD},
        }

    @staticmethod
    def check(conclusion):
        return {
            "id": 201,
            "name": "storage",
            "status": "completed",
            "conclusion": conclusion,
            "details_url": "https://github.com/example/project/actions/runs/10",
        }

    @staticmethod
    def page(rows, query):
        size, page = int(query.get("per_page", [100])[0]), int(query.get("page", [1])[0])
        return rows[(page - 1) * size : page * size]

    def reply(self, method, target, body, headers):
        self.requests.append((method, target, copy.deepcopy(body), headers.get("Authorization")))
        parsed = urllib.parse.urlsplit(target)
        path, query = parsed.path, urllib.parse.parse_qs(parsed.query)
        root = "/repos/example/project"
        if path.startswith("/downloads/"):
            self.assert_download_auth = headers.get("Authorization")
            return (
                200,
                self.archive
                if path.endswith("archive")
                else b"setup\nERROR: assertion failed\nBearer fixture-credential\nfixture-credential\n",
                {},
            )
        if path == "/graphql":
            q, v = body["query"], body["variables"]
            if "query Overview" in q:
                return (
                    200,
                    {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewDecision": "REVIEW_REQUIRED",
                                    "mergeStateStatus": "BLOCKED",
                                    "reviews": {"nodes": []},
                                }
                            }
                        }
                    },
                    {},
                )
            if "query Threads" in q:
                return (
                    200,
                    {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewThreads": {
                                        "nodes": [self.thread],
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    }
                                }
                            }
                        }
                    },
                    {},
                )
            if "query Thread" in q:
                row = copy.deepcopy(self.thread)
                if v["id"] == "WRONG_THREAD":
                    row["pullRequest"]["number"] = 999
                return 200, {"data": {"node": row}}, {}
            for mutation in ("convertPullRequestToDraft", "markPullRequestReadyForReview"):
                if mutation in q:
                    self.pr["draft"] = mutation == "convertPullRequestToDraft"
                    return 200, {"data": {mutation: {"pullRequest": {"id": "PR_7"}}}}, {}
            if "addPullRequestReviewThreadReply" in q:
                return (
                    200,
                    {
                        "data": {
                            "addPullRequestReviewThreadReply": {
                                "comment": {"id": "C13", "url": self.pr["html_url"] + "#discussion_r13"}
                            }
                        }
                    },
                    {},
                )
            for mutation in ("unresolveReviewThread", "resolveReviewThread"):
                if mutation in q:
                    self.thread["isResolved"] = mutation == "resolveReviewThread"
                    return (
                        200,
                        {"data": {mutation: {"thread": {"id": "THREAD_1", "isResolved": self.thread["isResolved"]}}}},
                        {},
                    )
        if path == root:
            return 200, {"allow_merge_commit": True, "allow_squash_merge": False, "allow_rebase_merge": False}, {}
        if path == root + "/pulls":
            if method == "POST":
                self.exists = True
                self.pr.update({key: body[key] for key in ("title", "body", "draft")})
                return 201, self.pr, {}
            return 200, [self.pr] if self.exists else [], {}
        if path == root + "/pulls/7":
            if method == "PATCH":
                self.pr.update(body)
            return 200, self.pr, {}
        if path == root + "/pulls/7/files":
            return 200, self.page(self.files, query), {}
        if path == root + "/pulls/7/reviews":
            if method == "POST":
                result = {
                    "id": 20 + len(self.reviews),
                    "html_url": self.pr["html_url"] + "#review",
                    "state": body["event"],
                    **body,
                }
                self.reviews.append(result)
                return 200, result, {}
            return 200, self.page(self.reviews, query), {}
        if path == root + "/pulls/7/comments":
            return 200, self.page(self.inline, query), {}
        if path == root + "/issues/7/comments":
            if method == "POST":
                result = {
                    "id": 40 + len(self.comments),
                    "html_url": self.pr["html_url"] + "#comment",
                    "issue_url": self.url + root + "/issues/7",
                    **body,
                }
                self.comments.append(result)
                return 201, result, {}
            return 200, self.page(self.comments, query), {}
        if path.startswith(root + "/issues/comments/"):
            return 200, next(row for row in self.comments if row["id"] == int(path.rsplit("/", 1)[1])), {}
        if path == root + "/pulls/7/merge":
            if body["sha"] != self.pr["head"]["sha"]:
                return 409, {"message": "Head changed"}, {}
            self.pr.update(merged=True, state="closed")
            return 200, {"merged": True, "sha": MERGE, "message": "Merged"}, {}
        if path.startswith(root + "/commits/"):
            revision = path.split("/")[-2]
            if path.endswith("/check-runs"):
                rows = self.checks.get(revision, [])
                return 200, {"total_count": len(rows), "check_runs": self.page(rows, query)}, {}
            return 200, {"state": "pending", "total_count": 0, "statuses": []}, {}
        if path == root + "/actions/runs":
            rows = [self.run] if query.get("head_sha", [None])[0] in (None, self.run["head_sha"]) else []
            return 200, {"workflow_runs": self.page(rows, query), "total_count": len(rows)}, {}
        if path == root + "/actions/runs/10":
            return 200, self.run, {}
        if path.startswith(root + "/actions/runs/10/attempts/"):
            if path.endswith("/jobs"):
                return 200, {"jobs": self.page(self.tasks, query), "total_count": len(self.tasks)}, {}
            return 200, {**self.run, "run_attempt": 1, "run_started_at": "2026-09-26T10:00:00Z"}, {}
        if path in (root + "/actions/jobs/101/logs", root + "/actions/artifacts/90/zip"):
            if path.endswith("logs") and self.logs_missing:
                return 410, {"message": "Logs expired"}, {}
            return (
                302,
                b"",
                {"Location": self.url + ("/downloads/log" if path.endswith("logs") else "/downloads/archive")},
            )
        if path == root + "/check-runs/201/annotations":
            return (
                200,
                [
                    {
                        "path": "test_storage.py",
                        "start_line": 12,
                        "message": "assertion failed",
                        "annotation_level": "failure",
                    }
                ],
                {},
            )
        if path == root + "/actions/workflows":
            return (
                200,
                {
                    "total_count": 1,
                    "workflows": [{"id": 2, "name": "CI", "path": ".github/workflows/ci.yml", "state": "active"}],
                },
                {},
            )
        if path == root + "/actions/workflows/ci.yml/dispatches":
            return 204, b"", {}
        if path.endswith(("/rerun", "/rerun-failed-jobs")):
            self.run.update(run_attempt=self.run["run_attempt"] + 1, status="queued", conclusion=None)
            return 201, b"", {}
        if path == root + "/actions/runs/10/cancel":
            self.run.update(status="completed", conclusion="cancelled")
            return 202, b"", {}
        if path == root + "/actions/runs/10/artifacts":
            return 200, {"total_count": 1, "artifacts": [self.artifact]}, {}
        if path == root + "/actions/artifacts/90":
            return 200, self.artifact, {}
        return 404, {"message": "Fixture route missing: " + path}, {}


class GitHubTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.directory = self.root / "state"
        initialize(self.directory, self.workspace, ["alpha:external", "beta:external"])
        self.store = Store(self.directory)
        config = json.loads((self.directory / "team.json").read_text())
        config["github"] = {"repository": "example/project", "base": "dev"}
        (self.directory / "team.json").write_text(json.dumps(config))
        self.provider = Provider()
        provider = self.provider

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                data = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                body = json.loads(data) if data else None
                status, value, headers = provider.reply(self.command, self.path, body, self.headers)
                encoded = value if isinstance(value, bytes) else json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(encoded)))
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(encoded)

            do_POST = do_PATCH = do_PUT = do_GET

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.provider.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.http = GitHubHTTP(api_root=self.provider.url, credential=lambda: "fixture-credential")

    def client(self, member="alpha"):
        env = {**os.environ, "FIXTURE_GITHUB_ROOT": self.provider.url}
        with patch("support.ENTRY", Path(__file__).with_name("github_fixture.py")):
            client = Client(self.directory, member, env=env, operator=True)
        self.addCleanup(client.close)
        return client

    def work(self, client):
        order = client.invoke(
            "work_order_create", title="GitHub support", objective="Agent tasks through MCP", done_when="CI passes"
        )
        job = client.invoke(
            "job_create",
            title="Add GitHub tools",
            objective="Help agents finish PR work",
            done_when="Reviewed PR",
            repository="example/project",
            branch="feature",
        )
        return order["work_order"]["id"], job["job"]["id"]

    def test_mcp_pr_lifecycle_uses_work_context_and_inspected_revision(self):
        client = self.client()
        order, job = self.work(client)
        created = client.invoke("pr_open", summary="Adds agent tasks")
        self.assertEqual((order, job), (created["work_order"], created["job"]))
        self.assertFalse(created["reused"])
        self.assertTrue(client.invoke("pr_open")["reused"])
        self.assertIn("Work order: " + str(order), self.provider.pr["body"])
        self.assertEqual(self.provider.pr["html_url"], client.invoke("job_get")["job"]["pull_request"])
        observed = client.invoke("pr_get")
        self.assertEqual("failed", observed["ci"]["state"])
        self.assertEqual(MERGE, observed["ci"]["tested_revision"])
        self.assertIn("PR is a draft", observed["observed_blockers"])
        diff = client.invoke("pr_diff", path="devtools/example.py", revision=HEAD)
        self.assertIn("+new", diff["patch"])
        client.invoke("pr_update", draft=False, title="Useful GitHub tasks")
        self.assertFalse(self.provider.pr["draft"])
        client.invoke(
            "pr_review",
            revision=HEAD,
            decision="request_changes",
            body="Please address the failure",
            findings=[{"path": "devtools/example.py", "line": 1, "body": "Check this branch"}],
        )
        self.assertEqual(HEAD, self.provider.reviews[0]["commit_id"])
        client.invoke("pr_comment", body="Evidence is attached to the work order")
        self.assertEqual("Evidence is attached to the work order", client.invoke("pr_comments")["comments"][0]["body"])
        self.assertEqual(HEAD, client.invoke("pr_comments", kind="review")["comments"][0]["revision"])
        with self.assertRaisesRegex(ValueError, "head changed"):
            client.invoke("pr_merge", revision="c" * 40)
        self.assertFalse(any(method == "PUT" for method, *_ in self.provider.requests))
        merged = client.invoke("pr_merge", revision=HEAD)
        self.assertEqual("merge", merged["method"])
        self.assertTrue(merged["merged"])
        self.assertEqual("open", client.invoke("work_order_get")["work_order"]["status"])
        self.assertTrue(client.invoke("pr_merge", revision=HEAD)["already_merged"])

    def test_review_threads_and_closed_input_boundary(self):
        client = self.client()
        self.work(client)
        client.invoke("pr_open")
        thread = client.invoke("pr_threads")["threads"][0]["id"]
        client.invoke("pr_threads", action="reply", thread=thread, body="Fixed in the next revision")
        self.assertTrue(client.invoke("pr_threads", action="resolve", thread=thread)["thread"]["thread"]["isResolved"])
        self.assertFalse(client.invoke("pr_threads", action="reopen", thread=thread)["thread"]["thread"]["isResolved"])
        with self.assertRaisesRegex(ValueError, "does not belong"):
            client.invoke("pr_threads", action="resolve", thread="WRONG_THREAD")
        for args in ({"endpoint": "/user"}, {"token": "secret"}, {"command": "gh api /user"}):
            with self.assertRaises(ValueError):
                client.invoke("pr_get", **args)
        with self.assertRaises(ValueError):
            client.invoke(
                "pr_review",
                revision=HEAD,
                decision="approve",
                body="Okay",
                findings=[{"path": "x", "line": "bad", "body": "y"}],
            )
        self.assertEqual(3, len(client.call("tools/list")["tools"]))

    def test_ci_diagnosis_control_and_redirect_credential_boundary(self):
        client = self.client()
        self.work(client)
        client.invoke("pr_open")
        diagnosis = client.invoke("ci_failures", run=10)
        failed = diagnosis["failures"][0]
        self.assertEqual("Run tests", failed["steps"][0]["name"])
        self.assertIn("assertion failed", failed["log_excerpt"])
        self.assertNotIn("fixture-credential", failed["log_excerpt"])
        self.assertIsNone(self.provider.assert_download_auth)
        self.assertEqual(12, failed["annotations"][0]["start_line"])
        self.provider.logs_missing = True
        unavailable = client.invoke("ci_failures", run=10)["failures"][0]
        self.assertIn("expired", unavailable["log_error"])
        self.assertEqual("Run tests", unavailable["steps"][0]["name"])
        self.assertEqual("CI", client.invoke("ci_workflows")["workflows"][0]["name"])
        self.assertTrue(client.invoke("ci_run", workflow="ci.yml", inputs={"suite": "storage"})["requested"])
        rerun = client.invoke("ci_rerun", run=10)
        self.assertEqual(HEAD, rerun["revision"])
        self.assertEqual("pending", client.invoke("ci_status", run=10)["state"])
        self.assertTrue(client.invoke("ci_cancel", run=10)["requested"])
        self.assertFalse(client.invoke("ci_cancel", run=10)["requested"])

    def test_ci_evidence_is_managed_and_retains_source(self):
        client = self.client()
        order, job = self.work(client)
        client.invoke("pr_open")
        self.assertEqual(90, client.invoke("ci_artifacts", run=10)["artifacts"][0]["id"])
        saved = client.invoke("ci_artifact_save", artifact=90)
        self.assertEqual((order, job), (saved["work_order"], saved["job"]))
        self.assertEqual(2, saved["entry_count"])
        self.assertEqual(HEAD, saved["source"]["revision"])
        self.assertEqual(10, saved["source"]["run"])
        self.assertTrue(client.invoke("ci_artifact_save", artifact=90)["reused"])
        self.provider.run["run_attempt"] = 2
        report = client.invoke("ci_artifact_save", artifact=90, entry="test-results.xml")
        self.assertEqual(2, report["source"]["observed_attempt"])
        self.assertIn("does not identify", report["source"]["note"])
        retained = client.invoke("artifact_read", artifact=report["artifact"]["id"])
        self.assertIn("tests='12'", retained["content"])
        self.assertEqual(90, retained["sources"][0]["source_artifact"])
        client.invoke("ci_artifact_save", artifact=90, entry="../evidence.txt")
        self.assertFalse((self.root / "evidence.txt").exists())
        self.provider.artifact["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "digest"):
            client.invoke("ci_artifact_save", artifact=90)

    def test_watch_survives_restart_and_retains_original_work(self):
        client = self.client()
        order, job = self.work(client)
        client.invoke("pr_open")
        self.provider.run.update(status="in_progress", conclusion=None)
        watch = client.invoke("ci_watch", run=10)["watch"]
        until(lambda: self.store.inbox("alpha")["messages"])
        client.close()
        service = GitHub(self.store, "alpha", http=self.http)
        with self.store.connect() as db:
            db.execute("UPDATE members SET selected_work_order=NULL,selected_job=NULL WHERE name='alpha'")
            # Simulate a process killed while it owned a polling lease; a restart recovers it immediately.
            db.execute(
                "UPDATE github_watches SET next_poll=?,poll_pid=? WHERE id=?",
                (time.time() + 600, client.process.pid, watch),
            )
        self.provider.run.update(status="completed", conclusion="success")
        restarted = self.client()
        messages = until(lambda: rows if len(rows := self.store.inbox("alpha")["messages"]) >= 2 else None)
        self.assertEqual((order, job), (messages[-1]["work_order"], messages[-1]["job"]))
        self.assertIn("passed", messages[-1]["body"])
        service.tick()
        self.assertEqual(2, len(self.store.inbox("alpha")["messages"]))
        restarted.invoke("job_select", job=job)
        next_watch = restarted.invoke("ci_watch")["watch"]
        self.provider.pr["head"]["sha"] = "c" * 40
        service.tick()
        self.assertIn("superseded", self.store.inbox("alpha")["messages"][-1]["body"])
        beta = self.client("beta")
        self.assertFalse(beta.invoke("ci_watch_stop", watch=next_watch)["stopped"])

    def test_pagination_does_not_make_incomplete_ci_green(self):
        self.provider.exists = True
        self.provider.checks[MERGE] = [dict(self.provider.check("success"), id=i) for i in range(1, 101)]
        self.provider.checks[MERGE].append(dict(self.provider.check("failure"), id=999))
        client = self.client()
        status = client.invoke("ci_status", pr=7)
        self.assertEqual("failed", status["state"])
        self.assertEqual(102, status["check_count"])
        self.assertEqual(20, len(status["checks"]))
        self.assertEqual(2, status["next_page"])

    def test_transport_reports_errors_without_exposing_credentials(self):
        with self.assertRaises(GitHubError) as error:
            self.http.request("GET", "/missing")
        self.assertEqual(404, error.exception.status)
        self.assertNotIn("fixture-credential", str(error.exception))
        with patch("devtools.github_http.subprocess.run", side_effect=FileNotFoundError):
            with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(GitHubError, "authentication"):
                GitHubHTTP().token()

    def test_comment_previews_and_full_text_keep_pr_scope(self):
        client = self.client()
        self.work(client)
        client.invoke("pr_open")
        body = "a" * 7000 + "final finding"
        comment = client.invoke("pr_comment", body=body)["comment"]
        preview = client.invoke("pr_comments")["comments"][0]
        self.assertEqual(1500, len(preview["body"]))
        self.assertEqual(body, client.invoke("pr_comments", comment=comment)["comments"][0]["body"])
        self.provider.comments[0]["issue_url"] = self.provider.url + "/repos/example/project/issues/999"
        with self.assertRaisesRegex(ValueError, "does not belong"):
            client.invoke("pr_comments", comment=comment)

    def test_existing_work_and_evidence_survive_version_one_upgrade(self):
        client = self.client()
        order, job = self.work(client)
        saved = client.invoke("artifact_save", name="earlier-report.txt", content="Prior evidence")
        client.close()
        with self.store.connect() as db:
            db.execute("DROP TABLE github_watches")
            db.execute("DROP TABLE artifact_sources")
            db.execute("PRAGMA user_version=1")
        restarted = self.client()
        self.assertEqual(job, restarted.invoke("job_get")["job"]["id"])
        report = restarted.invoke("artifact_read", artifact=saved["artifact"]["id"])
        self.assertEqual("Prior evidence", report["content"])
        self.assertEqual(order, report["work"][0]["work_order"])
        self.assertEqual([], report["sources"])
        with self.store.connect() as db:
            self.assertEqual(7, db.execute("PRAGMA user_version").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
