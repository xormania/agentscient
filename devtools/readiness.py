"""Operator setup and read-only preflight. Never launch models or infer acceptance."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from .compat import codex_capability
from .github_http import GitHubHTTP
from .launch import team_config
from .workspaces import git

ENTRY = Path(__file__).with_name("run.py")


def project(workspace, repository, target="dev", remote="origin", serena_image=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*/[A-Za-z0-9_.-]+", repository) or repository.split("/")[1] in {
        ".",
        "..",
    }:
        raise ValueError("repository must be a GitHub owner/repository.")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", remote):
        raise ValueError("Invalid Git remote name.")
    root = Path(workspace).expanduser().resolve(strict=True)
    if Path(git(root, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve() != root:
        raise ValueError("workspace must be the Git repository root.")
    git(root, "check-ref-format", "--branch", target)
    if target.startswith("-"):
        raise ValueError("Invalid integration branch.")
    value = {
        "checkout": str(root),
        "repository": repository,
        "target": target,
        "remote": remote,
        "workspaces": str(root.parent / "wt-ag"),
        "development": {},
    }
    if serena_image:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:@-]+", serena_image):
            raise ValueError("Invalid Serena container image name.")
        value["serena"] = {"image": serena_image}
    return value


def connection(directory):
    directory = Path(directory).expanduser().resolve()
    config = team_config(directory)
    if not config.get("co"):
        raise ValueError("Appoint the external CO in team.json first.")
    return {
        "mcpServers": {
            "agentscient_dev": {
                "command": sys.executable,
                "args": [str(ENTRY), "mcp", "--state", str(directory), "--member", config["co"]],
            }
        }
    }


def probe(argv, root=None, env=None):
    result = subprocess.run(
        argv, cwd=root, env=env, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL
    )
    if result.returncode:
        # Do not echo arbitrary binary output, credential URLs or environment data.
        raise ValueError(f"Installed command failed with exit status {result.returncode}.")
    return result.stdout.strip()


def platform(checkout, development):
    env = os.environ.copy()
    php = Path(development.get("php", "php"))
    if php.is_absolute():
        env["PATH"] = str(php.parent) + os.pathsep + env.get("PATH", "")
    # Ignore operator overrides that would hide real platform failures.
    for key in ("COMPOSER", "COMPOSER_IGNORE_PLATFORM_REQ", "COMPOSER_IGNORE_PLATFORM_REQS", "COMPOSER_NO_DEV"):
        env.pop(key, None)
    result = subprocess.run(
        [
            development.get("composer", "composer"),
            "--no-plugins",
            "--no-scripts",
            "--no-interaction",
            "check-platform-reqs",
            "--lock",
            "--format=json",
        ],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        stdin=subprocess.DEVNULL,
    )
    try:
        requirements = json.loads(result.stdout)
        failed = [row["name"] for row in requirements if row["status"] != "success"]
    except (ValueError, TypeError, KeyError):
        raise ValueError(
            "Composer could not inspect the locked platform; run check-platform-reqs --lock locally."
        ) from None
    if failed or result.returncode:
        raise ValueError("Unsatisfied locked platform requirements: " + ", ".join(failed))
    return "Locked PHP and extension requirements, including development packages, are satisfied."


def doctor(directory, online=False):
    directory = Path(directory).expanduser().resolve()
    checks = []

    def check(name, action):
        try:
            detail = action()
        except Exception as error:
            checks.append({"name": name, "status": "failed", "detail": GitHubHTTP().clean(str(error))[:600]})
            return None
        checks.append({"name": name, "status": "passed", "detail": detail})
        return detail

    def require(condition, detail):
        if not condition:
            raise ValueError(detail)
        return detail

    config = check("team", lambda: team_config(directory))
    if config is None:
        return {"status": "blocked", "checks": checks, "authenticated_acceptance": "not established by preflight"}
    checks[-1]["detail"] = "Team configuration is readable."
    check("CO connection", lambda: require(bool(config.get("co")), "An external user-facing CO must be appointed."))
    check(
        "collaborator capacity",
        lambda: require(
            len([m for m in config["members"] if m["name"] != config.get("co")]) >= 2,
            "At least two collaborator slots are needed for XO and a producer; add a third for concurrent audit.",
        ),
    )
    check(
        "private state",
        lambda: require(
            directory.stat().st_mode & 0o077 == 0
            and all(
                not directory.is_relative_to(Path(m["workspace"]).expanduser().resolve()) for m in config["members"]
            ),
            "State must be private (mode 700) and outside every source workspace.",
        ),
    )
    configured = config.get("project", {})
    validated = check(
        "project",
        lambda: project(
            configured.get("checkout", ""),
            configured.get("repository", ""),
            configured.get("target", "dev"),
            configured.get("remote", "origin"),
            configured.get("serena", {}).get("image"),
        ),
    )
    if validated:
        checks[-1]["detail"] = "Repository root, repository identity and integration branch syntax are valid."
        root, remote, target = validated["checkout"], validated["remote"], validated["target"]

        def remote_identity():
            url = git(root, "remote", "get-url", remote).stdout.decode().strip()
            match = re.search(r"(?:github\.com[:/])([^/]+/[^/]+?)(?:\.git)?$", url)
            require(
                bool(match) and match[1].casefold() == configured["repository"].casefold(),
                "The configured Git remote must identify the same GitHub repository as project.repository.",
            )
            return "Git push and GitHub outcomes address the same repository."

        check("Git remote", remote_identity)
        check(
            "Git identity",
            lambda: require(
                bool(configured.get("identity", {}).get("name") and configured.get("identity", {}).get("email"))
                or git(root, "var", "GIT_AUTHOR_IDENT", check=False).returncode == 0,
                "A commit identity must be configured in Git or project.identity.",
            ),
        )
        check(
            "Symfony tools enabled",
            lambda: require(
                isinstance(configured.get("development"), dict),
                "project.development must be an object ({} enables defaults).",
            ),
        )
        check("locked PHP platform", lambda: platform(root, configured.get("development", {})))
        image = configured.get("serena", {}).get("image")

        def serena():
            require(bool(image), "Configure project.serena.image for product source work.")
            docker = configured["serena"].get("docker", "docker")
            probe([docker, "info", "--format", "{{.ServerVersion}}"])
            labels = json.loads(probe([docker, "image", "inspect", "--format", "{{json .Config.Labels}}", image])) or {}
            source = Path(__file__).with_name("serena").joinpath("Dockerfile").read_text()
            revision = re.search(r"ARG SERENA_REVISION=([0-9a-f]{40})", source)[1]
            require(
                labels.get("org.opencontainers.image.revision") == revision,
                "Build the current devtools/serena image; its source revision label must match the pinned beta.",
            )
            return {
                "image": image,
                "source_revision": revision,
                "runtime_mounts": "verified by the separate integration test",
            }

        check("Serena image", serena)
        if online:
            check(
                "Git remote target",
                lambda: require(
                    bool(git(root, "ls-remote", "--exit-code", remote, "refs/heads/" + target).stdout.strip()),
                    "The integration branch must be readable on the configured remote.",
                ),
            )

            def github():
                result = GitHubHTTP(config.get("github", {})).request("GET", "/repos/" + configured["repository"])
                require(not result.get("archived") and not result.get("disabled"), "Repository must be active.")
                require(
                    result.get("permissions", {}).get("push") is True,
                    "GitHub credential must have repository push permission.",
                )
                return "Repository is readable and reports push permission; merge and review rules still apply."

            check("GitHub access", github)
        else:
            checks.append(
                {
                    "name": "Git/GitHub online access",
                    "status": "not_checked",
                    "detail": "Use doctor --online for read-only provider probes.",
                }
            )
    seen = set()
    members = list(config["members"])
    if config.get("runtime"):
        from .runtime import load

        def runtime_policy():
            policy, availability, revision = load(directory)
            members.extend(row for row in policy["profiles"].values()
                           if availability["vendors"][row["vendor"]]["available"])
            return {"revision": revision, "roles": list(policy["roles"])}

        check("Runtime policy", runtime_policy)
    if any(row["harness"] != "external" for row in members) or config.get("runtime"):
        check("tmux", lambda: require(bool(shutil.which("tmux")), "Managed harness sessions require tmux."))
    for member in members:
        harness = member["harness"]
        binary = member.get("binary") or harness
        if harness == "external" or (harness, binary) in seen:
            continue
        seen.add((harness, binary))

        def native(harness=harness, binary=binary):
            executable = shutil.which(binary)
            require(bool(executable), f"Install the configured {harness} binary and authenticate it locally.")
            version = re.search(r"\b\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", probe([executable, "--version"]))
            detail = {"version": version[0] if version else "unreported", "authentication": "requires live acceptance"}
            if harness == "codex":
                capability = codex_capability(executable)
                require(
                    capability["status"] == "supported",
                    "Installed Codex must support TurnStartParams.toolOutput; update before launch.",
                )
                detail["protocol"] = capability
            elif harness == "claude":
                detail["protocol"] = "Channel registration is checked on actual startup."
            else:
                detail["protocol"] = "ACP authentication and session creation are checked on actual startup."
            return detail

        check(harness + " binary", native)
    return {
        "status": "blocked" if any(c["status"] == "failed" for c in checks) else "preflight_passed",
        "checks": checks,
        "authenticated_acceptance": "not established by preflight",
        "next": "Follow docs/local-agent-readiness.md and retain the actual local run's evidence.",
    }


def evidence(directory, work_order):
    """Summarize existing records without upgrading the DB or certifying a model run."""
    path = Path(directory).expanduser().resolve() / "live.sqlite3"
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        order = db.execute("SELECT id,title,status FROM work_orders WHERE id=?", (work_order,)).fetchone()
        if not order:
            raise ValueError("No recorded work order has that number.")
        current_schema = db.execute("PRAGMA user_version").fetchone()[0] >= 8
        delivery = (
            db.execute(
                "SELECT w.pull_request,d.revision,d.merge_commit,d.assessment FROM work_orders w "
                "LEFT JOIN order_deliveries d ON d.work_order=w.id WHERE w.id=?",
                (work_order,),
            ).fetchone()
            if current_schema
            else None
        )
        rows = db.execute("SELECT actor,kind,data FROM events WHERE work_order=? ORDER BY id", (work_order,))
        sessions, tools, denied, serena = {}, {}, 0, 0
        runtime, actors = [], set()
        for row in rows:
            actors.add(row["actor"])
            data = json.loads(row["data"])
            if row["kind"] in {"runtime_requested", "runtime_observed", "mcp_client", "runtime_selected"}:
                runtime.append({"actor": row["actor"], "kind": row["kind"], **data})
            if row["kind"] in {"native_session", "channel_ready"} and data.get("native_id"):
                sessions.setdefault(row["actor"], set()).add(data["native_id"])
            if row["kind"] == "operation_finished":
                tool = data["capability"]
                tools[tool] = tools.get(tool, 0) + 1
            denied += row["kind"] in {"tool_denied", "native_tool_denied", "native_tool_violation"}
            serena += row["kind"] == "serena_call" and data.get("success") is True
        return {
            "work_order": dict(order),
            "delivery": dict(delivery) if delivery else None,
            "cleanup": [
                dict(r)
                for r in db.execute(
                    "SELECT job,state,detail FROM managed_worktrees WHERE work_order=? ORDER BY root",
                    (work_order,),
                )
            ]
            if current_schema
            else [],
            "native_sessions": {actor: sorted(ids) for actor, ids in sessions.items()},
            "runtime_records": runtime,
            "telemetry_files": [str(path.parent / "telemetry" / (actor + ".jsonl")) for actor in sorted(actors)
                                if (path.parent / "telemetry" / (actor + ".jsonl")).is_file()],
            "capture_notes": "Requested/inherited settings are not confirmed settings. Missing native fields are unknown. "
                             "Wire captures contain exposed protocol traffic; Claude transcript capture begins when "
                             "its hook registers a session transcript. External clients expose only their MCP traffic.",
            "completed_tool_calls": tools,
            "successful_serena_calls": serena,
            "denials_or_violations_to_inspect": denied,
            "messages": [
                dict(r)
                for r in db.execute(
                    "SELECT delivery,count(*) AS count,sum(acknowledged IS NOT NULL) AS acknowledged FROM messages WHERE work_order=? GROUP BY delivery",
                    (work_order,),
                )
            ],
            "jobs": [
                dict(r)
                for r in db.execute(
                    "SELECT j.title,j.status,j.pull_request,d.revision,d.merge_commit,d.assessment FROM jobs j LEFT JOIN deliveries d ON d.job=j.id WHERE j.work_order=? ORDER BY j.id",
                    (work_order,),
                )
            ],
            "operations": [
                dict(r)
                for r in db.execute(
                    "SELECT action,state,count(*) AS count FROM operations WHERE work_order=? GROUP BY action,state",
                    (work_order,),
                )
            ],
            "artifact_count": db.execute(
                "SELECT count(DISTINCT artifact) FROM work_links WHERE work_order=?", (work_order,)
            ).fetchone()[0],
            "interpretation": "Recorded observations only. Completed calls can return failures or receipts. Inspect operation results, traces and artifacts; this does not certify authenticated model acceptance.",
        }
