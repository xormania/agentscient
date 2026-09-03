#!/usr/bin/env python3
"""Wait for a pull request's check table to settle."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from typing import NoReturn

PASS_STATES = {"SUCCESS"}
FAIL_STATES = {
    "FAILURE",
    "ERROR",
    "CANCELLED",
    "TIMED_OUT",
    "ACTION_REQUIRED",
    "STARTUP_FAILURE",
}
SKIP_STATES = {"SKIPPED", "NEUTRAL"}


def refuse(kind: str, expected: str, found: str, needed: str) -> NoReturn:
    """One line, the lane's refusal wire, exit with the Rejection code."""
    print(
        f"{kind}: expected {expected}; found {found}; needed {needed}",
        file=sys.stderr,
    )
    raise SystemExit(2)


class Parser(argparse.ArgumentParser):
    """Turn argparse failures into the tool's refusal shape."""

    def error(self, message: str) -> NoReturn:
        refuse("arguments", "valid watch arguments", message, "use --help for usage")


def positive_number(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        refuse("number", "a positive integer", repr(value), "NUMBER must be at least 1")
    if number < 1:
        refuse("number", "a positive integer", str(number), "NUMBER must be at least 1")
    return number


def classify(state: str) -> str:
    if state in PASS_STATES:
        return "pass"
    if state in FAIL_STATES:
        return "fail"
    if state in SKIP_STATES:
        return "skip"
    return "pending"


def read_checks(number: int, repo: str | None) -> list[tuple[str, str]]:
    command = ["gh", "pr", "checks", str(number), "--json", "name,state"]
    if repo is not None:
        command.extend(["--repo", repo])
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        refuse("gh-missing", "gh on PATH", "gh was not found", "install gh or add it to PATH")
    if result.returncode != 0:
        detail = result.stderr.rstrip("\n")
        refuse(
            "gh-error",
            "gh pr checks to exit 0",
            f"exit {result.returncode}, stderr={detail!r}",
            "make the gh command succeed",
        )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        refuse("json", "a JSON array of name/state objects", str(error), "valid gh JSON output")
    if not isinstance(data, list) or any(
        not isinstance(row, dict)
        or set(row) != {"name", "state"}
        or not isinstance(row["name"], str)
        or not isinstance(row["state"], str)
        for row in data
    ):
        refuse(
            "json",
            "a JSON array of string name/state objects",
            repr(data),
            "the shape emitted by gh pr checks --json name,state",
        )
    return [(row["name"], classify(row["state"])) for row in data]


def counts(checks: list[tuple[str, str]]) -> dict[str, int]:
    result = {"rows": len(checks), "pass": 0, "fail": 0, "pending": 0, "skip": 0}
    for _, state in checks:
        result[state] += 1
    return result


def watch(args: argparse.Namespace) -> int:
    if args.interval < 5:
        refuse("interval", "at least 5 seconds", str(args.interval), "--interval must be at least 5")
    if args.expect_min < 1:
        refuse(
            "arguments",
            "--expect-min of at least 1",
            str(args.expect_min),
            "--expect-min must preserve the non-empty reading",
        )
    if shutil.which("gh") is None:
        refuse("gh-missing", "gh on PATH", "gh was not found", "install gh or add it to PATH")

    expected = tuple(
        name.strip() for name in (args.expect_names or "").split(",") if name.strip()
    )
    started = time.monotonic()
    # Registration is not atomic: a settled-looking table is a candidate,
    # settled only when the next poll reports the identical table.
    candidate = None
    while True:
        checks = read_checks(args.number, args.repo)
        observed = counts(checks)
        missing = [name for name in expected if name not in {n for n, _ in checks}]
        settled_shape = (
            observed["rows"] >= args.expect_min
            and observed["pending"] == 0
            and not missing
        )
        table = tuple(sorted(checks))
        confirmed = settled_shape and candidate == table
        candidate = table if settled_shape else None
        elapsed = int(time.monotonic() - started)
        line = (
            f"poll rows={observed['rows']} pass={observed['pass']} "
            f"fail={observed['fail']} pending={observed['pending']} "
            f"skip={observed['skip']} elapsed={elapsed}s"
        )
        if missing:
            line += f" missing={len(missing)}"
        if settled_shape and not confirmed:
            line += " confirming"
        print(line, file=sys.stderr)
        if confirmed:
            for name, state in checks:
                print(f"{state.upper()}\t{name}")
            print(
                f"settled rows={observed['rows']} pass={observed['pass']} "
                f"fail={observed['fail']} skip={observed['skip']}"
            )
            return 1 if observed["fail"] else 0
        if time.monotonic() - started >= args.timeout:
            print(
                f"abort rows={observed['rows']} pass={observed['pass']} "
                f"fail={observed['fail']} pending={observed['pending']} "
                f"skip={observed['skip']}",
                file=sys.stderr,
            )
            return 3
        time.sleep(args.interval)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = Parser(description=__doc__)
    subparsers = parser.add_subparsers(dest="verb", required=True)
    pr = subparsers.add_parser("pr")
    pr.add_argument("number", type=positive_number, metavar="NUMBER")
    pr.add_argument("--repo")
    pr.add_argument("--interval", type=float, default=30)
    pr.add_argument("--timeout", type=float, default=1800)
    pr.add_argument("--expect-min", type=int, default=1)
    pr.add_argument("--expect-names")
    return parser.parse_args(argv)


def main() -> int:
    return watch(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
