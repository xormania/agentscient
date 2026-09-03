---
name: guide-workflow
description: The wf mini app — work orders, stages, gates, claims, and the evidence chain that cannot be edited after the fact.
covers:
  - ops/devlane/workflow/
---

# The workflow app (`wf`)

`ops/devlane/workflow/wf.py` records what happened while work was done,
in a form someone else can replay. It is a recorder, not a task
runner: it never decides whether your change is good, only whether
the evidence you offered is real.

```sh
WF=ops/devlane/workflow/wf.py
python3 $WF --help
python3 $WF status                 # open work orders
python3 $WF --json status --checks # the registry, as JSON
```

## The pieces

| file | what it owns |
|:--|:--|
| `wf.py` | the CLI: every verb, and the exit-code map |
| `store.py` | SQLite persistence; identifiers from code, values always `?`-bound |
| `chain.py` | the append-only hash chain and its reducer |
| `cas.py` | content-addressed blobs, verified before write |
| `coord.py` | claims and leases — who holds what, until when |
| `gatekinds.py` | reading and validating the gate-kind registry |
| `receipts.py` | check receipts: the recorded output of a registered command |
| `gitio.py` | the tracked export and commit plumbing |
| `verify.py` | recompute every hash and link; `--deep` walks the prefix |
| `query.py` | read models for `status`, `log`, `next` |
| `mcp_server.py` / `mcp_launch.py` | the same read models over MCP |
| `checks/` | the registered checkers themselves |

## Stages, and why they refuse

A `tdd` work order walks `spec → red → green → review → done`. Two
refusals carry most of the value:

- **A red that passes is refused.** If the command you offer as proof
  of failure exits 0, there is no red — recording one would make the
  later green meaningless.
- **Green runs the frozen command.** The red stage seals the test
  command; `green` re-runs *that* argv. Offering a different one is
  refused, because otherwise the thing that passes need not be the
  thing that failed.

Re-entering red after a green voids the frozen set deliberately, and
the route back is recorded (`wf advance --to red --reason ...`) rather
than silent.

## Claims

```sh
python3 $WF claim WO-001              # take a lease
python3 $WF release WO-001            # give it back
```

A conflicting claim exits `3` and names the holder and expiry. Claims
and sessions live only in the database — deliberately **not** in the
tracked export — which is why `init --rebuild` destroys them and why
the MCP launcher refuses to rebuild as a side effect of starting a
reader. A two-hour lease once became null because a status server
rebuilt the cache on launch; that path is now locked behind an
explicit rebuild.

## Checks and receipts

```sh
python3 $WF check --verify-only lint        # run it, record nothing
python3 $WF check lint                      # run it, record a receipt
```

`--verify-only` is what CI uses: the exit code is `wf`'s own, so a
wrapped command's code cannot collide with the exit-code map, and CI
originates no state.

A receipt that failed is still recorded — records are evidence — but
it satisfies nothing.

## The evidence chain

Every recorded event links to the previous one by hash.

```sh
python3 $WF log --full --all WO-001 --attempts
python3 $WF verify --deep
```

`verify` alone catches tampering inside the chain. `--deep` also
catches a chain that is internally perfect but truncated — the shape
you get when someone replays a prefix and stops.

## Working on this app

```sh
python3 -m unittest discover -s ops/devlane/workflow/tests   # ~558 tests
python3 ops/devlane/workflow/tests/acceptance.py             # the 22 checks
python3 ops/devlane/workflow/checks/lint.py                  # the lint gate
```

Two things will trip you up:

- **Import order in the tests is load-bearing.** `support.py` wires
  `sys.path`, so it must import before any workflow module. `ruff.toml`
  keeps the sorter off those blocks and `test_standalone_import.py`
  proves each module still imports alone — a module that only works
  under discovery is a false green.
- **The suites are sharded in CI** and the shard glob is pinned
  verbatim, because the live tree has no module that would reveal a
  narrowed glob by failing.
