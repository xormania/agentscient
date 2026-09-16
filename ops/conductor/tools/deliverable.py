#!/usr/bin/env python3
"""The lane's deliverable lock.

    deliverable.py set BRANCH... --why TEXT [--measure CMD --until TEXT]
                                                 name the branches work may aim at, and the target
    deliverable.py add BRANCH... --why TEXT [--measure CMD --until TEXT]
                                                 name more beside the ones named (a second session)
    deliverable.py show                          print the lock, or "no lock"; each target with its
                                                 live reading and met or short
    deliverable.py done BRANCH                   run the target's measure: print the reading when it
                                                 carries the --until text, else refuse `target`
    deliverable.py remove BRANCH... [--unmet TEXT]
                                                 lift this session's branches; a short target refuses
                                                 without the reason; the last one lifts the lock
    deliverable.py clear                         lift it whole, every session's entry at once

Owner, 2026-09-11: "i want an immediate FIX to stop that - right fucking
now." While the lock names branches, the check matrix refuses any new
worktree or branch, dispatch, ladder start or PR creation aimed at a
branch not named. Several branches may be named: parallel work is
untouched; unnamed work is. Findings met on the way go to the ledger.
Writing verbs need an identity; reads never do. Refusals are one stderr
line, exit 2, stdout empty.

The target (owner, 2026-09-15, on a session that reported a plan's
slices all done with 210 of 226 test modules still off the kit:
"whatever it says - is the problem we to solve - right fucking now"):
"done" was measured against the named work, never against the owner's
target, and no gate had a floor. A target is a measure command and the
text its output must carry; show prints the reading beside the target
every time the lock is read, done is the reading and nothing else, and a
branch is not lifted while its target is short unless the reason is
said. A measure that cannot run reads unreachable, never met.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shlex
import sys

# The shared instrument module sits beside this file; its directory goes
# on the path so the import resolves however this file was loaded: as
# the script, by path from another tool, or as a copy a test staged
# with its siblings.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from instrument import Refusal, emit, identity, now, refuse, run, state_dir
except ModuleNotFoundError:
    print(
        "tooling: expected instrument.py beside this tool; found absent; "
        "needed restore ops/conductor/tools/instrument.py beside it",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

LOCK = "deliverable.json"
GUARD = "deliverable.json.lock"
MEASURE_TIMEOUT = 120
# The measure runs from the root of the checkout whose lever runs it, so a
# census written against relative paths reads one tree from any cwd.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def option(args, name):
    """The value after ``name`` in args, or None when the flag is absent."""
    if name not in args:
        return None
    i = args.index(name)
    return args[i + 1] if i + 1 < len(args) else ""


def positional(args, *flags):
    """The arguments that are neither a flag nor a flag's value."""
    values = {option(args, f) for f in flags}
    out = []
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a in flags:
            skip = True
            continue
        if a.startswith("--") or a in values:
            continue
        out.append(a)
    return out


def target_of(args):
    """(measure, until) from --measure and --until, both or neither."""
    measure, until = option(args, "--measure"), option(args, "--until")
    if (measure is None) != (until is None):
        refuse("arguments", "--measure CMD and --until TEXT together",
               f"measure={measure!r} until={until!r}", "give both, or neither")
    if measure is not None and not (measure.strip() and until.strip()):
        refuse("arguments", "a non-empty --measure and --until", f"measure={measure!r} until={until!r}",
               "name the command and the text its output must carry")
    return (measure, until) if measure is not None else None


def reading(target):
    """(met, line) for a target: the measure's first line carrying the
    until text when met, else its first non-empty line; a measure that
    cannot run, or exits non-zero, reads unreachable and is never met."""
    try:
        proc = run(shlex.split(target["measure"]), cwd=REPO_ROOT, timeout=MEASURE_TIMEOUT)
    except (Refusal, ValueError) as error:
        return False, f"unreachable ({error})"
    if proc.returncode != 0:
        return False, f"unreachable (exit {proc.returncode})"
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    for line in lines:
        if target["until"] in line:
            return True, line
    return False, (lines[0] if lines else "no output")


