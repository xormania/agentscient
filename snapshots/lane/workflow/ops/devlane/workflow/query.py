"""The query layer — everything that reads and nothing that writes.

PLAN §9 asks the MCP status server to be "read-only by construction: it
imports the query layer, not the append layer". That is only meaningful if
such a layer exists, so this is it: the body builders behind `status`,
`next`, `log` and `agents`, importing nothing that can append to a chain,
touch git, or record a receipt.

Every function here takes a context object and uses only its reading
surface — ``store``, ``chain``, ``specs``, ``cas``. It never imports wf, so
a caller can hand it a context far smaller than the CLI's.
"""

from __future__ import annotations

from pathlib import Path

import canonical
import chain as chainmod
import coord
import gatekinds
from errors import Integrity, Refusal


def spec_for(ctx, wo_row) -> gatekinds.Spec:
        """The spec a work order is pinned to — resolved from the CAS.

        The chain's pin is the authority and the registry is a convenience
        mirror (PLAN §6), so an in-place edit of a registered version cannot
        change how an already-open work order behaves.
        """
        digest = wo_row["spec_sha256"]
        if not ctx.cas.has(digest):
            raise Integrity(
                "the pinned gate-kind spec is missing from the object store",
                wo=wo_row["wo_id"], detail=digest,
            )
        raw = ctx.cas.get_json(digest)
        spec = gatekinds.Spec(raw, source=f"cas:{digest[:12]}")
        if spec.sha256 != digest:
            raise Integrity(
                "the stored gate-kind spec does not hash to its pin",
                wo=wo_row["wo_id"], detail=digest,
            )
        if (spec.kind, spec.version) != (wo_row["kind"], wo_row["kind_version"]):
            raise Integrity(
                "the pinned spec is for a different gate kind",
                wo=wo_row["wo_id"],
                detail=f"pin {wo_row['kind']}@{wo_row['kind_version']},"
                       f" spec {spec.kind}@{spec.version}",
            )
        return spec



def wf_argv(ctx=None) -> list:
    """The prefix that actually starts this CLI, against the right state.

    PLAN §4 promises `next` gives "the exact argv that advances it", and
    AGENTS.md tells agents the field runs verbatim. It emitted ["wf", …] and
    no `wf` binary is installed anywhere, so following the documentation
    produced `wf: command not found`. Nothing caught it because the test
    replayed argv[1:] through a harness that prepends the interpreter — a
    test shaped to agree with the code.

    The root is part of the argv for the same reason: without it, an argv
    computed for a non-default root replayed against the DEFAULT root — the
    checkout beside wf.py — and every test papered over it by appending
    --root by hand. It is emitted only when it differs from the default, so
    the common case still reads the way a person would type it.

    Relative to the working directory when that is shorter, so the command
    reads the way a person would type it.
    """
    import os

    script = Path(__file__).resolve().parent / "wf.py"
    try:
        relative = os.path.relpath(script, Path.cwd())
    except ValueError:                      # a different drive on Windows
        relative = ".."                     # forces the absolute form below
    argv = ["python3",
            relative if not relative.startswith("..") else str(script)]
    if ctx is not None:
        root = Path(ctx.root).resolve()
        if root != script.parent:
            argv += ["--root", str(root)]
    return argv


def missing_evidence(spec, state) -> list:
    """What the current stage still needs before it can be left."""
    stage = state.get("stage")
    if stage is None:
        return []
    satisfied = set(state.get("satisfied", []))
    return [r for r in spec.leave_requires(stage) if r not in satisfied]


def build_check_argv(spec):
    """The argv ``next`` suggests for a red/green receipt, when the spec
    determines one. Returns ``None`` when it does not — a suggestion that had
    to be invented would be a guess wearing a contract's clothes."""
    for check in spec.checks:
        if check.get("class") == "build":
            return list(check["argv"])
    return None


