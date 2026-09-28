# The mini-apps as one framework — the whole of it

Plan for the tree at `9f3e7de41744523645c83e3d5690818156a51ea5`, from the
owner's scope of 2026-08-29: *"I want to get the mini-apps redone into a
framework - it makes sense - i like symfony, its a good example"* and
*"don't constrain it too much - this is a big task"*, with *"plans
(contracts) at every level"*. Everything here was read from the snapshot
and `in/`; nothing was executed. The two prior plans in the tree
(`ops/docs/scratch/agentscient-kernel-research.md`,
`agentscient-framework-plan-narrow.md`) and the capability memo
(`in/capability-abstraction.md`, `ops/docs/scratch/capability-decisions.md`)
were read as prior takes, and are used where they were right; they do not
bound this one.

This document is itself the **root plan** in the sense §3 defines: it is
the thing `plan.cue` must accept once `plan.cue` exists (§3.5, U0), and
every unit below is a child plan that nests in it.

---

## 0. Settled, open, and how this plan treats each

Settled by the owner, carried without re-argument:

- framework before surface — the container, its registry and its gate land
  before any resource the conductor can feel;
- `wf` is the ledger and is renamed to `ledger`;
- the injected object is a **capability**; `service` is compose's word;
- the pinned launcher (`ops/devlane/dispatch/launch.py` and `levers/`) is
  untouched; the framework is built beside the old apps, proven on a
  fixture repository, and cut over explicitly.

Open, and decided here (each decision stated once in §11 with its premises
tagged): which capabilities (§4), their order (§7), storage (§5), size
(§6), the container's language (§2.4). "Decided here" means recommended
for ratification: the plan gate (§3) refuses a child unit whose parent
decision is still `open`, so these must be ruled before U2 starts, and the
first units (U0, U1) are chosen so that nothing in them depends on any of
the five.

---

## 1. What "a framework" means here, with Symfony as the example

Symfony is the example, not the target. What is taken from it is the
*shape of the obligations* a framework places on the things it hosts, and
the fact that every one of those obligations is checked at compile time
(`cache:warmup`) rather than discovered at runtime. Held to what the lane
already has:

