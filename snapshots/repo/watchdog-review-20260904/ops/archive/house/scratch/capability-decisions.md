# Capability abstraction — ratification ledger

Owner rulings against the open decisions in `capability-abstraction.md`.
Recording a ruling here **is** the ratification (hole-closing is ratification).

Status: **2 ruled, 1 deferred, 3 open.**

## Correction — `lane` deferred (owner, 2026-08-27)
`lane` was added as a required field (pinned `"dev"`) across the capability contracts, on
the rationale "bake the seam in now, cheap." That **contradicts** the ratified "dev-lane the
hard way / don't abstract from one instance" principle: `lane` only carries meaning once a
SECOND lane exists, and none does. So it is premature abstraction and is **NOT landed** — the
work lived only in a side-clone; nothing was committed or pushed.
- **LANE-NO-BLEED** stays a recorded *principle* for when prod-lane exists; it needs no `lane`
  field today (with one lane there is nothing to bleed into).
- The **D2 "per-lane instance"** refinement is likewise deferred until prod-lane exists.
- Revisit `lane` (as a shape/enum, factored from two *real* instances) only then.

## Ruled
- **D2 — evidence: SHARED.** One shared `evidence` ledger primitive; both `dispatch`
  and `certify` consume it (not an each-ledger-embedded design). — owner, 2026-08-27
- **D3 — snapshot: SPLIT.** `snapshot` (a frozen, read-only tree at a ref) is its own
  L0 primitive; `custody` depends on it (`custody → snapshot`). Custody =
  freeze-the-tree **+** control-what-crosses; snapshot = freeze-the-tree alone.
  Consumers that want snapshot *without* custody, which is why it splits:
  `certify` (run against a pinned tree), a diff (two trees), and the apply-push
  bridge (freeze the target branch to apply onto). — owner, 2026-08-27

## Ratified — contract/doc architecture (owner, 2026-08-27)
Two-level structure, the two-contracts model mapped onto the repo:
- **Per-app (local):** each mini-app has its own CUE contract (guarantees, record shapes,
  refusals) + its `guide/<app>.md`. Verified by the app's own gates.
- **General (tie-together):** one relational CUE contract — composition/DAG, cross-cutting
  invariants — plus `ops/docs/` (capability map, `DECISIONS.md`, reference).
- **All CUE contracts unify in one package**, so a single `cue vet` check verifies the whole
  composition FAST and deterministically (verification-collapse: verify the law once, not the
  implementation forever). Contracts are CUE, not prose — so the whole set is one quick check.
- **Discipline:** the general layer holds ONLY relations / composition / invariants / cross-app
  decisions — never app-internal detail; every fact has one home (an edge lives in the DAG once).
- **Migration is incremental/friction-driven:** harness `context.cue`/`evidence.cue` are already
  CUE; prose `CONTRACT.md` and JSON `imports.json` fold into the unified CUE set as touched.

## Deferred
- **D1 — task: OPEN.** Owner: "we'll talk about task more." Does `task` survive as a
  thin calling-convention façade, or dissolve into `dispatch` + `law`?

## Open (not yet raised)
- The remaining decisions in `capability-abstraction.md` §G (D4–D6) — not yet put to the owner.

## Cross-cutting invariant
- **LANE-NO-BLEED (owner, 2026-08-27).** These capabilities and the levers/bridge are
  dev-lane *instruments*, but their product is the House product (prod-lane). The two lanes must
  not bleed. Two bleed modes to guard:
  1. **Vocabulary/semantic** — dev-lane terms (custody, snapshot, dispatch, law, trinity,
     gap, contract) must not enter the House product-proper's specs/code. Extend the existing
     vocabulary-wall to the new capability vocabulary.
  2. **Instance/data** — no runtime instance (an evidence ledger, a dispatch record store,
     a context store) may be shared across lanes; custody is the enforcement.
  Consequence: a capability is defined **once** (shared shape/contract) but **instantiated
  per lane** — the shape is shared, the instance is not.

### Refines D2 (evidence: shared)
"Shared" = one shared evidence *capability/schema*, consumed by dispatch and certify
**within a lane**. It does NOT mean one ledger instance across dev-lane and prod-lane —
that would be instance-bleed. **Pending owner confirmation:** shared-schema, per-lane-instance.

## Directional rulings (capability shape)
- **`workflow` = lever-backed runner (owner, 2026-08-27).** The L2 `workflow`/orchestration
  capability is a deterministic DAG driver whose "run a stage" is a **lever dispatch**, never
  a Claude sub-agent. Orchestration = *sequence dispatches + gate on their scoped results*.
  The generic Workflow tool (which spawns full-context Claude sub-agents) is the WRONG
  implementation of this capability and is not to be used; the lever-backed runner replaces it.
  Layering: `workflow → dispatch → {custody, snapshot, evidence}`. Build order: it depends on
  `dispatch` being solid and the apply-push bridge being trusted (a runner that can't land is
  not a pipeline), so it comes AFTER those. Payoff: retires the conductor's hand-orchestration,
  which currently spends conductor context per stage.

## Consequences already in motion
- The **apply-push bridge** (in build) is the first concrete consumer of `snapshot`
  as a standalone primitive — it freezes the target branch's tree and applies onto it,
  with zero harness-custody. Consistent with D3.
- Migration **Step 1** remains the §Dispatch relocation (in flight): `launch.py` +
  `record.py` out of `task` into a `dispatch` composition capability.
