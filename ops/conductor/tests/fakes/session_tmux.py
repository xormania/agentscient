# testkit: exempt fixture program planted as tmux
"""Private-socket tmux shim: attach-session is a no-op so attach rows
do not hang a tty-less runner; every other argv execs the host tmux.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

REAL = "@@TMUX@@"
LOG = "@@LOG@@"


def main() -> int:
    argv = sys.argv[1:]
    line = json.dumps({"at": time.time_ns(), "pid": os.getpid(), "argv": argv}) + "\n"
    fd = os.open(LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    if "kill-server" in argv:
        sys.stderr.write(
            "tmux: expected no kill-server; found kill-server; needed target the owned session\n"
        )
        return 2
    if "attach-session" in argv or (argv and argv[0] == "attach"):
        return 0
    return subprocess.call([REAL, *argv])


if __name__ == "__main__":
    raise SystemExit(main())
