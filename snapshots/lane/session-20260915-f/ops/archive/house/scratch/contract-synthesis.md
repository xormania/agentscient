---
name: contract-synthesis
description: One method that unifies the proven ideas against the PLAN-as-contract disease — a CUE #Task contract over jobs.json, worked end to end, plus the data behind it, the insights, and where to point it next.
covers:
  - ops/devlane/task/jobs.json
  - ops/devlane/task/CONTRACT.md
  - ops/devlane/harness/context.cue
  - ops/devlane/workflow/contracts/
---

# The combined method — a contract that is a shape, ratified, and held against code

A **sketch and a record, not a spec.** The owner holds design authority;
this exists to be cited, argued with, and cut down. Its target is the
recurring disease and the several proven cures we keep re-discovering
separately.

**The disease, stated once.** A Fable-authored `PLAN.md` used *as if it
were a contract*. It is verified in the tree: `CONTRACT-NOTES.md` opens
with "`PLAN.md` is the only authority for semantic values," and every
constraint in `cli.cue` carries a `// PLAN.md SS4 lines 261-265`
citation. Its holes are recorded as `open`, `_`, and `inferred`. It
couples 212 files to it by *line number*. An attempt to retire it by
hand (0dca9ad, "section numbers preserved") was reverted 27 minutes
later (2d729d0); root cause, the owner's: *"wrote the process and didn't
follow it."* The standing lesson: **you manage a pipeline, you don't do
the work by hand.**

The cures already exist in the tree, unassembled: closed CUE shapes
(`context.cue`), closed-by-refusal prose (`CONTRACT.md §Dispatch`),
two-producer certification (the `workflow/contracts` run), a
ratified-artifact gate (3e4e6d8, the contract landing before its
launcher). This joins them into one method and works it on the smallest
real target that exercises all of it at once.

---

## PART 1 — the artifact, on the smallest real target

**Target: a CUE `#Task` over `ops/devlane/task/jobs.json`.** `jobs.json`
declares the delegated units — `verify`, `adversarial-review`,
`author-tests`, `sweep`, and (on the dispatch branch) `plan`,
`check-tests`, `implement`, `adjudicate`. `#Task` is the reusable atom:
certify it once, and every job that unifies with it is certified. That
is the whole reason to start here rather than at the workflow.

### (a) A closed shape — grammar, closure, absence said

```cue
package task

// A malformed name is refused by SHAPE, not by a downstream checker.
#JobName:  =~"^[a-z][a-z0-9-]*$"            // "author-tests", never "" or "AuthorTests"
#Adapter:  "direct" | "harness" | "stub"    // closed enum: a fourth adapter does not evaluate
#Role:     "read" | "write"
#Snapshot: "whole" | "fileset"
#NonEmpty: string & =~"[^[:space:]]"        // trimmed non-empty, per looplaw's #Text

// Absence has to be SAID. An omitted constraints list and an empty one
// mean different things — "nobody stated any" vs "we state there are
// none" — and a schema that accepts a missing field turns the first
// into the second silently.
#DeclaredAbsent: close({declared_absent: #NonEmpty})

// #Task is the SHAPE of a declared job. It is closed: a field nobody
// agreed to cannot be added to smuggle policy past the definition.
#Task: close({
	name:        #JobName
	adapter:     #Adapter
	deliverable: #NonEmpty
	constraints: [#NonEmpty, ...#NonEmpty] | #DeclaredAbsent

	// Fixed for a harness job, declared-absent for a direct one. The
	// pairing is said, not implied.
	role:     #Role     | #DeclaredAbsent
	snapshot: #Snapshot | #DeclaredAbsent
	prompt:   #NonEmpty | null       // null only where the work is mechanical

	// The holes the prompt template declares. A dispatch that fills a
	// hole the template does not name, or a template naming a value the
	// launcher cannot supply, is refused before any brief exists.
	fills: [...#TemplateVar]

	// Self-certification, carried on the task itself — see (b).
	fault: #FaultBinding
})
```

Extra field → `field not allowed`. Missing required field → does not
evaluate. Malformed name → fails the grammar. This is `context.cue`'s
argument (`#Context`/`#Dispatchable`) applied to the job table:
`extra → not in the definition → does not evaluate`.

### (b) Closed-by-refusal — the underspecified region is refused *by name*

The two legal adapter couplings are closed refinements — the `#Context`
vs `#Dispatchable` split, reused. Everything else is a type error:

