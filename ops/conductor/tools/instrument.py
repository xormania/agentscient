#!/usr/bin/env python3
"""The shared implementation of instrument-conventions.md.

One refusal wire, one identity check, one UTC clock, one state root, one
lane-conf read and one bounded subprocess call, imported by every
instrument under ops/conductor/tools/ instead of carried as a private
copy. The census of 2026-09-12 (ops/conductor/reports/) counted the
copies this replaces: eighteen refuse helpers with four behaviours,
twelve identity checks with four regexes, five clocks, four lane-name
readers with a hand-rolled fallback parser each.

    instrument.py identity                       print this command's agent, else refuse
    instrument.py identity --set "Name <addr>"   bind an agent to this session in the store
    instrument.py refuse CLASS EXPECTED FOUND NEEDED   emit one refusal line, exit 2

The three verbs exist for shell levers, so a script speaks the same wire
as the tools without a copy of the format string.

How a tool imports it: the tool appends its own directory to sys.path
and imports `instrument`, so the import resolves however the tool was
loaded: as the script, by path from another tool (launch.py loads
correction.py, which loads findings.py), or as a copy a test staged
with this module and laneconf.py beside it. A tool that finds no
instrument.py beside itself refuses `tooling` and exits 2.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import stat
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
STORED_NEEDED = (
    "instrument.py identity --set 'Your Model Name <noreply@vendor>' to "
    "rebind this session, or remove the row"
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
    bound = stored_identity()
    if bound:
        if IDENTITY.fullmatch(bound) is None:
            refuse("identity", "a stored identity in the Name <address> form",
                   f"{bound} in {state_db()}", STORED_NEEDED)
        return bound
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
# a host that exports it is answering the same question. Native Codex
# sessions supply CODEX_THREAD_ID and CODEX_SESSION_ID. A launcher's
# explicit legacy binding retains precedence over the worker's native id.
SESSION_UNKNOWN = "unknown"


def hook_profile():
    """Read a validated launch projection through this installation only."""
    named = os.environ.get("AGENTSCIENT_HOOK_PROFILE", "").strip()
    if not named or TERMINAL_POINTER.search(named):
        return None
    try:
        path = Path(__file__).resolve().parents[3] / "ops/devlane/hooks/profiles.py"
        spec = importlib.util.spec_from_file_location("instrument_hook_profiles", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.validate(module.read_binding(named))
    except Exception as error:  # noqa: BLE001 - explicit broken identity never falls through
        refuse("session-profile", "a valid pinned native profile", str(error),
               "regenerate the reviewed profile through its interactive or worker initializer")


# An owner-opened terminal's pointer (LD-125, sessions-lever.md "The owner's
# terminals"): the coordination capability `bind --run R-n` minted, with the
# run and terminal it was minted for. It is not a hook profile, since no hook
# is installed for that terminal, so hook_profile() never returns it and only
# capability_digest() reads it. The verb mints the token and inserts the
# participant carrying its digest; the file is written last, so a failure
# between them leaves no pointer and the next read refuses `missing`.
TERMINAL_SCHEMA = "owner-terminal-profile/1"
TERMINAL_POINTER = re.compile(r"(?:^|/)runs/(R-[1-9][0-9]*)/terminals/(PT-[1-9][0-9]*)/home/profile\.json\Z")
TERMINAL_KEYS = frozenset({"schema", "run", "terminal", "coordination_capability"})
RUN_ID = re.compile(r"R-[1-9][0-9]*")
TERMINAL_ID = re.compile(r"PT-[1-9][0-9]*")
CAPABILITY = re.compile(r"[0-9a-f]{64}")
TERMINAL_EXPECTED = "this owner terminal's minted capability, owner-terminal-profile/1"
TERMINAL_NEEDED = "bind --run R-n in this terminal again, which mints a new one"


def terminal_pointer(run: str, terminal: str) -> Path:
    return state_dir() / "runs" / run / "terminals" / terminal / "home" / "profile.json"


def mint_terminal_profile(run: str, terminal: str, capability: str) -> Path:
    """Write an owner terminal's pointer, 0600 and never replaced, and return its
    path. Called after the participant row carries the capability's digest."""
    if not (isinstance(run, str) and RUN_ID.fullmatch(run)
            and isinstance(terminal, str) and TERMINAL_ID.fullmatch(terminal)):
        refuse("arguments", "a run R-n and a terminal PT-n", f"run {run!r}, terminal {terminal!r}",
               "name the run and the participant the row was inserted as")
    if not isinstance(capability, str) or CAPABILITY.fullmatch(capability) is None:
        refuse("capability", TERMINAL_EXPECTED, "malformed capability",
               "mint 32 random bytes as hex before inserting the participant")
    path = terminal_pointer(run, terminal)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    body = json.dumps({"schema": TERMINAL_SCHEMA, "run": run, "terminal": terminal,
                       "coordination_capability": capability}, sort_keys=True, separators=(",", ":"))
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        refuse("capability", "a new home for this terminal", f"a minted profile already at {path}",
               "bind a new terminal; a minted capability is never replaced")
    with os.fdopen(descriptor, "w", encoding="ascii") as out:
        out.write(body)
    return path


