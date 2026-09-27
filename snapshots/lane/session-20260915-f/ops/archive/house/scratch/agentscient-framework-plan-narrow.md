# The mini-apps as a framework — plan

Plan for the tree at `dbbd72f3b735f01d18eb05ac12e61f85373a25d8`, from the
owner's scope of 2026-08-29: *"I want to get the mini-apps redone into a
framework - it makes sense - i like symfony, its a good example."* Symfony is
the model; nothing here is Symfony. Everything below was read from the
snapshot — the prior memo (`ops/docs/scratch/agentscient-kernel-research.md`),
the running list (`in/agentscient-mcp-tools.md`, entries to 16:45Z), the
ratification ledger (`ops/docs/scratch/capability-decisions.md`),
`workflow/store.py`, `ops/contracts/imports.{json,py}`, `vocab.cue`,
`checks/vocabulary_wall.py`. Nothing was executed. Ends in a unit list (§7)
and the new decisions, one sentence each with premises tagged (§8).

Fixed by the scope, not re-opened here: stdlib only; build beside the old
apps; the pinned launcher (`ops/devlane/dispatch/launch.py` and its levers)
untouched; E2E on the fixture repo, never the live lineage
(`AGENTS.md`: work that builds a tool never appears in the ledger it keeps);
`service` reserved for compose, the injected object is a `capability`;
units PR into `agentscient/dev`; `db` first; `ledger` (wf) renamed last,
behind a shim.

---

## 0. The claim in one paragraph

Symfony's three load-bearing ideas map onto things the lane already has one
instance of each. **The container** (`services.yaml` → a compiled graph,
injection by interface, autowiring refused when ambiguous) is `imports.json`
plus `mcp_server.py`'s registry pattern, generalised: a `capabilities.cue`
file the kernel boots from, wiring each capability's declared `deps` by
interface. **Environments** (`APP_ENV=dev|prod`, one config tree per env,
never mixed) are lanes: one `capabilities.cue` shape, one instance per lane,
which is exactly the ratified LANE-NO-BLEED rule — so `lane` returns *not*
as a per-capability field abstracted from one instance (the 2026-08-27
deferral stands) but as the container's boot parameter, the way `APP_ENV`
is not a field on every service. **Tags** (`kernel.event_listener`,
`console.command` — the compiler pass that refuses a mis-tagged service at
`cache:warmup`) are the `read`/`write` tags, and the container's one
framework-wide refusal: at boot, a `read`-tagged surface asking for a
`write` capability is a boot failure, not a runtime discovery. That turns
`test_mcp_server.ReadOnlyByConstruction` (one app, one unittest) into a
property of the container that every capability gets for free. The rest —
controllers, commands, listeners, message handlers — are the existing MCP
server, CLIs, git hooks and jobs, each renamed to the Symfony role it already
plays and made to receive its capabilities rather than import them.

---

## 1. The Symfony correspondence, held to what exists

| Symfony | here | today's single instance | what the framework adds |
|:--|:--|:--|:--|
| `services.yaml` | `capabilities.cue` | `imports.json` (`may_import` only), `jobs.json` | `id`, `module`, `deps`, `tags`, `lane`; CUE-closed; `cue vet` at the gate |
| `Kernel::boot()` / compiled container | `kernel/container.py` | `mcp_server.py` builds its own context by hand | boot from the file; resolve deps; refuse cycles, unknown ids, tag violations |
| constructor injection by interface | `deps: [{id, iface}]`, a `Protocol` per capability | `ReadOnlyContext` hands `store`, `chain`, `cas` by attribute | a capability receives objects; it never imports a sibling module |
| `APP_ENV` | `lane` (container boot argument) | none — one lane | one container per lane; the ratified "shape shared, instance not" |
| tags + compiler pass | `tags: ["read"] / ["write"] / ["surface.resource"] / ["command"] / ["listener"] / ["handler"]` | `test_mcp_server.py:141` names `wf`,`gitio`,`receipts` as forbidden | one boot-time check, framework-wide, with a fault fixture |
| Doctrine DBAL + migrations | `db` capability | `workflow/store.py` (sqlite, forward-only migrations, `read_only`) | extracted unchanged; the `ro` interface is the only one a `read` capability can be handed |
| Controller | `surface` (the MCP server) | `mcp_server.py` | one controller over `surface.resource`-tagged capabilities |
| Console command | CLI verbs | `wf.py`, `launch.py` | unchanged in this plan; `wf` becomes a command *over* `ledger` only at the rename |
| Event listener | `hooks/` | `commit-msg`, `post-commit`, `post-checkout` | registered, not rewired (out of scope beyond registration) |
| Message handler | jobs (`jobs.json`) | launcher-executed jobs | `decision.record`, `after-action` as the `memory` capability's only writers |