| Symfony | here | today's instance (measured in tree) | what the framework adds |
|:--|:--|:--|:--|
| **Kernel** (`Kernel::boot`) | `agentscient` — the kernel package | none; `mcp_server.py` wires itself by hand | one boot, one registry, one gate |
| **Bundle** | a **capability** — one directory, one manifest, one contract | seven apps under `ops/devlane/`, boundaries by accretion | a capability's directory has a fixed anatomy (§2.2) that a check can read |
| **`services.yaml` / compiled container** | `capabilities.cue` + `kernel/container.py` | `ops/contracts/imports.json` (`may_import` only) | ids, module path, interface, deps, tags; cycles/unknowns/tag-flow refused at boot |
| **Constructor injection by interface** | `build(deps, ctx)` receiving objects typed by a `Protocol` | `ReadOnlyContext` hands `store`/`chain`/`cas` by attribute | a capability never imports a sibling app; the container hands it what it declared |
| **`APP_ENV`** | `lane` — a boot argument, not a field | `lane: "dev"` on every dispatch record; `WF_LANE=dev` | one container per lane; the 2026-08-27 "no field from one instance" ruling stands |
| **Tags + compiler passes** | `tags` on a capability; the framework gate | `test_mcp_server.ReadOnlyByConstruction` (one app, one unittest) | `read` may not reach `write`, checked statically in CI and again at boot |
| **Config component / validation** | CUE — `capabilities.cue`, per-capability `contract.cue`, `plan.cue` | 12 workflow contracts + `harness/{context,evidence}.cue` in `cue/`+`examples/`+`faults/` form | every declaration the kernel reads is CUE-vetted with a fault corpus |
| **Doctrine DBAL + migrations** | `db` capability | `workflow/store.py` (sqlite, forward-only numbered migrations, digests) | extracted; `DbRO` is the only interface a `read` capability may receive |
| **HttpKernel / controller** | `surface` — the MCP controller | `mcp_server.py` + `mcp_launch.py` | one controller serving every `surface.resource`-tagged capability |
| **Console** | commands — `wf`, `launch`, `plan` | `wf.py` (2,031 lines), `launch.py` (807) | registered (`command` tag); `wf` becomes a command over `ledger` at cutover |
| **EventDispatcher / listeners** | git and harness hooks | `hooks/` (commit-msg, post-commit, post-checkout, claude/*) | registered (`listener` tag); no rewiring in this plan |
| **Messenger handlers** | jobs — `jobs.json` entries executed by the launcher | 8 jobs in `task/jobs.json` | writers are handlers, run only through the launcher; the surface *lists* jobs |
| **Profiler / web debug toolbar** | `observe` | `telemetry/{pulse,usage,worth,breaker}.py` | pulse and usage as `read` capabilities on the surface |
| **Flex recipe** | `scaffold` — `plan new-capability` writes the anatomy | none | the anatomy check (§2.2) is what the scaffold satisfies |
| **Symfony's own test suite / `symfony/skeleton`** | the **fixture repository** | `fixtures/stores.py` (session stores only) | a generated git repo with synthetic records, a ledger, stores, a db — the E2E ground |

Deliberately **not** carried: autowiring by type scan (every dep is
declared — `mini-app-lessons.md` §3, absence is refused); the service
locator (no capability may ask the container for another at runtime);
lazy proxies; bundle inheritance; anything that resolves at runtime what
could be refused at boot.

The one idea from Symfony that matters most and is easiest to lose: the
container is **compiled**. Everything the framework knows is known before
the first capability runs, and a mis-declared capability is a boot
failure with a named refusal, never a surprise during a dispatch.

---

## 2. The framework's shape

### 2.1 Layout on disk

```
ops/capabilities/                 the framework (new; beside ops/devlane/)
  kernel/                         container.py, registry.py, errors.py, boot.py
  contracts/                      capabilities.cue, plan.cue, capability.cue (anatomy),
                                  examples/, faults/, obs/, extract/   (the cue+faults form)
  checks/                         framework gate: registry_vet.py, tag_flow.py,
                                  anatomy.py, no_sibling_import.py, plan_vet.py
  capabilities/<id>/              one directory per capability (§2.2)
  surface/                        the MCP controller (composition root)
  commands/                       plan.py (the plan command), later wf → ledger shim
  fixture/                        the fixture-repository builder + E2E harness
  tests/                          kernel, gate and E2E suites
ops/devlane/                         the old apps, untouched until each is retired (§8)
```

Flat, one tier: the layering (L0/L1/L2) lives in the registry and the
gate reads it; a directory tier would be a second copy that drifts
(`mini-app-lessons.md` §8). `ops/capabilities/` is one `imports.json` app
for the duration of the build (§8), so the existing CI import gate sees
one new node with declared edges to nothing — the framework loads
capability modules by registry value, not by import, which is what keeps
that row honest.

### 2.2 The anatomy of a capability (what the `anatomy` check reads)

```
capabilities/<id>/
  capability.json      the manifest row — id, module, iface, deps, tags, stores, serves
                       (the row capabilities.cue closes over; one row per directory)
  CONTRACT.md          prose: guarantees, inputs, refusals — the text tests are authored from
  contract.cue         the closed record shapes and refusal names; unifies into the one package
  <id>.py              exports build(deps: dict[str, object], ctx: BootContext) -> object
                       and the Protocol(s) named in iface
  migrations/          NNNN_<name>.sql, only for capabilities that own tables (§5)
  tests/               the capability's own suite, run by its own gate row
  faults/              at least one negative control per refusal in CONTRACT.md
  guide.md             the operator's page (folds into ops/guide/ at cutover)
```

The check is both directions (`AGENTS.md` §A check must fire): a
directory missing any of these is refused by name; a file present that
the anatomy does not name is refused too (closure — the same reason
`#Context` is `close()`). `deps: []`, `stores: []`, `serves: []` are
declarations; an absent key is refused (`AGENTS.md` §Absent is not none).

A capability's public surface is exactly what its `iface` Protocol names.
Everything else in the directory is private, and the `no-sibling-import`
check makes it so: a module under `capabilities/<a>/` may import nothing
under `capabilities/<b>/` nor under `ops/devlane/`.

### 2.3 The registry and the container

`capabilities.cue` is the closed shape; `capabilities.json` is the
committed export the kernel reads (stdlib has no CUE parser; a check
asserts the export is current — D-cuejson in the narrow plan, kept).

```
#Capability: {
  id!:     =~"^[a-z][a-z0-9]*(\\.[a-z][a-z0-9]*)*$"
  layer!:  0 | 1 | 2
  module!: string                            // path under capabilities/
  iface!:  [#NonEmpty, ...#NonEmpty]         // Protocol names the module exports
  deps!:   [...{id!: string, iface!: string}]
  tags!:   [...#Tag]
  stores!: [...#NonEmpty]                    // paths or db tables it reads/owns
  serves!: [...#NonEmpty]                    // resource names, for surface.resource
}
#Tag: "read" | "write" | "surface.resource" | "command" | "listener" | "handler" | "migrates"
#Registry: { capabilities!: [...#Capability] }
  // relational: ids unique; every dep resolves; dep.layer < layer; acyclic;
  // read/surface.resource never transitively reach write; a `migrates`
  // capability owns at least one migration; every `serves` name unique.
```

Boot (`kernel/boot.py`), in order, each step a named refusal:

1. read `capabilities.json`; refuse an absent key anywhere;
2. check the export's digest against `capabilities.cue` (currency);
3. order topologically; refuse a cycle by naming it;
4. **tag flow** before any module loads: a `read` or `surface.resource`
   capability whose transitive deps include a `write` one is refused with
   the path;
5. load each module from its registry path (`importlib.util`), call
   `build(deps, ctx)`, keep the object under `id`;
6. assert each built object satisfies every declared `iface`
   (`runtime_checkable` Protocol: method presence; behaviour is the
   capability suite's job).

`ctx` (`BootContext`) carries: `lane`, the repository root, the db path
for the lane, the records root, and a clock. It is the *only* ambient
thing a capability receives, and it is a frozen dataclass. The container
is immutable after boot; `container.get(id)` exists for composition roots
(`surface/`, `commands/`) and the `no-locator` check refuses it inside
any capability module.

### 2.4 The container's language — decided

**Python, stdlib only, for the dev lane; the contracts are the portable
part.** The apps it hosts are 14,591 lines of Python (`wc -l` over
`ops/devlane/*/*.py` at this ref); the workflow contracts already show that
CUE, not the implementation language, is where the lane's law is
(`capability-decisions.md`, ratified 2026-08-27). A Rust container for the
product lane is written later *from the same `capabilities.cue`,
`capability.cue` and `plan.cue`*, and the dev-lane fixture repository is
the conformance suite it is run against — which is the "prove it in the
dev lane first" arrangement `AGENTS.md` describes, applied to the
framework itself. The plan does not build the Rust container and nothing
here depends on it; it constrains the CUE to say nothing Python-specific
(no module paths in `contract.cue`; `module` in the registry is a string
the kernel interprets, and the Rust kernel would interpret its own).

### 2.5 The framework-wide gate

One registered check row per assertion in `gate-kinds/artifact.json`
(`ci: true`), each with a positive control and a fault that must draw the
named refusal, run statically so CI catches it without booting:

| check | refuses | fault fixture |
|:--|:--|:--|
| `registry-vet` | `capabilities.json` not vetted by `capabilities.cue`, or stale against it | a stale export |
| `tag-flow` | `read`/`surface.resource` reaching `write` | a registry with `resume → db:DbRW` |
| `anatomy` | a capability directory missing or exceeding §2.2 | a directory without `faults/`; one with `notes.md` |
| `no-sibling-import` | a capability importing another capability or `ops/devlane/` | a module `from ..ledger import chain` |
| `no-locator` | `container` / `.get(` inside a capability module | a module calling `container.get("db")` |
| `plan-vet` | a plan not accepted by `plan.cue` (§3) | the §3.6 fault corpus |
| `imports-agree` | a `deps` edge with no matching `may_import` edge, until `imports.json` folds | a dep with no app edge |

The read-only-by-construction property that one unittest proves for one
server today becomes a property every capability gets by being
registered. That is the framework's first *felt* payoff even before the
surface: a capability cannot be wired wrong and stay green.

---

## 3. Plans as contracts at every level — `plan.cue`

The owner's rule: *plans (contracts) at every level*. A plan is a
contract between the level above (which supplies scope and settled
decisions) and the units below (which must deliver what the plan names
and nothing else). For a gate to vet it, a plan has to be data, not only
prose. The arrangement is the same one `#Brief`/`#Task` uses
(`harness/context.cue`): the prose stays, and a closed sidecar carries
the fields a gate can compare — because *"an interface written twice in
prose is an interface that will differ"*.

### 3.1 The two files

```
<plan>.md          the prose (this document is one)
<plan>.plan.json   the closed sidecar plan.cue vets; regenerated by `plan extract`
                   from the md's tables and refused when they disagree
```

### 3.2 What a plan must contain (`#Plan`)

```
#Plan: close({
  id!:        #NonEmpty                     // "agentscient" | "agentscient/U3" | "agentscient/U3/a"
  parent!:    #Parent | #DeclaredAbsent     // absent ONLY for the root, and said so
  ref!:       #Sha                          // the tree it was planned against
  scope!:     #Scope                        // the owner's words, verbatim, dated
  premises!:  [#Premise, ...#Premise]       // every claim the plan stands on, tagged
  settled!:   [...#Settled]                 // decisions inherited or ruled above; not re-openable
  decisions!: [...#Decision]                // NEW decisions this plan makes, one sentence each
  open!:      [...#Open]                    // what this plan leaves to a child, and which child
  deliverables!: [#Deliverable, ...#Deliverable]   // what "done" produces, with interfaces
  gates!:     [#Gate, ...#Gate]             // commands whose exit 0 means done; never prose
  units!:     [...#Unit]                    // children, or [] for a leaf
  refusals!:  [...#NonEmpty] | #DeclaredAbsent     // named refusals this plan's code will draw
  discharge!: #Discharge                    // where each durable part goes when the plan is spent
  denied!:    [...#NonEmpty]                // what the planner was denied (pipeline.md row 2)
})

#Scope:     close({ owner_words: #NonEmpty, dated: #Date, source: #NonEmpty })
#Premise:   close({ text: #NonEmpty, tag: "measured" | "read" | "memory" | "assumed", source: #NonEmpty })
#Settled:   close({ id: #NonEmpty, ruled_by: "owner", dated: #Date, where: #NonEmpty })
#Decision:  close({ id: #NonEmpty, sentence: #NonEmpty, premises: [#Premise, ...#Premise],
                    status: "recommended" | "ratified" | "rejected" })
#Open:      close({ what: #NonEmpty, delegated_to: #NonEmpty })   // a child id; never "later"
#Deliverable: close({ path: #NonEmpty, interface: #Interface | #DeclaredAbsent })  // context.cue's
#Gate:      close({ name: #NonEmpty, argv: [#NonEmpty, ...#NonEmpty], fires_on: #NonEmpty, quiet_on: #NonEmpty })
#Unit:      close({ id: #NonEmpty, deliverables: [#Deliverable, ...#Deliverable],
                    needs: [...#NonEmpty], stage: "plan" | "tests" | "check" | "code" | "review" | "done" })
#Discharge: close({ decisions_to: #NonEmpty, design_to: #NonEmpty, lessons_to: #NonEmpty })
#Parent:    close({ id: #NonEmpty, sha256: #Digest, unit: #NonEmpty })   // which row of the parent I am
```

Every list that may be empty is either a declaration (`units: []` is a
leaf) or `#DeclaredAbsent` with a reason; an omitted key is refused.
`gates` must have a `fires_on` and a `quiet_on` because a gate that only
passes the clean case is worse than none (`AGENTS.md`).

### 3.3 How a unit plan nests in its parent

A child plan is a **projection** of one row of its parent, and the gate
checks the projection in both directions, the way `#Dispatchable` binds
`task` to `brief`:

1. `child.parent.id` names a plan whose `.plan.json` digest equals
   `child.parent.sha256` — a child written against a parent that has
   since changed is **stale**, refused, and says which digest it expected.
2. `child.parent.unit` names a row in `parent.units`, and
   `child.deliverables == that row.deliverables` (exact equality, direct
   field reference — `cue-aar-equality.md`: equality lives in direct
   references, not aliases).
3. `child.settled ⊇ parent.settled ∪ parent.decisions[status=ratified]`
   — a child cannot drop a ruling; it carries it by id.
4. `child.decisions` may not name an id in `child.settled` — a child
   cannot re-open what is settled above. Disagreement is recorded as an
   `open` item delegated *upward* (`delegated_to: parent.id`) and the
   child stops there (`AGENTS.md` §Teamwork: disagreement is recorded, not
   overwritten).
5. `child.scope.owner_words` is the parent's, verbatim, or a quotation of
   a later owner ruling with its date — a child does not invent scope.
6. Every `parent.open` item is `delegated_to` a unit that exists in
   `parent.units`, and that unit's child plan lists it either in
   `decisions` or in its own `open` (delegated further down, never
   dropped).
7. A unit may not leave `stage: plan` until its child `.plan.json` passes;
   it may not enter `code` while any `decisions[].status == recommended`
   that its deliverables depend on remains unratified.

Depth is not bounded. A leaf is a plan with `units: []`; its `gates` are
the test commands the pipeline's stage 3 authors from its `deliverables`
and `refusals`, which is how *plans at every level* meets *tests before
code*: the tests author reads the leaf plan, never the code.

### 3.4 What vets it

`plan vet <path>` (in `checks/plan_vet.py`, later `commands/plan.py`):
a raw-document presence check first (`cue vet -c` cannot prove a key was
stated — `mini-app-lessons.md` §12), then `cue vet` against `plan.cue`,
then the seven relational rules above, each a named refusal with
expected / actual / what-would-satisfy. Registered `ci: true` over every
`*.plan.json` under `.dev/`. `plan extract <md>` regenerates the sidecar
from the prose's tables (unit table, decisions section, premises), and
`plan vet` refuses when the committed sidecar and a fresh extraction
differ — the prose and the data cannot drift.

### 3.5 Bootstrapping

This document is the root, and `plan.cue` does not exist yet. U0 builds
`plan.cue`, `plan vet` and its fault corpus, then hand-writes
`agentscient.plan.json` from §§0–11 here and makes it pass. If making it
pass requires changing this prose, that change is U0's finding and comes
back as a fix to this plan, not a silent edit of the sidecar. From U1 on,
no unit is dispatched without a passing child plan; the running list's
`launch.preflight` (#5) grows one refusal — "no ratified plan for this
unit" — the day the launcher is next touched, which is not in this plan.

### 3.6 Fault corpus for `plan.cue` (the tests author's list)

stale parent digest · deliverables not equal to the parent row · a
settled id re-decided · an open item delegated to no unit · a gate with
no `quiet_on` · a premise with a tag outside the four · a root that omits
`parent` instead of declaring it absent · `units: []` with `open` non-empty
(a leaf may not leave anything open) · a decision with zero premises ·
a child whose scope words differ from the parent's. Each must prove the
plant landed (differs from the clean example) and draw its named refusal.

---

## 4. Which capabilities — decided

The inventory, by layer. "From" names what is copied (never moved — the
old app keeps running until §8 retires it). Names follow the memo where
the owner has already used them and stay descriptive where he has not.

| id | L | iface(s) | deps | tags | from | contract source (tests come from this) |
|:--|:-:|:--|:--|:--|:--|:--|
| `db` | 0 | `DbRW`, `DbRO`, `Migrator` | — | `write`,`read`,`migrates` | `workflow/store.py` | `store.py` docstring; `cue/db.cue` |
| `gitro` | 0 | `GitRO` | — | `read` | new | allowlisted read subcommands; commit/fetch/push/update-ref proved unreachable |
| `snapshot` | 0 | `Snapshot` | `gitro` | `read` | `harness/stage.py` + `task/fileset.py` | `#Staged`/`#StagingProof` in `context.cue` (D3: its own primitive) |
| `observe` | 0 | `PulseRO`, `UsageRO`, `Wires` | — | `read` | `telemetry/{pulse,usage,worth}.py`, `harness/wires.py` | `ops/docs/telemetry.md`; `telemetry.md` guide |
| `fixture` | 0 | `Stores`, `Repo` | — | `read` | `fixtures/stores.py` + new repo builder | `guide/fixtures.md`; §9 |
| `ledger` | 0 | `LedgerRW`, `LedgerRO` | `db` | `write`,`read`,`migrates`,`surface.resource` | `workflow/{chain,cas,receipts,query,canonical}.py` | `workflow/query.py` docstring; `cue/{schema,events,canonical}.cue` |
| `records` | 0 | `RecordsRO` | — | `read`,`surface.resource` | the read paths of `dispatch/launch.py` (`_status`) and `record.py` | `dispatch/CONTRACT.md` §The record, §Watching |
| `law` | 0 | `Contracts` | — | `read` | `harness/{context,evidence}.cue`, `workflow/contracts/cue/*` | the unified CUE package; `capability-decisions.md` §Ratified |
| `custody` | 1 | `Custody` | `snapshot` | `read` | `harness/{isolation,probe}.py` | `#Isolation`/`#Dispatchable`; `harness.md` guide |
| `certify` | 1 | `Certify` | `law`,`gitro`,`ledger:LedgerRO` | `read` | `workflow/contracts/vet.py`, `ops/contracts/imports.py`, `workflow/checks/*` | memo B6; `CONTRACT-NOTES.md` |
| `memory` | 1 | `MemoryRO`, handlers | `db:DbRW` (handlers), `db:DbRO`, `ledger:LedgerRO`, `records` | `read`,`handler`,`migrates`,`surface.resource` | new | narrow plan §4.1 (decision/rule/lesson with premises; `resume`) |
| `jobs` | 1 | `Catalog` | — | `read`,`surface.resource` | `task/jobs.json` + `task/envelope.py` | `task/CONTRACT.md` §Jobs |
| `surface` | 2 | — (composition root) | every `surface.resource` | `command` | `workflow/mcp_server.py`, `mcp_launch.py` | `mcp_server.py` docstring; `cue/mcp.cue` |
| `workflow` | 2 | `Runner` | `records`,`ledger`,`jobs`,`custody` | `command` | new (the lever-backed DAG driver) | `capability-decisions.md` §Directional rulings |

Roles that are not capabilities and are registered as what they are:
`wf.py` and `launch.py` (`command`), `hooks/*` (`listener`), jobs that
write (`handler`) — registered so the registry is complete, not rewired.

What this resolves that the memo left open: `task` dissolves — its
catalogue becomes `jobs`, its envelope goes with it, `fileset.py` goes to
`snapshot`, `run.py` stays under `ops/devlane/` as the launcher's runner
until the launcher is next touched (D-task, §11). `dispatch` as a
capability is *not* built here: the launcher is pinned, and its read half
is `records`. `hook` stays a listener set, not a capability — it has no
interface anyone injects.

---

## 5. Storage — decided

**One sqlite file per lane, owned by `db`, with every capability that
owns tables shipping its own numbered migrations under the `migrates`
tag; git-committed JSON stays where it is the evidence.** The ledger's
tracked export under `chains/` and the dispatch records under
`.dev/records/dispatches/` are commits — they are the record, and the db
is a cache rebuilt from them (`store.py` docstring; `AGENTS.md`: "`wf.db`
is a gitignored cache"). `memory` entries are the one new durable thing
and they are ledger-shaped: appended through a handler, exported to a
tracked file by the same discipline as `chains/`, cached in `db`. The
`Migrator` applies migrations from every `migrates` capability in
registry order with the owning id recorded beside the digest, so a schema
row says *who* owns it. Interfaces name no sqlite type ("Postgres by
definition"); the sqlite build is the only build in this plan.

---

## 6. Size — decided

**Fourteen registered capabilities (§4), built over twenty-two units
(§7), no unit larger than one capability or one kernel piece, and the
kernel itself under two thousand lines of Python across `kernel/`,
`checks/` and `surface/`.** The bound is a gate: `checks/size.py` counts
lines under `ops/capabilities/kernel/`+`surface/` and refuses over 2,000,
so growth in the framework proper is a decision with a reason rather
than accretion — the failure mode the whole exercise exists to end.
Capabilities are not bounded by the framework (each has its own
contract); the *count* is bounded by the registry being closed and every
addition needing a row, a contract, a fault corpus and a guide.

---

## 7. Units — the build, in order

Each unit is a child plan (`agentscient/U<n>`), runs the pipeline
(`pipeline.md`: plan → tests by a non-implementing harness → skeptic →
code → two reviews), and PRs into `agentscient/dev`. "Gate" is the
command whose exit 0 is done. Tests are authored from the contract column
of §4 or the section named — never from the module the unit copies.

| # | unit | deliverables | gate (what the conductor measures) | needs |
|:--|:--|:--|:--|:--|
| U0 | **plan gate** | `contracts/plan.cue`, `checks/plan_vet.py`, `plan extract`, §3.6 faults, `agentscient.plan.json` passing | `plan vet ops/capabilities/agentscient.plan.json`; every fault draws its refusal | — |
| U1 | **vocabulary** | `capability` reserved; `service` reserved outside `.dev/infra/`; `vocab.cue` row + fault; wall docstring ↔ `AGENTS.md` sentence | `vocabulary_wall.py` clean; fault red | — |
| U2 | **registry contract** | `contracts/capabilities.cue`, `capability.cue` (anatomy), examples, faults, `registry-vet` + `anatomy` checks registered | `cue vet` over examples; faults red | U0 |
| U3 | **kernel boot** | `kernel/{registry,container,boot,errors}.py`; refusals of §2.3 with fault registries; `BootContext` | boot the fixture registry; six faults draw six refusals | U2 |
| U4 | **framework gate** | `tag-flow`, `no-sibling-import`, `no-locator`, `imports-agree`, `size` checks, `ci: true` rows | each fires on its fault, quiet on its control | U3 |
| U5 | **`db`** | `capabilities/db/` from `store.py` verbatim; `DbRW`/`DbRO`/`Migrator`; ported `test_store.py`; `0001` migration re-homed under `ledger` | ported suite green against `db/`; `DbRO` cannot create the file it reads | U3 |
| U6 | **`gitro`** | allowlisted read module; unreachable-write proof | test proves `commit`/`fetch`/`push`/`update-ref` unreachable | U3 |
| U7 | **`fixture` repo builder** | `fixture/repo.py`: a generated git repo with synthetic dispatch records, a ledger chain + export, session stores, a migrated db; the E2E harness `tests/e2e.py` | the builder proves its plant (repo differs from empty and matches its manifest) | U5, U6 |
| U8 | **`ledger`** (copies) | `capabilities/ledger/` over `db`; `LedgerRW`/`LedgerRO`; `wf.py` untouched; both suites green | `wf://` bodies from the old server == `ledger` query bodies on the fixture repo | U5, U7 |
| U9 | **`records`** | read paths of `launch.py` copied, not moved; board/running/record summary | `_status` behaviour reproduced against fixture records; launcher diff empty | U7 |
| U10 | **`observe`** | pulse/usage/worth reads + `wires` as one capability | telemetry suites green over the fixture stores | U7 |
| U11 | **`surface`** | container-driven MCP controller; `<id>://<name>` resources, `<id>_<name>` tools; `agentscient://capabilities`; tools/list cap as registry invariant; `mcp_launch` prepare-then-execv kept | `diff` of `wf://*` bodies old vs new on the fixture repo = empty; first felt unit | U4, U8, U9, U10 |
| U12 | **`jobs`** | catalogue + envelope as a `read` capability; `agentscient://jobs` | `jobs.json` served byte-identical; `research` job entry added as data | U11 |
| U13 | **`law`** | the unified CUE package: `harness/*.cue` + `workflow/contracts/cue/*` + framework contracts under one `cue vet`; `Contracts` iface | one `cue vet` over the package passes; one planted fault fails | U2 |
| U14 | **`certify`** | `vet.py`, `imports.py`, `checks/*` registered as one capability over `law`+`gitro`+`LedgerRO`; no behaviour change | every existing check runs through `certify` with identical output | U8, U13 |
| U15 | **`snapshot`** | `stage.py` + `fileset.py` as one capability over `gitro`; `#Staged` proof both directions | staging suite green; empty snapshot refused | U6 |
| U16 | **`custody`** | `isolation.py` + `probe.py` over `snapshot`; INVALID-never-pass kept | harness suites green; `probe` on an unlisted harness → INVALID | U15 |
| U17 | **`memory`** | entry kinds (decision/rule/lesson, premises tagged), `0002_memory.sql` with `contract.cue` as its shape; `record`/`after_action` handlers as jobs; `resume`; HANDOFF fixture regenerated | fixture handoff regenerated from entries == golden; unsourced premise refused | U8, U9, U12 |
| U18 | **`plan` command** | `commands/plan.py`: `new-capability` scaffold (writes §2.2 anatomy), `vet`, `extract`, `status` (every plan's stage tree) | scaffolded directory passes `anatomy`; `plan status` matches the unit table | U4, U0 |
| U19 | **`workflow` runner** | lever-backed DAG driver over `records`+`ledger`+`jobs`+`custody`; runs one pipeline stage per lever dispatch on the fixture repo | a two-stage DAG runs end-to-end on the fixture; a failed stage halts and records | U11, U12, U16 |
| U20 | **cutover** | `.mcp.json` → `surface`; `wf`→`ledger` registry id, `ledger://` with `wf://` aliases for one release; `ops/devlane/workflow/wf.py` a shim that `execv`s the command; `imports.json` rows for retired apps removed as each retires | byte-identity of `wf://` after the move; old suites still green through the shim | U11–U19 |
| U21 | **discharge** | decisions → `DECISIONS.md`; design → each capability's `CONTRACT.md`; lessons → `mini-app-lessons.md`; this plan and both prior takes marked spent | `plan status` shows every unit `done`; nothing under `.dev/` cites the plans | U20 |

Order, with parallelism: U0 ∥ U1 → U2 → U3 → U4 → (U5 ∥ U6) → U7 →
(U8 ∥ U9 ∥ U10 ∥ U13 ∥ U15) → U11 → (U12 ∥ U14 ∥ U16 ∥ U18) → (U17 ∥ U19)
→ U20 → U21. U11 is the first the conductor feels; U0 is the first that
lands and is what makes every later unit vettable.

Per-unit cost the pipeline pays: read roles cannot run python (handoff
2026-08-28 §4), so each gate above is the command the conductor runs and
stamps with the ref. The tests author for U5, U8, U15, U16 gets the
contract text and the old app's *tests* withheld as well as its code —
otherwise the ported suite is the spec and the port is trivially green
(`mini-app-lessons.md` §1).

---

## 8. Beside the old apps, then an explicit cutover

- **Beside:** nothing under `ops/devlane/` is edited by U0–U19 except
  `task/jobs.json` (data: new job entries) and registration rows in
  `gate-kinds/artifact.json` and `imports.json`. Every capability starts
  as a copy; the old module and the copy both run their suites; the
  byte-identity gates (U8, U11, U20) bound the duplication window.
- **Proven:** every E2E claim is made on the fixture repository (§9),
  never on the live lineage — `AGENTS.md`: work that builds a tool never
  appears in the ledger it keeps.
- **Cut over explicitly (U20):** one PR that repoints `.mcp.json`, renames
  the id, installs the shim, and retires old directories one per commit
  with `imports.json` and `gate-kinds` rows removed in the same commit —
  the import gate refuses a stale path literal, which is the check that
  the retirement was complete. The pinned launcher and `levers/` are not
  retired by this plan; they are the last thing standing under
  `ops/devlane/`, and their move under the framework is a plan of its own
  after U21, when `records` and `custody` have been in service.
- **Rollback** is `git revert` of the cutover PR; the old apps still
  exist at its parent, and the shim is what makes the revert clean.

---

## 9. The fixture repository

`fixture/repo.py` builds, from a manifest, a throwaway git repository
under a temp root: N lineage branches; synthetic dispatch records in
`.dev/records/dispatches/` with the `dispatch/CONTRACT.md` §The record
field order; a ledger chain with its tracked export; harness session
stores via `stores.py` (measured shapes, verbatim usage); a db migrated by
`Migrator`; three memory entries. The builder proves its plant both ways
(the repo differs from empty *and* matches its manifest) before handing
the path back, the `stage.py` rule applied to a repository. The E2E
harness boots the container against it, serves every `surface.resource`,
and compares to golden bodies committed beside the manifest. Time is a
variable the manifest sets (DECISIONS 2026-08-21: time is controlled in
all tests). The same repository is the conformance suite a later Rust
kernel is run against (§2.4).

---

## 10. Refused framework-wide

| refusal | drawn when |
|:--|:--|
| `plan.stale-parent` · `plan.deliverables-mismatch` · `plan.reopened` · `plan.undelegated` · `plan.gate-half` | §3.3 rules 1–7 |
| `capability.unknown` · `capability.cycle` · `capability.absent-key` · `capability.layer` | registry boot |
| `tag.write-into-read` | a `read`/`surface.resource` capability transitively reaching `write` |
| `anatomy.missing` · `anatomy.extra` | §2.2 |
| `iface.unsatisfied` | built object lacks a declared Protocol method |
| `import.sibling` · `locator.inside-capability` | §2.5 |
| `registry.stale-export` | `capabilities.json` not current against the `.cue` |
| `size.kernel` | kernel over 2,000 lines |
| `vocab.service-outside-infra` · `vocab.capability-absent` | U1 |
| `fixture.unproven` | the fixture repo does not differ from empty or does not match its manifest |
| `memory.premise-unsourced` | a premise with no source or a tag outside the four |

Every refusal is a named string in `kernel/errors.py` in
`workflow/errors.py`'s `Refusal(claim, actual=, needed=)` shape — copied,
because the kernel may not import `ops/devlane/`.

---

## 11. New decisions — one sentence each, premises tagged

Ruled already and not re-asked: capability as the axis; evidence shared
per lane (D2); snapshot split (D3); `lane` deferred as a field;
two-level CUE architecture; `wf`→`ledger` with a shim; `service` is
compose's; framework before surface; launcher pinned; beside, fixture,
explicit cutover.

- **D-plan-cue** — A plan is a prose document plus a closed
  `.plan.json` sidecar that `plan.cue` vets, and a child plan is a
  digest-bound projection of one row of its parent, checked in both
  directions. *Premises:* prose interfaces written twice differ
  [read: `context.cue` §brief]; `cue vet -c` cannot prove key presence,
  so a raw check precedes it [read: `mini-app-lessons.md` §12]; the
  pipeline denies the planner the freedom to move boundaries, which a
  parent-digest binding makes checkable [read: `pipeline.md` row 2].
  Status: recommended.
- **D-language** — The dev-lane container is Python stdlib, and the CUE
  contracts plus the fixture repository are what a later Rust container
  is written from and proved against. *Premises:* the hosted apps are
  14,591 lines of Python [measured: `wc -l` at this ref]; the ratified
  architecture puts the law in CUE, not code [read:
  `capability-decisions.md`]; the dev lane proves before the prod lane
  writes its equivalents [read: `AGENTS.md`]. Status: recommended.
- **D-storage** — One sqlite file per lane owned by `db`, each
  table-owning capability shipping its own migrations under a `migrates`
  tag with ownership recorded beside the digest, while committed JSON
  exports remain the evidence and the db a cache. *Premises:* `wf.db` is
  a gitignored cache and the export is the evidence [read: `AGENTS.md`,
  `store.py` docstring]; records are commits by contract [read:
  `dispatch/CONTRACT.md` §The record]; no runtime instance crosses lanes
  [read: LANE-NO-BLEED]. Status: recommended.
- **D-set** — Fourteen capabilities as tabled in §4, with `task`
  dissolved into `jobs` + `snapshot` and `dispatch` represented only by
  its read half `records` while the launcher stays pinned. *Premises:*
  `task` holds five things [read: memo §1.3]; the launcher is pinned
  [read: scope]; a subject-word app produces wrong counts [read:
  `mini-app-lessons.md` §7]. Status: recommended; the owner said "we'll
  talk about task more" [read: `capability-decisions.md` D1], so this is
  the row to rule on first.
- **D-size** — The kernel proper is bounded at 2,000 lines by a gate,
  and the capability count is bounded only by the registry being closed.
  *Premises:* "keep it small; every table, command, convention needs a
  stated reason" [read: `AGENTS.md` §Ground rules]; accretion is the
  failure being replaced [read: memo §1]; a bound nobody measures is
  taste [assumed]. Status: recommended.
- **D-order** — Plan gate and vocabulary first, kernel second,
  primitives third, surface fourth, and the runner and cutover last.
  *Premises:* framework before surface [read: scope]; every unit after
  U0 must be vettable by U0's gate [this plan §3.5]; the runner needs
  `dispatch` solid and the bridge trusted [read: `capability-decisions.md`
  §Directional]. Status: recommended.
- **D-anatomy** — A capability directory is a closed shape (manifest,
  CONTRACT.md, contract.cue, module, migrations?, tests, faults, guide)
  checked in both directions, and a scaffold command writes it.
  *Premises:* closure is what made `#Context` unforgettable [read:
  `context.cue` header]; every contract ships a positive and a negative
  control [read: memo B6; `mini-app-lessons.md` §19]. Status: recommended.
- **D-fixture-repo** — The fixture capability grows a manifest-driven
  repository builder that proves its own plant, and it is the only E2E
  ground and the conformance suite for any later kernel. *Premises:*
  the conductor cannot use what it builds [read: `AGENTS.md`]; a fixture
  whose plant silently failed answers about nothing [read:
  `mini-app-lessons.md` §6]; `stores.py` already has the measured store
  shapes [read: `guide/fixtures.md`]. Status: recommended.
- **D-hooks-listeners** — Hooks are registered as listeners, not made a
  capability, because nothing injects them. *Premises:* a capability has
  one interface others call [read: memo §A]; hooks are invoked by git and
  the harness, never by a sibling [read: tree listing]. Status:
  recommended.
- **D-launcher-after** — Moving the launcher and levers under the
  framework is a separate plan after U21, gated on `records` and
  `custody` having been in service. *Premises:* the launcher is pinned
  [read: scope]; its read half is copied not moved [this plan U9]; a
  runner that cannot land is not a pipeline [read:
  `capability-decisions.md`]. Status: recommended.

---

## 12. What this plan did not do, and what it carries as risk

No code, no execution, no reading outside the snapshot and `in/`. Line
counts are from `wc -l` at this ref; nothing else was measured. The
narrow plan's `D-cuejson`, `D-iface`, `D-copy`, `D-resume-deps` and
`D-imports-json` are adopted unchanged and not restated as new.

Risks stated rather than hidden: (1) U0 may find this prose does not
survive its own gate — that is the gate working, and the fix is a
revision here, tracked. (2) The duplication window U8→U20 is real; the
byte-identity gates bound it but a change to `workflow/` during the
window must land twice, and the imports-agree check is what says so.
(3) `task`'s dissolution is the one row the owner has flagged for
discussion; U12 and U15 are the units that depend on it and nothing
before U11 does. (4) The 2,000-line bound is a first number; it is a
gate so that raising it is a decision with a diff.
