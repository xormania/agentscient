# Ratification — U2 child plan (record 20260831T015736Z-plan-claude-eb31e9)

Ratified 2026-08-31 by the conductor (Claude Fable 5), design authority per
the owner's standing delegation ("not me - you have to know how to design a
framework"), on the plan at `agentscient-u2-plan.md` as landed verbatim.

## The seven decisions — ratified as written (plan §9)

D-U2-iface-manifest · D-U2-outcome-classes · D-U2-undemonstrated ·
D-U2-errors-outcome · D-U2-parent-amendment · D-U2-vacuous-honesty ·
D-U2-cue-in-ci — each with the premises the plan tags. All seven flip
`pending → standing` with this document as `ratified_by`.

**D-U2-iface-manifest is owner-visible**: it closes the root's D-new-2
`revisit` (interface members declared in the manifest, verified both ways;
the 3.12.14 pin stands; the introspection alternative fails portability to
a non-Python container outright). Ratified on the delegation; surfaced to
the owner in the same report as this commit — an owner objection reopens
it as `revisit` with the objection as premise.

## Findings routed (plan §12)

- **F1** (root U1 row stale against where the vocab work landed): folded
  into W0's root amendment — one amendment, both corrections. Conductor's
  call; the owner can unbundle.
- **F2** (rebind cascade is O(units × stages)): a `plan.cue` design
  question for U0's contract — recorded for the framework backlog, not
  U2's.
