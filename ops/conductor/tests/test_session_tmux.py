"""The private-socket tmux shim forwards a host tmux format value.

Contract: `ops/conductor/sessions-lever.md`. The planted shim in
`ops/conductor/tests/fakes/session_tmux.py` execs the host tmux for
every argv other than kill-server and attach. This row is the
regression the builder found: `main` returned only `result.exit`, so
`new-session -P -F` read empty. Skip when the host tmux is absent.

The one command that reads this file is
`python3 -m unittest discover -s ops/conductor/tests -p test_session_tmux.py`.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from ops.testkit import World, run

REPO = Path(__file__).resolve().parents[3]
TMUX_SRC = Path(__file__).resolve().parent / "fakes" / "session_tmux.py"
ORIGIN = "sessions-lever.md"
HOST_TMUX = shutil.which("tmux")
TIMEOUT = 60.0
SHORT_ROOT = "/tmp"


def shim_text(log: Path) -> str:
    if not TMUX_SRC.is_file():
        raise AssertionError(f"INVALID: planted program missing: {TMUX_SRC}")
    if not HOST_TMUX:
        raise AssertionError("INVALID: shim text requested without a host tmux")
    text = TMUX_SRC.read_text(encoding="utf-8")
    if text.startswith("#!"):
        text = text.split("\n", 1)[1]
    text = (
        text.replace("@@TMUX@@", HOST_TMUX)
        .replace("@@LOG@@", str(log))
        .replace("@@REPO@@", str(REPO))
    )
    return f"#!{sys.executable}\n" + text


class TheTmuxShimForwardsFormat(unittest.TestCase):
    """One regression row: a real tmux format value reaches the caller."""

    def open_world(self) -> World:
        """A world rooted under /tmp, so the private tmux socket it owns
        stays under 108 bytes. origin: 20260922T215604Z-review-codex-f6777b#10
        """
        # tempfile caches its directory at the first call, so TMPDIR set
        # here is not read; tempfile.tempdir is what mkdtemp consults.
        # origin: 20260923T003033Z-review-codex-c99cc9#2
        saved = tempfile.tempdir
        tempfile.tempdir = SHORT_ROOT
        try:
            return World(prefix="session-tmux-")
        finally:
            tempfile.tempdir = saved

    def test_the_shim_passes_a_host_tmux_format_value_through(self):
        """origin: sessions-lever.md"""
        if not HOST_TMUX:
            raise unittest.SkipTest(
                "tmux is absent; the format row needs the host tmux"
            )
        with self.subTest(id="tmux-format-passthrough", origin=ORIGIN):
            world = self.open_world()
            self.addCleanup(world.close)
            socket = world.tmp / "tmux.sock"
            self.assertLess(
                len(os.fsencode(str(socket))),
                108,
                f"private tmux socket must be under 108 bytes: {socket}",
            )
            log = world.root / "tmux.calls.jsonl"
            planted = world.tools.plant("tmux", script=shim_text(log))
            self.addCleanup(self.stop_server, world, socket)
            proc = run(
                [
                    str(planted),
                    "-S", str(socket),
                    "-f", "/dev/null",
                    "new-session", "-d", "-s", "probe",
                    "-P", "-F", "#{session_name}",
                ],
                cwd=world.cwd,
                env=world.env(),
                timeout=TIMEOUT,
            )
            self.assertEqual(proc.exit, 0, proc.stderr)
            self.assertEqual(
                proc.stdout.strip(),
                "probe",
                f"the shim dropped the host tmux format value: {proc.stdout!r}",
            )

    def stop_server(self, world: World, socket: Path) -> None:
        run(
            [HOST_TMUX, "-S", str(socket), "kill-server"],
            cwd=world.cwd,
            env=world.env(),
            timeout=TIMEOUT,
        )


if __name__ == "__main__":
    unittest.main()
