# Agentscient Test Framework Research and Results

**Document:** 02 — Test Framework Research and Results  
**Repository:** `uscient/agentscient`  
**Measured branch:** `dev`  
**Measured snapshot:** `032092c26521b674b626aa06aa0f3ea5585b6dec`  
**Date:** 2026-09-11  
**Status:** Research / design handoff; no source-of-truth changes implied

---

## 1. Purpose

Agentscient's test corpus is now large enough that the testing system itself needs explicit architecture.

The immediate problem is not simply "too many tests." The problem is that repeated test behaviors are being implemented as bespoke fixtures, subprocess wrappers, fake programs, temporary environments, file plants, SQLite setup, wire-protocol drivers, and regression-specific assertions. That creates four costs:

1. **duplicated testing machinery**,
2. **higher maintenance cost per regression**,
3. **more opportunities for flakiness and host-state leakage**, and
4. **difficulty measuring whether a new test adds independent fault-detection value or only repeats an existing invariant.**

The desired direction is therefore:

> Preserve test strength while making reusable invariants, test worlds, fakes, assertions, and case patterns the default unit of test construction.

This document records the current measurement, repository evidence, relevant external research, and a proposed framework for local-agent evaluation and implementation planning.

---

## 2. Executive Findings

### 2.1 The corpus is large but currently fast

The current lane suite runs **2,727 tests** across nine suites. Recent successful CI runs complete the lane job in roughly two minutes because the suite runner executes the nine suite directories concurrently and emits their logs in deterministic order.

Recent measured suite counts include:

| Suite | Tests | Approx. observed duration |
|---|---:|---:|
| dispatch | 583 | 70.6 s |
| harness | 155 | 6.2 s |
| task | 312 | 11.9 s |
| telemetry | 227 | 44.6 s |
| hooks | 246 | 54.3 s |
| fixtures | 221 | 34.1 s |
| workflow | 48 | 1.0 s |
| conductor | 927 | 106.6 s |
| pr-overview | 8 | 0.9 s |
| **Total** | **2,727** | **~2 min wall time** |

The execution strategy is already efficient. The primary problem is **test-system structure**, not raw CI runtime.

### 2.2 Test machinery is concentrated

Six conductor families were measured as an initial structural sample:

| Family | Test files | Test bytes | Corresponding production bytes | Test / production |
|---|---:|---:|---:|---:|
| `lane_mcp` | 3 | 152,308 | 16,462 | **9.25×** |
| `dispatch_wrapper` | 4 | 94,757 | 15,260 | **6.21×** |
| `findings` | 4 | 56,276 | 19,191 | **2.93×** |
| `monitor` | 4 | 178,162 | 67,093 | **2.66×** |
| `ladder` | 9 | 183,714 | 71,660 | **2.56×** |
| `watchdog` | 6 | 108,084 | 48,469 | **2.23×** |
| **Selected total** | **30** | **773,301** | **238,135** | **3.25×** |

This ratio is a **structural signal, not a quality verdict**. A large test/production ratio may be entirely justified by a rich behavioral surface.

The significant finding is that six related families alone contain roughly **0.77 MB of test source** around roughly **0.24 MB of production source**. At this scale, test scaffolding is a material subsystem and deserves deliberate reuse boundaries.

The strongest pilot candidate is `lane_mcp`: it has the highest measured structural ratio, but its v2 and review tests already demonstrate that fixture reuse can work.

### 2.3 The dominant duplication is not duplicate assertions

The repository shows at least three different forms of duplication:

1. **World-building duplication**  
   HOME/XDG isolation, temp directories, subprocess execution, cwd setup, cleanup, file planting, state snapshots, SQLite fixtures.

2. **Counterparty-simulation duplication**  
   Tests embed or construct fake external tools and executable scripts, sometimes as sizeable Python programs inside test modules.

3. **Behavior-pattern duplication**  
   Different components repeatedly prove the same classes of invariants:
   - invalid input refuses,
   - refusal does not mutate state,
   - host state is untouched,
   - malformed input does not kill the service,
   - secrets do not leak,
   - wire and CLI surfaces agree,
   - order does not alter semantics,
   - concurrent actors do not corrupt data,
   - bounded outputs obey limits,
   - temporary paths and unrelated metadata do not affect the assertion.