What is **not** carried over, said once: no autowiring by type scan (every
dep is declared — `mini-app-lessons.md` §3, absence is refused), no
service locator (a capability may not ask the container for another at
runtime; the graph is closed at boot), no lazy proxies, no bundles.

---

## 2. The container, precisely

### 2.1 `capabilities.cue` — one entry per capability

```
#Capability: {
  id!:     =~"^[a-z][a-z0-9.]*$"        // "db", "ledger", "git.ro"
  module!: string                        // "ops/devlane/<dir>/<file>.py", loaded by path
  iface!:  string                        // the Protocol name the module exports
  deps!:   [...{id!: string, iface!: string}]   // [] is a declaration
  tags!:   [...#Tag]                     // [] is a declaration
  lane!:   "dev"                         // closed enum; see D-lane (§8)
}
#Tag: "read" | "write" | "surface.resource" | "command" | "listener" | "handler"
#Registry: { capabilities!: [...#Capability], ... }   // ids unique; deps resolve; acyclic
```

The relational invariants (unique ids, every dep resolves, acyclic, the
read/write rule) live in the CUE as the "general layer" the 2026-08-27
architecture reserved for composition and cross-cutting invariants; the
per-capability guarantees stay in each app's own contract.

`imports.json` is **not** replaced in this plan: it is the app-level graph
the CI gate reads, and two registries drift (`mini-app-lessons.md` §8). A
check asserts they agree — every `deps` edge in `capabilities.cue` maps to
a declared `may_import` edge between the modules' apps, or to a same-app
edge — until `imports.json` folds into the CUE set "as touched"
(ratified 2026-08-27). That fold is a follow-on, not a unit here.

### 2.2 Boot

`kernel/container.py` (stdlib: `importlib.util`, `tomllib` is not enough —
CUE is read as the JSON `cue export` writes; see D-cuejson §8):

1. Load the registry JSON; refuse an absent key anywhere (never default).
2. Filter by `lane`; refuse if any dep crosses lanes.
3. Topologically order; refuse a cycle by naming it.
4. **Tag rule, before any module is loaded:** for each capability tagged
   `read` (or `surface.resource`, which implies `read`), walk its deps
   transitively; if any is tagged `write`, refuse with `{surface, path}`.
5. Load each module by the declared path (an `importlib` from a registry
   value, not a literal — `imports.py` sees no edge, which is the point),
   call its `build(deps: dict[str, object], lane: str)` and keep the result
   under `id`.
6. Assert the built object satisfies the declared `iface` (a
   `typing.Protocol`, checked with `runtime_checkable` for method presence;
   behaviour is the capability's own suite's job).

The container is immutable after boot. `container.get(id)` exists for the
composition root (the controller, a CLI `main`) only; the gate in §2.3
refuses it inside any capability module.

### 2.3 The framework-wide gate

One registered check (`ci: true`, in `gate-kinds/`), three assertions,
each with a positive control and a fault fixture that must draw the named
refusal (`AGENTS.md` §A check must fire):

- `tag-flow`: no `read` surface reaches a `write` capability (the boot
  rule, run statically over the registry so CI catches it without booting).
