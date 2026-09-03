---
name: guide-harness
description: The harness mini app — dispatching an agent with the operator's setup stripped out, the right files staged, and a supervisor whose thresholds were measured.
covers:
  - ops/devlane/harness/
---

# The harness app

Four modules and two CUE files that answer one question: **when this
lane dispatches an agent, what exactly is it dispatching?** Not the
prompt — the whole environment. Which instruction files the harness
picked up, which repository files it can see, what will terminate it,
and what its answer is allowed to claim.

Every part of it exists because the hand-rolled version was wrong on
2026-08-22 and nothing announced it.

| module | the question it answers |
|:--|:--|
| `ops/devlane/harness/isolation.py` | does this agent carry the operator's personal setup? |
| `ops/devlane/harness/probe.py` | is that still true of today's harness build? |
| `ops/devlane/harness/stage.py` | did the files we withheld actually stay withheld? |
| `ops/devlane/harness/wires.py` | what will kill this run, and why that number? |
| `ops/devlane/harness/context.cue` | is this dispatch complete enough to send? |
| `ops/devlane/harness/evidence.cue` | can this claim be re-derived, or only attested? |

## Isolation: a harness does not start empty

A harness launched from a developer's machine discovers instruction
files, hooks, skills and MCP servers from that person's home
directory. None of that is this project's law: it is not in the
repository, no other harness shares it, and CI does not have it.

All three harnesses do this, and each reads a different place, so the
fix is per-harness data rather than one flag:

```sh
python3 ops/devlane/harness/isolation.py --sh claude /tmp/snapshot
```

That emits `ISO_ENV`, `ISO_FLAGS` and `ISO_STORE` for a launcher to
eval. Two mechanisms are in play — some harnesses take flags that
suppress discovery, others only respect a redirected home — and a
harness with **no entry at all** raises `NotIsolated` and exits 78.
Refusing is the point: an unknown harness must not be dispatched on
the assumption that it behaves like a known one.

## The probe: an isolation claim has a shelf life

Every entry in `HARNESSES` was true of one harness version on one day.
A release that adds a discovery path breaks isolation without breaking
anything that would announce itself, so the entries are claims and the
probe re-runs them.

```sh
python3 ops/devlane/harness/probe.py
python3 ops/devlane/harness/probe.py claude --behavioural
```

The structural arm is free and reads the minimal home. The behavioural
arm actually launches the harness and asks it what it loaded — the
only kind that catches a harness ignoring the variable — so it costs a
dispatch.

A behavioural check runs **two** arms, and both must succeed on their
own terms: an unisolated arm that must show the leak, and an isolated
one that must not. An arm that never ran is reported `INVALID`, never
as a pass. A harness that died before loading anything shows no leak,
and reading that as "isolation worked" is a test proving its own setup
never happened.

## Staging: withholding is invisible unless you check

The dispatch method this lane relies on is that two authors work from
different halves of the truth and never see each other's half — one
writes a contract from the specification without the code, another
describes the code without the specification. A disagreement between
them is then real, because neither was in a position to reconcile it
quietly. See [the cross-review process](../process/cross-review.md).

That only holds if the withholding happened. A snapshot that leaked
the wrong file looks exactly like one that did not.

```python
m = load(path)
stage(m, "extractor", dest)      # copies exactly the given set
prove(m, "extractor", dest)      # raises FirewallBreach otherwise
```

`prove` asserts **both** directions — nothing withheld is present, and
everything given did match something. The second half is what catches
the empty snapshot, which satisfies every withholding rule perfectly
and tests nothing. Build noise (`__pycache__`, `.pyc`, lock files) is
returned as a third value rather than dropped silently, because a file
that vanished without being named is the same failure in miniature.

## Wires: the thresholds are data, with the measurement attached

`ops/devlane/telemetry/breaker.py` watches a running dispatch and
terminates it when a wire trips. The wires are sound; every misfire
came from a threshold set by intuition and never re-derived.

```sh
python3 ops/devlane/harness/wires.py --sh reviewer
```

Two jobs live here and confusing them caused every misfire:

- **runaway detection** — a loop, an error storm, a hang. These have a
  *shape*, and shape is what detects them.
- **budget backstop** — "more than any legitimate run of its kind".
  A volume number, generous, a last resort rather than a control.