The third category is the highest-leverage target because it allows a new defect to become **one additional case for an existing invariant** rather than another custom fixture/test file.

---

## 3. Repository Evidence

### 3.1 `lane_mcp` already contains a local test framework

`ops/conductor/tests/test_lane_mcp.py` defines a substantial `_LaneMcpFixture` that owns:

- an isolated temporary HOME,
- scratch/work/cwd trees,
- a staged copy of the CLI under test,
- XDG state,
- synthetic configuration,
- synthetic dispatch records,
- SQLite monitor state,
- rollout data,
- RPC request construction,
- response extraction and assertions.

The v2 suite reuses this fixture rather than reconstructing it:

- `ops/conductor/tests/test_lane_mcp_context.py`
- `ops/conductor/tests/test_lane_mcp_review.py`

This is important evidence. The proposed framework is not speculative: **the repository already contains successful local examples of fixture abstraction.** The missing step is promotion of the generic pieces into a cross-subsystem testkit.

### 3.2 Some suites embed executable counterparties

`ops/conductor/tests/test_ladder_lever.py` contains embedded fake Python programs such as `DISPATCH_PY`, `LAUNCH_PY`, and `GH_PY`, then plants those programs into a synthetic tool environment.

That is legitimate testing behavior, but the implementation form matters: once several test families need fake CLIs or fake counterparties, each copy becomes another place to implement process recording, response control, failure injection, serialization, and cleanup.

The reusable abstraction should be:

> a generic fake executable/counterparty facility with data-driven behavior,

not another subsystem-specific fake framework.

### 3.3 Support-code mass already exists

The dispatch tests already have dedicated support modules, including a large `launch_support.py`. This is a second signal that reusable test infrastructure is forming organically.

The goal is not to remove support code. It is to make support code **generic where the behavior is generic**, keep component semantics in the component suite, and prevent every new subsystem from independently rebuilding the same world/process/state machinery.

---

## 4. Flakiness and Isolation Evidence

Recent CI history gives direct evidence for the classes the shared framework should own.

### 4.1 LD-21 — assertion searched the wrong surface

PR #135's CI failed on an unrelated hooks change because a telemetry test asserted that the string form of a planted number (`41`) was absent from the **entire serialized report**.

The report also contained fixture metadata, including a random temporary path:

`/tmp/worth-contract-m041w_6s/repo`

The `41` in the directory name triggered the assertion even though the measured values were correct.

The same commit passed on rerun.

PR #138 repaired the test by checking only the **measured fields** rather than IDs, paths, timestamps, hashes, windows, and other metadata.

This is a classic reusable testing rule:

> Assertions should target the contract's semantic projection, not incidental serialization.

A testkit can make the semantic projection the easy/default API.

### 4.2 LD-22 — live HOME pollution

PR #138 also documents a hook test that ran under the operator's HOME. The hook correctly wrote skill-miss telemetry, but the test therefore wrote fixture events into the live skills registry.

The repaired suite uses a temporary HOME and verifies that the live registry's size and mtime are unchanged.

This should not be a per-suite discovery.

A shared `TestWorld` should isolate, by default:

- `HOME`
- `XDG_STATE_HOME`
- `XDG_CONFIG_HOME`
- `XDG_CACHE_HOME`
- temporary directory
- cwd
- process environment
- known application state roots

A test that deliberately needs live or inherited state should have to opt in explicitly.

### 4.3 Shared self-hosted state has already caused test interference

Earlier conductor failures were caused by tests observing state created concurrently by live jobs on the persistent self-hosted runner.

The important design lesson is broader than the individual repair:

> "Synthetic fixture" is insufficient if the code under test can still discover shared host state.

Isolation should be an enforceable property of the world abstraction, not a convention each author must remember.

### 4.4 Concurrent fake logging has already raced

A fake `git` shim previously recorded invocations by reading the whole log and rewriting it. Multiple concurrent fake processes could overwrite each other's records. Replacing rewrite with append eliminated the lost-call behavior.

A generic fake process facility should therefore own:

