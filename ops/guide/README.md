---
name: guide-index
description: Instructional entry point for the dev lane and each of its mini apps — start here.
covers:
  - ops/devlane/
  - ops/process/
---

# The dev-lane guide

Teaching material, not a status page. Every page here explains how
one part of the lane works, why it works that way, and what to run to
see it for yourself. When a page and the code disagree, the code is
right and the page is a bug — `test_guide.py` checks the parts a test
can check, and the rest is on the reader to report.

Three trees hold documentation here, and mixing them is how
documentation rots:

| where | holds | audience |
|:--|:--|:--|
| **this guide** | how the lane works, stable | anyone learning it |
| `ops/process/` | the contracts a work order must follow | whoever is executing one |
| `ops/docs/` | the owner's working shelf, current state | the owner |

## Read in this order

1. [The dev lane](dev-lane.md) — the whole system: what a work order
   is, how evidence is recorded, what CI enforces, how a change gets
   from an idea to `dev`. Read this first even if you only care about
   one app.
2. [The workflow app](workflow.md) — `wf`, the recorder: work orders,
   stages, gates, the evidence chain.
3. [The telemetry app](telemetry.md) — what runs cost and whether a
   background reviewer is still healthy.
4. [The fixtures app](fixtures.md) — measured store shapes, so tests
   assert against reality instead of a guess.
5. [The hooks app](hooks.md) — git-native recording of who moved
   what, for every actor rather than only the ones that cooperate.
6. [The harness app](harness.md) — dispatching an agent: what its
   environment carries, which files it may see, and what will stop
   it.
7. [The task app](task.md) — delegated work as one call returning one
   typed envelope, so a Conductor's context stays flat across rounds.
8. [The dispatch app](dispatch.md) — the launcher that runs those jobs
   under isolation and records each dispatch, composed from the task and
   harness apps.

## The idea underneath all of it

The lane is built around one rule: **a claim that no command can
re-derive is not evidence.** Nearly every mechanism here is that rule
applied to a different surface — a gate is the rule applied to
"the tests pass", the chain is the rule applied to "this happened",
the vocabulary wall is the rule applied to "the design stayed clean",
and the linter is the rule applied to "the code is tidy".

The corollary shapes the code more than anything else: **"nobody
looked" must never print the same way as "we checked and it was
fine."** Usually that means refusing outright — the secret scan and
the lint check both exit non-zero when their fileset matched nothing,
and the lint check does the same when ruff is missing or the pinned
contract is absent. Where refusing would be wrong it means saying so
instead: a tree with no design surface yet is vacuously clean, so the
vocabulary wall passes but prints "nothing to scan" rather than
"clean", and a test asserts the repo's own wall never reaches that
line. A planted fixture that failed to plant is the third shape — its
case is reported INVALID rather than passed or failed, because a
precondition that never happened has no result.
