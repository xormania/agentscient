---
name: decisions
description: The owner's ratified dev-lane decisions, one dated line each — the log every harness can read, unlike any one assistant's memory.
---

# Decisions

Append-only; newest first. A decision that lives only in a chat or a
memory store is invisible to two of the three harnesses.

- 2026-08-27 — Capability `lane` field: deferred until a second lane
  exists; keep lane separation as a principle, but do not abstract a
  shared shape from one instance.
- 2026-08-27 — Capability evidence: one shared evidence primitive is
  consumed by `dispatch` and `certify`; this does not authorize a
  shared runtime ledger across dev and product lanes.
- 2026-08-27 — Capability snapshot: split into its own L0 primitive;
  custody depends on snapshot, while certification, diffs, and the
  apply-push bridge may consume snapshots without custody.
- 2026-08-27 — Contract/doc architecture: per-app CUE contracts and
  guides own local guarantees; one unified relational CUE layer and
  `ops/docs/` own composition and cross-app invariants; migration is
  incremental as existing prose and JSON are touched.
- 2026-08-27 — Workflow capability: a deterministic DAG driver whose
  stages use lever dispatches, layered over dispatch, custody,
  snapshot, and evidence; it follows a trusted apply-push bridge.
- 2026-08-27 — Lane separation: dev-lane instruments may produce
  the House product, but neither their vocabulary nor runtime data may bleed
  into the product proper.
- 2026-08-21 — Slice sequencing: analytics 2a (readers) before 2b
  (breaker wires + doc + guards flipped atomically); then test/CI
  hardening from the two evaluations; then BDD; then budget wires;
  then E2E.
- 2026-08-21 — Grok accounting: cumulative per run; a run ends when a
  REPORTED totalTokens shrinks; last report per currency; cost stays
  raw ticks until the scale is verified; gaps never become zeros.
- 2026-08-21 — Budget layer: its own PR after analytics; realtime
  continue/kill is the loop agent's marginal-cost/marginal-utility
  call; decisions and outcomes are ledgered.
- 2026-08-21 — Analytics data lives in a separate private data repo
  (JSONL ledger; SQLite only as a disposable local cache).
- 2026-08-21 — MCP: telemetry query tools join the EXISTING wf server;
  a tools/list size cap guards the schema surface.
- 2026-08-21 — Worktree convention (PR #25): one line of work, one
  worktree; a worktree add is a lock grab; one owner per worktree;
  the main checkout belongs to nobody.
- 2026-08-21 — Merge gate: red-first tests by a non-implementing
  harness, skeptic pass, audits AND adversarial runs from both other
  harnesses, full CI check set present and green; never merge red;
  branches are never deleted.
- 2026-08-21 — Time is a variable we control in all tests; real time
  survives only in labeled E2E smoke.