- atomic or append-only call recording,
- per-invocation IDs,
- stdout/stderr/exit configuration,
- optional delays,
- failure injection,
- concurrency-safe logs,
- deterministic query APIs.

This removes another class of hand-rolled fake bugs from test authors.

### 4.5 Current ResourceWarnings are an architectural signal

Recent green CI still emits `ResourceWarning` messages for subprocesses and unclosed file objects in multiple suites.

They do not currently fail CI, but they indicate that process/file ownership is distributed across bespoke fixtures.

A shared world/process API should make resource ownership explicit and perform teardown checks centrally.

---

## 5. External Research Relevant to the Design

The repository evidence aligns with well-established testing research and practice.

### 5.1 Flaky tests undermine regression-test signal

Luo et al. studied 201 commits that likely repaired flaky tests across 51 open-source projects and classified common root causes of nondeterminism. Their core premise is directly relevant here: regression testing assumes repeatability; nondeterministic outcomes make test results harder to trust.

This supports treating flakiness as a system property to design against rather than a collection of isolated bad tests.

### 5.2 Hermetic environments reduce flakiness

Google's testing guidance repeatedly emphasizes hermeticity: tests that contain their dependencies and avoid uncontrolled external state are less likely to be flaky.

That maps directly to Agentscient's observed HOME pollution, shared self-hosted state, process races, and temporary-path sensitivity.

### 5.3 Test smells increase maintenance burden, but smell counts alone are weak

Empirical studies have found widespread test smells and negative effects on comprehension/maintenance. More recent work also warns that static smell detectors can over-classify or poorly correspond to real semantic problems.

For Agentscient this argues against inventing a simplistic "test smell score."

The better measurement is behavioral:

- what invariant does the test protect?
- what mutation/fault does it uniquely detect?
- what machinery does it require?
- what state can influence it?
- what runtime/maintenance cost does it impose?

### 5.4 Mutation testing measures fault-detection strength

Mutation testing deliberately introduces small faults and observes whether the test suite detects them. The mutation-testing literature is mature enough to support using mutation kill sets as a way to estimate overlap between tests.

For Agentscient, mutation testing is most useful **as a duplication instrument**, not as a coverage vanity metric.

If two tests:

- claim the same invariant,
- kill effectively the same mutations,
- and one adds no additional boundary/state dimension,

they are strong candidates for consolidation.

### 5.5 Property-based testing turns repeated examples into invariant checking

QuickCheck established the property-based model: define properties and generators rather than manually spelling every example.

Agentscient does not need a wholesale property-testing dependency to use the idea. The same model can be implemented incrementally with standard-library case generators for important invariant families.

Examples:

- all refusal variants preserve state,
- all malformed record shapes fail closed,
- arbitrary unrelated path/hash/timestamp strings cannot influence numeric-measurement assertions,
- ordering permutations preserve semantic output where ordering is unspecified.

### 5.6 Expressive test APIs reduce brittleness

Google's guidance on expressive test APIs is especially relevant to LD-21: tests should express the property that matters rather than pinning irrelevant representation details.

A reusable assertion such as:

`assert_measurements_exclude(planted_values)`

is both clearer and less brittle than searching the JSON rendering of an entire result object.

---

## 6. Proposed Architecture: `ops/testkit`

Do **not** replace `unittest`.

The existing runner is fast, simple, standard-library based, and already parallelizes suites effectively.

Add a reusable layer underneath/alongside existing suites:

```text
ops/testkit/
    __init__.py
    world.py
    command.py
    fake.py
    cases.py
    assertions.py
    invariants.py
    portfolio.py

    patterns/
        refusal.py
        no_mutation.py
        isolation.py
        ordering.py
        concurrency.py
        resource_hygiene.py
        wire_equivalence.py
        redaction.py
        bounded_output.py
```

The exact names are provisional. The ownership boundaries matter more than the filenames.

---

## 7. Core Primitive: `TestWorld`

`TestWorld` should create and own a hermetic execution world.

Illustrative responsibilities:

```python
with TestWorld() as world:
    result = world.run([...])
```

Default-owned state:

- isolated `HOME`,
- isolated XDG state/config/cache roots,
- isolated temp root,
- controlled cwd,
- sanitized environment,
- owned subprocess registry,
- owned file handles if exposed through helpers,
- synthetic executable path,
- optional network prohibition/guard where practical,
- before/after snapshots for forbidden paths.

