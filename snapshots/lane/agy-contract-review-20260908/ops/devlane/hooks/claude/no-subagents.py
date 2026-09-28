#!/usr/bin/env python3
"""Refuse in-session delegation through Claude's blocking hook channel.

PreToolUse hook. Sub-agents spawned inside a session burn the session's
context and leave no record a later actor can read; the lane's dispatch
leaves a snapshot, a run record, and a commit. So the only delegation
path is the launcher, and this hook says so at the moment of the call.

Exit 2 with the reason on stderr refuses the tool; exit 0 lets it run.
Malformed input is let through — a hook that fails takes the session
with it, and refusing on junk would refuse the wrong thing.
"""

import json
import sys

REFUSED = ("Agent", "Workflow", "Task")
DELEGATION_PATH = "ops/devlane/dispatch/launch.py"
REASON = (
    "Refused: in-session sub-agents are off in this repository. "
    f"The only delegation path is {DELEGATION_PATH}, pulled through "
    "ops/bin/dispatch.sh or ops/bin/go.sh — run a stage there instead."
)


def decide(payload):
    """Return the refusal reason for a refused tool, otherwise None."""
    if not isinstance(payload, dict):
        return None
    return REASON if payload.get("tool_name") in REFUSED else None


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    reason = decide(payload)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