A volume cap asked to do runaway detection is always wrong, because
the quantity it measures rises with legitimate depth. The `tokens`
wire is disabled outright for that reason: it counts cache re-reads,
which were the overwhelming majority of one run's "total" while real
output was a small fraction of it.

The asymmetry sets the numbers. A cap too high costs tokens on a
subscription already paid for; a cap too low costs the whole run and
sends the next reader diagnosing the wrong thing.

## The two CUE files

`ops/devlane/harness/context.cue` defines what a role is permitted to
hold and, more usefully, `#Dispatchable` — the conditions under which
a dispatch is complete enough to send at all. An unmet requirement or
a dangling cross-reference makes it undispatchable rather than merely
noted.

`ops/devlane/harness/evidence.cue` separates a **receipt** from an
**attestation**. A receipt names the command that re-derives it. An
attestation is a judgement, and the schema gives it no field in which
to claim reproducibility — the constraint is structural rather than a
rule someone has to remember.

## Working on this app

```sh
python3 -m unittest discover -s ops/devlane/harness/tests
python3 ops/devlane/harness/vet_context.py
python3 ops/devlane/harness/controls/build.py          # regenerate them
```

The first runs in CI. The second does not: it needs `cue` on PATH, and
rather than skip when the tool is missing it **refuses** — exit 2, no
verdict — because a check that quietly does not run is the failure this
app is named after.

`vet_context.py` runs the controls, and the half that matters is the
negative one. There are three that must validate — one per isolation
mechanism, plus a receipt for `evidence.cue` — because a schema that
rejects everything passes every negative case perfectly, and a rule only
the home branch witnesses is a rule the flags branch never exercises. Then each document under `controls/rejects/` must be rejected
**at the field its `.reason.json` names** — because a fixture refused
for some other reason reports a guard that is not there. That is not
hypothetical: the stale-version fixture was being rejected the whole
time by a `mechanism: conflicting values` error, because the constraint
had collapsed a disjunction instead of firing.

**A constraint is also a default, and that is the hole this app kept
falling into.** Writing `operator_config_present: false` in the gate
does not only *check* the field — it *supplies* it, so a context that
never mentioned the probe validates with the clean answer written in for
it. `cue vet -c` cannot tell: after inference the field is concrete.
Deleting every leaf of a passing control in turn found **28 paths** that
could be omitted and still validate.

So `vet_context.py` reads the raw JSON before it runs `cue vet`:

- `MUST_BE_STATED` — paths whose omission lets the gate manufacture the
  answer. `--stated <context.json>` runs this against a real dispatch.
- `MUST_MATCH_IN_SOURCE` — pairs the law unifies, which must also be
  equal *in the document*. A task stating `[{path}]` inherits the
  interface from the brief and then reads as agreement; comparing the
  raw values kills that whole class rather than listing every leaf.
- and every path that *can* be omitted must be on one of those lists or
  explicitly waived, so a new constraint that introduces a new default
  is reported rather than found by the next reviewer.

**The controls are generated, never edited.** `controls/build.py` reads
the harness facts out of `isolation.py` and derives every rejecting
document from a passing one by changing exactly one subtree; `--check`
regenerates and compares, and the harness suite fails if a control on
disk differs. Both rules come from the same incident: the hand-written
positive control encoded five untruths about the module it described —
flags the launcher does not pass, an environment variable that mechanism
never sets, a version the module records as unrecorded — and it was
itself illegal under the law it was meant to demonstrate. A fixture that
changes two things at once is the second rule: it still fails when only
one of the two guards exists, so it witnesses neither.

The modules' own entry points are the other thing to run:

```sh
python3 ops/devlane/harness/isolation.py
python3 ops/devlane/harness/probe.py
python3 ops/devlane/harness/wires.py
```

The doctrine a dispatched agent should hold is root `AGENTS.md`. Root
`CLAUDE.md` points at it for the harness that does not load `AGENTS.md`
on its own. Both are dev-lane surfaces. Root files reach every cwd
under cwd-upward load; they will not be inherited by the product lane
(`AGENTS.md` §The owner's standing rules).

Related: [the telemetry app](telemetry.md) owns the breaker these
wires configure, and [the dev lane](dev-lane.md) explains where a
dispatch sits in a work order.