def next_action(ctx, wo_row, projection):
    """What advances this work order, as an exact argv where one exists."""
    spec = ctx.spec_for(wo_row)
    state = projection.state
    wo = wo_row["wo_id"]
    stage = state.get("stage")
    complete = True

    if state.get("status") == "terminal":
        return {"advances": [], "advances_complete": True,
                "note": "work order is terminal"}

    missing = missing_evidence(spec, state)
    if "receipt.red" in missing:
        argv = build_check_argv(spec)
        complete = argv is not None
        return {"advances": wf_argv(ctx) + ["red", wo, "--"] + (argv or []),
                "advances_complete": complete, "requires_agent": True,
                "note": None if complete else
                        "the gate kind declares no build check; supply the test command"}
    if "receipt.green" in missing:
        frozen = state.get("frozen") or {}
        argv = frozen.get("argv")
        complete = bool(argv)
        return {"advances": wf_argv(ctx) + ["green", wo, "--"] + list(argv or []),
                "advances_complete": complete, "requires_agent": True,
                "note": None if complete else
                        "no frozen set is sealed; re-prove red and advance"}
    if missing:
        # A requirement is not a check name. "receipt.check:security" says
        # which *class* is wanted; the runnable command names a check that
        # has it, or there is no exact argv to give and saying so is better
        # than emitting one that cannot run (PLAN §4).
        etype, klass = gatekinds.split_requirement(missing[0])
        if etype == chainmod.RECEIPT_CHECK:
            candidates = [
                c["name"] for c in spec.checks
                if klass is None or c.get("class") == klass
            ]
            if len(candidates) == 1:
                return {"advances": wf_argv(ctx) + ["check", wo, candidates[0]],
                        "advances_complete": True, "requires_agent": True,
                        "note": None}
            if candidates:
                return {"advances": wf_argv(ctx) + ["check", wo, min(candidates)],
                        "advances_complete": False, "requires_agent": True,
                        "note": f"stage {stage} needs {missing[0]}; any of "
                                f"{', '.join(sorted(candidates))} carries that class"}
        return {"advances": [], "advances_complete": False,
                "note": f"stage {stage} still needs {', '.join(missing)},"
                        " and no registered check provides it"}

    outcomes = spec.outcomes(stage) if stage else {}
    if outcomes:
        actor = spec.actor(stage)
        note = (f"stage {stage} is left by recording an outcome:"
                f" {', '.join(sorted(outcomes))}")
        if actor:
            note += (f"; reserved to {actor} — recording states it, but the effect"
                     f" applies only when the attesting merge lands (D10)")
        # The verdict is the one thing next must never supply: a complete-
        # looking argv with an invented terminal decision (alphabetically,
        # "aborted") is the most dangerous suggestion there is. The skeleton
        # carries only what the spec states — the verb, and the actor when
        # one is reserved — and says what the caller must add.
        argv = wf_argv(ctx) + ["outcome", wo]
        if actor:
            argv += ["--by", actor]
        note += "; supply the verdict, --by (if not shown) and --source"
        return {"advances": argv,
                "advances_complete": False, "requires_agent": True,
                "note": note}
    if spec.next_stage(stage) is None:
        return {"advances": [], "advances_complete": True,
                "note": f"stage {stage} is the last stage and declares no outcomes"}
    return {"advances": wf_argv(ctx) + ["advance", wo], "advances_complete": True,
            "requires_agent": True, "note": None}


def summarise(ctx, wo_row, projection) -> dict:
    spec = ctx.spec_for(wo_row)
    state = projection.state
    return {
        "wo": wo_row["wo_id"],
        "kind": f"{wo_row['kind']}@{wo_row['kind_version']}",
        "objective": wo_row["objective"],
        "stage": state.get("stage"),
        "status": state.get("status"),
        "satisfied": list(state.get("satisfied", [])),
        "missing": missing_evidence(spec, state),
        "outcomes": list(state.get("outcomes", [])),
        "open_markers": list(state.get("open_markers", [])),
        "frozen": state.get("frozen"),
        "seq": projection.last_seq,
        "head": projection.last_hash,
        "last_commit": state.get("last_commit"),
        "claim": coord.current(ctx.store, wo_row["wo_id"], canonical.now()),
    }


# --------------------------------------------------------------------------
# verbs


def registered_checks(ctx) -> list:
    """Every check every gate kind registers, as a flat, sorted projection.

    PLAN §7 names this as the thing a CI matrix should be derived from, so
    the shape is the contract: a consumer must be able to build the matrix
    from this alone, with no other knowledge of the registry.

    ``ci`` defaults to **false**. The two failure directions are not
    symmetric — a check silently dropped from CI is a gate nobody notices is
    missing, while a check that breaks CI when added is noticed within one
    run — but the first is only silent if the default hides it. So the
    default is explicit opt-in, and this command reports the excluded checks
    alongside the included ones, which is what keeps the omission visible.
    """
    out = []
    for (kind, version), spec in sorted(ctx.specs.items()):
        for entry in spec.checks:
            out.append({
                "kind": kind,
                "kind_version": version,
                "name": entry["name"],
                "class": entry["class"],
                "argv": list(entry["argv"]),
                "ci": bool(entry.get("ci", False)),
            })
    return sorted(out, key=lambda c: (c["kind"], c["kind_version"], c["name"]))