def target_line(branch, target):
    met, line = reading(target)
    owner = f" (by {target['by']})" if target.get("by") else ""
    return (f"target {branch}: until {target['until']}; reading {line}; "
            f"{'met' if met else 'short'}{owner}")


def lock_path():
    return state_dir() / LOCK


@contextlib.contextmanager
def held():
    """The lock's path, with an exclusive flock held on deliverable.json.lock
    beside it. Sessions on one host share the lock, and every writer reads,
    changes and writes it inside this, so two writers never interleave: a
    concurrent remove and add lost a branch in 3 of 60 trials without it
    (Grok, dispatch 20260913T105222Z-review-grok-00b782, finding 2)."""
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(GUARD), "a+", encoding="utf-8") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        yield path


def write(path, data):
    """Replace the lock whole, so a reader never sees half a file."""
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(part, path)


def do_set(args):
    """T-71: a lead session ran set for its closing AAR and the lock then
    read one measure against all three branches it named, so two other
    sessions read short against a target that was never theirs -- and a
    branch left unnamed was dropped from the lock outright. set re-targets
    branches the lock already names and touches nothing else; add is the
    verb that introduces one. On no lock, set still writes the first."""
    branches = positional(args, "--why", "--measure", "--until")
    why = option(args, "--why") or ""
    if not branches:
        refuse("arguments", "set BRANCH... --why TEXT", " ".join(args) or "no branches", "name at least one branch")
    if not why.strip():
        refuse("arguments", "a non-empty --why", repr(why), "say what the deliverable is")
    target = target_of(args)
    by = identity()
    stamp = now().strftime("%Y-%m-%dT%H:%M:%SZ")
    with held() as path:
        try:
            held_data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            held_data = {}
        if not isinstance(held_data, dict):
            held_data = {}
        named = [str(b) for b in (held_data.get("branches") or [])]
        targets = dict(held_data.get("targets") or {})
        if named:
            missing = [b for b in branches if b not in named]
            if missing:
                refuse("absent", f"branches the lock names ({', '.join(named)})", ", ".join(missing),
                       "deliverable.py add <branch> names a new session's branch beside these")
            reasons = [r for r in [str(held_data.get("why") or ""), why] if r.strip()]
            if held_data.get("why") and why in held_data["why"]:
                reasons = [str(held_data["why"])]
            data = {"branches": named, "why": " | ".join(reasons),
                    "by": held_data.get("by") or by,
                    "at": held_data.get("at") or stamp}
        else:
            named = list(branches)
            data = {"branches": named, "why": why, "by": by, "at": stamp}
        if target:
            for branch in branches:
                targets[branch] = {"measure": target[0], "until": target[1],
                                   "by": by, "at": stamp}
        if targets:
            data["targets"] = targets
        write(path, data)
    print(f"locked {' '.join(named)}")
    return 0


def do_add(args):
    """Owner, 2026-09-12: "as long you account for the fact that i'll have
    multiple sessions running soon". Sessions on one host share this lock;
    a second session adds its branch beside the first's, never over it."""
    branches = positional(args, "--why", "--measure", "--until")
    why = option(args, "--why") or ""
    if not branches:
        refuse("arguments", "add BRANCH... --why TEXT", " ".join(args) or "no branches", "name at least one branch")
    if not why.strip():
        refuse("arguments", "a non-empty --why", repr(why), "say what this session's deliverable is")
    target = target_of(args)
    by = identity()
    stamp = now().strftime("%Y-%m-%dT%H:%M:%SZ")
    with held() as path:
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
        targets = dict(data.get("targets") or {})
        if target:
            # LD-49: the lock stamped one `by` at the top and add
            # overwrote it, so the last writer appeared to own every
            # branch. Each target says who set it and when; the
            # lock-level by stays with whoever opened the lock.
            for branch in branches:
                targets[branch] = {"measure": target[0], "until": target[1],
                                   "by": by, "at": stamp}
        data = {"branches": named, "why": " | ".join(reasons),
                "by": data.get("by") or by,
                "at": data.get("at") or stamp}
        if targets:
            data["targets"] = targets
        write(path, data)
    print(f"locked {' '.join(named)}")
    return 0


