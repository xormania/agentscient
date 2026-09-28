# U2 — the registry contract: child plan `agentscient/U2`

Plan for the tree at `c4bb3c081c905f96e73b375fe14dac5226acbacd`, from the
owner's scope of 2026-08-31: *"launch U2"*, appended to the parent scope of
2026-08-29. Everything here was read from the snapshot and `in/`; nothing
was executed. Parent: `ops/capabilities/agentscient.plan.json`, row `U2`;
prose parent `ops/docs/scratch/agentscient-framework-plan.md` §7 row U2,
§2.2 (anatomy), §2.3 (registry, boot refusals), as ratified by
`ops/docs/scratch/agentscient-framework-ratification.md`. The five gating
decisions stand and are carried without re-argument; the one `revisit` row
(D-new-2) is ruled here (§2).

This plan is written so the independent tests stage (pipeline row 3) needs
nothing but this document and the contract prose it names. Acceptance
criteria in §7 are stated as observable behaviours with named refusals,
never as "the code does what the plan says".

Vocabulary note, load-bearing for every artifact this plan names: the
prod-lane reserved term for the boot-and-registry program is not used
anywhere below; the framework's runtime is the **container**
(`ops/capabilities/container/`), matching the landed root sidecar and the
wall check (`vocabulary_wall.py`, `vocab.kernel-outside-homes`). See §10.

---

## 1. Position — what is landed, what this unit stands on

Measured from the tree (tag: `read`, sources inline):

- **U0 is landed** at stage `check`: `contracts/plan.cue`,
  `checks/plan_vet.py` (vet / extract / faults), an 18-fault corpus,
  `agentscient.plan.json` and the child `plans/U0.plan.json` +
  `U0.plan.md`. The relational rules U2's sidecar must satisfy are code,
  not prose: parent digest binding (`plan.stale-parent`), verbatim
  projection of the parent row (`plan.deliverables-mismatch`), settled
  carry (`plan.settled-dropped`), scope append form (`plan.scope-drift`),
  and `plan.stage-blocked` — no unit at `code` while any decision is
  `pending`/`revisit`.
- **The vocabulary wall is landed** (`ops/devlane/workflow/checks/
  vocabulary_wall.py`): the prod-lane term is refused in file contents
  *and path components* on every dev-lane surface outside the homes
  (`.dev/infra/`, `ops/docs/scratch/`, `.dev/handoffs/`,
  `.dev/records/`, `.git/`). `ops/capabilities/**` is a walled surface.
- **The shared refusal type exists**: `ops/capabilities/container/
  errors.py`, `Refusal(claim, expected=, actual=, needed=)`, imported by
  `plan_vet.py`.
- **Check registration is data**: rows `{name, class, argv, ci}` in
  `ops/devlane/workflow/gate-kinds/artifact.json`; CI derives its matrix
  from the registry (`ci-dev.yml` job `discover`), so a registered
  `ci: true` row runs on every PR with no workflow edit. The CI runner is
  **cue-free** (stated in `plan_vet.py`'s economics note; only ruff gets
  an install step today).
- **Parent row U2** (root sidecar): deliverables
  `[{path: "ops/capabilities/contracts/capabilities.cue", interface:
  {declared_absent: "specified by framework plan §7 U2"}}]`, needs
  `["U0"]`, stage `plan`. The prose row names more: `capability.cue`
  (anatomy), examples, faults, `registry-vet` + `anatomy` checks
  registered. §7 W0 resolves that gap by amendment, not by a child that
  under-declares.
- **Root sidecar carries D-new-2 at `status: revisit`** — which, via
  `plan.stage-blocked`, forbids moving *any* root unit (including U2) to
  `code` until the decision is settled and the root amended. Settling it
  is therefore not optional preamble; it is the first gate on the unit.

Carried verifications (`ops/conductor/handoff/evidence-2026-08-29/
verifications-u2u3.md`, tag `read`): V1 (`get_protocol_members` is 3.13;
lane pins 3.12.14), V4 (CUE list-element closedness is undocumented — the
"extra key inside `[...#Capability]` is refused" claim must be proven by a
negative fixture in U2, and the export digest is pinned to the lane's cue
0.14.1; a cue bump is a digest-changing event by policy).

---

## 2. The D-new-2 ruling — interface members are declared in the manifest

**Ruling (D-U2-iface-manifest, supersedes D-new-2): every interface a
capability exports is declared in its manifest as a name plus an explicit
member list, verified against the implementation in both directions — the
3.12.14 pin stands.** The statically-checkable half (declaration ↔
`Protocol` source, via `ast`) is U2's anatomy check; the runtime half
(declaration ↔ built object, member presence) is U3's boot step 6 and is
*specified* here, not built.

Premises, tagged for the ratify gate:

