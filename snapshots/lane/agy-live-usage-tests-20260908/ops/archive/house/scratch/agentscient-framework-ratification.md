# Ratification — the framework plan (abd945) and the patterns memo (4653b6)

Ratified 2026-08-29 by the conductor (Claude Fable 5), on the owner's word: "not me - you have to know how to design a framework". Rule applied from here on: **policy** decisions (anything the owner has spoken to — goals, vocabulary, what is real, lanes, money) are the owner's; **design** decisions (how the framework is built) are the conductor's, ratified with the reason and the premise, and recorded so a falsified premise can flip them to `revisit`. `ratified_by` carries who.

## Framework plan `ops/docs/scratch/agentscient-framework-plan.md` §11

| decision | ruling | reason (design) | premise it stands on |
|---|---|---|---|
| D-plan-cue | **standing** | a plan that is only prose cannot be vetted; a sidecar bound to the parent row makes nesting checkable both ways — the compiler-written-in-itself shape | `read`: prose written twice drifts (context.cue §brief); `measured`: today no plan is vetted |
| D-language | **standing** | 14,591 lines of stdlib Python are the hosted apps; a kernel in the same language costs no bridge, and the CUE contracts + fixture repo are what a later Rust kernel is proved against, so the language choice is reversible by construction | `measured`: line count; `read`: law lives in CUE |
| D-storage | **standing** | one sqlite per lane with migrations owned by the table-owning capability keeps ownership beside the schema; JSON exports stay the evidence so the db remains a cache — no new source of truth | `read`: wf.db is a gitignored cache, exports are evidence; LANE-NO-BLEED |
| D-set | **amended, standing** | fourteen capabilities as tabled, except: `task` is not dissolved — it returns as the workflow capability (node types = `jobs`, configured node instances, workflow definitions in CUE, an executor) built on the kernel after U4 | owner (policy): "my goal is snippets of work that are configured (like n8n)" — "yes - but framework first" |
| D-size | **standing** | a bound nobody measures is taste; a 2,000-line gate on the kernel proper is the cheapest guard against the accretion this whole plan replaces | `read`: AGENTS.md §Keep it small; `assumed`: 2,000 is the right first number — revisit when U4 measures |
| D-order | **standing** | plan gate and vocabulary first so every later unit is vettable and named correctly; kernel before primitives before surface; runner and cutover last | `read`: framework before surface (owner) |
| D-anatomy | **standing** | a closed directory shape checked both ways is what made `#Context` unforgettable; a scaffold command makes the shape cheaper to obey than to break | `read`: context.cue header; memo B6 |
| D-fixture-repo | **standing** | the only E2E ground; a fixture that proves its own plant answers about something | `read`: mini-app-lessons §6; owner: "we may need a fixture repo" |
| D-hooks-listeners | **standing** | nothing injects a hook; a thing nobody injects is not a capability | `read`: memo §A; tree listing |
| D-launcher-after | **standing** | the launcher is the pinned toolchain the conductor runs; it moves only after `records` and `custody` have been in service | owner (policy): "using existing dev-lane to dev dev-lane is risky" |

## Patterns memo `ops/docs/scratch/agentscient-patterns-research.md` §3

| decision | ruling | reason | premise |
|---|---|---|---|
| D-new-1 (container is a context manager; reverse-order close) | **standing** | `db` holds a connection; deterministic teardown in reverse registry order is the pattern every mature container uses | `read`: §4; `memory`: Spring/.NET/OSGi — accepted as design lore, not load-bearing |
| D-new-2 (deps handed as interface projections `<id>:<iface>`) | **revisit** | the split-at-runtime idea is right; its premise that stdlib can enumerate a Protocol's members is **falsified**: `get_protocol_members`/`is_protocol` are 3.13 additions and the lane pins 3.12 (measured 3.12.14). U3's plan must choose: move the pin to 3.13, or list an interface's members explicitly in the manifest (which the anatomy check can then verify both ways — arguably the better design, since it makes the interface a declared contract rather than an introspected one) | `read`: V1 in `verifications-u2u3.md` |
| D-new-3 (no lazy/scoped/overridden/version-ranged capabilities; named rejections) | **standing** | each is a real feature with a real cost; refusing them by name makes adding one a decision with a diff instead of an accretion | `read`: §1 not-carried list; §6 bound |

Verifications V2–V5 (Symfony compile-then-freeze; importlib explicit `sys.modules`; CUE list-element closedness undocumented → negative fixture in U2; n8n `typeVersion` pinned per workflow) are carried into the U2/U3 briefs as `read` facts.

## Amendment 2026-08-29 (later) — context custody

Owner: "its a bigger issue - you need on-demand context - from a context custody engine." Design ruling by the conductor:

| decision | ruling | reason | premise |
|---|---|---|---|
| D-context-custody — the capability set gains a **context custody** capability: a fact is a record with a chain of custody (command, environment, ref, time, actor/record, hash of raw output, tag proven not asserted); served on demand over the surface (`context://…?ref=&env=`), stale by construction across refs, re-measured through the `measure` job; briefs reference fact ids and the launcher hashes the facts a brief relied on into the record; transfers (brief ← fact, decision ← premise) are recorded so a falsified premise flips a decision to `revisit` mechanically | **standing** | five times on 2026-08-29 the conductor carried context by hand and lost custody of it (the "48 red" without its environment; a scope fact from memory; the daemon evidence memo; the salvage diff; every `measured/read/memory/assumed` tag typed by hand); a courier cannot be made reliable, a custody record can | `measured`: the five instances; `read`: `harness/context.cue` `#Context`, `evidence.cue`, running list items 7 and 13 |
| Placement | its own unit after U4 (kernel + framework gate) and before U17 (`memory`); U2/U3 leave the seam (a `context` read interface, measurement as a job) | it depends on `records` and `db`; `memory` depends on it for premise custody | `read`: framework plan §7 order |
| Naming | to be resolved in the unit plan: `custody` already names harness-run isolation; chain-of-custody of a fact is a different thing under the same word; the vocabulary wall (U1) will force the choice | `read`: framework plan §4 capability table; U1 plan | — |

## Amendment 2026-08-30 — Meters: spend, then yield

Owner: "one thing we need to get right is both data mining for cost savings - and a real-time semantic yield." Design ruling by the conductor:

| decision | ruling | reason | premise |
|---|---|---|---|
| D-meters-spend-first — `session.spend` is measured from each harness's own store before any other Meters work | standing | `spend: null` on 105 of 105 records; no cost saving can be measured, only guessed | `measured`: the records; `read`: Claude JSON output carries `total_cost_usd` and usage |
| D-yield — a `yield` unit computes effect ÷ cost per record (effect = structured deltas: tests red→green, gates, findings closed/opened/refuted by severity, commits, decisions settled/revisit, files by kind; cost = tokens/$ + minutes), classifies turns semantically from the stream's tool calls, emits live `yield` events from the stream watcher, and gives the breaker a floor on effect, not bytes | standing | a number the conductor and the automaton can steer on while a dispatch runs, from fields the records already carry; the day's mined waste (no-envelope deaths, static reviews, refusals, nohup) is the fixture it is tested against | `measured`: record fields, breaker and stream watcher exist; `assumed`: envelope deltas are a good enough proxy for meaning to steer on |
