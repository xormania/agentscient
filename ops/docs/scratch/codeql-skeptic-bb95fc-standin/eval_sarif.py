#!/usr/bin/env python3
"""Judge a CodeQL SARIF file, or the directory `analyze` emits.

Exit 0 only when every run in every document carries an explicit, empty
`results` list. Anything else — a result at any severity, a missing
file, an empty directory, malformed JSON, an absent `runs` key, a run
with no `results` key — is not a clean scan and exits nonzero.
"""

import json
import sys
from pathlib import Path


def documents(target):
    path = Path(target)
    if path.is_dir():
        found = sorted(path.rglob("*.sarif"))
        if not found:
            raise SystemExit(
                f"UNREACHABLE: no .sarif under {path}; an empty output "
                "directory is not a clean scan"
            )
        return found
    if not path.is_file():
        raise SystemExit(f"UNREACHABLE: {path} is missing; not a clean scan")
    return [path]


def results_in(path):
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as err:
        raise SystemExit(f"UNREACHABLE: {path} is not readable SARIF: {err}")
    if not isinstance(body, dict) or "runs" not in body:
        raise SystemExit(f"UNREACHABLE: {path} has no runs key; not a clean scan")
    runs = body["runs"]
    if not isinstance(runs, list) or not runs:
        raise SystemExit(f"UNREACHABLE: {path} carries no runs; not a clean scan")
    total = []
    for index, run in enumerate(runs):
        if not isinstance(run, dict) or "results" not in run:
            raise SystemExit(
                f"UNREACHABLE: {path} runs[{index}] has no results key; "
                "absent is not empty"
            )
        for item in run["results"] or []:
            rule = item.get("ruleId") if isinstance(item, dict) else None
            total.append(f"{path.name} runs[{index}] {rule}")
    return total


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: eval_sarif.py <sarif-file-or-directory>")
    hits = []
    for path in documents(argv[1]):
        hits.extend(results_in(path))
    if hits:
        for line in hits:
            print(line)
        raise SystemExit(f"{len(hits)} CodeQL result(s); not a clean scan")
    print("clean: every run carried an empty results list")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
