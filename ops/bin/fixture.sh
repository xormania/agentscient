#!/usr/bin/env bash
# fixture.sh — materialize and prove whole-project calibration fixtures.
set -uo pipefail

here=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(CDPATH='' cd -- "$here/../.." && pwd)

exec python3 - "$root" "$@" <<'PY'
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath


ROOT = Path(sys.argv[1]).resolve()
ARGS = sys.argv[2:]
APPS = ROOT / "ops" / "devlane" / "fixtures" / "apps"
IDENTITY = re.compile(r"^(.+?) <([^<>\s]+)>$")
PROBE_TIMEOUT = 2


def refuse(kind: str, expected: str, found: str, needed: str) -> None:
    print(
        f"{kind}: expected {expected}; found {found}; needed {needed}",
        file=sys.stderr,
    )
    raise SystemExit(2)


def abort(expected: str, found: str, needed: str) -> None:
    print(
        f"abort: expected {expected}; found {found}; needed {needed}",
        file=sys.stderr,
    )
    raise SystemExit(3)


def run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None):
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def identity() -> tuple[str, str, str]:
    raw = os.environ.get("WF_AGENT", "")
    match = IDENTITY.fullmatch(raw)
    if match is None:
        refuse(
            "identity",
            "WF_AGENT as Name <address>",
            repr(raw) if raw else "unset",
            "export WF_AGENT with the writing agent identity",
        )
    return raw, match.group(1), match.group(2)


def safe_relative(raw: str) -> str | None:
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts or path == PurePosixPath("."):
        return None
    return path.as_posix().rstrip("/")


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination, follow_symlinks=False)


def inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def make(argv: list[str]) -> int:
    if len(argv) not in {1, 2}:
        refuse("arguments", "make <app> [DIR]", repr(argv), "supply an app and optional target")
    agent, agent_name, agent_email = identity()
    conf_raw = os.environ.get("LANE_CONF", "")
    conf = Path(conf_raw) if conf_raw else None
    if conf is None or not conf.is_file():
        refuse(
            "conf",
            "LANE_CONF naming a readable copy list",
            repr(conf_raw) if conf_raw else "unset",
            "set LANE_CONF to the lane copy-list file",
        )
    copy_roots = [
        line.strip()
        for line in conf.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not copy_roots:
        refuse("conf", "one or more tracked copy paths", "an empty list", "name the lane files to copy")

    app_name = argv[0]
    if safe_relative(app_name) != app_name or "/" in app_name:
        refuse("app", "a fixture app name", repr(app_name), "name a directory below the fixture apps root")
    app_root = APPS / app_name
    if not (app_root / "FAULTS.json").is_file():
        refuse("app", f"{app_name}/FAULTS.json", "no fixture manifest", "choose an app with a manifest")

    listed = run(["git", "ls-files", "-z"], cwd=ROOT)
    if listed.returncode != 0:
        abort("the invoking tracked tree", "git ls-files failed", "restore the repository and retry")
    tracked = [item for item in listed.stdout.split("\0") if item]
    app_prefix = app_root.relative_to(ROOT).as_posix() + "/"
    app_files = [item for item in tracked if item.startswith(app_prefix)]
    if not app_files:
        refuse("app", "a tracked fixture app", f"{app_name} has no tracked files", "commit the app before making it")

    copy_files: set[str] = set()
    for raw in copy_roots:
        rel = safe_relative(raw)
        if rel is None:
            refuse("conf", "repository-relative tracked paths", repr(raw), "remove absolute and parent paths")
        matches = [item for item in tracked if item == rel or item.startswith(rel + "/")]
        if not matches or any(not (ROOT / item).is_file() for item in matches):
            refuse("conf", "every listed path tracked and present", repr(raw), "fix the lane copy list")
        copy_files.update(matches)

    if len(argv) == 2:
        target = Path(argv[1]).expanduser().resolve()
    else:
        state = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
        parent = state / "agentscient" / "fixtures"
        parent.mkdir(parents=True, exist_ok=True)
        target = Path(tempfile.mkdtemp(prefix=f"{app_name}-", dir=parent)).resolve()

    worktrees = run(["git", "worktree", "list", "--porcelain"], cwd=ROOT)
    if worktrees.returncode != 0:
        if len(argv) == 1:
            shutil.rmtree(target, ignore_errors=True)
        abort("the invoking worktree list", "git worktree list failed", "restore the repository and retry")
    roots = [
        Path(line.removeprefix("worktree ")).resolve()
        for line in worktrees.stdout.splitlines()
        if line.startswith("worktree ")
    ]
    if any(inside(target, worktree) for worktree in roots):
        if len(argv) == 1:
            shutil.rmtree(target, ignore_errors=True)
        refuse("target", "DIR outside every invoking worktree", str(target), "choose an external scratch directory")
    if len(argv) == 2 and target.exists():
        refuse("target", "an absent scratch DIR", str(target), "choose a new directory")

    created = len(argv) == 1
    try:
        if not created:
            target.mkdir(parents=True)
            created = True
        expected: set[str] = set()
        for rel in app_files:
            destination = rel.removeprefix(app_prefix)
            copy_file(ROOT / rel, target / destination)
            expected.add(destination)
        for rel in sorted(copy_files):
            copy_file(ROOT / rel, target / rel)
            expected.add(rel)
        present = {
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if path.is_file()
        }
        if present != expected:
            refuse("conf", "the app plus exactly the copy list", repr(sorted(present)), "correct the copy list")

        git_env = os.environ.copy()
        git_env.update(
            {
                "GIT_AUTHOR_NAME": agent_name,
                "GIT_AUTHOR_EMAIL": agent_email,
                "GIT_COMMITTER_NAME": agent_name,
                "GIT_COMMITTER_EMAIL": agent_email,
            }
        )
        steps = [
            ["git", "init", "-b", "fixture-lineage"],
            ["git", "add", "-A"],
            [
                "git",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-m",
                f"fixture: materialize {app_name}",
                "-m",
                f"Source: original\nCo-Authored-By: {agent}",
            ],
        ]
        for step in steps:
            proc = run(step, cwd=target, env=git_env)
            if proc.returncode != 0:
                abort("one fixture commit", proc.stderr.strip() or "git failed", "repair git and retry")
    except SystemExit:
        if created:
            shutil.rmtree(target, ignore_errors=True)
        raise
    except Exception as exc:
        if created:
            shutil.rmtree(target, ignore_errors=True)
        abort("a complete fixture copy", str(exc), "repair the source tree and retry")

    print(target)
    return 0


def load_manifest(directory: Path) -> dict:
    path = directory / "FAULTS.json"
    if not path.is_file():
        refuse("manifest", "DIR/FAULTS.json", "no manifest", "pass a made fixture directory")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        refuse("manifest", "a readable JSON fixture manifest", str(exc), "repair FAULTS.json")
    if not isinstance(data, dict) or not isinstance(data.get("faults"), list):
        refuse("manifest", "an object with a faults list", repr(data), "repair FAULTS.json")
    return data


def patch_fixture(directory: Path, manifest: dict) -> None:
    patches: list[Path] = []
    for fault in manifest["faults"]:
        rel = fault.get("fix") if isinstance(fault, dict) else None
        if not isinstance(rel, str) or safe_relative(rel) is None:
            refuse("fix", "an app-relative patch per fault", repr(rel), "repair the manifest fix path")
        patch = directory / rel
        if not patch.is_file():
            refuse("fix", f"existing patch {rel}", "missing", "restore the planted fix")
        patches.append(patch)

    with tempfile.TemporaryDirectory(prefix="fixture-fix-check-") as tmp:
        trial = Path(tmp) / "app"
        shutil.copytree(directory, trial, ignore=shutil.ignore_patterns(".git"))
        for patch in patches:
            trial_patch = trial / patch.relative_to(directory)
            checked = run(["git", "apply", "--check", str(trial_patch)], cwd=trial)
            if checked.returncode != 0:
                refuse("fix", "every planted patch to apply", checked.stderr.strip() or str(patch), "repair the patch set")
            applied = run(["git", "apply", str(trial_patch)], cwd=trial)
            if applied.returncode != 0:
                refuse("fix", "every planted patch to apply", applied.stderr.strip() or str(patch), "repair the patch set")
    for patch in patches:
        applied = run(["git", "apply", str(patch)], cwd=directory)
        if applied.returncode != 0:
            abort("the preflighted patch set", applied.stderr.strip() or str(patch), "restore the fixture and retry")


def probe(command: str, directory: Path) -> str:
    env = os.environ.copy()
    env.pop("WF_AGENT", None)
    env.pop("LANGUAGE", None)
    env.update({"LC_ALL": "C", "LANG": "C", "TZ": "UTC"})
    try:
        proc = subprocess.Popen(
            command,
            cwd=directory,
            env=env,
            shell=True,
            executable="/bin/sh",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return "UNREACHABLE"
    try:
        code = proc.wait(timeout=PROBE_TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        return "UNREACHABLE"
    if code in {126, 127} or code < 0:
        return "UNREACHABLE"
    return "GREEN" if code == 0 else "RED"


def prove(argv: list[str]) -> int:
    fixed = False
    if argv[:1] == ["--fixed"]:
        fixed = True
        argv = argv[1:]
    if len(argv) != 1:
        refuse("arguments", "prove [--fixed] DIR", repr(argv), "supply one made fixture directory")
    directory = Path(argv[0]).expanduser().resolve()
    manifest = load_manifest(directory)
    if fixed:
        patch_fixture(directory, manifest)

    counts = {"RED": 0, "GREEN": 0, "UNREACHABLE": 0}
    rows: list[tuple[str, str]] = []
    for fault in manifest["faults"]:
        if not isinstance(fault, dict) or not isinstance(fault.get("id"), str) or not isinstance(fault.get("probe"), str):
            refuse("manifest", "fault ids and probe commands", repr(fault), "repair FAULTS.json")
        colour = probe(fault["probe"], directory)
        counts[colour] += 1
        rows.append((fault["id"], colour))
    for fault_id, colour in rows:
        print(f"{fault_id} {colour}")
    print(
        f"red={counts['RED']} green={counts['GREEN']} "
        f"unreachable={counts['UNREACHABLE']}"
    )
    expected = "GREEN" if fixed else "RED"
    return 0 if rows and all(colour == expected for _, colour in rows) else 1


def grade(argv: list[str]) -> int:
    if len(argv) != 2:
        refuse("arguments", "grade <record> <app>", repr(argv), "supply a review record and fixture app")
    identity()
    record = Path(argv[0]).expanduser()
    if not record.is_file():
        refuse("record", "an existing review dispatch record", str(record), "supply its path")
    try:
        payload = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        refuse("record", "a readable JSON review record", str(exc), "repair or replace the record")
    review_jobs = {"security-audit", "adversarial-review"}
    if not isinstance(payload, dict) or payload.get("job") not in review_jobs:
        refuse("record", "a security-audit or adversarial-review record", repr(payload.get("job") if isinstance(payload, dict) else payload), "supply a review record")
    app = APPS / argv[1]
    if safe_relative(argv[1]) != argv[1] or "/" in argv[1] or not (app / "FAULTS.json").is_file():
        refuse("app", f"{argv[1]}/FAULTS.json", "no fixture manifest", "choose an app with a manifest")
    abort("grading semantics from run B", "wire-only grade in run A", "land the grading implementation")


if not ARGS:
    refuse("arguments", "fixture.sh <make|prove|grade> ...", "no verb", "choose a verb")
verb, tail = ARGS[0], ARGS[1:]
if verb == "make":
    raise SystemExit(make(tail))
if verb == "prove":
    raise SystemExit(prove(tail))
if verb == "grade":
    raise SystemExit(grade(tail))
refuse("arguments", "make, prove, or grade", repr(verb), "choose a supported verb")
PY
