#!/usr/bin/env python3
"""A Skill invocation logs a use in the skills registry.

PreToolUse hook on the Skill tool. Until 2026-09-13 a use was counted
only when a session typed `skills.py log-use` by hand, so the report's
use column was a floor: 12 close, 7 deliverable, 6 onboard, zero for
thirteen skills, and no way to tell an unused page from an unlogged one.
This hook records every invocation with the skill's name and its
arguments, the same event the hand command writes.

Best effort by construction, the shape of miss.py: the call is always
allowed (exit 0, no output). A registry without the row, a missing
lever, an unwritable store, a timeout or a malformed payload each log
nothing and change nothing. Identity is the session's WF_AGENT when the
hook inherits one, else the hook signs as itself with the lane's name.

Written by hand under grant 208 (owner, 2026-09-13: "hand grant ok'd for
new skills #1-4 - do them in one PR"); the test is
ops/devlane/hooks/tests/test_skill_use.py, under wall grant 209.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

SKILLS_LEVER = "ops/conductor/tools/skills.py"
DETAIL_CAP = 400
TIMEOUT = 10
HOOK = "skill-use"
CATALOGUE_CAP = 6000


def use_command(source, name="NAME"):
    """The same pinned owner serves every client; no shell interception."""
    return shlex.join(["python3", str(Path(source) / SKILLS_LEVER), "use", name])


def managed_page(owner, source, name, *, pins):
    return checked_page(owner.load_skill(name), source, name, pins=pins)


def checked_page(page, source, name, *, pins):
    """Check the owner response against this installed source boundary."""
    root = Path(source).resolve(strict=True)
    path = Path(page["path"])
    if (page["name"] != name or page["status"] != "active" or not path.is_absolute()
            or path.name != "SKILL.md" or path.resolve(strict=True) != path
            or not path.is_relative_to(root)
            or not isinstance(pins, dict) or pins.get(str(path)) != page["sha256"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != page["sha256"]):
        raise ValueError("managed skill is not an active canonical source")
    return page


def recovery(result, owner, source, *, mode):
    """Observe a final policy refusal without changing its authority decision.

    The existing miss owner maps classes; skills.py owns state, attribution and
    redaction. No caller-cwd script runs. A failed event never changes a refusal.
    """
    # record_event may resolve/register a page on a fresh host. Workers have
    # no operator page pins, so neither recovery nor its event owner is reached.
    if mode != "interactive":
        return result
    import miss
    klass = result.get("policy_class")
    if result["outcome"] == "allow" or not klass or klass in {"hook-error", "hook-input"}:
        return result
    name = miss.skill_for(klass)
    record_miss(owner, klass, result["reason"])
    return {**result, "reason": result["reason"] + " Recovery: " + use_command(source, name)
            + "; follow the refusal's needed remedy; this does not grant permission."}


def record_miss(owner, klass, found):
    """Reuse the miss mapping for ordinary refusals and the engine's cap event."""
    import miss
    detail = f"{klass}: {miss.found_clause(found)}"[:DETAIL_CAP]
    try:
        owner.record_event("miss", miss.skill_for(klass), detail)
        return True
    except Exception:  # noqa: BLE001 - telemetry must never replace the policy result
        return False


def startup(owner, source, *, pins):
    """A bounded, read-only projection of the existing managed catalogue."""
    command = use_command(source)
    header = ("Managed project skills (interactive session): " + command
              + ". It returns instructions and records the invocation; skip duplicate manual log-use. "
                "Read and follow the returned page when relevant; discovery itself records no use.\n")
    try:
        rows = owner.managed_catalog()
        if not isinstance(rows, list):
            raise ValueError("invalid managed catalogue")
        active = [row for row in rows if row["status"] == "active"]
        lines = []
        used = len(header)
        for row in sorted(active, key=lambda item: item["name"]):
            # The catalogue owner already resolved every page in one reading;
            # do not rescan that entire catalogue via load_skill for each row.
            page = checked_page(row, source, row["name"], pins=pins)
            # Native advisory text must not carry terminal or bidi controls.
            name = "".join(c for c in page["name"] if c.isprintable())
            description = "".join(c if c.isprintable() else " " for c in page["description"])
            line = name + ": " + " ".join(description.split())[:160]
            if used + len(line) + 100 > CATALOGUE_CAP:
                break
            lines.append(line)
            used += len(line) + 1
        if not active:
            lines.append("No active registered managed skills.")
        elif len(lines) < len(active):
            lines.append(f"{len(active) - len(lines)} additional active skills omitted from this compact reminder.")
        return header + "\n".join(lines)
    except Exception as error:  # noqa: BLE001 - unavailable advisory is explicit, not a policy allow
        return header + f"Managed catalogue unavailable ({type(error).__name__}); inspect the skills owner."


def skill_and_args(payload):
    """The skill name and its arguments from a Skill call, else None."""
    if not isinstance(payload, dict) or payload.get("tool_name") != "Skill":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    name = tool_input.get("skill") or tool_input.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    args = tool_input.get("args")
    detail = " ".join(str(args).split()) if isinstance(args, str) and args.strip() else ""
    return name.strip(), (detail or "(no arguments)")[:DETAIL_CAP]


def log_use(cwd, name, detail):
    """Record one invocation; never raise, never block."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from matrix import lane_conf, repo_root
        root = repo_root(cwd or os.getcwd())
        lane = lane_conf(root).get("LANE_NAME") if root else None
        if not root or not lane:
            return False
        lever = os.path.join(root, SKILLS_LEVER)
        if not os.path.isfile(lever):
            return False
        env = dict(os.environ)
        if not env.get("WF_AGENT"):
            env["WF_AGENT"] = f"{HOOK} hook <{HOOK}@{lane}>"
        proc = subprocess.run(  # noqa: S603 - fixed argv, the lane's own lever
            [sys.executable, lever, "log-use", name, detail],
            cwd=root, env=env, capture_output=True, text=True,
            timeout=TIMEOUT, check=False,
        )
        return proc.returncode == 0
    except Exception:  # noqa: BLE001 - a use that cannot be logged never blocks the call
        return False


def main():
    try:
        payload = json.loads(sys.stdin.read() or "null")
    except ValueError:
        return 0
    found = skill_and_args(payload)
    if found is None:
        return 0
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    log_use(cwd, *found)
    return 0


if __name__ == "__main__":
    sys.exit(main())
