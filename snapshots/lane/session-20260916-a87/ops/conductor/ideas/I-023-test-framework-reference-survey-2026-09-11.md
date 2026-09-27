# Agentscient Test Framework Reference Survey
## Existing Projects, Measured Test-System Pressure, and Design Implications

**Date:** 2026-09-11  
**Status:** Research / local-agent handoff  
**Scope:** Test architecture, reuse, duplication reduction, and test-portfolio measurement  
**Change authority:** This document proposes research directions only. It does **not** authorize source, CI, test, dependency, or workflow changes.

---

## 1. Executive conclusion

Agentscient does not primarily have a "too many tests" problem.

It has reached the point where its **test corpus is itself a substantial software system**, and repeated testing behaviors should become reusable infrastructure rather than continue to accrete independently inside individual test files.

The evidence already supports that conclusion:

- the current CI executes about **2,727 tests**;
- the conductor suite accounts for about **927 tests**, roughly **34%** of the total;
- six obvious conductor test families alone contain about **773 KB of test source** around **238 KB of corresponding production source**, or about **3.25× as much test material as implementation**;
- the largest structural outlier measured so far is `lane_mcp`, at roughly **9.25× test-source mass versus its principal production module**;
- several recent CI defects were defects in the test system itself: random temporary-path collisions, ordering assumptions, concurrent log rewrites, shared live-state interaction, and use of real `HOME`.

None of those facts says "delete tests."

They say that **test-system architecture now matters**.

The target should be:

> **Preserve or increase independent fault-detection power while reducing bespoke test machinery, duplicated scenarios, incidental implementation pins, and maintenance cost.**

A useful future test should increasingly look like a small declaration of:

1. the **invariant** that matters;
2. the **case** or generated inputs that exercise it;
3. the **world/environment** in which it is exercised;
4. the **observation/history** produced;
5. the **checker/matcher** that decides correctness;
6. the **evidence** retained when it fails.

Several mature projects already implement pieces of this model. Agentscient should study them before inventing its own equivalent mechanisms.

The strongest references are:

1. **Jepsen** — generator → operations → history → checker architecture.
2. **Hypothesis** — reusable property and state-machine invariants, generated cases, shrinking.
3. **pytest-cases** — explicit separation of test protocol from test cases.
4. **Pact** — reusable contract matchers rather than over-specific equality.
5. **mutmut / Infection** — mutation testing as an empirical measure of test effectiveness.
6. **Zenstruck Foundry** — native Symfony fixture/state reuse; avoid reinventing the PHP/Symfony half.
7. **CrossHair** — selective symbolic counterexample search for pure Python contracts.
8. **testmon** — test-to-code dependency data and selective-test ideas, useful initially as measurement rather than CI policy.
9. **ApprovalTests / snapshot-style approaches** — selective normalization of large structured outputs, but only where full-object approval genuinely represents the contract.

The likely Agentscient architecture is **not** a new universal test runner. It is a small shared semantic layer and reusable test kit, with Python and Symfony using their best native mechanisms underneath.

---

## 2. Measured Agentscient baseline

### 2.1 Overall suite

Current measured CI characteristics:

- about **2,727 tests** total;
- about **927 conductor tests**;
- conductor therefore represents about **34%** of the test count;
- the full lane currently completes in roughly two minutes because suites run concurrently;
- raw runtime is therefore **not currently the primary pressure**.

The concern is instead:

- maintenance mass;
- duplicate scaffolding;
- duplicate behavioral evidence;
- false failures caused by test machinery;
- test-induced rigidity;
- increasing difficulty determining what each additional test uniquely contributes.

### 2.2 Selected structural ratios

Six conductor families were grouped by the production component they primarily exercise.

| Family | Test files | Approx. test bytes | Principal production bytes | Test / production |
|---|---:|---:|---:|---:|
| `lane_mcp` | 3 | 152,308 | 16,462 | **9.25×** |
| `dispatch_wrapper` | 4 | 94,757 | 15,260 | **6.21×** |
| `findings` | 4 | 56,276 | 19,191 | **2.93×** |
| `monitor` | 4 | 178,162 | 67,093 | **2.66×** |
| `ladder` | 9 | 183,714 | 71,660 | **2.56×** |
| `watchdog` | 6 | 108,084 | 48,469 | **2.23×** |
| **Selected total** | **30** | **773,301** | **238,135** | **3.25×** |

