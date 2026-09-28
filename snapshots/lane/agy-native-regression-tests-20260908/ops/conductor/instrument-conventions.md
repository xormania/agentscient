# Instrument conventions — the lane's base contract

Scope: dev tooling, governed by
[AGENTS.md §Lane boundary and precedence](../../AGENTS.md#lane-boundary-and-precedence).
These instruments operate independently of the Symfony application and
its vendor directory. Shared wire and provenance remain binding; the
application's four projections do not prescribe these tools' runtime or
retirement. The 2026-09-05 owner correction overrides conflicting older
stack, migration and planning records, including when served by onboarding.

Standing: PROPOSED (D-LAW-8). Source of demand: the same conventions
were retyped from recall into three instrument contracts in one night
(register, ledger, watch) and the third retyping dropped a clause — the
refusal one-line rule — which two blind producers then implemented two
ways. The owner's diagnosis is the law here: conventions live as data
plus a gate, never as per-contract recall, "not point tipping the
stochastic scales."

An instrument contract **inherits this document by reference** and
states only what is specific to its instrument. Restating a convention
is drift: two statements of one rule will diverge, and the divergence
will be discovered by a reconciliation instead of a diff.

## The refusal wire

One line per refusal, on stderr, exit 2, stdout empty:

    class: expected <what>; found <what>; needed <remedy>

The class is a lower-case token from the instrument's refusal table.
Expected / found / needed are each present, in that order. Nothing else
accompanies a refusal.

## Identity

Writing verbs require `WF_AGENT` matching `.+ <addr>` and refuse class
`identity` without it. Reads need no identity. Where rows are stamped,
`agent` comes from `WF_AGENT` and `session` from `CLAUDE_SESSION_ID`
(else `unknown`).

## The four classes on the wire

| exit | class | meaning |
|---|---|---|
| 0 | — | the verb did what it says |
| 1 | Finding | ran to completion; the result carries findings |
| 2 | Rejection | refused before acting; the refusal wire says why |
| 3 | Abort | stopped mid-act by wall, kill, or conflict — printing its last reading first, leaving commits, never residue |

## Instrument shape

`python3 ops/conductor/tools/<name>.py`, stdlib only. Contract at
`ops/conductor/<name>.md` (or `<unit>-lever.md`); tests at
`ops/conductor/tests/test_<name>.py`. Timestamps UTC. Stores honor
`XDG_STATE_HOME`, else `~/.local/state`, so tests plant state under a
temp `HOME`.

## Lint duty

Repo `ruff.toml` governs. An instrument that must shell out earns a
THIS-FILE-ONLY per-file row with the reason stated, or stays clean —
never a wildcard.

## The conformance gate

`ops/conductor/tests/test_instrument_conventions.py` holds a registry
of instruments that declare this inheritance, each with one hermetic
refusal-provoking invocation, and asserts the wire on every one: exit
2, a single non-empty stderr line, class token, expected / found /
needed, empty stdout. A new instrument joins the registry in the PR
that lands it. Instruments predating this document (skills.py,
co_doc.py) join as they adopt the wire; until then their absence from
the registry is recorded fact, not compliance.
