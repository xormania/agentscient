# Agentscient over MCP — the kernel, and what it serves first

Plan for the tree at `af3ff012017b0f2a5994f0cfbab15cc541186cd9`, from the
owner's scope of 2026-08-29: *"start with delegating Fable to research
how we can use this Agentscient framework with MCP for coordinating
agents and getting them diagnostic data sooner than later"*, then
*"frame work first"*. Research, no code. Inputs: the running list
(`agentscient-mcp-tools.md`) and `conducting.md`. Everything below was
read from the snapshot; nothing was executed. Ends in a unit list for
the owner to ratify (§6). Serena and prod-lane code are out of scope.

---

## 0. The claim in one paragraph

The dev lane already contains one proven instance of every kernel part
the scope names, but each exists once, inside `workflow`, and nothing
generalises it. `mcp_server.py` proves a read-only surface by import
graph — for itself only, by a test that names `wf`, `gitio`, `receipts`
as the forbidden set (`workflow/tests/test_mcp_server.py:141`).
`imports.json` is a registry of apps and edges — but it knows nothing
about which module of an app is its query layer. `jobs.json` is a
service catalogue — for the launcher only. The minimum kernel is not a
new abstraction; it is those three files taught to describe every app
the same way, plus one thin server that reads the description instead
of importing apps by name. The conductor's first diagnostic and
coordination needs (§4) are then a handful of query functions over
`.dev/records/dispatches/` and the jobs root, which the launcher today
carries only as a write path.

---

## 1. What exists, measured against the four kernel parts

