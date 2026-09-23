#!/usr/bin/env python3
"""Managed sessions, slice 1: one managed native participant per member.

Contract: ops/conductor/sessions-lever.md. Inherits
ops/conductor/instrument-conventions.md: the refusal wire, the four exit
classes, identity for writes. Runs on the state engine (machine.py): the
run and member rows live in `state.db`, never in a file. Stdlib only; no
Symfony, no vendor. It never edits a global harness configuration: every
native home is the private profile `profiles.py prepare-interactive` makes.

    sessions.py doctor [--team FILE]
    sessions.py start --member NAME [--team FILE] [--run R-n] [--worktree PATH]
                      [--ready-timeout SEC] [--tmux-socket NAME]
    sessions.py status [--run R-n] [--member NAME]
    sessions.py attach --member NAME [--run R-n]
    sessions.py stop [--run R-n] [--terminate] [--drain SEC]
    sessions.py export [--run R-n] --to DIR

Message delivery (join, recover), the Codex and Grok adapters and dispatch
actions are later slices; a verb this page does not list refuses
`arguments`. Reads need no identity and never create the store.

The tmux handling adapts the proof's operator-owned tmux lifecycle
(Source: /home/scientdb/projects/poc/multi-harness-proof@a944f31,
mhproof/sessions.py `Tmux`): the owner option read on the exact session
component, the owned session and window created detached with the pane id
printed, and attach by `attach-session` or `switch-client`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

# The shared instrument module sits beside this file; its directory goes
# on the path so the import resolves however this file was loaded.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    import coordination
    import machine
    from coordination import ROLES
    from instrument import (
        EXIT_DONE,
        EXIT_FINDING,
        Refusal,
        emit,
        identity,
        refuse,
        stamp,
        state_dir,
    )
except ModuleNotFoundError:
    print(
        "tooling: expected instrument.py, machine.py and coordination.py beside this tool; "
        "found absent; needed restore them beside ops/conductor/tools/sessions.py",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ADAPTERS = HERE / "session_adapters"
COORDINATION = HERE / "coordination.py"
PROFILES = REPO / "ops" / "devlane" / "hooks" / "profiles.py"
DEFAULT_TEAM = REPO / "ops" / "conductor" / "team.default.json"
LOCAL_TEAM = REPO / ".dev" / "coordination" / "team.json"

SCHEMA_NAME = "agentscient-team/1"
HARNESSES = ("claude", "codex", "grok")
NAME = re.compile(r"[a-z][a-z0-9-]{0,31}")
RUN_ID = re.compile(r"^R-(\d+)$")
OWNER_OPTION = "@agentscient_owner"
READINESS = ("process", "profile", "identity", "participant", "role", "tools", "ingress", "response")
SLICE2 = ("tools", "ingress", "response")
LIVE = ("launched", "bound", "ready")
STEP_TIMEOUT = 120
TMUX_TIMEOUT = 10
POLL = 0.2
# Keys the pane never inherits: the operator's own coordination
# capability and harness identity, and the tmux client's own markers.
WITHHELD = (
    "COORDINATION_CAPABILITY", "CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID",
    "CODEX_THREAD_ID", "CODEX_SESSION_ID", "GROK_SESSION_ID",
    "AGENTSCIENT_HOOK_PROFILE", "AGENTSCIENT_LAUNCH_SESSION", "TMUX", "TMUX_PANE",
)
SHELL_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NATIVE_REFUSAL = re.compile(r"native: expected the launch session id \S+; found ([^;\s]+);")
LAUNCHER ='set -a; . "$0"; set +a; rm -f -- "$0"; exec "$@"'

T = machine.Transition
MEMBER = machine.Machine(
    name="session-member",
    version=1,
    initial="reserved",
    places=("reserved", "launched", "bound", "ready", "stopped", "lost"),
    # The contract's stop and lose each leave three places; the engine
    # declares one source per transition, so each is one row per source.
    transitions=(
        T("launch", "reserved", "launched", "any", "required", "place", "keep"),
        T("bind", "launched", "bound", "any", "required", "native", "keep"),
        T("ready", "bound", "ready", "any", "required", "readiness", "keep"),
        *(T(f"stop-{place}", place, "stopped", "any", "required", "place", "keep") for place in LIVE),
        *(T(f"lose-{place}", place, "lost", "any", "required", "place", "keep") for place in LIVE),
    ),
    ttl_s=8 * 3600,
)
RUN = machine.Machine(
    name="session-run",
    version=1,
    initial="open",
    places=("open", "stopping", "stopped"),
    transitions=(
        T("stop", "open", "stopping", "any", "required", "place", "keep"),
        T("close", "stopping", "stopped", "any", "required", "place", "keep"),
    ),
    ttl_s=8 * 3600,
)
SCHEMA = """
CREATE TABLE IF NOT EXISTS session_run(
    id INTEGER PRIMARY KEY AUTOINCREMENT, subject INTEGER NOT NULL UNIQUE, name TEXT NOT NULL, team_file TEXT NOT NULL,
    team_sha256 TEXT NOT NULL, tmux_socket TEXT, tmux_session TEXT NOT NULL,
    started_by TEXT NOT NULL, started_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS session_member(
    id INTEGER PRIMARY KEY AUTOINCREMENT, subject INTEGER NOT NULL UNIQUE, run INTEGER NOT NULL, name TEXT NOT NULL,
    harness TEXT NOT NULL, roles TEXT NOT NULL, generation INTEGER NOT NULL,
    launch_id TEXT, native_id TEXT, participant INTEGER, pid INTEGER,
    start_ticks TEXT, pane TEXT, worktree TEXT NOT NULL, profile TEXT,
    evidence TEXT NOT NULL, readiness TEXT, outcome TEXT,
    started_by TEXT NOT NULL, started_at TEXT NOT NULL);
"""
TABLES = ("session_run", "session_member")


# -- arguments ---------------------------------------------------------------

def usage() -> str:
    return "see the verbs in the module doc of sessions.py"


def parse(rest, *, required=(), optional=(), flags=()):
    """--options only; anything else refuses `arguments`."""
    options = {}
    tokens = list(rest)
    while tokens:
        token = tokens.pop(0)
        if not token.startswith("--"):
            refuse("arguments", "no positional argument", token, usage())
        name = token[2:]
        if name in flags:
            options[name] = True
            continue
        if name not in required and name not in optional:
            refuse("arguments", "a known option", token, usage())
        if not tokens:
            refuse("arguments", f"a value after --{name}", "end of arguments", usage())
        options[name] = tokens.pop(0)
    for name in required:
        if name not in options:
            refuse("arguments", f"--{name}", "absent", usage())
    return options


def seconds(options, name: str, default: int) -> int:
    raw = options.get(name, str(default))
    if not raw.isdigit():
        refuse("arguments", f"--{name} as whole seconds", raw, usage())
    return int(raw)


def run_number(text: str) -> int:
    match = RUN_ID.match(text)
    if match is None:
        refuse("arguments", "a run id like R-1", text, "the run id start or status printed")
    return int(match.group(1))


# -- the team file -------------------------------------------------------------

def team_path(options) -> Path:
    if "team" in options:
        return Path(options["team"]).absolute()
    return LOCAL_TEAM if LOCAL_TEAM.is_file() else DEFAULT_TEAM


def load_team(path: Path) -> tuple[dict, str]:
    """The team file, validated whole, and its sha256; else refuse `team`."""
    needed = f"fix {path} to schema {SCHEMA_NAME} (sessions-lever.md, The team file)"
    try:
        raw = path.read_bytes()
        team = json.loads(raw)
    except (OSError, ValueError) as error:
        refuse("team", f"a readable JSON team file at {path}", f"{type(error).__name__}: {error}", needed)
    if not isinstance(team, dict) or set(team) != {"schema", "run", "members"}:
        refuse("team", "exactly the keys schema, run, members",
               sorted(team) if isinstance(team, dict) else type(team).__name__, needed)
    if team["schema"] != SCHEMA_NAME:
        refuse("team", f"schema {SCHEMA_NAME}", team["schema"], needed)
    header = team["run"]
    if not isinstance(header, dict) or set(header) != {"name", "tmux"} or not all(
            isinstance(header[key], str) and NAME.fullmatch(header[key]) for key in ("name", "tmux")):
        refuse("team", "run with a name and a tmux prefix, each matching [a-z][a-z0-9-]{0,31}",
               header, needed)
    members = team["members"]
    if not isinstance(members, list) or not members:
        refuse("team", "a non-empty members list", members, needed)
    seen = set()
    for member in members:
        if not isinstance(member, dict) or not {"name", "harness", "roles"} <= set(member) or \
                not set(member) <= {"name", "harness", "roles", "executable"}:
            refuse("team", "a member of name, harness, roles and an optional executable", member, needed)
        name = member["name"]
        if not isinstance(name, str) or not NAME.fullmatch(name):
            refuse("team", "a member name matching [a-z][a-z0-9-]{0,31}", name, needed)
        if name in seen:
            refuse("team", "member names unique in the file", f"{name} twice", needed)
        seen.add(name)
        if member["harness"] not in HARNESSES:
            refuse("team", "a harness of " + ", ".join(HARNESSES), member["harness"], needed)
        roles = member["roles"]
        if not isinstance(roles, list) or not roles or any(role not in ROLES for role in roles):
            refuse("team", "a non-empty roles list from " + ", ".join(ROLES), roles, needed)
        executable = member.get("executable")
        if executable is not None and (not isinstance(executable, str) or not os.path.isabs(executable)):
            refuse("team", "an executable given as an absolute path", executable, needed)
    return team, hashlib.sha256(raw).hexdigest()


def team_member(team: dict, name: str, path: Path) -> dict:
    for member in team["members"]:
        if member["name"] == name:
            return member
    names = ", ".join(member["name"] for member in team["members"])
    refuse("team", f"a member of {path}: {names}", name, "name a member the team file declares")


def executable_of(member: dict) -> str | None:
    named = member.get("executable")
    return named or shutil.which(member["harness"])


def load_adapter(harness: str):
    path = ADAPTERS / f"{harness}.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"session_adapter_{harness}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Adapter()


# -- the store ---------------------------------------------------------------

def writer() -> sqlite3.Connection:
    try:
        # The coordination core owns its schema; a cold store gains it here
        # so the profile's SessionStart finds a store to bind into. No
        # participant is written.
        conn = coordination.writer()
        conn.executescript(SCHEMA)
    except sqlite3.DatabaseError as error:
        refuse("store", f"a readable SQLite store at {machine.store_path()}", str(error),
               "restore or move the store aside; the engine never rebuilds one to order")
    machine.declare(conn, RUN)
    machine.declare(conn, MEMBER)
    return conn


def reader() -> sqlite3.Connection | None:
    """The store read-only, or None when it holds no runs; never created."""
    path = machine.store_path()
    if not path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True,
                               timeout=machine.BUSY_TIMEOUT_MS / 1000)
        conn.row_factory = sqlite3.Row
        held = {row["name"] for row in
                conn.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")}
    except sqlite3.DatabaseError as error:
        refuse("store", f"a readable SQLite store at {path}", str(error),
               "restore or move the store aside; a read never rebuilds it")
    if not all(table in held for table in TABLES):
        conn.close()
        return None
    return conn


PARTICIPANT_BY = {
    "session_id": "SELECT * FROM participants WHERE session_id = ?",
    "capability_digest": "SELECT * FROM participants WHERE capability_digest = ?",
}


def participant_by(conn, column: str, value: str):
    """A coordination participant row, or None when the store has none."""
    if conn is None:
        return None
    try:
        return conn.execute(PARTICIPANT_BY[column], (value,)).fetchone()
    except sqlite3.OperationalError:
        return None


def coordination_reader() -> sqlite3.Connection | None:
    path = machine.store_path()
    if not path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True,
                               timeout=machine.BUSY_TIMEOUT_MS / 1000)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.DatabaseError:
        return None


def run_row(conn, rid: int):
    return conn.execute(
        "SELECT r.*, s.place FROM session_run r JOIN subjects s ON s.id = r.subject WHERE r.id = ?",
        (rid,),
    ).fetchone()


def member_rows(conn, *, rid=None, name=None):
    sql = ("SELECT m.*, s.place FROM session_member m JOIN subjects s ON s.id = m.subject "
           "WHERE 1 = 1")
    args: list = []
    if rid is not None:
        sql += " AND m.run = ?"
        args.append(rid)
    if name is not None:
        sql += " AND m.name = ?"
        args.append(name)
    return conn.execute(sql + " ORDER BY m.id", args).fetchall()


def chosen_run(conn, options, *, places=("open", "stopping")):
    """The run named by --run, else the newest run in one of `places`."""
    if "run" in options:
        rid = run_number(options["run"])
        row = run_row(conn, rid) if conn is not None else None
        if row is None:
            refuse("absent", "a run of this store", options["run"], "sessions.py status lists the runs")
        return row
    if conn is not None:
        for row in conn.execute(
                "SELECT r.*, s.place FROM session_run r JOIN subjects s ON s.id = r.subject "
                "ORDER BY r.id DESC"):
            if row["place"] in places:
                return row
    refuse("absent", "a run in place " + " or ".join(places), "none", "sessions.py start --member NAME")


def member_dir(rid: int, name: str, generation: int) -> Path:
    base = state_dir() / "sessions" / f"R-{rid}" / name
    return base if generation == 1 else base / f"gen-{generation}"


# -- processes and tmux ----------------------------------------------------------

def start_ticks(pid: int) -> str | None:
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    return text.rsplit(")", 1)[1].split()[19]


def socket_args(socket: str | None) -> list[str]:
    if not socket:
        return []
    return ["-S", socket] if "/" in socket else ["-L", socket]


def quiet_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in WITHHELD}


def tmux(socket: str | None, *args: str, timeout: float = TMUX_TIMEOUT) -> subprocess.CompletedProcess:
    binary = shutil.which("tmux")
    if binary is None:
        refuse("tmux", "tmux on PATH", "absent", "install tmux; sessions run in an owned tmux session")
    try:
        return subprocess.run(  # noqa: S603 - argv is a list, never a shell string
            [binary, *socket_args(socket), *args], capture_output=True, text=True,
            timeout=timeout, env=quiet_env(), check=False,
        )
    except subprocess.TimeoutExpired:
        refuse("tmux", f"tmux answering within {timeout}s", f"no answer to {args[0]}",
               "inspect the tmux server on the named socket")


def ownership(run) -> str:
    """`absent` for no such session, `owned`, or the owner option actually found."""
    name = run["tmux_session"]
    if tmux(run["tmux_socket"], "has-session", "-t", f"={name}").returncode != 0:
        return "absent"
    # Option commands parse a target pane; the colon makes the exact
    # session component explicit (the proof's Tmux.owned).
    shown = tmux(run["tmux_socket"], "show-options", "-qv", "-t", f"={name}:", OWNER_OPTION)
    value = shown.stdout.strip()
    return "owned" if value == f"R-{run['id']}" else (value or "unset")


def refuse_unowned(run, found: str) -> None:
    refuse("ownership", f"tmux session {run['tmux_session']} with {OWNER_OPTION} R-{run['id']}",
           f"{OWNER_OPTION} {found}",
           "the supervisor never sets, kills or attaches a session it does not own; "
           "rename or close that session yourself, or start another run")


def launcher(argv: list[str], directory: Path) -> tuple[list[str], Path]:
    """The pane's command: source a private env file, delete it, exec the argv.

    Every environment value reaches the pane through a mode-600 file, never
    a command line; the operator's capability and harness ids never reach it.
    """
    lines = ["unset " + " ".join(WITHHELD) + " 2>/dev/null"]
    for key, value in sorted(quiet_env().items()):
        if SHELL_KEY.fullmatch(key) and key not in ("_", "PWD", "OLDPWD", "SHLVL"):
            lines.append(f"{key}={shlex.quote(value)}")
    path = directory / "launch.env"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return ["/bin/sh", "-c", LAUNCHER, str(path), *argv], path


# -- readiness -----------------------------------------------------------------

def profile_reading(profile: str | None) -> str:
    if not profile:
        return "waiting profile"
    binding = Path(profile) / "binding.json"
    checked = subprocess.run(  # noqa: S603 - argv is a list, never a shell string
        [sys.executable, str(PROFILES), "check", "--binding", str(binding)],
        capture_output=True, text=True, timeout=STEP_TIMEOUT, check=False,
    )
    if checked.returncode == 0:
        return f"ok {profile}"
    line = (checked.stderr or checked.stdout).strip().splitlines()
    return "refused profile " + (line[0] if line else f"exit {checked.returncode}")


def profile_digest(profile: str | None) -> str | None:
    if not profile:
        return None
    try:
        binding = json.loads((Path(profile) / "binding.json").read_text(encoding="utf-8"))
        return hashlib.sha256(binding["coordination_capability"].encode("ascii")).hexdigest()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def native_refusal(evidence: str) -> str | None:
    """The native id the profile's SessionStart refused, read from the pane.

    `initialize` refuses a native id that is not the launch id before it
    binds anything, so the store never shows it; the refusal line is in
    the member's pane capture.
    """
    try:
        text = (Path(evidence) / "pane.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = NATIVE_REFUSAL.search(text)
    return match.group(1) if match else None


def readiness(member, *, check_profile: bool = True) -> dict[str, str]:
    """The eight dimensions, read now; slice 2's three are unmeasured."""
    found: dict[str, str] = {}
    pid, ticks = member["pid"], member["start_ticks"]
    if pid is None:
        found["process"] = "waiting launch"
    elif start_ticks(pid) == ticks:
        found["process"] = f"ok pid={pid} start={ticks}"
    else:
        found["process"] = f"refused gone pid={pid} start={ticks}"
    found["profile"] = profile_reading(member["profile"]) if check_profile else (
        f"ok {member['profile']}" if member["profile"] else "waiting profile")
    conn = coordination_reader()
    try:
        bound = participant_by(conn, "session_id", member["launch_id"]) if member["launch_id"] else None
        digest = profile_digest(member["profile"])
        other = participant_by(conn, "capability_digest", digest) if digest else None
    finally:
        if conn is not None:
            conn.close()
    refused = native_refusal(member["evidence"])
    if other is not None and other["session_id"] != member["launch_id"]:
        found["identity"] = f"refused native {other['session_id']}, launched as {member['launch_id']}"
    elif refused is not None and bound is None:
        found["identity"] = f"refused native {refused}, launched as {member['launch_id']}"
    elif bound is not None:
        found["identity"] = f"ok {bound['session_id']}"
    else:
        found["identity"] = f"waiting bind of {member['launch_id'] or 'no launch'}"
    if bound is None:
        found["participant"] = "waiting bind"
        found["role"] = "waiting participant"
    else:
        found["participant"] = f"ok PT-{bound['id']}"
        held = set(bound["roles"].split(","))
        missing = [role for role in member["roles"].split(",") if role not in held]
        found["role"] = (f"ok {bound['roles']}" if not missing
                         else f"waiting grant PT-{bound['id']} --roles {','.join(missing)}")
    for dimension in SLICE2:
        found[dimension] = "unmeasured slice 2"
    return found


def is_ready(found: dict[str, str]) -> bool:
    """The first five ok; role may wait on a lead's grant (sessions-lever.md)."""
    head = all(found[d].startswith("ok") for d in ("process", "profile", "identity", "participant"))
    return head and (found["role"].startswith("ok") or found["role"].startswith("waiting grant"))


def readiness_lines(found: dict[str, str]) -> list[str]:
    return [f"  {dimension} {found[dimension]}" for dimension in READINESS]


# -- verbs ---------------------------------------------------------------------

def do_doctor(rest):
    options = parse(rest, optional=("team",))
    path = team_path(options)
    team, _ = load_team(path)
    lines = []
    for tool in ("tmux", "bwrap"):
        found = shutil.which(tool)
        if found is None:
            lines.append(f"missing {tool}: not on PATH")
            continue
        flag = "-V" if tool == "tmux" else "--version"
        try:
            version = subprocess.run(  # noqa: S603 - argv is a list, never a shell string
                [found, flag], capture_output=True, text=True, timeout=TMUX_TIMEOUT, check=False,
            ).stdout.strip() or "version unread"
        except (OSError, subprocess.TimeoutExpired) as error:
            version = f"version unread: {error}"
        lines.append(f"ok {tool}: {found} {version}")
    store = machine.store_path()
    if not store.is_file():
        lines.append(f"ok state store: absent at {store}")
        lines.append("ok coordination store: absent, so no lead is bound")
    else:
        conn = coordination_reader()
        try:
            conn.execute("SELECT name FROM sqlite_schema LIMIT 1").fetchall()
            lines.append(f"ok state store: {store}")
            try:
                leads = [row["id"] for row in conn.execute("SELECT id, roles FROM participants")
                         if "lead" in row["roles"].split(",")]
                lines.append("ok coordination store: " + (
                    "lead " + ", ".join(f"PT-{pid}" for pid in leads) + " bound" if leads
                    else "no lead bound"))
            except sqlite3.OperationalError:
                lines.append("ok coordination store: no participants table, so no lead is bound")
        except (sqlite3.DatabaseError, AttributeError) as error:
            lines.append(f"refused state store: {store} unreadable: {error}")
        finally:
            if conn is not None:
                conn.close()
    lines.append(f"ok python: {sys.executable} {sys.version.split()[0]}")
    for member in team["members"]:
        label = f"{member['name']} ({member['harness']})"
        exe = executable_of(member)
        if exe and os.path.isfile(exe):
            digest = hashlib.sha256(Path(exe).read_bytes()).hexdigest()
            lines.append(f"ok executable {label}: {exe} sha256={digest}")
        else:
            lines.append(f"missing executable {label}: {exe or member['harness'] + ' not on PATH'}")
        adapter = ADAPTERS / f"{member['harness']}.py"
        if adapter.is_file():
            lines.append(f"ok adapter {label}: {adapter.relative_to(REPO)}")
        else:
            lines.append(f"missing adapter {label}: no session_adapters/{member['harness']}.py; "
                         "slice 2 closes it")
    for line in lines:
        print(line)
    return EXIT_DONE if all(line.startswith("ok ") for line in lines) else EXIT_FINDING


def check_authority(member: dict) -> str | None:
    """None, or the lead's own PT-n when this shell carries the lead capability.

    A role above worker is the live lead's to grant: from the lead's own
    shell here, else by coordination.py grant afterwards. A capability that
    is not the lead's refuses `authority`.
    """
    above = [role for role in member["roles"] if role != "worker"]
    capability = os.environ.get("COORDINATION_CAPABILITY", "")
    if not above or not capability:
        return None
    remedy = (f"start without COORDINATION_CAPABILITY and let the lead run "
              f"coordination.py grant PT-n --roles {','.join(above)} once {member['name']} binds, "
              "or run start from the lead's own shell")
    if not re.fullmatch(r"[0-9a-f]{64}", capability):
        refuse("authority", "the lead's capability for " + ",".join(above), "a malformed capability", remedy)
    conn = coordination_reader()
    try:
        row = participant_by(conn, "capability_digest",
                             hashlib.sha256(capability.encode("ascii")).hexdigest())
    finally:
        if conn is not None:
            conn.close()
    if row is None or "lead" not in row["roles"].split(","):
        held = "no participant" if row is None else f"PT-{row['id']} holding {row['roles']}"
        refuse("authority", f"the lead's capability to grant {','.join(above)} to {member['name']}",
               f"a capability of {held}", remedy)
    return f"PT-{row['id']}"


def check_worktree(options) -> Path:
    if "worktree" not in options:
        return REPO
    path = Path(options["worktree"]).absolute()
    needed = "name a git worktree of this repository (git worktree list)"
    if not path.is_dir():
        refuse("worktree", f"a git worktree of {REPO}", f"{path}: no such directory", needed)
    common = []
    for where in (path, REPO):
        done = subprocess.run(  # noqa: S603 - argv is a list, never a shell string
            ["git", "-C", str(where), "rev-parse",  # noqa: S607 - git from PATH, as every lane tool
             "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=STEP_TIMEOUT, check=False,
        )
        common.append(Path(done.stdout.strip()).resolve() if done.returncode == 0 else None)
    if common[0] is None or common[0] != common[1]:
        refuse("worktree", f"a git worktree of {REPO}", f"{path}: not a worktree of it", needed)
    return path


def launched_elsewhere(conn, name: str):
    return conn.execute(
        "SELECT m.id, m.run, s.place FROM session_member m JOIN subjects s ON s.id = m.subject "
        "JOIN session_run sr ON sr.id = m.run JOIN subjects r ON r.id = sr.subject "
        "WHERE m.name = ? AND s.place IN ('launched', 'bound', 'ready') "
        "AND r.place IN ('open', 'stopping') ORDER BY m.id DESC LIMIT 1", (name,),
    ).fetchone()


def step(argv: list[str], log: Path) -> subprocess.CompletedProcess:
    done = subprocess.run(  # noqa: S603 - argv is a list, never a shell string
        argv, capture_output=True, text=True, timeout=STEP_TIMEOUT, check=False,
    )
    with log.open("a", encoding="utf-8") as handle:
        handle.write(f"$ {shlex.join(argv)}\nexit {done.returncode}\n{done.stderr}")
    return done


def last_line(done: subprocess.CompletedProcess) -> str:
    lines = (done.stderr or done.stdout).strip().splitlines()
    return lines[-1] if lines else f"exit {done.returncode}, no output"


def do_start(rest):
    options = parse(rest, required=("member",),
                    optional=("team", "run", "worktree", "ready-timeout", "tmux-socket"))
    agent = identity()
    path = team_path(options)
    team, team_sha = load_team(path)
    member = team_member(team, options["member"], path)
    timeout = seconds(options, "ready-timeout", 120)
    if shutil.which("tmux") is None:
        refuse("tmux", "tmux on PATH", "absent", "install tmux; sessions run in an owned tmux session")
    worktree = check_worktree(options)
    adapter = load_adapter(member["harness"])
    if adapter is None:
        refuse("team", "a member whose harness has an adapter in slice 1 (claude)",
               f"{member['name']} on {member['harness']}", "slice 2 adds the codex and grok adapters")
    lead = check_authority(member)
    conn = writer()
    with conn:
        clash = launched_elsewhere(conn, member["name"])
        if clash is not None:
            refuse("place", f"{member['name']} not launched in an open run",
                   f"SM-{clash['id']} in R-{clash['run']} at {clash['place']}",
                   f"sessions.py stop --run R-{clash['run']} first")
        if "run" in options:
            run = run_row(conn, run_number(options["run"]))
            if run is None:
                refuse("absent", "a run of this store", options["run"], "sessions.py status lists the runs")
            if run["place"] != "open":
                refuse("place", "an open run", f"R-{run['id']} at {run['place']}", "start a new run")
        else:
            subject = machine.create(conn, RUN, agent, note=f"team {path}")
            socket = options.get("tmux-socket") or os.environ.get("AGENTSCIENT_TMUX_SOCKET") or None
            rid = conn.execute(
                "INSERT INTO session_run(subject, name, team_file, team_sha256, tmux_socket, tmux_session, "
                "started_by, started_at) VALUES (?, ?, ?, ?, ?, '', ?, ?)",
                (subject, team["run"]["name"], str(path), team_sha, socket, agent, stamp()),
            ).lastrowid
            conn.execute("UPDATE session_run SET tmux_session = ? WHERE id = ?",
                         (f"{team['run']['tmux']}-R-{rid}", rid))
            run = run_row(conn, rid)
        owner = ownership(run)
        if owner not in ("absent", "owned"):
            if "run" not in options:
                machine.move(conn, RUN, run["subject"], "stop", agent, evidence="ownership refused before launch")
                machine.move(conn, RUN, run["subject"], "close", agent, evidence="no members")
            refuse_unowned(run, owner)
        previous = member_rows(conn, rid=run["id"], name=member["name"])
        generation = previous[-1]["generation"] + 1 if previous and previous[-1]["place"] != "reserved" else 1
        if previous and previous[-1]["place"] == "reserved":
            sid, generation = previous[-1]["id"], previous[-1]["generation"]
        else:
            subject = machine.create(conn, MEMBER, agent, note=f"R-{run['id']} {member['name']}")
            sid = conn.execute(
                "INSERT INTO session_member(subject, run, name, harness, roles, generation, worktree, "
                "evidence, started_by, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (subject, run["id"], member["name"], member["harness"], ",".join(member["roles"]),
                 generation, str(worktree), str(member_dir(run["id"], member["name"], generation)),
                 agent, stamp()),
            ).lastrowid
    return launch(conn, agent, team, member, run, sid, generation, worktree, adapter, lead, timeout)


def launch(conn, agent, team, member, run, sid, generation, worktree, adapter, lead, timeout):
    directory = member_dir(run["id"], member["name"], generation)
    if directory.exists() and any(directory.iterdir()):
        directory.rename(directory.with_name(f"{directory.name}.attempt-{time.time_ns()}"))
    directory.mkdir(parents=True, exist_ok=True)
    stderr_log = directory / "stderr.log"
    executable = executable_of(member)
    if not executable:
        refuse("profile", f"a {member['harness']} executable on PATH or in the team file",
               "absent", f"install {member['harness']} or name its absolute path as executable")
    prepared = step([sys.executable, str(PROFILES), "prepare-interactive", "--harness", member["harness"],
                     "--destination", str(directory), "--cwd", str(worktree),
                     "--executable", executable, "--agent", agent], stderr_log)
    if prepared.returncode != 0:
        refuse("profile", "profiles.py prepare-interactive to prepare the private profile",
               last_line(prepared),"fix what the profile refusal names, then start again")
    binding_path = Path(prepared.stdout.strip().splitlines()[-1])
    checked = step([sys.executable, str(PROFILES), "check", "--binding", str(binding_path)], stderr_log)
    if checked.returncode != 0:
        refuse("profile", "profiles.py check to accept the prepared profile",
               last_line(checked),"fix what the profile refusal names, then start again")
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    profile = str(binding_path.parent)
    launch_id = str(uuid.uuid4())
    argv = [str(part) for part in adapter.argv(member, binding, launch_id)]
    pane_log = directory / "pane.log"
    pane_log.touch(mode=0o600)
    command, env_file = launcher(argv, directory)
    session = run["tmux_session"]
    window = f"={session}:={member['name']}"
    owned = ownership(run)
    if owned == "owned":
        opening = ["new-window", "-d", "-P", "-F", "#{pane_id} #{pane_pid}", "-t", f"={session}:",
                   "-n", member["name"], "-c", str(worktree), *command]
    elif owned == "absent":
        opening = ["new-session", "-d", "-P", "-F", "#{pane_id} #{pane_pid}", "-s", session,
                   "-n", member["name"], "-c", str(worktree), *command,
                   ";", "set-option", "-t", f"={session}:", OWNER_OPTION, f"R-{run['id']}"]
    else:
        env_file.unlink(missing_ok=True)
        refuse_unowned(run, owned)
    # One tmux invocation, so the window keeps its dead pane and its
    # capture before the process in it can exit.
    created = tmux(run["tmux_socket"], *opening,
                   ";", "set-option", "-w", "-t", window, "remain-on-exit", "on",
                   ";", "pipe-pane", "-o", "-t", window, "cat >> " + shlex.quote(str(pane_log)))
    printed = created.stdout.split()
    if created.returncode != 0 or len(printed) < 2 or not printed[1].isdigit():
        env_file.unlink(missing_ok=True)
        refuse("tmux", f"tmux to open window {member['name']} in {session}",
               (created.stderr or created.stdout).strip() or f"exit {created.returncode}",
               "inspect the tmux server on the run's socket")
    pane, pid = printed[0], int(printed[1])
    ticks = None
    deadline = time.monotonic() + 5
    while ticks is None and time.monotonic() < deadline:
        ticks = start_ticks(pid)
        if ticks is None:
            time.sleep(0.02)
    record = {
        "run": f"R-{run['id']}", "member": member["name"], "sm": f"SM-{sid}",
        "generation": generation, "pane": pane, "pid": pid, "start_ticks": ticks,
        "launch_id": launch_id, "argv": argv, "tmux_socket": run["tmux_socket"],
        "tmux_session": session, "worktree": str(worktree), "profile": profile,
        "launched_at": stamp(), "launched_by": agent,
    }
    (directory / "launch.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    with conn:
        conn.execute(
            "UPDATE session_member SET launch_id = ?, pid = ?, start_ticks = ?, pane = ?, profile = ? "
            "WHERE id = ?", (launch_id, pid, ticks, pane, profile, sid))
        machine.move(conn, MEMBER, member_row(conn, sid)["subject"], "launch", agent, evidence=f"pane {pane} pid {pid}")
    return settle(conn, agent, member, run, sid, generation, pane, lead, timeout)


def member_row(conn, sid: int):
    return conn.execute(
        "SELECT m.*, s.place FROM session_member m JOIN subjects s ON s.id = m.subject WHERE m.id = ?",
        (sid,),
    ).fetchone()


def settle(conn, agent, member, run, sid, generation, pane, lead, timeout):
    """Wait for identity and participant; bind, grant through the lead, ready."""
    deadline = time.monotonic() + timeout
    granted = False
    while True:
        row = member_row(conn, sid)
        found = readiness(row, check_profile=False)
        if found["identity"].startswith("refused native"):
            record_readiness(conn, sid, found)
            refuse("native", f"the native session the launch named, {row['launch_id']}",
                   found["identity"].removeprefix("refused native "),
                   "relaunch the profile; never rebind it (sessions.py stop --terminate, then start)")
        if row["place"] == "launched" and found["participant"].startswith("ok"):
            with conn:
                conn.execute("UPDATE session_member SET native_id = ?, participant = ? WHERE id = ?",
                             (found["identity"].split()[1],
                              int(found["participant"].split("PT-")[1]), sid))
                machine.move(conn, MEMBER, row["subject"], "bind", agent,
                             evidence=f"native {found['identity'].split()[1]} {found['participant'].split()[1]}")
            continue
        if found["role"].startswith("waiting grant") and lead and not granted:
            granted = True
            missing = found["role"].split("--roles ")[1]
            subprocess.run(  # noqa: S603 - argv is a list, never a shell string
                [sys.executable, str(COORDINATION), "grant", found["participant"].split()[1],
                 "--roles", missing], capture_output=True, text=True, timeout=STEP_TIMEOUT, check=False,
            )
            continue
        if row["place"] == "bound" and found["process"].startswith("ok"):
            found["profile"] = profile_reading(row["profile"])
            if is_ready(found):
                with conn:
                    machine.move(conn, MEMBER, row["subject"], "ready", agent,
                                 evidence="; ".join(f"{d} {found[d]}" for d in READINESS))
                return report(conn, member, run, sid, generation, pane, found, EXIT_DONE)
        if not found["process"].startswith("ok"):
            # A pane that exited never reads ready, whatever else bound.
            record_readiness(conn, sid, found)
            refuse("readiness", f"process ok for {member['name']} SM-{sid} until ready",
                   f"process {found['process']}; " + "; ".join(
                       f"{d} {found[d]}" for d in READINESS if d != "process"),
                   f"read {member_dir(run['id'], member['name'], generation) / 'pane.log'}, "
                   "then sessions.py stop --terminate and start again")
        if time.monotonic() >= deadline:
            if row["place"] == "bound":
                found["profile"] = profile_reading(row["profile"])
            return report(conn, member, run, sid, generation, pane, found, EXIT_FINDING)
        time.sleep(POLL)


def record_readiness(conn, sid: int, found: dict[str, str]) -> None:
    with conn:
        conn.execute("UPDATE session_member SET readiness = ? WHERE id = ?", (json.dumps(found), sid))


def report(conn, member, run, sid, generation, pane, found, code):
    record_readiness(conn, sid, found)
    participant = found["participant"].split()[1] if found["participant"].startswith("ok") else "-"
    print(f"started {member['name']} SM-{sid} as {participant} in R-{run['id']} "
          f"pane {pane} gen {generation}")
    for line in readiness_lines(found):
        print(line)
    return code


def do_status(rest):
    options = parse(rest, optional=("run", "member"))
    conn = reader()
    if conn is None:
        print("no runs")
        return EXIT_DONE
    with conn:
        if "run" in options:
            runs = [chosen_run(conn, options)]
        else:
            runs = conn.execute(
                "SELECT r.*, s.place FROM session_run r JOIN subjects s ON s.id = r.subject ORDER BY r.id"
            ).fetchall()
        if not runs:
            print("no runs")
            return EXIT_DONE
        for run in runs:
            print(f"R-{run['id']} {run['place']} {run['name']} tmux {run['tmux_session']}")
            for member in member_rows(conn, rid=run["id"], name=options.get("member")):
                found = readiness(member, check_profile=member["place"] in LIVE)
                alive = "ok" if found["process"].startswith("ok") else "gone"
                participant = f"PT-{member['participant']}" if member["participant"] else "-"
                print(f"R-{run['id']} {member['name']} SM-{member['id']} {member['place']} "
                      f"{participant} gen {member['generation']} pane {member['pane'] or '-'} "
                      f"process {alive}")
                for line in readiness_lines(found):
                    print(line)
    return EXIT_DONE


def newest_member(conn, run, name: str):
    rows = member_rows(conn, rid=run["id"], name=name)
    if not rows:
        refuse("absent", f"member {name} in R-{run['id']}", "none", "sessions.py status --run R-n")
    return rows[-1]


def do_attach(rest):
    options = parse(rest, required=("member",), optional=("run",))
    identity()
    conn = reader()
    try:
        run = chosen_run(conn, options, places=("open",))
        member = newest_member(conn, run, options["member"])
    finally:
        if conn is not None:
            conn.close()
    if not member["pane"]:
        refuse("absent", f"a pane for {member['name']} SM-{member['id']}", "none",
               "sessions.py start --member NAME")
    needed = f"sessions.py status --run R-{run['id']}; start {member['name']} again after stop"
    owner = ownership(run)
    if owner == "absent":
        refuse("absent", f"the pane of {member['name']} SM-{member['id']} in tmux session "
               f"{run['tmux_session']}", "no such session", needed)
    if owner != "owned":
        refuse_unowned(run, owner)
    window = f"={run['tmux_session']}:={member['name']}"
    shown = tmux(run["tmux_socket"], "select-window", "-t", window)
    if shown.returncode != 0:
        refuse("absent", f"the pane of {member['name']} SM-{member['id']} in tmux session "
               f"{run['tmux_session']}", shown.stderr.strip() or f"exit {shown.returncode}", needed)
    verb = "switch-client" if os.environ.get("TMUX") else "attach-session"
    binary = shutil.which("tmux")
    os.execv(binary, [binary,  # noqa: S606 - attach hands this terminal to tmux, argv a list
*socket_args(run["tmux_socket"]), verb, "-t", window])
    return EXIT_DONE


def do_stop(rest):
    options = parse(rest, optional=("run", "drain"), flags=("terminate",))
    agent = identity()
    drain = seconds(options, "drain", 0)
    terminate = bool(options.get("terminate"))
    if reader() is None:
        refuse("absent", "a run of this store", options.get("run", "none"), "sessions.py status")
    conn = writer()
    with conn:
        run = chosen_run(conn, options)
        if run["place"] == "stopped":
            refuse("place", "an open or stopping run", f"R-{run['id']} at stopped", "nothing to stop")
        if run["place"] == "open":
            machine.move(conn, RUN, run["subject"], "stop", agent,
                         evidence="terminate" if terminate else f"drain {drain}s")
        members = [row for row in member_rows(conn, rid=run["id"]) if row["place"] in LIVE]
    deadline = time.monotonic() + drain
    while not terminate and time.monotonic() < deadline and any(
            row["pid"] and start_ticks(row["pid"]) == row["start_ticks"] for row in members):
        time.sleep(POLL)
    owner = ownership(run)
    outcomes = []
    for row in members:
        adapter = load_adapter(row["harness"])
        if row["pid"] is None:
            outcome = "unresolved no pid recorded"
        elif not terminate:
            outcome = ("stopped exited" if start_ticks(row["pid"]) != row["start_ticks"]
                       else f"unresolved running pid {row['pid']}")
        else:
            outcome = adapter.stop({"pid": row["pid"], "start": row["start_ticks"]}, True)
        if terminate and owner == "owned":
            window = f"={run['tmux_session']}:={row['name']}"
            if tmux(run["tmux_socket"], "has-session", "-t", window).returncode == 0:
                tmux(run["tmux_socket"], "kill-window", "-t", window)
        with conn:
            if outcome.startswith("stopped"):
                machine.move(conn, MEMBER, row["subject"], f"stop-{row['place']}", agent, evidence=outcome)
            elif terminate:
                machine.move(conn, MEMBER, row["subject"], f"lose-{row['place']}", agent, evidence=outcome)
            conn.execute("UPDATE session_member SET outcome = ? WHERE id = ?", (outcome, row["id"]))
        outcomes.append(outcome)
        print(f"R-{run['id']} {row['name']} SM-{row['id']} {outcome}")
    if terminate and owner not in ("owned", "absent"):
        print(f"R-{run['id']} unresolved tmux session {run['tmux_session']} is not owned "
              f"({OWNER_OPTION} {owner}); nothing in it was touched")
    with conn:
        left = [row for row in member_rows(conn, rid=run["id"]) if row["place"] in LIVE]
        if not left:
            settled = ", ".join(f"SM-{row['id']} {row['place']}" for row in member_rows(conn, rid=run["id"]))
            machine.move(conn, RUN, run["subject"], "close", agent, evidence=settled or "no members")
            print(f"R-{run['id']} stopped")
    return EXIT_DONE if all(outcome.startswith("stopped") for outcome in outcomes) and not left \
        else EXIT_FINDING


def secrets_of(profile: str | None) -> list[str]:
    """The binding's capability and every credential_environment value."""
    if not profile:
        return []
    try:
        binding = json.loads((Path(profile) / "binding.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    values = [binding.get("coordination_capability")]
    values += list((binding.get("credential_environment") or {}).values())
    return sorted({str(value) for value in values if value}, key=len, reverse=True)


def scrub(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, "[omitted]")
    return text


def do_export(rest):
    options = parse(rest, required=("to",), optional=("run",))
    identity()
    conn = reader()
    try:
        run = chosen_run(conn, options, places=("open", "stopping", "stopped"))
        members = member_rows(conn, rid=run["id"])
    finally:
        if conn is not None:
            conn.close()
    dest = Path(options["to"]).absolute()
    dest.mkdir(parents=True, exist_ok=True)
    secrets = sorted({s for row in members for s in secrets_of(row["profile"])}, key=len, reverse=True)
    failures: list[str] = []
    files = 0

    def write(relative: str, text: str) -> None:
        nonlocal files
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(scrub(text, secrets), encoding="utf-8")
        files += 1

    described = []
    for row in members:
        found = readiness(row, check_profile=False)
        entry = dict(row)
        entry["readiness"] = found
        entry["process_identity"] = {"pid": row["pid"], "start_ticks": row["start_ticks"],
                                     "alive": found["process"].startswith("ok")}
        described.append(entry)
        folder = row["name"] if row["generation"] == 1 else f"{row['name']}-gen-{row['generation']}"
        adapter = load_adapter(row["harness"])
        retained = adapter.diagnostics(row["evidence"]) if adapter is not None else []
        exported = []
        for source in retained:
            name = Path(source).name
            try:
                text = Path(source).read_text(encoding="utf-8", errors="replace")
            except OSError as error:
                failures.append(f"{row['name']} {name}: {type(error).__name__}: {error}")
                continue
            write(f"{folder}/{name}", text)
            exported.append(f"{folder}/{name}")
        write(f"{folder}/diagnostics.json", json.dumps(exported, indent=1) + "\n")
    summary = {
        "run": dict(run),
        "team_sha256": run["team_sha256"],
        "tmux": {"socket": run["tmux_socket"], "session": run["tmux_session"]},
        "members": described,
        "exported_at": stamp(),
        "omitted": "each binding's coordination_capability and credential_environment values",
    }
    write("run.json", json.dumps(summary, indent=1, default=str) + "\n")
    if failures:
        print(f"partial {dest} ({len(members)} members, {files} files); first failure: {failures[0]}")
        return EXIT_FINDING
    print(f"exported {dest} ({len(members)} members, {files} files)")
    return EXIT_DONE


LATER = {"join": "slice 2", "recover": "slice 2"}
VERBS = {
    "doctor": do_doctor, "start": do_start, "status": do_status,
    "attach": do_attach, "stop": do_stop, "export": do_export,
}


def main(argv: list[str]) -> int:
    verb = argv[1] if len(argv) > 1 else ""
    try:
        if verb in LATER:
            refuse("arguments", "a slice 1 verb: " + ", ".join(VERBS), f"{verb}, which is {LATER[verb]}",
                   "the courier route lands in slice 2; sessions-lever.md lists slice 1")
        if verb not in VERBS:
            refuse("arguments", "one of " + ", ".join(VERBS), verb or "no verb",
                   "name one verb; the module doc has the arguments")
        return VERBS[verb](argv[2:]) or EXIT_DONE
    except Refusal as refusal:
        return emit(refusal)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
