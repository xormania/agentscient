"""ci_minutes.py bills the way GitHub does, fires over budget, stays
quiet at it, and never renders an unread window as a zero."""

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

import support

SCRIPT = support.WF_DIR / "checks" / "ci_minutes.py"
REPO = support.WF_DIR.parent.parent.parent
GUARD = REPO / ".github" / "workflows" / "ci-minutes.yml"


def job(name, seconds, started=True, labels=("ubuntu-latest",)):
    """A job as the jobs API reports it. `started=False` is a job GitHub
    refused before a runner was assigned: no steps, four seconds of
    lifetime, and no bill."""
    base = "2026-08-28T04:26:20+00:00"
    end = f"2026-08-28T04:{26 + seconds // 60:02d}:{20 + seconds % 60:02d}+00:00"
    if seconds >= 40:
        # keep the arithmetic honest past the minute boundary
        minute, second = divmod(26 * 60 + 20 + seconds, 60)
        end = f"2026-08-28T04:{minute:02d}:{second:02d}+00:00"
    return {
        "name": name,
        "started_at": base,
        "completed_at": end if started else "2026-08-28T04:26:24+00:00",
        "steps": [{"name": "Set up job"}] if started else [],
        "labels": list(labels),
    }


def run(run_id, path, sha, event="pull_request"):
    return {"id": run_id, "path": f".github/workflows/{path}",
            "head_sha": sha, "event": event}


def payload(runs, jobs):
    return {"runs": runs, "jobs": {str(k): v for k, v in jobs.items()}}


# One complete hosted job as the jobs API reports it, including GitHub's
# `Z` timestamps and a field the reconstructed dump is free to drop.
_API_RUN = {
    "id": 1,
    "path": ".github/workflows/ci-dev.yml",
    "head_sha": "aaaaaaaa",
    "event": "pull_request",
    "name": "CI",
}
_API_JOB = {
    "name": "dev: verify",
    "started_at": "2026-08-28T04:26:20Z",
    "completed_at": "2026-08-28T04:26:26Z",
    "steps": [{"name": "Set up job"}],
    "labels": ["ubuntu-latest"],
    "html_url": "https://example.invalid/job",
}


def _gh_script(mode):
    """A fake `gh` that logs argv and answers the runs listing.

    * ``truncated`` — jobs page with total_count 150 and 100 records
    * ``jobs-fail`` — runs succeed, jobs request exits 1
    * ``ok`` — one run, one complete job, raw API envelopes
    """
    run = json.dumps(_API_RUN)
    job = json.dumps(_API_JOB)
    return f"""#!/usr/bin/env python3
import json, sys
from pathlib import Path
log = Path(__file__).resolve().parent / "argv.log"
log.write_text((log.read_text() if log.exists() else "") + " ".join(sys.argv[1:]) + "\\n")
argv = " ".join(sys.argv[1:])
run = {run}
job = {job}
if "/jobs" in argv:
    if {mode!r} == "jobs-fail":
        print("HTTP 403: rate limited", file=sys.stderr)
        sys.exit(1)
    jobs = [dict(job, name=f"dev: job {{i}}") for i in range(100)] if {mode!r} == "truncated" else [job]
    body = {{"total_count": 150 if {mode!r} == "truncated" else 1, "jobs": jobs}}
    json.dump(body, sys.stdout)
    sys.exit(0)
body = {{"total_count": 1, "workflow_runs": [run]}}
json.dump([body] if "--slurp" in argv else body, sys.stdout)
"""


_GH_TRUNCATED_JOBS = _gh_script("truncated")
_GH_JOBS_FAIL = _gh_script("jobs-fail")
_GH_OK = _gh_script("ok")


