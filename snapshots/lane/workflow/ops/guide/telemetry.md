---
name: guide-telemetry
description: The telemetry mini app — supervising background reviewers, and answering what work cost and where it was wasted.
covers:
  - ops/devlane/telemetry/
---

# The telemetry app

Four programs over the harness session stores. They answer three
questions: is a background run still healthy, what did work cost, and
where did the cost go.

| program | question |
|:--|:--|
| `breaker.py` | is this background reviewer still doing useful work? |
| `usage.py` | what has each harness spent, per session? |
| `pulse.py` | what is running right now, in this checkout? |
| `worth.py` | what did a window of work cost, and what did it produce? |

Every figure is derived from the stores at run time and stamped with
the window and repo state it was measured in. Nothing here is ever
reported in dollars: the only native cost figure any harness emits is
Grok's `costUsdTicks`, whose scale is unverified, so it is reported as
raw ticks or as `unrecorded`.

## The battery: supervising a background reviewer

An unattended reviewer once ran for an hour in a loop. `breaker.py`
watches its session stream and trips six wires — total tokens, output
tokens, stall, size, repeat-loop, error-storm:

```sh
python3 ops/devlane/telemetry/breaker.py "$STREAM" --pid "$RPID" \
  --cap 2000000 --cap-out 100000 --stall 600 --size-mb 50 \
  --terminate --tripped-file TRIPPED.md
```

A trip is **exit code 3**: the evidence goes to stderr, a `TRIPPED`
file names the wire that fired, and `--terminate` kills the runaway.

Three things about arming it:

- **The caps default to zero and a zero cap is a disarmed wire.** The
  table of wires is only true if the recipe passes them.
- **A killed review did not finish.** Name the tripped reviewer in the
  PR body exactly as you would an unreachable one; a review cut short
  silently is the same lie as one that silently shrank.
- **Grok's accounting is cumulative per run**, and a run ends when a
  reported total *shrinks*. Getting this wrong over-counts badly — an
  early version reported 5.5M tokens for one session by taking a
  running maximum.

The whole recipe, including how to find the stream a reviewer just
opened, is pinned verbatim in
[`ops/process/cross-review.md`](../process/cross-review.md) — pinned
because shell offers unlimited ways to write a subtly different
command, and the check compares the fence to a constant rather than
trying to pattern-match intent.

## Spend

```sh
python3 ops/devlane/telemetry/usage.py report --repo "$PWD"
python3 ops/devlane/telemetry/pulse.py --repo "$PWD"
```

Accounting rules, each measured rather than assumed:

- **Claude**: per message, last write per message id wins. Summing
  every line double-counts re-emitted messages — that mistake once
  inflated a figure by about 1.9×.
- **Codex**: token counts are cumulative, so the *last* count is the
  spend. Summing them is the classic double-count here.
- **Grok**: usage rides `updates.jsonl` `turn_completed` events,
  cumulative within a run, runs split when a reported total shrinks.

Absent or unreadable stores report `unrecorded` — never `0`. A session
whose spend cannot be read still holds its place in a `counted=N/M`
denominator, so a store with holes cannot present itself as complete.

## Worth: cost against results

```sh
python3 ops/devlane/telemetry/worth.py report --repo "$PWD"
python3 ops/devlane/telemetry/worth.py waste --repo "$PWD" --top 5
```

`report` joins the window's spend with what the repo's first-parent
history actually landed — merges with their PR numbers, commits, and
the change in test-definition count between the window's edge trees.
`waste` ranks sessions by window spend and names two signals:

- **cache-churn** — cached reads more than 20× output, meaning context
  is being re-read rather than used.
- **heavy-turn** — the single heaviest message or run, with the
  session id, so the transcript can be opened.

Signals point; they never conclude. The classes they map to, and the
countermeasure for each, are in
[`ops/process/token-thrift.md`](../process/token-thrift.md).

Time is always an input: `--now` is injectable so no test depends on
the wall clock, and windows are `[since, until)` — inclusive lower,
exclusive upper.

## Working on this app

```sh
python3 -m unittest discover -s ops/devlane/telemetry/tests
```

The suites lean on [the fixtures app](fixtures.md) for realistic store
shapes. When you change an accounting rule, change the fixture and the
reader together — a rule that only exists in the reader is a rule no
test can contradict.
