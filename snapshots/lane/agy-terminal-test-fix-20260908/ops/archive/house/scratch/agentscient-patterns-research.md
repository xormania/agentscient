# Memo — design patterns for adding and managing capabilities in the Agentscient kernel

Research only, no code. For the tree at `76fd53d99a0868a7fa860d1cca2473cc91853a88`,
scope: Owner 2026-08-29, *"make sure you research design patterns via claude — we
want a framework so we can add/manage services"*. Input to units U2 (registry
contract) and U3 (kernel boot) of `ops/docs/scratch/agentscient-framework-plan.md`.
Read: `in/BRIEF-patterns.md` whole; the framework plan whole (§2, §4, §6, §7, §10
used); `ops/devlane/workflow/errors.py` (`Refusal` signature); a grep of
`.dev/app` for `importlib.util`. Nothing executed beyond `grep`/`wc`.

Vocabulary: the injected object is a **capability**; `service` is compose's word.
Below, the industry word is used when naming a pattern, the repo word when
applying it.

**No network.** Every claim about an external framework is tagged `memory`
(my training, cutoff early 2026) unless marked otherwise. Claims about this
repo are `read` (from the snapshot) or `measured` (a command run here). Items
the conductor should verify before U2/U3 rely on them are marked **[verify]**
and collected in §4.

---

## 1. Pattern catalogue

Each entry: what it solves · the cost it adds · where it is used · what it looks
like in stdlib Python at our scale (≤2,000-line kernel, registry in CUE, exported
to JSON, read/write split enforced at boot).

### P1. Compiled / frozen container
- **Solves:** every wiring error is found before the first service runs; the
  runtime object graph is immutable, so behaviour cannot depend on call order.
- **Cost:** a build step (cache warmup / codegen) and a "stale build" failure
  mode that needs its own check.
- **Used in:** Symfony (`cache:warmup` compiles `ContainerBuilder` into a PHP
  class; compiler passes run at that point) [memory]; Go `wire` (generates
  `wire_gen.go` from provider sets; missing provider is a compile error)
  [memory]; Dagger 2 in Java (annotation processing) [memory].
- **Here:** already chosen (plan §1 "the container is compiled", §2.3 boot
  steps 1–6) [read]. The "build step" is `cue export` → `capabilities.json` plus
  the currency digest (step 2) [read]. Stdlib shape: a frozen dataclass
  `Container` holding a `types.MappingProxyType` of id → object, constructed
  once by `boot()`; no `register()` method after construction.

### P2. Declarative manifest per unit (bundle / provider / AppConfig / node description)
- **Solves:** the framework can enumerate, validate and order its parts without
  importing them.
- **Cost:** a second source of truth beside the code; needs a check that
  manifest and module agree (Symfony solves it by making the manifest *be*
  the compiled definition; n8n by a `description` object the node class
  exports [memory]).
- **Used in:** Symfony bundle + `services.yaml` [memory]; Laravel
  `config/app.php` providers list and package `extra.laravel.providers`
  [memory]; Django `INSTALLED_APPS` + `AppConfig` [memory]; OSGi
  `MANIFEST.MF` `Export-Package`/`Import-Package` with version ranges [memory];
  n8n `INodeTypeDescription` (name, version, inputs, outputs, properties,
  credentials) [memory]; Rust `Cargo.toml` features as a manifest of optional
  capabilities [memory].
- **Here:** `capability.json` per directory, closed over by `capabilities.cue`
  (§2.2, §2.3) [read]. Stdlib shape: `json.load` per directory, then a
  `registry_vet` that the *union* of manifests equals the committed
  `capabilities.json` (see §3 edit E1 — the plan currently has both a per-
  directory manifest and a central export without saying which is primary).

### P3. Explicit provider function (`build(deps, ctx)`) — constructor injection without reflection
- **Solves:** a capability receives what it declared and nothing else; no
  container reference leaks in; testable by calling `build()` with fakes.
- **Cost:** boilerplate per capability; no autowiring convenience.
- **Used in:** Go `wire` providers (plain functions whose parameter types are
  the deps) [memory]; Spring `@Bean` methods taking parameters [memory]; .NET
  `services.AddSingleton<I>(sp => new Impl(sp.GetRequiredService<Dep>()))`
  factory overloads [memory]; Pluggy `hookimpl` functions receive only the
  named hookspec arguments [memory].
