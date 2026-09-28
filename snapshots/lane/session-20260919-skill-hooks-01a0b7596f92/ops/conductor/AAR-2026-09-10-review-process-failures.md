# Debrief: review churn, invalid TDD evidence, and test growth

Status: incident analysis and corrective work record, not a declaration that
review enforcement is implemented or that delivery is complete.

Recorded from measurements at **2026-09-10 01:51 UTC**, against trunk
`20f9bcaf2b3ae2152b9cab766637b5a89b71214b` and the branch heads below.
The owner requested tests first, verified RED followed by GREEN, bounded
finding admission, and draft PRs into dev. Those requirements remain in force.

## 1. What actually failed

The immediate failure was not Git synchronization. It was how I conducted the
work. I treated test creation, a nonzero test exit, and independent review as
sufficient evidence to proceed without establishing that the test fixtures and
expected behavior agreed with the declared contract. They did not always agree.
I then allowed corrections and additional review work to accumulate.

Some tests stopped at an absent API before reaching their faulty downstream
assertions. Others omitted prerequisites while expecting success, or expected
opposite results from the same setup. One monitor test demanded OIDs in an event
whose declared evidence contained only `repo`, `remote`, and `ref`. The worker
started changing the event contract to satisfy that test. That was scope
expansion, not a justified implementation correction.

I also commissioned a much larger enforcement design than the initial finding
filter required. The owner subsequently required real enforcement of fixture
proof, repeat-review eligibility, and completion criteria; that requirement
was legitimate. Turning it into an extensive work-order and receipt protocol,
then accepting a large but incoherent test batch as progress, was my design and
execution decision. The owner did not request thousands of test lines or
unbounded review rounds.

**Responsibility rests with the conducting assistant.** Worker mistakes and
insufficient reviews are evidence of the failure; they do not transfer that
responsibility to the user. More apologies, more test cases, and more review
stages do not repair it.

## 2. What happened to TDD

Tests came first chronologically. Valid TDD requires more than chronology:
the independently authored test must fail because the intended behavior is
absent or wrong, with its other prerequisites already established.

The broken sequence was:

1. Write independent tests.
2. Run them against absent or incomplete behavior.
3. Treat early failures as proof of the whole test's validity.
4. Begin implementation.
5. Discover that later assertions or fixture assumptions were wrong.
6. Correct tests and repeat parts of the workflow.

Steps 3 and 4 were the control failure. A missing-API failure can establish that
an API is absent. It cannot establish that an event assertion, retained producer
record, or later success-path setup is correct. A corrected test rerun red
against old source is new evidence; it does not retroactively validate the
original TDD sequence.

I also started one monitor correction while its independent test review was
still running. That exposed the unsupported event-OID requirement only after
implementation had begun. The review later approved that test batch and missed
the same contradiction. Thus neither chronological RED nor multiple producers
was sufficient in this run.

The recovery must preserve both histories: the failed earlier sequence and the
later valid sequence. It must not relabel invalid fixture evidence as an honest
RED, silently change frozen tests, or claim unchanged test hashes when they
changed between cycles.

## 3. Concrete incidents and their causes