```cue
// A harness job runs a model under a role inside a proven snapshot.
#HarnessJob: #Task & {
	adapter: "harness", role: #Role, snapshot: #Snapshot, prompt: #NonEmpty
}
// A direct job is mechanical: the caller's own fileset, no role.
#DirectJob: #Task & {
	adapter: "direct", role: #DeclaredAbsent, snapshot: #DeclaredAbsent, prompt: null
}
#Job: #HarnessJob | #DirectJob
```

CUE proves *shape agreement*. The **named refusal with its text** lives
in the launcher — and this is real, `CONTRACT.md §Dispatch`'s refusal
table, prose enforced by tests, not `open`/`_`/`inferred`:

| id | refuses when | expected / found / satisfy |
|:--|:--|:--|
| `mode-unavailable` | job declares `fileset`, which the launcher cannot yet mint | *expected `whole`; found `fileset` on `<job>`; stage it by hand with `stage.py` and name the dispatch in the PR body until fileset lands* |
| `scope-cap` | `--scope` given to a job whose template has no `{scope}` | *expected ≤1024 bytes on a job that takes a scope; found a scope on `<job>`, which takes none; drop it — a scope that needs more is a brief, and briefs are derived* |
| `history-vs-withheld` | a job declares both `withheld` and `whole` | *expected one of history or withholding; found both on `<job>`; a withheld file is recoverable from `.git`, so declare `fileset`* |

An underspecified region becomes a *named* refusal carrying
expected/found/satisfy — never a hole marked `inferred`. `fileset` isn't
absent-and-forgotten; it is **refused, with the recovery printed.**

> **One correction the tree forces on this sketch.** The session brief
> had the runtime — harness, model, effort — living *in the task*. The
> code says the opposite, and the code is right: `jobs.json` fixes
> `role`, `deliverable`, `constraints`, `snapshot`, `prompt`, and *never*
> a model; `--harness --model --effort` are the owner's dial at the
> **call**. That is deliberate — *"a job never names a model… which is
> what makes 'eight cheap ones' and 'one careful one' the same job."*
> So what the task **fixes-and-certifies** is the deliverable shape, the
> role, the constraints, the snapshot mode, and the fault-binding; the
> model is a dial the certification is *invariant to*. Swapping it at the
> call is not an uncertified no-op — it is the permitted dial. What *is*
> refused-by-name is a call that changes what the task fixed (`scope-cap`,
> `history-vs-withheld` above). **This disagreement is not mine to
> settle** — it is exactly the contract-vs-code kind that part (d) exists
> to drive to the owner, and it is worth recording that the method caught
> it on its own first target.

### (c) Contract-first — the owner ratifies the reading of intent before code exists