Teardown responsibilities:

- reap/kill owned child processes,
- close owned handles,
- fail on leaked processes where appropriate,
- verify declared immutable/forbidden paths were unchanged,
- remove temporary state,
- surface cleanup errors instead of silently swallowing them.

### Design rule

**Hermetic should be default. Ambient should be explicit.**

A test requiring the real HOME, live repository state, actual credentials, or external services should be visibly classified as integration/live and should not accidentally inherit them because `os.environ.copy()` was convenient.

---

## 8. `CommandHarness`

All subprocess-based tests should receive one normalized result shape.

Example:

```python
result = world.command(
    ["python3", tool, "query", "lane_record", payload],
    timeout=30,
)
```

Potential result contract:

```text
result.argv
result.exit
result.stdout
result.stderr
result.duration
result.env_delta
result.cwd
result.files_before
result.files_after
result.files_changed
result.processes_left
```

Benefits:

- one timeout policy,
- one decoding/error policy,
- one process cleanup path,
- one call-recording model,
- easy no-mutation assertions,
- easy resource-leak assertions,
- easier diagnostics.

---

## 9. `FakeToolRegistry`

Tests repeatedly need fake CLIs and counterparties.

Instead of embedding a new script per suite:

```python
world.tools.install(
    "gh",
    responses=[
        Call(args=["pr", "view"], stdout="...", exit=0),
        Call(args=["api", "..."], stdout="...", exit=0),
    ],
)
```

The registry should support:

- exact/pattern argv matching,
- stdin matching,
- stdout/stderr,
- exit status,
- delay/timeout injection,
- malformed output,
- environment capture,
- cwd capture,
- ordered and unordered expectations,
- call count assertions,
- concurrency-safe append-only invocation logs.

Subsystem-specific fake semantics can extend this layer, but generic process emulation should exist once.

---

## 10. Invariants as First-Class Objects

The core conceptual change is:

> A test should identify the invariant it protects.

Example:

```python
RefusalCase(
    id="scope-file-missing",
    invariant="dispatch.invalid-input.refuses-without-mutation",
    argv=["--scope-file", "missing"],
    expect=Refusal(exit=2),
    origin="LD-...",
)
```

The pattern runner can automatically enforce shared properties:

```text
- refusal exit code/predicate
- stdout policy
- stderr grammar/policy
- owned state unchanged
- forbidden state unchanged
- no child process leaked
- no credential/live-state access
```

A new regression then ideally adds:

1. a new case,
2. a new boundary value,
3. or a genuinely new invariant.

It should not automatically require a new mini-framework.

---

## 11. Initial Invariant Families

The first framework should cover invariants that already recur in Agentscient.

### `refusal`

For invalid/unauthorized input:

- refuses with documented exit/result,
- explains the refusal,
- does not mutate forbidden state,
- does not partially execute,
- does not leak process/resource state.

### `no_mutation`

Snapshot a declared surface, invoke behavior, compare semantic/byte/metadata state according to policy.

Useful for:

- refusal,
- read/query operations,
- validation,
- dry runs,
- contract checks.

### `isolation`

Assert that activity is confined to the test world.

Examples:

- live HOME unchanged,
- live XDG store unchanged,
- no undeclared external file touched,
- no live dispatch record consumed,
- no ambient credential used.

### `wire_equivalence`

Where CLI and MCP/wire interfaces promise the same domain behavior:

- same semantic result,
- transport differences ignored where contract allows,
- same domain error/refusal meaning.

### `redaction`

Given planted secrets/sentinels:

- semantic output contains no secret,
- allowed identifiers remain,
- tests inspect the contract projection rather than arbitrary whole-object serialization.

### `ordering`

When order is unspecified or explicitly irrelevant:

- permuting input/listing/order does not alter semantic result.

This directly targets the class of bugs where tests accidentally depend on digest/filesystem/list ordering.

### `concurrency`

For append-only stores, logs, fake call records, queues:

- N concurrent operations produce N durable records,
- no lost updates,
- no partial records,
- deterministic reconstruction where promised.

