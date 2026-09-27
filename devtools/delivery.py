"""Revision-bound review, acceptance and retained job turnover behind work outcomes."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .control import Control, binding, includes
from .github import GitHub
from .github_http import GitHubError
from .store import canonical, stamp
from .work import Work, record
from .workspaces import EDITORS, Workspaces, git

SCOPE_FIELDS = ("role", "work_order", "job", "reports_to", "revision", "paused")


def capabilities(spec):
    text = {"type": "string", "minLength": 1, "maxLength": 3000}
    return [
        spec(
            "review_record",
            "Record and publish your audit conclusion against the inspected revision; route findings automatically.",
            {"conclusion": {"type": "string", "enum": ["ready", "changes_requested", "comment"]}, "summary": text},
            ("conclusion", "summary"),
        ),
        spec(
            "review_respond",
            "Respond to the current job's review with explanation or evidence; retain and route it in the original context.",
            {"text": text, "review": {"type": "string", "pattern": "review:[1-9][0-9]*"}},
            ("text",),
        ),
    ]


def review_snapshot(store, member, workspace, *, refresh=False):
    """Called under the repository lock. Audit sees an immutable commit, never live dirty files."""
    with store.connect() as db:
        old = db.execute("SELECT * FROM review_views WHERE member=? AND job=?", (member, workspace["job"])).fetchone()
        job = record(db, "jobs", workspace["job"])
    if old and not refresh:
        return {
            **workspace,
            "root": old["root"],
            "base_revision": old["base_revision"],
            "review_revision": old["revision"],
        }
    base = workspace["base_revision"]
    revision = git(workspace["root"], "rev-parse", "HEAD").stdout.decode().strip()
    if job["pull_request"]:
        provider = GitHub(store, member)
        context = provider._context(job=job["id"])
        pr = provider._pr(context)
        revision, base = pr["head"]["sha"], pr["base"]["sha"]
        if pr["head"]["ref"] != workspace["branch"] or pr["base"]["ref"] != workspace["target"]:
            raise ValueError("The PR no longer matches its managed branch and target.")
        if git(workspace["root"], "cat-file", "-e", revision + "^{commit}", check=False).returncode:
            spaces = Workspaces(store, member)
            remote = spaces.config.get("remote", "origin")
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", remote):
                raise ValueError("Invalid configured Git remote.")
            git(spaces.checkout(), "fetch", "--no-tags", remote, workspace["branch"])
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Provider did not supply a commit revision.")
    root = Path(workspace["root"]).parent / f"review-{job['id']}-{member}-{revision}"
    if not root.exists():
        git(workspace["root"], "worktree", "add", "--detach", str(root), revision)
    view = {**workspace, "root": str(root), "base_revision": base, "review_revision": revision}
    Workspaces._verify(view, Workspaces(store, member).checkout())
    with store.connect() as db:
        db.execute(
            "INSERT INTO review_views(member,job,root,revision,base_revision) VALUES (?,?,?,?,?) ON CONFLICT(member,job) DO UPDATE SET root=excluded.root,revision=excluded.revision,base_revision=excluded.base_revision",
            (member, job["id"], str(root), revision, base),
        )
    return view


class Delivery:
    def __init__(self, store, member):
        self.store, self.member = store, member
        self.control = Control(store, member)
        self.spaces = Workspaces(store, member)
        self.github = GitHub(store, member)

    def scope(self, job=None, role=None):
        expected = self.control.current()
        with self.store.connect() as db:
            scope = binding(db, self.member)
            job = job if job is not None else scope["job"] if scope else None
            work = record(db, "jobs", job) if job else None
        if (
            not scope
            or not expected
            or not work
            or any(scope[k] != expected[k] for k in SCOPE_FIELDS)
            or not includes(scope, work["work_order"], job)
        ):
            raise ValueError("This outcome requires the current work binding.")
        if role is not None and scope["role"] not in role:
            raise ValueError("This role cannot perform that outcome.")
        return scope, work

    def inspect(self, job=None, path=None, offset=0, page=1):
        scope, work = self.scope(job)
        with self.spaces.lock("job-" + str(work["id"])):
            if scope["role"] == "audit":
                with self.spaces.lock("repository"):
                    workspace = self.spaces._ensure(scope)
                    view = review_snapshot(self.store, self.member, workspace, refresh=True)
            else:
                view = None
            if not work["pull_request"]:
                with self.store.connect() as db:
                    accepted = db.execute(
                        "SELECT outcome,assessment FROM deliveries WHERE job=?", (work["id"],)
                    ).fetchone()
                return {
                    "state": "not_submitted",
                    "review_revision": view["review_revision"] if view else None,
                    "message": "No PR is attached yet. Findings can be retained with work_report.",
                    "acceptance": dict(accepted) if accepted else None,
                }
            context = self.github._context(job=work["id"])
            result = self.github.pr_get(context)
            revision = result["pr"]["revision"]
            if view and view["review_revision"] != revision:
                raise ValueError("The PR changed while preparing its audit snapshot. Inspect again.")
            diff = self.github.pr_diff(context, revision=revision, path=path, offset=offset, page=page)
            with self.store.connect() as db:
                db.execute(
                    "INSERT INTO inspections(member,job,revision,updated) VALUES (?,?,?,?) ON CONFLICT(member,job) DO UPDATE SET revision=excluded.revision,updated=excluded.updated",
                    (self.member, work["id"], revision, stamp()),
                )
                reviews = [
                    self.review_row(r)
                    for r in db.execute("SELECT * FROM reviews WHERE job=? ORDER BY id DESC LIMIT 10", (work["id"],))
                ]
                accepted = db.execute(
                    "SELECT outcome,assessment,revision,merge_commit FROM deliveries WHERE job=?", (work["id"],)
                ).fetchone()
            return {
                "pr": result["pr"],
                "ci": result["ci"],
                "observed_blockers": result["observed_blockers"],
                "provider_reviews": result["reviews"],
                "reviews": reviews,
                "changes": diff,
                "source": "immutable audit snapshot" if view else "current producer workspace",
                "acceptance": dict(accepted) if accepted else None,
            }

    @staticmethod
    def review_row(row):
        return {
            "reference": "review:" + str(row["id"]),
            **{k: row[k] for k in ("revision", "conclusion", "summary", "state", "remote_url")},
        }

    def inspected(self, job):
        with self.store.connect() as db:
            row = db.execute("SELECT revision FROM inspections WHERE member=? AND job=?", (self.member, job)).fetchone()
        if not row:
            raise ValueError("Inspect the current review packet before reviewing or accepting it.")
        return row["revision"]

    def review(self, conclusion, summary):
        scope, work = self.scope(role={"audit"})
        if scope["paused"]:
            raise ValueError("Work is paused.")
        with self.spaces.use():
            return self._publish(work, self.inspected(work["id"]), conclusion, summary)

    def respond(self, text, review=None):
        scope, work = self.scope(role=EDITORS)
        if scope["paused"]:
            raise ValueError("Work is paused.")
        with self.spaces.use():
            with self.store.connect() as db:
                row = db.execute(
                    "SELECT * FROM reviews WHERE job=? AND conclusion!='response'"
                    + (" AND id=?" if review else "")
                    + " ORDER BY id DESC LIMIT 1",
                    (work["id"], *((int(review.split(":")[1]),) if review else ())),
                ).fetchone()
            if not row:
                raise ValueError("No matching review belongs to this job.")
            context = self.github._context(job=work["id"])
            revision = self.github._pr(context)["head"]["sha"]
            return self._publish(work, revision, "response", text, row["id"])

    def _publish(self, work, revision, conclusion, summary, response_to=None):
        context = self.github._context(job=work["id"])
        pr = self.github._pr(context)
        self.github._revision(pr, revision)
        key = hashlib.sha256(
            canonical([self.member, work["id"], revision, conclusion, summary, response_to]).encode()
        ).hexdigest()
        marker = "<!-- agentscient-review:" + key + " -->"
        body = (
            f"{conclusion.replace('_', ' ').title()} at `{revision}`\n\n{summary}\n\n"
            + (f"Response to review:{response_to}\n\n" if response_to else "")
            + marker
        )
        with self.store.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO reviews(job,actor,revision,conclusion,summary,response_to,request_key,state,created,updated) VALUES (?,?,?,?,?,?,?,'pending',?,?)",
                (work["id"], self.member, revision, conclusion, summary, response_to, key, stamp(), stamp()),
            )
            row = db.execute("SELECT * FROM reviews WHERE request_key=?", (key,)).fetchone()
        if row["state"] != "published":
            endpoint = context["root"] + f"/pulls/{context['pr']}/reviews"
            existing = next((r for r in self.github._all(endpoint) if marker in (r.get("body") or "")), None)
            if existing:
                url = existing["html_url"]
            elif row["state"] == "uncertain":
                raise ValueError(
                    "The prior review publication is uncertain and has not appeared on GitHub. Request guidance before repeating it."
                )
            else:
                scope, _ = self.scope(work["id"], role=EDITORS if response_to else {"audit"})
                if scope["paused"]:
                    raise ValueError("Work is paused.")
                with self.store.connect() as db:
                    db.execute("UPDATE reviews SET state='uncertain',updated=? WHERE id=?", (stamp(), row["id"]))
                # Shared harnesses may use the PR author's account. Audit conclusions are
                # comments, not a fabricated GitHub approval or repository-rule bypass.
                try:
                    published = self.github.pr_review(context, revision=revision, decision="comment", body=body)
                except GitHubError as error:
                    if error.status in {400, 401, 403, 404, 422, 429}:
                        # An explicit rejection made no review. Connectivity failures
                        # keep their uncertain state until remote evidence reconciles it.
                        with self.store.connect() as db:
                            db.execute("UPDATE reviews SET state='pending' WHERE id=?", (row["id"],))
                    raise
                url = published["url"]
            with self.store.connect() as db:
                db.execute(
                    "UPDATE reviews SET state='published',remote_url=?,updated=? WHERE id=?", (url, stamp(), row["id"])
                )
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM reviews WHERE request_key=?", (key,)).fetchone()
            receipt = self.review_row(row)
            message = canonical(receipt)
            recipients = {
                r["member"] for r in db.execute("SELECT member FROM member_bindings WHERE job=?", (work["id"],))
            } - {self.member}
            scope = self.control.current()
            recipients.add(scope["reports_to"])
            for recipient in recipients - {None}:
                target = binding(db, recipient)
                if includes(target, work["work_order"], work["id"]):
                    self.store._send(
                        db,
                        self.member,
                        recipient,
                        message,
                        key="review:" + key + ":" + recipient,
                        work_order=work["work_order"],
                        job=work["id"],
                    )
        self.control.report("Review " + conclusion + ": " + summary + "\n" + str(receipt["remote_url"]), kind="finding")
        return receipt

    def finish_job(self, job, assessment, *, cancel=False):
        scope, work = self.scope(job, role={"xo"})
        if scope["paused"]:
            raise ValueError("Work is paused.")
        with self.spaces.lock("job-" + str(job)):
            with self.store.connect() as db:
                old = db.execute("SELECT * FROM deliveries WHERE job=?", (job,)).fetchone()
                if old:
                    return {
                        "work": work["title"],
                        "outcome": old["outcome"],
                        "assessment": old["assessment"],
                        "retained": True,
                    }
                active = db.execute(
                    "SELECT 1 FROM operations WHERE job=? AND state IN ('queued','running')", (job,)
                ).fetchone()
                workspace = db.execute("SELECT * FROM job_workspaces WHERE job=?", (job,)).fetchone()
                report = db.execute("SELECT 1 FROM work_updates WHERE job=? AND kind='result'", (job,)).fetchone()
            if active:
                raise ValueError("A development operation is still active. Its result will be delivered automatically.")
            revision, merge_commit = None, None
            if not cancel and work["pull_request"]:
                revision = self.inspected(job)
                context = self.github._context(job=job)
                current = self.github.pr_get(context)
                if current["pr"]["revision"] != revision:
                    raise ValueError(
                        "The PR changed after inspection. Monitor this responsibility again before accepting it."
                    )
                if not workspace:
                    raise ValueError("This code job has no managed workspace to verify.")
                workspace = dict(workspace)
                if current["pr"]["branch"] != workspace["branch"] or current["pr"]["base"] != workspace["target"]:
                    raise ValueError("The PR no longer matches this job's managed branch and target.")
                self.spaces._verify(workspace, self.spaces.checkout())
                if (
                    self.spaces.changes(workspace["root"])
                    or git(workspace["root"], "rev-parse", "HEAD").stdout.decode().strip() != revision
                ):
                    raise ValueError(
                        "The producer has unsubmitted changes. Preserve and submit them before acceptance."
                    )
                if current["pr"]["state"] != "merged" and current["ci"]["state"] != "passed":
                    raise ValueError("CI has not passed for the current PR revision.")
                self.scope(job, role={"xo"})
                merged = self.github.pr_merge(context, revision=revision)
                if not merged["merged"]:
                    return {"work": work["title"], "outcome": "not_merged", "provider": merged}
                merge_commit = merged["commit"]
            elif not cancel:
                if workspace and (
                    self.spaces.changes(workspace["root"])
                    or git(workspace["root"], "rev-parse", "HEAD").stdout.decode().strip() != workspace["base_revision"]
                ):
                    raise ValueError("This job has code changes that must be submitted through its PR.")
                if not report:
                    raise ValueError("A non-code job needs a retained result report before acceptance.")
            outcome = "cancelled" if cancel else "done"
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                current = binding(db, self.member)
                if not current or any(current[k] != scope[k] for k in SCOPE_FIELDS):
                    raise ValueError("Command scope changed. Inspect the provider result before retrying finalization.")
                Work(self.store, self.member).update_in(
                    db, "jobs", scope["work_order"], job, status=outcome, next_action="", blocker=""
                )
                db.execute(
                    "INSERT INTO deliveries(job,accepted_by,revision,merge_commit,assessment,outcome,created) VALUES (?,?,?,?,?,?,?)",
                    (job, self.member, revision, merge_commit, assessment, outcome, stamp()),
                )
                members = [r["member"] for r in db.execute("SELECT member FROM member_bindings WHERE job=?", (job,))]
                for member in members:
                    self.release(db, member)
                self.store._event(
                    db,
                    self.member,
                    "job_finished",
                    {
                        "job": job,
                        "work_order": scope["work_order"],
                        "outcome": outcome,
                        "assessment": assessment,
                        "revision": revision,
                        "merge_commit": merge_commit,
                    },
                )
            return {
                "work": work["title"],
                "outcome": outcome,
                "assessment": assessment,
                "retained": True,
                "sessions": "stop requested; slots become reusable after shutdown",
                "pr": work["pull_request"] or None,
            }

    @staticmethod
    def release(db, member):
        db.execute(
            "UPDATE members SET desired='stopped',selected_work_order=NULL,selected_job=NULL WHERE name=?", (member,)
        )
        db.execute("DELETE FROM member_bindings WHERE member=?", (member,))