- **F3** (U0's plan-vet unregistered in CI) + **F4** (the runner is
  cue-free, so U0's cue path never ran in CI): owner's desk — registering
  plan-vet annexes U0's landed surface; D-U2-cue-in-ci makes it effective
  once ruled.
- **F5** (envelope status vocabulary swap): blocked on D-launcher-after by
  its own analysis; waits for the unit that next touches the envelope.
- **F6**: no action; consistent with the vocabulary amendment at
  `c4bb3c0`.

## Pipeline for the unit (shapes recorded)

Stage 3 tests (grok — queued behind the vocab tests dispatch in flight) →
stage 4 bounded skeptic pass 1 (Opus) → stage 5 code (Sol; W0 first, which
flips D-new-2 to superseded in the root and rebinds children) → stage 6
two reviews. The contract-work variant applies as the plan states: the
tests author receives §§2–6 and the parent §2.2–2.3 only.

## Amendment U2-A1 (2026-08-31) — the skeptic's contract findings, ruled

Skeptic `20260831T024411Z-check-tests-claude-b01437` (CHANGES: 3 P1, 9 P2,
4 P3; 6 findings against the contract; exported verbatim beside this file).
Rulings, each naming its finding:

1. **F1 — `registry.cycle` is retired; acyclicity is a corollary of strict
   layering.** Under `dep.layer < layer` every cycle contains a layer
   violation, so a distinct cycle check is dead code with an undemonstrable
   refusal. The name leaves `#RegistryRefusals`; R7 leaves the corpus (the
   tests-fix stage removes its rows, this amendment the named reason); R6
   stays as the layer witness; §5.1 step 3 drops the cycle item. Tier 1 —
   the violation is unrepresentable, which outranks checking for it.
2. **F2 — the currency digest lives in a sidecar**,
   `capabilities.json.digest` (sha256 of the canonical export), beside each
   example likewise. `#Registry` stays closed and digest-free. §5.1 step 4
   reads the sidecar and draws `registry.stale-export` when it is ABSENT as
   well as stale — absence is a refusal, never a silent skip, which kills
   the "currency check no-ops" mutant.
3. **F3 — the §3.4(d) coverage set is closed and named**: every enumerated
   refusal whose subject is a committed file fixture. The carve-out is
   exactly two names — `registry.cue-unreachable`, `anatomy.cue-unreachable`
   (class abort, environment-subject) — demonstrated by the executable
   plant in the unit suites instead. Nothing else may join the carve-out.
   A7 gains the committed empty variant (`migrations/` holding only
   `.gitkeep`; `anatomy.migrates-empty` fires when no migration entry
   besides `.gitkeep` exists).
4. **F5 — §5.2 is first-failure-only per directory** (as §5.1 states for
   the registry); the vacuous-honesty line remains output, not refusal.
5. **F6 + F7 — §3.4(b)/(c) gain enumerated finding-class names**:
   `registry.fault-intact`, `registry.fault-mismatch`, `anatomy.fault-intact`,
   `anatomy.fault-mismatch`, mirroring U0's `plan.fault-*`; the `faults`
   runner draws them and the tests assert them against the RUNNER, closing
   both the returncode-only proxy and the unpinned (c).
6. **F8 — new rejection `anatomy.iface-unresolved`**: a declared iface whose
   named Protocol class is absent from the module; new A-row; §5.2 step 4
   resolves the class before comparing members.
7. **F9 — `goodcap` declares at least two ifaces**; member plants target
   the last declared one.
8. **F10 — the CONTRACT.md / contract.cue / manifest refusal-set agreement
   gets a name**: rejection `anatomy.refusals-disagree`, its own A-row, and
   §5.2 step 6 performs the comparison. The claim stays; it now has an
   oracle.
9. **F11 — exit semantics stated**: on `vet`, any drawn refusal of any
   class exits 1; only the vacuous-scan case exits 0. In CI a finding fails
   the gate. The tests' inference is ratified as contract.
10. **F4 — fault meta gains required `site`** (U0's own discipline); the
    anatomy corpus plant proof must name the differing path, not assert
    whole-directory inequality.
11. **Corpus-mutation finding — `faults` gains an optional corpus-root
    argument** (default: the committed path); coverage tests mutate a
    scratch copy, never the committed corpus.
12. **F12 dissolves**: W3's acceptance already requires `str()` to render
    class and remedy; the exact line format follows the tests as written.

P3 rows: the tests-fix stage addresses or declines each with a named
reason. The tests-fix is one grok pass with the skeptic report and this
amendment as contract; the code stage (W0 first) follows it.

Ratified by: the conductor (Claude Fable 5), 2026-08-31.

## Amendment U2-A2 (2026-08-31) — sole-claim counts drawn claims, not mentions

Sol's code stage (record `20260831T031828Z-code-codex-a20eb7`) stopped,
correctly, on a genuine tests contradiction: `assert_u2_refusal`'s
sole-claim rule counts every `registry.*`/`anatomy.*` token in the output,
while §3.4(d)'s undemonstrated refusal must NAME the refusal lacking a
fixture in its expected/needed text — the remedy discipline requires it.
Ruling: a CLAIM is a `refused: <name>` line; names appearing in
`expected`/`actual`/`needed` prose are licensed mentions. The helper is
amended by the tests stage accordingly; nothing else in U2-A1 changes.

Ratified by: the conductor (Claude Fable 5), 2026-08-31.

## Amendment U2-A3 (2026-08-31) — the contracts reader is a shared service

Sweep `20260831T050659Z-review-grok-b13303` (exported verbatim beside the
plan) measured the definition-that-enforces-nothing class at three
members: `#Anatomy`, `#Capability` (capability.cue), and all of
`outcome.cue` — whose taxonomy vets only as a duplicate inside
capability.cue, with `errors.py` holding a third copy. Root structural
fact: no `cue import` exists and every check invokes cue per-FILE, so
definitions can never unify across files.

Rulings, on the sweep's measurements and the owner's principle of
2026-08-31 ("one of the reasons for a framework is to provide re-usable
services"):

1. **A shared contracts-reading service** (one module under
   `ops/capabilities/container/`) owns every cue invocation: the pinned
   binary, package-granularity loading of `contracts/`, `export -e` of
   named definitions, and the single abort-class `cue-unreachable`
   refusal. `plan_vet`, `registry_vet` and `anatomy` consume it; no check
   invokes cue directly again.
2. **Package-granularity loading makes `outcome.cue` live and
   canonical**: capability.cue's duplicated `#Refusal`/`#OutcomeClass`
   are deleted in favour of the unified package; `errors.py` derives
   `OUTCOMES` from the export instead of restating it.
3. **`#Anatomy` becomes a concrete exportable value** (required files,
   required dirs, optional dirs — the `#AnatomyRefusals` pattern), per
   the sweep's Option A; the migrates-iff, empty-migrations and
   file-vs-directory rules stay in Python, stated as such. The
   `close({...!: true})` schema form is dropped rather than kept
   unclaimed. `#Capability` in capability.cue is deleted or unified with
   the registry's — one of the two, never a third copy.
4. **The sweep's six pins are the tests contract** (§3 of the report):
   CUE-add→missing and CUE-remove→extra on a scratch package copy,
   comment-edit stays quiet, A1/A2 kept as filesystem plants, the
   `tests`-file kind case kept, the migrates pair kept. `ANATOMY_ENTRIES`
   and every remaining hand copy in tests derive from the same export or
   die (the b42c54 P3 test-side closes here).
5. The check gains a contracts-root argument as `faults` gained
   `corpus_root`, so scratch-package tests need not copy the package by
   hand.

Premises: `measured` (every table in the sweep, at 62bcdee on host cue
0.17.1; the 0.14.1 caveat carried as stated); `owner 2026-08-31` (the
reusable-services principle). Pipeline: grok authors the pins → Sol
implements the service and the rewrite → bounded confirm.

Ratified by: the conductor (Claude Fable 5), 2026-08-31.

## Owner doctrine (2026-08-31) — think like a Symfony dev: bundleable capabilities

Owner's words: "i think like a Symfony dev - services - that way we can
bundle them like symfony." Read with the standing U1 vocabulary ruling
(the injectable is a `capability`; `service` remains compose's word — the
owner's own conflation reasoning, unchanged): the capability IS the
bundle; its exported interfaces ARE the services. Consequences carried
into design:

1. New tooling is born bundle-shaped — manifest, contract, tests, faults
   from day one — never as loose scripts. First subjects: the shared
   contracts reader (U2-A3), the MCP records bridge (board-U1), and the
   conductor tools (`meters`, the dispatch wrapper, the board) as named
   migration candidates once U3's container boots capabilities.
2. U11's surface bundles registry-declared capabilities; it must never
   need to rewrite one to serve it.

Premise: `owner 2026-08-31`; the framework plan's §1 Symfony table,
ratified, is the same doctrine stated before it had tonight's proof.

## Amendment U2-A4 (2026-08-31) — the CI-shape grammar learns U2's arrivals

The half-done-amendment class again, third instance tonight: D-U2-cue-in-ci
ratified the install step and W6 registered two checks, but the CI-shape
suite's pins (`test_ci_shape.py`) were never amended — three tests fail on
the merged tree exactly as their design intends. Rulings:

1. **The expected-context baseline gains `dev: gates (anatomy)` and
   `dev: gates (registry-vet)`** — additions through the registry are the
   sanctioned path; the pinned lists learn them; nothing else changes.
2. **The gates-job install grammar gains a second sanctioned form**: a
   version-pinned release fetch that is checksum-verified. The landed step
   (`curl … v0.14.1 … | tar`) is version-pinned but carries no digest —
   it does NOT satisfy the amended grammar as-is; the code stage adds the
   sha256 verification rather than the tests blessing a bare pipe-to-tar.
   `pipx|pip install` remains the first form; nothing else may share the
   job.
3. Discriminating cases kept: an unpinned fetch, an unverified fetch, and
   any non-install step in the job all remain refusals.

Premises: `measured` — the three failing tests at 608d236 on the merged
tree and the step at ci-dev.yml:139-144; `read` — D-U2-cue-in-ci ("the
exact shape of the existing ruff step") and the D-IMG digest-pinning
precedent. Pipeline: grok amends the pins, Sol adds the digest, bounded
confirm rides the next review.

Ratified by: the conductor (Claude Fable 5), 2026-08-31.
