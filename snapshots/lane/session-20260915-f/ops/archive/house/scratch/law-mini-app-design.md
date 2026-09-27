---
name: law-mini-app-design
description: Design proposal for `law`, a looplaw-based dev-lane mini-app that replaces PLAN.md as semantic authority and certifies the other dev-lane mini-apps. PRE-RATIFICATION — nothing here is built, nothing here is law.
covers:
  - ops/devlane/workflow/PLAN.md
  - ops/devlane/workflow/contracts/
  - ops/devlane/task/
  - ops/devlane/harness/context.cue
  - ops/docs/mini-app-lessons.md
---

# The `law` mini-app — design proposal

**Standing: PROPOSAL, not law. Nothing below is built, ratified, or in
force.** This document is itself the intent half of the two-producer
method it proposes (§4): drafted from scope and the accumulated record,
no code written to match it. It exists to be ratified, amended, or
rejected by the owner — that act is what would make any of it real.

Owner's directive, verbatim, restated once so scope stays anchored:
*"PLAN.md has to go away — we don't patch it — we redesign the whole
thing so it's practical for the mini-apps now. What we learn we use for
a new mini-app. Law (looplaw based)."*

Everything here is traceable to a named source, never a line number —
the discipline this document asks the mini-app to enforce, applied to
itself. Citations point at document names and, where a fact was
measured, the measurement; re-derive them, don't trust them.

---

## 0 · What kind of document this is

A concrete design, not an essay: named artifact, named schema, named
gate conditions, named migration steps, each flagged for what it needs
from the owner. Where this proposal states a default, it states it as a
recommendation the owner can accept, amend, or override — never as
something already decided. Section 6 collects every point that is the
owner's call, not this document's.

---

## 1 · What the mini-app is

**Name: `law`. Location: `ops/devlane/law/`,** alongside `task`, `harness`,
`workflow`, `telemetry`, `hooks`, `fixtures` — the existing dev-lane
mini-apps, one lowercase word each. `law` follows that convention
because it is one more mini-app among peers, not a superstructure above
them.

**Single responsibility, stated as two halves of one job:**

1. **Hold the closed, enforceable semantic authority for the dev-lane
   mini-apps** — named, versioned contracts stating what must be true
   of each mini-app's interfaces, data shapes, and refusal behavior,
   plus the lexicon those contracts are written in and the judgment
   register accumulated from certifying them.
2. **Certify that each mini-app's code aligns with that authority** —
   run the comparison that proves agreement (or names the disagreement),
   and refuse CI when it doesn't hold.

These two halves are inseparable by design: a law nobody checks code
against degenerates back into prose (PLAN.md's fate); a certifier with
no named law to certify against has nothing to refuse by. `law` is
looplaw's own four essentials (define, judge coherence, diff goal
against view, adjudicate authority — `loopstack/organs/looplaw.md`)
scaled to this repo's dev lane and its current stack (Python, `cue`
shelled out — see §3), not a port of the Go kernel.

**What it is NOT** — each line below closes a door PLAN.md's history, or
looplaw's own boundary, opened and then had to shut by hand:

- **Not a workflow.** It does not decide order, schedule work, or
  replace `wf`'s stage/gate machinery. `wf` remains the loopstrap-shaped
  organ — it drives work; `law` is what work is driven *against*.
- **Not a plan.** It never states "how, in what order" — that is
  exactly PLAN.md's category error (§2). A plan is prose about sequence;
  a contract is a closed claim about shape. `law` holds only the latter.
- **Not a recorder of who did what.** Receipts, attempts, and claims
  stay `wf`'s lane (loopflow's role in the family). `law` records
  *certification* receipts only (§4) — a narrower, different ledger.
- **Not a deriver.** Reading what a mini-app's code actually does is the
  **observation producer's** job (§4), mechanical and blind to the
  contract, never the kernel's own inference.
- **Not aware of git or CI mechanics.** Trees and hashes are handed to
  it; it does not fetch, checkout, or branch. Substrate-blind, exactly
  as looplaw is (`looplaw-spec.md` §7): a driver swap at the edges never
  touches the law itself.