- `no-sibling-import`: a capability module imports nothing under
  `ops/devlane/` except its own app; every cross-capability reach is a `deps`
  entry (AST walk, reusing `imports.py`'s edge finder).
- `no-locator`: no capability module names `container` or `get(` on the
  kernel; only composition roots may.

This is the memo's U2, moved from `imports.py` into the container's
property, as the running list 16:35Z entry asked.

---

## 3. Vocabulary — `capability` in, `service` walled

`vocab.cue` today asserts the reserved terms are *present* in the observed
literals (`_has_wf!: true` etc.); the wall check has a `RESERVED` list and
an allowlist. Two additions, both to existing files:

- `capability` joins `RESERVED` in `checks/vocabulary_wall.py` and gains a
  `_has_capability!` row in `vocab.cue` (extractor `extract/vocab.py`
  regenerates `obs/vocab.json`; `faults/vocab.4.json` is the fault that omits
  it).
- `service` is reserved **outside `.dev/infra/`**: a second pattern set in
  the wall with its own allow-prefix (`.dev/infra/`, compose files), refused
  under `ops/devlane/`, `ops/docs/`, `ops/process/` and root dev-lane files.
  Measured claim from the running list (16:45Z): `service` is absent from
  `.dev/app` outside tests/infra — the tests author re-measures before
  pinning; a hit is a rename in the same unit, not an allowlist entry.

The wall's docstring and `AGENTS.md`'s vocabulary sentence must name the
same surfaces; the test that enforces that agreement already exists
(`test_vocabulary_wall.py`) and is the one to extend.

---

## 4. The capabilities, in build order

| id | module (new, beside the old) | iface | deps | tags | extracted from |
|:--|:--|:--|:--|:--|:--|
| `db` | `ops/devlane/db/{store,migrate}.py` | `DbRW`, `DbRO` | [] | `write` (RW), `read` (RO) | `workflow/store.py` verbatim; `Store(read_only=True)` becomes the `DbRO` build |
| `ledger` | `ops/devlane/ledger/{chain,cas,receipts,query,canonical}.py` | `LedgerRW`, `LedgerRO` | `db` | `write`/`read` | `workflow/*` — copies first; `wf.py` keeps importing its own until the rename |
| `memory` | `ops/devlane/memory/{entries,resume}.py` | `MemoryRO` + handlers | `db:DbRW` (handlers), `db:DbRO` (resume), `ledger:LedgerRO` | `read` (resume), `handler` (record/after-action) | new; entry kinds decision/rule/lesson per running list 16:25Z |
| `dispatch.query` | `ops/devlane/dispatch/query.py` | `DispatchRO` | [] (files only) | `read`, `surface.resource` | the read paths of `launch.py` (`_status`, records dir, `state.json`, `exit`, `TRIPPED.md`) **copied**, not moved — launcher untouched |
| `contracts` | `ops/devlane/contracts/vet.py` (wrapper) | `Certify` | `git.ro` | `read` | `workflow/contracts/vet.py` + `ops/contracts/imports.py` registered as one capability |
| `git.ro` | `ops/devlane/gitro/gitro.py` | `GitRO` | [] | `read` | new; allowlisted read subcommands (`rev-parse`, `rev-list`, `merge-base`, `ls-tree`, `show`, `status --porcelain`); test proves `commit`/`fetch`/`update-ref`/`push` unreachable |
| `telemetry` | `ops/devlane/telemetry/query.py` | `TelemetryRO` | [] | `read`, `surface.resource` | `pulse.py`/`usage.py` reads; `breaker.py` stays where the launcher loads it |

`db` is first because everything else is either over it or reads files.
Its contract is `store.py`'s docstring (cache with a rebuild command;
forward-only numbered migrations recorded with the digest; a changed
applied file is an integrity failure; a reader cannot create the file it
reads) — the tests are authored from that text and from `cue/db.cue`, not
from the implementation. "Postgres by definition" means `DbRW`/`DbRO` name
no sqlite type; the sqlite build is the only build.

### 4.1 `memory` — decision/rule/lesson with premises, and `resume`

Not a new store: three entry kinds in `db` under a migration
`0002_memory.sql` owned by the `memory` capability (schema written as CUE
in `memory/contract.cue`, the SQL generated at the migration gate — see
D-cuesql §8; until that generator exists the SQL is hand-written and the
CUE is the shape it must satisfy).