### `resource_hygiene`

- child processes terminate,
- handles close,
- temporary resources are reclaimed,
- warnings/leaks become actionable failures in framework-owned code.

### `bounded_output`

For MCP/context surfaces with strict limits:

- valid output does not exceed cap,
- reduction/omission order follows contract,
- next legal whole item cannot fit when "full" is claimed,
- unrelated metadata does not affect size semantics unless contract says it does.

---

## 12. Case Tables Over Regression Files

Historical defects remain valuable. Their **history should not force permanent bespoke architecture**.

Instead of:

```text
test_bug_20260911_x.py
test_bug_20260912_y.py
test_bug_20260913_z.py
```

prefer, where semantics permit:

```python
REFUSAL_CASES = [
    RefusalCase(..., origin="LD-12"),
    RefusalCase(..., origin="LD-16"),
    RefusalCase(..., origin="LD-22"),
]
```

The defect ID remains evidence and provenance.

The shared pattern owns the mechanics.

A standalone regression test remains appropriate when the defect protects a genuinely unique behavior or is clearer as a focused scenario.

---

## 13. Measurement Framework: `portfolio.py`

Source-line reduction alone is not the goal.

The framework should continuously measure whether the portfolio is becoming **more informative per unit cost**.

### 13.1 Invariant density

```text
distinct invariants / test cases
```

Interpretation must be contextual. A low ratio can be healthy when many boundary cases exercise one important invariant, but it surfaces areas for inspection.

### 13.2 Pattern reuse rate

```text
cases using shared testkit patterns / eligible cases
```

Do not force 100%. Unique behaviors should remain explicit.

### 13.3 Scaffolding ratio

Measure fixture/helper/fake/support code against declarative case/assertion code.

This is more useful than raw test LOC because it shows how much code is spent constructing the testing apparatus.

### 13.4 Regression absorption rate

```text
historical regressions represented as cases of generalized invariants
---------------------------------------------------------------
eligible historical regressions
```

This measures whether the framework is actually preventing regression-file accretion.

### 13.5 Isolation-risk count

Count tests with undeclared use of:

- ambient HOME/XDG,
- live state directories,
- network,
- credentials,
- uncontrolled temp locations,
- real external programs,
- wall-clock timing,
- shared process state.

The exact detector can begin approximate and improve.

### 13.6 Flake rate

Track by test identity and invariant:

```text
same-code pass/fail outcome changes / executions
```

Retries should not erase the first-attempt signal.

### 13.7 Mutation kill set

For selected high-value modules, introduce sampled mutations and record which tests kill each mutation.

For test `T`:

```text
kill_set(T) = mutations detected by T
```

Potential redundancy is high when tests have:

- the same invariant,
- near-identical kill sets,
- the same state/boundary dimension,
- and one adds no distinct contractual observation.

### 13.8 Marginal detection value

Conceptually:

```text
unique faults/invariants detected
-------------------------------
runtime + maintenance burden
```

This need not become a fake single universal score immediately.

Store the underlying measurements first. Let later analysis determine useful economics from observed data.

---

## 14. Why Mutation Overlap Is Better Than Source Similarity

Source similarity catches only superficial duplication.

Two tests can:

- look completely different,
- build different fixtures,
- use different assertions,

yet fail on exactly the same faults.

Conversely, twenty table-driven boundary examples may look almost identical while each protects a distinct contract boundary.

Therefore:

> Source duplication is a hint. Fault-detection overlap is evidence.

Mutation testing provides a practical approximation of that overlap.

It should initially be sampled against hotspots rather than imposed on every CI run.

---

## 15. Framework Guardrails

The proposed framework should embody these defaults:

1. **Every reusable case names an invariant.**
2. **Hermetic execution is default.**
3. **Ambient/live dependencies require explicit opt-in.**
4. **Generic fake executable behavior comes from one registry.**
5. **Assertions operate on semantic projections where possible.**
6. **Exact representation is pinned only when the contract makes it exact.**
7. **Known test behavior used by multiple subsystems should graduate into `testkit`.**
8. **A flake repair should improve the generalized pattern when the root cause is generalized.**
9. **`testkit` remains domain-free.**
10. **No existing test is deleted solely because a new abstraction exists.**

