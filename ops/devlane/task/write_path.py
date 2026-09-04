"""Detect instructions that ask a read-role worker to write a path."""

from __future__ import annotations

import re


WRITE_PATH_ASK = re.compile(
    r"(?is)"
    r"\b(?:write|create|persist|save|store|emit|dump)\b"
    r"(?:"
    r".{0,200}?(?:\{out\}|(?<![A-Za-z])out/|/\S+|\b[\w.-]+\.\w{1,8}\b)"
    r"|\s+(?:(?:a|an|the)\s+)?[A-Z][A-Z0-9_-]*\b"
    r")"
)
ARTIFACTS_OUTPUT_ASK = re.compile(
    r"(?i)\b(?:write|name|include|put|place)\b.{0,80}\bartifacts\b"
)


def write_path_ask(text: str):
    """Return the first write-path instruction in text, or None."""
    if not isinstance(text, str) or not text.strip():
        return None
    return WRITE_PATH_ASK.search(text) or ARTIFACTS_OUTPUT_ASK.search(text)