- `decision`: owner's words verbatim, date, `premises: [{text, tag:
  measured|read|memory|assumed, source}]`, `status: standing|revisit|
  superseded`, `supersedes?`.
- `rule`: origin (the correction that produced it), enforcing gate (a
  check id), date.
- `lesson`: measured after-action — the incident, the measurement, the
  lesson; the form `mini-app-lessons.md` already keeps.

Writers are handlers only (`memory.record` for decision/rule,
`memory.after_action` for lesson), executed through the launcher as jobs;
no MCP write. `resume(lineage, stage)` composes `ledger` board state (from
`dispatch.query` once it is a dep — D-resume §8 says which) + standing
decisions + rules + open `revisit` decisions into the handoff packet. The
positive E2E fixture is `handoff/HANDOFF-fable-2026-08-29.md` regenerated
from entries (running list 16:25Z); the negative is an entry whose
premise source is absent → refused, never `assumed` by default.

A premise's `tag` is the reader's honesty about *how* it knows; a
falsified premise flips `status` to `revisit` by a handler, never by hand
in the DB. That is the owner's "what if you're wrong and I answer without
realising" question, made a column.

### 4.2 `ledger` — the rename, last, with a shim

`wf` is the ledger (running list 15:55Z). The plan never edits
`workflow/`'s behaviour: `ledger/` starts as copies that the container
wires, `wf.py` keeps its own imports, both suites run. The final unit
renames the registry id (`wf` resources served as `ledger://…`, `wf://…`
kept as aliases for one release), then the directory, and leaves
`ops/devlane/workflow/wf.py` as a shim that `execv`s `ledger/wf.py`. The
byte-identity test from the memo's U4 (`wf_*` bodies unchanged) is the
gate for the rename.

---

## 5. The composition roots

- **Controller (`surface`)** — `ops/devlane/surface/mcp.py`: `mcp_server.py`'s
  `handle`/`serve`/`resources`/`TOOLS` shape, but it boots the container
  and asks for every `surface.resource`-tagged capability; resource URIs
  `<id>://<name>`; tool names `<id>_<name>`; the tools/list cap
  (2026-08-21) is a registry invariant (`len(surface.resource) ≤ N` in
  CUE). It imports no app by name — the `no-sibling-import` gate applies
  to it too. `mcp_launch.py`'s prepare-then-`execv` split stays. `.mcp.json`
  is repointed only in the last unit (§7 U9), after `wf://` byte-identity.
- **Commands** — untouched: `wf.py`, `launch.py` keep their imports. They
  are *registered* (tag `command`) so the registry is complete, which is
  the only claim made about them.
- **Listeners** — `hooks/` registered (tag `listener`); no rewiring.
- **Handlers** — jobs: `memory.record`, `memory.after_action` join
  `jobs.json`; the launcher runs them as it runs any job. The launcher is
  not edited; a job entry is data.

The composition root is the only place `container.get` appears. E2E =
boot the container against the fixture repo (`fixtures/stores.py`'s
pattern, extended with synthetic dispatch records, a `db` file built by
migration, and three memory entries), serve `ledger://status`,
`dispatch://board`, `memory://resume`, compare to golden bodies.

---

## 6. What is refused, framework-wide (the contract the tests come from)

| refusal | drawn when | control |
|:--|:--|:--|
| `capability.unknown` | a dep names an id not in the registry | fault registry |
| `capability.cycle` | topological order impossible; names the cycle | fault registry |
| `capability.absent-key` | any `#Capability` key missing (`deps: []` is a value; no key is not) | fault registry |
| `tag.write-into-read` | a `read`/`surface.resource` capability transitively depends on a `write` one | fault registry + the static gate |
| `lane.cross` | a dep's `lane` differs | fault registry (needs a second lane value only in the fixture — D-lane) |
| `iface.unsatisfied` | the built object lacks a Protocol method | fault module |
| `import.sibling` | a capability module imports another app under `ops/devlane/` | fault module |
| `locator.inside-capability` | a capability module names the container | fault module |
| `vocab.service-outside-infra` | `service` under a non-infra surface | fault doc |
| `memory.premise-unsourced` | a premise with no `source` or a tag outside the four | fault entry |