The last rule is essential during migration.

---

## 16. Migration Strategy

### Phase 0 — Baseline only

Before refactoring:

- record current test inventory,
- file/byte counts,
- suite durations,
- first-attempt flake history where available,
- warnings,
- selected mutation baseline,
- live-state access inventory.

No test deletion.

### Phase 1 — Build generic primitives

Implement only:

- `TestWorld`,
- `CommandHarness`,
- minimal fake executable registry,
- no-mutation assertion,
- isolation assertion,
- resource teardown checks.

Test the testkit itself.

### Phase 2 — Pilot on `lane_mcp`

Why first:

- highest measured test/production structural ratio,
- existing reusable fixture,
- rich CLI/MCP behavior,
- filesystem + SQLite + RPC + bounded output,
- enough complexity to prove or disprove the abstraction.

Migration sequence:

1. preserve every existing behavior,
2. move only generic world/process pieces,
3. run old/new forms side-by-side if useful,
4. convert repeated scenario bodies into cases,
5. compare suite runtime and fault detection,
6. only then consider deletion/consolidation.

### Phase 3 — Dispatch wrapper

Second target because:

- 6.21× measured structural ratio,
- subprocess-heavy behavior,
- fake/counterparty needs,
- refusal/no-mutation/isolation patterns,
- existing large support machinery.

This phase is the real test of whether the abstractions generalize beyond lane MCP.

### Phase 4 — Ladder + monitor

These exercise:

- fake tool interaction,
- concurrency,
- process lifecycle,
- shared state,
- ordering,
- long-lived workflows.

If the same primitives serve these without domain leakage, the testkit boundary is probably correct.

### Phase 5 — Portfolio instrumentation

Once multiple families use the kit:

- invariant registry/report,
- scaffolding ratio,
- pattern reuse,
- isolation-risk scan,
- mutation overlap experiments,
- marginal-value analysis.

Only at this point should substantial test consolidation begin.

---

## 17. Acceptance Criteria

The framework should be judged by measurements, not aesthetics.

### Required

- No reduction in protected behavior during migration.
- No increase in first-attempt flake rate.
- No live HOME/XDG/state access in migrated hermetic suites.
- No leaked child processes from testkit-owned commands.
- Existing CI wall time remains acceptable.
- At least two materially different subsystems reuse the same generic primitives.
- Framework core contains no domain concepts such as lane, ladder, finding, dispatch, or telemetry.
- Regression provenance remains traceable.

### Desired

- Lower scaffolding ratio in migrated suites.
- New regressions increasingly arrive as new cases rather than new fixture machinery.
- ResourceWarnings disappear from migrated areas.
- Fewer duplicate fake executables.
- Measurable mutation kill-set overlap enables evidence-based consolidation.
- Better diagnostics: failures identify invariant + case + semantic difference.

### Failure condition

If a "generic" testkit accumulates subsystem knowledge or requires a second abstraction layer per subsystem, stop and reconsider the boundary.

The objective is **shared mechanics and invariant patterns**, not centralization for its own sake.

---

## 18. Non-Goals

Do not:

- replace `unittest` merely for stylistic reasons,
- migrate to pytest just to obtain fixtures,
- introduce broad path-based test skipping before understanding dependencies,
- reduce test count as a vanity metric,
- delete historical regressions without detection-equivalence evidence,
- force every test into a declarative DSL,
- make mutation testing a mandatory full-suite CI gate initially,
- hide complex scenarios behind abstractions that make failures harder to understand.

A good testkit should make common correct behavior cheaper while leaving unusual tests free to remain direct.

---

## 19. Recommended Local-Agent Research Tasks

Local agents can proceed independently on the following measurements without changing production code.

### A. Inventory testing machinery

Classify each test/support module into:

```text
case/assertion
fixture/world
subprocess runner
fake/counterparty
filesystem/state plant
DB plant
protocol/wire driver
snapshot/no-mutation
concurrency helper
other
```

Output byte/LOC totals by category and subsystem.

### B. Build an invariant inventory

For every test method in the pilot families:

```text
test ID
subsystem
invariant
boundary/state dimension
fixture class
external/fake dependencies
origin defect/contract if known
runtime if available
```

