"""Recognize output-path instructions in harness job prompts."""

from __future__ import annotations

import re

_EXPLICIT_PATH = (
    r"\{out\}(?:/[\w.{}-]+)*"
    r"|(?:[\w.{}-]+/)+[\w.{}-]+"
    r"|[\w{}-]+\.[\w.-]+"
)
_WRITE_PATH = re.compile(
    rf"(?imsx)(?:^|(?<=[.!?]))[\t ]*"
    rf"(?!do\s+not\b|don't\b|never\b|without\b)"
    rf"[a-z][\w'-]*\b"
    rf"(?:"
    rf"\s+(?:{_EXPLICIT_PATH}"
    rf"|[\w.-]+(?=\s+(?:in\s+(?:the\s+)?repository|on\s+disk)\b))"
    rf"|[^.!?\r\n]{{0,100}}?\b(?:as|into|to|under)\s+"
    rf"(?:{_EXPLICIT_PATH})"
    rf")"
)


def write_path_ask(text: str) -> re.Match[str] | None:
    """Return the first positive write instruction naming a path."""
    return _WRITE_PATH.search(text)
