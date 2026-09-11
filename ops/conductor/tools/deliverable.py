#!/usr/bin/env python3
"""The lane's deliverable lock.

    deliverable.py set BRANCH... --why TEXT     name the branches work may aim at
    deliverable.py show                          print the lock, or "no lock"
    deliverable.py clear                         lift it

Owner, 2026-09-11: "i want an immediate FIX to stop that - right fucking
now." While the lock names branches, the check matrix refuses any new
worktree or branch, dispatch, ladder start or PR creation aimed at a
branch not named. Several branches may be named: parallel work is
untouched; unnamed work is. Findings met on the way go to the ledger.
Writing verbs need an identity; reads never do. Refusals are one stderr
line, exit 2, stdout empty.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

IDENTITY = re.compile(r"[^<>\n]+ <[^<>\s@]+@[^<>\s]+>")
LOCK = "deliverable.json"


class Refused(Exception):
    pass


def refuse(kind, expected, found, needed):
    raise Refused(f"{kind}: expected {expected}; found {found}; needed {needed}")


def lane_name():
    path = Path(os.environ.get("LANE_CONF", Path(__file__).resolve().parents[2] / "lane.conf"))
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        refuse("conf-file", f"a readable lane conf at {path}", str(error), "restore it")
    match = re.search(r"(?m)^LANE_NAME='([^']*)'\s*$", text)
    if match is None:
        refuse("conf-key", "LANE_NAME declared in the lane conf", f"no LANE_NAME in {path}", "define it")
    return match.group(1)


def lock_path():
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    return Path(state) / lane_name() / LOCK


def identity():
    value = os.environ.get("WF_AGENT", "")
    if not IDENTITY.fullmatch(value):
        refuse("identity", "WF_AGENT in the Name <address> form", value or "unset",
               "export WF_AGENT='Your Model Name <noreply@vendor>'")
    return value


def do_set(args):
    branches = [a for a in args if not a.startswith("--")]
    why = ""
    if "--why" in args:
        i = args.index("--why")
        why = args[i + 1] if i + 1 < len(args) else ""
        branches = [b for b in branches if b != why]
    if not branches:
        refuse("arguments", "set BRANCH... --why TEXT", " ".join(args) or "no branches", "name at least one branch")
    if not why.strip():
        refuse("arguments", "a non-empty --why", repr(why), "say what the deliverable is")
    by = identity()
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"branches": branches, "why": why, "by": by,
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"locked {' '.join(branches)}")
    return 0


def do_show(_args):
    path = lock_path()
    try:
        print(path.read_text(encoding="utf-8").rstrip())
    except OSError:
        print("no lock")
    return 0


def do_clear(_args):
    identity()
    path = lock_path()
    try:
        path.unlink()
    except FileNotFoundError:
        print("no lock")
        return 0
    print("cleared")
    return 0


VERBS = {"set": do_set, "show": do_show, "clear": do_clear}


def main(argv):
    try:
        if len(argv) < 2 or argv[1] not in VERBS:
            refuse("arguments", "one of set, show, clear", argv[1] if len(argv) > 1 else "no verb", "name a verb")
        return VERBS[argv[1]](argv[2:])
    except Refused as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