This is a **structural** metric, not a quality score.

A high test/implementation ratio can be justified when:

- behavior is safety-critical;
- the state space is large;
- refusal behavior is important;
- compatibility contracts are rich;
- adversarial and boundary behavior dominate simple happy paths.

Agentscient has several of those characteristics.

The ratio becomes important because it tells us where a reuse framework has the highest potential leverage.

### 2.3 Additional support machinery

The mass above also understates reusable-support pressure.

For example, the dispatch suite contains substantial dedicated support code, including a roughly 50 KB `launch_support.py`. Large conductor tests also embed fake counterparties, executable scripts, environment construction, process invocation, data-store setup, response parsing, and cleanup logic.

At that point, a test file is not merely a list of assertions. It is constructing a miniature execution system.

### 2.4 Confirmed test-system failure classes

Recent CI history has already exposed multiple classes of test-system defect:

1. **Random path contamination**
   - a planted token was searched across an entire serialized object;
   - an unrelated random temporary-directory name happened to contain the token;
   - the same commit failed and then passed on rerun.

2. **Ordering assumptions**
   - a test treated a digest-sorted filename listing as if it represented creation/newest order;
   - outcome depended on an unrelated ordering property.

3. **Shared mutable host state**
   - concurrent activity on the self-hosted machine changed the live store while a test was inspecting it.

4. **Concurrent log rewrite**
   - multiple fake processes rewrote a whole log file concurrently and lost entries.

5. **Real `HOME` pollution**
   - a test wrote fixture-generated misses into the operator's live skills registry.

6. **Resource hygiene**
   - current green runs still show `ResourceWarning` evidence for unreaped subprocesses or unclosed file objects.

These are not arguments against testing.

They are evidence that **the framework underneath tests needs stronger invariants of its own**.

---

## 3. What should be reused

Three distinct kinds of duplication should be treated separately.

### 3.1 World-building duplication

Repeated mechanics such as:

- isolated `HOME`;
- XDG state/config/cache;
- `TMPDIR`;
- working directories;
- environment cleanup;
- subprocess invocation;
- process reaping;
- owned filesystem roots;
- SQLite/database construction;
- filesystem snapshots;
- before/after mutation checks.

These should become reusable infrastructure.

### 3.2 Counterparty-simulation duplication

Repeated fake implementations of:

- Git/GitHub behavior;
- dispatch;
- launchers;
- worker commands;
- external CLIs;
- protocol endpoints;
- MCP/JSON-RPC counterparties.

These should increasingly become reusable protocol fakes with case-specific behavior supplied as data.

### 3.3 Behavioral-pattern duplication

Repeated semantic claims such as:

- invalid input refuses;
- refusal causes no mutation;
- secrets do not leak;
- malformed input cannot terminate a long-lived service;
- ordering does not change semantics;
- CLI and protocol surfaces agree;
- concurrent access cannot corrupt state;
- temporary-path names cannot affect meaning;
- resource ownership is discharged at exit;
- extra unconstrained fields do not break consumers;
- exact values are pinned only where the contract requires exactness.

This category matters most.

The long-term unit of reuse should be the **invariant or checker**, not merely a helper function.

---

# 4. External projects worth studying

---

## 4.1 Jepsen

**Project:** https://github.com/jepsen-io/jepsen  
**History library:** https://github.com/jepsen-io/history  
**Deterministic history simulator:** https://github.com/jepsen-io/history.sim

### Why it matters

Jepsen's architecture separates:

```text
generator
    ↓
operations
    ↓
system under test
    ↓
history
    ↓
checker
```

Fault injection is separately composable.

The test does not have to scatter its definition of correctness across every operation. Operations produce a **history**; a checker analyzes the history.

Jepsen also retains the test, history, analysis, and supporting results as inspectable evidence.

The separate `jepsen.history` project is especially relevant. Its stated goal includes a small reusable footprint that **de-duplicates history-analysis routines** that otherwise become repeated between Jepsen and individual checkers.

`history.sim` adds another useful idea: deterministic generation of histories with specific anomaly classes so checkers themselves can be tested against controlled known behavior.

### What Agentscient should borrow

Conceptually:

