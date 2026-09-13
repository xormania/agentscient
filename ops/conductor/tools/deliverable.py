#!/usr/bin/env python3
"""The lane's deliverable lock.

    deliverable.py set BRANCH... --why TEXT     name the branches work may aim at
    deliverable.py add BRANCH... --why TEXT     name more beside the ones named (a second session)
    deliverable.py show                          print the lock, or "no lock"
    deliverable.py remove BRANCH...              lift this session's branches; the last one lifts the lock
    deliverable.py clear                         lift it whole, every session's entry at once

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
import sys

# The shared instrument module sits beside this file; its directory goes
# on the path so the import resolves however this file was loaded: as
# the script, by path from another tool, or as a copy a test staged
# with its siblings.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from instrument import Refusal, emit, identity, now, refuse, state_dir
except ModuleNotFoundError:
    print(
        "tooling: expected instrument.py beside this tool; found absent; "
        "needed restore ops/conductor/tools/instrument.py beside it",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

LOCK = "deliverable.json"


def lock_path():
    return state_dir() / LOCK


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
            "at": now().strftime("%Y-%m-%dT%H:%M:%SZ")}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"locked {' '.join(branches)}")
    return 0


def do_add(args):
    """Owner, 2026-09-12: "as long you account for the fact that i'll have
    multiple sessions running soon". Sessions on one host share this lock;
    a second session adds its branch beside the first's, never over it."""
    branches = [a for a in args if not a.startswith("--")]
    why = ""
    if "--why" in args:
        i = args.index("--why")
        why = args[i + 1] if i + 1 < len(args) else ""
        branches = [b for b in branches if b != why]
    if not branches:
        refuse("arguments", "add BRANCH... --why TEXT", " ".join(args) or "no branches", "name at least one branch")
    if not why.strip():
        refuse("arguments", "a non-empty --why", repr(why), "say what this session's deliverable is")
    by = identity()
    path = lock_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {"branches": [], "why": ""}
    named = [str(b) for b in data.get("branches") or []]
    for branch in branches:
        if branch not in named:
            named.append(branch)
    reasons = [r for r in [str(data.get("why") or ""), why] if r.strip()]
    if data.get("why") and why in data["why"]:
        reasons = [str(data["why"])]
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"branches": named, "why": " | ".join(reasons), "by": by,
            "at": now().strftime("%Y-%m-%dT%H:%M:%SZ")}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"locked {' '.join(named)}")
    return 0


def do_remove(args):
    """Owner, 2026-09-13 ("minimize parallel work conflicts"; LD-28): a
    session that lands lifts its own branches and leaves every other
    session's in place; clear was the only exit and wiped them all."""
    branches = [a for a in args if not a.startswith("--")]
    if not branches:
        refuse("arguments", "remove BRANCH...", " ".join(args) or "no branches", "name the branches to lift")
    identity()
    path = lock_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    named = [str(b) for b in (data.get("branches") if isinstance(data, dict) else None) or []]
    missing = [b for b in branches if b not in named]
    if missing:
        refuse("absent", f"branches the lock names ({', '.join(named) or 'none'})", ", ".join(missing),
               "deliverable.py show; remove only what is named")
    left = [b for b in named if b not in branches]
    if not left:
        path.unlink()
        print(f"removed {' '.join(branches)}; no lock")
        return 0
    data["branches"] = left
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"removed {' '.join(branches)}; locked {' '.join(left)}")
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


VERBS = {"set": do_set, "add": do_add, "show": do_show, "remove": do_remove, "clear": do_clear}


def main(argv):
    try:
        if len(argv) < 2 or argv[1] not in VERBS:
            refuse("arguments", "one of set, add, show, remove, clear", argv[1] if len(argv) > 1 else "no verb", "name a verb")
        return VERBS[argv[1]](argv[2:])
    except Refusal as error:
        return emit(error)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