#: The compact event line: what a reader scanning a chain needs. The
#: payload — hashes, digests, receipt bodies — is what ``full`` is for.
#: Measured before this existed: a six-event log cost 5094 bytes with full
#: payloads (~850/event), and every harness paid it per call, forever
#: growing with the chain.
COMPACT_EVENT_KEYS = ("seq", "type", "time", "agent", "class")

#: The default bound on an unqualified log read. Announced, never silent:
#: the body always carries ``considered`` so a bounded answer says so.
DEFAULT_LOG_TAIL = 50


def compact_events(events):
    return [{k: e[k] for k in COMPACT_EVENT_KEYS if e.get(k) is not None}
            for e in events]


def filter_events(events, *, types=None, agent=None, since=None, tail=None):
    """Narrow a chain for reading. Never touches what is stored.

    A filter that matches nothing and a filter that is broken look identical
    from the outside, so the caller is told how many events were considered
    and how many survived — and an unknown type refuses rather than quietly
    returning nothing (see cmd_log).
    """
    out = list(events)
    if types:
        wanted = set(types)
        out = [e for e in out if e.get("type") in wanted
               or f"{e.get('type')}:{e.get('class')}" in wanted]
    if agent:
        out = [e for e in out if e.get("agent") == agent]
    if since:
        out = [e for e in out if e.get("time", "") >= since]
    if tail is not None:
        # The last n. A log tail read from the front is the wrong end of the
        # log, which is the only end anyone wants.
        out = out[-tail:] if tail > 0 else []
    return out


# -- whole-response bodies -------------------------------------------------
#
# The CLI and the MCP server must answer with the SAME bytes (PLAN §9's "over
# the same --json surface"), so the response is built in one place and both
# callers dump it canonically.


def status_body(ctx) -> dict:
    items = []
    for row in ctx.store.list_work_orders():
        items.append(summarise(ctx, row, ctx.chain.project(row["wo_id"])))
    return {
        "work_orders": items,
        "sessions": coord.active_sessions(ctx.store, canonical.now()),
    }


def status_one_body(ctx, wo_id: str) -> dict:
    row = ctx.store.get_work_order(wo_id)
    if row is None:
        raise Refusal("work order exists", actual=wo_id,
                      needed="an id that has been opened", wo=wo_id)
    projection = ctx.chain.project(wo_id)
    body = summarise(ctx, row, projection)
    body["events"] = [
        {"seq": e["seq"], "type": e.get("type"), "time": e["time"]}
        for e in projection.events
    ]
    body["attempts"] = ctx.store.count_attempts(wo_id)
    return body


def next_body(ctx, wo_id=None) -> dict:
    if wo_id:
        row = ctx.store.get_work_order(wo_id)
        if row is None:
            raise Refusal("work order exists", actual=wo_id,
                          needed="an id that has been opened", wo=wo_id)
    else:
        rows = [
            r for r in ctx.store.list_work_orders()
            if ctx.chain.project(r["wo_id"]).state.get("status") != "terminal"
        ]
        if not rows:
            return {"wo": None, "note": "no open work orders"}
        row = rows[0]
    projection = ctx.chain.project(row["wo_id"])
    body = summarise(ctx, row, projection)
    body.update(next_action(ctx, row, projection))
    return body


def log_body(ctx, wo_id: str, *, types=None, recorded_by=None, since=None,
             tail=None, attempts=False, full=False) -> dict:
    row = ctx.store.get_work_order(wo_id)
    if row is None:
        raise Refusal("work order exists", actual=wo_id,
                      needed="an id that has been opened", wo=wo_id)
    projection = ctx.chain.project(wo_id)
    effective_tail = DEFAULT_LOG_TAIL if tail is None else (
        None if tail < 0 else tail)   # tail=-1 is the explicit "all"
    events = filter_events(projection.events, types=types, agent=recorded_by,
                           since=since, tail=effective_tail)
    body = {"wo": wo_id,
            "events": events if full else compact_events(events)}
    # `considered` is unconditional: a compact or bounded answer must say
    # what it was an answer about. `matched` keeps its filter semantics.
    body["considered"] = len(projection.events)
    if types or recorded_by or since or tail is not None:
        body["matched"] = len(events)
    if attempts:
        rows = [dict(a) for a in ctx.store.list_attempts(wo_id)]
        if recorded_by:
            rows = [a for a in rows if a.get("agent") == recorded_by]
        body["attempts"] = rows
    return body


def agents_body(ctx) -> dict:
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
                key = f"{etype}:{event['class']}" if event.get("class") else etype
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
    active = {s["agent"] for s in coord.active_sessions(ctx.store, now)}
    for entry in listed:
        entry["work_orders"].sort()
        entry["holds"].sort()
        entry["active"] = entry["agent"] in active
    return {"agents": listed}
