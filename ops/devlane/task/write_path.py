"""Recognize output-path instructions in harness job prompts."""

from __future__ import annotations

import re

_WRITE_PATH = re.compile(
    r"(?is)\b(?:create|dump|generate|persist|save|store|write)\b"
    r".{0,120}?"
    r"(?:"
    r"\{out\}(?:/[\w.{}-]+)*"
    r"|(?:[\w.{}-]+/)+[\w.{}-]+"
    r"|[\w{}-]+\.[\w.-]+"
    r"|[\w.-]+(?=\s+(?:in\s+(?:the\s+)?repository|on\s+disk)\b)"
    r")"
)
_NEGATION = re.compile(r"(?i)\b(?:do\s+not|don't|never|without)\s+$")


def write_path_ask(text: str) -> re.Match[str] | None:
    """Return the first positive write instruction naming a path."""
    for match in _WRITE_PATH.finditer(text):
        if not _NEGATION.search(text[max(0, match.start() - 16):match.start()]):
            return match
    return None
