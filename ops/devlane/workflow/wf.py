#!/usr/bin/env python3
"""wf — the dev-lane workflow recorder (PLAN §4).

Agent-first by contract: ``--json`` on every command, documented exit codes,
no interactive prompts anywhere, and outputs that stay small — tails, not
dumps; digests, not bodies.

Exit codes (PLAN §4, loopflow's, unchanged):

  0   ok, including a recorded denial
  1   refused or failed, naming the first failed precondition
  2   evidence integrity — something did not re-hash to what was recorded
  3   claim held by another agent (Slice 2)
  64  usage

and, outside that map, 70 for an internal error — a bug in wf is neither a
refusal nor an integrity failure, and filing a crash under "refused" is the
one reading that must never be wrong.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import canonical
import chain as chainmod
import coord
import gatekinds
import gitio
import query
import receipts
import verify
from cas import Cas
from errors import (
    EXIT_INTERNAL, EXIT_OK, EXIT_REFUSED,
    Integrity, Refusal, Usage, WfError,
)
from store import Store

# A Co-Authored-By value: a name, then a vendor address in angle brackets.
AGENT_IDENTITY = re.compile(r"^\S.*\s<[^<>@\s]+@[^<>@\s]+>$")

CODE_DIR = Path(__file__).resolve().parent
EXPORT_FORMAT_VERSION = 1
TAIL_BYTES = 2000

# Chain-appending verbs auto-commit by default (D5) and require an agent
# identity from the first commit (PLAN §4).
APPENDING_VERBS = {"open", "red", "green", "check", "outcome", "marker", "advance"}


# --------------------------------------------------------------------------
# context


class Context:
    """Everything a verb needs: paths, the database, the registry, identity."""

    def __init__(self, args):
        self.args = args
        root = getattr(args, "root", None)
        self.root = Path(root).resolve() if root else CODE_DIR
        self.json = bool(getattr(args, "json", False))
        self.agent = getattr(args, "agent", None) or os.environ.get("WF_AGENT") or ""
        self.sources = list(getattr(args, "source", None) or [])
        self.no_commit = bool(getattr(args, "no_commit", False))
        self.migrations = CODE_DIR / "migrations"
        # Set false by verify-only paths: CI reads evidence and originates
        # none, and a session row is state however small it is.
        self.records = True
        self.EXPORT_FORMAT_VERSION = EXPORT_FORMAT_VERSION
        self.store = None
        self.chain = None
        self.cas = Cas(self.root / "objects")
        self._specs = None
        self._repo = None

    # -- paths -------------------------------------------------------------

    @property
    def chains_dir(self) -> Path:
        return self.root / "chains"

    @property
    def attempts_dir(self) -> Path:
        return self.root / "attempts"

    @property
    def gate_kinds_dir(self) -> Path:
        return self.root / "gate-kinds"

    @property
    def meta_path(self) -> Path:
        return self.root / "meta.json"

    @property
    def db_path(self) -> Path:
        return self.root / "wf.db"

    @property
    def repo(self) -> Path:
        if self._repo is None:
            out = subprocess.run(
                ["git", "-C", str(self.root), "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=False)
            if out.returncode != 0:
                raise Refusal(
                    "the state root is inside a git repository",
                    actual=str(self.root),
                    needed="a checkout — the chain binds to commits",
                )
            self._repo = Path(out.stdout.strip())
        return self._repo

    def ensure_dirs(self) -> None:
        for path in (self.chains_dir, self.attempts_dir, self.root / "objects"):
            path.mkdir(parents=True, exist_ok=True)

    # -- resources ---------------------------------------------------------

    def open_store(self, migrate: bool = True) -> Store:
        if self.store is None:
            self.store = Store(self.db_path)
            if migrate:
                self.store.migrate(self.migrations, canonical.now())
                if self.records:
                    # Presence, not permission: one row per agent, never
                    # exported — and never written by a verify-only run.
                    coord.touch_session(self.store, self.agent, "",
                                        canonical.now())
            self.chain = chainmod.Chain(self.store)
        return self.store

    @property
    def specs(self) -> dict:
        if self._specs is None:
            self._specs = gatekinds.load_specs(self.gate_kinds_dir)
        return self._specs

    def spec_for(self, wo_row) -> gatekinds.Spec:
        return query.spec_for(self, wo_row)

    def require_agent(self) -> str:
        if not self.agent:
            raise Refusal(
                "an agent identity is supplied",
                needed="--agent 'Model Name <noreply@vendor>' or $WF_AGENT",
            )
        if not AGENT_IDENTITY.match(self.agent):
            # The value becomes a Co-Authored-By trailer. A bare name produces
            # `Co-Authored-By: some-agent`, which is not a trailer git or the
            # forge will attribute — so the malformed case refuses here rather
            # than reaching a commit.
            raise Refusal(
                "the agent identity carries a vendor address",
                actual=self.agent,
                needed=("the form 'Claude Opus 5 <noreply@anthropic.com>' —"
                        " AGENTS.md requires the specific model and a vendor"
                        " noreply address"),
            )
        return self.agent

    def work_order(self, wo_id: str):
        row = self.store.get_work_order(wo_id)
        if row is None:
            known = [r["wo_id"] for r in self.store.list_work_orders()]
            raise Refusal(
                "work order exists",
                actual=wo_id,
                expected=", ".join(known) or "(none open)",
                needed="wf open, or an id that has been opened",
                wo=wo_id,
            )
        return row

    # -- output ------------------------------------------------------------

    def emit(self, obj, human: str) -> None:
        print(canonical.dumps(obj) if self.json else human)


# --------------------------------------------------------------------------
# attempts — every attempted transition, refusals included


def _snapshot(ctx, wo_id):
    """Best-effort (seq, hash, stage) for an attempt's bindings.

    Deliberately tolerant of a broken chain: an integrity failure is exactly
    the moment the attempt record matters most, so it must not itself depend
    on the chain being sound.
    """
    tail = ctx.store.chain_tail(wo_id) if ctx.store else None
    seq = tail["seq"] if tail else 0
    head = tail["hash"] if tail else ""
    stage = ""
    row = ctx.store.get_state(wo_id) if ctx.store else None
    if row is not None:
        try:
            stage = canonical.loads(row["state_json"]).get("stage") or ""
        except (ValueError, AttributeError):
            stage = ""
    return seq, head, stage


def _tail(text: str) -> str:
    if text is None:
        return ""
    return text[-TAIL_BYTES:]


def record_attempt(ctx, wo_id, verb, argv, before, exit_code, record_kind,
                   reason="", event_appended=0, stdout="", stderr=""):
    """Append one attempt row. Never raises: a failed record must not mask
    the failure it was recording."""
    try:
        after = _snapshot(ctx, wo_id)
        n = ctx.store.count_attempts(wo_id) + 1
        ctx.store.insert_attempt({
            "attempt_id": f"{wo_id}#{n:06d}",
            "wo_id": wo_id,
            "verb": verb,
            "agent": ctx.agent,
            "argv": canonical.dumps(list(argv)),
            "attempted_at": canonical.now(),
            "duration_ms": 0,
            "exit_code": exit_code,
            "record_kind": record_kind,
            "exhaustiveness": "first-failure" if record_kind == "refusal" else "",
            "reason": reason,
            "event_appended": event_appended,
            "seq_before": before[0],
            "seq_after": after[0],
            "head_before": before[1],
            "head_after": after[1],
            "stage_before": before[2],
            "stage_after": after[2],
            "stdout_tail": _tail(stdout),
            "stderr_tail": _tail(stderr),
            "stdout_sha256": canonical.sha256_hex(stdout.encode()) if stdout else "",
            "stderr_sha256": canonical.sha256_hex(stderr.encode()) if stderr else "",
        })
    except Exception:  # noqa: BLE001,S110 — recording must never
        # mask the result it is recording; pragma: no cover
        pass


class Attempt:
    """Records one attempted transition, whatever its outcome."""

    def __init__(self, ctx, wo_id, verb, argv):
        self.ctx = ctx
        self.wo_id = wo_id
        self.verb = verb
        self.argv = list(argv)
        self.before = None
        self.started = None
        self.events = 0
        self.stdout = ""
        self.stderr = ""

    def __enter__(self):
        self.before = _snapshot(self.ctx, self.wo_id)
        self.started = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is None:
            record_attempt(
                self.ctx, self.wo_id, self.verb, self.argv, self.before,
                exit_code=EXIT_OK, record_kind="accepted", event_appended=self.events,
                stdout=self.stdout, stderr=self.stderr,
            )
        elif isinstance(exc, WfError):
            record_attempt(
                self.ctx, self.wo_id, self.verb, self.argv, self.before,
                exit_code=exc.exit_code, record_kind=exc.kind, reason=str(exc),
                event_appended=self.events, stdout=self.stdout, stderr=self.stderr,
            )
        return False


# --------------------------------------------------------------------------
# helpers shared by verbs


def cmd_init(ctx, args) -> int:
    if not ctx.gate_kinds_dir.exists():
        raise Refusal(
            "the gate-kind registry directory exists",
            actual=str(ctx.gate_kinds_dir),
            needed="a gate-kinds/ directory holding the registry",
        )
    ctx.ensure_dirs()
    if args.rebuild and not ctx.meta_path.exists():
        # Minting it here and then accepting the version we just wrote would
        # make the format check a mirror: a change that deletes meta.json
        # would rebuild green. The export must carry its own version.
        raise Refusal(
            "the export declares its format version",
            actual=f"{ctx.meta_path} is missing",
            needed="a tracked meta.json — run wf init (without --rebuild) to create one",
        )
    if not ctx.meta_path.exists():
        ctx.meta_path.write_bytes(
            canonical.dumpb({"format_version": EXPORT_FORMAT_VERSION})
        )
    if args.rebuild:
        result = rebuild(ctx)
        registered = sorted(f"{k}@{v}" for (k, v) in ctx.specs)
        ctx.emit(
            {"root": str(ctx.root), "rebuilt": True, "gate_kinds": registered,
             "format_version": EXPORT_FORMAT_VERSION, **result},
            f"rebuilt {ctx.root} from the export: {len(result['work_orders'])}"
            f" work order(s), {result['events']} event(s),"
            f" {result['attempts']} attempt(s), {result['objects']} object(s)",
        )
        return EXIT_OK

    store = ctx.open_store(migrate=False)
    applied = store.migrate(ctx.migrations, canonical.now())
    specs = ctx.specs
    gatekinds.sync(store, specs, canonical.now())
    registered = sorted(f"{k}@{v}" for (k, v) in specs)
    ctx.emit(
        {"root": str(ctx.root), "rebuilt": False, "migrations_applied": applied,
         "gate_kinds": registered, "format_version": EXPORT_FORMAT_VERSION},
        f"init {ctx.root}: {len(applied)} migration(s) applied, "
        f"gate kinds {', '.join(registered)}",
    )
    return EXIT_OK


def allocate_wo_id(store) -> str:
    used = set()
    for row in store.list_work_orders():
        wo = row["wo_id"]
        if wo.startswith("WO-") and wo[3:].isdigit():
            used.add(int(wo[3:]))
    n = 1
    while n in used:
        n += 1
    return f"WO-{n:03d}"


def cmd_open(ctx, args) -> int:
    agent = ctx.require_agent()
    store = ctx.open_store()
    spec = gatekinds.latest(ctx.specs, args.kind)

    wo_id = args.wo
    if wo_id is None:
        wo_id = allocate_wo_id(store)
    elif not (wo_id.startswith("WO-") and len(wo_id) >= 6 and wo_id[3:].isdigit()):
        raise Refusal(
            "work-order ids take the form WO-NNN",
            actual=wo_id, needed="WO- followed by at least three digits (D6)",
        )

    existing = store.get_work_order(wo_id)
    if existing is not None:
        # Idempotent: a re-run with identical arguments is a no-op success.
        same = (
            existing["kind"] == spec.kind
            and existing["kind_version"] == spec.version
            and existing["spec_sha256"] == spec.sha256
            and existing["objective"] == args.objective
        )
        if not same:
            raise Refusal(
                "the work order is not already open with different arguments",
                actual=f"{wo_id} is {existing['kind']}@{existing['kind_version']}"
                       f" — {existing['objective']!r}",
                needed="a new id, or the same arguments it was opened with",
                wo=wo_id,
            )
        projection = ctx.chain.project(wo_id)
        ctx.emit({**summarise(ctx, existing, projection), "created": False},
                 f"{wo_id} already open at stage {projection.state.get('stage')}")
        return EXIT_OK

    with Attempt(ctx, wo_id, "open", sys.argv[1:]) as attempt:
        require_sources(ctx, "open")   # the objective is authored text
        digest = ctx.cas.put_json(spec.raw)
        store.upsert_artifact(
            digest, len(canonical.dumpb(spec.raw)), "application/json",
            "gate-kind-spec", canonical.now(),
        )
        store.insert_work_order(
            wo_id, args.objective, spec.kind, spec.version, digest, canonical.now()
        )
        ctx.chain.append(wo_id, {
            "type": chainmod.WO_OPENED, "kind": spec.kind, "kind_version": spec.version,
            "spec_sha256": digest, "objective": args.objective,
            "agent": agent, "sources": ctx.sources,
        })
        ctx.chain.append(wo_id, {
            "type": chainmod.STAGE_ENTERED, "stage": spec.first_stage,
            "frozen": None, "agent": agent, "sources": ctx.sources,
        })
        attempt.events = 2

    maybe_commit(ctx, wo_id, "open", f"{chainmod.WO_OPENED} {spec.kind}@{spec.version}")
    row = store.get_work_order(wo_id)
    projection = ctx.chain.project(wo_id)
    ctx.emit(
        {**summarise(ctx, row, projection), "created": True},
        f"{wo_id} opened — {spec.kind}@{spec.version}, stage {spec.first_stage}",
    )
    return EXIT_OK


def cmd_claim(ctx, args) -> int:
    agent = ctx.require_agent()
    ctx.open_store()
    ctx.work_order(args.wo)
    body = coord.claim(
        ctx.store, args.wo, agent, args.ttl, args.note, canonical.now()
    )
    ctx.emit(
        body,
        f"{args.wo} {'renewed by' if body['renewed'] else 'claimed by'} {agent}"
        f" until {body['expires_at']}",
    )
    return EXIT_OK


def cmd_release(ctx, args) -> int:
    agent = ctx.require_agent()
    ctx.open_store()
    ctx.work_order(args.wo)
    body = coord.release(ctx.store, args.wo, agent, canonical.now())
    if body["released"]:
        human = (f"{args.wo} released"
                 + (" (the claim had already expired)" if body["was_expired"] else ""))
    else:
        human = f"{args.wo} had no claim to release"
    ctx.emit(body, human)
    return EXIT_OK


def cmd_next(ctx, args) -> int:
    ctx.open_store()
    if args.wo:
        rows = [ctx.work_order(args.wo)]
    else:
        rows = [
            r for r in ctx.store.list_work_orders()
            if ctx.chain.project(r["wo_id"]).state.get("status") != "terminal"
        ]
        if not rows:
            ctx.emit({"wo": None, "note": "no open work orders"}, "no open work orders")
            return EXIT_OK
        rows = rows[:1]

    row = rows[0]
    projection = ctx.chain.project(row["wo_id"])
    body = summarise(ctx, row, projection)
    body.update(next_action(ctx, row, projection))
    human = (
        f"{body['wo']} {body['kind']} stage={body['stage']} "
        f"missing={','.join(body['missing']) or '-'}\n"
        f"  {' '.join(body['advances']) or '(nothing — ' + str(body.get('note')) + ')'}"
    )
    ctx.emit(body, human)
    return EXIT_OK


def cmd_status(ctx, args) -> int:
    if args.checks:
        # Reads the tracked registry only: no database, no migration, no
        # session row. CI's matrix step runs this before anything has been
        # rebuilt, and it must originate nothing.
        checks = registered_checks(ctx)
        runnable = sorted({c["name"] for c in checks if c["ci"]})
        human = "\n".join(
            f"{c['kind']}@{c['kind_version']}  {c['name']:<18} {c['class']:<12}"
            f" {'ci' if c['ci'] else '--'}  {' '.join(c['argv'])}"
            for c in checks
        ) or "no checks registered"
        if checks:
            human += (f"\n--- {len(runnable)} of {len(checks)} run in CI:"
                      f" {', '.join(runnable) or '(none)'}")
        ctx.emit({"checks": checks, "ci_matrix": runnable}, human)
        return EXIT_OK

    ctx.open_store()
    if args.wo:
        row = ctx.work_order(args.wo)
        projection = ctx.chain.project(row["wo_id"])
        body = summarise(ctx, row, projection)
        body["events"] = [
            {"seq": e["seq"], "type": e.get("type"), "time": e["time"]}
            for e in projection.events
        ]
        body["attempts"] = ctx.store.count_attempts(row["wo_id"])
        human = "\n".join([
            f"{body['wo']} {body['kind']} — {body['objective']}",
            f"  stage    {body['stage']} ({body['status']})",
            (f"  evidence {', '.join(body['satisfied']) or '-'}"
            f"  missing {', '.join(body['missing']) or '-'}"),
            (f"  chain    seq {body['seq']} {str(body['head'])[:12]}"
            f"  attempts {body['attempts']}"),
        ])
        ctx.emit(body, human)
        return EXIT_OK

    payload = query.status_body(ctx)
    items, sessions = payload["work_orders"], payload["sessions"]
    human = "\n".join(
        f"{i['wo']}  {i['kind']:<12} {i['stage']!s:<8} {i['status']:<8} "
        f"seq={i['seq']:<4} {i['objective']}"
        + (f"  [claimed by {i['claim']['agent']}]" if i.get("claim") else "")
        for i in items
    ) or "no work orders"
    if sessions:
        human += "\n--- active\n" + "\n".join(
            f"  {s['agent']}  last seen {s['last_seen']}" for s in sessions
        )
    ctx.emit(payload, human)
    return EXIT_OK


def cmd_log(ctx, args) -> int:
    ctx.open_store()
    row = ctx.work_order(args.wo)
    projection = ctx.chain.project(row["wo_id"])

    for requested in (args.type or []):
        base = requested.split(gatekinds.REQUIREMENT_SEPARATOR, 1)[0]
        if not chainmod.is_known_type(base):
            raise Refusal(
                "the event type is one the chain can hold",
                actual=requested,
                expected=", ".join(chainmod.KNOWN_TYPES),
                needed="a known type, or receipt.<something> — a typo would"
                       " otherwise read as an empty log",
                wo=row["wo_id"],
            )
    since = None
    if args.since:
        try:
            since = canonical.format_time(canonical.parse_time(args.since))
        except (ValueError, TypeError) as exc:
            raise Refusal(
                "--since is a canonical timestamp",
                actual=args.since,
                needed=f"{canonical.now()} — {exc}",
            ) from None

    tail = -1 if args.all else args.number
    events = filter_events(
        projection.events, types=args.type, agent=args.recorded_by, since=since,
        tail=(query.DEFAULT_LOG_TAIL if tail is None
              else (None if tail < 0 else tail)),
    )
    filtered = (args.type or args.recorded_by or args.since
                or args.number is not None)
    # Compact by default: every harness pays this body per call, and the
    # payload is what --full is for. `considered` is unconditional so a
    # bounded or compact answer says what it was an answer about.
    body = {"wo": row["wo_id"],
            "events": events if args.full else query.compact_events(events)}
    body["considered"] = len(projection.events)
    if filtered:
        # Distinguishing "nothing matched" from "the filter is broken" is the
        # whole reason these two numbers are reported.
        body["matched"] = len(events)
    if args.attempts:
        rows = [dict(a) for a in ctx.store.list_attempts(row["wo_id"])]
        if args.recorded_by:
            rows = [a for a in rows if a.get("agent") == args.recorded_by]
        body["attempts"] = rows
    human_lines = [
        f"{e['seq']:>3}  {e['time']}  {e.get('type')}  {e['hash'][:12]}"
        for e in events
    ]
    if args.attempts:
        human_lines.append("--- attempts")
        human_lines += [
            f"  {a['attempt_id']}  {a['verb']:<8} {a['record_kind']:<9}"
            f" exit={a['exit_code']}  {a['reason'][:70]}"
            for a in body["attempts"]
        ]
    if filtered:
        human_lines.append(
            f"--- {len(events)} of {len(projection.events)} event(s) matched"
        )
    ctx.emit(body, "\n".join(human_lines) or "(no events matched)")
    return EXIT_OK


def cmd_agents(ctx, args) -> int:
    """Per-agent visibility as a projection over what is already recorded.

    PLAN §9: receipts, attempts and claims already carry `agent`, so this
    invents no storage — it counts what the chain and the attempt log say.
    """
    ctx.open_store()
    now = canonical.now()
    agents = {}

    def slot(name):
        return agents.setdefault(name, {
            "agent": name, "events": 0, "receipts": {}, "attempts": {},
            "work_orders": [], "holds": [],
        })

    for row in ctx.store.list_work_orders():
        wo = row["wo_id"]
        for event in ctx.chain.project(wo).events:
            name = event.get("agent")
            if not name:
                continue
            entry = slot(name)
            entry["events"] += 1
            if wo not in entry["work_orders"]:
                entry["work_orders"].append(wo)
            etype = event.get("type", "")
            if etype.startswith(chainmod.RECEIPT_PREFIX):
                key = etype
                if event.get("class"):
                    key = f"{etype}:{event['class']}"
                entry["receipts"][key] = entry["receipts"].get(key, 0) + 1
        for attempt in ctx.store.list_attempts(wo):
            name = attempt["agent"]
            if not name:
                continue
            entry = slot(name)
            kind = attempt["record_kind"]
            entry["attempts"][kind] = entry["attempts"].get(kind, 0) + 1
        claim = coord.current(ctx.store, wo, now)
        if claim:
            slot(claim["agent"])["holds"].append(wo)

    listed = [agents[name] for name in sorted(agents)]
    for entry in listed:
        entry["work_orders"].sort()
        entry["holds"].sort()
    sessions = coord.active_sessions(ctx.store, now)
    active = {s["agent"] for s in sessions}
    for entry in listed:
        entry["active"] = entry["agent"] in active

    human = "\n".join(
        f"{e['agent']}\n"
        f"    events {e['events']:<5} receipts "
        f"{', '.join(f'{k}={v}' for k, v in sorted(e['receipts'].items())) or '-'}\n"
        f"    attempts "
        f"{', '.join(f'{k}={v}' for k, v in sorted(e['attempts'].items())) or '-'}"
        f"    holds {', '.join(e['holds']) or '-'}"
        f"{'   (active)' if e['active'] else ''}"
        for e in listed
    ) or "no agents have recorded anything"
    ctx.emit({"agents": listed}, human)
    return EXIT_OK


def missing_evidence(*args, **kwargs):
    return query.missing_evidence(*args, **kwargs)

def build_check_argv(*args, **kwargs):
    return query.build_check_argv(*args, **kwargs)

def next_action(*args, **kwargs):
    return query.next_action(*args, **kwargs)

def summarise(*args, **kwargs):
    return query.summarise(*args, **kwargs)

def registered_checks(*args, **kwargs):
    return query.registered_checks(*args, **kwargs)

def filter_events(*args, **kwargs):
    return query.filter_events(*args, **kwargs)


def prepared(ctx, wo_id):
    """Row, pinned spec and verified projection, in that order.

    Projection comes last on purpose: it is the call that can raise an
    integrity error, and by then the pin has already been checked.
    """
    ctx.open_store()
    row = ctx.work_order(wo_id)
    spec = ctx.spec_for(row)
    projection = ctx.chain.project(wo_id)
    return row, spec, projection


def require_unclaimed(ctx, wo_id):
    """Claimed work is not yours to take (AGENTS.md §Teamwork).

    Reads are never blocked — only appends. A stale claim expires and is
    never overridden, so there is no force flag here and there should not be
    one: the answer to a live claim is to wait or to ask.
    """
    coord.require_not_claimed(ctx.store, wo_id, ctx.agent, canonical.now())


def require_open(projection, wo_id):
    if projection.state.get("status") == "terminal":
        raise Refusal(
            "the work order is open",
            actual="terminal",
            needed="a work order that has not reached a terminal outcome",
            wo=wo_id,
        )
    if projection.state.get("stage") is None:
        raise Refusal(
            "the work order has entered a stage",
            needed="wf open records the first stage",
            wo=wo_id,
        )


def require_sources(ctx, verb):
    """Content the caller authored must name where it came from.

    AGENTS.md: every commit names its content's origin, and "I wrote it" is a
    source that must be claimed explicitly. ``Source: generated: wf`` covers
    the serialization only, so a verb that embeds an objective or a note must
    say where that text came from.

    Open, outcome, and marker — a finding's id and note are authored text
    like an objective or a verdict. ``advance`` records a transition and no content, and
    receipts source themselves from the command whose output they carry —
    demanding a flag where there is nothing to attribute would be ceremony,
    and ceremony is what gets skipped.
    """
    if not [s for s in ctx.sources if s and s.strip()]:
        # A blank --source is not a provenance claim; accepting it would let
        # the requirement be satisfied by typing nothing.
        raise Refusal(
            f"{verb} names the source of the content it records",
            needed=("--source original | '<repo>@<sha>' | '<url>' |"
                    " 'owner <date>' | 'generated: <tool>' (repeatable)"),
        )
    return ctx.sources


def require_wrapped(args, verb):
    if not args.wrapped:
        raise Refusal(
            f"{verb} is given a command to run",
            needed=f"wf {verb} <wo> -- <command…>",
        )
    return list(args.wrapped)


def require_no_open_markers(spec, state, stage, wo_id, moving_to):
    """PLAN §3.5: a fix stage cannot be left with findings still open.

    Mechanical, and spec data rather than an engine rule — the engine does
    not know which stage is "fix". Re-entering an *earlier* stage is not
    blocked: that is the correction path, and holding it shut would leave a
    work order with nowhere to go.
    """
    if not spec.blocked_by_open_markers(stage):
        return
    open_markers = list(state.get("open_markers", []))
    if open_markers:
        raise Refusal(
            "the stage has no open markers left",
            actual=f"{len(open_markers)} open: {', '.join(open_markers)}",
            needed=f"wf marker {wo_id} close <id> for each, before leaving {stage}"
                   f" for {moving_to}",
            wo=wo_id,
        )


def require_stage_evidence(spec, stage, evidence, wo_id):
    if evidence not in spec.leave_requires(stage):
        raise Refusal(
            f"the current stage requires {evidence}",
            actual=f"stage {stage} requires {', '.join(spec.leave_requires(stage)) or 'nothing'}",
            needed=f"a stage whose gate kind asks for {evidence}",
            wo=wo_id,
        )


def tree_state(ctx, allow_dirty, wo_id):
    """HEAD and whether the tree differs from it, enforcing D3."""
    repo = ctx.repo
    head = gitio.head_sha(repo)
    dirty = gitio.dirty_paths(repo, ctx.root)
    if dirty and not allow_dirty:
        shown = ", ".join(dirty[:3]) + ("…" if len(dirty) > 3 else "")
        raise Refusal(
            "the working tree is clean",
            actual=f"{len(dirty)} modified path(s): {shown}",
            needed="commit the tree, or --allow-dirty to record tree_dirty (D3)",
            wo=wo_id,
        )
    return head, bool(dirty)


def store_output(ctx, text, class_):
    data = (text or "").encode("utf-8")
    digest = ctx.cas.put(data)
    ctx.store.upsert_artifact(
        digest, len(data), "text/plain; charset=utf-8", class_, canonical.now()
    )
    return digest


def store_manifest(ctx, manifest):
    data = canonical.dumpb(manifest)
    digest = ctx.cas.put(data)
    ctx.store.upsert_artifact(
        digest, len(data), "application/json", "test-manifest", canonical.now()
    )
    return digest


def check_name_for(spec, argv):
    """The registered check this argv *is*, or None when it is ad hoc."""
    for check in spec.checks:
        if list(check["argv"]) == list(argv):
            return check["name"]
    return None


def receipt_event(ctx, etype, stage, spec, argv, code, out, err, ms,
                  manifest, digest, head, dirty, toolchain, extra=None):
    # A receipt's content is the output of the command it ran, so its origin
    # is derivable rather than declarable. An explicit --source still wins.
    sources = ctx.sources or [f"generated: {' '.join(argv)}"]
    body = {
        "type": etype,
        "stage": stage,
        "check": check_name_for(spec, argv),
        "argv": list(argv),
        "cwd": ".",
        "exit_code": code,
        "duration_ms": ms,
        "stdout_sha256": store_output(ctx, out, "receipt-stdout"),
        "stderr_sha256": store_output(ctx, err, "receipt-stderr"),
        "stdout_tail": receipts.tail(out),
        "stderr_tail": receipts.tail(err),
        "test_manifest_sha256": digest,
        "manifest_files": len(manifest),
        "test_scope": spec.test_scope,
        "harness_scope": spec.harness_scope,
        "toolchain": toolchain,
        "head_sha": head,
        "tree_dirty": dirty,
        "agent": ctx.agent,
        "sources": sources,
    }
    body.update(extra or {})
    return body


def cmd_red(ctx, args) -> int:
    ctx.require_agent()
    row, spec, projection = prepared(ctx, args.wo)
    with Attempt(ctx, args.wo, "red", sys.argv[1:]) as attempt:
        require_unclaimed(ctx, args.wo)
        require_open(projection, args.wo)
        stage = projection.state["stage"]
        require_stage_evidence(spec, stage, chainmod.RECEIPT_RED, args.wo)
        argv = require_wrapped(args, "red")
        head, dirty = tree_state(ctx, args.allow_dirty, args.wo)
        manifest, digest = receipts.compute_manifest(
            ctx.repo, spec, commit=head, worktree=dirty
        )
        toolchain = receipts.toolchain_string(spec, ctx.repo)
        code, out, err, ms = receipts.run(argv, ctx.repo)
        attempt.stdout, attempt.stderr = out, err
        if code == 0:
            # A zero exit is a refusal: there is nothing red to prove.
            raise Refusal(
                "the test command fails",
                expected="a nonzero exit",
                actual="0",
                needed="a command that demonstrates the gap the work order closes",
                wo=args.wo,
            )
        store_manifest(ctx, manifest)
        ctx.chain.append(args.wo, receipt_event(
            ctx, chainmod.RECEIPT_RED, stage, spec, argv, code, out, err, ms,
            manifest, digest, head, dirty, toolchain,
        ))
        attempt.events = 1
    maybe_commit(ctx, args.wo, "red", f"{chainmod.RECEIPT_RED} {' '.join(argv)}")
    projection = ctx.chain.project(args.wo)
    ctx.emit(
        {**summarise(ctx, row, projection), "exit_code": code,
         "test_manifest_sha256": digest, "manifest_files": len(manifest),
         "tree_dirty": dirty},
        f"{args.wo} receipt.red recorded — exit {code}, "
        f"{len(manifest)} file(s) in scope, manifest {digest[:12]}",
    )
    return EXIT_OK


def seal_for(ctx, spec, projection, target, wo_id):
    """The frozen set sealed on entering ``target``, or None.

    Freezing is an effect, not a verb: the *latest* red receipt's manifest is
    sealed as the work order advances, so prove-red and freeze cannot drift
    apart — they are one measurement (PLAN §3.3).
    """
    if not spec.seals_frozen_set(target):
        return None
    latest = None
    for event in projection.events:
        if event.get("type") == chainmod.RECEIPT_RED:
            latest = event
    if latest is None:
        raise Refusal(
            "a red receipt exists to seal the frozen set",
            actual=f"no {chainmod.RECEIPT_RED} in the chain",
            needed=f"wf red before entering {target}",
            wo=wo_id,
        )
    return {
        "manifest_sha256": latest["test_manifest_sha256"],
        "red_seq": latest["seq"],
        "red_hash": latest["hash"],
        "argv": list(latest["argv"]),
        "head_sha": latest["head_sha"],
        "tree_dirty": latest["tree_dirty"],
    }


def cmd_advance(ctx, args) -> int:
    agent = ctx.require_agent()
    row, spec, projection = prepared(ctx, args.wo)
    with Attempt(ctx, args.wo, "advance", sys.argv[1:]) as attempt:
        require_unclaimed(ctx, args.wo)
        require_open(projection, args.wo)
        state = projection.state
        stage = state["stage"]
        names = spec.stage_names

        if args.to:
            target = spec.stage(args.to)["name"]
            if not args.reason:
                raise Refusal(
                    "re-entering a stage states a reason",
                    needed="--reason '…' — the voided path stays in the chain",
                    wo=args.wo,
                )
            require_no_open_markers(spec, state, stage, args.wo, target)
            if names.index(target) > names.index(stage):
                raise Refusal(
                    "advance --to re-enters an earlier stage",
                    actual=f"{stage} -> {target}",
                    needed="plain wf advance to move forward, which checks evidence",
                    wo=args.wo,
                )
        else:
            if spec.outcomes(stage):
                raise Refusal(
                    "the current stage is left by advancing",
                    actual=f"stage {stage} is left by recording an outcome",
                    needed=f"wf outcome {args.wo} <{'|'.join(sorted(spec.outcomes(stage)))}>",
                    wo=args.wo,
                )
            missing = missing_evidence(spec, state)
            if missing:
                raise Refusal(
                    "the stage has the evidence its gate kind requires",
                    expected=", ".join(spec.leave_requires(stage)),
                    actual=f"missing {', '.join(missing)}",
                    needed=f"record {missing[0]} before leaving {stage}",
                    wo=args.wo,
                )
            require_no_open_markers(spec, state, stage, args.wo,
                                    spec.next_stage(stage))
            target = spec.next_stage(stage)
            if target is None:
                raise Refusal(
                    "there is a stage after the current one",
                    actual=f"{stage} is the last stage of {spec.kind}@{spec.version}",
                    needed="record a terminal outcome instead",
                    wo=args.wo,
                )

        frozen = seal_for(ctx, spec, projection, target, args.wo)
        event = {
            "type": chainmod.STAGE_ENTERED, "stage": target, "frozen": frozen,
            "from_stage": stage, "agent": agent, "sources": ctx.sources,
        }
        if args.reason:
            event["reason"] = args.reason
        ctx.chain.append(args.wo, event)
        attempt.events = 1

    maybe_commit(ctx, args.wo, "advance", f"{chainmod.STAGE_ENTERED} {target}")
    projection = ctx.chain.project(args.wo)
    sealed = (frozen or {}).get("manifest_sha256")
    ctx.emit(
        {**summarise(ctx, row, projection), "from_stage": stage, "stage": target,
         "sealed_manifest_sha256": sealed},
        f"{args.wo} entered {target}"
        + (f" — frozen set {sealed[:12]} sealed from seq {frozen['red_seq']}"
           if sealed else ""),
    )
    return EXIT_OK


def cmd_green(ctx, args) -> int:
    ctx.require_agent()
    row, spec, projection = prepared(ctx, args.wo)
    with Attempt(ctx, args.wo, "green", sys.argv[1:]) as attempt:
        require_unclaimed(ctx, args.wo)
        require_open(projection, args.wo)
        state = projection.state
        stage = state["stage"]
        require_stage_evidence(spec, stage, chainmod.RECEIPT_GREEN, args.wo)
        argv = require_wrapped(args, "green")

        frozen = state.get("frozen")
        if not frozen:
            raise Refusal(
                "a frozen set is sealed for this stage",
                actual=f"stage {stage} entered without a seal",
                needed="re-prove red, then advance — the seal is an effect of advancing",
                wo=args.wo,
            )
        if list(frozen.get("argv") or []) != argv:
            # Green runs the same argv the bound red recorded; a different
            # command is a refusal, not a comparison.
            raise Refusal(
                "green runs the same command the bound red recorded",
                expected=" ".join(frozen.get("argv") or []),
                actual=" ".join(argv),
                needed="the same argv, so red and green measure the same thing",
                wo=args.wo,
            )

        head, dirty = tree_state(ctx, args.allow_dirty, args.wo)
        manifest, digest = receipts.compute_manifest(
            ctx.repo, spec, commit=head, worktree=dirty
        )
        if digest != frozen["manifest_sha256"]:
            raise Refusal(
                "the test manifest equals the frozen set",
                expected=frozen["manifest_sha256"],
                actual=digest,
                needed="restore the frozen tests, or advance --to red to reseal",
                wo=args.wo,
            )
        toolchain = receipts.toolchain_string(spec, ctx.repo)
        code, out, err, ms = receipts.run(argv, ctx.repo)
        attempt.stdout, attempt.stderr = out, err
        if code != 0:
            raise Refusal(
                "the test command succeeds",
                expected="exit 0",
                actual=str(code),
                needed="a passing run against the frozen set",
                wo=args.wo,
            )
        store_manifest(ctx, manifest)
        ctx.chain.append(args.wo, receipt_event(
            ctx, chainmod.RECEIPT_GREEN, stage, spec, argv, code, out, err, ms,
            manifest, digest, head, dirty, toolchain,
            extra={
                "red_seq": frozen["red_seq"],
                "red_hash": frozen["red_hash"],
                "frozen_manifest_sha256": frozen["manifest_sha256"],
            },
        ))
        attempt.events = 1

    maybe_commit(ctx, args.wo, "green", f"{chainmod.RECEIPT_GREEN} {' '.join(argv)}")
    projection = ctx.chain.project(args.wo)
    ctx.emit(
        {**summarise(ctx, row, projection), "exit_code": code,
         "test_manifest_sha256": digest, "red_seq": frozen["red_seq"]},
        f"{args.wo} receipt.green recorded — exit 0 against frozen set "
        f"{digest[:12]} bound to red seq {frozen['red_seq']}",
    )
    return EXIT_OK


def cmd_outcome(ctx, args) -> int:
    """Record a gate outcome and who stated it (PLAN §3.5).

    The engine never interprets an outcome value. The spec declares each
    value's effect as data and the engine applies it mechanically. Two
    consequences are load-bearing:

    * a recorded denial **exits 0** — recording the denial succeeded, and
      denial is the process working, not an error;
    * an outcome on a stage the spec marks ``actor: owner`` is recorded like
      any other statement, but its effect is **not applied**. An agent typing
      ``ratified`` must never become workflow state. The attestation that
      applies it is the owner's merge into protected ``main`` (D10).

    ``--by`` records the stating actor. That is evidence a statement was
    made, not proof of who made it — a single-machine trust boundary stated
    rather than hidden.
    """
    agent = ctx.require_agent()
    row, spec, projection = prepared(ctx, args.wo)
    applied = None
    with Attempt(ctx, args.wo, "outcome", sys.argv[1:]) as attempt:
        require_unclaimed(ctx, args.wo)
        require_sources(ctx, "outcome")   # a stated verdict, and often a note
        require_open(projection, args.wo)
        state = projection.state
        stage = state["stage"]
        allowed = spec.outcomes(stage)
        if not allowed:
            raise Refusal(
                "the current stage declares outcomes",
                actual=f"stage {stage} declares none",
                needed=f"wf advance {args.wo} — this stage is left by advancing",
                wo=args.wo,
            )
        if args.value not in allowed:
            raise Refusal(
                "the outcome value is declared by this stage",
                expected=", ".join(sorted(allowed)),
                actual=args.value,
                needed=f"one of the values {spec.kind}@{spec.version} declares for {stage}",
                wo=args.wo,
            )

        declared = allowed[args.value]
        reserved = spec.actor(stage) is not None
        applied = None if reserved else declared

        # Resolve the movement *before* anything is appended. Validating it
        # afterwards would leave the outcome event permanently in the chain
        # behind a refusal exit — a partial transition, which is precisely
        # what "a refusal records nothing" forbids.
        target = None
        if applied == gatekinds.EFFECT_ADVANCE:
            target = spec.next_stage(stage)
            if target is None:
                raise Refusal(
                    "there is a stage to advance into",
                    actual=f"{stage} is the last stage of {spec.kind}@{spec.version}",
                    needed="a spec whose advancing outcome has somewhere to go",
                    wo=args.wo,
                )
        elif applied not in (None, gatekinds.EFFECT_STAY, gatekinds.EFFECT_TERMINAL):
            target = spec.stage(applied)["name"]

        # Evidence gates *forward* movement, however it is spelled. Checking
        # only the literal "advance" let a spec name a later stage directly
        # and step over every leave_requires receipt on the current one.
        # A denial, or a return to an earlier stage, stays recordable
        # whatever is missing: refusing to record a denial would make the
        # record less honest, not more careful.
        names = spec.stage_names
        moving_forward = target is not None and names.index(target) > names.index(stage)
        if moving_forward:
            require_no_open_markers(spec, state, stage, args.wo, target)
            missing = missing_evidence(spec, state)
            if missing:
                raise Refusal(
                    "the stage has the evidence its gate kind requires",
                    expected=", ".join(spec.leave_requires(stage)),
                    actual=f"missing {', '.join(missing)}",
                    needed=(f"record {missing[0]} before an outcome moves {stage}"
                            f" forward to {target}"),
                    wo=args.wo,
                )

        # The seal too: resolving it after the append would strand the same
        # partial transition. It reads the chain as it stands, and the
        # outcome event adds no receipt, so the answer does not change.
        frozen = seal_for(ctx, spec, projection, target, args.wo) if target else None
        event = {
            "type": chainmod.OUTCOME,
            "stage": stage,
            "value": args.value,
            "by": args.by,
            "declared_effect": declared,
            "effect": applied,
            "actor_reserved": reserved,
            "agent": agent,
            "sources": ctx.sources,
        }
        if args.note:
            event["note"] = args.note
        ctx.chain.append(args.wo, event)
        attempt.events = 1

        # Applying the effect is a second, separate event: the statement and
        # the movement it caused are both in the chain, and neither is
        # inferred from the other.
        if target is not None:
            ctx.chain.append(args.wo, {
                "type": chainmod.STAGE_ENTERED, "stage": target, "frozen": frozen,
                "from_stage": stage, "via_outcome": args.value,
                "agent": agent, "sources": ctx.sources,
            })
            attempt.events = 2

    maybe_commit(ctx, args.wo, "outcome", f"{chainmod.OUTCOME} {args.value}")
    projection = ctx.chain.project(args.wo)
    body = {
        **summarise(ctx, row, projection),
        "value": args.value,
        "by": args.by,
        "declared_effect": declared,
        "applied_effect": applied,
        "actor_reserved": reserved,
    }
    if reserved:
        human = (
            f"{args.wo} outcome {args.value} recorded by {args.by} — effect "
            f"'{declared}' withheld: stage {stage} is reserved to "
            f"{spec.actor(stage)} (D10, the protected-main merge applies it)"
        )
    else:
        human = (
            f"{args.wo} outcome {args.value} recorded by {args.by} — "
            f"effect '{declared}' applied, now at stage {projection.state.get('stage')}"
            f" ({projection.state.get('status')})"
        )
    ctx.emit(body, human)
    return EXIT_OK


# Digest-bearing event fields, and what the object behind each one is. The
# artifacts table is a queryable mirror rebuilt from the chain plus the object
# files, which is why the export does not carry it separately.
DIGEST_FIELDS = {
    "spec_sha256": ("application/json", "gate-kind-spec"),
    "stdout_sha256": ("text/plain; charset=utf-8", "receipt-stdout"),
    "stderr_sha256": ("text/plain; charset=utf-8", "receipt-stderr"),
    "test_manifest_sha256": ("application/json", "test-manifest"),
}


def referenced_digests(event: dict):
    for field, (media_type, class_) in DIGEST_FIELDS.items():
        digest = event.get(field)
        if isinstance(digest, str) and len(digest) == 64:
            yield digest, media_type, class_


def do_commit(ctx, wo_id=None, summary="flush export"):
    """Flush the export, commit it, and bind the commit into the chains.

    An event cannot contain the hash of the commit that will contain it, so
    the bind is one commit behind by construction (PLAN §3.6): commit.landed
    is appended *after* the commit it names and lands in the next one. In
    steady state exactly one bind is pending, and the tip is witnessed by CI
    until the next append lands it in-chain.
    """
    gitio.export(ctx)
    staged = gitio.stage_export(ctx)
    if not staged:
        return None, []

    rel_root = Path(ctx.root).resolve().relative_to(Path(ctx.repo).resolve()).as_posix()
    prefix = f"{rel_root}/chains/"
    touched = [
        Path(p).name[: -len(".jsonl")]
        for p in staged
        if p.startswith(prefix) and p.endswith(".jsonl")
    ]
    if wo_id and wo_id not in touched:
        touched.append(wo_id)
    touched = sorted(set(touched))

    # A bind is stamped with ctx.agent, so binding a chain somebody else holds
    # writes their work under this agent's name. Skip those rather than
    # refusing the whole commit: the export legitimately carries other work
    # orders' lines, and refusing would let one agent's claim block every
    # other agent's auto-commit. A work order named explicitly is different —
    # that is a direct action on their work, and cmd_commit refuses it.
    held_elsewhere = [
        wo for wo in touched
        if coord.held_by_other(ctx.store, wo, ctx.agent, canonical.now()) is not None
    ]
    touched = [wo for wo in touched if wo not in held_elsewhere]
    if held_elsewhere:
        # Out of the git commit too, not just the bind list: committing the
        # file puts their work under this agent's trailers, and leaves the
        # tree clean so the holder's own later flush has nothing to bind.
        held_paths = {
            f"{rel_root}/{kind}/{wo}.jsonl"
            for wo in held_elsewhere for kind in ("chains", "attempts")
        }
        staged = [p for p in staged if p not in held_paths]
        if not staged:
            # An empty pathspec would commit the whole index. Nothing of
            # ours to commit is exactly the "nothing to commit" answer.
            return None, sorted(held_elsewhere)
    if not touched:
        # An export change with no chain in it (meta.json, or an object
        # written by a verb that then refused) still deserves a commit, but
        # there is no chain to bind it into.
        headline = wo_id or "-"
        message = gitio.commit_message(
            headline, "-", 0, canonical.ZERO_DIGEST, summary, ctx.agent, ctx.sources
        )
        _git_commit(ctx, message, staged)
        return gitio.head_sha(ctx.repo), sorted(held_elsewhere)

    headline = wo_id if wo_id in touched else touched[0]
    projection = ctx.chain.project(headline)
    message = gitio.commit_message(
        headline, projection.state.get("stage") or "-", projection.last_seq,
        projection.last_hash, summary, ctx.agent, ctx.sources,
    )
    _git_commit(ctx, message, staged)
    sha = gitio.head_sha(ctx.repo)

    for wo in touched:
        current = ctx.chain.project(wo)
        ctx.chain.append(wo, {
            "type": chainmod.COMMIT_LANDED,
            "sha": sha,
            "chain_seq": current.last_seq,
            "chain_hash": current.last_hash,
            "agent": ctx.agent,
        })
    gitio.export(ctx)  # the pending bind reaches disk; the next commit sweeps it
    return sha, sorted(held_elsewhere)


def commit_identity(ctx):
    """The author/committer a wf auto-commit must use, if the repo declares one.

    Left to ambient git config, an auto-commit is authored by whichever agent
    happens to be running, which is exactly the attribution AGENTS.md forbids.
    The identity is tracked data in meta.json rather than hardcoded, so the
    tool stays general and the policy stays reviewable.
    """
    if not ctx.meta_path.exists():
        return None
    try:
        meta = canonical.loads(ctx.meta_path.read_bytes())
    except ValueError:
        return None
    identity = (meta or {}).get("commit_identity")
    if not isinstance(identity, dict):
        return None
    name, email = identity.get("name"), identity.get("email")
    if not (isinstance(name, str) and name and isinstance(email, str) and email):
        raise Refusal(
            "meta.json's commit_identity names both a name and an email",
            actual=repr(identity),
            needed='{"name": "…", "email": "…"}',
        )
    return name, email


def _git_commit(ctx, message: str, paths) -> None:
    """Commit only wf's own export paths, as the identity the repo declares.

    The pathspec is load-bearing: `git commit` without one commits the whole
    index, so any product file an agent had already staged would ride into a
    generated workflow commit under wf's Source and co-author trailers.
    Restricting it leaves unrelated staged work staged, which is correct.
    """
    import tempfile

    identity = commit_identity(ctx)
    prefix = []
    if identity:
        prefix = ["-c", f"user.name={identity[0]}", "-c", f"user.email={identity[1]}"]
    # delete=False and closed by hand: the path outlives the
    # object because git reads the file after we close it.
    handle = tempfile.NamedTemporaryFile(  # noqa: SIM115
        "w", suffix=".msg", delete=False, encoding="utf-8"
    )
    try:
        handle.write(message)
        handle.close()
        gitio.git(ctx.repo, *prefix, "commit", "-q", "-F", handle.name, "--", *paths)
    finally:
        os.unlink(handle.name)


def cmd_commit(ctx, args) -> int:
    # The bind is stamped with ctx.agent and the git commit carries its
    # trailer, so commit is an appending verb like any other: no identity,
    # no commit. Every other appending verb already refused.
    ctx.require_agent()
    ctx.open_store()
    if args.wo:
        ctx.work_order(args.wo)
        require_unclaimed(ctx, args.wo)
    sha, skipped = do_commit(ctx, wo_id=args.wo,
                             summary=args.message or "flush export")
    body = {"committed": sha}
    if skipped:
        # A silent skip is a gap nobody notices; the holder learns their
        # chain is still theirs to flush by reading this.
        body["skipped_held"] = skipped
    if sha is None:
        body["note"] = "nothing to commit"
        ctx.emit(body, "nothing to commit"
                 + (f" (held elsewhere: {', '.join(skipped)})" if skipped else ""))
        return EXIT_OK
    ctx.emit(body, f"committed {sha[:12]}"
             + (f" — skipped held: {', '.join(skipped)}" if skipped else ""))
    return EXIT_OK


def cmd_export(ctx, args) -> int:
    ctx.open_store()
    written = gitio.export(ctx)
    ctx.emit({"written": written}, "\n".join(written) or "export already current")
    return EXIT_OK


# --------------------------------------------------------------------------
# rebuild — reconstruct the database from the tracked export


def import_chain(ctx, wo_id: str, path: Path) -> list:
    """Import one exported chain, verifying every line as it lands.

    Rebuild fidelity is a property of the format: the payload column stores
    exactly the export line, so a rebuilt database re-exports byte-identical
    files.
    """
    raw = path.read_bytes()
    # A canonical JSON document never contains a raw newline — they are
    # escaped — so line splitting is exact rather than approximate.
    lines = [line for line in raw.split(b"\n") if line.strip()]
    payloads, prev, prev_time = [], canonical.ZERO_DIGEST, None
    for index, line in enumerate(lines, 1):
        if not canonical.is_canonical(line):
            raise Integrity(
                "exported event is not in canonical form", wo=wo_id, seq=index
            )
        event = canonical.loads(line)
        if not isinstance(event, dict):
            raise Integrity("exported event is not a JSON object", wo=wo_id, seq=index)
        # Shape before content: comparing a missing field against a stored one
        # raises a TypeError, and a malformed export line must be an integrity
        # failure with a message, never a traceback.
        for field, kind in (("seq", int), ("prev", str), ("time", str),
                            ("hash", str), ("state_sha256", str), ("type", str)):
            value = event.get(field)
            if not isinstance(value, kind) or isinstance(value, bool):
                raise Integrity(
                    "exported event is missing a core field, or it is the wrong type",
                    wo=wo_id, seq=index,
                    detail=f"{field}: {value!r}",
                )
        try:
            canonical.parse_time(event["time"])
        except ValueError as exc:
            raise Integrity(
                "exported event time is unreadable", wo=wo_id, seq=index,
                detail=str(exc),
            ) from None
        if event.get("seq") != index:
            raise Integrity(
                "exported chain is not contiguous", wo=wo_id, seq=index,
                detail=f"line {index} carries seq {event.get('seq')!r}",
            )
        if chainmod.event_hash(event) != event.get("hash"):
            raise Integrity(
                "exported event does not hash to its recorded hash",
                wo=wo_id, seq=index,
            )
        if event.get("prev") != prev:
            raise Integrity(
                "exported event does not link to the preceding one",
                wo=wo_id, seq=index,
            )
        if prev_time is not None and event.get("time") < prev_time:
            raise Integrity("exported event time decreases", wo=wo_id, seq=index)
        prev, prev_time = event["hash"], event["time"]
        payloads.append((line.decode("utf-8"), event))

    if not payloads:
        return []
    first = payloads[0][1]
    if first.get("type") != chainmod.WO_OPENED:
        raise Integrity(
            "a chain begins with wo.opened", wo=wo_id, seq=1,
            detail=f"first event is {first.get('type')!r}",
        )
    ctx.store.insert_work_order(
        wo_id, first.get("objective") or "", first["kind"], first["kind_version"],
        first["spec_sha256"], first["time"],
    )
    for index, (text, event) in enumerate(payloads, 1):
        ctx.store.insert_event(
            wo_id, index, event["hash"], event["prev"], event["time"], text,
            event["state_sha256"],
        )
    events = [event for _, event in payloads]
    state = chainmod.replay(wo_id, events)
    digest = canonical.digest(state)
    if digest != events[-1]["state_sha256"]:
        raise Integrity(
            "replayed state does not match the state hashed into the export",
            wo=wo_id, seq=len(events),
        )
    ctx.store.upsert_state(
        wo_id, canonical.dumps(state), digest, len(events), events[-1]["hash"]
    )
    return events


def import_attempts(ctx, wo_id: str, path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for line in path.read_bytes().split(b"\n"):
        if not line.strip():
            continue
        if not canonical.is_canonical(line):
            raise Integrity("exported attempt is not in canonical form", wo=wo_id)
        row = canonical.loads(line)
        if row.get("wo_id") != wo_id:
            raise Integrity(
                "exported attempt names a different work order", wo=wo_id,
                detail=str(row.get("wo_id")),
            )
        ctx.store.insert_attempt(row)
        count += 1
    return count


def rebuild_artifacts(ctx, events_by_wo: dict) -> int:
    """Rebuild the artifacts mirror from the chain and the object files."""
    seen = {}
    for events in events_by_wo.values():
        for event in events:
            for digest, media_type, class_ in referenced_digests(event):
                seen.setdefault(digest, (media_type, class_))
    for digest, (media_type, class_) in sorted(seen.items()):
        data = ctx.cas.get(digest)  # verifies the object hashes to its name
        ctx.store.upsert_artifact(
            digest, len(data), media_type, class_, canonical.now()
        )
    return len(seen)


def rebuild(ctx) -> dict:
    # Refuse before touching anything: the old order unlinked the cache
    # first, so a mere format refusal destroyed it.
    if ctx.meta_path.exists():
        meta = canonical.loads(ctx.meta_path.read_bytes())
        if meta.get("format_version") != EXPORT_FORMAT_VERSION:
            raise Refusal(
                "the export format version is one this build understands",
                expected=EXPORT_FORMAT_VERSION,
                actual=meta.get("format_version"),
                needed="a wf build matching the export, or a migration",
            )

    # Atomic: build into a temp beside wf.db and rename only on success. A
    # rebuild that failed partway used to leave work_orders populated and the
    # attempts it refused on absent — a partial that passed for finished, and
    # the MCP launcher's cache check then trusted it permanently. Failure now
    # leaves the previous state: a coherent old cache, or nothing.
    final = ctx.db_path
    tmp = final.with_name(final.name + ".rebuild")
    for leftover in [tmp] + [Path(str(tmp) + s) for s in ("-journal", "-wal", "-shm")]:
        if leftover.exists():
            leftover.unlink()

    if ctx.store is not None:
        ctx.store.close()
    store = ctx.store = Store(tmp)
    ctx.chain = chainmod.Chain(store)
    try:
        applied = store.migrate(ctx.migrations, canonical.now())
        gatekinds.sync(store, ctx.specs, canonical.now())

        events_by_wo, attempts = {}, 0
        for path in sorted(ctx.chains_dir.glob("*.jsonl")) if ctx.chains_dir.exists() else []:
            wo_id = path.name[: -len(".jsonl")]
            events_by_wo[wo_id] = import_chain(ctx, wo_id, path)
            attempts += import_attempts(ctx, wo_id, ctx.attempts_dir / f"{wo_id}.jsonl")
        objects = rebuild_artifacts(ctx, events_by_wo)
    except BaseException:
        store.close()
        ctx.store = ctx.chain = None
        for leftover in [tmp] + [Path(str(tmp) + s) for s in ("-journal", "-wal", "-shm")]:
            if leftover.exists():
                leftover.unlink()
        raise
    store.close()
    ctx.store = ctx.chain = None
    # The old cache's sidecars belong to the file being replaced; left in
    # place, SQLite would replay them into the new one.
    for suffix in ("-journal", "-wal", "-shm"):
        stale = Path(str(final) + suffix)
        if stale.exists():
            stale.unlink()
    os.replace(tmp, final)
    return {
        "migrations_applied": applied,
        "work_orders": sorted(events_by_wo),
        "events": sum(len(v) for v in events_by_wo.values()),
        "attempts": attempts,
        "objects": objects,
    }


def cmd_verify(ctx, args) -> int:
    report = verify.run(ctx, deep=args.deep)
    lines = [
        f"verify{' --deep' if args.deep else ''} at {str(report['head'])[:12]}:"
        f" {len(report['work_orders'])} work order(s),"
        f" {report['events']} event(s), {report['objects']} object(s)"
        + (f", {report['chain_files_in_history']} chain file(s) in history"
           if args.deep else "")
        + " — ok"
    ]
    for entry in report["work_orders"]:
        detail = f"  {entry['wo']}  seq {entry['events']}  {entry['head'][:12]}"
        if args.deep:
            detail += (
                f"  receipts {entry['receipts']['checked']}"
                f" (+{entry['receipts']['skipped_dirty']} dirty)"
                f"  binds {entry['cross_binds']['bound']}"
                f"  versions {entry['append_only']['versions']}"
                f"  unbound {entry['unbound_tip']['pending_events']}"
            )
        lines.append(detail)
    ctx.emit(report, "\n".join(lines))
    return EXIT_OK


def cmd_check(ctx, args) -> int:
    """Run a registered check and record the receipt (PLAN §3.4).

    Security is not special-cased anywhere in here: a check is a name, a
    class and an argv template in the gate-kind spec, and a security stage is
    simply one whose spec requires a receipt of that class. The engine never
    learns the word.

    A check that *fails* is recorded and exits 0 — recording succeeded, and
    §4 reserves exit 0 for "ok, including a recorded denial". What a failure
    changes is `satisfies`, so the stage stays unsatisfied and `wf next`
    still asks for it. Records are evidence, never authority.

    ``--verify-only`` is the CI mode: run the registered command, record
    nothing, and let its exit code through so the job is red when the check
    is. It needs no work order, because CI checks a tree, not a chain.
    """
    positional = list(args.target)
    if args.verify_only and len(positional) == 1:
        name, wo_id = positional[0], None
    elif len(positional) == 2:
        wo_id, name = positional
    elif len(positional) == 1:
        raise Refusal(
            "check names a work order",
            actual=f"only {positional[0]!r} was given",
            needed=f"wf check <wo> {positional[0]}, or --verify-only for CI mode",
        )
    else:
        raise Usage("check takes <wo> <check-name>, or <check-name> with --verify-only")

    ctx.records = not args.verify_only
    ctx.open_store()
    if wo_id is None:
        # PLAN §7's matrix job runs `wf check --verify-only NAME` with no
        # --kind, so the kind is inferred when the name is unambiguous across
        # the registry. Ambiguity refuses and names the candidates rather than
        # silently picking one.
        if args.kind:
            spec = gatekinds.latest(ctx.specs, args.kind)
        else:
            owners = {}
            for (kind, _version), candidate in sorted(ctx.specs.items()):
                for entry in candidate.checks:
                    if entry["name"] == name:
                        owners.setdefault(kind, candidate)
            if not owners:
                known = sorted({
                    e["name"] for s in ctx.specs.values() for e in s.checks
                })
                raise Refusal(
                    "the check is registered by some gate kind",
                    actual=repr(name),
                    expected=", ".join(known) or "(none)",
                    needed="a check declared in gate-kinds/",
                )
            argvs = {canonical.dumps(e["argv"]) for s in owners.values()
                     for e in s.checks if e["name"] == name}
            if len(owners) > 1 and len(argvs) > 1:
                raise Refusal(
                    "the check name identifies one command",
                    actual=f"{name} is declared differently by "
                           f"{', '.join(sorted(owners))}",
                    needed="--kind K to say which one",
                )
            spec = owners[min(owners)]
        row, projection, stage = None, None, None
    else:
        row, spec, projection = prepared(ctx, wo_id)
        stage = projection.state.get("stage")

    entry = spec.check(name)
    registered = list(entry["argv"])
    argv = list(args.wrapped) if args.wrapped else registered
    # Running something else is not running the check. The override stays —
    # §4 documents it and it is useful for a diagnostic run — but it cannot
    # satisfy a gate, or `-- true` would clear a security stage without the
    # scanner ever executing. The substitution is recorded so review can see it.
    overridden = argv != registered

    if args.verify_only:
        # Records nothing, so there is no attempt row and no commit: CI must
        # not be able to originate state.
        code, out, err, ms = receipts.run(argv, ctx.repo)
        ctx.emit(
            {"check": name, "class": entry["class"], "argv": argv,
             "exit_code": code, "recorded": False, "overridden": overridden,
             "stdout_tail": receipts.tail(out), "stderr_tail": receipts.tail(err)},
            f"{name} ({entry['class']}) exited {code} — nothing recorded",
        )
        # The wrapped command's exit code is evidence, not wf's answer. Passing
        # it through would let a check that exits 3 read as "claimed by another
        # agent", or 2 as "evidence integrity" — the codes §4 reserves.
        return EXIT_OK if code == 0 else EXIT_REFUSED

    ctx.require_agent()
    with Attempt(ctx, wo_id, "check", sys.argv[1:]) as attempt:
        require_unclaimed(ctx, wo_id)
        require_open(projection, wo_id)
        head, dirty = tree_state(ctx, args.allow_dirty, wo_id)
        manifest, digest = receipts.compute_manifest(
            ctx.repo, spec, commit=head, worktree=dirty
        )
        toolchain = receipts.toolchain_string(spec, ctx.repo)
        code, out, err, ms = receipts.run(argv, ctx.repo)
        attempt.stdout, attempt.stderr = out, err
        store_manifest(ctx, manifest)
        ctx.chain.append(wo_id, receipt_event(
            ctx, chainmod.RECEIPT_CHECK, stage, spec, argv, code, out, err, ms,
            manifest, digest, head, dirty, toolchain,
            extra={"class": entry["class"], "satisfies": code == 0 and not overridden,
                   "overridden": overridden, "registered_argv": registered},
        ))
        attempt.events = 1

    maybe_commit(ctx, wo_id, "check", f"{chainmod.RECEIPT_CHECK} {name}")
    projection = ctx.chain.project(wo_id)
    satisfies = code == 0 and not overridden
    ctx.emit(
        {**summarise(ctx, row, projection), "check": name, "class": entry["class"],
         "exit_code": code, "satisfies": satisfies, "recorded": True,
         "overridden": overridden},
        f"{wo_id} receipt.check {name} ({entry['class']}) recorded — exit {code}"
        + ("" if satisfies else
           (" — the command was substituted, so it does not satisfy the stage"
            if overridden else
            " — FAILED, so it does not satisfy the stage")),
    )
    return EXIT_OK


def cmd_marker(ctx, args) -> int:
    """Open or close a marker — a finding or a blocker (PLAN §3.5).

    Nothing is rewritten: closing appends a `marker.close`, and the
    `marker.open` stays in the chain where a reviewer left it.
    """
    agent = ctx.require_agent()
    row, _spec, projection = prepared(ctx, args.wo)
    with Attempt(ctx, args.wo, "marker", sys.argv[1:]) as attempt:
        require_sources(ctx, "marker")   # the id and note are authored text
        require_unclaimed(ctx, args.wo)
        require_open(projection, args.wo)
        state = projection.state
        open_markers = list(state.get("open_markers", []))

        if args.action == "open":
            if args.id in open_markers:
                raise Refusal(
                    "the marker is not already open",
                    actual=f"{args.id} is already open",
                    needed="a marker id that is not currently open",
                    wo=args.wo,
                )
            etype = chainmod.MARKER_OPEN
        else:
            if args.id not in open_markers:
                raise Refusal(
                    "the marker is open",
                    actual=f"{args.id} is not open",
                    expected=", ".join(open_markers) or "(none open)",
                    needed="the id of a marker that is currently open",
                    wo=args.wo,
                )
            etype = chainmod.MARKER_CLOSE

        event = {
            "type": etype, "id": args.id, "stage": state.get("stage"),
            "agent": agent, "sources": ctx.sources,
        }
        if args.note:
            event["note"] = args.note
        ctx.chain.append(args.wo, event)
        attempt.events = 1

    maybe_commit(ctx, args.wo, "marker", f"{etype} {args.id}")
    projection = ctx.chain.project(args.wo)
    ctx.emit(
        {**summarise(ctx, row, projection), "marker": args.id, "action": args.action},
        f"{args.wo} marker {args.id} {args.action}ed — open: "
        f"{', '.join(projection.state.get('open_markers', [])) or '(none)'}",
    )
    return EXIT_OK


def maybe_commit(ctx, wo_id, verb, summary):
    """Auto-commit after a chain-appending verb (D5: default on)."""
    if ctx.no_commit:
        return None
    sha, _skipped = do_commit(ctx, wo_id=wo_id, summary=summary)
    return sha


# --------------------------------------------------------------------------
# command line


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse exits 2; the map says usage is 64
        raise Usage(message)


def common_options(parser, *, suppress: bool) -> None:
    """The options every verb takes, before or after the verb name.

    They are declared twice — once on the top-level parser with real
    defaults, once on a parent shared by every subparser with
    ``SUPPRESS`` — because argparse copies a subparser's namespace over the
    top-level one. Without SUPPRESS an absent ``--agent`` after the verb
    would overwrite one given before it with None, which is the classic way
    this ends up half-working.
    """
    missing = argparse.SUPPRESS if suppress else None
    parser.add_argument("--root", default=missing,
                        help="state root (default: beside wf.py)")
    parser.add_argument("--json", action="store_true",
                        default=argparse.SUPPRESS if suppress else False,
                        help="machine-readable output")
    parser.add_argument("--agent", default=missing,
                        help="agent identity; falls back to $WF_AGENT")
    parser.add_argument("--source", action="append", default=missing,
                        help="provenance for the content this verb records (repeatable)")
    parser.add_argument("--no-commit", action="store_true",
                        default=argparse.SUPPRESS if suppress else False,
                        help="defer the auto-commit; flush later with wf commit")


def build_parser() -> Parser:
    parser = Parser(prog="wf", description="dev-lane workflow recorder")
    common_options(parser, suppress=False)
    common = argparse.ArgumentParser(add_help=False)
    common_options(common, suppress=True)
    subparsers = parser.add_subparsers(dest="verb", required=True)

    p = subparsers.add_parser("init", parents=[common], help="create or upgrade the database")
    p.add_argument("--rebuild", action="store_true",
                   help="reconstruct the database from the tracked export")
    p.set_defaults(func=cmd_init)

    p = subparsers.add_parser("open", parents=[common], help="open a work order")
    p.add_argument("wo", nargs="?", default=None, help="WO-NNN; allocated when omitted")
    p.add_argument("--kind", required=True)
    p.add_argument("--objective", required=True)
    p.set_defaults(func=cmd_open)

    p = subparsers.add_parser("claim", parents=[common],
                              help="claim a work order for a while")
    p.add_argument("wo")
    p.add_argument("--ttl", default=coord.DEFAULT_TTL,
                   help=f"duration, e.g. 30m (default {coord.DEFAULT_TTL});"
                        " re-claiming is the heartbeat")
    p.add_argument("--note", default=None)
    p.set_defaults(func=cmd_claim)

    p = subparsers.add_parser("release", parents=[common],
                              help="give up a claim you hold")
    p.add_argument("wo")
    p.set_defaults(func=cmd_release)

    p = subparsers.add_parser("next", parents=[common], help="what advances this work order")
    p.add_argument("wo", nargs="?", default=None)
    p.set_defaults(func=cmd_next)

    p = subparsers.add_parser("status", parents=[common], help="open work orders, or one in detail")
    p.add_argument("wo", nargs="?", default=None)
    p.add_argument("--checks", action="store_true",
                   help="the registered checks, and which of them CI runs")
    p.set_defaults(func=cmd_status)

    p = subparsers.add_parser("red", parents=[common], help="run a failing test command and record it")
    p.add_argument("wo")
    p.add_argument("--allow-dirty", action="store_true",
                   help="record against a dirty tree, accepting hash-only re-verification (D3)")
    p.set_defaults(func=cmd_red)

    p = subparsers.add_parser("green", parents=[common], help="run the frozen command and record success")
    p.add_argument("wo")
    p.add_argument("--allow-dirty", action="store_true")
    p.set_defaults(func=cmd_green)

    p = subparsers.add_parser("advance", parents=[common], help="enter the next stage")
    p.add_argument("wo")
    p.add_argument("--to", default=None, help="re-enter an earlier stage")
    p.add_argument("--reason", default=None, help="required with --to")
    p.set_defaults(func=cmd_advance)

    p = subparsers.add_parser("outcome", parents=[common], help="record a gate outcome and who stated it")
    p.add_argument("wo")
    p.add_argument("value")
    p.add_argument("--by", required=True, help="owner, or the agent stating it")
    p.add_argument("--note", default=None)
    p.set_defaults(func=cmd_outcome)

    p = subparsers.add_parser("commit", parents=[common], help="flush the export and commit it")
    p.add_argument("wo", nargs="?", default=None)
    p.add_argument("--message", default=None)
    p.set_defaults(func=cmd_commit)

    p = subparsers.add_parser("export", parents=[common], help="regenerate the tracked export")
    p.set_defaults(func=cmd_export)

    p = subparsers.add_parser("verify", parents=[common],
                              help="recompute every hash and link")
    p.add_argument("--deep", action="store_true",
                   help="also re-verify receipts, cross-binds and the prefix walk")
    p.set_defaults(func=cmd_verify)

    p = subparsers.add_parser("check", parents=[common],
                              help="run a registered check and record the receipt")
    p.add_argument("target", nargs="*", metavar="WO CHECK",
                   help="<wo> <check-name>, or <check-name> with --verify-only")
    p.add_argument("--verify-only", action="store_true",
                   help="run and exit meaningfully, recording nothing (CI mode)")
    p.add_argument("--kind", default=None,
                   help="gate kind to read the check from, for --verify-only")
    p.add_argument("--allow-dirty", action="store_true")
    p.set_defaults(func=cmd_check)

    p = subparsers.add_parser("marker", parents=[common],
                              help="open or close a finding or blocker")
    p.add_argument("wo")
    p.add_argument("action", choices=("open", "close"))
    p.add_argument("id")
    p.add_argument("--note", default=None)
    p.set_defaults(func=cmd_marker)

    p = subparsers.add_parser("log", parents=[common], help="the chain")
    p.add_argument("wo")
    p.add_argument("--attempts", action="store_true", help="include refusal history")
    p.add_argument("--type", action="append", default=None,
                   help="only this event type (repeatable); receipt.check:class works")
    # Not --agent: that is already the global "who I am" option, and a
    # filter sharing its name would read as identity.
    p.add_argument("--recorded-by", dest="recorded_by", default=None,
                   help="only events this agent recorded")
    p.add_argument("--since", default=None, help="only events at or after this time")
    p.add_argument("-n", "--number", type=int, default=None,
                   help=f"only the last N matching events"
                        f" (default {query.DEFAULT_LOG_TAIL})")
    p.add_argument("--all", action="store_true",
                   help="no tail bound — the whole chain")
    p.add_argument("--full", action="store_true",
                   help="complete event payloads instead of compact lines")
    p.set_defaults(func=cmd_log)

    p = subparsers.add_parser("agents", parents=[common],
                              help="per-agent projection over what is recorded")
    p.set_defaults(func=cmd_agents)

    return parser


def split_command(argv):
    """Everything after a standalone ``--`` is the wrapped command, verbatim."""
    if "--" in argv:
        index = argv.index("--")
        return argv[:index], argv[index + 1:]
    return argv, None


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    head, wrapped = split_command(argv)
    parser = build_parser()
    ctx = None
    try:
        args = parser.parse_args(head)
        args.wrapped = wrapped
        ctx = Context(args)
        return args.func(ctx, args)
    except WfError as exc:
        payload = exc.payload()
        if ctx is not None and ctx.json:
            print(canonical.dumps(payload), file=sys.stderr)
        else:
            print(str(exc), file=sys.stderr)
        return exc.exit_code
    except BrokenPipeError:  # pragma: no cover
        return EXIT_OK
    except Exception:  # noqa: BLE001 — a bug is not a refusal
        # A bug in wf is neither a refusal nor an evidence-integrity failure.
        # Exiting 1 would file it under "refused", which is the one reading
        # that must never be wrong, so it gets a code outside §4's map.
        import traceback

        traceback.print_exc()
        print("wf: internal error — the exit map above does not cover this",
              file=sys.stderr)
        return EXIT_INTERNAL
    finally:
        if ctx is not None and ctx.store is not None:
            ctx.store.close()


if __name__ == "__main__":
    sys.exit(main())
