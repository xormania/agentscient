"""Recognize prompt instructions that write to a path."""

from __future__ import annotations

import re


_WRITE_TO_SHAPED_PATH = re.compile(
    r"(?ix)\b(?:create|write|persist|save|store|put|place)\b"
    r"[^.!?\n]{0,100}?"
    r"(?:\{out\}(?:/[^\s,;]+)?|(?:/|\.{1,2}/|[\w.{}-]+/)[^\s,;]+|"
    r"[\w{}-]+\.[\w-]+)"
)
_WRITE_EXTENSIONLESS_IN_LOCATION = re.compile(
    r"(?ix)\b(?:create|write|persist|save|store|put|place)\s+"
    r"(?:an?\s+|the\s+)?[\w{}-]+\s+"
    r"(?:in|under|inside|within|at)\s+(?:the\s+)?"
    r"(?:repository|worktree|snapshot|directory)\b"
)


def write_path_ask(text: str) -> re.Match[str] | None:
    """Return the first path-writing instruction, if one is present."""
    matches = [
        match
        for pattern in (_WRITE_TO_SHAPED_PATH, _WRITE_EXTENSIONLESS_IN_LOCATION)
        if (match := pattern.search(text)) is not None
    ]
    return min(matches, key=lambda match: match.start()) if matches else None