1. `measured` — the lane pins Python 3.12.14; `get_protocol_members` /
   `is_protocol` are 3.13 additions and are not on the lane
   (ratification D-new-2 row; V1 in `verifications-u2u3.md`).
2. `read` — the ratification text already leans this way: "arguably the
   better design, since it makes the interface a declared contract rather
   than an introspected one" (`agentscient-framework-ratification.md`,
   D-new-2 row).
3. `read` — D-language (standing) requires the CUE to say nothing
   Python-specific so a later Rust container is written from the same
   contracts (framework plan §2.4). A Rust container cannot introspect a
   Python `Protocol` under any pin; a declared member list is the only
   form both containers can read. Moving to 3.13 buys nothing portable.
4. `read` — the framework's one central idea is that everything the
   container knows is known before the first capability runs (framework
   plan §1, closing paragraph). Introspection discovers; a manifest
   declares. `@runtime_checkable` checks member *presence* only anyway
   (V1), so introspection would not even yield a stronger check.
5. `read` — the pin is owner-adjacent policy (the lane image), and
   nothing else in U2–U4 needs 3.13; spending a lane-image change to
   avoid writing a member list is cost without yield
   (`AGENTS.md` §Keep it small, via root settled `stdlib-only`).

The rejected alternative — move the lane pin to 3.13 and enumerate via
`get_protocol_members` — fails premises 3 and 4 outright and is not
reconsidered below.

Consequence in the schema (§3): `#Capability.iface` and the manifest's
`iface` become `[#Iface, ...#Iface]` with
`#Iface: close({name!: #NonEmpty, members!: [#NonEmpty, ...#NonEmpty]})`.
`deps` entries name the interface they receive (`{id!, iface!}` as in the
parent §2.3), and a dep's `iface` must resolve to a declared `#Iface.name`
on the dep's row — checked by `registry-vet`.

Both directions, concretely (this is what the tests stage authors
against): a member declared in the manifest but absent from the named
`Protocol` class body draws `anatomy.member-missing`; a method or
annotated attribute on the `Protocol` class body not declared in the
manifest draws `anatomy.member-undeclared`. Dunder names and private
(`_`-prefixed) names are outside the declared surface and ignored in the
undeclared direction.

Sequencing consequence (§7 W0): on ratification of this ruling, the root
sidecar's D-new-2 row flips `revisit → superseded` in the same amendment
that expands the U2 row; until that lands, no U2 work may be recorded at
stage `code` (that is `plan.stage-blocked` doing its job, not an
obstacle to route around).

---

## 3. The contract package — what U2 delivers under `contracts/`

All CUE in `package agentscient`, in the lane's `cue/` + `examples/` +
`faults/` form, doctrine as U0 set it: raw-presence before `cue vet -c`,
positive control, negative control, planted fault proven to differ from
the clean example.

### 3.1 `contracts/outcome.cue` — the four-class taxonomy and the refusal shape

```
#OutcomeClass: "rejection" | "denial" | "abort" | "finding"
  // rejection: malformed input or breached precondition; nothing commits.
  // denial:    a well-formed submission the deciding authority declines —
  //            a SUCCESSFUL execution, recorded as one, never routed
  //            through error handling.
  // abort:     infrastructure failure; nothing commits, no partial records.
  // finding:   on verification paths, an item the checks cannot process —
  //            first-class, never skipped, recorded rather than absent.

#Refusal: close({
  name!:   =~"^[a-z][a-z0-9-]*(\\.[a-z][a-z0-9-]*)+$"   // e.g. "registry.cycle"
  class!:  #OutcomeClass
  remedy!: #NonEmpty        // what would satisfy the check; part of the contract
})
```

`remedy` is required — a refusal without one does not vet. This is the
looplaw "refusals are protocol, not UX" rule as schema
(`ops/conductor/looplaw-findings.md` §2); the lane's
`Refusal(claim, expected=, actual=, needed=)` already carries the remedy
as `needed`, so the Python side is an extension, not a rework (§5.3).

### 3.2 `contracts/capabilities.cue` — the registry

The parent §2.3 shape, amended by §2 above and by the taxonomy:

```
#Iface: close({name!: #NonEmpty, members!: [#NonEmpty, ...#NonEmpty]})

#Capability: close({
  id!:     =~"^[a-z][a-z0-9]*(\\.[a-z][a-z0-9]*)*$"
  layer!:  0 | 1 | 2
  module!: string                      // a string the container interprets;
                                       // no language-specific path grammar
  iface!:  [#Iface, ...#Iface]
  deps!:   [...close({id!: #NonEmpty, iface!: #NonEmpty})]
  tags!:   [...#Tag]
  stores!: [...#NonEmpty]
  serves!: [...#NonEmpty]
})
#Tag: "read" | "write" | "surface.resource" | "command" | "listener" |
      "handler" | "migrates"
#Registry: close({capabilities!: [...#Capability]})
```

