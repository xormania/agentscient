#!/usr/bin/env python3
"""Refuse a CodeQL proof unless readable SARIF contains no results."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def sarif_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(target.rglob("*.sarif"))
    raise ValueError(f"missing SARIF path: {target}")


def result_count(path: Path) -> int:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"unreadable SARIF {path}: {error}") from error
    runs = document.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError(f"SARIF {path} has no non-empty runs list")
    count = 0
    for index, run in enumerate(runs):
        if not isinstance(run, dict) or "results" not in run:
            raise ValueError(f"SARIF {path} run {index} has no results list")
        results = run["results"]
        if not isinstance(results, list):
            raise ValueError(f"SARIF {path} run {index} results is not a list")
        count += len(results)
    return count


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: eval_sarif.py PATH", file=sys.stderr)
        return 2
    target = Path(argv[1])
    try:
        files = sarif_files(target)
        if not files:
            raise ValueError(f"no SARIF files found under {target}")
        findings = sum(result_count(path) for path in files)
    except ValueError as error:
        print(f"UNREACHABLE: {error}", file=sys.stderr)
        return 2
    if findings:
        print(f"FAIL: CodeQL reported {findings} result(s)", file=sys.stderr)
        return 1
    print(f"PASS: CodeQL reported no results in {len(files)} SARIF file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
