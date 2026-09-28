"""Isolated stdlib bootstrap; restore a private launch environment before app imports."""

import json
import os
import sys


def main():
    with open(sys.argv[1], encoding="utf-8") as stream:
        environment = json.load(stream)["environment"]
    # These values identify the new terminal rather than the older caller's pane.
    environment.update({key: os.environ[key] for key in ("TERM", "TMUX", "TMUX_PANE") if key in os.environ})
    os.execve(sys.argv[2], sys.argv[2:], environment)


if __name__ == "__main__":
    main()