Plus the registry layer's own enumerated check list, the vocab-wall
pattern (`#WallReserved` in `ops/devlane/workflow/contracts/cue/vocab.cue`)
applied here: `#RegistryRefusals` is a closed map from refusal name to
`#Refusal`, and **that map is the test manifest** — §3.4's coverage rule
holds the fault corpus to it.

Relational rules that are `registry-vet`'s (Python, §5.1) because CUE
cannot state them or `cue-aar-equality.md` says not to trust that it can:
ids unique; every `deps[].id` resolves to a row; every `deps[].iface`
resolves to a declared `#Iface.name` on that row; `dep.layer < layer`;
the dep graph is acyclic; `serves` names globally unique; the committed
export is current. Tag-flow (read never transitively reaching write) is
**U4**, per the parent §2.5 row split — U2 must not half-build it.

`capabilities.json` is the committed export the container reads
(D-cuejson, carried). U2 commits the live export with
`capabilities: []` — empty is a *declaration* (parent §2.2: absent is
refused, empty is stated) — plus the currency digest, so `registry-vet`
has a real target from its first day. Currency: the export file carries
the sha256 of the canonical `cue export` of the vetted source; the digest
is pinned to the lane's cue 0.14.1 and a cue bump is a digest-changing
event by policy (V4).

### 3.3 `contracts/capability.cue` — the anatomy

The parent §2.2 directory shape as a closed record, checked in both
directions (missing entry refused by name; unnamed entry refused —
closure), plus the manifest shape:

```
#Manifest: close({
  id!: ..., layer!: ..., module!: ..., iface!: [#Iface, ...#Iface],
  deps!: ..., tags!: ..., stores!: ..., serves!: ...      // = #Capability
  refusals!: [...#Refusal]     // every refusal this capability's contract
                               // draws, classified, remedy-bearing
})

#Anatomy: close({
  "capability.json"!: true, "CONTRACT.md"!: true, "contract.cue"!: true,
  module!: #NonEmpty,          // "<id>.py"
  "migrations/"?: true,        // required iff "migrates" ∈ tags
  "tests/"!: true, "faults/"!: true, "guide.md"!: true
})
```

The `refusals` field on the manifest is where looplaw requirement 1 lands
per capability: every refusal in the four classes, none a generic error,
each with a remedy. `CONTRACT.md`'s refusals section and
`contract.cue` name the same set; the anatomy check compares (§5.2).

`#AnatomyRefusals` — the anatomy check's own enumerated refusal map, same
pattern as `#RegistryRefusals`.

### 3.4 The undemonstrated-gate rule — where looplaw requirement 3 lands

Two layers, both delivered in U2:

1. **The framework's own checks.** Every name in `#RegistryRefusals` and
   `#AnatomyRefusals` must be drawn by at least one committed fault
   fixture; each check ships a `faults` subcommand (the `plan_vet.py
   faults` precedent) that (a) vets the clean example, (b) proves every
   fault differs from its source, (c) proves every fault draws exactly
   its meta-named refusal, and (d) **refuses any enumerated refusal no
   fault draws** — `registry.undemonstrated` / `anatomy.undemonstrated`,
   class `finding`. An undemonstrated gate is an unproven behaviour; the
   check list is the test manifest, structurally.
2. **Every future capability.** The anatomy check enforces that
   `faults/` contains at least one negative control per refusal declared
   in the manifest's `refusals` list. A capability that declares a
   refusal and ships no demonstration is refused at the same gate that
   reads its directory. This is the rule the parent §2.2 stated for
   `CONTRACT.md` refusals, generalized to the classified list and made
   name-addressable.

### 3.5 Where looplaw requirement 1's *semantics* land, and the seam left