def terminal_profile():
    """The owner terminal's pointer AGENTSCIENT_HOOK_PROFILE names, or None when it
    names none; `capability` naming `missing` or `malformed <what>` otherwise."""
    named = os.environ.get("AGENTSCIENT_HOOK_PROFILE", "").strip()
    match = TERMINAL_POINTER.search(named) if named else None
    if match is None:
        return None
    run, terminal = match.groups()
    path = Path(named).absolute()

    def malformed(what: str) -> NoReturn:
        refuse("capability", TERMINAL_EXPECTED, f"malformed {what}", TERMINAL_NEEDED)

    expected = terminal_pointer(run, terminal)
    if path.name != expected.name or os.path.realpath(path.parent) != os.path.realpath(expected.parent):
        malformed(f"location {named}")
    try:
        status = os.lstat(path)
    except FileNotFoundError:
        refuse("capability", TERMINAL_EXPECTED, "missing", TERMINAL_NEEDED)
    if not stat.S_ISREG(status.st_mode):
        malformed("file type")
    if status.st_mode & 0o077:
        malformed("permissions")
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, ValueError):
        malformed("json")
    if not isinstance(value, dict) or set(value) != TERMINAL_KEYS:
        malformed("keys")
    if value["schema"] != TERMINAL_SCHEMA:
        malformed("schema")
    if (value["run"], value["terminal"]) != (run, terminal):
        malformed("run or terminal")
    capability = value["coordination_capability"]
    if not isinstance(capability, str) or CAPABILITY.fullmatch(capability) is None:
        malformed("capability")
    return value


def authority_home() -> Path:
    profile = hook_profile()
    return Path(profile["authority_environment"]["HOME"]) if profile else Path.home()


def capability_digest(profile=None) -> str:
    """Digest the caller's private coordination capability, never a session id.

    A declared profile is authoritative and cannot fall back to an ambient
    credential. The core owns enrollment and comparison; native identity
    resolution uses this same digest to retain existing messaging endpoints.
    """
    if profile is None:
        profile = hook_profile()
    if profile is None:
        profile = terminal_profile()
    value = (profile.get("coordination_capability") if profile is not None
             else os.environ.get("COORDINATION_CAPABILITY"))
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        refuse("capability", "this participant's private launch capability",
               "missing or malformed credential",
               "use the admitted native profile or its private CLI credential")
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def session(default: str = SESSION_UNKNOWN) -> str:
    """The session id the harness set, or `default` when none did.

    An unprofiled read uses the caller's absence word. An explicit guarded
    profile must resolve its existing SQLite participant or refuses.

    The keys are spelled literally here rather than looped over a tuple
    of names: laneconf's closure check matches a literal beside
    `os.environ.get`, and a read its own gate cannot see is the dark
    coupling docs/verified-couplings.md names.
    """
    aliases = (
        os.environ.get("CLAUDE_CODE_SESSION_ID", ""),
        os.environ.get("CLAUDE_SESSION_ID", ""),
        os.environ.get("CODEX_THREAD_ID", ""),
        os.environ.get("CODEX_SESSION_ID", ""),
        os.environ.get("GROK_SESSION_ID", ""),
    )
    profile = hook_profile()
    if profile:
        if profile["mode"] == "worker":
            return profile["session"]
        try:
            conf_values = _laneconf().parse_file(Path(profile["source"]) / "ops/lane.conf")
            db = Path(profile["authority_environment"]["XDG_STATE_HOME"]) / conf_values["LANE_NAME"] / "state.db"
            with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
                rows = conn.execute("SELECT session_id, harness FROM participants WHERE capability_digest = ?",
                                    (capability_digest(profile),)).fetchall()
            if len(rows) != 1 or rows[0][1] != profile["harness"]:
                raise ValueError("missing or ambiguous native participant association")
            named = rows[0][0]
            if any(value.strip() and value.strip() != named for value in aliases):
                raise ValueError("inherited native alias conflicts with the registered session")
            return named
        except (OSError, ValueError, KeyError, sqlite3.Error) as error:
            refuse("session-profile", "one matching native participant", str(error),
                   "initialize this terminal through its own reviewed profile")
    for value in aliases:
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
    profile = hook_profile()
    if profile:
        return Path(profile["authority_environment"]["XDG_STATE_HOME"])
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
        profile = hook_profile()
        if profile:
            return laneconf.parse_file(Path(profile["source"]) / "ops/lane.conf")[name]
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


