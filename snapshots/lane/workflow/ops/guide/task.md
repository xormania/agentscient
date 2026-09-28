---
name: guide-task
description: The task mini app — a calling convention for delegated work, so a Conductor can buy labour without reading it.
covers:
  - ops/devlane/task/
---

# The task app

A **task** is one delegated unit of work that returns one deliverable
in one round. It is not a conversation and not a workflow stage: the
Conductor calls it with parameters, the task iterates internally, and
it hands back a typed envelope.

| file | job |
|:--|:--|
| `ops/devlane/task/run.py` | the wiring: snapshot, launch, supervise, collect, parse |
| `ops/devlane/task/envelope.py` | the return shape, and one implementation per rule |
| `ops/devlane/task/fileset.py` | the smallest context a task needs, proved minimal |
| `ops/devlane/task/verify.py` | the job that needs no harness |
| `ops/devlane/task/jobs.json` | the jobs, as data rather than code |

The full calling convention lives in `ops/devlane/task/CONTRACT.md`. This
page is the shorter version: why it exists, and what to run to watch
it work.

## Why it exists

The point is not correctness — the checks and the cross-review process
already own that. The point is a standard, token-efficient way to run
delegated work, so the plumbing is written once and the Conductor never
parses prose.

It was measured before it was built. One session launched 36 agents and
hand-wrote the same ~40 lines of plumbing for nearly every one; 15 of
those 36 were repeat rounds of a review already run, each handed the
whole diff again because there was no parameter for scope. Two costs
follow, and both are what this app removes: plumbing retyped per
launch, and the Conductor reading work product until its context is too
full to run another round.

The property it holds: **iteration N should cost the Conductor about
what iteration 1 cost.** The envelope is the mechanism — `artifacts`
are handles, not contents, so the prose stays on disk and the Conductor
reads it only if it decides to.

## Status is not verdict

Every task returns the same shape, and two of its fields are
deliberately separate:

| field | answers |
|:--|:--|
| `status` | did the task run? `ok`, `invalid`, or `tripped` |
| `verdict` | what did it conclude? `approve`, `changes`, or null |

A task that could not look — harness missing, ref absent, output
unparseable — reports `invalid`, and **`invalid` is never reported as
an approving verdict**. That is the same rule the registered checks
follow, and the reason these are two fields rather than one.

`tripped` means the battery in `ops/devlane/telemetry/breaker.py` stopped
a runaway; the deliverable is partial and says so.

## What the runner does not do

It does not read the work product, and it does not decide anything a
job could not have decided in advance. Two things stay outside
it. **Intent** — which of two defensible designs is right — belongs to
the job author or escalates to the owner. And **the wiring's own
correctness** cannot be delegated to the tasks it wires, which is why
every job is bound to a planted fault: run it against a fixture
with a known defect and it must surface it, run it clean and it must
stay quiet.

## See it for yourself

The suite runs against a `stub` adapter, so nothing here spends a token
or needs a model:

```sh
python3 -m unittest discover -s ops/devlane/task/tests -t ops/devlane/task/tests
```

One job is callable on its own, because its answer is mechanical
— an exit code or a diff, not another opinion:

```sh
python3 ops/devlane/task/verify.py --help
```
