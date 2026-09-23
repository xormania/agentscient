"""The claude adapter: one managed native Claude Code TUI in a tmux pane.

Contract: ops/conductor/sessions-lever.md, "The adapter boundary". The
supervisor calls these five methods and no others: `argv`, `observe_identity`,
`probe`, `stop`, `diagnostics`. The launch goes through the existing
`profiles.py run-interactive` path unchanged; the launch identity is passed
the way Claude Code accepts one, `--session-id`.

`diagnostics` adapts the proof's retention of a window's terminal capture
as evidence, by path (Source:
/home/scientdb/projects/poc/multi-harness-proof@a944f31, mhproof/sessions.py
`Tmux.finish_peer`). `argv` and `stop` are this contract's: the proof
launched its own entry point and closed panes without signalling a pid.

Stdlib only.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROFILES = REPO / "ops" / "devlane" / "hooks" / "profiles.py"
PROBE_TIMEOUT = 10
STOP_WAIT = 5.0
EVIDENCE = ("pane.log", "stderr.log", "launch.json")


def _start_ticks(pid: int) -> str | None:
    """Field 22 of /proc/PID/stat, the start time in clock ticks; None when gone."""
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    return text.rsplit(")", 1)[1].split()[19]


def _wait_gone(pid: int, start: str, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if _start_ticks(pid) != start:
            return True
        time.sleep(0.05)
    return _start_ticks(pid) != start


class Adapter:
    """Claude Code's native TUI, launched through the profile."""

    harness = "claude"

    def argv(self, member, binding, launch_id):
        """The fixed launch argv for the profile's run-interactive, never operator text."""
        return [
            sys.executable, str(PROFILES), "run-interactive",
            "--binding", str(binding["binding"]),
            "--", "--session-id", str(launch_id),
        ]

    def observe_identity(self, store, launch_id):
        """The native id the coordination store shows for this launch, or None."""
        if store is None:
            return None
        try:
            row = store.execute(
                "SELECT session_id FROM participants WHERE session_id = ?", (launch_id,)
            ).fetchone()
        except Exception:  # noqa: BLE001 - a store without participants shows nothing
            return None
        return None if row is None else row[0]

    def probe(self, executable):
        """The installed version; the channel capability is slice 2's to measure."""
        reading = {"executable": str(executable), "capability": "unmeasured slice 2"}
        try:
            done = subprocess.run(  # noqa: S603 - argv is a list, never a shell string
                [str(executable), "--version"], capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=PROBE_TIMEOUT, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            reading["version"] = f"unresolved {type(error).__name__}: {error}"
            return reading
        lines = (done.stdout or done.stderr).strip().splitlines()
        reading["version"] = lines[0] if lines else f"unresolved exit {done.returncode}, no output"
        return reading

    def stop(self, handle, terminate):
        """Signal only a pid whose start ticks still match the record."""
        pid, start = int(handle["pid"]), str(handle["start"])
        current = _start_ticks(pid)
        if current != start:
            return f"unresolved stale pid {pid}: start ticks {current or 'gone'}, recorded {start}"
        if not terminate:
            return f"unresolved running pid {pid}"
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as error:
            return f"unresolved pid {pid}: SIGTERM failed: {error}"
        if _wait_gone(pid, start, STOP_WAIT):
            return f"stopped terminated pid {pid}"
        if _start_ticks(pid) == start:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError as error:
                return f"unresolved pid {pid}: SIGKILL failed: {error}"
        if _wait_gone(pid, start, STOP_WAIT):
            return f"stopped killed pid {pid}"
        return f"unresolved pid {pid}: alive after SIGKILL"

    def diagnostics(self, member_dir):
        """The evidence paths retained for this member, each one a file."""
        base = Path(member_dir)
        return [str(base / name) for name in EVIDENCE if (base / name).is_file()]