Do not infer multiple invariants merely from multiple assertions; identify the behavioral promise the test exists to protect.

### C. Find repeated mechanics

Search for repeated forms of:

- `TemporaryDirectory` / `mkdtemp`,
- HOME/XDG overrides,
- `subprocess.run` / `Popen`,
- executable planting / chmod,
- SQLite schema planting,
- JSON-RPC handshake helpers,
- before/after filesystem snapshots,
- leak/redaction sentinels,
- `assertEqual(returncode, ...)`,
- custom timeout handling,
- fake invocation logs.

Report candidates used in two or more subsystem families.

### D. Sample mutation overlap

Start with one production file from `lane_mcp` and one from `dispatch_wrapper`.

Use a small controlled set of mutations:

- inverted condition,
- removed validation,
- wrong exit,
- omitted field,
- wrong ordering,
- boundary ±1,
- disabled redaction,
- removed no-mutation guard.

Record which tests detect each mutation.

The goal is not mutation score. The goal is **test overlap structure**.

### E. Prototype without migration

Prototype:

- `TestWorld`
- `CommandHarness`
- `FakeToolRegistry`

Then reproduce several existing tests unchanged in semantic meaning.

Do not delete or rewrite the original suite until equivalence is demonstrated.

---

## 20. Reproduction Notes for Structural Measurement

The byte-ratio table is intentionally easy to remeasure.

At the measured commit, agents can use repository-native tooling, for example:

```bash
git checkout 032092c26521b674b626aa06aa0f3ea5585b6dec

wc -c \
  ops/conductor/tests/test_lane_mcp*.py \
  ops/conductor/tests/test_dispatch_wrapper*.py \
  ops/conductor/tests/test_findings*.py \
  ops/conductor/tests/test_monitor*.py \
  ops/conductor/tests/test_ladder*.py \
  ops/conductor/tests/test_watchdog*.py
```

Then measure the corresponding production modules selected for each family.

Because family boundaries can be debated, agents should preserve the exact path set they use in machine-readable output. The important property is reproducibility, not pretending there is one metaphysically perfect test/production ratio.

---

## 21. Decision Direction

The evidence supports building a shared testing framework now.

The preferred order is:

1. **standardize hermetic world/process ownership,**
2. **standardize fake/counterparty behavior,**
3. **standardize repeated invariant patterns,**
4. **measure semantic overlap,**
5. **then consolidate redundant tests.**

The framework should make the marginal cost of adding protection **decrease as the corpus grows**.

The desired end-state is not "fewer tests."

It is:

> Each additional test case should buy identifiable new behavioral information, while generic mechanics are paid for once.

---

# References

## Repository evidence

**Snapshot used for measurement**

- Agentscient `dev` merge commit `032092c26521b674b626aa06aa0f3ea5585b6dec`  
  https://github.com/uscient/agentscient/commit/032092c26521b674b626aa06aa0f3ea5585b6dec

**Primary test files**

- `ops/conductor/tests/test_lane_mcp.py`  
  https://github.com/uscient/agentscient/blob/032092c26521b674b626aa06aa0f3ea5585b6dec/ops/conductor/tests/test_lane_mcp.py
- `ops/conductor/tests/test_lane_mcp_context.py`  
  https://github.com/uscient/agentscient/blob/032092c26521b674b626aa06aa0f3ea5585b6dec/ops/conductor/tests/test_lane_mcp_context.py
- `ops/conductor/tests/test_lane_mcp_review.py`  
  https://github.com/uscient/agentscient/blob/032092c26521b674b626aa06aa0f3ea5585b6dec/ops/conductor/tests/test_lane_mcp_review.py
- `ops/conductor/tests/test_ladder_lever.py`  
  https://github.com/uscient/agentscient/blob/032092c26521b674b626aa06aa0f3ea5585b6dec/ops/conductor/tests/test_ladder_lever.py

**Suite runner / CI**

- `ops/bin/suites.sh`  
  https://github.com/uscient/agentscient/blob/032092c26521b674b626aa06aa0f3ea5585b6dec/ops/bin/suites.sh
- `.github/workflows/ci.yml`  
  https://github.com/uscient/agentscient/blob/032092c26521b674b626aa06aa0f3ea5585b6dec/.github/workflows/ci.yml