class MinutesScript(unittest.TestCase):
    def replay(self, body, extra=(), raw=None):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False
        ) as handle:
            if raw is not None:
                handle.write(raw)
            else:
                json.dump(body, handle)
            path = handle.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        argv = [sys.executable, str(SCRIPT), "--input", path, *extra]
        return subprocess.run(argv, capture_output=True, text=True, check=False)

    def summary(self, body, extra=()):
        proc = self.replay(body, ("--json", *extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    # -- GitHub's rounding --------------------------------------------

    def test_fifty_nine_seconds_bills_one_minute(self):
        body = payload([run(1, "ci-dev.yml", "aaaaaaa")],
                       {1: [job("dev: verify", 59)]})
        summary = self.summary(body)
        self.assertEqual(summary["billed"], 1)
        self.assertEqual(summary["real"], 1.0)

    def test_sixty_seconds_bills_one_minute(self):
        # 59s bills 1 and 61s bills 2; `seconds // 60 + 1` agrees with
        # both and bills a 60-second job 2. ceil(60/60) is 1.
        body = payload([run(1, "ci-dev.yml", "aaaaaaa")],
                       {1: [job("dev: verify", 60)]})
        summary = self.summary(body)
        self.assertEqual(summary["billed"], 1)
        self.assertEqual(summary["real"], 1.0)

    def test_sixty_one_seconds_bills_two_minutes(self):
        body = payload([run(1, "ci-dev.yml", "aaaaaaa")],
                       {1: [job("dev: verify", 61)]})
        self.assertEqual(self.summary(body)["billed"], 2)

    def test_a_job_that_never_reached_a_runner_bills_nothing(self):
        body = payload([run(1, "ci-dev.yml", "aaaaaaa")],
                       {1: [job("dev: verify", 0, started=False)]})
        summary = self.summary(body)
        self.assertEqual(summary["billed"], 0)
        self.assertEqual(summary["never_started"], 1)
        self.assertEqual(summary["jobs"], 1)

    def test_a_self_hosted_job_is_real_work_and_no_bill(self):
        # GitHub meters hosted minutes only. The seconds are still
        # reported: the guard's number is the bill, the table is the work.
        body = payload([run(1, "ci-dev.yml", "aaaaaaa")],
                       {1: [job("dev: verify", 90, labels=("self-hosted", "Linux")),
                            job("dev: discover", 6)]})
        summary = self.summary(body)
        self.assertEqual(summary["billed"], 1)
        self.assertEqual(summary["self_hosted"], 1)
        self.assertEqual(summary["real"], 1.6)
        self.assertEqual(summary["families"]["dev: verify"]["billed"], 0)
        self.assertEqual(summary["families"]["dev: verify"]["real"], 1.5)

    def test_rounding_share_ignores_self_hosted_seconds(self):
        # 90s self-hosted + 6s hosted: billed 1, hosted real 0.1 min.
        # The share is "the bill that did no work" — hosted rounding —
        # so 1 - 0.1/1 = 0.9. Folding self-hosted seconds into `real`
        # makes it 1 - 1.6/1 = -0.6 and prints rounding -60%.
        body = payload([run(1, "ci-dev.yml", "aaaaaaa")],
                       {1: [job("dev: verify", 90, labels=("self-hosted", "Linux")),
                            job("dev: discover", 6)]})
        summary = self.summary(body)
        self.assertEqual(summary["billed"], 1)
        self.assertEqual(summary["rounding_share"], 0.9)
        self.assertGreaterEqual(summary["rounding_share"], 0)

    def test_self_hosted_is_recognised_wherever_it_sits_in_labels(self):
        # `runs-on: [Linux, self-hosted]` reports labels in that order.
        # A labels[0] test bills it. The hosted companion keeps billed
        # off zero so rounding_share is not in this case.
        body = payload([run(1, "ci-dev.yml", "aaaaaaa")],
                       {1: [job("dev: verify", 90, labels=("Linux", "self-hosted")),
                            job("dev: discover", 6)]})
        summary = self.summary(body)
        self.assertEqual(summary["billed"], 1)
        self.assertEqual(summary["self_hosted"], 1)
        self.assertEqual(summary["families"]["dev: verify"]["billed"], 0)

    def test_a_hosted_job_is_billed_whatever_else_its_labels_say(self):
        body = payload([run(1, "ci-dev.yml", "aaaaaaa")],
                       {1: [job("dev: verify", 6, labels=("ubuntu-latest", "x64"))]})
        self.assertEqual(self.summary(body)["billed"], 1)

    def test_rounding_share_is_the_bill_that_did_no_work(self):
        # 6s + 6s + 6s = 18s real, 3 billed minutes: 90% of the bill is
        # rounding, which is the incident in one number.
        body = payload([run(1, "ci-dev.yml", "aaaaaaa")],
                       {1: [job("dev: gates (lint)", 6),
                            job("dev: gates (imports)", 6),
                            job("dev: gates (secret-scan)", 6)]})
        summary = self.summary(body)
        self.assertEqual(summary["billed"], 3)
        self.assertEqual(summary["rounding_share"], 0.9)
        self.assertEqual(summary["families"]["dev: gates"]["jobs"], 3)

    # -- per push -----------------------------------------------------

    def test_two_runs_on_one_commit_are_one_push(self):
        body = payload(
            [run(1, "ci-dev.yml", "aaaaaaa"), run(2, "ci-dev-apps.yml", "aaaaaaa")],
            {1: [job("dev: verify", 6)], 2: [job("dev: workflow (0)", 90)]},
        )
        summary = self.summary(body)
        self.assertEqual(summary["runs"], 2)
        self.assertEqual(summary["pushes"], 1)
        self.assertEqual(summary["billed"], 3)
        self.assertEqual(summary["billed_per_push"], 3.0)
        self.assertEqual(summary["workflows"]["ci-dev.yml"]["billed_per_push"], 1.0)
        self.assertEqual(
            summary["workflows"]["ci-dev-apps.yml"]["billed_per_push"], 2.0
        )

    # -- fire, and stay quiet -----------------------------------------

    def _three_minutes(self):
        return payload([run(1, "ci-dev.yml", "aaaaaaa")],
                       {1: [job("dev: verify", 6), job("dev: discover", 6),
                            job("dev: gates (lint)", 6)]})

    def test_over_budget_fires(self):
        proc = self.replay(self._three_minutes(), ("--budget", "2"))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("budget 2 min: OVER (3 billed)", proc.stdout)

    def test_at_budget_stays_quiet(self):
        proc = self.replay(self._three_minutes(), ("--budget", "3"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("budget 3 min: within (3 billed)", proc.stdout)

    def test_no_budget_is_a_report_not_a_verdict(self):
        proc = self.replay(self._three_minutes())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("budget", proc.stdout)
        self.assertIn("| 3 |", proc.stdout)

    def test_a_negative_budget_is_a_usage_error(self):
        proc = self.replay(self._three_minutes(), ("--budget", "-1"))
        self.assertEqual(proc.returncode, 64)
        self.assertIn("expected", proc.stderr)
        self.assertIn("found -1", proc.stderr)

    # -- absent is not none -------------------------------------------

    def test_a_window_that_read_clean_and_empty_is_a_genuine_zero(self):
        proc = self.replay(payload([], {}), ("--budget", "0"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("| 0 | 0 | 0 | 0 | 0 | 0.0 | 0 |", proc.stdout)

    def assert_unreachable(self, proc):
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "", f"figures printed: {proc.stdout!r}")
        self.assertTrue(proc.stderr.startswith("UNREACHABLE:"), proc.stderr)

    def test_a_missing_input_is_unreachable_not_zero(self):
        argv = [sys.executable, str(SCRIPT), "--input", "/nonexistent/window.json",
                "--budget", "0"]
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
        self.assert_unreachable(proc)

    def test_a_body_that_is_not_json_is_unreachable(self):
        self.assert_unreachable(self.replay(None, ("--budget", "0"), raw="<html>"))

    def test_a_malformed_or_in_flight_job_is_unreachable_not_a_zero(self):
        # A job with steps and completed_at: null is this run measuring
        # itself; billing it 0 with no column is a figure the tool did
        # not establish. A jobs list of ["x"] is AttributeError today,
        # which Python exits as 1 — the over-budget verdict.
        inflight = job("dev: minutes", 6)
        inflight["completed_at"] = None
        cases = {
            "in-flight": payload(
                [run(1, "ci-minutes.yml", "aaaaaaa", event="schedule")],
                {1: [inflight]},
            ),
            "non-mapping": payload(
                [run(1, "ci-dev.yml", "aaaaaaa")],
                {1: ["x"]},
            ),
        }
        for label, body in cases.items():
            with self.subTest(label):
                self.assert_unreachable(self.replay(body))

    def test_a_payload_without_runs_is_unreachable(self):
        self.assert_unreachable(self.replay({"runs": "?", "jobs": {}}))

    def test_a_payload_that_omits_runs_is_unreachable(self):
        # The sibling supplies runs with the wrong type. `payload.get("runs", [])`
        # still refuses that, and prints a genuine-looking zero when the key
        # is absent. Absent is not none.
        self.assert_unreachable(self.replay({"jobs": {}}))

    def test_a_run_whose_jobs_were_not_fetched_is_unreachable(self):
        body = payload([run(1, "ci-dev.yml", "aaaaaaa")], {})
        self.assert_unreachable(self.replay(body))

    def test_an_api_that_answers_with_an_error_is_unreachable(self):
        raw = tempfile.mkdtemp(prefix="ci-min-")
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", raw], check=False))
        fake = Path(raw) / "gh"
        fake.write_text("#!/bin/sh\necho 'HTTP 403: rate limited' >&2\nexit 1\n")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        argv = [sys.executable, str(SCRIPT), "--gh", str(fake),
                "--repo", "o/r", "--days", "7", "--budget", "0"]
        proc = subprocess.run(
            argv, capture_output=True, text=True, check=False,
            env={**os.environ, "GH_TOKEN": "unused"},
        )
        self.assert_unreachable(proc)
        self.assertIn("rate limited", proc.stderr)

    def test_a_missing_gh_is_unreachable(self):
        argv = [sys.executable, str(SCRIPT), "--gh", "/nonexistent/gh",
                "--repo", "o/r", "--days", "1"]
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
        self.assert_unreachable(proc)

    def test_a_non_positive_window_is_a_usage_error(self):
        argv = [sys.executable, str(SCRIPT), "--repo", "o/r", "--days", "0"]
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 64)
        self.assertIn("found 0", proc.stderr)

    def install_gh(self, source):
        raw = tempfile.mkdtemp(prefix="ci-min-")
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", raw], check=False))
        fake = Path(raw) / "gh"
        fake.write_text(source)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        return Path(raw)

    def run_gh(self, root, extra=()):
        argv = [sys.executable, str(SCRIPT), "--gh", str(root / "gh"),
                "--repo", "o/r", "--days", "7", *extra]
        return subprocess.run(
            argv, capture_output=True, text=True, check=False,
            env={**os.environ, "GH_TOKEN": "unused"},
        )

    def test_the_created_filter_carries_a_timestamp_not_a_bare_date(self):
        """`--days 7` truncated to YYYY-MM-DD becomes 00:00 UTC on that
        date in GitHub's `created` filter, so a Monday 06:17 cron
        measures 7d 6h 17m and double-counts the overlap next week."""
        root = self.install_gh(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$(dirname \"$0\")/argv.log\"\n"
            "echo 'HTTP 403: rate limited' >&2\n"
            "exit 1\n"
        )
        proc = self.run_gh(root)
        log = root / "argv.log"
        self.assertTrue(log.exists(), proc.stderr)
        argv = unquote(log.read_text())
        # gh argv is `...&created=>=DATE` (query `created` = `>=DATE`).
        found = re.findall(r"created(?:=)?>=([^\s&\"']+)", argv)
        self.assertTrue(found, f"no created filter in argv: {argv!r}")
        since = found[0].rstrip("'\"")
        self.assertRegex(
            since,
            r"T\d{2}:",
            f"created filter is a bare date, not a timestamp: {since!r} "
            f"in {argv!r}",
        )

    def test_a_truncated_jobs_page_is_unreachable_not_a_partial_bill(self):
        """A run of 101 jobs contributes 100 when the jobs request is
        unpaginated, and summarize has no expected-count to notice.
        A total_count guard must refuse rather than print a total."""
        root = self.install_gh(_GH_TRUNCATED_JOBS)
        proc = self.run_gh(root)
        argv = (root / "argv.log").read_text() if (root / "argv.log").exists() else ""
        self.assertIn("/jobs", argv, f"jobs endpoint never called; argv={argv!r} stderr={proc.stderr!r}")
        self.assert_unreachable(proc)

    def test_a_failed_dump_is_unreachable_not_over_budget(self):
        """`--input` already maps OSError to UNREACHABLE. `--dump` of an
        unwritable path must not fall through to Python's exit 1, which
        is EXIT_OVER — a filesystem error is not a budget verdict."""
        root = self.install_gh(_GH_OK)
        proc = self.run_gh(root, extra=("--dump", "/nonexistent-ci-min/out.json"))
        argv = (root / "argv.log").read_text() if (root / "argv.log").exists() else ""
        self.assertIn("/jobs", argv, f"fetch never completed; argv={argv!r} stderr={proc.stderr!r}")
        self.assert_unreachable(proc)

    def test_a_jobs_request_that_fails_is_unreachable_not_a_zero(self):
        """A runs listing that reads and a jobs request that does not
        must not print a complete-looking zero for that run. The
        existing API-failure fake fails every call, so `one()` is never
        reached."""
        root = self.install_gh(_GH_JOBS_FAIL)
        proc = self.run_gh(root, extra=("--budget", "0"))
        argv = (root / "argv.log").read_text() if (root / "argv.log").exists() else ""
        self.assertIn("/jobs", argv, f"jobs endpoint never called; argv={argv!r} stderr={proc.stderr!r}")
        self.assert_unreachable(proc)
        self.assertIn("rate limited", proc.stderr)

    def test_dump_saves_fetched_bytes_and_input_replays_them(self):
        """`--dump` saves the fetched payload so a figure can be
        re-derived later from the bytes it was measured on.
        json.dump of a reconstructed {repo, since, runs, jobs} dict
        is not those bytes: the API envelope (`workflow_runs`) and
        the `Z` timestamps the jobs endpoint actually returns must
        survive, and `--input` of the dump must bill the same."""
        root = self.install_gh(_GH_OK)
        dump_dir = tempfile.mkdtemp(prefix="ci-min-dump-")
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", dump_dir], check=False))
        dump = Path(dump_dir) / "window.json"
        live = self.run_gh(root, extra=("--dump", str(dump), "--json"))
        self.assertEqual(live.returncode, 0, live.stderr)
        self.assertTrue(dump.is_file() and dump.stat().st_size > 0, dump)
        dumped = dump.read_bytes()
        self.assertIn(b"workflow_runs", dumped)
        self.assertIn(b"2026-08-28T04:26:20Z", dumped)
        replayed = subprocess.run(
            [sys.executable, str(SCRIPT), "--input", str(dump), "--json"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(replayed.returncode, 0, replayed.stderr)
        self.assertEqual(
            json.loads(live.stdout)["billed"],
            json.loads(replayed.stdout)["billed"],
        )


class Guard(unittest.TestCase):
    """The weekly workflow is bound to the tool, or the tool guards
    nothing."""

    def setUp(self):
        self.text = GUARD.read_text(encoding="utf-8")

    def test_it_runs_the_tool_with_a_budget(self):
        self.assertIn("python3 ops/devlane/workflow/checks/ci_minutes.py", self.text)
        self.assertRegex(self.text, r"--budget\s+\S+")
        self.assertIn('--days "$DAYS"', self.text)

    def test_it_is_scheduled_and_reports_no_pull_request_context(self):
        # A scheduled run is the guard; a pull_request trigger would add
        # a context ci_contexts.py does not derive, and a required check
        # that never reports blocks the pull request forever.
        self.assertIn("schedule:", self.text)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("pull_request", self.text.split("jobs:")[0].split("on:")[1])

    def test_it_reads_actions_and_nothing_more(self):
        permissions = self.text.split("permissions:")[1].split("\n\n")[0]
        self.assertIn("actions: read", permissions)
        self.assertIn("contents: read", permissions)
        self.assertNotIn("write", permissions)

    def test_the_tools_exit_reaches_the_runner(self):
        """GitHub's default Linux `run:` shell is `bash -e {0}`.
        `pipefail` is added only when the step sets `shell: bash`
        (`bash --noprofile --norc -eo pipefail {0}`). `tool | tee`
        then reports tee's zero, so over-budget (exit 1) and
        unreachable (exit 2) both land green and the guard cannot
        go red. Dropping the pipe, or selecting that shell, keeps
        the tool's exit."""
        self.assertIn("ci_minutes.py", self.text)
        # `run: |` is a YAML block scalar sitting *before* the
        # invocation; a shell pipe of the tool sits after it.
        piped = re.search(r"ci_minutes\.py[\s\S]{0,400}?(?<!\|)\|(?!\|)", self.text)
        if not piped:
            return
        start = max(0, self.text.index("ci_minutes.py") - 800)
        window = self.text[start:self.text.index("ci_minutes.py") + 400]
        selects_pipefail = (
            re.search(r"(?m)^\s*shell:\s+bash\s*$", window) is not None
            or "set -o pipefail" in window
            or "set -eo pipefail" in window
        )
        self.assertTrue(
            selects_pipefail,
            "the tool is piped, so the step must select a pipefail "
            "shell (`shell: bash`) or `set -o pipefail`; otherwise "
            "tee's zero swallows over-budget and unreachable",
        )


if __name__ == "__main__":
    unittest.main()
