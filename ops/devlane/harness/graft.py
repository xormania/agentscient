#!/usr/bin/env python3
"""Contract bootstrap for graft/CONTRACT.md; enabled service is unavailable."""

from __future__ import annotations

import json
import sys


class Refused(ValueError):
    """A declared capability refusal, available before implementation."""


def configuration():
    return None


def install(destination):
    raise Refused("graft-install: expected implemented installer; found contract bootstrap; needed implement graft/CONTRACT.md")


def prepare(root, cache, installation, *, role="conductor"):
    raise Refused("graft-provider: expected implemented provider; found contract bootstrap; needed implement graft/CONTRACT.md")


def query(context, tool, arguments):
    return {"text": "Graft contract bootstrap: provider unavailable", "isError": True}


def prepare_worker(job_dir, snapshot, job):
    return None


def verify_worker(job_dir, snapshot, metadata):
    raise Refused("graft-context: expected implemented verification; found contract bootstrap; needed implement graft/CONTRACT.md")


def worker_note(metadata):
    return ""


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["status"]:
        print(json.dumps({"state": "unavailable", "reason": "contract bootstrap"}))
        return 0
    print("graft-provider: expected implemented capability; found contract bootstrap; needed implement graft/CONTRACT.md", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
