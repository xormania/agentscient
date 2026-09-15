#!/usr/bin/env python3
"""Print the repository law, live state, and the handoff board."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# The shared instrument module sits beside this file; its directory goes
# on the path so the import resolves however this file was loaded: as
# the script, by path from another tool, or as a copy a test staged
# with its siblings.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from instrument import Refusal, emit, lane_name, refuse
except ModuleNotFoundError:
    print(
        "tooling: expected instrument.py beside this tool; found absent; "
        "needed restore ops/conductor/tools/instrument.py beside it",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

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
    ("ops/conductor/discovery-lever.md", "profile discovery, source custody, and uncertainty"),
    ("ops/conductor/conductor-start-plan.md", "the conductor startup sequence and admission boundaries"),
)


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


def lock_lines(root: Path) -> tuple[list[str], bool]:
    """The deliverable lock as deliverable.py show prints it: the branches
    and the owner's words on one line, then every target with its live
    reading (owner, 2026-09-15: a brief that never printed the lock let a
    plan's paraphrase of the order stand in for the order)."""
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    lock = state_home / lane_name() / "deliverable.json"
    if not lock.is_file():
        # Checked before the lever runs: a read never creates the state
        # directory (the doctor's read-only probe reads it that way).
        return ["lock: none"], True
    tool = root / "ops/conductor/tools/deliverable.py"
    output, reason = run([sys.executable, str(tool), "show"], root)
    if output is None:
        return [f"lock: unavailable: {reason}"], False
    if output.strip() == "no lock":
        return ["lock: none"], True
    lines = output.splitlines()
    targets = [line for line in lines if line.startswith("target ")]
    body = "\n".join(line for line in lines if not line.startswith("target "))
    try:
        data = json.loads(body)
        branches = ", ".join(str(b) for b in data.get("branches") or []) or "nothing"
        why = str(data.get("why") or "").strip() or "no why"
    except (json.JSONDecodeError, AttributeError) as error:
        return [f"lock: invalid report: {error}"], False
    return [f"lock: {branches} — {why}", *targets], True


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


def handoffs_lines(root: Path) -> tuple[list[str], bool]:
    """The handoff manager's brief, or a measured absence. The store is
    checked before the sibling runs: a read must never create it."""
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    store = state_home / lane_name() / "state.db"
    if not store.is_file():
        return [f"handoffs: ABSENT {store} (none recorded)"], True
    tool = root / "ops/conductor/tools/handoff.py"
    output, reason = run([sys.executable, str(tool), "brief"], root)
    if output is None:
        return [f"handoffs: unavailable: {reason}"], False
    lines = output.splitlines()
    if not lines or not lines[0].startswith("handoffs:"):
        return ["handoffs: invalid report: the brief does not open with handoffs:"], False
    return lines, True


def branch_line(root: Path) -> tuple[str, bool]:
    branch, branch_reason = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    sha, sha_reason = run(["git", "rev-parse", "--short", "HEAD"], root)
    if branch is None or sha is None:
        return f"branch: {branch_reason or sha_reason}", False
    return f"branch: {branch} {sha}", True


def main() -> int:
    try:
        return brief()
    except Refusal as refusal:
        return emit(refusal)


def brief() -> int:
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
    lock, lock_measured = lock_lines(root)
    for line in lock:
        print(line)
    absences += not lock_measured

    print("== handoffs")
    handoff_lines, handoffs_measured = handoffs_lines(root)
    for line in handoff_lines:
        print(line)
    absences += not handoffs_measured

    suffix = "" if absences == 0 else f", {absences} absence(s)"
    print(f"brief complete{suffix}")
    return 0 if absences == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
