#!/usr/bin/env python3
"""Serve the tracked workflow check registry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent / "gate-kinds"


def refuse(expected: str, found: str, needed: str) -> int:
    line = f"registry: expected {expected}; found {found}; needed {needed}"
    print(" ".join(line.split()), file=sys.stderr)
    return 2


def registry() -> dict:
    checks = []
    for path in sorted(REGISTRY.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        kind = payload["kind"]
        version = payload["version"]
        entries = payload["checks"]
        if not isinstance(kind, str) or not isinstance(version, int):
            raise ValueError(f"{path}: invalid kind or version")
        if not isinstance(entries, list):
            raise ValueError(f"{path}: checks is not a list")
        for entry in entries:
            checks.append(
                {
                    "kind": kind,
                    "kind_version": version,
                    "name": entry["name"],
                    "class": entry["class"],
                    "argv": list(entry["argv"]),
                    "ci": bool(entry.get("ci", False)),
                }
            )
    if not checks:
        raise ValueError(f"{REGISTRY}: no checks")
    checks.sort(key=lambda check: (check["kind"], check["kind_version"], check["name"]))
    return {
        "checks": checks,
        "ci_matrix": sorted({check["name"] for check in checks if check["ci"]}),
    }


def main(argv: list[str]) -> int:
    if argv[1:] != ["--json", "status", "--checks"]:
        return refuse(
            "--json status --checks",
            " ".join(argv[1:]) or "no arguments",
            "request the tracked check registry",
        )
    try:
        payload = registry()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return refuse(
            "valid gate-kind JSON",
            str(exc),
            "repair the tracked registry before deriving CI checks",
        )
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