Every refusal is a named string in `kernel/errors.py` reusing
`workflow/errors.py`'s `Refusal(claim, actual=, needed=)` shape — copied,
not imported, because `kernel` may not reach into `workflow`.

---

## 7. Units, each a PR into `agentscient/dev`

Each unit runs the pipeline (`pipeline.md`: plan → tests by a
non-implementing harness → skeptic → code → two reviews). The tests for a
unit are authored from the contract column, never from the code named in
"extracted from". One lineage per unit.

| # | unit | deliverable | tests authored from | needs |
|:--|:--|:--|:--|:--|
| U0 | vocabulary | `capability` reserved; `service` reserved outside `.dev/infra/`; `vocab.cue` + fault; wall docstring ↔ `AGENTS.md` agreement | §3; `AGENTS.md` vocabulary paragraph | — |
| U1 | `db` | `ops/devlane/db/` from `store.py` verbatim; `DbRW`/`DbRO` Protocols; `build(deps, lane)`; migration discipline suite ported; `read_only` becomes the RO build; `imports.json` row `db: []` | `store.py` docstring; `cue/db.cue` | — |
| U2 | registry + container | `capabilities.cue` + `#Registry`; `kernel/container.py` boot; refusals of §6 rows 1–6 with fault registries; `db` the only entry | §2.1, §2.2, §6 | U1 |
| U3 | container gate | `tag-flow`, `no-sibling-import`, `no-locator` as one registered check, `ci: true`; fault modules; the `imports.json` agreement check | §2.3 | U2 |
| U4 | `ledger` (copies) + `git.ro` | `ledger/` wired over `db`; `gitro.py` allowlist proved; both registered; `wf.py` untouched | `workflow/query.py` docstring; `mcp_server.py` promises; memo D4 | U2 |
| U5 | `dispatch.query` + `telemetry` | read layers as `surface.resource`; `_status` behaviour reproduced against the fixture records, launcher untouched | `dispatch/CONTRACT.md` §The record, §Watching; `telemetry.md` | U2 |
| U6 | `surface` controller | container-driven MCP; `wf://` byte-identical to today's server on the fixture repo; `agentscient://apps` lists the registry; E2E harness | `mcp_server.py` docstring; `mcp.cue` | U3, U4, U5 |
| U7 | `memory` | entry kinds + `0002_memory.sql` (CUE shape first); `record`/`after_action` handlers as jobs; `resume`; HANDOFF fixture regenerated | §4.1; running list 16:05Z/16:25Z; `DECISIONS.md` form | U4, U5 |
| U8 | `contracts` | `vet.py` + `imports.py` registered as one `read` capability over `git.ro`; no behaviour change | memo B6; `contracts/CONTRACT-NOTES.md` | U4 |
| U9 | rename `wf`→`ledger` | registry id, `ledger://` with `wf://` aliases, directory move, `wf.py` shim; `.mcp.json` repointed; byte-identity gate | §4.2 | U6, U7, U8 |

Order: U0 ∥ U1 → U2 → U3 → (U4 ∥ U5) → U6 → (U7 ∥ U8) → U9. U6 is the
first unit the conductor feels; U1 is the first unit that lands.

Cost the pipeline pays per unit: the tests author cannot run python
(handoff §4), so each unit names what the conductor measures — U1: the
ported `test_store.py` green against `db/`; U2/U3: every fault draws its
named refusal and the clean registry boots; U6: `diff` of `wf://` bodies
old vs new = empty on the fixture repo; U9: same diff after the move.

---

## 8. New decisions only — one sentence each, premises tagged

Ruled already and not re-asked: capability as the axis (§A, owner), evidence
shared per lane (D2), snapshot split (D3), lane deferred as a field,
two-level CUE architecture, `service`/`capability` vocabulary, `wf`→`ledger`
last with a shim, memory as ledger entry kinds, `db` first.

