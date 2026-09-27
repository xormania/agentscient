# Ratification — the conductor's live-state board

Plan: `ops/docs/scratch/board-plan.md`, record
`20260830T091157Z-plan-codex-3ac9d4`, landed verbatim at `0938e74`.

Owner, 2026-08-30, on being shown 350+ commits adrift across 14 branches with
three open PRs between them: "too many things get lost currently - i feel the
need for some form of project managment feats are in order" → "yes - ratfiy -
get work done - done".

## D-BOARD-1 — option (a), the bridge, with its deletion boundary (ratified_by: owner)

Ship a read-only conductor instrument over the data that exists now — the
dispatch records, `meters.db`, `git`, `gh` — under `ops/conductor/`, replacing
its acquisition adapters as the ratified kernel and custody capability land.

The plan's boundary is ratified with it and is not advisory: the bridge may not
grow its own registry, dependency injection, service locator, MCP server or
durable source of truth. Those would be a second kernel and would turn bounded
rework into a rewrite. Its CLI verbs, renderer, JSON shape, owner-decision
markers and failure corpus are what survives; acquisition, cache and provenance
code are what gets replaced.

**Reason:** the failure it prevents is active and measured. Two closed units
(`agentscient/U0`, `U1`) have sat 24 and 25 commits off their integration
branch for a day; PR #83 was red for four hours while the conductor twice
reported it green. **Premise:** the branch measurement of 2026-08-30 and the
plan's own §1.

## D-BOARD-2 — the board is read, not remembered (ratified_by: conductor, Claude Fable 5)

Owner: "we need to get MCP useful - it is the way you access fresh context."
The plan excludes any MCP surface before the kernel, and the ratified framework
order keeps MCP at U11. Both stand. **A CLI the conductor must remember to run
reproduces the failure it exists to fix**, so the bridge's output is surfaced
automatically — a session-start hook injecting the compact digest — rather than
depending on the conductor's recall. No MCP server, no second kernel, no change
to the framework order.

**Reason:** every stale claim this session came from state that required an act
of remembering. The transport is not the point; the automaticity is.
**Premise:** four measured false claims on 2026-08-30, `session-2026-08-30.md`.

## D-BOARD-3 — v1 answers exactly the losses that were measured (ratified_by: conductor, Claude Fable 5)

Four queries, no more: branches ahead of their target **with no open PR**; PR
check state **with the time it was measured**; open decisions awaiting the
owner; dispatches in flight with elapsed time.

Duplicate-deliverable detection is **out of v1** and named here so it is not
forgotten: `e2e-fixture/dev` and framework **U7** are substantially the same
deliverable and that was found by accident. It needs the plan-unit graph, which
is framework U18.

## D-BOARD-4 — every value carries when it was measured (ratified_by: owner, standing)

The ratified context-custody amendment applies without exception: a value
carries the time and command it was measured by, and "unmeasured here" is a
legitimate answer. A board that returns a confident stale number is worse than
no board, because it launders a recollection into a fact — which is the exact
mechanism of this session's four false claims.