- **Not self-ratifying.** `law` can refuse; it cannot ratify. Only the
  owner ratifies, non-delegably, for `law`'s own founding contracts and
  for every contract it subsequently holds (§5, §6).
- **Not a home for `open`, `_`, or `inferred`.** These three spellings
  are banned outright, not discouraged (learnings-since-loopstrap.md
  §5.4). Every underspecified region becomes a **named refusal** or an
  **`unresolved:` entry awaiting ratification** — never a silent hole
  wearing a green check (§3).
- **Not a second PLAN.md.** No numbered sections, no addressable-by-
  position content anywhere in its schema or its files. The one failure
  mode this document is most directly answerable for avoiding.

---

## 2 · How it replaces PLAN.md

### 2.1 What PLAN.md's role actually is, measured

`CONTRACT-NOTES.md` (`ops/devlane/workflow/contracts/`) opens with: *"PLAN.md
is the only authority for semantic values."* Every constraint in the
twelve contracts it documents carries a `// PLAN.md lines N–M` comment.
Session-record count: **~1,340 line-number citations across 239 files**;
an independent recount in `contract-synthesis.md` corroborates the
magnitude at **212 files / ≥1,260 citations**. `vet.py`, the very script
meant to *compare* code against PLAN.md, itself binds `../PLAN.md` by
relative path at a fixed line — the comparator is coupled to the plan's
position on disk, not to anything named.

The category error, stated once: **a plan says how, in what order; a
contract says what must be true.** PLAN.md is written and read as the
first but cited as if it were the second. You can only cite a plan *by
position*, because it has no named, closed claims to cite by name — that
is the entire reason the citation count is a symptom, not a style
choice.

### 2.2 The decomposition already exists — reuse it, don't redo it

The good news: PLAN.md's semantic content has **already been decomposed
by hand once**, correctly, into exactly the shape `law` needs. The
twelve named regions in `CONTRACT-NOTES.md` / `EXTRACTION-NOTES.md` —
`schema`, `db`, `gatekinds`, `meta`, `layout`, `canonical`, `exitcodes`,
`cli`, `events`, `commitmsg`, `mcp`, `vocab` — are the twelve contracts
already measured in the two-producer run
(learnings-since-loopstrap.md §4.1: *12 contracts × 12 observations →
38 disagreements → 4 confirmed real*). Each already carries a clause
accounting (`stated` / `illustrative` / `inferred` counts) and a list of
exactly which PLAN.md ambiguities it resolved and how. **This is the
worklist.** `law`'s job in migration is to turn each of these twelve
regions into a named, ratified `#Contract` (§3) — not to re-derive the
decomposition, and not to re-read PLAN.md from scratch.

### 2.3 The replacement mechanism