```text
World
  +
Generator / Cases
      ↓
Operation history
      ↓
Subject adapter
      ↓
Observation
      ↓
Invariant checker
      ↓
Evidence
```

Particularly valuable ideas:

- operations as structured records;
- explicit invocation/completion/failure;
- checker separate from scenario generation;
- fault injection separate from correctness definition;
- histories retained for post-hoc analysis;
- deterministic simulated histories for testing checkers;
- reusable history primitives rather than bespoke per-test event formats.

### What not to import automatically

- Clojure as an implementation choice;
- distributed-database-specific models;
- SSH/node orchestration;
- Jepsen's exact operation schema;
- Jepsen-scale infrastructure where a simple unit/contract test is sufficient.

The value is the **architecture**, not direct adoption of the full stack.

### Local-agent research questions

1. What is the smallest useful Agentscient operation/history record?
2. Which current conductor tests already implicitly build histories?
3. Can refusal, mutation, process, filesystem, and protocol observations share one event representation?
4. Can a checker run equally against:
   - deterministic examples;
   - randomized/property-generated cases;
   - historical CI failures;
   - mutation-testing runs?
5. Can test failures preserve a replayable history cheaply?

---

## 4.2 Hypothesis

**Stateful testing:** https://hypothesis.readthedocs.io/en/latest/stateful.html  
**General documentation:** https://hypothesis.readthedocs.io/

### Why it matters

Hypothesis can generate not merely input values but entire **sequences of actions**.

Its rule-based state machines provide:

- generated operations;
- preconditions;
- reusable value strategies;
- state-aware action sequences;
- invariants checked after actions;
- shrinking of failures toward smaller counterexamples.

This maps directly to Agentscient behavior where correctness depends on sequences such as:

```text
create
→ dispatch
→ refuse
→ retry
→ correct
→ close
```

or:

```text
read
→ concurrent mutation
→ read
→ verify isolation
```

### What Agentscient should borrow

- **properties/invariants rather than enumerated examples** where practical;
- generated hostile names/paths/Unicode/lengths/orderings;
- state-machine testing for lifecycle behavior;
- shrinking so discovered failures become minimal examples;
- reusable strategies for common Agentscient data types.

Example semantic target:

```text
for every generated temporary path:
    unrelated characters in that path
    cannot change a usage-currency result
```

That is stronger than retaining a regression case for the one random path that happened to break LD-21.

### What not to import automatically

- property testing for behavior that is better represented by one clear deterministic contract case;
- unrestricted randomized tests in CI without reproducibility;
- giant strategies that obscure which invariant failed;
- Hypothesis state machines for simple pure functions.

The rule should be: **use generated input when it covers a failure class better than enumerated examples**.

### Local-agent research questions

1. Which historic defects represent input classes that Hypothesis can generate?
2. Can hostile `HOME`, `TMPDIR`, filename, Unicode, ordering, byte-length and malformed-JSON inputs be shared as strategies?
3. Which conductor workflows are genuine state machines?
4. Can shrunk failures be persisted as ordinary deterministic regression cases automatically or semi-automatically?
5. Does Hypothesis materially reduce case source while preserving detection?

---

## 4.3 pytest-cases

**Project:** https://github.com/smarie/python-pytest-cases  
**Docs:** https://smarie.github.io/python-pytest-cases/  
**PyPI:** https://pypi.org/project/pytest-cases/

### Why it matters

Its explicit goal is to **separate test code from test cases**.

That is almost exactly the refactoring direction Agentscient needs:

```text
Current tendency:

test_one_failure():
    build world
    install fake
    run command
    parse result
    assert refusal
    assert no mutation
    assert no leak

test_second_failure():
    rebuild most of the above
    ...
```

versus:

```text
case = RefusalCase(...)

verify(REFUSAL_WITHOUT_MUTATION, case)
```

`pytest-cases` is worth studying even if Agentscient never adopts it as a dependency.

### What Agentscient should borrow

- case data separated from test protocol;
- reusable case functions;
- parametrization over behaviors rather than repeated test bodies;
- composable fixtures where native pytest use makes sense.

### Important compatibility point

The existing lane uses `unittest`.

Moving the entire suite to pytest is **not justified merely to get this abstraction**.

Python's existing tests can be discovered by pytest, but that is still a test-runner/tooling decision and should be evaluated separately.