| Incident | Reachable failure and evidence | Cause / disposition |
|---|---|---|
| Explicit empty branches became defaults | A helper replaced `[]` with valid branches, so the supposed invalid-input case never planted the invalid input. Correction retained in `20260910T003157Z-tests-grok-298598`. | Test-fixture defect. An explicit empty value is not an absent value. |
| Existing event interface was guessed | Monitor tests expected values and unavailable summaries different from the established consumer. Correction retained in `20260910T003832Z-tests-grok-53065e`. | I withheld established implementation context too broadly and did not require a working consumer control before missing-API RED. |
| Independent admission fixtures lacked bindings | Missing dependencies/provenance, keys outside the mocked batch, and raw-report inputs conflicting with the admission contract required correction in `20260910T003757Z-tests-grok-49b66c`. | Fixture prerequisites were not verified as a coherent set. |
| Preserved source could not be recovered | Closed write jobs had exit 0, invalid envelopes, committed source and no residual files. `collect` required nonzero/tripped attempts plus residue. Records `20260910T001457Z-code-codex-8b77f2` and `20260910T002932Z-code-codex-4d6fb6` were refused. | Real recovery-interface gap. Paid source replays were unnecessary overhead. Direct repair now permits explicitly verified recovery of the exact preserved commit. |
| Parallel activity failed an isolation guard | The admission full suite at `16f8709` failed in teardown when a separate canonical launcher created `.launcher.iCO9sU`. The tested onboarding assertion passed. | Guard recognized new job directories but not the wrapper's transient logs. Direct repair normalizes only their exact canonical names; ordinary mutations still fail. |
| Malformed Git metadata stopped monitoring | A regular `.git` file containing `not a gitdir pointer` caused a valid monitor run to refuse, even with that source disabled, blocking a healthy sibling. Finding `20260910T010725Z-review-grok-2a62fd#1` was reproduced directly. | Real adapter defect, admitted for correction. Readable invalid metadata now becomes observation unavailability while storage separation remains enforced. |
| A new test expanded event evidence | `assert_healthy_sibling_observed` rejected the unchanged healthy consumer because it could not find OIDs anywhere in its freshness events. The contract explicitly declared evidence `{repo,remote,ref}`. | Unsupported test demand. I stopped implementation `20260910T013408Z-code-codex-1c093c`; its invalid result and partial source remain preserved. Independent correction `20260910T013916Z-tests-grok-76b0e1` removed the demand and added a healthy baseline control. |
| Enforcement tests contradicted each other | The valid-review case omitted its required review request; repeat-review cases omitted the mandatory work order; verification success and failure used the same undeclared plan setup. | Invalid acceptance batch, held before enforcement implementation. It cannot be made green by inventing defaults or bypassing the contract. |
| Some tests did not test enforcement | Followup cases constructed requests or asserted a literal refusal string without submitting them to the admission boundary. A terminal case allowed either success or refusal. | Test volume without evidence of the promised behavior. These need actual entrypoint assertions, not additional helper-only tests. |

The other agent owns the filename-dispatch defect and onboarding integration.
It is a separate reported failure; this debrief does not claim I repaired or
independently completed that work.

## 4. Measured test growth

These are **added lines in committed branch diffs**, not coverage percentages,
unique runtime scenarios, or a count of all tokens spent. Test-scope lines
include helpers, fixtures and existing test-infrastructure changes. Evidence
JSON and dispatch captures are separated from runtime source. Uncommitted work
in active worker snapshots is excluded.

| Branch / measured head | Test-scope files changed | Test-scope lines added / removed | Runtime-source lines added / removed | Documentation lines added / removed |
|---|---:|---:|---:|---:|
| Finding admission — `7a0dc24487802cdf89da8ab7b111d1f3c9296e4b` | 14 | 3,827 / 3 | 753 / 90 | 857 / 41 |
| Git-refs monitor — `61556038e3bec511bb17d53feb67d3a54699c0c0` | 2 | 1,708 / 0 | 149 / 5 | 93 / 0 |
| Process repairs — `b3f792d3149ebc678c90bc1a9a58e857fd53cb64` | 3 | 1,247 / 5 | 27 / 2 | 104 / 4 |
| **Total** | **19** | **6,782 / 8** | **929 / 97** | **1,054 / 45** |

The process branch's runtime-source column excludes its guard helper because
that helper lives inside an existing test file. A raw source/test ratio is
therefore not a quality metric. The scale still demands explanation: the
mandatory enforcement addition alone added **2,033 lines across nine test and
support files**, yet contained contradictory or non-exercising cases.

At these heads, the three diffs contain **37 added/changed retained dispatch
records** (15 admission, 18 monitor, 4 process). That is not a total bill or a
count of all model calls: active uncommitted records and individual attempts
are excluded. No monetary cost estimate has been measured here.

Reproduction and the per-file classification are in
[growth.json](handoff/evidence-2026-09-10-review-process/growth.json). For each
recorded head, run:

```sh
git diff --numstat 20f9bcaf2b3ae2152b9cab766637b5a89b71214b...HEAD -- ops ruff.toml
git diff --name-only 20f9bcaf2b3ae2152b9cab766637b5a89b71214b...HEAD -- .dev/records/dispatches
```

The source-control measurements do not prove that every added test is wasteful.
They do prove substantial growth; the incidents above prove that some of that
growth failed to provide the claimed protection.

## 5. Why the test count grew

- I requested broad acceptance matrices before settling a small, coherent
  execution boundary. Each matrix row encouraged another fixture or test class.
- New files repeated record construction, temporary-repository setup and
  schema assertions. Boilerplate accumulated faster than distinct behavior.
- Corrections tended to append new checks instead of first identifying which
  existing test should be corrected or shared.
- Missing-API RED concealed downstream problems. Discovering those later led
  to more fixtures, reviews and tests without curing the original setup.
- I reported aggregate pass counts too prominently. Counts were real command
  outputs, but they obscured whether the new acceptance path was exercised.
- The process did not impose a decision at test admission: what demonstrated
  failure does this test catch, and why can existing coverage not catch it?

