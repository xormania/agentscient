#!/usr/bin/env python3
"""Session watch: watchdog.py plus conf/session probes the lever does not read.

Prints only ACTION_REQUIRED / DONE / FAILED. Watchdog's own lines are
the source for dispatch/forge conditions; this adds the session-shaped
misses (forbidden Claude models, WF_AGENT_DEFAULT stamping the wrong
harness) that a dispatch-only watchdog cannot see.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/home/scientdb/projects/uscient/agentscient")
WATCHDOG = ROOT / "ops/conductor/tools/watchdog.py"
STORE = Path.home() / ".local/state/agentscient/dispatch"
LIVE = (
    "20260904T200133Z-code-codex-f951e9",
)
FORBIDDEN_MODELS = ("fable", "claude-opus-5", "opus-5")
KEEP_PREFIXES = (
    "closed ",
    "harness gone ",
    "exit written",
    "long ",
    "ci ",
    "launchers ",
    "deviation retry ",
    "deviation minutes ",
)
seen: set[str] = set()


def say(line: str) -> None:
    if line in seen:
        return
    seen.add(line)
    print(line, flush=True)


def forbidden(value: str) -> bool:
    lower = value.lower()
    return any(token in lower for token in FORBIDDEN_MODELS)


def probe_session() -> None:
    settings = Path.home() / ".claude" / "settings.json"
    if settings.is_file():
        model = json.loads(settings.read_text()).get("model") or ""
        if forbidden(str(model)):
            say(
                "FAILED: interactive Claude model is "
                f"{model!r}; owner 2026-09-04 forbade Fable and Opus 5"
            )
            sys.exit(1)
    local = ROOT / "ops/lane.local.conf"
    if local.is_file():
        for line in local.read_text().splitlines():
            if line.startswith("WF_AGENT_DEFAULT=") and "Grok" in line:
                say(
                    "ACTION_REQUIRED: WF_AGENT_DEFAULT in lane.local.conf "
                    "would stamp Claude dispatches as Grok"
                )
            if line.startswith("MODEL_CLAUDE_") and forbidden(line):
                say(
                    "FAILED: lane.local.conf names a forbidden Claude model: "
                    f"{line}"
                )
                sys.exit(1)


def watchdog_tick() -> list[str]:
    proc = subprocess.run(
        [
            sys.executable,
            str(WATCHDOG),
            "--once",
            "--heartbeat-every",
            "1000000",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        say("FAILED: watchdog exited "
            f"{proc.returncode}: {(err[-1] if err else 'no stderr')}")
        sys.exit(1)
    return [ln for ln in proc.stdout.splitlines() if ln]


def live_rows():
    rows = []
    for rid in LIVE:
        rec = STORE / rid / "record.json"
        if not rec.is_file():
            rows.append((rid, None, None, None))
            continue
        data = json.loads(rec.read_text())
        env = (data.get("result") or {}).get("envelope") or {}
        env_st = env.get("status") if isinstance(env, dict) else None
        rows.append((rid, data.get("status"), env_st, data))
    return rows


def live_closed() -> bool:
    rows = live_rows()
    return all(status in {"closed", "died"} for _, status, _, _ in rows)


def main() -> int:
    probe_session()
    while True:
        probe_session()
        for line in watchdog_tick():
            if line.startswith("watchdog armed:"):
                continue
            if any(token in line for token in LIVE) or line.startswith(KEEP_PREFIXES):
                if line.startswith("harness gone "):
                    say(f"FAILED: {line}")
                    return 1
                say(f"ACTION_REQUIRED: {line}")
        if live_closed():
            bad = [
                f"{rid} status={st} envelope={env}"
                for rid, st, env, _ in live_rows()
                if st == "died"
            ]
            if bad:
                say("FAILED: " + "; ".join(bad))
                return 1
            say("DONE")
            return 0
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