- **D-lane** — `lane` appears once, as the container's boot argument and a
  closed one-value enum in `#Capability`, not as a shape abstracted from
  two instances. *Premises:* the 2026-08-27 deferral forbids abstracting a
  field from one instance [read: `capability-decisions.md`]; the scope
  says "lanes = environments" [read: scope]; Symfony's `APP_ENV` is a
  kernel parameter, not a per-service field [memory: Symfony docs, not in
  tree]. Recommendation: accept; the fault fixture for `lane.cross` uses
  a fixture-only second value and is the only place two lanes exist.
- **D-cuejson** — the container reads `capabilities.json` exported from
  `capabilities.cue`, committed beside it, with a check that the export is
  current. *Premises:* stdlib only, so no CUE parser [read: scope]; the
  workflow contracts already pair `cue/` with JSON `examples/`/`obs/`
  [measured: `contracts/` listing]; `cue vet` validates JSON against the
  `.cue` [read: memo §2.1]. Recommendation: accept.
- **D-cuesql** — the CUE→SQL migration generator is a follow-on; U7 ships
  hand-written `0002_memory.sql` with `memory/contract.cue` as the shape it
  must satisfy. *Premises:* the running list names "CUE → SQL migrations at
  the migration gate" as the target [read: 16:35Z]; `store.py`'s migration
  discipline records the digest of the file applied, so a generated file
  must be deterministic before it can be trusted [read: `store.py`
  docstring]; no generator exists [measured: tree]. Recommendation:
  accept; make the generator its own unit after U9.
- **D-copy** — `ledger`, `dispatch.query`, `telemetry` start as copies
  wired by the container while the originals keep running, and the copies
  become canonical only at U9. *Premises:* "build beside the old apps" and
  "pinned launcher untouched" [read: scope]; `wf.py` imports `store` by
  name (`wf.py:46`) so a move breaks it [measured]; `launch.py` holds
  `_status` beside its writers [read: memo §1]. Recommendation: accept;
  the duplication window is U4→U9 and the byte-identity test bounds it.
- **D-iface** — interfaces are `typing.Protocol` classes checked for method
  presence at boot; behaviour is the capability suite's job. *Premises:*
  stdlib only [read: scope]; `runtime_checkable` verifies presence, not
  signatures [memory: Python docs]; the lane's rule that a contract cannot
  constrain what nobody extracts [read: `mini-app-lessons.md` §4].
  Recommendation: accept.
- **D-resume-deps** — `memory.resume` depends on `dispatch.query` (files)
  and `ledger:LedgerRO`, so the handoff packet is built from the record
  store and the ledger, not from a copy of either. *Premises:* board state
  is a pure read over `.dev/records/dispatches/*.json` [read: memo §3];
  `resume` = board + running + open decisions [read: running list #14];
  the read/write rule allows a `read` capability to depend on `read`
  capabilities only [this plan §2.2]. Recommendation: accept.
- **D-imports-json** — `imports.json` stays the CI gate's input and a check
  asserts it agrees with `capabilities.cue`, until it folds into the CUE
  set. *Premises:* two registries drift [read: `mini-app-lessons.md` §8];
  the fold is ratified as incremental "as touched" [read:
  `capability-decisions.md`]; `imports.py` is `ci: true` today [read:
  memo §1]. Recommendation: accept; the fold is the first unit after U9.
- **D-surface-name** — the controller app is `surface`; `agentscient` names
  the framework, `kernel` the container package. *Premises:* memo D1 left
  the name open [read]; "harness" taught that a subject-word for an app
  produces wrong counts [read: `mini-app-lessons.md` §7]; `surface` is the
  running list's own column word [read]. Recommendation: accept, or the
  owner names it in U2 before any path literal binds it.

## 9. What this plan did not do

No code, no execution, no reading outside the snapshot and `in/`. The
running list's measured claim that `service` is absent from `.dev/app`
outside tests/infra is carried as *read*, not re-measured. The
`telemetry` read split (which of `pulse.py`/`usage.py` is pure) is the
U5 tests author's to establish from `telemetry.md`. `task`'s fate (D1 in
the ratification ledger) stays open and nothing here depends on it.