The flow, and it already has a precedent in this tree (3e4e6d8, *"the
dispatch contract lands before the launcher that must satisfy it… the
implementer must not be the one who writes the contract rows"*):

```
scope  ──▶  drafter writes #Task  ──▶  review  ──▶  OWNER RATIFIES  ──▶  jobs.json + run.py
(prose)     (from scope only,          (holes                            are MADE to
             no code in sight)          named)      │                    satisfy #Task
                                                     ▼
                                              DECISIONS.md
                                     (every ratified reading, byproduct)
```

The owner ratifies the **reading of intent**, not the implementation.
Nothing is `inferred`: an unresolved reading is either ratified into
`DECISIONS.md` or refused by name in the contract. Compare the disease,
where `inferred` is a *valid* value that a single author assigned to
itself with no one ratifying it.

### (d) Two-producer certification — break the circularity of judging code by a contract drawn from that code

Two producers who cannot quietly reconcile, meeting at a shape neither
owns:

- **contract-from-intent** — the drafter's `#Task`, from scope, no code.
- **observation-from-code** — an extractor reads `jobs.json` + `run.py`
  and emits, mechanically, what each job *actually* declares. It never
  imports the contract.

```
#Task (intent) ─┐
                ├─▶  cue vet -d '#Task' task.cue  observed.json  ─▶  disagreements ─▶ owner
observed.json ──┘        (against a FROZEN packet)                    (re-validated
 (from code)                                                          against the same
                                                                      frozen packet)
```

Grounded in the measured run (`cue-sys.md`): **12 contracts × 12
observations → 38 disagreements, 4 confirmed real** — among them `wf.py`
declaring **17** CLI verbs where the spec documents 16 (`agents`), and
exit codes `[0,1,2,3,64,70]` where the spec states `{0,1,2,3,64}`. A
`cue vet` line *is* the adjudication packet:

```
facts.commands: incompatible list lengths (16 and 17)
```

Every contract must also **fire and stay quiet**. A **positive control**
built only from scope must vet green; an **attack corpus** of mutations
must each vet RED, each binding the constraint it must draw, permanent,
looped until dry:

```cue
// attacks/model-pinned-in-job.cue  — a job that names a model
job: {name: "review", adapter: "harness", model: "opus-4.8", /* … */}
must_draw: "a job never names a model; the runtime is the caller's dial"

// attacks/scope-to-scopeless.cue    — scope handed to a {scope}-free template
dispatch: {job: "adjudicate", scope: "aim at the parser"}   // adjudicate takes no {scope}
must_draw: "scope-cap"
```

Further attacks in the same corpus: `attacks/unpinned-follows.cue` (a
`follows` edge that is not a record id), `attacks/ran-not-from-stream.cue`
(`model.ran` copied from the requested alias instead of read from the
harness's own session stream). The measured first round: **66 faults →
20 fired, 40 rejected at an unpredicted path, 6 accepted (real holes).**
Disagreements are driven to **0 or terminated-with-recorded-cost, and
held** as the code moves.

### Bounded, and productively coupled

- **Bounded law.** A gate-budget / max-invariants cap keeps the law small
  enough to be *fully* verified rather than sampled. A contract you cannot
  read in one sitting cannot be certified whole, and a law that is not
  certified whole has lost the property that makes it worth having (Part 3).
  *(gate-budget: session record; not yet a tree mechanism.)*
- **Productive coupling.** `#Task` cites **closed `#Definition` seams**,
  versioned, one-directional — `#HarnessJob refines #Task`, never
  `run.py:412`. The seam can move; the citation still resolves.
  **Contrast the disease:** `cli.cue`'s every line names `PLAN.md lines
  261-265`, so editing `PLAN.md` silently invalidates 212 files and no
  checker notices. Line numbers are the toxic coupling; named closed
  seams are the productive one.

---

## PART 2 — data recorded

Verified against the tree where cheap; session-record items labelled.

| fact | value | status |
|:--|:--|:--|
| `PLAN.md` used as contract | `CONTRACT-NOTES.md`: "PLAN.md is the only authority for semantic values" | **verified** (read) |
| line-number coupling | `cli.cue` tags every constraint `// PLAN.md SS4 lines NNN-NNN` | **verified** (read) |
| coupling breadth | 1,339 citations / 238 files (session record) — my counts: **212 files** reference `PLAN.md`, **≥1,260** line-range citations under `contracts/` | corroborated in magnitude |
| holes recorded as | `open` / `_` / `inferred` throughout `CONTRACT-NOTES.md` | **verified** (read) |
| retire-by-hand → revert | 0dca9ad ("section numbers preserved," left references + file present) → 2d729d0 | **verified** (both commits) |
| time to revert | ~31 min (session record) — commit timestamps are **27m 35s** apart | corroborated |
| root cause | "wrote the process and didn't follow it" | session record |
| `vet.py` still binds `PLAN.md` | no `PLAN_ARTIFACT` constant at line 116; `plan_abs = ../PLAN.md` at **line 852**, §9-whole-plan at line 810 | **verified** — substance holds, "116/PLAN_ARTIFACT" does not |
| §Dispatch closed-by-refusal | `CONTRACT.md`, **463 lines**, commit **3e4e6d8** | **verified** (both) |
| two-producer | 12 contracts × 12 observations → **38** disagreements → **4** real | **verified** (cue-sys.md §2) |
| a real disagreement | `wf.py` declares **17** verbs vs the spec's **16** (`agents`); exit codes `[0,1,2,3,64,70]` vs `{0,1,2,3,64}` | **verified** (cue-sys.md) |
| fault corpus | **66** faults → 20 fired / 40 unpredicted-path / **6** real holes | **verified** (cue-sys.md §8) |
| CUE footprint | **13** `.cue` files (`#Context` + 12 workflow contracts); `cue-sys.md` = **12 sections**; §9 = the earned-ness limit | **verified** |
| ratified / frozen-packet / gate-budget | `ratified` is a live status in `trinity.cue`; frozen adjudication packets exist under `contracts/adjudicated/packets/`; gate-budget is a concept only | mixed — labelled inline |

---

## PART 3 — insights

**Plans and contracts are different KINDS.** A plan says *how, in what
order*. A contract says *what must be true*. `PLAN.md` is the category
error made physical: a document of ordered intent, cited as if it were a
law of shape. The `1,339` line citations are the symptom — you can only
cite a plan by *position* because it has no *named, closed* claims to
cite.

**The verification collapse — and how one hole breaks it.** A contract
that is *whole* and *verified* lets you verify the **law once** instead
of the **implementation forever**: prove the law self-consistent, prove
code agrees by `cue vet`, done. But **a single unenforced hole breaks
the collapse right there.** Every `inferred`, every `open`, every `_` in
`CONTRACT-NOTES.md` is a point where "certified whole" silently becomes
"certified except here" — and a reader who trusts the green has no way to
see the exception. This is why bounded law (Part 1) is load-bearing and
why `inferred` is banned, not discouraged.

**The law is a GRAPH driven to EQUILIBRIUM.** Contract, code, extractor,
attacks, positive control — nodes; `cue vet` — the edges. Gaps are driven
to **0 or terminated-with-recorded-cost**, and the equilibrium is
**held** as the code moves. `38 → 4 → 0` is one pass; the corpus loops
until dry and stays wired in, so drift re-draws red.

**Two coupling regimes.** Productive: closed seams, versioned,
one-directional — the seam moves and the citation still resolves. Toxic:
line numbers — the target moves and 212 files are silently wrong.

**The two halves are different problems.** Getting *intent → contract*
right is the **ratified-artifact / no-inferred** half. Getting
*contract vs code* right is the **two-producer firewall**, which exists
to break a specific circularity: you cannot judge code by a contract
*derived from that code*. Both halves are needed; the tree has each
once, never together.

**CUE proves agreement; gates prove earned-ness.** CUE's one structural
limit (`cue-sys.md §9`): it proves two closed shapes agree; it cannot
prove *earned-ness* — that something ran, that a status is truthful, that
a role saw only what it was entitled to. Those need receipts and gates.
*"A contract can pin the shape of a receipt; it cannot pin that the
receipt was earned."* Design to the split: CUE for agreement, gates for
behaviour.

**The recurring failure is the executive doing the work by hand.** The
revert (0dca9ad → 2d729d0) is the disease in miniature: the retirement
was correct as a *design* and fatal as a *hand-edit*. The fix is to
**manage a pipeline and keep durable records** — context custody — so
the reading survives the session that produced it.

---

## PART 4 — where to point it

**1. Retire `PLAN.md`, correctly, as a managed pipeline.** Not by hand —
that is what got reverted. In order: (i) draft a *closed* workflow
`CONTRACT.md` by this method and have the owner ratify it; (ii) switch
`vet.py` off `PLAN.md` (the real bind is `../PLAN.md` at line 852, not a
`PLAN_ARTIFACT` at 116); (iii) re-point the citations from line numbers
to **named closed seams**; (iv) discharge the decision and appendix
sections into `DECISIONS.md`; (v) *then* delete. Every step a dispatched
job with a record, not a session's hand-edit.

**2. Build the House product itself this way.** Its prose architecture scope
becomes enforceable law by the same flow: a drafter writes the contract
from scope, the **owner ratifies**, the server is built to satisfy it.
This is how *"a context-custody certifier with insane quality
requirements"* gets built agentically — the quality bar is the contract,
and the contract is certified whole before a line of server exists.

**3. Formalize the task/workflow split.** The **task** is the CUE atom:
it fixes what is certified (deliverable, role, constraints, snapshot
mode, fault-binding) and self-certifies against its planted fault; the
runtime is the owner's call-time dial. The **workflow** is a CUE shape
*plus* gate-enforced ordering and firewall relations (plan → tests →
check-tests → code → review → adjudicate; the two-producer firewall).
Certify the atom once; reuse it certified everywhere it unifies.

**4. Any app's self-contract.** The method is not workflow-specific. Any
mini-app with a prose scope and a test suite can draft → ratify → extract
→ vet → attack, and hold its own law at equilibrium against its own code.

---

*The owner's frame, kept: "I do as much as I can and let the contracts
and the equilibrium fill in the pieces." This record is the contract for
the contracts — draft, ratified by no one yet, holes named rather than
hidden.*