Declaring the classes is U2's; enforcing their runtime semantics is not.
The seam, stated so U3+ can be planned against it: container boot
refusals (parent §2.3 steps 1–6) are class `rejection` except
module-load/env failures (`abort`); a built capability *declining* a
well-formed call is a `denial` and the container must hand it back as a
recorded success, never an exception path; verification paths
(`registry-vet`, `anatomy`, later `certify`) emit `finding` for what they
cannot process instead of skipping it. The envelope's
`status` vocabulary (looplaw's "replace `ok | invalid | tripped`")
belongs to the launcher/records contract, which is **pinned** — see
finding F5 in §12; U2 provides the vocabulary that adoption will import
and changes nothing under the launcher.

---

## 4. Where each looplaw requirement lands — the summary table

| requirement (`ops/conductor/looplaw-findings.md`) | lands in U2 as | enforced by |
|:--|:--|:--|
| four-class taxonomy; none a generic error | `#OutcomeClass` + doc'd semantics (`outcome.cue` §3.1); `#Manifest.refusals` classified (§3.3); U2's own checks classify every refusal they emit | `cue vet` over manifests; `errors.Refusal` outcome field (§5.3) |
| a Denial is a successful execution, recorded | class semantics in `outcome.cue` comments + the §3.5 seam specification for U3's container | U3 (specified here, built there) |
| a Finding is first-class, never skipped | `finding` class; vacuous-scan honesty (§5.2); `*.undemonstrated` are findings | anatomy + registry-vet output contract |
| refusals as structured protocol carrying a Remedy | `#Refusal.remedy!` (§3.1); `errors.Refusal` maps `needed` → remedy and gains `outcome` (§5.3) | `cue vet`; both checks' unit suites |
| undemonstrated gate = unproven behaviour | §3.4 both layers: `faults` subcommand coverage + per-capability `faults/`-per-refusal | `registry-vet faults`, `anatomy faults`, anatomy directory pass |

---

## 5. The checks

### 5.1 `checks/registry_vet.py` — registered `registry-vet`

Subcommands `vet <registry.json>` and `faults`. `vet`, in order, first
failure only, every refusal drawn as `errors.Refusal` with an outcome
class and the enumerated name from `#RegistryRefusals`:

1. raw-presence: JSON object; every `#Registry`/`#Capability` key stated
   (`registry.absent-key`, rejection) — before CUE, because `cue vet -c`
   cannot prove a key was stated (`mini-app-lessons.md` §12, carried via
   U0);
2. `cue vet -c -d #Registry` against `capabilities.cue`
   (`registry.contract`, rejection); a missing `cue` binary is
   `registry.cue-unreachable`, class **abort** — the check refuses
   loudly, it never reports clean unrun (the lint-gate precedent in
   `ci-dev.yml`);
3. relational (§3.2 list): `registry.duplicate-id`,
   `registry.unknown-dep`, `registry.unknown-iface`, `registry.layer`,
   `registry.cycle` (the cycle is named in the message),
   `registry.serves-duplicate` — all rejections;
4. currency: recompute the export digest, compare
   (`registry.stale-export`, rejection).

`faults` implements §3.4 layer 1 over `contracts/examples/registry.json`
and `contracts/faults/registry.*.json` + `.meta.json`.

### 5.2 `checks/anatomy.py` — registered `anatomy`

Subcommands `vet [DIR ...]` (default: every directory under
`ops/capabilities/capabilities/`) and `faults`. Per directory:

1. directory closure both ways against `#Anatomy`: `anatomy.missing`,
   `anatomy.extra` (rejections);
2. manifest: `capability.json` raw-presence + `cue vet -c -d #Manifest`
   (`anatomy.manifest`, rejection; `anatomy.cue-unreachable`, abort);
3. `migrates` ∈ tags ⇒ `migrations/` present and non-empty
   (`anatomy.migrates-empty`, rejection);
4. iface both-ways member check via `ast` over the module named `module`
   (§2): `anatomy.member-missing`, `anatomy.member-undeclared`
   (rejections); a module that does not parse is `anatomy.unparsed`,
   class **finding** (an item the check cannot process — recorded, never
   skipped);
5. refusal demonstration (§3.4 layer 2): every `refusals[].name` in the
   manifest has ≥1 fixture under `faults/`
   (`anatomy.undemonstrated`, finding).

**Vacuous-scan honesty:** at U2 the real `capabilities/` is empty. The
check reports `0 capability directory(ies) scanned — none was looked at`
and exits 0 — it must never print "clean" over nothing. This is the
vocabulary wall's own lesson (`vocabulary_wall.py` lines 176–185),
carried; it is also the `finding` doctrine applied to the check's own
output. The check is proven against fixture directories (§6.2), not
against the empty tree.

### 5.3 `container/errors.py` — the Refusal carries its class

`Refusal` gains a required `outcome` field constrained to the four class
strings; `needed` is documented as the remedy and surfaces as such in
`str()`. `plan_vet.py`'s call sites are classified in the same change —
mechanically: `plan.cue-unreachable` → abort; the `faults()` runner's
`plan.fault-*` refusals → finding; everything else → rejection. U0's
suite (`tests/test_plan*.py`) green, unchanged in assertion content
except where it pins `Refusal`'s constructor/rendering, is the regression
gate: this is an amendment to a landed artifact and rides on its own
tests, not on trust.

### 5.4 Registration and CI

Two rows appended to `ops/devlane/workflow/gate-kinds/artifact.json`
`checks[]` (the only `ops/devlane/` edit besides nothing — parent §8 allows
exactly registration rows):

```
{"name": "registry-vet", "class": "policy",
 "argv": ["python3", "ops/capabilities/checks/registry_vet.py", "vet",
          "ops/capabilities/capabilities.json"], "ci": true},
{"name": "anatomy", "class": "policy",
 "argv": ["python3", "ops/capabilities/checks/anatomy.py", "vet"], "ci": true}
```

The CI matrix picks them up with no workflow edit (`ci-dev.yml` job
`discover`). The runner is cue-free, so `ci-dev.yml` gains one
conditional install step for the pinned cue 0.14.1, the exact shape of
the existing ruff step (`if: matrix.check == 'registry-vet' || matrix.check
== 'anatomy'`). Without it both checks would be red-by-abort in CI —
which is the *correct* failure (loud, classified), and the install step
is what turns it green rather than any silent skip.

---

## 6. Examples and fault corpus — a contract without firing faults is presumed to enforce nothing

### 6.1 Examples (positive controls)

- `contracts/examples/registry.json` — a clean registry with two fixture
  rows exercising every field: a layer-0 row with `migrates` and two
  ifaces, a layer-1 row depending on one of them by name.
- `contracts/examples/registry.empty.json` — `{"capabilities": []}` with
  a current digest: the live export's shape, proven vettable.
- `contracts/examples/anatomy/goodcap/` — a complete fixture capability
  directory: manifest with classified remedy-bearing refusals, a module
  whose `Protocol` bodies match the declared members exactly, one
  migration, one fault fixture per declared refusal.

### 6.2 Faults (negative controls)

One per enumerated refusal, minimum — the coverage rule (§3.4) makes the
minimum a gate, not an aspiration. Registry faults are
`registry.N.json` + `registry.N.meta.json` (`from`, `change`,
`violates`, `reject_path`, the U0/vocab meta form); anatomy faults are
fixture directories with the same meta sidecar. The corpus, by name:

| # | plants | must draw |
|:--|:--|:--|
| R1 | a `#Capability` element with an extra key `notes` | `registry.contract` — **this is V4's negative fixture**: list-element closedness is undocumented upstream and is hereby proven, not assumed; if this fault does NOT fire, the finding goes to the conductor and the closure moves to the raw-presence pass |
| R2 | `deps` key deleted from a row | `registry.absent-key` (absent is not none) |
| R3 | two rows, same id | `registry.duplicate-id` |
| R4 | a dep naming an id with no row | `registry.unknown-dep` |
| R5 | a dep naming an iface its target row does not declare | `registry.unknown-iface` |
| R6 | a layer-0 row depending on a layer-1 row | `registry.layer` |
| R7 | two rows depending on each other (equal layers slip past R6's rule only if layer allows; plant accordingly) | `registry.cycle` |
| R8 | two rows serving the same resource name | `registry.serves-duplicate` |
| R9 | export bytes valid but digest stale against the cue source | `registry.stale-export` |
| R10 | an enumerated refusal name removed from the meta corpus (meta-fault: run `faults` with one fixture deleted) | `registry.undemonstrated` |
| A1 | `goodcap` minus `faults/` | `anatomy.missing` |
| A2 | `goodcap` plus `notes.md` | `anatomy.extra` |
| A3 | manifest declares member `close` the Protocol lacks | `anatomy.member-missing` |
| A4 | Protocol gains method `drop` the manifest does not declare | `anatomy.member-undeclared` |
| A5 | manifest refusal row without `remedy` | `anatomy.manifest` (cue-level: `#Refusal.remedy!`) |
| A6 | manifest refusal row with class `error` | `anatomy.manifest` (outside `#OutcomeClass`) |
| A7 | `migrates` tagged, `migrations/` absent | `anatomy.missing` / `anatomy.migrates-empty` (empty dir variant) |
| A8 | a declared refusal with no fixture under `faults/` | `anatomy.undemonstrated` |
| A9 | module with a syntax error | `anatomy.unparsed` |

Every fault must be proven to differ from its clean source (plant landed)
before its refusal is checked — the `fixture_intact` discipline, carried
from U0.

---

## 7. Work breakdown — acceptance criteria and dependencies

The U2 sidecar is a **leaf** (`units: []`); these are ordered work items
inside one unit, not sub-units — a sub-unit would demand its own child
plan per parent §3.3 rule 7, and nothing here is bigger than one
pipeline pass. Stages per `pipeline.md`: this document is stage 2; stage
3 (tests, non-implementing harness) authors from §§2–6 acceptance rows;
stage 4 skeptic; stage 5 code; stage 6 two reviews. For the CUE half,
the contract-work variant applies: the contract author gets §§2–4 and
the parent's §2.2–2.3 only; the anatomy check's `ast` extractor half is
written against the fixture directories with the CUE removed from its
snapshot.

| # | work item | acceptance (observable, self-contained) | needs |
|:--|:--|:--|:--|
| W0 | **root amendment + rebind** — expand root U2 row deliverables to the full set (capabilities.cue, capability.cue, outcome.cue, examples/, faults/, both checks, the live export, both registration rows) each with a `#Interface`; flip D-new-2 `revisit → superseded` citing D-U2-iface-manifest; rebind `plans/U0.plan.json` (+ md, re-extract) to the new root digest; write `plans/U2.plan.md` + `.plan.json` bound likewise, scope = parent words + `" \| 2026-08-31: launch U2"` | `plan_vet.py vet` exits 0 on all three sidecars; `plan_vet.py faults` still green; the root shows no decision at `revisit` | ratify gate on §9 D-U2-iface-manifest |
| W1 | `contracts/outcome.cue` + `contracts/capabilities.cue` + `contracts/capability.cue` | `cue vet -c` accepts every §6.1 example against its definition; rejects every cue-level fault (R1, R2 at cue layer, A5, A6) with an error naming the offending path | W0 |
| W2 | examples + fault corpus (§6) committed | every fault's bytes differ from its named source; meta sidecars complete (`from`, `change`, `violates`, `reject_path`) | W1 |
| W3 | `container/errors.py` outcome class + `plan_vet.py` call-site classification | U0 suite green; `Refusal` without an outcome class is a `TypeError`/refused construction; `str()` renders class and remedy | W0 |
| W4 | `checks/registry_vet.py` | `vet` on `examples/registry.json` and on the live empty export exits 0; each R-fault draws exactly its meta-named refusal with the right class; `faults` exits 1 when any enumerated `#RegistryRefusals` name has no firing fixture (prove by deleting R4 in a scratch copy); cue absent ⇒ `registry.cue-unreachable`, abort, exit 1 | W2, W3 |
| W5 | `checks/anatomy.py` | `vet` on `examples/anatomy/goodcap` exits 0; each A-fault directory draws its named refusal; on the real (empty) `capabilities/` prints the zero-scanned honesty line and exits 0; `faults` enforces `#AnatomyRefusals` coverage same as W4 | W2, W3 |
| W6 | live export `capabilities.json` (empty, digested) + the two `gate-kinds/artifact.json` rows + the cue install step in `ci-dev.yml` | `wf.py --json status --checks` lists `registry-vet` and `anatomy`; `wf.py check --verify-only registry-vet` and `... anatomy` exit 0 on the tree; `vocabulary_wall.py` exits 0 over the whole tree (no reserved term added on a walled surface — this includes every new path component) | W4, W5 |

Unit gate (the parent row's, made concrete): `cue vet` over the examples
green; every fault red with its named refusal; both `faults` runners
green (full coverage); both registered checks green on the tree; wall
green; all three sidecars `plan vet` green.

Economics: `write.minutes: 90`, tag `assumed`.

---

## 8. Gates (the sidecar's `gates` rows, prose form)

| name | argv | fires_on | quiet_on | cost |
|:--|:--|:--|:--|:--|
| registry-vet-live | `python3 ops/capabilities/checks/registry_vet.py vet ops/capabilities/capabilities.json` | stale/invalid live export | the committed empty export | cheap |
| registry-faults | `python3 ops/capabilities/checks/registry_vet.py faults` | any R-fault not firing, firing wrong, intact, or any enumerated refusal undemonstrated | full corpus each drawing its name | cheap |
| anatomy-examples | `python3 ops/capabilities/checks/anatomy.py vet ops/capabilities/contracts/examples/anatomy/goodcap` | goodcap refused | goodcap accepted | cheap |
| anatomy-faults | `python3 ops/capabilities/checks/anatomy.py faults` | same rule as registry-faults, A-corpus | full corpus | cheap |
| plan-vet-u2 | `python3 ops/capabilities/checks/plan_vet.py vet ops/capabilities/plans/U2.plan.json` | stale binding, projection mismatch, dropped ruling, drift | the landed sidecar | cheap |
| u0-regression | `python3 -m unittest discover -s ops/capabilities/tests -p 'test_plan*.py'` | the errors.py extension breaking U0 | U0 suite green | cheap |
| u2-tests | `python3 -m unittest discover -s ops/capabilities/tests -p 'test_registry*.py'` (+ `test_anatomy*.py`) | the stage-3 suite red | green with the skeptic's additions | cheap |
| wall | `python3 ops/devlane/workflow/checks/vocabulary_wall.py` | a reserved term on any new surface or path | clean tree | cheap |

---

## 9. New decisions — one sentence each, premises tagged

- **D-U2-iface-manifest** *(settles D-new-2; supersedes it)* — Interface
  members are declared explicitly in the capability manifest and verified
  both ways (declaration ↔ Protocol source by the anatomy check;
  declaration ↔ built object at container boot), and the lane's 3.12.14
  pin stands. *Premises:* §2 items 1–5 (measured: the pin; read ×4:
  ratification D-new-2 row, framework plan §2.4/D-language, §1 closing
  paragraph, V1). Status: **pending** — this is the row the ratify gate
  rules on; nothing enters `code` before it (`plan.stage-blocked`).
- **D-U2-outcome-classes** — The contract package defines the four
  outcome classes and a closed remedy-bearing `#Refusal`, every refusal
  the registry layer or a capability manifest declares is classified,
  and a denial is specified as a recorded success for U3 to enforce.
  *Premises:* read: `looplaw-findings.md` §§1–2; read:
  `gate-kinds/artifact.json` stage outcomes already speak
  `finding/denied/aborted`; read: the brief — framework-wide, at this
  layer, not retrofitted at U13. Status: pending.
- **D-U2-undemonstrated** — Every refusal enumerated by
  `#RegistryRefusals`, `#AnatomyRefusals`, or a capability manifest must
  be drawn by at least one committed fault, and the `faults` runners
  refuse an undemonstrated name as a finding. *Premises:* read:
  `looplaw-findings.md` §3 ("the check list is the test manifest");
  read: `plan_vet.py faults()` precedent; read: parent §2.2 `faults/`
  row; read: AGENTS.md a-check-must-fire (via parent §2.2). Status:
  pending.
- **D-U2-errors-outcome** — `container/errors.py` `Refusal` gains a
  required outcome class with `needed` documented as the remedy, and
  U0's `plan_vet.py` call sites are classified in the same change with
  U0's suite as the regression gate. *Premises:* read:
  `looplaw-findings.md` §2; read: `errors.py`/`plan_vet.py` as landed;
  read: parent §10 (refusals are the lane's `Refusal` shape, copied).
  Status: pending.
- **D-U2-parent-amendment** — The root sidecar's U2 row is amended to
  name the full artifact set before any other W-item, D-new-2 flips to
  superseded in that amendment, and every existing child sidecar is
  rebound to the new root digest in the same commit. *Premises:* read:
  `plan_vet.py` relational rules (`stale-parent`,
  `deliverables-mismatch`, `stage-blocked` as code); read: root sidecar
  U2 row vs framework plan §7 row U2 (the sidecar under-declares); read:
  parent §3.3 rules 1–2. Status: pending.
- **D-U2-vacuous-honesty** — The anatomy check over an empty
  `capabilities/` reports zero directories scanned and never prints
  clean over nothing. *Premises:* read: `vocabulary_wall.py` lines
  176–185 (the lesson, in code, with its incident comment); read:
  `looplaw-findings.md` §1 (unmeasured is a recorded outcome, not an
  absence). Status: pending.
- **D-U2-cue-in-ci** — `registry-vet` and `anatomy` refuse with an
  abort-class refusal when `cue` is unreachable rather than reporting
  clean, and `ci-dev.yml` gains a conditional install of the pinned cue
  0.14.1 in the exact shape of the existing ruff step. *Premises:* read:
  `ci-dev.yml` lint-gate comment ("refuses rather than reporting clean
  when it cannot run"); read: `plan_vet.py` economics note (the runner
  is cue-free); read: V4 (digests pinned to cue 0.14.1). Status:
  pending.

All seven route to the ratify gate together; per the ratification doc's
rule these are design decisions (conductor ratifies, recorded with
reason and premise), except that D-U2-iface-manifest closes an owner-
visible `revisit` and should be surfaced to the owner with the others as
context — the delegation ("not me — you have to know how to design a
framework") is the authority binding and is cited, not assumed
(`looplaw-findings.md` §4).

---

## 10. Naming reconciliation — container, not the reserved term

- Every U2 artifact — paths, file contents, refusal names, prose in
  `plans/U2.plan.md`, `CONTRACT.md` text in fixtures — uses
  **container** for the boot-and-registry program. The wall check
  enforces this mechanically on `ops/capabilities/**` (contents *and*
  path components), and gate `wall` (§8) is in the unit gate set so a
  violation cannot land quietly.
- The parent prose (framework plan §2) predates the rename and says the
  reserved word; it lives in `ops/docs/scratch/`, an exempt quoting
  home, and is **not** edited by U2 — the landed root sidecar already
  says `container/boot.py` for U3, and that sidecar, not the prose
  path strings, is what children bind to.
- The parent §10 refusal name for the size bound carries the reserved
  term; that gate is **U4's** deliverable and the rename
  (`size.container`) is noted here for U4's planner, not performed
  here. No U2 refusal name contains the term.
- `capability`/`capabilities` are dev-lane reserved terms (wall pass 1)
  — fine under `.dev/`, where all of U2 lives; nothing in U2 touches a
  design surface outside `.dev/`.

---

## 11. Sidecar mechanics (so stage 3 can pin them)

- `id: "agentscient/U2"`; `parent: {id: "agentscient", sha256: <digest
  of the amended root>, unit: "U2", bound_to: "sidecar"}`.
- `scope.owner_words`: parent's verbatim + `" | 2026-08-31: launch U2"`,
  `source` naming the owner — the `plan.scope-drift` append form.
- `settled`: all 9 root settled ids + all root decisions at `standing`
  ratified by owner/conductor (11 today: D-plan-cue, D-language,
  D-storage, D-set, D-context-custody, D-size, D-order, D-anatomy,
  D-fixture-repo, D-hooks-listeners, D-launcher-after). D-new-2 is not
  carried (it is `revisit` pre-W0, `superseded` post-W0; neither is
  carried by the vet's rule, and its successor lives in this plan's
  `decisions`).
- `deliverables`: the amended root U2 row, verbatim (rule 2).
- `units: []` (leaf) ⇒ `open: []` (`plan.leaf-open`). Everything this
  plan does not build is either specified as a seam for a named later
  unit in prose (§3.5, §10) or reported in §12 — never an `open` row.
- `denied`: reading outside the snapshot and `in/`; executing anything;
  touching `ops/devlane/` beyond the two registration rows; touching the
  pinned launcher or the envelope contract; building tag-flow or any
  U4 check; building the container's boot (U3); editing the parent
  prose.
- U2's stage in the *root* moves `plan → tests → check → code → review →
  done` over the unit's life; each move re-digests the root and stales
  every child binding — see F2.

---

## 12. Reported findings — outside the brief's questions, would change plans

- **F1 — the root U1 row does not match where the vocabulary work
  landed.** Root sidecar U1 declares
  `ops/capabilities/contracts/vocab.cue`, stage `plan`; the landed wall
  and vocab contract live under `ops/devlane/workflow/` (`contracts/cue/
  vocab.cue`, `checks/vocabulary_wall.py`). U2 is unaffected (needs U0
  only; the wall enforces regardless of address), but the root row is
  stale against reality and should be reconciled in a root amendment —
  cheapest is riding W0's, if the owner agrees; otherwise it will
  surface as `plan.deliverables-mismatch` the day a U1 child is written.
- **F2 — root-amendment cascade cost is structural.** Every edit to
  `agentscient.plan.json` — including each per-unit *stage* transition —
  changes its digest and stales every child's `parent.sha256`, forcing a
  rebind commit across all landed child sidecars (and their `.md`
  re-extraction). U2 pays this at least twice (W0, then each stage
  move). With ~20 units ahead this is O(units × stages) rebind commits.
  Worth a framework decision (e.g. bind children to a stage-stripped
  projection digest) — that is a `plan.cue` change, U0's contract, not
  U2's to make.
- **F3 — U0's own gates are not registered in `gate-kinds`.** No
  `plan-vet` / `plan-faults` rows exist in `artifact.json`, so CI's
  derived matrix never runs them; they live only in U0's unit suite and
  hands. Parent §2.5 wants `plan-vet` registered `ci: true`. W6 could
  carry the two rows for plan-vet at near-zero cost, but that amends
  U0's landed deliverable surface — flagged for the owner rather than
  silently annexed.
- **F4 — the CI runner is cue-free today**, which also means U0's
  `cue vet` path has never run in CI. D-U2-cue-in-ci fixes the runner
  for U2's checks; once cue is installed, registering plan-vet (F3)
  becomes fully effective rather than partially.
- **F5 — the looplaw envelope recommendation cannot land in U2.**
  "Adopt the four classes as the envelope's `status` vocabulary,
  replacing `ok | invalid | tripped`" is a change to the
  launcher/records contract, and the launcher is pinned by a standing
  owner ruling (D-launcher-after). U2 delivers the class vocabulary the
  envelope will import; the swap itself needs an owner-sequenced slot
  (plausibly the unit that next touches `records`/the envelope, U9 or
  the post-U21 launcher plan).
- **F6 — `ops/conductor/` quoting exemption.** HEAD (c4bb3c0) exempts
  `ops/conductor/` as a quoting surface for reserved terms; the U2-
  relevant consequence is only that `looplaw-findings.md` may quote the
  reserved word freely — no U2 artifact lives there, nothing changes in
  this plan.

Risks stated: (1) R1 (list-element closedness) may reveal that CUE does
not refuse the extra key — the plan already names the fallback (closure
moves to the raw-presence pass) so a surprise is a route, not a stall.
(2) The `ast` member check reads class bodies, not semantics; a member
built dynamically would evade it — accepted, because U3's boot re-checks
presence on the built object, and the two checks together close the gap.
(3) Classifying U0's refusal call sites touches landed tested code; the
U0 suite is the containment, and the change is additive by design.
