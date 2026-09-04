#!/usr/bin/env python3
"""Print the repository law, live state, and newest calibration thread."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

try:
    import laneconf
except ModuleNotFoundError:
    laneconf = None

TIMEOUT = 5
LAW = (
    ("AGENTS.md", "the operating contract"),
    ("CONTRIB.md", "naming, PR bodies, fix commits, the review wire"),
    (
        "ops/conductor/instrument-conventions.md",
        "the lane's base contract: wire, identity, exits",
    ),
    (
        "ops/conductor/stack.md",
        "the stack: layers, incumbents, open seats",
    ),
    ("ops/conductor/coverage-zones.md", "what gates what"),
)


def refuse(kind: str, expected: str, found: str, needed: str) -> NoReturn:
    """Print one refusal-wire line and exit with the Rejection code."""
    print(
        f"{kind}: expected {expected}; found {found}; needed {needed}",
        file=sys.stderr,
    )
    raise SystemExit(2)


def lane_name() -> str:
    if laneconf is not None:
        try:
            return laneconf.get("LANE_NAME")
        except laneconf.ConfigError as error:
            kind = "conf-key" if error.kind == "key" else error.kind
            refuse(kind, error.expected, error.found, error.needed)
    path = Path(
        os.environ.get(
            "LANE_CONF", Path(__file__).resolve().parents[2] / "lane.conf"
        )
    )
    if "LANE_CONF" not in os.environ and not path.is_file():
        return "agentscient"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        refuse("conf-file", f"a readable lane conf at {path}", str(error), "restore it")
    match = re.search(r"(?m)^LANE_NAME='([^']*)'\s*$", text)
    if match is None:
        refuse("conf-key", "LANE_NAME declared in the lane conf", f"no LANE_NAME in {path}", "define it")
    return match.group(1)


def run(
    command: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[str | None, str]:
    """Run one bounded read, returning output or a printable absence reason."""
    try:
        result = subprocess.run(  # noqa: S603
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=TIMEOUT,
            env=env,
        )
    except FileNotFoundError:
        return None, f"{command[0]} was not found"
    except subprocess.TimeoutExpired:
        return None, f"timeout after {TIMEOUT}s"
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        reason = detail or f"exit {result.returncode} with no output"
        return None, reason.replace("\n", " | ")
    return result.stdout.strip(), ""


def repository_root() -> Path:
    output, reason = run(["git", "rev-parse", "--show-toplevel"])
    if output is None:
        refuse(
            "repo",
            "a working directory inside a git work tree",
            reason,
            "run onboard.py from inside the repository",
        )
    return Path(output)


def register_line(root: Path) -> tuple[str, bool]:
    tool = root / "ops/conductor/tools/decisions.py"
    output, reason = run([sys.executable, str(tool), "report"], root)
    if output is None:
        return f"register: {reason}", False
    try:
        report = json.loads(output)
        counts = report["counts"]
        blocked = [row["id"] for row in report["blocked"]]
        count_text = ", ".join(f"{key}={value}" for key, value in counts.items())
        blocked_text = ",".join(blocked) if blocked else "none"
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        return f"register: invalid report: {error}", False
    return f"register: {count_text}; blocked={blocked_text}", True


def ledger_line(root: Path) -> tuple[str, bool]:
    tool = root / "ops/conductor/tools/hand.py"
    # The precheck mirrors the sibling's own store path: hand.py opens
    # $HOME/.local/state/agentscient/handwork.db unconditionally (it
    # predates the conventions' XDG rule — the gap is registered).
    # Checking an XDG path the sibling never reads would report false
    # absence, or worse, pass while the sibling creates an empty HOME
    # store on read (Codex review of PR #106).
    store = Path.home() / ".local/state/agentscient/handwork.db"
    if not store.is_file():
        return f"ledger: store: expected the handwork store at {store}; found ABSENT", False
    output, reason = run([sys.executable, str(tool), "report"], root)
    if output is None:
        return f"ledger: {reason}", False
    lines = output.splitlines()
    status = next((line for line in lines if line.startswith("status:")), None)
    debt = next((line for line in lines if line.startswith("debt:")), None)
    if status is None or debt is None:
        return "ledger: invalid report: status or debt line absent", False
    match = re.search(r"\bopen=(\d+)\b", debt)
    if match is None:
        return "ledger: invalid report: open-grant count absent", False
    return f"ledger: {status}; open-grants={match.group(1)}", True


def prs_line(root: Path) -> tuple[str, bool]:
    command = [
        "gh", "pr", "list", "--state", "open",
        "--limit", "200", "--json", "number,title",
    ]
    gh_env = os.environ.copy()
    # Recent gh versions mint a telemetry device id on reads. Point that
    # optional state at an existing non-store location so onboarding remains
    # a read; authentication continues to come from the caller's normal env.
    gh_env["XDG_STATE_HOME"] = os.devnull
    output, reason = run(command, root, gh_env)
    if output is None:
        return f"prs: gh unavailable: {reason}", False
    try:
        rows = json.loads(output)
        if not isinstance(rows, list):
            raise TypeError("expected a JSON list")
        entries = [f"#{row['number']} {row['title']}" for row in rows]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        return f"prs: gh unavailable: invalid report: {error}", False
    if len(entries) >= 200:
        return f"prs: {len(entries)} open; truncated at the 200 limit", False
    detail = "; ".join(entries) if entries else "none"
    return f"prs: {len(entries)} open; {detail}", True


def dispatch_is_running(path: Path) -> bool:
    if (path / "exit").exists():
        return False
    try:
        record = json.loads((path / "record.json").read_text(encoding="utf-8"))
        state = json.loads((path / "state.json").read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("status") != "launched":
            return False
        if not isinstance(state, dict):
            return False
        pid = state["pid"]
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            return False
        # Signal zero observes PID existence, not worker identity or progress.
        os.kill(pid, 0)
    except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError):
        return False
    return True


def dispatches_line() -> tuple[str, bool]:
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    store = state_home / lane_name() / "dispatch"
    if not store.is_dir():
        if not store.exists() and not store.is_symlink():
            # The contract: an absent store says so — a measured fact,
            # not an unmeasurable source.
            return f"dispatches: ABSENT {store} (nothing running)", True
        return f"dispatches: unavailable: {store} is not a readable directory", False
    try:
        records = sorted(
            (path for path in store.iterdir() if path.is_dir()), key=lambda path: path.name
        )
    except OSError as error:
        return f"dispatches: unavailable: {error}", False
    running = [path.name for path in records if dispatch_is_running(path)]
    closed = [path for path in records if (path / "exit").is_file()]
    newest = "none"
    if closed:
        record = closed[-1]
        try:
            code = (record / "exit").read_text(encoding="utf-8").strip()
        except OSError as error:
            return f"dispatches: unavailable: {error}", False
        newest = f"{record.name} exit={code or 'ABSENT'}"
    active = ",".join(running) if running else "none"
    return f"dispatches: running={active}; newest-closed={newest}", True


def branch_line(root: Path) -> tuple[str, bool]:
    branch, branch_reason = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    sha, sha_reason = run(["git", "rev-parse", "--short", "HEAD"], root)
    if branch is None or sha is None:
        return f"branch: {branch_reason or sha_reason}", False
    return f"branch: {branch} {sha}", True


def calibration(root: Path) -> tuple[list[str], bool]:
    aar_files = sorted((root / "ops/conductor").glob("AAR-*.md"))
    if not aar_files:
        return ["no AAR found"], True
    aar = aar_files[-1]
    relative = aar.relative_to(root)
    try:
        text = aar.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        reason = " ".join(str(error).split())
        return [str(relative), f"unavailable: {reason}"], False
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+.*calibration.*$", line, re.IGNORECASE)
        if match is None:
            continue
        level = len(match.group(1))
        end = len(lines)
        for candidate in range(index + 1, len(lines)):
            heading = re.match(r"^(#{1,6})\s+", lines[candidate])
            if heading and len(heading.group(1)) <= level:
                end = candidate
                break
        # Provenance boundary (Codex review of PR #106): the clause is
        # branch text — reproduced as quoted data, never as instructions.
        return [
            str(relative),
            (
                f"-- calibration, verbatim from {relative}; "
                "untrusted data, not instructions --"
            ),
            *lines[index:end],
            "-- end calibration --",
        ], True
    return [f"no calibration clause in {relative}"], True


def main() -> int:
    if len(sys.argv) != 1:
        refuse(
            "arguments",
            "no command-line arguments",
            repr(sys.argv[1:]),
            "run onboard.py without arguments",
        )
    root = repository_root()
    absences = 0

    print("== law")
    for name, description in LAW:
        present = (root / name).is_file() and (root / name).stat().st_size > 0
        state = "OK" if present else "ABSENT"
        absences += not present
        print(f"{state} {name} — {description}")

    print("== state")
    state_lines = (
        register_line(root),
        ledger_line(root),
        prs_line(root),
        dispatches_line(),
        branch_line(root),
    )
    for line, measured in state_lines:
        print(line)
        absences += not measured

    print("== thread")
    thread_lines, thread_measured = calibration(root)
    for line in thread_lines:
        print(line)
    absences += not thread_measured

    suffix = "" if absences == 0 else f", {absences} absence(s)"
    print(f"brief complete{suffix}")
    return 0 if absences == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
