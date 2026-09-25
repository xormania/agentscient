"""Select CI from the files changed in the tested GitHub event revision."""

from __future__ import annotations

import json
import os
import subprocess  # noqa: S404 -- read-only Git commands for CI routing.
from pathlib import Path

DEV_DIRS = ("ops/", ".dev/", ".claude/", ".agents/", ".serena/")
PROD_DIRS = (
    "src/", "config/", "packages/", "tests/", "public/", "bin/", "mate/",
    "assets/", "templates/", "translations/", "migrations/", "docker/",
)
DEV_FILES = {"ruff.toml", "unittest", ".mcp.json"}
PROD_FILES = {
    "composer.json", "composer.lock", "symfony.lock", "phpunit.xml",
    "phpunit.dist.xml", ".phpactor.json", ".github/workflows/ci-prod-lane.yml",
}


def select(paths):
    dev = prod = False
    for path in paths:
        if path.endswith(".md"):
            continue
        if path.startswith(DEV_DIRS) or path in DEV_FILES:
            dev = True
        elif (path.startswith(PROD_DIRS) or path in PROD_FILES
              or path.startswith((".env", "Dockerfile", "compose."))):
            prod = True
        else:
            # Shared CI/configuration and unclassified files need both lanes.
            dev = prod = True
    return {"dev": dev, "prod": prod}


def git(*args):
    return subprocess.check_output(["git", *args], timeout=60)  # noqa: S603,S607 -- fixed Git operations; no shell.


def changed_files(event_name, event):
    if event_name == "pull_request":
        base = event["pull_request"]["base"]["sha"]
    elif event_name == "merge_group":
        base = event["merge_group"]["base_sha"]
    elif event_name == "push":
        base = event["before"]
    else:
        raise ValueError(f"Unsupported CI event: {event_name}")
    # A newly created branch has no previous tree. Otherwise a missing base
    # is an error, never evidence that no checks are needed.
    if base == "0" * 40:
        data = git("ls-files", "-z")
    else:
        # Disabling rename detection includes both old and new paths. A move
        # across the lane boundary therefore checks both sides.
        data = git("diff", "--name-only", "--no-renames", "-z", base, "HEAD", "--")
    return base, [os.fsdecode(path) for path in data.split(b"\0") if path]


def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    revision = git("rev-parse", "HEAD").decode().strip()
    if revision != os.environ["GITHUB_SHA"]:
        raise ValueError("Checkout does not match the GitHub event revision")
    base, paths = changed_files(os.environ["GITHUB_EVENT_NAME"], event)
    selected = select(paths)
    print(json.dumps({"revision": revision, "base": base,
                      "changed_files": paths, **selected}, indent=2))
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        for lane, enabled in selected.items():
            output.write(f"{lane}={str(enabled).lower()}\n")
        output.write(f"revision={revision}\n")
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as summary:
        summary.write(f"Tested revision: `{revision}`\n\nComparison base: `{base}`\n\n")
        summary.write(f"Changed files: {len(paths)}. Dev-lane: {selected['dev']}. "
                      f"Prod-lane: {selected['prod']}.\n")


if __name__ == "__main__":
    main()
