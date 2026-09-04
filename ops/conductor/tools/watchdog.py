#!/usr/bin/env python3
"""Session watchdog: one line per condition worth acting on, a heartbeat
every 30 minutes. Reads the live dispatch store and the forge; never
writes. Conditions: a record closes (with its envelope status and size),
a running record passes 40 minutes (walls are 60), a launcher pid is
gone with no exit written, CI is red on an open PR into dev."""
import json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

STORE = Path.home() / ".local/state/agentscient/dispatch"
TICK = 300
HEARTBEAT_EVERY = 6
WARN_MIN = 40

def say(line):
    print(line, flush=True)

def now():
    return datetime.now(timezone.utc)

def stamp_of(name):
    try:
        return datetime.strptime(name[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

def read_json(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False

def records():
    out = []
    if not STORE.is_dir():
        return out
    for d in sorted(STORE.iterdir()):
        if not d.is_dir():
            continue
        rec = read_json(d / "record.json") or {}
        state = read_json(d / "state.json") or {}
        status = rec.get("status") or ("unknown")
        has_exit = (d / "exit").exists()
        closed = status in {"closed", "died"} or has_exit
        out.append((d.name, status, closed, state.get("pid"), rec))
    return out

def summary(rec):
    res = rec.get("result") or {}
    env = res.get("envelope") or {}
    n = len(res.get("changed_paths") or [])
    return f"env={env.get('status')} changed={n}"

def minutes(name):
    t = stamp_of(name)
    return int((now() - t).total_seconds() // 60) if t else -1

def gh(*args):
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None

def ci_red():
    raw = gh("pr", "list", "--base", "dev", "--state", "open", "--json", "number,headRefOid")
    if raw is None:
        return None, []
    reds = []
    prs = json.loads(raw)
    for pr in prs:
        checks = gh("pr", "checks", str(pr["number"]), "--json", "name,bucket")
        if checks is None:
            continue
        for c in json.loads(checks):
            if c.get("bucket") == "fail":
                reds.append((pr["number"], pr["headRefOid"][:7], c.get("name")))
    return len(prs), reds

seen_closed = {name for name, _, closed, _, _ in records() if closed}
warned = set()
gone = set()
red_seen = set()
tick = 0
say(f"watchdog armed: {len(seen_closed)} closed records ignored, tick {TICK}s")
while True:
    tick += 1
    running = []
    for name, status, closed, pid, rec in records():
        if closed:
            if name not in seen_closed:
                seen_closed.add(name)
                say(f"closed {name} status={status} {summary(rec)} after {minutes(name)} min")
            continue
        m = minutes(name)
        if pid and not alive(pid) and name not in gone:
            gone.add(name)
            say(f"launcher gone {name} after {m} min: pid {pid} dead, no exit written")
            continue
        running.append((name, m))
        if m >= WARN_MIN and name not in warned:
            warned.add(name)
            say(f"long {name}: {m} min running, wall 60")
    n_prs, reds = ci_red()
    for pr, sha, check in reds:
        key = (pr, sha)
        if key not in red_seen:
            red_seen.add(key)
            say(f"ci red #{pr} at {sha}: {check}")
    if tick % HEARTBEAT_EVERY == 1 and tick > 1:
        live = ", ".join(f"{n} {m}m" for n, m in running) or "none"
        prs = "unreachable" if n_prs is None else n_prs
        say(f"heartbeat: running={live}; open PRs into dev={prs}")
    time.sleep(TICK)
