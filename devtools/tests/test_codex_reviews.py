import unittest
from unittest.mock import patch

import test_feedback
import test_github

from devtools.codex_reviews import BOT, BOT_ID, SUMMARY, CodexReviews
from devtools.github import GitHub
from devtools.github_http import GitHubError


class CodexReviewTests(unittest.TestCase):
    base_setup = test_github.GitHubTests.setUp
    client = test_feedback.FeedbackTests.client

    def setUp(self):
        test_feedback.FeedbackTests.setUp(self)
        with self.store.connect() as db:
            db.execute("UPDATE work_orders SET pull_request=?,branch='feature' WHERE id=?",
                       (self.provider.pr["html_url"], self.order))
        self.provider.pr["draft"] = False
        self.provider.thread["isResolved"] = True
        self.service = GitHub(self.store, "beta", http=self.http)
        self.context = self.service._context(job=None)
        self.reviews = CodexReviews(self.service)

    def summary(self, code="Completed", security="Completed", revision=test_github.HEAD):
        comment = {
            "id": 100, "user": {"id": BOT_ID, "login": BOT, "type": "Bot"},
            "html_url": self.provider.pr["html_url"] + "#summary",
            "body": SUMMARY + "\n\n| Review | Status | Commit | Review trigger |\n| --- | --- | --- | --- |\n"
            + f"| 📝 **Code Review** | ✅ **{code}** <relative-time>now</relative-time> | `{revision[:7]}` | Manual request |\n"
            + (f"| 🔒 **Security Review** | ✅ **{security}** | `{revision[:7]}` | Manual request |\n" if security else ""),
        }
        self.provider.comments = [comment]
        return comment

    def test_request_is_once_per_kind_and_head_and_recovers_lost_reply(self):
        publish = self.service.pr_comment

        def lost_reply(*args, **kwargs):
            publish(*args, **kwargs)
            raise GitHubError(0, "Reply lost")

        with patch.object(self.service, "pr_comment", side_effect=lost_reply):
            with self.assertRaises(GitHubError):
                self.reviews.request(self.context, test_github.HEAD)
        CodexReviews(self.service).request(self.context, test_github.HEAD)
        self.reviews.request(self.context, test_github.HEAD)
        self.assertEqual(2, len(self.provider.comments))
        self.assertEqual(["@codex review", "@codex security review"],
                         [row["body"].splitlines()[0] for row in self.provider.comments])
        changed = "c" * 40
        self.provider.pr["head"]["sha"] = changed
        self.reviews.request(self.context, changed)
        self.assertEqual(4, len(self.provider.comments))
        with self.assertRaisesRegex(ValueError, "work-order"):
            self.reviews.request({**self.context, "job": self.job}, changed)
        with self.assertRaisesRegex(ValueError, "changed"):
            self.reviews.request(self.context, test_github.HEAD)

    def test_both_trusted_current_reviews_required_even_without_findings(self):
        self.summary(security=None)
        with self.assertRaisesRegex(ValueError, "Both Codex"):
            self.reviews.require_ready(self.context, test_github.HEAD)
        comment = self.summary()
        comment["user"]["id"] = 1
        self.assertEqual("pending", self.reviews.status(self.context, test_github.HEAD)["state"])
        comment["user"]["id"] = BOT_ID
        self.assertEqual("ready", self.reviews.require_ready(self.context, test_github.HEAD)["state"])
        self.provider.pr["head"]["sha"] = "c" * 40
        self.assertEqual("pending", self.reviews.status(self.context, "c" * 40)["state"])
        self.summary(security="Failed", revision="c" * 40)
        self.assertEqual("needs_attention", self.reviews.status(self.context, "c" * 40)["state"])
        self.summary(revision="c" * 40)["body"] += "| 📝 **Code Review** | ✅ **Completed** | `ccccccc` | Manual request |\n"
        self.assertEqual("pending", self.reviews.status(self.context, "c" * 40)["state"])

    def test_all_thread_pages_and_last_head_read_participate_in_merge_check(self):
        self.summary()
        read = self.service.pr_threads

        def pages(context, cursor=None):
            result = read(context)
            if cursor is None:
                result["next_cursor"] = "second"
            else:
                result["threads"][0]["isResolved"] = False
                result["threads"][0]["isOutdated"] = True
            return result

        with patch.object(self.service, "pr_threads", side_effect=pages):
            with self.assertRaisesRegex(ValueError, "threads"):
                self.reviews.require_ready(self.context, test_github.HEAD)
        self.provider.thread["isResolved"] = True
        original = self.service._unchanged

        def change(context, pr):
            self.provider.pr["head"]["sha"] = "c" * 40
            return original(context, pr)

        with patch.object(self.service, "_unchanged", side_effect=change):
            with self.assertRaisesRegex(ValueError, "changed"):
                self.reviews.require_ready(self.context, test_github.HEAD)

    def test_xo_reads_replies_and_resolves_through_existing_mcp_tools(self):
        self.summary()
        self.provider.thread["isResolved"] = False
        xo = self.client("beta")
        result = xo.tool("monitor", {"section": "feedback"})["delivery"]
        self.assertEqual("findings", result["codex"]["state"])
        reference = result["codex"]["threads"][0]["reference"]
        args = {"review": reference, "text": "Fixed in the integrated commit; boundary check passed.", "resolve": True}
        receipt = xo.tool("review_respond", args)
        self.assertTrue(receipt["resolved"])
        xo.tool("review_respond", args)
        replies = [r for r in self.provider.requests if "addPullRequestReviewThreadReply" in str(r[2])]
        self.assertEqual(1, len(replies))
        self.assertIn("Fixed", xo.tool("work_context", {"reference": receipt["evidence"]})["text"])
        with self.assertRaisesRegex(ValueError, "belong"):
            xo.tool("review_respond", {**args, "review": "thread:WRONG_THREAD"})
        with self.assertRaises(ValueError):
            self.client().tool("review_respond", args)
        with self.assertRaises(ValueError):
            self.client("alpha").tool("review_respond", args)
        self.assertEqual("ready", xo.tool("monitor", {"section": "feedback"})["delivery"]["codex"]["state"])

    def tick(self):
        with self.store.connect() as db:
            db.execute("UPDATE github_watches SET next_poll=0")
        self.service.tick()
        return [r for r in self.store.inbox("beta")["messages"] if "Work-order PR #" in r["body"]]

    def test_watch_waits_for_reviews_and_only_notifies_changes_including_reopened_findings(self):
        self.provider.run["conclusion"] = "success"
        self.provider.checks[test_github.MERGE] = [self.provider.check("success")]
        self.summary(security="Running")
        self.service.ci_watch(self.context, reviews=True)
        self.assertEqual(1, len(self.tick()))
        self.assertEqual(1, len(self.tick()))
        with self.store.connect() as db:
            self.assertEqual("active", db.execute("SELECT state FROM github_watches").fetchone()[0])
        self.summary()
        self.assertIn("ready", self.tick()[-1]["body"])
        self.provider.thread["isResolved"] = False
        self.assertIn("findings", self.tick()[-1]["body"])
        self.provider.thread["isResolved"] = True
        messages = self.tick()
        self.assertEqual(4, len(messages))
        self.assertIn("ready", messages[-1]["body"])
        self.assertEqual(4, len(self.tick()))
        self.provider.pr["head"]["sha"] = "c" * 40
        self.assertIn("superseded", self.tick()[-1]["body"])

    def test_request_uncertainty_and_rate_limit_do_not_repeat_writes(self):
        with patch.object(self.service, "pr_comment", side_effect=GitHubError(0, "Lost")):
            with self.assertRaises(GitHubError):
                self.reviews.request(self.context, test_github.HEAD)
        with self.assertRaisesRegex(ValueError, "uncertain"):
            self.reviews.request(self.context, test_github.HEAD)
        self.service.ci_watch(self.context, reviews=True)
        with patch.object(self.service, "_pr", side_effect=GitHubError(429, "Back off", retry_at=9999999999)):
            self.assertIn("unavailable", self.tick()[-1]["body"])
        with self.store.connect() as db:
            self.assertEqual(9999999999, db.execute("SELECT next_poll FROM github_watches").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
