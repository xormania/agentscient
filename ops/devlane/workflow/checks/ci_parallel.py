"""Partition the complete dev plan and reject incomplete native job evidence."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from ops.devlane.workflow.checks import lane

JOBS = tuple(f"lane-{index}" for index in range(4))


def partition(checks, *, root):
    result = {name: [] for name in JOBS}
    costs = dict.fromkeys(JOBS, 0)
    for check in sorted(checks, key=lambda check: (-lane.check_cost(check, root), check.name)):
        name = min(JOBS, key=lambda name: (costs[name], name))
        result[name].append(check)
        costs[name] += lane.check_cost(check, root)
    return result


def validate(parts, receipts, jobs, context):
    if set(jobs) != set(JOBS) or any(job.get("result") != "success" for job in jobs.values()):
        raise ValueError("ci: required dev jobs are missing or unsuccessful")
    if len(receipts) != len(JOBS) or {r.get("kind") for r in receipts} != set(JOBS):
        raise ValueError("ci: expected one receipt per dev job")
    count = 0
    for receipt in receipts:
        for key in ("repository", "run_id", "event_revision"):
            if receipt.get(key) != context[key]:
                raise ValueError(f"ci: receipt has wrong {key}")
        attempt = receipt.get("attempt")
        if type(attempt) is not int or not 1 <= attempt <= context["attempt"]:
            raise ValueError("ci: invalid receipt attempt")
        if receipt.get("inputs", {}).get("runner_environment", {}).get("requested_mode") != context["mode"]:
            raise ValueError("ci: receipt has wrong runner mode")
        expected = sorted(check.name for check in parts[receipt["kind"]])
        rows = receipt.get("results", [])
        if (type(receipt.get("exit")) is not int or receipt["exit"] != 0
                or receipt.get("plan") != expected
                or sorted(row.get("name", "") for row in rows) != expected
                or any(type(row.get("exit")) is not int or row["exit"] != 0
                       or row.get("mode") not in ("executed", "reused") for row in rows)):
            raise ValueError("ci: missing, duplicate or unsuccessful required check")
        count += len(rows)
    return count


def elapsed_seconds(jobs, now):
    starts = [datetime.fromisoformat(job["started_at"]) for job in jobs]
    if not starts:
        raise ValueError("ci: missing native job start times")
    elapsed = (now - min(starts)).total_seconds()
    if not 0 <= elapsed <= 240:
        raise ValueError(f"ci: complete dev verification exceeded four minutes ({elapsed:.1f}s)")
    return elapsed


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        if len(args) != 1:
            raise ValueError("ci: expected the downloaded evidence directory")
        receipts = [json.loads(path.read_text()) for path in Path(args[0]).rglob("receipt.json")]
        context = {"repository": os.environ["GITHUB_REPOSITORY"], "run_id": int(os.environ["GITHUB_RUN_ID"]),
                   "event_revision": os.environ["GITHUB_SHA"], "mode": os.environ["CI_RUNNER_MODE"],
                   "attempt": int(os.environ["GITHUB_RUN_ATTEMPT"])}
        count = validate(partition(lane.plan(lane.ROOT), root=lane.ROOT), receipts,
                         json.loads(os.environ["CI_JOB_RESULTS"]), context)
        # Native start times include checkout/setup and the gap before aggregation.
        # Read only this attempt so an older successful job retained by a partial
        # rerun does not count as execution time in the new attempt.
        from ops.devlane.workflow.checks.ci import GitHub
        api = GitHub(context["repository"], os.environ["GITHUB_TOKEN"])
        payload = api.get(f"/actions/runs/{context['run_id']}/attempts/{context['attempt']}/jobs?per_page=100")
        if len(payload["jobs"]) != payload["total_count"]:
            raise ValueError("ci: incomplete native duration evidence")
        elapsed = elapsed_seconds(payload["jobs"], datetime.now(timezone.utc))
        print(f"FULL DEV LANE: PASS ({count} checks across {len(JOBS)} jobs; {elapsed:.1f}s including setup). Application CI is separate.")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