| PLAN.md's shape | `law`'s replacement |
|:--|:--|
| Cited by line number (`PLAN.md lines 261–265`) | Cited by contract id (`C-WORKFLOW-CLI`) — a name that resolves by lookup, never by position |
| One file, unversioned, edited in place | One contract per seam, versioned by the append-only ratification ledger (§3); a contract's history is its amendment record, never an in-place edit |
| Coupling is bidirectional in effect (edit PLAN.md, 212 files go stale silently) | Coupling is one-directional by construction: mini-app code and tests cite law; **law never cites code, never cites a file path, never cites a line** |
| Holes recorded as `open` / `_` / `inferred` | Holes are a **named refusal** (a refusal table entry, generalizing `CONTRACT.md §Dispatch`'s style — id / refuses-when / expected–found–satisfy) or an **`unresolved:` entry** awaiting owner ratification |
| Ambiguities resolved once, by a contract author, unratified (`CONTRACT-NOTES.md`'s own "Ambiguities and choices" sections) | Every resolution the extraction step chose becomes an explicit ratification act, recorded by name (§5 step 2) |
| Ordering / phasing prose (§11, §13) | **Not law at all.** Sequencing is `wf`'s (loopstrap's) concern; if still needed it lives there, never re-enters `law` |
| Ratified decisions (§12) | Migrate to a decisions ledger — evidence of what was decided and why, distinct from the contracts themselves (learning-since-loopstrap.md §10.9's provenance discipline applies to decisions too) |

### 2.4 No section numbers — the known revert, avoided by construction

`0dca9ad` ("section numbers preserved") retired PLAN.md by splitting it
while keeping its numbering as the addressable unit; it was reverted 27
minutes later at `2d729d0`, root cause (owner's): *"wrote the process
and didn't follow it."* Two structural choices here exist specifically
because of that failure, not as taste:

1. **No construct in `law`'s schema has a numbered "section" as its
   addressable unit.** The addressable units are: a contract id
   (`C-[A-Z0-9-]+`), a clause id within it (`P-`/`G-`/`LI-`, per §3), or
   a global invariant id (`L-[0-9]+`). None of these can be produced by
   `sed`-ing a range out of a prose document — each is authored as a
   closed CUE field with its own grammar.
2. **Retirement is a managed pipeline, never a session's hand-edit**
   (§5). The revert is the disease in miniature: a correct *design*,
   executed as a hand-edit, with no dispatched record and no ratification
   checkpoint between steps. `law`'s migration sequence exists to make
   that failure structurally unavailable, not merely to remember not to
   repeat it.

---

## 3 · The looplaw shape, adapted

### 3.1 The trinity, mapped

| looplaw | `law` (this repo's dev lane) |
|:--|:--|
| **Lexicon** (meaning) | Every dev-lane mini-app's reserved terms, tiered `CANON \| REVIEW \| QUALIFY \| BANNED`. Absorbs and **generates** `AGENTS.md`'s vocabulary-wall allowlist (work order, gate, stage, receipt, red/green, chain, claim, marker, …) from one source instead of maintaining the wall's list and the sentence describing it by hand in two places — closing the self-referential gap learnings-since-loopstrap.md §8.1 names explicitly. |
| **Contracts** (behavior) | One `#Contract` per certified seam — the twelve extracted from PLAN.md (§2.2) plus `task`'s job/envelope/dispatch shapes, `harness`'s `#Context`/`#Dispatchable` (already looplaw-shaped — see 3.2), and eventually `telemetry`/`hooks`/`fixtures` as they earn a contract. |
| **Experience** (judgment) | Advisory-only precedent: *"a refusal table generalizes better than prose,"* *"line-number coupling into a prose doc is toxic; named-seam coupling is productive"* — cited to contracts, never binding on its own, never a backdoor for un-ratified law. |

### 3.2 The schema is not new — one already exists in-tree

`ops/devlane/harness/context.cue`'s `#Context` / `#Dispatchable` split is
already exactly looplaw-shaped: a closed observation shape, a stricter
law-shape refining it, `#DeclaredAbsent` for absence-that-must-be-said,
and a refusal doctrine baked into field names (`withheld_present`,
`given_unmet`). `contract-synthesis.md`'s `#Task` (`ops/devlane/task/`) is
the same pattern applied to job declarations, complete with a
closed-by-refusal table. **`law`'s core schema is these two patterns,
generalized and given one home**, not a third reinvention. Concretely,
`law` vendors an adapted copy of looplaw's own `schema/*.cue`
(`#TrinitySet`, `#Contract`, `#Provenance`, `#Gap`) into
`ops/devlane/law/schema/`, because looplaw currently ships no importable
library — only a CLI and internal Go packages
(`loopstack/organs/looplaw.md`: *"the importable-crate version… is
designed against a real consumer, not before"*). This is a vendored
copy with a stated reopening trigger (swap to a live dependency once
looplaw publishes one), not a permanent fork — the same "driver swap at
the edges, never a redesign" doctrine the family already applies to git
→ fugit (`loopstack/proj/stack.md`).

A dev-lane contract clause, in the vendored shape:

```cue
package law

// One certified seam. Same anatomy as looplaw's #Contract; "parties"
// here are dev-lane mini-apps, not runtime components.
#Contract: close({
	id:   #ContractID           // "^C-[A-Z0-9-]+$" — never a file path, never a line
	name: #NonEmpty
	parties: {
		client:   #PartyRef      // the mini-app that owes the preconditions
		supplier: #PartyRef      // the mini-app whose code owes the guarantees
	}
	preconditions: [ID=#ClauseID]: {text: #NonEmpty}
	guarantees:    [ID=#ClauseID]: {text: #NonEmpty, records: #NonEmpty}
	cites: [...#InvariantID]     // global invariants this contract binds under
	blame: [...{violation_class: #NonEmpty, at_fault: #PartyRef, evidence: #NonEmpty}]
	status: "proposed" | "ratified" | "corrected" | "withdrawn"
})
```

### 3.3 The three banned spellings — what replaces each

| banned | why (measured) | replacement |
|:--|:--|:--|
| `open` (an unclosed list/struct) | `[...#NonEmpty]` is satisfied by an absent field CUE infers as `[]`; asserts nothing about presence (learnings §1.4) | `[#NonEmpty, ...#NonEmpty]` where presence is required, or an explicit `#DeclaredAbsent` sentinel where absence is a *stated fact* |
| `_` (hidden field / free-form) | A hidden-field reference is one-directional, not an equality; reads as agreement, enforces nothing (§1.1) | A direct reference (`b: a`), or, where genuinely unconstrained content is intended, a `#RegionUnconstrained` sentinel that a relational gate flags for review rather than silently passing |
| `inferred` (a reading nobody ratified) | A single author assigns "inferred" to itself; no one ratifies it (`contract-synthesis.md` Part 3) | A `#Unresolved` sentinel — see below |

**`#DeclaredAbsent` vs. `#Unresolved` — two different facts, kept
separate** (this distinction generalizes learnings-since-loopstrap.md
§10.1 — absence must be *said*, and *why* it's absent matters):

```cue
// "There is nothing here, and this is a settled, ratified fact."
#DeclaredAbsent: close({declared_absent: #NonEmpty})

// "This needs the owner to rule, and here is the exact question." A
// contract may carry these at draft time; NONE may survive ratification
// — a CUE gate refuses a "ratified" status while any #Unresolved exists
// anywhere in the set.
#Unresolved: close({
	unresolved:   #NonEmpty  // the open question, stated
	opened:       #NonEmpty  // when it was raised
	escalated_to: "owner"    // always the owner; never a harness, never a role
})
```

A CI check enumerates every `#Unresolved` in the tree as a **standing
ratification backlog** — a to-do list of exactly what needs an owner
decision, never a silent default. This is the mechanical form of "hole-
closing IS ratification" (§5).

### 3.4 CUE for agreement, gates for earned-ness, receipts from day one

CUE proves that two closed shapes agree. It structurally cannot prove
that something ran, that a status is truthful, or that a receipt was
earned rather than fabricated (learnings §2.1, `cue-sys.md` §9). `law`
therefore ships three layers together from the first contract, not
gates-later:

1. **CUE (`cue vet`)** — shape agreement between a contract clause and
   an observation. Deterministic, offline, a pure function of its two
   inputs.
2. **Relational gates (Python)** — what CUE cannot express: closure
   (every reserved dev-lane verb/act appears in exactly one contract),
   citation resolution (every `cites` id exists), bijection where
   claimed, and — critically — **presence-before-inference**: a raw-JSON
   check that a field was actually *stated* in the observation, run
   *before* `cue vet`, because unification is comparison-and-default at
   once and a missing field can be silently filled from the contract
   side (learnings §1.5). `vet.py` already has exactly this pattern
   (`MUST_BE_STATED`); `law` generalizes it into one shared check
   (`law/checks/presence.py`) instead of one ad hoc version per
   contract.
3. **Receipts** — a record that a `cue vet` run actually executed, over
   which frozen packet, with which verdict, stamped to the commit it is
   true of. Shape follows looplaw's `#Provenance` (`scope`, `sources`
   keyed by content hash, `derivations`) plus a vet-log entry
   (`packet_hash`, `verdict`, `checked_at`, `commit`). This is the
   mechanism that answers *"was this actually earned"* — a contract can
   pin the shape of a receipt; only a receipt, produced by a run that
   actually happened, proves the receipt was earned
   (`contract-synthesis.md` Part 3).

### 3.5 Attack corpus — reuse the shape, seed from what's already found

`law`'s attack corpus is a direct copy of looplaw's own index shape
(`internal/gate/testdata/attacks/index.cue`):

```cue
#Attack: {
	file:      string
	found_in:  string          // which contract / review round produced it
	must_draw: [string, ...string]  // refusal id(s) the attack must draw
}
```

Seeded on day one from work this project has already done, not
re-derived: `model-pinned-in-job.cue` → `must_draw: "a job never names a
model"`; `scope-to-scopeless.cue` → `must_draw: "scope-cap"` (both
already exist as worked examples in `contract-synthesis.md` Part 1(d)).
Every contract ships with **both** a positive control (vets clean, built
only from ratified scope) and at least one negative attack (must vet
red, must draw the named refusal) before it may reach `status: ratified`
— a contract with only a clean-case check is worse than no contract
(learnings §4.3, §6.3, measured three separate times in this project's
own record). **Bounded law**: each contract carries a stated max-clause
budget so it stays readable and fully verifiable in one sitting, never
sampled (learnings §3.4).

---

## 4 · How it certifies the mini-apps

### 4.1 The two-producer firewall, proven blind — not promised blind

Two producers meet only at `cue vet`, and neither may see the other's
source:

- **contract-from-intent** — drafts the `#Contract` from scope/prose
  only (this design doc, a mini-app's own README, an owner conversation)
  — no code in sight.
- **observation-from-code** — an extractor reads the mini-app's actual
  files and emits, mechanically, what is *actually* declared — never
  imports the contract.

The firewall must be **mechanically proven**, not assumed: an empty or
mis-scoped snapshot that withholds the wrong side looks identical to one
that withheld correctly (learnings §4.2, measured: staging four roles by
hand once firewalled one side wrongly, undetected until checked). `law`
reuses the machinery `harness`/`stage.py` already built and proved for
exactly this problem rather than re-solving it: each producer is
dispatched against a **staged snapshot** built from an explicit
`given`/`withheld` manifest, proved in *both* directions before
dispatch — `proof.withheld_present` empty (nothing that should be
excluded got in) **and** `proof.given_unmet` empty (nothing that should
be included is missing; an empty snapshot must not trivially pass). The
contract-drafter's snapshot withholds the code; the extractor's snapshot
withholds the contract draft and this document. Both dispatches are
recorded (per `CONTRACT.md §Dispatch`'s record shape), so the firewall
is auditable after the fact, not merely trusted at design time.

### 4.2 `cue vet` as the comparator, over a frozen packet

Both producers' outputs are hashed and pinned *before* comparison — a
**frozen packet** — so re-vetting later reproduces the identical
verdict (equilibrium requires this: a stale certification is a
"confident lie" that nothing announces on its own). A disagreement
(`cue vet`'s own structured output — e.g. `facts.commands: incompatible
list lengths (16 and 17)`, the measured real defect in `wf.py`'s CLI
verb count) goes to a **third party**, never one of the two producers:
an adjudicator rules "code is wrong" (fix it) or "contract is wrong"
(revise and re-ratify) — never silently reconciled by either side that
produced the disagreement.

### 4.3 Receipts and equilibrium — four properties, non-negotiable

A commit that breaks a previously-certified edge and nothing announces
it is exactly the failure mode `law` exists to close. Every certified
edge's receipt must:

| property | means |
|:--|:--|
| **materialize & persist** | never recompute-and-discard; a receipt is a row, not a cache |
| **sync incrementally** | re-vetted on every commit that touches either side of the edge, not on a schedule |
| **stamp commit-state** | every receipt names the exact commit it is true of — a fact detached from its commit is unfalsifiable |
| **expose read-only, lane-scoped** | a `law`-specific MCP (or CLI-only, if an MCP is deferred — see §6), **never the same server instance as `wf`'s MCP** — the lane boundary is enforced by which server an agent is handed, not by convention (learnings §8.2) |

### 4.4 The CI gate — enumerated refusal conditions

CI refuses merge on **any** of:

| condition | why it's fatal, not advisory |
|:--|:--|
| a contract clause with no certified edge | a "hole" — a node pretending to have an edge; the verification collapse breaks exactly here (learnings §5.4) |
| a certified edge stale against `HEAD` | a confident lie nothing announces on its own |
| an attack in the corpus that fails to draw its `must_draw` id | a checker that only passes the clean case is worse than no checker |
| a positive control that fails to vet clean | proves the contract can fire *and* stay quiet — only one half is not enough |
| a `#Unresolved` present anywhere in a set marked `ratified` | "inferred" wearing a ratified label |
| a banned-tier lexicon term used outside its allowed surface | the lexicon wall, mechanically enforced rather than remembered |
| dev-lane vocabulary (or `law`'s own new vocabulary — contract, lexicon, ratify, gap, trinity) leaking into a the House product design artifact | the existing wall, extended to cover `law`'s new surface explicitly (learnings §8.1) |
| a tracked file matching a `PLAN.md`-line-number citation pattern, post-cutover | prevents the disease from quietly regrowing after retirement (§5) |

Diagnostics (a Serena-style surfaced warning, or a `wf`-adjacent read
projection) may warn earlier in the loop — while drafting, while
coding — but **only CI's refusal is enforcement**; a diagnostic never
becomes a second authority (learnings §5.3).

### 4.5 Producer independence — a bound, stated, not assumed

With three harnesses and a finite budget, someone will sometimes fill
two roles. Default to a **fresh, uninvolved producer per role**
wherever affordable — drafter ≠ extractor ≠ adjudicator ≠ implementer —
and where the compromise is unavoidable, **record the overlap
explicitly** as a scarcity artifact rather than let it drift in by
convenience (learnings §10.4). The one hard rule: the **same
person/harness never fills two roles on one contract's own
certification** — a producer never adjudicates its own escalation.

---

## 5 · The migration off PLAN.md

A managed, ratification-gated pipeline — never a session's hand-edit.
Each step names what it needs from the owner; steps marked
**[RATIFY]** cannot proceed on inference or silence.

| step | what happens | gate |
|:--|:--|:--|
| **0** | Owner ratifies this document's core decisions: `law`'s name/location, the trinity adaptation, the banned-spellings rule as CI-enforced (not just doctrine), the vocabulary-wall extension. | **[RATIFY]** — this is the ratification this document exists to seek |
| **1** | Draft one closed `#Contract` per PLAN.md region already decomposed in `CONTRACT-NOTES.md`/`EXTRACTION-NOTES.md` (§2.2's twelve), each as its own dispatched job with its own record — never a batch hand-edit. Every PLAN.md ambiguity the extraction already resolved becomes a named clause or an explicit `#Unresolved`. | mechanical dispatch, one record per contract |
| **2** | Owner ratifies each drafted contract (accept / revise / reject), one at a time. Every hole PLAN.md left unstated that this step closes is itself a ratification act, recorded by name. | **[RATIFY]**, per contract — "hole-closing IS ratification" |
| **3** | Re-point every current citer of `PLAN.md lines N–M` (the ~1,340 across 239 files: `CONTRACT-NOTES.md`, `EXTRACTION-NOTES.md`, `vet.py`, `cli.cue`, and any test that names a line) to the matching contract id. | mechanical; a gate scans for the line-citation pattern and refuses if any remain after this step closes |
| **4** | Discharge PLAN.md's non-semantic remainder: §12 (ratified decisions) → the decisions ledger (evidence, not law); §11/§13 (ordering/phasing) → `wf`'s own planning surface if still needed, else retired as historically complete; illustrative/sketch blocks → either ratified into a contract clause or marked explicitly superseded. | **[RATIFY]** on where each block lands — nothing discharged silently |
| **5** | Switch the comparator off `PLAN.md`: `vet.py`'s literal `../PLAN.md` bind (line 852, not a `PLAN_ARTIFACT` constant — a prior claim this document corrects) is replaced with a reference to the ratified contract set, not a new single-file constant pointing somewhere else. | mechanical, tested against the frozen packet from step 1–2 |
| **6** | Owner ratifies cutover completeness: zero remaining PLAN.md citations, every contract has a certified edge, the attack corpus is green, every positive control vets clean. | **[RATIFY]** — the checklist gate |
| **7** | Delete `PLAN.md`. One dispatched, recorded, single-purpose commit. Never a side effect of an editing session — the exact discipline whose absence caused the 27-minute revert (`0dca9ad` → `2d729d0`). | mechanical, but only reachable after step 6 |

No step downstream of an unratified **[RATIFY]** step may begin. This
is the structural fix for *"wrote the process and didn't follow it"* —
the pipeline enforces the order; nobody has to remember it.

---

## 6 · Open questions for the owner

Crisp, because these are the owner's decisions, not this document's:

1. **Name and vocabulary-wall status.** Is `law` (`ops/devlane/law/`)
   ratified as the name/location? And: does `law`'s own vocabulary
   (contract, lexicon, ratify, gap, trinity, experience) get added to
   the dev-lane vocabulary wall as dev-lane-only, or is some of it meant
   to eventually reach the House product-proper's own specs (`contract-
   synthesis.md` Part 4 point 2 suggests the same method should
   certify the House product itself, later)?
2. **Scope boundary, now vs. later.** Does `law` certify *only* the
   current dev-lane mini-apps (`task`, `harness`, `workflow`,
   `telemetry`, `hooks`, `fixtures`) to start, or does it also need to
   hold the House product-proper's own architecture contracts from day one? These
   are different urgency levels and possibly different lexicons.
3. **Stack commitment: Python-and-shelled-`cue`, or a Go kernel like
   looplaw's own.** The dev lane already has a proven pattern
   (`vet.py`) doing exactly this work for twelve contracts; this
   document recommends extending it rather than introducing a second
   toolchain, but the fork is real and worth an explicit ratification
   rather than a default nobody chose.
4. **Where PLAN.md's non-semantic remainder lands.** A new decisions
   ledger inside `law`, or `wf`'s existing chain/receipt mechanism? Who
   owns that ledger's schema going forward?
5. **Producer-segregation bar.** With three harnesses and a finite
   budget, which contracts get true four-role segregation (drafter /
   extractor / adjudicator / implementer, all different) from day one,
   and which are allowed the two-role compromise, explicitly recorded?
   The owner sets the bar; it should not drift in by convenience.
6. **Authority timing (Cedar-equivalent).** Looplaw defers "who may
   ratify/amend" to a later Cedar layer, running a hardcoded single-
   owner check meanwhile. Does `law` need even that hardcoded check built
   now, or is "the owner is the only party who can flip `status:
   ratified`" enough as a convention until more than one accountable
   party exists?
7. **Receipt store and MCP.** A new table in `wf`'s existing sqlite
   store, or a dedicated store for `law` (mirroring looplaw's own
   separate kernel)? This decides whether the lane-partition rule
   (§4.3) is satisfied by one server with two schemas or genuinely two
   servers.

---

## Sources

Read in full or in the cited section for this design:
`.dev/xor/out/learnings-since-loopstrap.md` (57 entries, cited by
section throughout); `.dev/xor/out/contract-synthesis.md`;
`.dev/xor/out/countract-2/two-contracts-aligning.md`;
`.dev/xor/out/cue-sys.md`; `ops/devlane/workflow/contracts/CONTRACT-NOTES.md`;
`ops/devlane/workflow/PLAN.md` (headers only); `ops/devlane/harness/context.cue`;
`git show task/dispatch-contract:ops/devlane/task/CONTRACT.md`;
`github.com/xormania/looplaw/schema/{trinity,gap,components}.cue`;
`github.com/xormania/looplaw/proj/looplaw-spec.md`;
`github.com/xormania/looplaw/internal/gate/{trinity,ratification}.go`;
`github.com/xormania/looplaw/internal/gate/testdata/attacks/index.cue`;
`github.com/xormania/looplaw/dev/registry.cue`;
loopstack's `{registry,boundaries}.md`, `organs/looplaw.md` and
`proj/stack.md` (operator-local at the time of writing; no public
repository resolves, so they cannot be re-read from this tree);
`AGENTS.md` (this repo).