**Flake / isolation evidence**

- PR #135 — hooks: every refusal logs a miss against the skill it names  
  https://github.com/uscient/agentscient/pull/135
- GitHub Actions run `34644878635` — same-commit flaky failure described by LD-21  
  https://github.com/uscient/agentscient/actions/runs/34644878635
- PR #138 — LD-21 repair; also records LD-22 HOME pollution  
  https://github.com/uscient/agentscient/pull/138

PR #138 is especially useful as an evidence artifact because its description records:

- the random temp path that caused the LD-21 false match,
- deterministic reproduction under a TMPDIR containing a planted token,
- the field-projection repair,
- telemetry suite green at 227 tests,
- full nine-suite green at 2,727 tests,
- LD-22's temporary-HOME isolation repair.

**Additional workflow/triage evidence**

- PR #113 — examples of focused regression tests added around dispatch/findings behavior  
  https://github.com/uscient/agentscient/pull/113

---

## External literature / testing practice

1. Qingzhou Luo, Farah Hariri, Lamyaa Eloussi, Darko Marinov. **“An Empirical Analysis of Flaky Tests.”** FSE 2014, pp. 643–653. DOI: `10.1145/2635868.2635920`.  
   University of Illinois publication page:  
   https://experts.illinois.edu/en/publications/an-empirical-analysis-of-flaky-tests/  
   Paper:  
   https://mir.cs.illinois.edu/marinov/publications/LuoETAL14FlakyTestsAnalysis.pdf

2. George Pirocanac. **“Test Flakiness — One of the main challenges of automated testing.”** Google Testing Blog, 2020.  
   https://testing.googleblog.com/2020/12/test-flakiness-one-of-main-challenges.html

3. George Pirocanac. **“Test Flakiness — One of the main challenges of automated testing (Part II).”** Google Testing Blog, 2021.  
   https://testing.googleblog.com/2021/03/test-flakiness-one-of-main-challenges.html

4. Chaitali Narla, Diego Salas. **“Hermetic Servers.”** Google Testing Blog, 2012.  
   https://testing.googleblog.com/2012/10/hermetic-servers.html

5. Google Testing Blog. **“Test Sizes.”** 2010.  
   Describes Small/Medium/Large test classifications and dependency/resource expectations.  
   https://testing.googleblog.com/2010/12/test-sizes.html

6. Titus Winters. **“How I Learned To Stop Writing Brittle Tests and Love Expressive APIs.”** Google Testing Blog, 2024.  
   https://testing.googleblog.com/2024/04/how-i-learned-to-stop-writing-brittle.html

7. Yue Jia, Mark Harman. **“An Analysis and Survey of the Development of Mutation Testing.”** IEEE Transactions on Software Engineering.  
   https://crest.cs.ucl.ac.uk/fileadmin/crest/sebasepaper/JiaH10.pdf

8. Koen Claessen, John Hughes. **“QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs.”** ICFP 2000, pp. 268–279. DOI: `10.1145/351240.351266`.  
   Chalmers publication record:  
   https://research.chalmers.se/en/publication/237427

9. Gabriele Bavota et al. **“An empirical analysis of the distribution of unit test smells and their impact on software maintenance.”** ICSM 2012. DOI: `10.1109/ICSM.2012.6405253`.  
   https://ieeexplore.ieee.org/document/6405253/

10. Michele Tufano et al. **“An empirical investigation into the nature of test smells.”** Automated Software Engineering, 2016.  
    Microsoft Research publication page:  
    https://www.microsoft.com/en-us/research/publication/an-empirical-investigation-into-the-nature-of-test-smells/

11. **“Test smells 20 years later: detectability, validity, and reliability.”** Empirical Software Engineering, 2022.  
    Useful caution that static smell vocabularies/detectors do not perfectly correspond to real maintainability problems.  
    https://link.springer.com/article/10.1007/s10664-022-10207-5

---

## Interpretation note for agents

The external references support the direction; they do **not** override the repository's measured behavior.

When research terminology conflicts with Agentscient's actual contracts or evidence, preserve the repository semantics and use the literature as a design aid only.
