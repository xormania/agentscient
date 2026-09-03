---
name: telemetry
description: The dev lane's telemetry family — usage (after the fact), pulse (right now), breaker (live tripwires) — and the measured accounting rules behind them.
covers: [ops/devlane/telemetry/]
---

# Telemetry

Three tools, one question each:

| tool | question | when |
|:--|:--|:--|
| `usage.py` | what did it cost? | after the fact |
| `pulse.py` | what is running and what is it doing? | right now |
| `breaker.py` | is it failing? (kills on trip) | live |

All three read the harnesses' own stores; nothing instruments
anything, unknowns stay explicit gaps, and content never leaves the
stores — names and numbers only.

## The grok accounting rule (measured 2026-08-21)

Grok records spend in `updates.jsonl` `turn_completed` events. Usage
is cumulative *within a run*; a run ends when a REPORTED totalTokens
shrinks (turns can rise or repeat across a reset, so numTurns is not
the signal); within a run the last report per currency wins; session
spend is the runs' sum. `costUsdTicks` is raw — the tick scale is
unverified, so no USD is ever derived. Claude dedups by message id
(snapshot rewrites re-emit lines); Codex counts are cumulative,
last-wins. Sessions predating grok's usage recording stay
`tokens=unrecorded` — a gap, never a zero.

## Reading it

    python3 ops/devlane/telemetry/usage.py report --repo <path>
    python3 ops/devlane/telemetry/pulse.py --repo <path>

The cross-review recipe (ops/process/cross-review.md) arms the
breaker over every background reviewer; a trip is exit 3 plus a
TRIPPED file, and a tripped review must be named in the PR body.