### Local-agent research questions

1. How much of the desired separation can be implemented with standard-library `unittest`?
2. Would pytest adoption create enough value beyond reusable cases to justify migration?
3. Can a small Agentscient-native `Case`/`Pattern` layer remain runner-neutral?
4. How much current test LOC disappears when scenario data is separated from protocol?

---

## 4.4 Pact

**Docs:** https://docs.pact.io/  
**Matching concepts:** https://docs.pact.io/implementation_guides/javascript/docs/matching

### Why it matters

Pact focuses on **contracts at integration boundaries**.

Two particularly useful ideas for Agentscient:

1. test counterparties in isolation against a shared contract;
2. use **matching rules** instead of demanding exact equality for data the consumer does not actually constrain.

Pact explicitly supports matching by:

- exact value;
- type;
- number/integer;
- regex;
- date/time formats;
- collection rules;
- composed rules.

The architectural lesson is not limited to HTTP.

Agentscient has many boundaries:

- CLI ↔ caller;
- launcher ↔ dispatch;
- monitor ↔ store;
- MCP ↔ consumer;
- service ↔ telemetry;
- workflow ↔ state.

### What Agentscient should borrow

A contract assertion should pin only what the contract actually owns.

Instead of:

```text
actual == enormous fully serialized expected object
```

prefer:

```text
schema == expected schema
state ∈ allowed states
id matches required grammar
required fields satisfy matchers
secret fields absent
events monotonic
unconstrained fields ignored
```

This can reduce both brittle tests and accidental conversion of implementation choices into compatibility guarantees.

### What not to import automatically

- Pact broker infrastructure unless Agentscient later has a real use for it;
- HTTP-centric assumptions;
- consumer-driven contract semantics where the ownership model is different;
- matcher looseness where Agentscient deliberately requires exact output.

### Local-agent research questions

1. Which current exact assertions represent genuine contract requirements?
2. Which `PIN_*` behaviors exist because the test needed *some* value rather than because the contract owns that value?
3. Can Agentscient define reusable matcher primitives?
4. Can the same matcher vocabulary be used in Python and PHP?

---

## 4.5 mutmut

**Project:** https://github.com/boxed/mutmut  
**Docs:** https://mutmut.readthedocs.io/

### Why it matters

Mutation testing changes production code in small ways and observes whether the test suite detects those changes.

That gives a more useful measurement than line coverage:

> Did the test suite notice a plausible behavioral fault?

Current mutmut emphasizes:

- incremental cached work;
- parallel execution;
- selecting relevant tests;
- mutation filtering;
- pytest integration.

Its documentation also warns about functions that are only incidentally exercised by huge swaths of a codebase, because that can make failures difficult to localize. That concern is directly relevant to test-portfolio design.

### What Agentscient should borrow

Mutation data can support:

- mutant → killing-test relationships;
- tests with identical or highly overlapping kill sets;
- unique mutant kills per test/pattern;
- surviving mutants;
- functions reached only incidentally by broad tests;
- marginal detection value.

A useful long-term measure could be:

```text
unique useful fault detections
──────────────────────────────
test maintenance + runtime cost
```

Mutation testing should provide evidence, not become an objective function by itself.

### Important compatibility point

Current mutmut 3.x is pytest-oriented.

The existing Agentscient Python suite is primarily `unittest`.

Therefore a mutmut pilot should first determine whether running existing tests through pytest is sufficiently compatible and whether the measurement value justifies adding that dependency/tooling path.

### What not to do

- do not maximize mutation score blindly;
- do not add nonsense assertions merely to kill every mutant;
- do not treat equivalent or invalid mutants as product defects;
- do not make mutation testing mandatory on every normal CI run initially;
- do not delete tests solely because they do not produce unique kills in a small sample.

### Local-agent research questions

1. Can a representative conductor family run unchanged under pytest?
2. Can mutmut identify which tests kill which mutants at useful granularity?
3. How stable are kill sets across runs?
4. Can kill overlap identify likely redundant regression families?
5. What is the runtime cost for a bounded pilot?

---

## 4.6 Infection

**Project:** https://github.com/infection/infection  
**Docs:** https://infection.github.io/

### Why it matters

Infection is the corresponding mature mutation-testing ecosystem for PHP.