def do_remove(args):
    """Owner, 2026-09-13 ("minimize parallel work conflicts"; LD-28): a
    session that lands lifts its own branches and leaves every other
    session's in place; clear was the only exit and wiped them all."""
    branches = positional(args, "--unmet")
    unmet = option(args, "--unmet")
    if not branches:
        refuse("arguments", "remove BRANCH... [--unmet TEXT]", " ".join(args) or "no branches",
               "name the branches to lift")
    if unmet is not None and not unmet.strip():
        refuse("arguments", "a non-empty --unmet", repr(unmet), "say why the target is left short")
    identity()
    with held() as path:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        named = [str(b) for b in (data.get("branches") if isinstance(data, dict) else None) or []]
        missing = [b for b in branches if b not in named]
        if missing:
            refuse("absent", f"branches the lock names ({', '.join(named) or 'none'})", ", ".join(missing),
                   "deliverable.py show; remove only what is named")
        targets = dict(data.get("targets") or {})
        short = []
        for branch in branches:
            if branch in targets:
                met, line = reading(targets[branch])
                if not met:
                    short.append(f"{branch} reads {line}")
        if short and unmet is None:
            refuse("target", "every target of the branches lifted met, or --unmet TEXT saying why not",
                   "; ".join(short), "finish the deliverable (deliverable.py done BRANCH), or remove --unmet '<why>'")
        tail = f" unmet ({unmet})" if short else ""
        for branch in branches:
            targets.pop(branch, None)
        left = [b for b in named if b not in branches]
        if not left:
            path.unlink()
            print(f"removed {' '.join(branches)}{tail}; no lock")
            return 0
        data["branches"] = left
        if targets:
            data["targets"] = targets
        else:
            data.pop("targets", None)
        write(path, data)
    print(f"removed {' '.join(branches)}{tail}; locked {' '.join(left)}")
    return 0


def do_done(args):
    """The reading, or the refusal: done is never the named slices."""
    branches = [a for a in args if not a.startswith("--")]
    if len(branches) != 1:
        refuse("arguments", "done BRANCH", " ".join(args) or "no branch", "name one branch")
    branch = branches[0]
    try:
        data = json.loads(lock_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    named = [str(b) for b in (data.get("branches") if isinstance(data, dict) else None) or []]
    if branch not in named:
        refuse("absent", f"a branch the lock names ({', '.join(named) or 'none'})", branch,
               "deliverable.py show; done is asked of a named branch")
    target = (data.get("targets") or {}).get(branch)
    if not target:
        refuse("target", f"a measured target on {branch} (--measure CMD --until TEXT on set or add)",
               "none: the lock names the branch and no reading", "set the target, then ask again; done is a reading")
    met, line = reading(target)
    if not met:
        refuse("target", f"the measure to read {target['until']}", line,
               "keep going; done is the reading, never the named slices")
    print(f"done {branch}: {line}")
    return 0


def do_show(_args):
    path = lock_path()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        print("no lock")
        return 0
    print(text.rstrip())
    try:
        data = json.loads(text)
    except ValueError:
        return 0
    for branch, target in (data.get("targets") or {}).items():
        print(target_line(branch, target))
    return 0


def do_clear(_args):
    identity()
    with held() as path:
        try:
            path.unlink()
        except FileNotFoundError:
            print("no lock")
            return 0
    print("cleared")
    return 0


VERBS = {"set": do_set, "add": do_add, "show": do_show, "done": do_done, "remove": do_remove, "clear": do_clear}


def main(argv):
    try:
        if len(argv) < 2 or argv[1] not in VERBS:
            refuse("arguments", "one of set, add, show, done, remove, clear",
                   argv[1] if len(argv) > 1 else "no verb", "name a verb")
        return VERBS[argv[1]](argv[2:])
    except Refusal as error:
        return emit(error)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
