#!/usr/bin/env python3
"""Run the declared audit ladder in a branch's owning worktree."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import NoReturn
from urllib.parse import urlsplit

IDENTITY = re.compile(r"(?P<name>[^<>\n]+) <(?P<email>[^<>\s@]+@[^<>\s]+)>")
RECORD_ID = re.compile(r"^record:\s+(\S+)\s*$", re.MULTILINE)
LANDED = re.compile(r"^LANDED\t([0-9a-f]{40})\t", re.MULTILINE)
DISPATCH_STAGES = (
    ("tests", "author-tests", "grok", "tests"),
    ("check-tests", "check-tests", "codex", "check-tests"),
    ("tests-fix", "author-tests", "grok", "tests"),
    ("code", "implement", "codex", "code"),
    ("security", "security-audit", "codex", "review"),
    ("adversarial", "adversarial-review", "grok", "review"),
    ("fix-tests", "author-tests", "grok", "tests"),
    ("fix-code", "implement", "codex", "code"),
    ("security-re", "security-audit", "codex", "review"),
)
REVIEW_STAGES = frozenset(
    {"check-tests", "security", "adversarial", "security-re"}
)
WITHHELD_STAGES = frozenset(
    {"tests", "check-tests", "tests-fix", "fix-tests"}
)
CONF_KEYS = (
    "LANE_NAME",
    "TRUNK_BRANCH",
    "REPO_SLUG",
    "CHECK_NAMES",
    "LANE_AUTHOR",
    "SCOPE_CAP",
    "WALL_DEFAULT",
    "WORKTREE_ROOT",
    "ADDRESS_GROK",
    "ADDRESS_CODEX",
    "ADDRESS_CLAUDE",
)


class Refused(Exception):
    """A pre-act rejection on the shared refusal wire."""

    def __init__(self, kind: str, expected: str, found: str, needed: str) -> None:
        self.kind = kind
        self.expected = expected
        self.found = found
        self.needed = needed
        super().__init__(self.line())

    def line(self) -> str:
        return " ".join(
            f"{self.kind}: expected {self.expected}; found {self.found}; "
            f"needed {self.needed}".split()
        )


class Stopped(Exception):
    """A mid-act stop after the ladder has a durable record."""

    def __init__(
        self,
        stage: str,
        record_id: str = "none",
        reason: str | None = None,
        verdict: str | None = None,
        detail: str | None = None,
        exit_code: int = 3,
    ) -> None:
        self.stage = stage
        self.record_id = record_id
        self.reason = reason
        self.verdict = verdict
        self.detail = detail
        self.exit_code = exit_code
        super().__init__(self.line())

    def line(self) -> str:
        fields = [f"stopped stage={self.stage}", f"record={self.record_id}"]
        if self.reason:
            fields.append(f"reason={self.reason}")
        if self.verdict:
            fields.append(f"verdict={self.verdict}")
        return " ".join(fields)


@dataclass
class Pending:
    """A detached dispatch waiting to be consumed."""

    name: str
    record_id: str
    record_path: Path
    model: str
    effort: str
    base_sha: str
    started: float


_LANECONF: ModuleType | None = None


def refuse(kind: str, expected: str, found: str, needed: str) -> NoReturn:
    raise Refused(kind, expected, found, needed)


def _load_laneconf() -> ModuleType:
    global _LANECONF  # noqa: PLW0603 - one lazily loaded sibling module
    if _LANECONF is not None:
        return _LANECONF
    candidates = (
        Path(__file__).resolve().with_name("laneconf.py"),
        Path.cwd() / "ops" / "conductor" / "tools" / "laneconf.py",
    )
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("ladder_laneconf", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LANECONF = module
        return module
    refuse(
        "conf-file",
        "the lane conf reader beside the driver or in the invoking checkout",
        "laneconf.py absent",
        "restore ops/conductor/tools/laneconf.py",
    )


def conf_value(name: str) -> str:
    module = _load_laneconf()
    try:
        return module.get(name)
    except module.ConfigError as error:
        kind = "conf-key" if error.kind == "key" else error.kind
        refuse(kind, error.expected, error.found, error.needed)


def configuration() -> dict[str, str]:
    """Read every driver-owned required key through the shared reader."""
    laneconf = _load_laneconf()
    try:
        return {
            "WORKTREE_ROOT": laneconf.get("WORKTREE_ROOT"),
            "ADDRESS_GROK": laneconf.get("ADDRESS_GROK"),
            "ADDRESS_CODEX": laneconf.get("ADDRESS_CODEX"),
            "ADDRESS_CLAUDE": laneconf.get("ADDRESS_CLAUDE"),
        }
    except laneconf.ConfigError as error:
        kind = "conf-key" if error.kind == "key" else error.kind
        refuse(kind, error.expected, error.found, error.needed)


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("git") or "git"
    return run([executable, *args], cwd)


def git_out(cwd: Path, *args: str) -> str:
    result = git(cwd, *args)
    if result.returncode != 0:
        refuse(
            "worktree",
            "a readable git worktree",
            result.stderr.strip() or f"git exited {result.returncode}",
            "repair the repository metadata",
        )
    return result.stdout.strip()


def worktrees(cwd: Path) -> list[tuple[Path, str | None]]:
    result = git(cwd, "worktree", "list", "--porcelain")
    if result.returncode != 0:
        refuse(
            "worktree",
            "git worktree metadata",
            result.stderr.strip() or f"git exited {result.returncode}",
            "invoke the driver from a checkout of the repository",
        )
    rows: list[tuple[Path, str | None]] = []
    path: Path | None = None
    branch: str | None = None
    for raw in [*result.stdout.splitlines(), ""]:
        if raw.startswith("worktree "):
            path = Path(raw.removeprefix("worktree ")).resolve()
        elif raw.startswith("branch refs/heads/"):
            branch = raw.removeprefix("branch refs/heads/")
        elif not raw and path is not None:
            rows.append((path, branch))
            path = None
            branch = None
    return rows


def branch_worktree(cwd: Path, branch: str, root_hint: str) -> Path:
    for path, checked_out in worktrees(cwd):
        if checked_out == branch:
            return path
    slug = branch.rsplit("/", 1)[-1]
    refuse(
        "worktree",
        f"branch {branch} checked out in a worktree",
        "none",
        f"run git worktree add {root_hint}/ag-{slug} {branch}",
    )


def record_worktree(cwd: Path, ladder_id: str) -> tuple[Path, dict]:
    relative = Path(".dev") / "records" / "ladders" / f"{ladder_id}.json"
    for path, _branch in worktrees(cwd):
        candidate = path / relative
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            refuse(
                "record",
                f"a valid ladder record {ladder_id}",
                str(error),
                "repair the named record",
            )
        if not isinstance(data, dict) or data.get("id") != ladder_id:
            refuse(
                "record",
                f"record id {ladder_id}",
                repr(data.get("id") if isinstance(data, dict) else data),
                "repair the named record",
            )
        return path, data
    refuse(
        "record",
        f"ladder record {ladder_id} in a repository worktree",
        "absent",
        "choose or repair the record",
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def full_identity(value: str, label: str) -> str:
    if IDENTITY.fullmatch(value) is None:
        refuse(
            "identity",
            f"{label} in the Name <address> form",
            value or "unset",
            f"supply {label} as Name <address>",
        )
    return value


def file_arg(path: str, label: str, *, required: bool = True) -> Path | None:
    candidate = Path(path).resolve()
    if candidate.is_file():
        try:
            candidate.read_bytes()
        except OSError as error:
            refuse(label, f"a readable {label} file", str(error), "correct its permissions")
        return candidate
    if required:
        refuse(label, f"a readable {label} file", str(candidate), f"supply a {label}")
    return None


def flag_value(argv: list[str], flag: str) -> str | None:
    try:
        index = argv.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(argv):
        return None
    return argv[index + 1]


def parse_dispatch_json(text: str) -> dict:
    for raw in reversed(text.splitlines()):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("argv"), list):
            return payload
    raise ValueError("dispatcher dry-run emitted no argv object")


def stage_spec(name: str) -> tuple[str, str, str]:
    base = "code" if name.startswith("code-") else name
    for stage, job, harness, flag in DISPATCH_STAGES:
        if stage == base:
            return job, harness, flag
    raise KeyError(name)


def parse_plan(plan: Path | None) -> tuple[list[dict], list[dict]]:
    buckets: list[dict] = []
    slices: list[dict] = []
    if plan is not None:
        for raw in plan.read_text(encoding="utf-8").splitlines():
            fields = raw.split("\t")
            if len(fields) >= 3 and fields[0] == "slice":
                slices.append({"name": fields[1], "declared": fields[2]})
            elif len(fields) >= 4 and fields[0] == "bucket":
                buckets.append(
                    {
                        "name": fields[1],
                        "declared": fields[2],
                        "files": fields[3].split(),
                    }
                )
    for item in slices:
        if item["declared"] != "M":
            continue
        valid = len(buckets) == 2 and all(
            bucket["name"] and bucket["declared"] == "S"
            for bucket in buckets
        )
        if not valid:
            refuse(
                "plan",
                f"slice {item['name']} declared M with exactly two named S buckets",
                f"{len(buckets)} buckets in {plan}",
                "declare exactly two named S buckets",
            )
    if not buckets:
        buckets.append({"name": "scope", "declared": "S", "files": []})
    return buckets, slices


def recorded_file(worktree: Path, data: object, label: str) -> Path:
    """Resolve and verify one file named by a durable ladder record."""
    if not isinstance(data, dict):
        refuse("record", f"a recorded {label}", repr(data), "repair the record")
    raw_path = data.get("path")
    expected = data.get("sha256")
    if not isinstance(raw_path, str) or not raw_path:
        refuse("record", f"a recorded {label} path", repr(raw_path), "repair the record")
    candidate = Path(raw_path).resolve()
    if not candidate.is_relative_to(worktree.resolve()):
        refuse(
            "record",
            f"the {label} path inside {worktree}",
            str(candidate),
            "repair the record with an in-worktree path",
        )
    if not candidate.is_file():
        refuse("record", f"a readable recorded {label}", str(candidate), "repair the record")
    actual = digest(candidate)
    if not isinstance(expected, str) or actual != expected:
        refuse(
            "record",
            f"the recorded {label} sha256 {expected}",
            actual,
            "restore the recorded bytes or repair the digest",
        )
    return candidate


class Driver:
    """The stateful orchestration projection of the ladder contract."""

    def __init__(
        self,
        worktree: Path,
        branch: str,
        scope: Path,
        plan: Path | None,
        conf: dict[str, str],
        agent: str,
        record: dict | None = None,
    ) -> None:
        self.worktree = worktree
        self.branch = branch
        self.scope = scope
        self.plan = plan
        self.conf = conf
        self.agent = agent
        self.record = record or self.new_record()
        self.record_path = (
            worktree
            / ".dev"
            / "records"
            / "ladders"
            / f"{self.record['id']}.json"
        )
        self.inputs_dir = self.record_path.with_suffix("")
        self.dispatch = worktree / "ops" / "bin" / "dispatch.sh"
        self.launch = worktree / "ops" / "devlane" / "dispatch" / "launch.py"
        self.land = worktree / "ops" / "conductor" / "tools" / "land.py"
        self.findings = worktree / "ops" / "conductor" / "tools" / "findings.py"
        self.gh = shutil.which("gh") or "gh"
        self.stage_by_name = {
            row["name"]: row for row in self.record.get("stages", [])
        }
        self.buckets, self.slices = parse_plan(plan)
        self.implementation_markers: list[str] = list(
            self.record.get("implementation_markers") or []
        )

    def new_record(self) -> dict:
        suffix = hashlib.sha256(
            f"{os.getpid()}:{datetime.now(timezone.utc).timestamp()}".encode()
        ).hexdigest()[:6]
        ladder_id = f"{utc_stamp()}-ladder-{suffix}"
        base_sha = git_out(self.worktree, "rev-parse", "HEAD")
        stages = [
            {
                "name": name,
                "job": job,
                "harness": harness,
                "stage": flag,
                "condition": "declared stage condition not yet evaluated",
                "attempt": 0,
                "outcome": "pending",
            }
            for name, job, harness, flag in DISPATCH_STAGES
        ]
        stages.append(
            {
                "name": "pr",
                "job": None,
                "harness": None,
                "stage": None,
                "condition": "audits approve",
                "attempt": 0,
                "outcome": "pending",
            }
        )
        return {
            "id": ladder_id,
            "lane": self.conf["LANE_NAME"],
            "branch": self.branch,
            "worktree": str(self.worktree),
            "base_sha": base_sha,
            "status": "running",
            "stopped": None,
            "pr": None,
            "scope": {"path": str(self.scope), "sha256": digest(self.scope)},
            "plan": (
                {"path": str(self.plan), "sha256": digest(self.plan)}
                if self.plan is not None
                else None
            ),
            "conf": {
                "path": str(self.worktree / "ops" / "lane.conf"),
                "sha256": digest(self.worktree / "ops" / "lane.conf"),
            },
            "stages": stages,
            "calibration": [],
            "implementation_markers": [],
        }

    def row(self, name: str) -> dict:
        if name not in self.stage_by_name:
            job, harness, flag = stage_spec(name)
            row = {
                "name": name,
                "job": job,
                "harness": harness,
                "stage": flag,
                "condition": "one declared S bucket",
                "attempt": 0,
                "outcome": "pending",
            }
            pr_index = next(
                (
                    index
                    for index, item in enumerate(self.record["stages"])
                    if item["name"] == "pr"
                ),
                len(self.record["stages"]),
            )
            self.record["stages"].insert(pr_index, row)
            self.stage_by_name[name] = row
        return self.stage_by_name[name]

    def commit(self, *extra: Path) -> None:
        self.record_path.parent.mkdir(parents=True, exist_ok=True)
        self.record["implementation_markers"] = self.implementation_markers
        self.record_path.write_text(
            json.dumps(self.record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        paths = [self.record_path, *extra]
        relative = [str(path.relative_to(self.worktree)) for path in paths if path.exists()]
        added = git(self.worktree, "add", "--", *relative)
        if added.returncode != 0:
            raise Stopped("record", reason="commit", detail=added.stderr.strip())
        message = (
            f"ladder: record {self.record['id']}\n\n"
            "Source: generated: ops/conductor/tools/ladder.py\n"
            f"Co-Authored-By: {self.agent}\n"
        )
        committed = git(
            self.worktree,
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-m",
            message,
        )
        if committed.returncode != 0:
            raise Stopped("record", reason="commit", detail=committed.stderr.strip())

    def stop(self, stopped: Stopped) -> NoReturn:
        self.record["status"] = "stopped"
        self.record["stopped"] = {
            "stage": stopped.stage,
            "record": stopped.record_id,
            "reason": stopped.reason,
            "verdict": stopped.verdict,
        }
        row = self.row(stopped.stage)
        row["outcome"] = stopped.verdict or "stopped"
        if stopped.reason:
            row["reason"] = stopped.reason
        self.commit()
        raise stopped

    def make_input(self, name: str, body: str) -> Path:
        self.inputs_dir.mkdir(parents=True, exist_ok=True)
        path = self.inputs_dir / f"{name}.md"
        path.write_text(body.rstrip() + "\n", encoding="utf-8")
        return path

    def dispatch_args(
        self,
        name: str,
        inputs: list[Path],
        previous: str | None,
    ) -> list[str]:
        job, harness, flag = stage_spec(name)
        scope = self.stage_scope(name, inputs)
        argv = [
            str(self.dispatch),
            "--branch",
            self.branch,
            "--job",
            job,
            "--harness",
            harness,
            "--unit",
            self.branch,
            "--stage",
            flag,
            "--scope-file",
            str(scope),
        ]
        for path in inputs:
            if path == scope:
                continue
            argv.extend(("--input", str(path)))
        if previous:
            argv.extend(("--follows", previous))
        return argv

    def stage_scope(self, name: str, inputs: list[Path]) -> Path:
        if name == "fix-code" or name == "code" or name.startswith("code-"):
            for path in inputs:
                if path.name == "test-command.md":
                    return path
        return self.scope

    def resolved(
        self,
        name: str,
        inputs: list[Path],
        previous: str | None,
    ) -> tuple[str, str, list[str]]:
        base = self.dispatch_args(name, inputs, previous)
        result = run([*base, "--dry-run"], self.worktree)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            reason = detail.split(":", 1)[0] if detail else "job"
            raise Stopped(name, reason=reason, detail=detail)
        try:
            launch = parse_dispatch_json(result.stdout)
        except ValueError as error:
            raise Stopped(name, reason="model", detail=str(error)) from error
        argv = [str(item) for item in launch["argv"]]
        model = flag_value(argv, "--model")
        effort = flag_value(argv, "--effort")
        if not model or not effort:
            raise Stopped(
                name,
                reason="model",
                detail="dispatcher dry-run omitted model or effort",
            )
        return model, effort, base

    def custody(self, name: str, previous: str | None) -> dict:
        first = self.scope.read_text(encoding="utf-8").splitlines()[0]
        given = [first]
        if previous:
            given.append(previous)
        withheld = list(self.implementation_markers) if name in WITHHELD_STAGES else []
        return {"given": given, "withheld": withheld}

    def mint(
        self,
        name: str,
        inputs: list[Path],
        previous: str | None,
    ) -> Pending:
        row = self.row(name)
        attempt = int(row.get("attempt") or 0) + 1
        row["attempt"] = attempt
        model, effort, base = self.resolved(name, inputs, previous)
        row["dispatched"] = {"model": model, "effort": effort}
        proof = self.custody(name, previous)
        self.verify_custody(name, inputs, previous, proof)
        input_path = inputs[-1] if inputs else self.scope
        row["input"] = {
            "path": str(input_path),
            "sha256": digest(input_path),
            "proof": proof,
        }
        self.commit(*[path for path in inputs if path.is_relative_to(self.inputs_dir)])
        base_sha = git_out(self.worktree, "rev-parse", "HEAD")
        result = run(
            [*base, "--model", model, "--effort", effort, "--detach"],
            self.worktree,
        )
        match = RECORD_ID.search(result.stdout)
        if result.returncode != 0 or match is None:
            reason = "job"
            detail = result.stderr.strip() or result.stdout.strip()
            if detail and ":" in detail:
                reason = detail.split(":", 1)[0].split()[-1]
            raise Stopped(name, reason=reason, detail=detail)
        record_id = match.group(1)
        record_path = (
            self.worktree
            / ".dev"
            / "records"
            / "dispatches"
            / f"{record_id}.json"
        )
        if not record_path.is_file():
            raise Stopped(
                name,
                record_id,
                "record",
                detail="dispatch record absent",
            )
        row["dispatch_record"] = record_id
        row["record"] = record_id
        row["outcome"] = "launched"
        self.commit(record_path)
        try:
            launched = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise Stopped(name, record_id, "record", detail=str(error)) from error
        selection = launched.get("model") or {}
        if (
            selection.get("requested") != model
            or selection.get("effort_requested") != effort
        ):
            raise Stopped(
                name,
                record_id,
                "model",
                detail="minted selection differs from dispatcher dry-run",
            )
        return Pending(
            name,
            record_id,
            record_path,
            model,
            effort,
            base_sha,
            time.monotonic(),
        )

    def load_envelope(self, pending: Pending) -> tuple[dict, dict]:
        try:
            dispatch_record = json.loads(pending.record_path.read_text(encoding="utf-8"))
            result = dispatch_record["result"]
            envelope = result["envelope"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise Stopped(
                pending.name,
                pending.record_id,
                "envelope",
                detail=str(error),
            ) from error
        if dispatch_record.get("status") != "closed" or envelope.get("status") != "ok":
            raise Stopped(
                pending.name,
                pending.record_id,
                "envelope",
                detail="dispatch or envelope was not accepted",
            )
        job, harness, stage = stage_spec(pending.name)
        lineage = dispatch_record.get("lineage") or {}
        binding = {
            "job": dispatch_record.get("job"),
            "stage": dispatch_record.get("stage"),
            "harness": (dispatch_record.get("harness") or {}).get("name"),
            "branch": lineage.get("branch"),
            "unit": dispatch_record.get("unit"),
        }
        expected_binding = {
            "job": job,
            "stage": stage,
            "harness": harness,
            "branch": self.branch,
            "unit": self.branch,
        }
        if binding != expected_binding:
            raise Stopped(
                pending.name,
                pending.record_id,
                "record",
                detail=(
                    f"dispatch record binding differs: expected {expected_binding!r}; "
                    f"found {binding!r}"
                ),
            )
        requested = (dispatch_record.get("model") or {}).get("requested")
        effort = (dispatch_record.get("model") or {}).get("effort_requested")
        if requested != pending.model or effort != pending.effort:
            raise Stopped(
                pending.name,
                pending.record_id,
                "model",
                detail="recorded selection differs from dispatcher dry-run",
            )
        row = self.row(pending.name)
        row["recorded"] = {
            "model_requested": requested,
            "effort": effort,
            "model_ran": (dispatch_record.get("model") or {}).get("ran"),
        }
        return dispatch_record, envelope

    def await_result(self, pending: Pending) -> tuple[dict, dict]:
        try:
            launched = json.loads(pending.record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            launched = {}
        cap = (launched.get("caps") or {}).get("timeout")
        try:
            wall = int(cap or self.conf["WALL_DEFAULT"])
            grace = int(self.conf["LADDER_WAIT_GRACE"])
        except (TypeError, ValueError) as error:
            raise Stopped(
                pending.name,
                pending.record_id,
                "wall",
                detail=f"invalid wait cap: {error}",
            ) from error
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.launch),
                    "wait",
                    pending.record_id,
                    "--timeout",
                    str(wall + grace),
                ],
                cwd=self.worktree,
                capture_output=True,
                text=True,
                check=False,
                timeout=wall + grace,
            )
        except subprocess.TimeoutExpired as error:
            raise Stopped(
                pending.name,
                pending.record_id,
                "wall",
                detail=f"launch.py wait exceeded {wall + grace} seconds",
            ) from error
        if result.returncode != 0:
            detail = "\n".join(
                text.strip() for text in (result.stdout, result.stderr) if text.strip()
            )
            lower = detail.lower()
            reason = "tripped" if "tripped=true" in lower else "wall" if "running" in lower else "died"
            if reason in {"tripped", "died"}:
                detail = (
                    f"{detail}\nneeded run launch.py collect {pending.record_id} "
                    "--verify COMMAND"
                )
            raise Stopped(pending.name, pending.record_id, reason, detail=detail)
        self.commit(pending.record_path)
        dispatch_record, envelope = self.load_envelope(pending)
        return dispatch_record, envelope

    def existing_result(self, name: str) -> tuple[Pending, dict, dict] | None:
        row = self.row(name)
        record_id = row.get("dispatch_record")
        dispatched = row.get("dispatched") or {}
        if not record_id or not dispatched.get("model") or not dispatched.get("effort"):
            return None
        record_path = (
            self.worktree
            / ".dev"
            / "records"
            / "dispatches"
            / f"{record_id}.json"
        )
        pending = Pending(
            name,
            record_id,
            record_path,
            dispatched["model"],
            dispatched["effort"],
            self.record.get("base_sha") or git_out(self.worktree, "rev-parse", "HEAD"),
            time.monotonic(),
        )
        try:
            dispatch_record, envelope = self.load_envelope(pending)
        except Stopped as error:
            if error.reason == "record":
                raise
            return None
        return pending, dispatch_record, envelope

    def land_result(self, pending: Pending, dispatch_record: dict) -> None:
        row = self.row(pending.name)
        ran = (dispatch_record.get("model") or {}).get("ran")
        harness = (dispatch_record.get("harness") or {}).get("name")
        address = self.conf.get(f"ADDRESS_{str(harness).upper()}")
        if not isinstance(ran, str) or not ran or not address:
            raise Stopped(pending.name, pending.record_id, "model", detail="ran model has no address")
        author = full_identity(self.conf["LANE_AUTHOR"], "LANE_AUTHOR")
        coauthor = full_identity(f"{ran} <{address}>", "harness co-author")
        stage_base = git_out(self.worktree, "rev-parse", "HEAD")
        result = run(
            [
                sys.executable,
                str(self.land),
                pending.record_id,
                "--author",
                author,
                "--co-author",
                coauthor,
            ],
            self.worktree,
        )
        if result.returncode != 0:
            detail = result.stdout.strip() or result.stderr.strip()
            raise Stopped(pending.name, pending.record_id, "land", detail=detail)
        shas = LANDED.findall(result.stdout)
        for sha in shas:
            ancestry = git(self.worktree, "merge-base", "--is-ancestor", stage_base, sha)
            if ancestry.returncode != 0:
                raise Stopped(pending.name, pending.record_id, "lineage", detail=sha)
        row["landed_shas"] = shas
        row["landed"] = shas
        if (pending.name == "code" or pending.name.startswith("code-")) and shas:
            index = 0 if pending.name == "code" else int(pending.name.split("-", 1)[1]) - 1
            bucket = self.buckets[index]
            allowed = set(bucket["files"])
            if allowed:
                measured = git(
                    self.worktree,
                    "diff",
                    "--name-only",
                    stage_base,
                    shas[-1],
                    "--",
                )
                if measured.returncode != 0:
                    raise Stopped(
                        pending.name,
                        pending.record_id,
                        "bucket",
                        detail=measured.stderr.strip(),
                    )
                outside = sorted(set(measured.stdout.splitlines()) - allowed)
                if outside:
                    raise Stopped(
                        pending.name,
                        pending.record_id,
                        "bucket",
                        detail=f"landed paths outside bucket {bucket['name']}: {outside!r}",
                    )
        row["outcome"] = "ok"
        if pending.name == "code" or pending.name.startswith("code-") or pending.name == "fix-code":
            envelope = (dispatch_record.get("result") or {}).get("envelope") or {}
            marker_values = [pending.record_id]
            for key in ("note", "artifacts", "findings"):
                marker_values.extend(self.strings(envelope.get(key)))
            for marker in marker_values:
                if isinstance(marker, str) and marker and marker not in self.implementation_markers:
                    self.implementation_markers.append(marker)
        self.commit()

    def ledger_result(self, pending: Pending, envelope: dict) -> None:
        imported = run([sys.executable, str(self.findings), "import"], self.worktree)
        if imported.returncode != 0:
            raise Stopped(
                pending.name,
                pending.record_id,
                "ledger",
                detail=imported.stderr.strip() or imported.stdout.strip(),
            )
        exported = run([sys.executable, str(self.findings), "export"], self.worktree)
        if exported.returncode != 0:
            raise Stopped(
                pending.name,
                pending.record_id,
                "ledger",
                detail=exported.stderr.strip() or exported.stdout.strip(),
            )
        destination = self.worktree / "ops" / "conductor" / "findings" / "findings.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(exported.stdout, encoding="utf-8")
        row = self.row(pending.name)
        row["ledger"] = {"imported": True, "exported": str(destination)}
        row["verdict"] = envelope.get("verdict")
        counts = envelope.get("counts") or {}
        row["findings"] = sum(
            int(counts.get(key) or 0) for key in ("p1", "p2", "p3")
        )
        extra = [destination]
        if pending.name == "check-tests":
            findings_file = self.inputs_dir / "check-tests-findings.json"
            findings_file.parent.mkdir(parents=True, exist_ok=True)
            findings_file.write_text(
                json.dumps(envelope.get("findings"), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            row["findings_file"] = str(findings_file)
            extra.append(findings_file)
        row["outcome"] = "ok"
        self.commit(*extra)

    def finish(self, pending: Pending, *, already_closed: tuple[dict, dict] | None = None) -> dict:
        if already_closed is None:
            dispatch_record, envelope = self.await_result(pending)
        else:
            dispatch_record, envelope = already_closed
            self.commit(pending.record_path)
        if pending.name in REVIEW_STAGES:
            self.ledger_result(pending, envelope)
        else:
            self.land_result(pending, dispatch_record)
        self.row(pending.name)["minutes"] = round(
            (time.monotonic() - pending.started) / 60,
            6,
        )
        self.commit()
        return envelope

    def inputs_for(
        self,
        name: str,
        records: dict[str, str],
        command_file: Path | None,
    ) -> list[Path]:
        inputs = [self.plan] if self.plan is not None else []
        dispatch_dir = self.worktree / ".dev" / "records" / "dispatches"
        if name == "check-tests" and "tests" in records:
            inputs.append(dispatch_dir / f"{records['tests']}.json")
        elif name == "tests-fix" and "check-tests" in records:
            record_path = dispatch_dir / f"{records['check-tests']}.json"
            inputs.append(record_path)
            findings_file = self.row("check-tests").get("findings_file")
            if isinstance(findings_file, str):
                inputs.append(Path(findings_file))
        elif name == "code" or name.startswith("code-"):
            inputs.append(self.scope)
            if command_file is not None:
                inputs.append(command_file)
        elif name in {"fix-tests", "fix-code"}:
            for audit in ("security", "adversarial"):
                if audit in records:
                    inputs.append(dispatch_dir / f"{records[audit]}.json")
            if name == "fix-code" and command_file is not None:
                inputs.append(self.scope)
                inputs.append(command_file)
                context = self.make_input(
                    "implementation-records",
                    "implementation records: " + " ".join(self.implementation_markers),
                )
                inputs.append(context)
        elif name == "security-re" and "security" in records:
            inputs.append(dispatch_dir / f"{records['security']}.json")
        return [path for path in inputs if path is not None]

    def execute(
        self,
        name: str,
        records: dict[str, str],
        command_file: Path | None,
        previous: str | None,
        *,
        resume: bool = False,
    ) -> tuple[dict, str]:
        inputs = self.inputs_for(name, records, command_file)
        if resume:
            row = self.row(name)
            if row.get("outcome") == "ok":
                existing = self.existing_result(name)
                if existing is None:
                    raise Stopped(
                        name,
                        str(row.get("dispatch_record") or "none"),
                        "record",
                        detail="completed stage has no accepted dispatch record",
                    )
                pending, _dispatch_record, envelope = existing
                records[name] = pending.record_id
                return envelope, pending.record_id
            existing = self.existing_result(name)
            if existing is not None:
                pending, dispatch_record, envelope = existing
                result = self.finish(pending, already_closed=(dispatch_record, envelope))
                records[name] = pending.record_id
                return result, pending.record_id
            if int(row.get("attempt") or 0) >= 2:
                raise Stopped(
                    name,
                    str(row.get("dispatch_record") or "none"),
                    "retry-cap",
                    detail="stage already reached its two-attempt cap",
                )
        try:
            pending = self.mint(name, inputs, previous)
            records[name] = pending.record_id
            return self.finish(pending), pending.record_id
        except Stopped as stopped:
            if resume and int(self.row(name).get("attempt") or 0) >= 2:
                detail = "\n".join(
                    part
                    for part in (
                        stopped.detail,
                        f"second attempt failed reason={stopped.reason or 'unknown'}",
                    )
                    if part
                )
                raise Stopped(
                    name,
                    stopped.record_id,
                    "retry-cap",
                    detail=detail,
                ) from stopped
            raise

    def mark_skipped(self, name: str, condition: str) -> None:
        row = self.row(name)
        row["condition"] = condition
        row["outcome"] = "skipped"

    def derive_command(self, tests_envelope: dict) -> Path:
        commands: list[str] = []
        artifacts = tests_envelope.get("artifacts")
        if isinstance(artifacts, dict):
            for value in artifacts.values():
                if not isinstance(value, str):
                    continue
                path = Path(value)
                if (
                    path.suffix != ".py"
                    or "tests" not in path.parts[:-1]
                    or re.search(r"[;&|\r\n]", value)
                ):
                    continue
                commands.append(
                    "python3 -m unittest discover "
                    f"-s {shlex.quote(path.parent.as_posix())} "
                    f"-p {shlex.quote(path.name)}"
                )
        if not commands:
            raise Stopped("code", reason="artifacts", detail="no test artifact")
        command = " && ".join(commands)
        if len(command.encode()) > int(self.conf["SCOPE_CAP"]):
            raise Stopped(
                "code",
                reason="scope",
                detail="derived test command exceeds SCOPE_CAP",
            )
        return self.make_input("test-command", command)

    @classmethod
    def strings(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [item for child in value.values() for item in cls.strings(child)]
        if isinstance(value, list):
            return [item for child in value for item in cls.strings(child)]
        return []

    def has_leak(self, envelope: dict) -> bool:
        encoded = json.dumps(envelope, sort_keys=True)
        return any(marker in encoded for marker in self.implementation_markers) or bool(
            re.search(r"implement(?:ation)?[_ -]+envelope", encoded, re.IGNORECASE)
        )

    def verify_custody(
        self,
        name: str,
        inputs: list[Path],
        previous: str | None,
        proof: dict,
    ) -> None:
        chunks = [str(self.scope), self.scope.read_text(encoding="utf-8")]
        for path in inputs:
            chunks.extend((str(path), path.read_text(encoding="utf-8")))
        if previous:
            chunks.append(previous)
        dispatched = "\n".join(chunks)
        missing = [item for item in proof["given"] if item not in dispatched]
        leaked = [item for item in proof["withheld"] if item in dispatched]
        if missing or leaked:
            raise Stopped(
                name,
                reason="withheld",
                detail=f"custody proof failed missing={missing!r} leaked={leaked!r}",
            )

    def audit_pair(
        self,
        records: dict[str, str],
        command_file: Path,
        previous: str,
        *,
        resume: bool = False,
    ) -> tuple[dict, dict, str]:
        if resume:
            security_envelope, security_id = self.execute(
                "security", records, command_file, previous, resume=True
            )
            adversarial_envelope, adversarial_id = self.execute(
                "adversarial", records, command_file, security_id, resume=True
            )
            return security_envelope, adversarial_envelope, adversarial_id
        security = self.mint(
            "security",
            self.inputs_for("security", records, command_file),
            previous,
        )
        records["security"] = security.record_id
        adversarial = self.mint(
            "adversarial",
            self.inputs_for("adversarial", records, command_file),
            security.record_id,
        )
        records["adversarial"] = adversarial.record_id
        first_error: Stopped | None = None
        try:
            security_envelope = self.finish(security)
        except Stopped as error:
            security_envelope = {}
            first_error = error
        try:
            adversarial_envelope = self.finish(adversarial)
        except Stopped:
            if first_error is None:
                raise
            adversarial_envelope = {}
        if first_error is not None:
            raise first_error
        return security_envelope, adversarial_envelope, adversarial.record_id

    def calibrate(self) -> None:
        head = git_out(self.worktree, "rev-parse", "HEAD")
        changed = git(
            self.worktree,
            "diff",
            "--numstat",
            self.record.get("base_sha") or head,
            head,
        ).stdout.splitlines()
        files = len(changed)
        lines = 0
        for raw in changed:
            fields = raw.split("\t", 2)
            if len(fields) >= 2 and fields[0].isdigit() and fields[1].isdigit():
                lines += int(fields[0]) + int(fields[1])
        test_count = sum(1 for raw in changed if "/tests/" in raw or "test_" in raw)
        minutes = {
            row["name"]: float(row.get("minutes") or 0)
            for row in self.record["stages"]
            if row.get("outcome") not in {"pending", "skipped"}
        }
        findings = {
            row["name"]: 0
            for row in self.record["stages"]
            if row.get("verdict") is not None
        }
        slices = self.slices or [{"name": self.buckets[0]["name"], "declared": "S"}]
        self.record["calibration"] = [
            {
                "name": item["name"],
                "declared": item["declared"],
                "measured": {
                    "files": files,
                    "tests": test_count,
                    "lines": lines,
                    "minutes": minutes,
                    "findings": findings,
                },
                "buckets": [
                    {"name": bucket["name"], "declared": bucket["declared"]}
                    for bucket in self.buckets
                ],
            }
            for item in slices
        ]

    def open_pr(self) -> str:
        head = git_out(self.worktree, "rev-parse", "HEAD")
        stage_evidence = []
        open_findings = []
        for stage in self.record["stages"]:
            record_id = stage.get("record") or stage.get("dispatch_record")
            if record_id:
                dispatched = stage.get("dispatched") or {}
                stage_evidence.append(
                    f"- {stage['name']}: record `{record_id}`, model "
                    f"`{dispatched.get('model')}`, effort "
                    f"`{dispatched.get('effort')}`, verdict "
                    f"`{stage.get('verdict')}` — record read at `{head}`"
                )
            if stage.get("verdict") == "changes":
                open_findings.append(f"- Review `{stage['name']}` requested changes.")
        body_text = "\n".join(
            [
                "## What",
                "",
                f"Run the declared audit ladder for `{self.branch}` and open its draft review.",
                f"The branch passed the configured `{self.conf['CHECK_NAMES']}` gate sequence.",
                "",
                "## Sources",
                "",
                "- original",
                f"- scope `{self.scope}`",
                "",
                "## Evidence",
                "",
                f"- Branch head was `{head}` — `git rev-parse HEAD` at `{head}`",
                *stage_evidence,
                "",
                "## For reviewers",
                "",
                *(open_findings or ["- Recheck the stage-selection and custody proofs."]),
            ]
        )
        body = self.make_input(
            "pull-request",
            body_text,
        )
        row = self.row("pr")
        row["attempt"] = 1
        self.commit(body)
        pushed = git(self.worktree, "push", "origin", "--", self.branch)
        if pushed.returncode != 0:
            raise Stopped("pr", reason="push", detail=pushed.stderr.strip())
        argv = [
            self.gh,
            "pr",
            "create",
            "--draft",
            "--base",
            self.conf["TRUNK_BRANCH"],
            "--head",
            self.branch,
            "--repo",
            self.conf["REPO_SLUG"],
            "--title",
            f"Audit ladder {self.record['id']}",
            "--body-file",
            str(body),
        ]
        created = run(argv, self.worktree)
        if created.returncode != 0:
            raise Stopped(
                "pr",
                reason="pr",
                detail=created.stderr.strip() or created.stdout.strip(),
            )
        output = created.stdout.strip().splitlines()
        if not output:
            raise Stopped(
                "pr",
                reason="pr",
                detail="gh pr create returned no URL",
            )
        url = output[-1]
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or any(
            character.isspace() for character in url
        ):
            raise Stopped(
                "pr",
                reason="pr",
                detail="gh pr create returned an invalid URL",
            )
        row["outcome"] = "ok"
        tail = url.rstrip("/").rsplit("/", 1)[-1]
        self.record["pr"] = {
            "number": int(tail) if tail.isdigit() else None,
            "url": url,
        }
        self.record["status"] = "done"
        self.record["stopped"] = None
        self.calibrate()
        self.commit()
        return url

    def run(self, *, resume: bool = False) -> str:
        records = {
            row["name"]: row["dispatch_record"]
            for row in self.record["stages"]
            if row.get("dispatch_record")
        }
        previous: str | None = None
        try:
            if resume:
                self.record["status"] = "running"
                self.record["stopped"] = None
            self.commit()
            tests_envelope, previous = self.execute(
                "tests", records, None, previous, resume=resume
            )
            check_envelope, previous = self.execute(
                "check-tests", records, None, previous, resume=resume
            )
            if check_envelope.get("verdict") == "changes":
                if self.has_leak(check_envelope):
                    raise Stopped("tests-fix", reason="withheld")
                _fixed, previous = self.execute(
                    "tests-fix", records, None, previous, resume=resume
                )
            else:
                self.mark_skipped("tests-fix", "skeptic did not request changes")
            command_file = self.derive_command(tests_envelope)
            for index, _bucket in enumerate(self.buckets, 1):
                name = "code" if index == 1 else f"code-{index}"
                _coded, previous = self.execute(
                    name, records, command_file, previous, resume=resume
                )
            security, adversarial, previous = self.audit_pair(
                records, command_file, previous, resume=resume
            )
            changes = (
                security.get("verdict") == "changes"
                or adversarial.get("verdict") == "changes"
            )
            if changes:
                if self.has_leak(security) or self.has_leak(adversarial):
                    raise Stopped("fix-tests", reason="withheld")
                _test_fix, previous = self.execute(
                    "fix-tests", records, command_file, previous, resume=resume
                )
                _code_fix, previous = self.execute(
                    "fix-code", records, command_file, previous, resume=resume
                )
                security_re, previous = self.execute(
                    "security-re", records, command_file, previous, resume=resume
                )
                if security_re.get("verdict") == "changes":
                    raise Stopped(
                        "security-re",
                        previous,
                        verdict="changes",
                        exit_code=1,
                    )
            else:
                for name in ("fix-tests", "fix-code", "security-re"):
                    self.mark_skipped(name, "audits did not request changes")
            return self.open_pr()
        except Stopped as stopped:
            self.stop(stopped)


def initial_conf_path(cwd: Path) -> Path:
    explicit = os.environ.get("LANE_CONF")
    if explicit:
        return Path(explicit).resolve()
    return (cwd / "ops" / "lane.conf").resolve()


def load_conf(worktree: Path) -> dict[str, str]:
    os.environ["LANE_CONF"] = str(worktree / "ops" / "lane.conf")
    values: dict[str, str] = {}
    for key in CONF_KEYS:
        try:
            values[key] = conf_value(key)
        except Refused as error:
            if key != "CHECK_NAMES" or error.kind != "conf-key":
                raise
            values[key] = conf_value("CHECK_NAME")
    try:
        values["LADDER_WAIT_GRACE"] = conf_value("LADDER_WAIT_GRACE")
    except Refused as error:
        if error.kind != "conf-key":
            raise
        values["LADDER_WAIT_GRACE"] = "300"
    values.update(configuration())
    return values


def validate_preconditions(
    worktree: Path,
    conf: dict[str, str],
    scope: Path,
    agent: str,
    *,
    recovery_record: str | None = None,
) -> str:
    try:
        cap = int(conf["SCOPE_CAP"])
    except ValueError:
        refuse(
            "scope",
            "SCOPE_CAP as a positive whole number",
            conf["SCOPE_CAP"],
            "correct the lane conf",
        )
    size = len(scope.read_bytes())
    if cap < 1 or size > cap:
        refuse(
            "scope",
            f"a readable scope at most {cap} bytes",
            f"{size} bytes at {scope}",
            "supply a bounded readable scope",
        )
    dirty = git(worktree, "status", "--porcelain").stdout.splitlines()
    allowed = (
        f".dev/records/dispatches/{recovery_record}.json"
        if recovery_record
        else None
    )
    unexpected = [
        line
        for line in dirty
        if allowed is None or line[3:].strip().strip('"') != allowed
    ]
    if unexpected:
        refuse(
            "dirty",
            "a clean target worktree",
            f"changes in {worktree}: {' | '.join(unexpected)}",
            "commit or stash them",
        )
    full_identity(agent, "WF_AGENT")
    full_identity(conf["LANE_AUTHOR"], "LANE_AUTHOR")
    name = git_out(worktree, "config", "--get", "user.name")
    email = git_out(worktree, "config", "--get", "user.email")
    full_identity(f"{name} <{email}>", "worktree git identity")
    if shutil.which("gh") is None:
        refuse(
            "gh-missing",
            "an executable gh on PATH",
            "none",
            "install or expose the GitHub CLI",
        )
    jobs_path = worktree / "ops" / "devlane" / "task" / "jobs.json"
    try:
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        refuse("job", "a readable job registry", str(error), "restore jobs.json")
    for _stage, job, _harness, _flag in DISPATCH_STAGES:
        if job not in jobs:
            refuse(
                "job",
                f"job {job} in {jobs_path}",
                "absent",
                "restore the job declaration",
            )
    return agent


def dry_run(driver: Driver) -> int:
    stages: list[dict] = []
    for name, _job, _harness, _flag in DISPATCH_STAGES:
        inputs = [driver.plan] if driver.plan is not None else []
        model, effort, base = driver.resolved(name, inputs, None)
        resolved = run([*base, "--model", model, "--effort", effort, "--dry-run"], driver.worktree)
        payload = parse_dispatch_json(resolved.stdout)
        stages.append({"name": name, "argv": payload["argv"]})
    stages.append(
        {
            "name": "pr",
            "argv": [
                driver.gh,
                "pr",
                "create",
                "--draft",
                "--base",
                driver.conf["TRUNK_BRANCH"],
                "--head",
                driver.branch,
                "--repo",
                driver.conf["REPO_SLUG"],
            ],
        }
    )
    print(json.dumps({"stages": stages}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if not args:
            refuse(
                "arguments",
                "SCOPE BRANCH [PLAN] or resume LADDER_ID",
                "no arguments",
                "choose one documented form",
            )
        cwd = Path.cwd().resolve()
        agent = os.environ.get("WF_AGENT", "")
        resume = args[0] == "resume"
        if resume:
            if len(args) != 2:
                refuse(
                    "arguments",
                    "resume LADDER_ID",
                    " ".join(args),
                    "pass the named record id",
                )
            worktree, record = record_worktree(cwd, args[1])
            branch = record.get("branch")
            if not isinstance(branch, str) or not branch:
                refuse("record", "a named branch", repr(branch), "repair the record")
            current_branch = git_out(worktree, "symbolic-ref", "--short", "HEAD")
            branch_check = git(worktree, "check-ref-format", f"refs/heads/{branch}")
            if branch.startswith("-") or branch_check.returncode != 0 or branch != current_branch:
                refuse(
                    "record",
                    f"the checked-out branch {current_branch}",
                    branch,
                    "repair the record branch",
                )
            scope = recorded_file(worktree, record.get("scope"), "scope")
            plan_data = record.get("plan")
            plan = recorded_file(worktree, plan_data, "plan") if plan_data else None
            recorded_file(worktree, record.get("conf"), "conf")
        else:
            dry = args[0] == "--dry-run"
            positionals = args[1:] if dry else args
            if len(positionals) not in {2, 3}:
                refuse(
                    "arguments",
                    "SCOPE BRANCH [PLAN]",
                    " ".join(args),
                    "choose the documented start form",
                )
            scope = file_arg(positionals[0], "scope")
            branch = positionals[1]
            os.environ["LANE_CONF"] = str(initial_conf_path(cwd))
            root_hint = configuration()["WORKTREE_ROOT"]
            worktree = branch_worktree(cwd, branch, root_hint)
            record = None
            if len(positionals) == 3:
                plan = file_arg(positionals[2], "plan")
            else:
                default_plan = worktree / "plan.md"
                plan = default_plan if default_plan.is_file() else None
        conf = load_conf(worktree)
        validate_preconditions(
            worktree,
            conf,
            scope,
            agent,
            recovery_record=(
                str((record.get("stopped") or {}).get("record") or "") or None
                if resume
                else None
            ),
        )
        driver = Driver(worktree, branch, scope, plan, conf, agent, record)
        if not resume and args[0] == "--dry-run":
            return dry_run(driver)
        url = driver.run(resume=resume)
        print(f"ladder={driver.record['id']} pr={url}")
        return 0
    except Refused as error:
        print(error.line(), file=sys.stderr)
        return 2
    except Stopped as error:
        if error.detail:
            print(error.detail)
        print(error.line())
        return error.exit_code


if __name__ == "__main__":
    sys.exit(main())
