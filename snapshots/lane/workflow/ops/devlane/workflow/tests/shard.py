#!/usr/bin/env python3
"""Run one shard of the suite: `shard.py [--list] N I` runs (or lists) the
test files whose sorted index is congruent to I mod N.

The tests job is >90% of CI wall time (195-342s against a 24s verifier), so
it runs as an N-way matrix. Sharding lives in a script rather than a YAML
expression for the usual reason — the YAML expression is the part nobody can
run locally — and the partition property (every file in exactly one shard,
no shard empty) is asserted in test_ci_shape.py rather than assumed.

Assignment is round-robin over the name-sorted files. That is arbitrary but
deterministic; if shard durations drift far apart, balance by measured time
before reaching for more machinery.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def shard_modules(n: int, i: int) -> list:
    files = sorted(p.stem for p in TESTS.glob("test*.py"))
    return [name for index, name in enumerate(files) if index % n == i]


def main(argv) -> int:
    args = list(argv[1:])
    list_only = "--list" in args
    if list_only:
        args.remove("--list")
    try:
        n, i = int(args[0]), int(args[1])
    except (IndexError, ValueError):
        print(__doc__.strip(), file=sys.stderr)
        return 64
    if not (n > 0 and 0 <= i < n):
        print(f"shard {i} of {n} does not exist", file=sys.stderr)
        return 64
    modules = shard_modules(n, i)
    if list_only:
        print("\n".join(modules))
        return 0
    if not modules:
        # An empty shard is a partition bug upstream, not a green job.
        print(f"shard {i} of {n} matched no test files", file=sys.stderr)
        return 1
    sys.path.insert(0, str(TESTS))
    result = unittest.main(
        module=None, argv=["shard.py", "-v", *modules], exit=False
    ).result
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
