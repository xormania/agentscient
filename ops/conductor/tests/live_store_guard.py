"""The live-store guard shared by the conductor suites.

A test's teardown proves the tool under test wrote nothing into the
operator's live stores. On this host the CI runner and the conductor
share those stores with running dispatches, so the comparison declares
exactly which concurrent canonical mutations are not the tool's:

- a new job directory, ``<stamp>-<stage>-<harness>-<hash>``;
- a transient launcher log, ``.launcher.`` plus six letters or digits,
  created or removed while a concurrent launcher owns it.

Everything else still fails: missing stores, changed store types,
removed pre-existing job directories, ordinary added or removed names,
near-miss launcher names. The guard has never established process
attribution; ``ops/conductor/test-store-guard.md`` is its contract.
"""
from __future__ import annotations

import re

JOB_DIR = re.compile(r"^\d{8}T\d{6}Z-[a-z-]+-[a-z]+-[0-9a-f]{6}$")
LAUNCH_LOG = re.compile(r"\.launcher\.[A-Za-z0-9]{6}\Z")


def normalize(before: dict, after: dict) -> tuple[dict, dict]:
    """Return (expected, actual) with the declared exclusions applied."""
    expected: dict = {}
    for key, (kind, names) in before.items():
        if kind == "dir":
            names = tuple(n for n in names if not LAUNCH_LOG.fullmatch(n))
        expected[key] = (kind, names)
    actual: dict = {}
    for key, (kind, names) in after.items():
        if kind == "dir" and key in before and before[key][0] == "dir":
            previous = set(before[key][1])
            names = tuple(
                n for n in names
                if not LAUNCH_LOG.fullmatch(n)
                and (n in previous or not JOB_DIR.match(n))
            )
        actual[key] = (kind, names)
    return expected, actual


def without_new_job_dirs(before: dict, after: dict) -> dict:
    """The normalized ``after`` alone; the shape the retained suite pins."""
    return normalize(before, after)[1]


def assert_unchanged(case, before: dict, after: dict,
                     message: str = "live dispatch store mutated") -> None:
    """Fail ``case`` unless ``after`` equals ``before`` under the exclusions."""
    expected, actual = normalize(before, after)
    case.assertEqual(actual, expected, message)