It supports PHPUnit-oriented mutation testing and explicitly distinguishes line execution from tests that actually detect behavior changes.

It also supports static-analysis integration. A useful design lesson is that some mutants that violate an established type/static contract can be rejected by static analysis rather than forcing developers to add unnecessary runtime tests solely to kill them.

### What Agentscient should borrow

For the Symfony production lane:

- mutation testing as an effectiveness measurement;
- mutation score tracked as evidence, not dogma;
- diff-scoped mutation runs for experimentation;
- interaction with PHPStan/static analysis where appropriate.

### What not to do

Do not force symmetry for symmetry's sake.

Python and PHP can share the **measurement vocabulary** without sharing the same test implementation.

### Local-agent research questions

1. What Symfony service class is a small but representative pilot?
2. How does Infection behave with the project's PHPUnit/Symfony configuration?
3. Which mutants are killed by static analysis rather than runtime tests?
4. Can mutation evidence be normalized into the same portfolio schema as Python?

---

## 4.7 Zenstruck Foundry

**Docs:** https://symfony.com/bundles/ZenstruckFoundryBundle/current/index.html  
**Project:** https://github.com/zenstruck/foundry

### Why it matters

Foundry already solves several forms of repeated Symfony test setup:

- factories;
- reusable factory states;
- stories;
- fixture grouping;
- database reset;
- integration with Symfony/PHPUnit conventions.

Its database reset facilities are especially relevant to the isolation goal.

### What Agentscient should borrow

Use native Symfony ecosystem solutions for native Symfony problems.

If Foundry already provides:

- reusable object construction;
- scenario/story setup;
- reset semantics;
- fixture reuse;

then an Agentscient test framework should **compose with it**, not reproduce it.

### Local-agent research questions

1. Which current Symfony fixture/setup code overlaps Foundry capabilities?
2. Are Stories a useful representation for reusable test worlds?
3. Does Foundry's reset model align with Agentscient's storage semantics?
4. Where should Agentscient stop and Foundry begin?

---

## 4.8 CrossHair

**Docs:** https://crosshair.readthedocs.io/

### Why it matters

CrossHair repeatedly executes typed Python functions with **symbolic inputs**, using an SMT solver to search viable paths for counterexamples to declared contracts.

That can complement both example tests and property tests.

It is potentially valuable for small pure or mostly pure functions such as:

- parsers;
- bounds;
- validators;
- normalization functions;
- ordering logic;
- numeric accounting;
- state-transition predicates.

### What Agentscient should borrow

Potential selective use where:

- the function is small enough for symbolic exploration;
- its contract can be stated precisely;
- enumerating edge cases manually creates lots of repetitive tests.

### What not to do

Do not make symbolic execution a universal testing strategy.

Subprocess-heavy, filesystem-heavy, external-state-heavy conductor behavior is not its natural target.

---

## 4.9 testmon

**Docs:** https://www.testmon.org/

### Why it matters

testmon records dependencies between tests and executed project code using coverage data, then uses that database to identify tests affected by code changes.

Even if Agentscient should **not yet use selective test execution in CI**, the dependency graph itself is interesting.

It could help measure:

- broad tests touching many unrelated components;
- test families with highly overlapping execution surfaces;
- tests with surprisingly indirect dependencies;
- hidden coupling.

### What Agentscient should borrow

Initially: **measurement only**.

Do not use dependency selection to weaken full-suite correctness until the test architecture is better understood.

### Local-agent research questions

1. Can test→code dependency data be extracted without adopting selective CI?
2. Does it correlate with mutation kill overlap?
3. Which tests execute unexpectedly wide surfaces?
4. Can dependency entropy become another portfolio metric?

---

## 4.10 Approval/snapshot testing

**Example project:** https://github.com/approvals/ApprovalTests.Python

### Why it matters

Some tests contain many individual assertions only because they are validating one large structured output.

Approval/snapshot techniques can reduce assertion boilerplate by normalizing the output and comparing it with an approved representation.

### Appropriate uses

Potentially useful for:

- stable human-readable reports;
- normalized generated manifests;
- intentionally exact CLI help;
- serialization that is itself the contract.

### Risks

Snapshots can become **giant implementation pins**.

They are dangerous when developers approve changes without understanding them, or when only a small subset of fields is contractually meaningful.