Parametrizing 24 cases into one method would reduce the displayed count but
would not by itself reduce cost or improve evidence. The right target is
unnecessary setup and duplicate behavioral coverage, not a cosmetic number.

## 6. Control changes required by these incidents

### Preserve actual tests-first execution

For each corrected behavior, retain the independent test producer, exact test
bytes, fixture-precondition result, intended failing assertion and later GREEN.
If a fixture is invalid, stop implementation against that case. Correct it
through its independent author, rerun RED, and preserve the superseded evidence.
The implementation producer neither authors nor approves its own acceptance
tests. Taking direct control does not suspend this rule.

### Apply the same scope test to tests and reviews

A test expectation does not create a requirement. Before changing code or a
contract to satisfy it, identify the existing requirement, reachable trigger,
actual failure and reproduction or evidenced path. The malformed `.git` issue
earns action. Adding OIDs to freshness-event evidence does not.

A review finding without that link remains visible but does not become a
condition. A followup reviews the admitted correction and affected behavior;
it does not purchase another complete search or new completion criteria.

### Require real fixture controls

Check the actual plant and the actual existing consumer. A passing toy helper
or a successful `true` command is not proof that a paid review's real request,
producer records and retained inputs are valid. Success and failure cases must
have distinguishable setups, and each negative should violate the named
boundary rather than an earlier missing prerequisite.

### Control test growth by marginal value

Before adding a permanent case, identify its distinct reachable failure and
the gap in existing coverage. Prefer correcting or extending an existing test
and sharing a coherent fixture. Do not add tests merely for every command,
constant, helper constructor or prose rule. Do not grow a new test inventory
from review suggestions.

For the current additions, review what should be retained, consolidated or
removed by behavior. Preserve distinct success, refusal, no-side-effect and
provenance checks. Consolidate repeated setup and duplicate shape checks.
Replace helper-only assertions with actual boundary tests. Remove unsupported
expectations and cases that pass when the promised behavior is never exercised.
Do not delete valid tests simply to make counts smaller or the suite green.
This curation is not yet complete; no test-reduction claim is made here.

### Keep the finish line fixed and visible

The deliverables remain finding admission plus the explicitly required
prevention controls, the git-refs observer, and the two measured process
repairs. The terminal action is draft PRs into dev, not ready/merge/release.
No additional capability, review roster or generic policy framework is
justified by these incidents. The existing separate onboarding work remains
separately owned.

## 7. What is verified now, and what is not

| Deliverable | Verified evidence | Remaining work |
|---|---|---|
| Original finding admission | Final independent frozen set: 102 focused tests, 34 intended assertion RED failures and no errors; unchanged bytes later GREEN at `e81d369`. Earlier invalid fixtures remain in history. | Mandatory prevention extension is not implemented; the new test batch is being corrected. Full combined acceptance and draft PR remain. |
| Two process repairs | 48 independent tests: 14 assertion RED failures, no errors; unchanged bytes GREEN. Independent test review `20260910T013842Z-check-tests-claude-755cf8` approved. Full suite passed 2,262 tests, six skipped, at source `955e0a9`. Only a review-record commit moved HEAD during that run. | Final independent code/security reviews and draft publication status must be read from current records. |
| Monitor correction | Corrected file: four tests, five assertion RED failures, no errors, healthy baseline control GREEN; same bytes later GREEN. Original 19 tests remain unchanged and GREEN. Full suite passed 2,237 tests, six skipped, HEAD unchanged at `6155603`. | Final bounded followup acceptance, including the exact corrected test expectation, is running. |
| Git synchronization | New adapter's live reading at 2026-09-10T01:48:41Z: local dev equals GitHub `20f9bca`; local master equals GitHub `fc839a5`. | This is a point-in-time reading. Periodic activation belongs to the onboarding integration; no activation is claimed here. |

Machine enforcement cannot prove that every natural-language claim is true or
that every test is semantically complete. It can enforce recorded prerequisites,
exact bindings, actual command execution and authorized transitions. Those are
necessary controls; presenting them as a substitute for a valid test oracle
would repeat this incident.

## 8. Accountability and reporting standard

I should have said that the original feature was partly implemented while the
required enforcement remained substantial. Repeatedly implying the work was
near completion was inaccurate. Reports must separate implemented, tested,
independently accepted, published draft and merged; none implies the next.

The completion report must include draft URLs, the precise RED/GREEN evidence,
any remaining limitation, and the test-growth disposition. It must not claim
that a large passing suite validates an earlier broken TDD sequence, that a
document enforces a rule, or that a stopped worker's partial code was accepted.
