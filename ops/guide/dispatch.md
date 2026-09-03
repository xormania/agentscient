---
name: guide-dispatch
description: The dispatch mini app — the dev-lane launcher, split out of task so it may compose task's jobs with harness's isolation without the forbidden import edge.
covers:
  - ops/devlane/dispatch/
---

# The dispatch app

**Dispatch** is the policy that turns a named job into a supervised
run: it mints a snapshot from a git ref, keeps every artifact outside
the tree, applies its preconditions as refusals, supervises the child
inline, and writes a tracked dispatch record on the lineage branch. It
is the sole dispatch path for dev-lane work.

| file | job |
|:--|:--|
| `ops/devlane/dispatch/launch.py` | the policy: mint, launch, supervise, collect, record |
| `ops/devlane/dispatch/record.py` | build and validate one dispatch record |

The full contract lives in `ops/devlane/dispatch/CONTRACT.md`. This page is
the shorter version: why it is a separate app, and what to run to watch
it work.

## Why it is its own app

The launcher genuinely depends on two others. It reads the task app's
job registry, `ops/devlane/task/jobs.json`, to know which brief to render;
and it drives the harness app's `ops/devlane/harness/isolation.py` and
`ops/devlane/harness/wires.py` to strip the operator's setup off the child
and to read the budget its battery enforces.

Living inside the task app, that second dependency would be a
`task → harness` edge, which the cross-app import contract in
`ops/contracts/imports.json` forbids — a launcher's coupling to a
harness must not be smuggled into the calling convention. So dispatch is
a *composition* app: it may depend **downward** on both `task` and
`harness`, and those two edges are declared explicitly. The reverse,
`harness → task`, would be a cycle and is not allowed.

`jobs.json` stays in the task app. A path read is data, not an import
edge in spirit — but the checker still sees the `task` path segment, so
`dispatch → task` is declared for it too, honestly.

## What it does, and does not

The launcher wires; it does not judge. It mints the snapshot with a
plain fetch (never `git worktree add`, never `git clone --shared`, both
of which leave the source reachable from inside the copy), supervises
the child with the battery in `ops/devlane/telemetry/breaker.py`, and
records what happened. It reads no work product and decides nothing a
job could not have decided in advance.

Every outcome that is not a clean run has a name — a refusal before
anything is minted, or a runtime outcome like `unsupervised`, `timeout`,
or `trip` — and the record carries it. "Nobody looked" never renders as
"we checked and it was fine".

## See it for yourself

The suite runs against a `stub` adapter, so nothing here spends a token
or needs a model or a network:

```sh
python3 -m unittest discover -s ops/devlane/dispatch/tests -t ops/devlane/dispatch/tests
```

The launcher's verbs are discoverable without dispatching anything:

```sh
python3 ops/devlane/dispatch/launch.py --help
```

Related: [the task app](task.md) is the calling convention whose jobs
this launches, and [the harness app](harness.md) is the isolation it
drives.