- **Here:** already chosen (§2.2 `build(deps: dict[str, object], ctx:
  BootContext) -> object`) [read]. Stdlib: `deps` should be keyed by the
  *declared alias* `"<id>:<iface>"` or by `id` — the plan says `deps: [{id,
  iface}]` but `build` receives `dict[str, object]` with the key unstated
  (§3 edit E2).

### P4. Interface-keyed resolution (register by interface, not by class)
- **Solves:** a consumer depends on a contract; the read/write split falls out
  of handing `DbRO` vs `DbRW` views of the same object.
- **Cost:** one object may need to be projected into several interfaces; a
  `Protocol` check only proves method presence.
- **Used in:** .NET `IServiceCollection.AddScoped<IFoo, Foo>()` [memory];
  Symfony aliases from interface FQCN to service id (`autowire` uses the
  type-hint as the alias) [memory]; OSGi registers a service under one or
  more interface names, with properties [memory]; Rust `dyn Trait` objects in
  a typemap (`anymap`, `http::Extensions`, `axum` `State`) [memory].
- **Here:** `iface: [...]` per capability and `deps: [{id, iface}]` [read].
  Stdlib: `typing.runtime_checkable` + `isinstance` at boot step 6 (method
  presence only — the plan says so [read]). At our scale the projection
  question matters: `db` exports `DbRW`, `DbRO`, `Migrator` as *one* object
  (§4 table) [read]; a `read` capability declared as `db:DbRO` would still
  receive the object that also has `write` methods unless the kernel wraps
  it. See §2 "resolve" and edit E3.

### P5. Tags + collectors (compiler passes)
- **Solves:** one-to-many wiring — "give me every command / every resource
  handler" — without the consumer naming each provider.
- **Cost:** the tag vocabulary becomes an API; a tag with no collector is
  silently dead; collectors run in an order that must be stated.
- **Used in:** Symfony `tags:` + `CompilerPassInterface` (`findTaggedServiceIds`)
  and `!tagged_iterator` / `!tagged_locator` [memory]; Laravel
  `$this->app->tag([...], 'reports')` + `$app->tagged('reports')` [memory];
  Spring `List<Foo>` injection collects every bean of type `Foo`, ordered by
  `@Order` [memory]; .NET `IEnumerable<IFoo>` collects all registrations
  [memory]; OSGi service properties with LDAP filters [memory]; pytest plugin
  hooks are collected by hook name (Pluggy) [memory].
- **Here:** `#Tag` closed to seven values (§2.3) [read]; `surface` consumes
  every `surface.resource` (§4) [read]; `Migrator` consumes every `migrates`
  (§5) [read]. Stdlib: a `collect(tag) -> list[(id, obj)]` on the container in
  registry order, callable **only** from composition roots — which the plan's
  `no-locator` check must not mis-fire on (`collect(` is not `get(`; edit E5).

### P6. Decoration (wrap a service under its own id)
- **Solves:** cross-cutting behaviour (logging, caching, read-only view)
  without the consumer knowing.
- **Cost:** ordering of multiple decorators; debugging "which object am I
  holding".
- **Used in:** Symfony `decorates:` with `.inner` and `decoration_priority`
  [memory]; .NET via Scrutor `Decorate<I, Wrapper>()` (not first-party)
  [memory]; Spring `BeanPostProcessor` / AOP proxies [memory]; Python
  `functools.wraps`, and Django middleware as a stack [memory].
- **Here:** the *only* decoration the kernel should perform is the read-only
  projection (P4): wrap `db` as a `DbRO` façade that forwards only `DbRO`'s
  methods. Everything else (telemetry, logging) belongs to `observe` as a
  capability, not to the kernel — keeping under the 2,000-line bound (§6)
  [read]. Recommendation in §2 "decorate".

### P7. Lifecycle hooks (boot / ready / start / stop)
- **Solves:** work that needs every other service present (Django `ready()`
  registers signals; Symfony `Kernel::boot` → bundles `boot()`; Spring
  `SmartLifecycle.start()/stop()` phased; OSGi `BundleActivator.start/stop`;
  .NET `IHostedService.StartAsync/StopAsync`) [memory]; and orderly shutdown.