| kernel part (scope) | exists today | where | what is missing |
|:--|:--|:--|:--|
| app registry | partial | `ops/contracts/imports.json` — 7 apps, `may_import` only | no `query` entry, no `serves`, no `stores`, no `append` declaration per app |
| allowed-import graph as CUE contract + gate | gate yes, CUE no | `ops/contracts/imports.py` (AST + path-literal + loader-call edges; INVALID never 0); `workflow/contracts/cue/mcp.cue` `server_imports?: [...(string & !="gitio" & !="chain")]` | the CUE form is optional (`?`) and the server *does* import `chain` (`mcp_server.py:43`) — the very hole `imports.py`'s docstring records. The read-only property is proved by a unittest, not by the contract |
| query/append split | `workflow` only | `query.py` ("everything that reads and nothing that writes"); `ReadOnlyContext`/`ReadOnlyChain` remove `append` from reach | `dispatch` has no split: `launch.py` holds `_status` (read, l.641) beside `_write_record`/`_commit_record`; `telemetry/pulse.py` is read-only by nature but undeclared; `task` reads `jobs.json` inside `run.py` |
| `jobs.json` as service definitions | yes, for the launcher | 8 jobs: adapter, deliverable, role, snapshot mode, prompt, constraints | no `research` job (running list #10; `conducting.md` §2 "it has no job in jobs.json yet"); no way for a surface to *list* jobs; W items on the running list have no job entries |

Two facts that shape the design:

- **Reading never needs an identity; recording always does**
  (`AGENTS.md` §Finding out where things stand). The wf server has no
  write tool "and there will not be one". The kernel inherits this
  verbatim: every MCP tool is a read; every append is a launcher
  invocation (`conducting.md` §1: "there is no other way a transition
  happens legitimately").
- **The conductor cannot use what it builds** (`AGENTS.md`: "no change
  that edits `ops/devlane/` may also record a work order"). So the kernel
  is proved E2E against a fixture repository with synthetic records
  and job directories (`fixtures/stores.py` is the existing pattern
  for synthetic session stores), never against the live lineage.

---

## 2. The minimum kernel

Four pieces. Each is the generalisation of one thing that already
works, and each is landable alone.

### 2.1 The registry — one row per app, and what a row says

Extend the existing declaration rather than add a second one; two
registries drift (`mini-app-lessons.md` §8 "write it where the next
reader will look"). Per app, in addition to `may_import`:

```
query:   "ops/devlane/<app>/query.py"     # the read layer; absent = "no surface" (a declaration, not a default)
append:  [modules that can write]      # e.g. workflow: ["wf","gitio","receipts","chain"]; dispatch: ["launch"]
stores:  [paths the query layer reads] # e.g. dispatch: [".dev/records/dispatches", "$DISPATCH_JOBS"]
serves:  [resource names]              # e.g. dispatch: ["board","record","running"]
```

`query: null` must be stated, not omitted (`AGENTS.md` §Absent is not
none — "`withheld: []` is a declaration; an absent key is refused").

Format: the owner asked for a CUE contract. Recommendation: keep
`imports.json` as the data the gate reads (`imports.py` already parses
it; `cue vet` can validate JSON against a `.cue` schema without a
second file), and add `ops/contracts/registry.cue` as the closed shape
it must satisfy. That follows the ratified 2026-08-27 architecture
("per-app CUE contracts … one unified relational CUE layer … own
composition and cross-app invariants") and the workflow contracts'
existing shape (`cue/` + `examples/` + `faults/` with `must_draw`).

### 2.2 The gate — read-only by import graph, for every registered app

`imports.py` today answers "may app A reference app B". The kernel adds
one more question it can answer with the same AST walk: **is any
module in `append` reachable from `query`, transitively?** That is
`test_mcp_server.ReadOnlyByConstruction` lifted out of a unittest and
into the registered check, parameterised by the registry, with the
negative control the lane requires (a fault fixture whose `query.py`
imports its app's append module must draw the refusal;
`AGENTS.md` §A check must fire, and it must stay quiet).

One correction this forces, worth stating before it is found by a
reviewer: `workflow`'s `query.py` imports `chain` (`query.py:19`), and
`chain.Chain` carries `append`. The wf server neutralises that at the
object level (`ReadOnlyChain`), not the import level. The gate must
therefore accept *either* "append module unreachable" *or* "the
context type hands out no appending object" — or the workflow app
splits `chain` into project/verify vs append. Recommend the split
(decision D3, §5); until then the gate records the object-level proof
as the workflow row's stated exception, never as a silent pass.

### 2.3 The server — one process, no app imported by name

A stdlib JSON-RPC/stdio server in the shape of `mcp_server.py`
(`handle`/`serve`/`resources`/`TOOLS`, canonical JSON bodies, refusals
returned as `isError` results). Differences:

- On start it reads the registry, loads each app's `query` module by
  the declared path (`importlib` from a registry value, not a literal
  — so `imports.py` sees no edge, which is why the registry, not the
  code, is where the kernel's edges are declared; the gate checks the
  kernel imports nothing under `ops/devlane/` except via the registry).
- Resource URIs are namespaced by app: `wf://…` stays as is;
  `dispatch://board`, `dispatch://record/<id>`, `dispatch://running`.
  A kernel-level `agentscient://apps` lists the registry, and
  `agentscient://jobs` serves `jobs.json` (the service catalogue,
  read).
- Tool names are `<app>_<resource>`, matching `wf_status` etc. The
  2026-08-21 decision "a tools/list size cap guards the schema
  surface" applies; the cap is a registry-level invariant.
- Each app's query module exposes one conventional entry,
  `resources(ctx)` → `[{name, body(args)}]`, and one `context(root)`
  constructor that opens only read handles. The wf pattern
  (`ReadOnlyContext.require_cache`) becomes the convention: an app
  whose store is not ready refuses with the command that readies it.
- Launch: `mcp_launch.py`'s prepare-then-`execv` split stays the
  kernel's launcher; `.mcp.json` points at the kernel; wf becomes the
  first registered app rather than the only server. This resolves
  D2 (§5) the way the 2026-08-21 decision already did for telemetry:
  "join the EXISTING wf server".

### 2.4 `jobs.json` as service definitions

The W items on the running list (#7 `measure`, #8 `land`, #9 `pr.post`,
#12 `owner.ask`, #13 `decision.record`, `group.cut`) are exactly what
the scope calls services: things that append, executed only through
the launcher, leaving a record. They do not become MCP tools. They
become **job entries** — deliverable, role, constraints, and the
record shape they leave — and the surface *lists* them
(`agentscient://jobs`) so that any harness can see what can be asked
for and `launch.preflight` can check an invocation before spend.
The `research` job (#10) is the first entry because it already has
its failure story (`conducting.md` §2: Codex fabricated an npm
package; a 4 KB memo of quoted docs ended it).

What this does *not* solve, said plainly: `measure` (#7, "evidence has
no home") and `decision.record` (#13) need a place on the record or
the lineage to write to. That is a record-schema change in
`dispatch/CONTRACT.md`, owner-ratified, and is outside a read-only
surface. It is listed as a follow-on unit, not hidden.

---

## 3. What the surface can and cannot serve, by construction

| running-list item | shape | can the kernel serve it read-only? |
|:--|:--|:--|
| #1 `board` | R over `.dev/records/dispatches/*.json` | **yes** — pure read; the query `launch.py` has no read path for today |
| #2 `record.summary`, `record.report` | R over one record | **yes** |
| #3 `lineage.timeline` | R, derived from records' `at` and `attempts` | **yes** |
| #4 `scope.check` | R, pure function of text | **yes** — no store; `scope-cap` refusal logic from `launch.py` reused, not duplicated |
| #5 `launch.preflight` | R, but needs `rev-list`/`merge-base` | **conditional** — git reads are read-only but the wf server forbids `gitio` wholesale because it commits. Needs a read-only git module (D4) |
| #6 `tests.red` | runs `unittest` | **no** — execution is a job (`verify`), not a read |
| #14 `context.resume` | R = #1 + #15 + open decisions | **partly** — #1 and #15 yes; open decisions need #13's home |
| #15 `dispatch.running` | R over `$DISPATCH_JOBS/*/state.json` + pid liveness + `exit`/`TRIPPED.md` | **yes** — `_status` in `launch.py:641` is already this, minus elapsed/timeout; `os.kill(pid, 0)` is a probe, not a write |
| #16 `spend` | R over records — but `spend` is null on every record | **serves the gap honestly** (`tokens=unrecorded`, as `pulse.py` does), never a zero |
| #18 `handoff` | R, composition of #1, #3, #13 | after #1/#3; #13 gap stated |
| #7 #8 #9 #12 #13 | W | **never on the surface** — job entries (§2.4) |

Diagnostics "sooner than later" is #15 joined with `telemetry/pulse.py`
(live session: age, idle, tokens, recent event names, never content).
Both are reads over stores the launcher already names in the record
(`session.stream`, `harness.isolation.store`), so the join is a query
function, not new plumbing.

---

## 4. What to serve first, and why this order

The running list's own note: "#1, #5, #7, #13 together are the
conductor loop's state; without them the state lives in this session's
context, which is what compaction destroys" (four compactions in one
session). Of those four, two are reads. So:

1. **`board`** — the state the loop re-derives before every action
   (`conducting.md` §1). Serves per lineage: last record, stage,
   verdict, `follows` chain, red count, PR (if recorded), open
   decision (gap stated until #13 exists).
2. **`running`** — the diagnostic the conductor checked by hand from
   `state.json`; elapsed vs `caps.timeout`, attempt, stream growing or
   not (from pulse). The item that turns "three jobs finished
   unnoticed" (`agentic-management.md` §Span of control) into a read.
3. **`record`** (summary ≤ 40 lines + findings as markdown) — every
   dispatch ends with the conductor opening the JSON.
4. **`scope.check`** — "cheap, do first" on the list; zero stores.
5. **`preflight`** — the three refusals that cost a relaunch each
   (`conducting.md` §6), computable before spend; gated on D4.
6. **`timeline`**, **`handoff`**, **`resume`** — compositions of the
   above; land after, cheaply.

Everything in 1–4 is a function over files the record contract already
fixes (`dispatch/CONTRACT.md` §The record, §The job directory), so
tests can be authored from the contract without reading `launch.py` —
which is the pipeline's requirement, not a convenience.

---

## 5. Decisions the owner has to make (tl;dr, tradeoff, recommendation)

**D1 — where the kernel lives and what it is called.** `ops/devlane/<name>/`
as one more mini-app (imports.json requires every app to declare its
edges, which is the point). Tradeoff: a new app vs. growing `workflow`.
Growing `workflow` puts a lane-wide surface inside the ledger app,
which the capability proposal already names as five things in one.
Recommend: a new app; name is the owner's (`surface` is descriptive;
`agentscient` is the owner's word for the whole framework, so it may
be too big for one app).

**D2 — one server instance or two.** The 2026-08-21 decision says
telemetry joins the existing wf server; the law proposal (§4.3) argues
a separate instance per lane. Both hold: one instance for the dev
lane, and the prod lane's Conductor carries its own (as
`dispatch/CONTRACT.md` §Lane already says of the launcher).
Recommend: one dev-lane instance; wf is its first registered app.

**D3 — how `workflow` satisfies the query/append gate.** Split
`chain.py` (project/verify vs append), or record the object-level
proof as an exception. Split is one commit and removes the exception;
the exception ships sooner. Recommend: ship the gate with the
exception stated in the registry row, then split as its own unit.

**D4 — read-only git on the surface.** `preflight` and `board`'s
`behind_tip` need `rev-list`/`merge-base`. Options: a `gitro.py` that
can only run an allowlisted set of read subcommands (proved by test:
no `commit`, `fetch`, `update-ref` reachable), or serve those fields
from the record only (`snapshot.behind_tip` is already recorded, stale
by definition). Recommend: the allowlisted module; without it
`preflight` cannot exist and it is the item that "refuses before the
harness spends".

**D5 — homes for `measure` evidence and `decision.record`.** Both are
appends to the record/lineage the surface would then serve. Record
schema change; owner's ratification. Not blocking units 1–5; blocking
`context.resume`'s "open decisions" field and `handoff`.

**D6 — registry format.** `registry.cue` validating the extended
`imports.json` (recommended) vs. a new `apps.cue` beside it.

---

## 6. Unit list for ratification

Each unit runs the pipeline as `conducting.md` §1 records it (plan →
tests by a non-implementing harness → skeptic → code → measured →
two reviews → adjudicate if they conflict). Read roles cannot run
python (handoff §4), so each unit names what the conductor measures.
One lineage per unit; `group.cut` by hand until it is a job.

| # | unit | deliverable | contract it is tested from | needs |
|:--|:--|:--|:--|:--|
| U1 | registry contract | `registry.cue`; `imports.json` rows gain `query/append/stores/serves`; `query: null` stated for apps without a surface; `cue vet` examples + faults | this memo §2.1; `imports.json` `_comment` | D6 |
| U2 | query/append gate | `imports.py` (or a sibling check) refuses an `append` module reachable from `query`; fault fixture must draw it; clean fixture stays quiet; registered in a gate kind with `ci: true` | §2.2; `AGENTS.md` §A check must fire | U1, D3 |
| U3 | `dispatch/query.py` | the read layer extracted from `launch.py`: records dir, jobs root, `state.json`, `exit`, `TRIPPED.md`; `_status` becomes a caller of it; no behaviour change; AST test that it imports nothing that writes | `dispatch/CONTRACT.md` §The record, §Watching | — (parallel to U1) |
| U4 | kernel server + launcher | registry-driven server; `agentscient://apps`, `agentscient://jobs`; wf registered and byte-identical to today's `wf_*` bodies; `.mcp.json` repointed; E2E on a fixture repo with synthetic records and job dirs | §2.3; `mcp_server.py` docstring (the promises it states); `mcp.cue` | U1, U3, D1, D2 |
| U5 | first resources | `board`, `running` (+ pulse join), `record` summary/report, `scope.check` | §3, §4; running list #1 #2 #4 #15 | U3, U4 |
| U6 | read-only git + `preflight` | allowlisted read module; `preflight` refuses on model/follows/ref/scope before launch | running list #5; `dispatch/CONTRACT.md` §Refusals | U5, D4 |
| U7 | compositions | `timeline`, `handoff`, `resume` (with "open decisions: unresolved" until U9) | running list #3 #14 #18 | U5 |
| U8 | `jobs.json` services | `research` job; W items #7 #8 #9 #12 #13 as job entries with deliverable + record shape; `agentscient://jobs` lists them | §2.4; `task/CONTRACT.md` §Jobs | U4 |
| U9 | homes for measure/decision | record schema change so `measure` evidence and rulings live on the lineage; then `board.open_decision` and `resume` fill in | running list #7 #13; `dispatch/CONTRACT.md` | D5 |

Order: U1 ∥ U3 → U2 → U4 → U5 → U6 ∥ U7 ∥ U8 → U9. U5 is the first
unit the conductor feels; everything before it is the frame the owner
asked for first.

## 7. What this memo did not do

No code, no execution, no reading outside the snapshot and the two
inputs. Line numbers cited are at `af3ff01`. `mcp.cue`'s `server_imports`
constraint was read but `cue vet` was not run; the claim that it is
optional is from the `?` marker, not a run. The count of records (41)
is the handoff's, not re-measured.
