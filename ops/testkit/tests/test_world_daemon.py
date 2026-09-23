"""world.daemon and world.adopt: a recorded daemon is stopped at close and
proven gone; a daemon its own stop does not bring down is refused class
daemon on the wire; a daemon started around the kit is refused by close's
sweep
(docs/tests.md §The kit, Daemons; the invariant testkit.daemon).

Each row closes a world holding one planted daemon in a child process,
fixtures/closer.py, so the wire is read as a caller reads it: exit, stdout,
stderr. Whether anything survived is read here from /proc, never from the
kit's own process table. Every survivor is killed before the row is judged.
The planted faults in world.py these rows catch are fixtures/daemon_faults.py.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import unittest
from pathlib import Path

import support

from ops.testkit import RefusalCase, World, run, run_table

CLOSER = "ops.testkit.tests.fixtures.closer"
TIMEOUT = "2"
ORIGIN = "PR #274; PR #275: at a93368b5, 1 run in 20 leaked 18 tmux servers with no failure"

CLEAN = (
    RefusalCase(
        "recorded-and-well-behaved", ("recorded",), "none", exit=0, origin=ORIGIN,
        note="world.daemon records it, its stop brings it down, close leaves nothing",
    ),
    RefusalCase(
        "adopted-and-well-behaved", ("adopted",), "none", exit=0, origin=ORIGIN,
        note="the subject starts it, world.adopt records it by its socket, close leaves nothing",
    ),
)
REFUSED = (
    RefusalCase(
        "recorded-and-deaf-to-its-stop", ("recorded", "--deaf-stop"), "daemon",
        named=("fixture", "SIGTERM ended it"), origin=ORIGIN,
        note="its stop answers and it keeps serving; SIGTERM ends it, and close still refuses",
    ),
    RefusalCase(
        "recorded-and-deaf-to-stop-and-sigterm", ("recorded", "--deaf-stop", "--deaf-term"), "daemon",
        named=("fixture", "SIGKILL ended it"), origin=ORIGIN,
        note="only SIGKILL ends it",
    ),
    RefusalCase(
        "started-around-the-kit", ("around",), "daemon",
        named=("started around the kit",), origin=ORIGIN,
        note="a well-behaved daemon the case started with run and never recorded",
    ),
)


def alive(pid: int, started: str) -> bool:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    rest = raw[raw.rindex(")") + 2:].split()
    return rest[0] not in ("Z", "X") and rest[19] == started


def kill_survivors(pids: dict) -> list[int]:
    """The recorded pids still running, each killed before it is reported."""
    left = sorted(int(pid) for pid, started in pids.items() if alive(int(pid), started))
    for pid in left:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
    return left


@unittest.skipUnless(Path("/proc/self/stat").is_file(), "world.daemon reads /proc; this host has none")
class Daemons(unittest.TestCase):
    def close(self, world, row):
        """Close a world holding the row's daemon; returns (result, reading),
        after proving the reading names a daemon and nothing of it survived."""
        reading = world.root / f"{row.id}.json"
        result = run([support.PYTHON, "-m", CLOSER, str(reading), TIMEOUT, *row.argv],
                     cwd=support.REPO, env=world.env(), timeout=120)
        self.assertTrue(reading.is_file(), f"{row.id}: no reading; exit {result.exit}: {result.stderr[-400:]}")
        record = json.loads(reading.read_text(encoding="utf-8"))
        self.assertTrue(record["pids"], f"{row.id}: the reading names no daemon: {record}")
        self.assertEqual(kill_survivors(record["pids"]), [], f"{row.id}: alive after close")
        return result, record

    def test_a_recorded_or_adopted_daemon_whose_stop_works_leaves_nothing_at_close(self):
        with World(host_path=False) as world:
            for row in CLEAN:
                with self.subTest(id=row.id):
                    result, record = self.close(world, row)
                    self.assertEqual((result.exit, result.stdout, result.stderr), (0, "", ""), row.id)
                    self.assertFalse(Path(record["root"]).exists(), f"{row.id}: the world's root survived close")

    def test_a_daemon_its_stop_does_not_end_or_the_kit_never_recorded_is_refused(self):
        with World(host_path=False) as world:
            run_table(self, REFUSED, lambda row: self.close(world, row)[0])


if __name__ == "__main__":
    unittest.main()