Use matcher-style assertions instead when the representation contains unconstrained data.

---

# 5. Architectural synthesis for Agentscient

The common idea across these projects can be expressed without adopting a universal external framework.

## 5.1 Shared semantic vocabulary

Possible domain-neutral concepts:

```text
Invariant
Case
Generator
World
Operation
Observation
History
Checker / Matcher
Evidence
Cost
Origin
```

### Invariant

A named fact that must remain true.

Examples:

```text
refusal.no-mutation
secret.never-emitted
temporary-path.semantic-independence
ordering.creation-not-filename
process.no-leak
rpc.server-survives-domain-error
```

### Case

A deterministic example or parameter set that exercises an invariant.

Historical regressions should usually become **cases attached to an invariant**, not permanently independent mini-frameworks.

### Generator

Produces additional cases or action sequences.

Possible implementations:

- static table;
- Hypothesis strategy;
- Hypothesis state machine;
- deterministic simulator;
- historical failure corpus.

### World

Owns execution state:

- `HOME`;
- XDG dirs;
- temp tree;
- env;
- process ownership;
- DB/store state;
- fake tool registry;
- network policy if applicable.

### Operation / History

Structured record of what happened.

A history can support:

- failure replay;
- concurrency analysis;
- checker reuse;
- CI evidence;
- post-hoc telemetry.

### Checker / Matcher

The reusable definition of correctness.

This is where maximum semantic reuse should live.

### Evidence

Failure artifact:

- invariant ID;
- case ID;
- seed;
- operation history;
- stdout/stderr;
- filesystem delta;
- process/resource delta;
- minimal/shrunk input where applicable.

### Cost

Portfolio telemetry:

- runtime;
- setup mass;
- flake history;
- maintenance/change rate;
- mutant kills;
- unique mutant kills;
- execution surface;
- dependency fan-out.

---

# 6. Proposed implementation boundary

Do **not** begin by creating a new test runner.

A likely shape is:

```text
                   Agentscient test vocabulary
          invariant / case / history / evidence / cost
                         /                 \
                        /                   \
               Python adapter            PHP adapter
          unittest + optional         PHPUnit + Symfony
             Hypothesis                 Foundry
              mutmut                    Infection
```

The semantic model can be shared while implementations remain native.

For the current Python lane, a small package such as:

```text
ops/testkit/
    world.py
    command.py
    fake.py
    history.py
    cases.py
    matchers.py
    evidence.py
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
```

is a plausible shape for investigation.

This is **not a requested implementation**. It is a concrete target against which local agents can compare external projects and current code.

---

# 7. Example of the desired compression

Current style often has to spell out mechanics repeatedly:

```text
construct isolated HOME
construct config
install fake binary
run subprocess
parse JSON
assert exit
assert stderr
snapshot directory
compare directory
check live HOME
check child process
clean temporary resources
```

A reusable pattern should make the semantic content dominant:

```python
RefusalCase(
    id="missing-scope-file",
    invariant="dispatch.invalid-input.refuses-without-mutation",
    argv=["--scope-file", "missing"],
    expect=Refusal(exit=2),
    origin="LD-...",
)
```

A shared checker can own:

```text
expected refusal exit
refusal grammar
stdout policy
stderr policy
owned-state unchanged
forbidden-state unchanged
no live-host mutation
no resource leak
```

A second component can use the same invariant pattern with different arguments.

That is the principal form of duplication reduction being sought.

---

# 8. Test-portfolio measurement

Test count should become a secondary metric.

The more useful measurements are:

## 8.1 Invariant count

How many distinct, named behavioral claims does the suite protect?

## 8.2 Cases per invariant

Large ratios may be healthy for boundary/property testing or may indicate accumulated historical examples. The ratio needs interpretation.

## 8.3 Pattern reuse rate

Percentage of cases using standard world/checker/pattern infrastructure rather than bespoke machinery.

## 8.4 Scaffolding ratio

Approximate:

```text
fixture + fake + setup + parser + helper LOC
───────────────────────────────────────────
case + invariant LOC
```

The goal is for the marginal test to become cheap.

## 8.5 Regression absorption

When a defect is found:

```text
Did it add another independent test artifact?
```

or:

```text
Did it strengthen an existing invariant/generator/pattern?
```

