---
name: guide-dev-lane
description: How the whole dev lane works — work orders, gates, evidence, cross-review, and CI — end to end.
covers:
  - ops/devlane/workflow/
  - ops/process/
  - .github/workflows/
---

# The dev lane, end to end

The lane exists because several agents and one owner change this repo
concurrently, and none of them can be taken at their word. Every
mechanism below replaces a claim with something re-derivable.

## The unit of work

A **work order** is one change with a recorded history. It carries a
kind (`tdd` for code, `artifact` for design), moves through stages,
and accumulates evidence that can be replayed later:

```sh
python3 ops/devlane/workflow/wf.py open WO-001 --kind tdd --objective "..."
python3 ops/devlane/workflow/wf.py claim WO-001
python3 ops/devlane/workflow/wf.py status
```

Stages are not decoration. `red` refuses a test command that passes,
because a red stage whose command was already green proves nothing.
`green` runs the command the red stage froze, not a fresh one, so the
thing that passed is the thing that failed before. Details in
[the workflow guide](workflow.md).

## Claims: refusal is a result

A claim is a lease on a work order. A second agent claiming a held
work order exits with a dedicated code and names the holder — it does
not queue, and it does not silently steal:

```sh
$ wf claim WO-001            # held by someone else
WO-001 is claimed by Other Agent <...> until 2026-08-22T09:00:00Z
$ echo $?
3
```

Distinct exit codes are a contract: `0` accepted, `1` refused, `2`
evidence integrity, `3` claimed, `64` usage, `70` internal. A refusal
is a normal outcome the system records; an integrity failure is not.

## Gates and checks

A **gate kind** (`ops/devlane/workflow/gate-kinds/*.json`) lists the
checks a work order of that kind must satisfy. Each check is an argv
command plus a `ci` flag:

```json
{"name": "lint", "class": "quality",
 "argv": ["python3", "ops/devlane/workflow/checks/lint.py"], "ci": true}
```

The registry is the single source of truth. CI does not keep its own
list — `checks/ci_matrix.py` derives the job matrix from the registry,
so adding a check with `"ci": true` puts it in CI with no workflow
edit. Verify that for yourself:

```sh
python3 ops/devlane/workflow/wf.py --json status --checks > /tmp/c.json
python3 ops/devlane/workflow/checks/ci_matrix.py /tmp/c.json
```

The registered checks today — the command above prints the same
matrix, so a row here that disagrees with it is this table being
stale, not the registry:

| check | in CI | refuses when |
|:--|:--|:--|
| `secret-scan` | yes | a credential-shaped string is tracked, **or the fileset matched zero files** |
| `vocabulary-wall` | yes | dev-lane words appear in the design tree |
| `commit-trailers` | yes | a commit's `Source:` or `Co-Authored-By:` line sits where git will not parse it as a trailer |
| `imports` | yes | a mini app reaches into another's internals, against the graph `ops/contracts/` states |
| `doc-commands` | yes | a shell fence tells a reader to run a path that is not there |
| `doc-covers` | yes | a shelf header lacks `name:` or `description:`, or a `covers:` path is not a repo-relative name resolving inside the tree |
| `lint` | yes | ruff finds anything, ruff is absent, or the pinned contract is missing |
| `cargo-test` | no | (registered, joins CI the day a Cargo workspace exists) |
| `audit` | no | (the same day, for the same reason) |
| `diagnostics` | no | (the same day, for the same reason) |

Every one whose argv names a script under
`ops/devlane/workflow/checks/` is bound to a planted fault by
`test_gate_binding.py`: running the **registered argv** against a repo
with the fault must fail, and against a clean repo must pass. That is
what stops a gate from being quietly gutted to `python3 -c pass` while
CI stays green. `imports` is the one CI check outside that directory,
so it is bound by its own suite under `ops/contracts/tests/` instead.

## Evidence that cannot be edited afterwards

Records go into an append-only chain, hashed link by link. `wf verify`
recomputes every hash; `--deep` also walks the prefix, which catches a
truncated tail that is internally consistent:

```sh
python3 ops/devlane/workflow/wf.py verify --deep
```

The tracked export under `ops/devlane/workflow/` is regenerated from the
database rather than written by hand, so the file in git and the
recorded state cannot drift apart.

## Cross-review: the part that finds real defects

Work is reviewed by a *different* harness than the one that wrote it,
because a suite written by the author of the code inherits the
author's blind spots. The process lives in
[`ops/process/cross-review.md`](../process/cross-review.md); the
shape is:

1. One harness authors failing tests from a behavior contract, without
   reading the implementation.
2. Another implements until they pass.
3. A third — the **skeptic** — plants mutants and reports which ones
   the suite fails to catch.

A finding is only accepted once it has been reproduced against the
live tree, and the fix ships with the reproduction. Reviews are pinned
to a commit; any push voids them.

Background reviewers are supervised by the battery
([telemetry guide](telemetry.md)) because an unattended one has burned
an hour and millions of tokens in a loop.

## CI

Two workflow files, five job shapes, eighteen check-run names:

GitHub's check-run / ruleset surface is the job name. The merge box
shows them as `CI / <name> (<event>)` — the ` / ` and the `(<event>)`
are GitHub's, not ours. A product lane later reads `CI / prod: …` with
nothing renamed.

| check-run name | runs |
|:--|:--|
| `dev: verify` | evidence verification — always reports |
| `dev: discover` | derives the gates matrix from the registry |
| `dev: gates (<check>)` | one entry per registered `ci` check |
| `dev: workflow (<shard>)` | the wf suite, sharded three ways |
| `dev: <app>` | one check per mini app: telemetry, task, hooks, fixtures, contracts, harness |

The merge box shows those as `CI / <name> (<event>)`. Both workflows
are unfiltered, so every check reports on every pull request and can
be required.

The full expected set is one command:

```sh
python3 ops/devlane/workflow/wf.py --json status --checks > checks.json
python3 ops/devlane/workflow/checks/ci_contexts.py checks.json
```

One invariant worth knowing before editing CI: **the gates job never
renders a verdict itself.** Exactly one step may evaluate — the `wf`
call, last — and anything else must be a version-pinned dependency
install. Otherwise a gate could be satisfied by work done CI-side.

## Getting a change in

Branch from `dev`, work in your own worktree, PR into `dev`. `main`
is the owner's. The full contract is in `AGENTS.md` and `CONTRIB.md`;
the parts people get wrong:

- **One line of work, one worktree.** A `git checkout` in a shared
  tree yanks HEAD from under every other session using it, and a
  `worktree add` on someone's branch locks them out at their next
  checkout with no error at add time.
- **Open the PR as a draft** while it is in flight, and mark it ready
  only when reviews are folded in. An open non-draft PR can merge at
  any instant, and anything pushed after that is stranded.
- **Every figure in a PR body or commit message comes from a command
  run at the moment of writing.** A remembered number is not evidence,
  and this lane has caught itself typing the wrong one more than once.