def state_db() -> Path:
    """The lane's one state store. Rows, not files (the state skill)."""
    return state_dir() / "state.db"


SESSION_IDENTITY = """
CREATE TABLE IF NOT EXISTS session_identity (
    session_id TEXT PRIMARY KEY,
    agent      TEXT NOT NULL,
    at         TEXT NOT NULL
)
"""


def stored_identity() -> str:
    """The agent this session bound to itself, or "" when it bound none.

    A read, and it never creates the store: a host where no session has
    bound a name has looked and found nothing, and the ambient key
    answers. A store that exists and cannot be read is the other case
    entirely and refuses class `store`, because "could not look" must
    never arrive dressed as an answer (docs/wire.md, absence discipline).
    """
    try:
        path = state_db()
    except Refusal:
        # No lane conf means no lane, so no lane state directory and so
        # no store. That is found-nothing, not could-not-look: a staged
        # copy of this module with no conf must still be able to name its
        # agent from the environment rather than refuse on a store it
        # could never have had.
        return ""
    key = session("")
    if not key or not path.is_file():
        return ""
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
            # PRAGMA, not a SELECT against the schema table: that
            # table's name ends in the release branch's name, and
            # laneconf.py's literal scan reads the substring, not the
            # SQL (measured 2026-09-16: instrument.py:263 forbidden
            # literal, literals exit 1). table_info answers the same
            # question -- no rows means no such table -- on every
            # SQLite this lane has run on; the schema-table alias that
            # also avoids the word needs 3.33 or newer.
            if not con.execute(
                "PRAGMA table_info(session_identity)"
            ).fetchone():
                return ""
            row = con.execute(
                "SELECT agent FROM session_identity WHERE session_id = ?", (key,)
            ).fetchone()
    except sqlite3.DatabaseError as error:
        refuse("store", "a readable state store", f"{path}: {error}",
               "repair or remove the store, or name the agent with "
               "WF_AGENT_OVERRIDE for this command")
    return row[0] if row else ""


def set_identity(agent: str) -> str:
    """Bind an agent to this session; return the session id it was bound to.

    The one writing verb of this module, and it takes no identity of its
    own: it is how a session acquires one. The row is keyed on the
    session, so two sessions on one host never overwrite each other, and
    a second call replaces this session's row rather than adding one.
    """
    if IDENTITY.fullmatch(agent.strip()) is None:
        refuse("identity", "an agent in the Name <address> form",
               agent.strip() or "unset", IDENTITY_NEEDED)
    key = session("")
    if not key:
        # A row keyed on the word `unknown` would be shared by every
        # session that has no id, which is worse than no row at all.
        refuse("session", "a session id in the environment", "unset",
               "run under a harness that sets CLAUDE_CODE_SESSION_ID, or "
               "name the agent with WF_AGENT_OVERRIDE for one command")
    path = state_db()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, isolation_level=None) as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute(SESSION_IDENTITY)
        con.execute(
            "INSERT INTO session_identity (session_id, agent, at)"
            " VALUES (?, ?, ?)"
            " ON CONFLICT(session_id) DO UPDATE SET"
            " agent = excluded.agent, at = excluded.at",
            (key, agent.strip(), stamp()),
        )
        con.execute("COMMIT")
    return key


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
        if verb == "identity" and len(argv) == 4 and argv[2] == "--set":
            key = set_identity(argv[3])
            print(f"identity: {argv[3].strip()} bound to session {key}")
            return EXIT_DONE
        if verb == "refuse" and len(argv) == 6:
            refuse(*argv[2:6])
        refuse("arguments",
               "identity, identity --set 'Name <addr>', or refuse CLASS "
               "EXPECTED FOUND NEEDED",
               " ".join(argv[1:]) or "no verb", "name one verb with its arguments")
    except Refusal as refusal:
        return emit(refusal)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