The latter should increasingly be preferred.

## 8.6 Mutation overlap

For a sampled set of mutants:

```text
mutant → {tests/patterns that kill it}
```

This permits measurements such as:

- unique kills;
- overlapping kills;
- identical/near-identical kill sets;
- surviving mutants.

Tests that express the same invariant **and** have effectively identical kill sets are strong consolidation candidates.

## 8.7 Dependency overlap

Coverage/testmon-like data can add:

```text
test → {production functions/modules exercised}
```

High overlap does not prove duplication, but combined with invariant identity and mutation overlap it becomes strong evidence.

## 8.8 Flake/repair cost

Track per pattern/test:

- nondeterministic failures;
- repairs;
- resource warnings;
- host-state incidents;
- test-only regressions.

## 8.9 Marginal detection value

The long-term economic measure is approximately:

```text
independent useful fault detection
──────────────────────────────────
runtime + maintenance + rigidity + flake cost
```

This does not need to become one magic scalar.

The component measurements are more valuable than an oversimplified score.

---

# 9. Recommended local-agent investigation

## Phase A — no migrations, no deletions

Create a measured census for representative families.

Suggested first families:

1. `lane_mcp`
2. `dispatch_wrapper`
3. `monitor`
4. `ladder`

For every test/case, record where practical:

- file;
- test name;
- contract/invariant;
- origin/LD/PR if known;
- setup helpers;
- fake counterparties;
- production surface;
- exact/shape/order assertions;
- environment dependencies;
- runtime;
- known flake/repair history.

Deliverable: **data and findings only**.

## Phase B — external-pattern comparison

For each candidate project in this report, produce:

```text
use directly
borrow architecture
borrow vocabulary
reject for this problem
```

Require concrete evidence.

Do not choose a dependency merely because its vocabulary sounds similar.

## Phase C — one framework pilot

`lane_mcp` is a strong candidate because:

- its test/production structural ratio is the largest measured;
- it already demonstrates fixture inheritance/reuse;
- it has CLI + JSON-RPC behavior;
- it has rich boundary and malformed-input behavior;
- it contains meaningful contract semantics.

The pilot should:

1. preserve current test semantics;
2. extract reusable world/process/protocol mechanics;
3. name a small set of invariants;
4. express some existing tests as cases;
5. run old/new forms side by side;
6. compare failures and runtime;
7. make **no deletions** until equivalence is demonstrated.

## Phase D — mutation/effectiveness pilot

On a bounded surface:

- Python: evaluate mutmut compatibility and collect mutant→test data;
- PHP: evaluate Infection on a representative Symfony service.

Do not optimize for score.

Ask instead:

- which tests add unique detection?
- which patterns kill broad fault classes?
- where are tests correlated?
- what survives despite high line coverage?

## Phase E — decide architecture from evidence

Only after the pilots should Agentscient decide:

- whether pytest is useful or unnecessary;
- whether Hypothesis becomes a dependency;
- whether a runner-neutral internal case model is enough;
- what belongs in `ops/testkit`;
- what belongs in Symfony-native testing;
- whether operation-history evidence is worth standardizing;
- which old regression artifacts can safely collapse into generalized invariants.

---

# 10. Guardrails

The framework should not become another source of test entropy.

Recommended constraints:

1. **Testkit remains domain-neutral.**  
   If generic test infrastructure starts knowing what a ladder, finding, or specific service means, abstraction has leaked.

2. **Every reusable pattern names the invariant it checks.**

3. **Historical regression IDs are metadata, not architecture.**

4. **Exact output is asserted only when exactness is contractual.**

5. **Unit/contract worlds are isolated from operator state by default.**

6. **Fake counterparties are reusable protocol implementations, not repeatedly embedded scripts.**

7. **Generated tests must produce reproducible failures.**

8. **Mutation score is evidence, not a target to game.**

9. **Full CI should not become selectively weakened merely because dependency-selection tooling exists.**

10. **No test deletion based solely on age, size, execution frequency, or "never failed."**

11. **A new dependency needs measurable leverage over a small internal abstraction.**

12. **Framework complexity must itself be measured.**

---

# 11. Project ranking for Agentscient

