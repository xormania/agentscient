"""Owned worktrees and serialized Git operations; no agent-supplied commands."""

from __future__ import annotations

import fcntl
import hashlib
import io
import json
import os
import re
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from .artifacts import Artifacts
from .control import Control, binding
from .store import UNSET, stamp
from .work import Work, record

EDITORS = {"coder", "docs", "test_writer", "architect"}
DEFAULT_PATHS = {
    "coder": [
        "src/",
        "config/",
        "packages/",
        "tests/",
        "templates/",
        "assets/",
        "translations/",
        "public/",
        "migrations/",
        "composer.json",
        "composer.lock",
        "symfony.lock",
        "phpunit.dist.xml",
    ],
    "test_writer": ["tests/", "phpunit.dist.xml"],
    "docs": ["docs/", "README.md"],
    "architect": ["docs/"],
}


def project_config(store):
    path = store.directory / "team.json"
    return json.loads(path.read_text()).get("project", {}) if path.is_file() else {}


def git(root, *args, check=True, timeout=60, env=None):
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment.update(GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat", GIT_LITERAL_PATHSPECS="1", LC_ALL="C", **(env or {}))
    result = subprocess.run(
        ["git", "-C", str(root), "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args],
        capture_output=True,
        timeout=timeout,
        env=environment,
    )
    if len(result.stdout) > 16 * 1024 * 1024:
        raise ValueError("Git output exceeds the managed operation limit; narrow the requested inspection.")
    if check and result.returncode:
        # Remote credential-bearing URLs and environment contents are not returned to agents.
        from .github_http import GitHubHTTP

        error = GitHubHTTP().clean(result.stderr.decode(errors="replace"))
        error = re.sub(r"https?://[^\s/@]+:[^\s/@]+@", "https://[REDACTED]@", error)
        raise ValueError("Git operation failed: " + error[-1500:])
    return result


class Workspaces:
    def __init__(self, store, member):
        self.store, self.member = store, member
        self.control = Control(store, member)
        self.config = project_config(store)

    def scope(self, write=False):
        self.config = project_config(self.store)
        expected = self.control.current()
        with self.store.connect() as db:
            current = binding(db, self.member)
        if (
            not current
            or (not current["job"] and current["role"] not in {"co", "xo", "nco"})
            or not expected
            or any(current[k] != expected[k] for k in ("role", "job", "work_order", "revision", "paused", "reports_to"))
        ):
            raise ValueError("This capability needs your current work binding; it may have changed or been paused.")
        writable = current["role"] in EDITORS if current["job"] else current["role"] == "xo"
        if write and (not writable or current["paused"]):
            raise ValueError("Your current role cannot change this work, or the work is paused.")
        if write:
            with self.store.connect() as db:
                table, ident = ("jobs", current["job"]) if current["job"] else ("work_orders", current["work_order"])
                if record(db, table, ident)["status"] in {"done", "cancelled"}:
                    raise ValueError("This work is finished; new changes belong to a new responsibility.")
        return current

    @contextmanager
    def lock(self, name, timeout=0):
        directory = self.store.directory / "work-locks"
        directory.mkdir(mode=0o700, exist_ok=True)
        with (directory / (str(name) + ".lock")).open("a") as stream:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise ValueError(
                            "Another operation is using this work. Inspect progress before retrying."
                        ) from None
                    time.sleep(0.01)
            yield

    def checkout(self):
        if not self.config.get("checkout"):
            raise ValueError("The operator must configure project.checkout before local development can start.")
        root = Path(self.config["checkout"]).expanduser().resolve(strict=True)
        actual = git(root, "rev-parse", "--show-toplevel").stdout.decode().strip()
        if Path(actual).resolve() != root:
            raise ValueError("project.checkout must be the repository root.")
        return root

    def target(self):
        target = self.config.get("target", "dev")
        git(self.checkout(), "check-ref-format", "--branch", target)
        if target.startswith("-"):
            raise ValueError("Invalid configured target branch.")
        return target

    def remote(self):
        remote = self.config.get("remote", "origin")
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", remote):
            raise ValueError("Invalid configured Git remote.")
        return remote

    def upstream(self, target):
        checkout, remote = self.checkout(), self.remote()
        ref = target
        if self.config.get("fetch", True) and git(checkout, "remote", "get-url", remote, check=False).returncode == 0:
            ref = "refs/remotes/" + remote + "/" + target
            git(checkout, "fetch", "--no-tags", remote, target + ":" + ref)
        return git(checkout, "rev-parse", "--verify", ref + "^{commit}").stdout.decode().strip()

    def parent(self):
        checkout = self.checkout()
        parent = Path(self.config.get("workspaces", checkout.parent / "wt-ag")).expanduser().resolve()
        if (
            parent == checkout
            or parent.is_relative_to(checkout)
            or parent == self.store.directory
            or parent.is_relative_to(self.store.directory)
        ):
            raise ValueError("Managed workspaces must be outside the source checkout and private control-plane state.")
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        return parent

    def team(self):
        return hashlib.sha256(str(self.store.directory).encode()).hexdigest()[:10]

    @staticmethod
    def scope_lock(scope):
        return "job-" + str(scope["job"]) if scope["job"] else "order-" + str(scope["work_order"])

    def ensure(self):
        scope = self.scope()
        with self.lock("repository"):
            workspace = self._ensure(scope)
            if scope["role"] == "audit":
                from .delivery import review_snapshot

                workspace = review_snapshot(self.store, self.member, workspace)
            return workspace

    def _ensure(self, scope):
        from .orders import Orders
        from .retirement import register

        if not scope["job"]:
            return Orders(self.store, self.member).ensure_in(scope["work_order"])
        checkout = self.checkout()
        with self.store.connect() as db:
            old = db.execute("SELECT * FROM job_workspaces WHERE job=?", (scope["job"],)).fetchone()
            job = record(db, "jobs", scope["job"])
        if old:
            self._verify(dict(old), checkout)
            return dict(old)
        order = Orders(self.store, self.member).ensure_in(scope["work_order"])
        target = order["branch"]
        base = self.upstream(target)
        team, parent = self.team(), self.parent()
        generation = hashlib.sha256(job["created"].encode()).hexdigest()[:8]
        root = parent / f"job-{team}-{scope['job']}-{generation}"
        # Job refs are siblings: Git cannot hold both <order> and <order>/<job>.
        # The work-order ruleset excludes the -job-* suffix so fixes can be pushed.
        branch = f"{target}-job-{scope['job']}-{generation}"
        if not root.exists():
            existing = git(checkout, "show-ref", "--verify", "refs/heads/" + branch, check=False)
            if existing.returncode == 0:
                git(checkout, "worktree", "add", str(root), branch)
            else:
                git(checkout, "worktree", "add", "-b", branch, str(root), base)
        workspace = dict(job=scope["job"], root=str(root), branch=branch, target=target, base_revision=base)
        self._verify(workspace, checkout)
        repository = self.config.get("repository", "")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT OR IGNORE INTO job_workspaces(job,root,branch,target,base_revision) VALUES (?,?,?,?,?)",
                (scope["job"], str(root), branch, target, base),
            )
            Work(self.store, self.member).update_in(
                db, "jobs", scope["work_order"], scope["job"], repository=repository, branch=branch
            )
            Work(self.store, self.member).attach(db, scope["work_order"], scope["job"], "worktree", str(root))
            register(db, workspace, scope["work_order"])
        return workspace

    @staticmethod
    def _verify(workspace, checkout):
        root = Path(workspace["root"])
        if root.is_symlink() or root.resolve() != root:
            raise ValueError("Managed workspace path was replaced.")

        def common(path):
            return Path(
                git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.decode().strip()
            ).resolve()

        if common(root) != common(checkout):
            raise ValueError("Managed workspace no longer belongs to its configured repository.")
        if workspace.get("review_revision"):
            if git(root, "rev-parse", "HEAD").stdout.decode().strip() != workspace["review_revision"]:
                raise ValueError("Audit snapshot revision changed outside the control plane.")
            if git(root, "diff", "--quiet", "HEAD", check=False).returncode:
                raise ValueError(
                    "Audit snapshot has modified tracked source. Preserve the evidence and request guidance."
                )
            return
        branch = git(root, "symbolic-ref", "--short", "HEAD").stdout.decode().strip()
        if branch != workspace["branch"]:
            raise ValueError("Managed workspace changed branch outside the control plane.")

    def paths(self, role, assignment=None):
        from .assignments import covers, current, policy, valid_path

        self.config = project_config(self.store)
        allowed = self.config.get("paths", {}).get(role, DEFAULT_PATHS.get(role, [])) if role in EDITORS else []
        if not isinstance(allowed, list) or any(not isinstance(p, str) or not valid_path(p) for p in allowed):
            raise ValueError("Configure relative editable role paths.")
        rules = policy(self.store, self.config)
        assignment = current(self.store, self.control.current()) if assignment is None else assignment
        requested = assignment.get("editable_paths", allowed)
        if role not in EDITORS:
            return []
        return [path for path in requested if any(covers(parent, path) for parent in allowed)
                and not any(covers(parent, path) for parent in rules["protected_paths"])]

    def permitted_path(self, path, role, assignment=None):
        from .assignments import covers, policy, valid_path

        if not valid_path(path):
            return False
        rules = policy(self.store, project_config(self.store))
        return not any(covers(parent, path) for parent in rules["protected_paths"]) and any(
            covers(allowed, path) for allowed in self.paths(role, assignment))

    @staticmethod
    def changes(root):
        pieces = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout.decode().split("\0")
        result, index = [], 0
        while index < len(pieces) and pieces[index]:
            row = pieces[index]
            item = {"status": row[:2], "path": row[3:]}
            if "R" in row[:2] or "C" in row[:2]:
                index += 1
                item["previous_path"] = pieces[index]
            result.append(item)
            index += 1
        return result

    @staticmethod
    def index_entries(root):
        entries = {}
        for entry in git(root, "ls-files", "--stage", "-z").stdout.decode().split("\0"):
            if entry:
                metadata, path = entry.split("\t", 1)
                entries.setdefault(path, []).append(metadata)
        return entries

    def _allowed_changes(self, workspace, scope, imported=None):
        changes = self.changes(workspace["root"])
        entries = self.index_entries(workspace["root"]) if imported is not None else {}

        def allowed(item, path):
            if self.permitted_path(path, scope["role"]):
                return True
            # Clean upstream changes outside the editor's scope can be committed only
            # unchanged from the recorded merge index. Conflict resolution stays scoped.
            return (
                imported is not None
                and item["status"][1] == " "
                and entries.get(path) == imported.get(path)
                and all(entry.endswith(" 0") for entry in imported.get(path, []))
            )

        denied = [
            path
            for item in changes
            for path in (item["path"], item.get("previous_path"))
            if path and not allowed(item, path)
        ]
        if denied:
            raise ValueError(
                "Changes outside this role's configured paths: "
                + ", ".join(denied[:10])
                + ". They were preserved; request guidance."
            )
        return changes

    @contextmanager
    def use(self, write=False):
        scope = self.scope(write)
        workspace = self.ensure()
        with self.lock(self.scope_lock(scope)):
            self.scope(write)
            self._verify(workspace, self.checkout())
            yield scope, workspace

    def inspect(self, section="overview", path=None, offset=0):
        with self.use() as (scope, workspace):
            root = workspace["root"]
            head = git(root, "rev-parse", "HEAD").stdout.decode().strip()
            if section == "changes":
                args = ["diff", "--no-ext-diff", "--no-textconv", workspace["base_revision"]]
                if path:
                    if Path(path).is_absolute() or ".." in Path(path).parts or ".git" in Path(path).parts:
                        raise ValueError("Inspect a relative project path.")
                    args += ["--", path]
                else:
                    args += ["--stat"]
                patch = git(root, *args).stdout.decode(errors="replace")
                return {
                    "revision": head,
                    "changes": patch[offset : offset + 10000],
                    "next_offset": offset + 10000 if len(patch) > offset + 10000 else None,
                    "uncommitted": self.changes(root)[:20],
                }
            with self.store.connect() as db:
                history = [
                    dict(row)
                    for row in db.execute(
                        "SELECT revision,note,created FROM checkpoints WHERE job=? ORDER BY id DESC LIMIT 10",
                        (scope["job"],),
                    )
                ]
            return {
                "revision": head,
                "changes": self.changes(root)[:20],
                "checkpoints": [{"reference": "checkpoint:" + row.pop("revision"), **row} for row in history],
                "editable_paths": self.paths(scope["role"]),
                "workspace": "prepared",
            }

    def _save(self, scope, workspace, note):
        self.scope(write=True)
        root = workspace["root"]
        merging = git(root, "rev-parse", "--verify", "MERGE_HEAD", check=False)
        imported = None
        if merging.returncode == 0:
            with self.store.connect() as db:
                pending = db.execute("SELECT * FROM workspace_merges WHERE job=?", (scope["job"],)).fetchone()
            if (
                not pending
                or pending["revision"] != merging.stdout.decode().strip()
                or pending["head"] != git(root, "rev-parse", "HEAD").stdout.decode().strip()
            ):
                raise ValueError("An unrecognized integration is in progress. Work was preserved; request guidance.")
            imported = json.loads(pending["entries"])
            if git(root, "diff", "--check", check=False).returncode:
                raise ValueError("Resolve conflict markers and whitespace errors before saving this integration.")
        changes = self._allowed_changes(workspace, scope, imported)
        if changes or imported is not None:
            git(root, "add", "--all", "--", ".")
            if imported is not None and git(root, "diff", "--cached", "--check", check=False).returncode:
                raise ValueError("Resolve conflict markers and whitespace errors before saving this integration.")
            identity = self.config.get("identity", {})
            env = (
                {
                    "GIT_AUTHOR_NAME": identity["name"],
                    "GIT_COMMITTER_NAME": identity["name"],
                    "GIT_AUTHOR_EMAIL": identity["email"],
                    "GIT_COMMITTER_EMAIL": identity["email"],
                }
                if identity
                else None
            )
            git(root, "-c", "commit.gpgsign=false", "commit", "--no-verify", "-m", note, env=env)
        revision = git(root, "rev-parse", "HEAD").stdout.decode().strip()
        with self.store.connect() as db:
            db.execute("DELETE FROM workspace_merges WHERE job=?", (scope["job"],))
            db.execute(
                "INSERT OR IGNORE INTO checkpoints(job,revision,note,created) VALUES (?,?,?,?)",
                (scope["job"], revision, note, stamp()),
            )
        diff = git(root, "diff", "--no-ext-diff", "--no-textconv", workspace["base_revision"], revision).stdout
        saved = Artifacts(self.store, self.member).ingest(
            "changes-" + revision[:12] + ".diff",
            io.BytesIO(diff),
            "text/plain",
            work_order=scope["work_order"],
            job=scope["job"],
        )["artifact"]["id"]
        return {
            "checkpoint": "checkpoint:" + revision,
            "changed": bool(changes) or imported is not None,
            "evidence": "artifact:" + str(saved),
        }

    def save(self, note):
        with self.use(write=True) as (scope, workspace):
            return self._save(scope, workspace, note)

    def refresh(self):
        with self.use(write=True) as (scope, workspace):
            if not scope["job"]:
                from .orders import Orders

                return Orders(self.store, self.member).sync(workspace)
            preserved = self._save(scope, workspace, "Preserve work before incorporating upstream changes")
            with self.lock("repository"):
                targets = list(dict.fromkeys([workspace["target"], self.target()]))
                revisions = [self.upstream(target) for target in targets]
            identity = self.config.get("identity", {})
            env = (
                {
                    "GIT_AUTHOR_NAME": identity["name"],
                    "GIT_COMMITTER_NAME": identity["name"],
                    "GIT_AUTHOR_EMAIL": identity["email"],
                    "GIT_COMMITTER_EMAIL": identity["email"],
                }
                if identity
                else None
            )
            for revision in revisions:
                result = git(
                    workspace["root"],
                    "-c",
                    "commit.gpgsign=false",
                    "merge",
                    "--no-edit",
                    revision,
                    check=False,
                    env=env,
                )
                if result.returncode:
                    conflicts = (
                        git(workspace["root"], "diff", "--name-only", "--diff-filter=U").stdout.decode().splitlines()
                    )
                    if conflicts:
                        with self.store.connect() as db:
                            db.execute(
                                "INSERT OR REPLACE INTO workspace_merges(job,head,revision,entries) VALUES (?,?,?,?)",
                                (
                                    scope["job"],
                                    git(workspace["root"], "rev-parse", "HEAD").stdout.decode().strip(),
                                    revision,
                                    json.dumps(self.index_entries(workspace["root"])),
                                ),
                            )
                    else:
                        git(workspace["root"], "merge", "--abort", check=False)
                    return {
                        "state": "needs_resolution" if conflicts else "needs_guidance",
                        "conflicts": conflicts[:20],
                        "preserved": preserved,
                        "message": (
                            "Your checkpoint is preserved. Resolve the listed files with your editing tools, "
                            "then work_save and work_refresh. Request guidance for paths outside your role."
                            if conflicts
                            else "Upstream could not be incorporated automatically. Your checkpoint is preserved."
                        ),
                    }
            with self.store.connect() as db:
                db.execute("UPDATE job_workspaces SET base_revision=? WHERE job=?", (revisions[0], scope["job"]))
            return {
                "state": "refreshed",
                "preserved": preserved,
                "revision": git(workspace["root"], "rev-parse", "HEAD").stdout.decode().strip(),
            }

    def recover(self, checkpoint, reason):
        revision = checkpoint.removeprefix("checkpoint:")
        with self.use(write=True) as (scope, workspace):
            with self.store.connect() as db:
                known = db.execute(
                    "SELECT 1 FROM checkpoints WHERE job=? AND revision=?", (scope["job"], revision)
                ).fetchone()
            if not known:
                raise ValueError("Choose a checkpoint from this job's history.")
            preserved = self._save(scope, workspace, "Preserve work before recovery: " + reason)
            git(workspace["root"], "restore", "--source=" + revision, "--staged", "--worktree", "--", ".")
            restored = self._save(scope, workspace, "Recover checkpoint: " + reason)
            return {"restored": restored, "preserved": preserved}

    def submit(self, summary):
        from .github import GitHub

        with self.use(write=True) as (scope, workspace):
            if not scope["job"]:
                from .orders import Orders

                return Orders(self.store, self.member).submit(scope, workspace, summary)
            github, context = None, None
            with self.store.connect() as db:
                attached = record(db, "jobs", scope["job"])["pull_request"]
            if attached:
                github = GitHub(self.store, self.member)
                context = github._context(job=scope["job"])
                current = github._pr(context)
                if current["head"]["ref"] != workspace["branch"] or current["base"]["ref"] != workspace["target"]:
                    raise ValueError("The PR no longer matches this job's managed branch and target.")
                if current.get("merged") or current["state"] == "closed":
                    raise ValueError(
                        "This job's PR is already closed. Ask XO to accept it or create new work; local changes were preserved."
                    )
            saved = self._save(scope, workspace, summary)
            revision = saved["checkpoint"].split(":", 1)[1]
            from .development import Development, configured

            validation = None
            if configured(self.store):
                validation = Development(self.store, self.member).checks(workspace["root"])
                if not validation["passed"] or validation["uncommitted"]:
                    return {
                        "state": "needs_attention",
                        "checkpoint": saved["checkpoint"],
                        "validation": validation,
                        "message": "Validation failed or changed files. Inspect the evidence before submitting again.",
                    }
            remote = self.config.get("remote", "origin")
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", remote):
                raise ValueError("Invalid configured Git remote.")
            self.scope(write=True)
            if github is None:
                github = GitHub(self.store, self.member)
                context = github._context(job=scope["job"])
            git(workspace["root"], "push", remote, "HEAD:refs/heads/" + workspace["branch"])
            opened = github.pr_open(
                context, base=workspace["target"], summary=summary + "\n\nEvidence: " + saved["evidence"], draft=False
            )
            if opened["pr"]["revision"] != revision:
                raise ValueError("Published PR does not match this checkpoint; inspect the job before proceeding.")
            watched = github.ci_watch(context)
            Work(self.store, self.member).job_update(
                job=scope["job"], status="in_progress", next_action="Review submitted changes and observed CI"
            )
            self.control.report("Submitted work: " + opened["pr"]["url"], kind="result")
            return {
                "state": "submitted",
                "checkpoint": saved["checkpoint"],
                "pr": opened["pr"]["url"],
                "evidence": saved["evidence"],
                "ci": watched,
                "validation": validation,
            }


def current_workspace(store, member, job=UNSET):
    scope = Control(store, member).current()
    with store.connect() as db:
        order, job = store.current_work(db, member, job=job)
        row = db.execute("SELECT root FROM job_workspaces WHERE job=?", (job,)).fetchone() if job else None
        if order and not job:
            row = db.execute("SELECT root FROM order_workspaces WHERE work_order=?", (order,)).fetchone()
        if job and scope and scope["role"] == "audit":
            row = db.execute("SELECT root FROM review_views WHERE member=? AND job=?", (member, job)).fetchone() or row
    return Path(row["root"] if row else store.member(member)["workspace"])