- **Cost:** a second entry point per unit; the temptation to do wiring in
  `ready()` (Django's documented anti-pattern: no ORM queries in `ready()`)
  [memory].
- **Here:** `build()` is the only hook (§2.3) [read]. Two things need a
  lifecycle we do not have: closing the sqlite connection in `db`, and the
  MCP server's process lifetime. Stdlib: make `Container` a context manager;
  a capability whose built object has `close()` gets it called in reverse
  registry order. Recommendation §2 "lifecycle" (D-new-1).

### P8. Lazy instantiation / deferred providers
- **Solves:** boot cost when most services are unused per request.
- **Cost:** errors move from boot to first use — exactly what the plan
  forbids (§1 "anything that resolves at runtime what could be refused at
  boot") [read].
- **Used in:** Symfony `lazy: true` (ProxyManager/`Closure` ghost objects)
  [memory]; Laravel `DeferrableProvider` with `provides()` [memory]; Spring
  `@Lazy` [memory]; .NET `Lazy<T>` registration [memory].
- **Here:** **rejected** for the kernel — fourteen capabilities (§6) [read]
  boot in milliseconds; the fixture E2E measures it. Keep the *option* of
  lazy inside a capability (e.g. `gitro` opens no subprocess until called).

### P9. Environment / profile overrides
- **Solves:** the same graph, different bindings per environment.
- **Cost:** combinatorial config; "works in dev" errors.
- **Used in:** Symfony `APP_ENV` + `config/packages/{env}/`, `when@dev` in
  YAML [memory]; Spring `@Profile("prod")` [memory]; Laravel `.env` + config
  cache [memory]; .NET `IHostEnvironment` + `appsettings.{Env}.json` [memory].
- **Here:** `lane` is a **boot argument**, one container per lane (§1 table,
  D2 "no field from one instance") [read]. Stdlib: `boot(lane=...)`; the
  *registry* does not vary by lane; only `BootContext` values do. Overriding
  which *capability* is bound per lane is **rejected** (§2 "override per
  lane") — the fixture capability is the only "test binding" and it is a
  normal `read` capability.

### P10. Discovery by scan (entry points, namespace packages, classpath scanning)
- **Solves:** third-party additions without editing a central list.
- **Cost:** import-time side effects; the set of loaded things depends on
  what is installed, which is not committed anywhere.
- **Used in:** `importlib.metadata.entry_points(group=...)` (pytest `pytest11`
  group, Flake8, Sphinx) [memory]; `pkgutil.iter_modules` over a namespace
  package (`flask_*` style) [memory]; Spring `@ComponentScan` [memory];
  Symfony `resource: '../src/'` glob with `autoconfigure` [memory]; Rust
  `inventory::submit!` / `linkme` distributed slices — link-time collection
  into a static [memory]; Django `apps.populate(INSTALLED_APPS)` is a list,
  not a scan [memory].
- **Here:** **rejected** as the source of truth (plan §1 "not carried:
  autowiring by type scan") [read]. The directory walk of `capabilities/*/`
  is permitted for the *anatomy check* and to prove the registry is complete
  (every directory has a row; every row has a directory) — a scan used as a
  gate, never as a loader. Rust note: `inventory`/`linkme` are the Rust
  analogue of import-time registration and should also be rejected for the
  later Rust kernel; the CUE registry is what it reads (§2.4) [read].

### P11. Hook specification / implementation (Pluggy)
- **Solves:** extension points with a declared signature, N implementations,
  ordered (`tryfirst`/`trylast`), with `firstresult` / all-results semantics;
  implementations are validated against the spec at registration [memory].
- **Cost:** everything becomes a hook call; hard to see the graph.
- **Here:** relevant to `listener` and `handler` tags (§4 "roles that are not
  capabilities") [read]. Not for U2/U3; the kernel does not dispatch events.
  Record for the hooks plan after U21.

### P12. Versioned interfaces (OSGi semantic versioning of packages; n8n node `version` array)
- **Solves:** two providers of the same interface coexisting; consumers
  declaring a range.
- **Cost:** version arithmetic in the resolver.
- **Used in:** OSGi `Import-Package; version="[1.0,2.0)"` [memory]; n8n nodes
  carry `version: [1, 1.1, 2]` and workflows pin `typeVersion` so old
  workflows keep running [memory]; Rust semver on crates [memory].
- **Here:** **not needed** while one repo owns every capability and the
  registry is closed. What *is* needed is the n8n lesson applied to
  **contracts**: `contract.cue` is the versioned thing; a change to it is a
  migration for consumers. Recommendation: `iface` names carry no version;
  `contract.cue` digests are recorded in the ledger export (§2 "deprecate").

### P13. Scoped lifetimes (.NET singleton / scoped / transient)
- **Solves:** per-request state (a `DbContext` per HTTP request).
- **Cost:** captive-dependency bugs (singleton holding a scoped) — .NET
  validates this in dev (`ValidateScopes`) [memory].
- **Here:** **rejected** — every capability is a singleton per container per
  lane; MCP request scope, if it ever needs state, is the surface's
  business. Stated so that U3 does not add a `scope` field.

### P14. Fakes by contract (test doubles registered under the same interface)
- **Solves:** testing a capability without its real deps.
- **Cost:** a fake that drifts from the real contract passes tests that the
  real one fails.
- **Used in:** Symfony test container (`static::getContainer()->set()`) [memory];
  Laravel `$this->app->instance(Foo::class, $fake)` and facade `::fake()`
  [memory]; Spring `@MockBean` [memory]; Pluggy plugin registration in tests
  [memory].
- **Here:** `build(deps, ctx)` takes plain dicts, so a test calls `build({"db:
  DbRO": FakeDb()}, ctx)` with no container at all [read: §2.2 signature].
  The drift problem is answered by the existing rule: one contract, positive
  and negative controls (`memo B6`, plan D-anatomy) [read] — a fake must pass
  the same `contract.cue` examples as the real one. Recommendation §2 "test
  with fakes".

### Anti-patterns (named so the checks can refuse them)
- **Service locator** — a component asks the container for deps at runtime;
  hides the dependency graph; the plan's `no-locator` check [read]. Symfony
  itself uses a *scoped* locator (`ServiceSubscriberInterface`) as the
  sanctioned exception [memory]; here, not carried.
- **God container / god config** — one object every module imports. The
  `no-locator` and `no-sibling-import` checks address it [read]; also, the
  kernel must not become the god: keep `Container` to `get`, `collect`,
  `ids`, `close`.
- **Implicit global state** — Django `settings`, Laravel facades, Flask
  `current_app` [memory]. Here `BootContext` is passed, not imported [read];
  U3 must ensure no module-level singleton in `kernel/` (e.g. a cached
  `_container`).
- **Import-time registration side effects** — `@register` decorators at
  module top level, entry points, `inventory::submit!`. The registry is data;
  modules are loaded *after* the graph is vetted (boot step 4 before 5)
  [read]. One residual: `importlib.util` execution runs the module's top
  level; the anatomy/no-sibling checks are static, but a module that does
  I/O at import is not refused by anything in the plan (edit E6).

---

## 2. Per concern: recommended pattern, rejected alternatives, premises

| concern | recommended for this framework | rejected | premises |
|:--|:--|:--|:--|
| **declare** | P2 per-directory `capability.json`, closed by `capability.cue`; the central `capabilities.json` is a *derived* export, checked equal to the union of manifests | one hand-edited central list (Django `INSTALLED_APPS`); code-side decorators | the plan already has both files but leaves precedence unstated [read §2.2/§2.3]; two sources drift [read: plan §3 "an interface written twice"] |
| **discover** | directory walk used only as a *gate* (every dir ↔ every row, both directions) | entry points, namespace scan, `inventory`-style link-time registration | scan-as-loader makes the loaded set depend on the filesystem, not the commit [memory: entry points; read: plan §1] |
| **register** | P1 compiled: `cue export` + digest currency check, at build/CI, never at runtime | runtime `container.register()` | plan §2.3 steps 1–2 [read] |
| **configure** | `BootContext` frozen dataclass, values from the lane; capabilities have no config of their own in the kernel | per-capability config sections in the registry | §2.3 `ctx` list [read]; "no field from one instance" [read: §1 table] — see D-new-2 for the one gap (a capability that needs a setting, e.g. `gitro` allowlist, keeps it in its own `contract.cue`, not in the kernel) |
| **resolve** | P3+P4: topological order, `deps` handed as a dict keyed `"<id>:<iface>"`, each value the **projection** of the built object to that Protocol (P6 façade) | reflection autowiring; handing the raw object | §4 `db` exports `DbRW`+`DbRO` from one object [read]; without projection, `tag-flow` proves nothing about what a `read` capability can *call* [assumed — verify V1] |
| **tag / collect** | P5 `collect(tag)` on the container in registry order, callable only from composition roots (`surface/`, `commands/`) | compiler-pass classes; tag attributes | §2.3 `#Tag` closed [read]; `surface` and `Migrator` are the only collectors in §4/§5 [read] |
| **override per lane** | none in the registry; `lane` selects `BootContext` values only | Symfony `when@env`, Spring profiles, per-lane registries | D2 ruling [read: §1]; one container per lane [read] |
| **decorate** | only the kernel's read-only projection (above); all other cross-cutting behaviour is a capability (`observe`) | Symfony `decorates:`; AOP proxies | 2,000-line bound [read §6]; a decorator chain is a second graph to vet [assumed] |
| **lazy** | none in the kernel; a capability may be internally lazy | lazy proxies, deferred providers | §1 "not carried: lazy proxies" [read]; fourteen capabilities [read §6] |
| **lifecycle** | `build()` at boot; `close()` if present, reverse order, via `Container.__exit__` (D-new-1) | `ready()`/`start()`/`stop()` phases; hosted services | `db` holds a sqlite connection [read: §4 from `store.py`] — a connection nobody closes is the only lifecycle need found |
| **observe** | the container exposes `ids()`, `graph()` (deps as data) and `collect()`; `agentscient://capabilities` serves it (U11) [read]; kernel emits nothing else | kernel-level tracing / profiler | §6 bound; `observe` capability owns telemetry [read §4] |
| **deprecate** | a `deprecated: bool` is **not** added; deprecation is a contract change recorded in `contract.cue` and a registry row removed by a commit that `imports-agree` vets | Symfony `deprecated:` on a definition; OSGi version ranges | closed registry; retirement is a commit (§8) [read] |
| **test with fakes** | P14: call `build()` directly with fakes; a fake must pass the contract's examples/faults | test container with `set()`; mocking the container | `build(deps, ctx)` takes dicts [read]; D-anatomy positive+negative controls [read] |

Premise tags: `read` = plan text or tree; `memory` = my knowledge of the
external framework; `assumed` = my inference, marked for verification.

---

## 3. What §2.3 / §2.5 get wrong or leave out — edits to §7 rows U2 and U3

**E1 (U2) — say which manifest is primary.** §2.2 has `capability.json` per
directory and §2.3 has `capabilities.json` central; the boot reads only the
central one. Edit U2 deliverables: *"`capabilities.json` is the `cue export` of
the union of `capabilities/*/capability.json`; `registry-vet` refuses when the
union and the export differ (`registry.stale-export`) and when a directory has
no row or a row no directory (`registry.orphan`, new refusal)."* Premise: two
sources drift [read §3].

**E2 (U2, U3) — fix the `deps` key.** `build(deps: dict[str, object], ctx)` with
`deps: [{id, iface}]` leaves the dict key unstated; `memory` declares both
`db:DbRW` and `db:DbRO` (§4) so `id` alone cannot be the key. Edit U2:
`capabilities.cue` states the key is `"<id>:<iface>"`, unique per capability.
Edit U3: `kernel/registry.py` builds the dict under that key. Premise: §4 row
`memory` [read].

**E3 (U3) — resolve by projection, not by object.** Boot step 5 "keep the
object under `id`" and step 6 "assert each built object satisfies every
declared `iface`" hand a `read` capability the whole `db` object. Edit U3:
*"for each dep, hand a façade exposing only the methods the named Protocol
declares (built from `typing.get_type_hints`/`dir(Protocol)`), so `tag-flow`
is enforced by construction at runtime as well as by the static check; a
fault registry where a `read` capability calls a `write` method through its
`DbRO` dep must draw `iface.unsatisfied` or a new `iface.projection`."*
Premise: assumed — **verify V1** that `Protocol` member enumeration is stable
in stdlib for the Python version pinned here.

**E4 (U3) — order the six refusals against the six boot steps.** §2.3 lists
six steps and U3 says "six faults draw six refusals", but §10 has
`capability.unknown`, `.cycle`, `.absent-key`, `.layer`, `tag.write-into-read`,
`iface.unsatisfied`, `registry.stale-export` — seven, and `capability.layer`
(dep.layer < layer) is a relational rule of `#Registry` with no boot step.
Edit U3: enumerate step → refusal explicitly: 1 `absent-key`, 2
`stale-export`, 3 `unknown` + `cycle` + `layer`, 4 `write-into-read`, 5
`build` failure (new: `capability.build-failed`, carrying the module's
exception), 6 `iface.unsatisfied`. Premise: read §2.3, §10.

**E5 (U2, U4 by reference) — `collect(tag)` and the `no-locator` check.**
§2.3 gives `container.get(id)` to composition roots but nothing collects by
tag, yet `surface` and `Migrator` both need it. Edit U2: the container
contract names `get(id)`, `collect(tag)`, `ids()`, `graph()`, `close()` and
nothing else; the `no-locator` fault corpus (U4) includes `collect(` inside a
capability. Premise: read §4, §5.

**E6 (U3) — import-time side effects are not refused.** Step 5 executes the
module's top level before `build()`. Edit U3: *"load with `importlib.util`
under a guard: cwd unchanged, no new files under the repo root, no sqlite
file created (compare a listing before/after); a fault module that writes at
import draws `capability.import-effect`."* Premise: anti-pattern list;
`importlib.util` is already the loader in `launch.py` [measured: grep].

**E7 (U3) — lifecycle.** Add `Container` as a context manager calling
`close()` in reverse registry order where present (D-new-1). Premise: `db`
holds a connection [read §4].

**E8 (U2) — `BootContext` is not in any CUE.** §2.3 lists its fields in prose
only. Edit U2: a `#BootContext` closed record in `capabilities.cue` (lane,
repo_root, db_path, records_root, clock as a named source), so the Rust
kernel (§2.4) reads the same shape; U3's dataclass is generated by hand from
it and a test asserts field equality. Premise: read §2.4 "contracts are the
portable part".

**E9 (U2) — `#Tag` collectors.** A tag with no collector is dead. Edit U2:
`capabilities.cue` records, per tag, which capability id collects it
(`surface.resource → surface`, `migrates → db`, `command`/`listener`/`handler`
→ declared absent with reason until the runner lands). Premise: P5 cost.

**E10 (U3) — no module-level container.** State it as a `no-global` clause of
the size/anatomy check or as a U3 test: `kernel/*.py` defines no module-level
mutable except `__all__`. Premise: implicit-global anti-pattern.

New decisions (one sentence each):
- **D-new-1** — The container is a context manager; a built object with
  `close()` is closed in reverse registry order. *Premises:* `db` holds a
  sqlite connection [read §4]; Spring/.NET/OSGi all stop in reverse start
  order [memory]. Status: recommended.
- **D-new-2** — Deps are handed as interface projections keyed
  `"<id>:<iface>"`, so the read/write split holds at runtime by construction.
  *Premises:* E2, E3. Status: recommended; depends on V1.
- **D-new-3** — No lazy, scoped, per-lane-overridden or version-ranged
  capabilities in the kernel; each is a named rejection, so adding one is a
  decision with a diff. *Premises:* §1 not-carried list [read]; §6 bound
  [read]. Status: recommended.

---

## 4. Five things to verify against primary docs before U2/U3 are planned

| # | verify | exact question it answers | why it matters |
|:--|:--|:--|:--|
| V1 | Python `typing` docs (pinned version) — `Protocol`, `runtime_checkable`, `get_protocol_members` (3.13+) | Can the kernel enumerate a Protocol's members in stdlib to build the read-only façade (E3), and does `isinstance` check only method presence (not signatures)? | D-new-2 rests on it |
| V2 | Symfony docs — Service Container: compiler passes, `tagged_iterator`, `decorates`, `Kernel::boot` order | Does Symfony really refuse a missing dependency at compile, and in what order do passes (before-optimization … removing) run — so U3's step order copies a working sequence rather than my memory | §2.3 steps 3–6 order |
| V3 | `importlib.util` docs — `spec_from_file_location` + `module_from_spec` + `exec_module`, and whether the loaded module lands in `sys.modules` | Can a capability module be loaded without registering a name that a sibling could then `import`? (If it lands in `sys.modules`, `no-sibling-import` must also be a runtime check.) | E6, `no-sibling-import` |
| V4 | CUE docs — `cue export` determinism and whether `cue vet -c` closes list element records | Is the `capabilities.json` digest stable across CUE versions, and does `close({})` apply inside `[...#Capability]` so an extra manifest key is refused? | E1, step 2 currency |
| V5 | n8n docs — node `version`/`typeVersion` and how a workflow pins a node version | Does n8n version the node *description* or the *implementation*, and how does a breaking change ship — so the "deprecate" row (contract digest, not registry flag) matches the owner's model | §2 deprecate row |

Also worth a look but not blocking: Pluggy hook validation semantics (for the
post-U21 hooks plan); .NET `ValidateOnBuild`/`ValidateScopes` as the closest
first-party analogue to boot-time graph validation.

---

## 5. What this memo did not do

No network, no execution beyond `grep`/`wc`, no reading outside the snapshot
and `in/`. Every external-framework claim is `memory` and may be out of date;
V1–V5 are where a wrong memory would change a unit plan. Not covered: Rust
kernel design beyond "reject `inventory`-style registration, read the CUE";
the hooks/listener dispatch model (deferred to after U21 by the plan).