| Project | Primary value | Direct use? | Reference value | Priority |
|---|---|---:|---:|---:|
| Jepsen | operation/history/checker architecture | Low | **Very high** | **1** |
| Hypothesis | properties, state machines, shrinking | **High** for selected Python areas | **Very high** | **1** |
| mutmut | effectiveness / overlap measurement | Pilot | **High** | **1** |
| Infection | PHP mutation measurement | Pilot | **High** | **1** |
| Pact | matchers and contract boundaries | Selective | **Very high** | **1** |
| pytest-cases | case/protocol separation | Maybe | **High** | **2** |
| Zenstruck Foundry | Symfony world/fixture reuse | **High if applicable** | **High** | **1** |
| CrossHair | symbolic counterexamples | Selective | Medium | 3 |
| testmon | dependency measurement | Selective / measurement | High | 3 |
| ApprovalTests | large exact-output validation | Narrow | Medium | 4 |

The priority indicates **research relevance**, not approval for installation.

---

# 12. The key design decision

The question is not:

> "How can Agentscient have fewer tests?"

It is:

> **"How can one unit of testing knowledge be expressed once and reused across many cases, while retaining evidence that the resulting suite detects at least as many independent faults?"**

The external projects strongly suggest an answer:

```text
Reusable world
+ reusable operation model
+ reusable invariants/checkers
+ cheap cases/generators
+ retained evidence/history
+ mutation/dependency measurements
```

That would change the growth curve.

Today, a defect can create:

```text
new regression file
+ new fixture
+ new fake
+ new assertions
+ new maintenance surface
```

The desired future is closer to:

```text
existing invariant
+ one new case
```

or, better:

```text
existing invariant
+ improved generator
```

or, when genuinely new behavior is discovered:

```text
one new invariant
+ reusable checker
+ representative cases
```

That is the test framework worth building.

---

# 13. Sources / reference material

## Agentscient evidence

- Current CI workflow:  
  https://github.com/uscient/agentscient/blob/dev/.github/workflows/ci.yml
- Current suite runner:  
  https://github.com/uscient/agentscient/blob/dev/ops/bin/suites.sh
- Example same-commit rerun flake / LD-21 precursor:  
  https://github.com/uscient/agentscient/actions/runs/34644878635
- Repair PR #138:  
  https://github.com/uscient/agentscient/pull/138
- Shared live-store race repair PR #114:  
  https://github.com/uscient/agentscient/pull/114
- Concurrent fake-git logging repair PR #103:  
  https://github.com/uscient/agentscient/pull/103
- Real-HOME pollution repair PR #136:  
  https://github.com/uscient/agentscient/pull/136

## External projects

### Jepsen
- https://github.com/jepsen-io/jepsen
- https://github.com/jepsen-io/history
- https://github.com/jepsen-io/history.sim

### Hypothesis
- https://hypothesis.readthedocs.io/
- https://hypothesis.readthedocs.io/en/latest/stateful.html

### pytest-cases
- https://github.com/smarie/python-pytest-cases
- https://smarie.github.io/python-pytest-cases/
- https://pypi.org/project/pytest-cases/

### Pact
- https://docs.pact.io/
- https://docs.pact.io/consumer
- https://docs.pact.io/implementation_guides/javascript/docs/matching

### mutmut
- https://github.com/boxed/mutmut
- https://mutmut.readthedocs.io/

### Infection
- https://github.com/infection/infection
- https://infection.github.io/

### Zenstruck Foundry
- https://github.com/zenstruck/foundry
- https://symfony.com/bundles/ZenstruckFoundryBundle/current/index.html

### CrossHair
- https://crosshair.readthedocs.io/

### testmon
- https://www.testmon.org/

### ApprovalTests.Python
- https://github.com/approvals/ApprovalTests.Python

---

## Final note to local agents

Do not begin by selecting a framework.

Begin by measuring the present test system and identifying the repeated **semantic patterns** beneath the files.

External projects should be used to answer concrete questions:

- Has this abstraction already been solved well?
- Is there a battle-tested vocabulary we should reuse?
- Is a dependency justified, or is the architectural lesson enough?
- Can the proposal demonstrate equal or greater detection with less bespoke machinery?
- Does it reduce future marginal test cost?
- Can its value be measured?

The success criterion is not elegance and not raw test-count reduction.

It is:

> **more independent confidence per unit of test-system complexity.**
