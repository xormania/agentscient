#!/usr/bin/env python3
"""The shared implementation of instrument-conventions.md.

One refusal wire, one identity check, one UTC clock, one state root, one
lane-conf read and one bounded subprocess call, imported by every
instrument under ops/conductor/tools/ instead of carried as a private
copy. The census of 2026-09-12 (ops/conductor/reports/) counted the
copies this replaces: eighteen refuse helpers with four behaviours,
twelve identity checks with four regexes, five clocks, four lane-name
readers with a hand-rolled fallback parser each.

    instrument.py identity                       print WF_AGENT in Name <address> form, else refuse
    instrument.py refuse CLASS EXPECTED FOUND NEEDED   emit one refusal line, exit 2

The two verbs exist for shell levers, so a script speaks the same wire
as the tools without a copy of the format string.

How a tool imports it: the tool appends its own directory to sys.path
and imports `instrument`, so the import resolves however the tool was
loaded: as the script, by path from another tool (launch.py loads
correction.py, which loads findings.py), or as a copy a test staged
with this module and laneconf.py beside it. A tool that finds no
instrument.py beside itself refuses `tooling` and exits 2.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

EXIT_DONE = 0
EXIT_FINDING = 1
EXIT_REJECTION = 2
EXIT_ABORT = 3

IDENTITY = re.compile(r"(?P<name>[^<>\n]+) <(?P<address>[^<>\s@]+@[^<>\s]+)>")
IDENTITY_NEEDED = "export WF_AGENT='Your Model Name <noreply@vendor>'"
OVERRIDE_NEEDED = (
    "WF_AGENT_OVERRIDE='Your Model Name <noreply@vendor>' on the command, "
    "or unset it to use WF_AGENT"
)
GIT = shutil.which("git") or "git"


def _flat(value: object) -> str:
    return " ".join(str(value).split())


class Refusal(Exception):
    """A pre-act rejection: one line on stderr, exit 2, stdout empty."""

    def __init__(self, kind: str, expected: object, found: object, needed: object) -> None:
        self.kind = _flat(kind)
        self.expected = _flat(expected)
        self.found = _flat(found)
        self.needed = _flat(needed)
        super().__init__(self.line())

    def line(self) -> str:
        return (
            f"{self.kind}: expected {self.expected}; found {self.found}; "
            f"needed {self.needed}"
        )


def refuse(kind: str, expected: object, found: object, needed: object) -> NoReturn:
    raise Refusal(kind, expected, found, needed)


def emit(refusal: Refusal, stream=None) -> int:
    """Print the refusal at the CLI boundary; return the Rejection code."""
    print(refusal.line(), file=stream or sys.stderr)
    return EXIT_REJECTION


def identity() -> str:
    """The agent for this command in Name <address> form, or refuse identity.

    WF_AGENT_OVERRIDE is read first and outranks WF_AGENT. The second key
    exists because the first is not always the command's own: measured
    2026-09-16, .claude/settings.local.json binds env.WF_AGENT for every
    session on this host, so WF_AGENT is always set and nothing reading
    os.environ can tell "meant, on this command" from "inherited from
    settings" — both arrive as the same key. A precedence written on
    WF_AGENT alone can therefore never reach a later branch, and every
    row a session writes carries whichever name that file holds.

    A malformed override refuses rather than falling through to WF_AGENT.
    Falling through would stamp rows with one agent while the command
    named another, which is the misattribution the key was added to end;
    a deliberate value that is wrong is not an absent one. A blank
    override is not a declaration and is passed over.
    """
    override = os.environ.get("WF_AGENT_OVERRIDE", "").strip()
    if override:
        if IDENTITY.fullmatch(override) is None:
            refuse("identity", "WF_AGENT_OVERRIDE in the Name <address> form",
                   override, OVERRIDE_NEEDED)
        return override
    value = os.environ.get("WF_AGENT", "")
    if IDENTITY.fullmatch(value) is None:
        refuse("identity", "WF_AGENT in the Name <address> form", value or "unset",
               IDENTITY_NEEDED)
    return value


def identity_parts() -> tuple[str, str]:
    match = IDENTITY.fullmatch(identity())
    return match.group("name"), match.group("address")


# The harness names the session in CLAUDE_CODE_SESSION_ID. The lane read
# CLAUDE_SESSION_ID, which nothing sets here, so every row it stamped
# recorded nobody: 251 handwork rows `unknown` and 506 skill events
# `unrecorded` at bbdcc651 (LD-50). The older key stays admitted, because
# a host that exports it is answering the same question.
SESSION_UNKNOWN = "unknown"


def session(default: str = SESSION_UNKNOWN) -> str:
    """The session id the harness set, or `default` when none did.

    A read, so it never refuses: a row that cannot name its session says
    so in the word the caller chose. Blank is not a declaration and is
    passed over, so an exported-but-empty key never reads as an answer.

    Both keys are spelled literally here rather than looped over a tuple
    of names: laneconf's closure check matches a literal beside
    `os.environ.get`, and a read its own gate cannot see is the dark
    coupling docs/verified-couplings.md names.
    """
    for value in (
        os.environ.get("CLAUDE_CODE_SESSION_ID", ""),
        os.environ.get("CLAUDE_SESSION_ID", ""),
    ):
        named = value.strip()
        if named:
            return named
    return default


def now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(value: datetime | None = None) -> str:
    """An ISO 8601 UTC stamp ending in Z."""
    moment = value if value is not None else now()
    return moment.isoformat().replace("+00:00", "Z")


def parse_stamp(text: str) -> datetime:
    """The aware datetime of a stamp; a naive one is read as UTC.
    A malformed stamp raises ValueError for the caller to classify."""
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def state_root() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    return Path(configured) if configured else Path.home() / ".local" / "state"


_LANECONF = None


def _laneconf():
    """The lane conf reader beside this module, loaded once from its file
    so it resolves however this module itself was loaded."""
    global _LANECONF  # noqa: PLW0603 - one lazily loaded sibling module
    if _LANECONF is None:
        path = Path(__file__).resolve().with_name("laneconf.py")
        if not path.is_file():
            refuse("conf-file", "the lane conf reader laneconf.py beside this module",
                   "absent", "restore ops/conductor/tools/laneconf.py")
        spec = importlib.util.spec_from_file_location("instrument_laneconf", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LANECONF = module
    return _LANECONF


def conf(name: str) -> str:
    """One lane-conf key through laneconf; its refusal on this wire."""
    laneconf = _laneconf()
    try:
        return laneconf.get(name)
    except laneconf.ConfigError as error:
        kind = "conf-key" if error.kind == "key" else error.kind
        refuse(kind, error.expected, error.found, error.needed)


def lane_name() -> str:
    """LANE_NAME through the lane conf reader: LANE_CONF when named,
    else the tracked conf beside the reader. No name stands in for an
    absent conf; the ledger, lock, register and brief levers each
    carried one as a deferred literal, and a copy of a tool run away
    from its checkout names its conf through LANE_CONF instead."""
    return conf("LANE_NAME")


def state_dir() -> Path:
    return state_root() / lane_name()


def run(
    argv: list[str],
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    input: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """One command, no shell, output captured; a timeout or a missing
    executable refuses `<name>-error` instead of raising."""
    name = Path(argv[0]).name
    try:
        return subprocess.run(  # noqa: S603 - argv is a list, never a shell string
            argv, cwd=cwd, env=env, timeout=timeout, input=input,
            capture_output=True, text=True, check=False,
        )
    except subprocess.TimeoutExpired:
        refuse(f"{name}-error", f"{name} completing within {timeout}s", "timeout",
               f"restore {name} access and retry")
    except FileNotFoundError:
        refuse(f"{name}-error", f"{name} on PATH", "not found", f"install {name}")


def git(*args: str, cwd: Path | str | None = None,
        timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return run([GIT, *args], cwd=cwd, timeout=timeout)


def main(argv: list[str]) -> int:
    verb = argv[1] if len(argv) > 1 else ""
    try:
        if verb == "identity" and len(argv) == 2:
            print(identity())
            return EXIT_DONE
        if verb == "refuse" and len(argv) == 6:
            refuse(*argv[2:6])
        refuse("arguments", "identity, or refuse CLASS EXPECTED FOUND NEEDED",
               " ".join(argv[1:]) or "no verb", "name one verb with its arguments")
    except Refusal as refusal:
        return emit(refusal)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
