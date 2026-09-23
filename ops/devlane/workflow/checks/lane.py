"""The full local/CI check plan; CONTRACT-ci.md owns its guarantees."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from pathlib import Path

from ops.testkit import Check, execute_checks, suite_checks

ROOT = Path(__file__).resolve().parents[4]
FAMILIES = (
    "ops/devlane/dispatch/tests", "ops/devlane/harness/tests",
    "ops/devlane/task/tests", "ops/devlane/telemetry/tests",
    "ops/devlane/hooks/tests", "ops/devlane/fixtures/tests",
    "ops/devlane/workflow/tests", "ops/testkit/tests",
    "ops/conductor/tests", ".claude/skills/pr-overview/tests",
)
SHARDS = {"ops/conductor/tests": (
    "test_[c]*.py", "test_[l]*.py", "test_[ow]*.py", "test_[!clow]*.py",
)}


def python_check(name, path, *args, timeout=60, required=()):
    return Check(name, (sys.executable, path, *args), timeout, (path, *required))


LINT = Check("ruff", ("ruff", "check", "."), 60, ("ruff.toml",))
GUARDS = (
    LINT,
    python_check("term-wall", "ops/devlane/workflow/checks/term_wall.py", "--root", "."),
    python_check("testkit-ratchet", "ops/devlane/workflow/checks/testkit_ratchet.py",
                 required=("ops/devlane/workflow/checks/testkit-ratchet.json",)),
    python_check("conf-closure", "ops/conductor/tools/laneconf.py", "closure",
                 required=("ops/lane.conf",)),
    python_check("conf-literals", "ops/conductor/tools/laneconf.py", "literals",
                 required=("ops/lane.conf",)),
    python_check("probes", "ops/conductor/tools/probes.py", "run", timeout=600,
                 required=("ops/conductor/handoff/probes",)),
)


def plan(root, selected=()):
    # Portable subjects carry their own lint contract. They explicitly select
    # their copied suites, and never claim the full repository was checked.
    checks = [replace(LINT, required=())] if selected else list(GUARDS)
    for directory in selected or FAMILIES:
        patterns = ("test_*.py",) if selected else SHARDS.get(directory, ("test_*.py",))
        checks.extend(suite_checks(root, directory, patterns))
    return checks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", action="append", default=[], metavar="DIR",
                        help="lint plus explicitly selected suites; PARTIAL, never full CI")
    args = parser.parse_args(argv)
    env = dict(os.environ)
    try:
        checks = plan(ROOT, args.suite)
        results = execute_checks(checks, cwd=ROOT, env=env,
                                 workers=1 if env.get("SUITES_SERIAL") == "1" else None)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    scope = "PARTIAL" if args.suite else "FULL"
    print(f"{scope}: {len(checks)} required checks", flush=True)
    completed = set()
    failed = []
    for name, result in results:
        print(f"== {name}", flush=True)
        print(result.stdout, end="", flush=True)
        print(result.stderr, end="", flush=True)
        print(f"{'PASS' if result.exit == 0 else 'FAIL'} {name} ({result.duration:.3f}s)", flush=True)
        completed.add(name)
        if result.exit != 0:
            failed.append(name)
    missing = {check.name for check in checks} - completed
    good = not failed and not missing
    print(f"{scope}: {'PASS' if good else 'FAIL'} ({len(completed)}/{len(checks)} completed)", flush=True)
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
