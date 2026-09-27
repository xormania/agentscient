# Agentscient CI Review — Reliability, Efficiency, and Flake Handoff

**Repository:** `uscient/agentscient`  
**Branch reviewed:** `dev`  
**Review date:** 2026-09-11  
**Reviewed state:** `dev` at merge of PR #138 (`032092c26521b674b626aa06aa0f3ea5585b6dec`)  
**Purpose:** handoff to local agents for follow-up measurement and targeted CI hardening.

## Executive summary

The current CI is **fast for the amount of work it performs** and its broad structure is sound. The latest observed PR run executed roughly **2,727 lane tests** plus the Symfony application checks in about **two minutes wall-clock**. The application job is effectively negligible at roughly **5 seconds**; the lane job is the critical path at roughly **117 seconds**. The lane's test launcher already runs its nine unittest groups concurrently, so there is no obvious large win from generic parallelization or caching. [E1][E2][E3]

The more important finding is **real but explainable flakiness**. Recent failures show several concrete nondeterminism/isolation defects rather than evidence that GitHub Actions itself is generally unreliable:

1. A telemetry assertion matched its planted number against a random temporary-directory name; PR #135 failed on attempt 1 and passed on attempt 2 on the same commit. PR #138 repairs that exact defect. [E4][E5]
2. A receipt test chose a result by digest-sorted filename and failed depending on ordering; the repair commit records a measured rate of 1 failure in 17 runs before the fix and 12 consecutive green runs afterward. [E6]
3. A conductor wrapper test read the live dispatch store while another job created a directory on the same host; PR #114 repaired that shared-state race. [E7]
4. Monitor test apparatus rewrote a shared argv log from concurrent shim processes; PR #103 records failures on three PRs, each passing on rerun, and a reproduction where 60 concurrent calls produced only 11 lines before the append fix and 60/60 after. [E8]
5. A hook test ran with the operator's real `HOME` and polluted the live skills registry; PR #136 moved it to a temporary HOME. [E9]

The common failure class is therefore **ambient host state leaking into tests**: random paths, shared HOME/state directories, filesystem ordering, or concurrent host activity. This matters because multiple self-hosted runner instances execute on the same machine (`ubuntu-dev`), so separate Actions runner workspaces do **not** imply separate host state. [E3][E4]

The latest green lane still emits `ResourceWarning`s for subprocesses left running and an unclosed file. Those warnings are not current failures, but they are credible precursors to timing-sensitive failures and should be treated as active reliability debt. [E3]

On workflow efficiency, the largest avoidable-looking cost is not inside a run but **run duplication**. PR #138 ran full PR CI, then its merged `dev` commit immediately ran another full push CI. PR #137 shows the same pattern. However, the current workflow explicitly states that the `push` run on `dev` exists to stamp the landed commit for the release PR to `master`, so local agents must not remove it without preserving that requirement. [E1][E10][E11]

## Current CI architecture

There is one current workflow under `.github/workflows`: `ci.yml`. [E1]

### Triggers

The current workflow runs on:

- `pull_request` into `dev`, limited to `opened`, `synchronize`, and `reopened`;
- `merge_group` into `dev`;
- `push` to `dev`. [E1]

The workflow comment states two important intent constraints:

- both `lane` and `app` are gates that a PR into `dev` must pass whole;
- the `push` run on `dev` is intentionally used to stamp the landed commit so the release PR from `dev` to `master` is covered. [E1]

At review time, the repository had **zero observed `merge_group` workflow runs**, so the practical recent pattern has been PR CI plus a post-merge `dev` push CI. [E12]

### Jobs

#### `lane`

Current steps:

- checkout with persisted credentials disabled;
- add host user toolchain path;
- term wall check;
- Ruff version + full repository lint;
- `ops/bin/suites.sh`;
- lane configuration closure check;
- lane configuration literal check. [E1]

#### `app`

Current steps:

- checkout with persisted credentials disabled;
- expose host user toolchain;
- print PHP, Composer, Python, CUE, jq, and Ruff versions;
- strict Composer validation;
- Composer install from lock;
- PHP lint over `src` and `packages`;
- Symfony kernel boot through `bin/console about`;
- PHPUnit;
- MATE query/list smoke checks against the compiled container. [E1]

### What the workflow does not currently declare

The current file has no workflow/job `concurrency` policy and no explicit job `timeout-minutes`. [E1]

That means:

- obsolete PR runs are not automatically cancelled when a newer synchronize event arrives;
- a genuinely wedged test or leaked subprocess can occupy a self-hosted runner until external intervention/GitHub's outer limit.

These are workflow-level hardening opportunities, not explanations for the recent known flakes.

## Performance observations

### Latest measured PR run: #138

PR #138 run `34647488620` is a useful clean baseline. [E3]

| Item | Observed duration |
|---|---:|
| `app` job | ~5 s |
| `lane` job | ~117 s |
| `lane suites` step | ~112 s |
| Composer install | ~3 s |

The app side is not a meaningful optimization target at present. [E3]

### Lane suite composition

`ops/bin/suites.sh` discovers these nine suites and runs them concurrently by default, buffering each suite's output separately and printing logs in a fixed order afterward. It exposes `SUITES_SERIAL=1` for serial execution. [E2]

Latest #138 observed suite timings: [E3]

| Suite | Tests | Duration |
|---|---:|---:|
| devlane/dispatch | 583 | ~70.6 s |
| devlane/harness | 155 | ~6.2 s |
| devlane/task | 312 | ~11.9 s |
| devlane/telemetry | 227 | ~44.6 s |
| devlane/hooks | 246 | ~54.3 s |
| devlane/fixtures | 221 | ~34.1 s |
| devlane/workflow | 48 | ~1.0 s |
| conductor | 927 | ~106.6 s |
| pr-overview | 8 | ~0.9 s |
| **Total** | **2,727** | concurrent; do not sum for wall time |

The conductor suite is currently the longest individual group and therefore the best place to investigate if runtime itself becomes a problem. Generic optimization elsewhere will have little effect on the two-minute critical path.

### Parallelism tradeoff

The suite runner's concurrency is a good efficiency choice, but the repository has repeatedly exposed tests that accidentally depend on host-global state. Running suites concurrently is therefore doing two useful things at once:

1. keeping wall time low;
2. surfacing hidden non-hermetic behavior that quiet serial/local execution may not reveal.

Do **not** respond to these flakes by serializing the whole suite unless measurement proves host resource contention rather than isolation defects. Serial execution would likely hide races while slowing feedback.

## Confirmed flake and isolation evidence

### F1 — random temporary path matched semantic assertion

PR #135's run `34644878635`, attempt 1, failed in `test_worth_claude_usage_currency.py`. The assertion searched for token `41` in the entire serialized waste report. The random temporary repository path happened to contain `worth-contract-m041w_6s`, so `41` appeared even though the measured usage field was correct. The same run/commit passed on attempt 2. [E4]

PR #138 changes the helper to inspect measured values rather than unrelated IDs, paths, windows, and stamps. Its PR run passed. [E5][E3]

**Classification:** genuine flake; random fixture/environment naming leaked into assertion semantics.

### F2 — result chosen by unstable digest ordering

The receipt branch recorded a failure where a test treated the last filename in digest-sorted order as the newest receipt. Which digest sorted last was data-dependent. The repair commit in the run history records **1 failure in 17 runs** before the change and **12 consecutive runs green** after selecting the file actually added by the iteration. [E6]

**Classification:** genuine nondeterministic test selection bug.

### F3 — test observed concurrent live dispatch state

PR #114 states that PR #113's lane check failed with three assertions naming a directory created by the slice-4 ladder while the suite ran. The self-hosted runner and live development machinery share the host dispatch store. Other conductor suites already used a `live_store_guard`; the wrapper suite did not until #114. [E7]

**Classification:** genuine host-state isolation race.

### F4 — concurrent test shim lost log writes

PR #103 documents three failing CI runs (PRs #89, #93, and #101) that passed on rerun and passed 8/8 quiet local runs. Its test `git` shim read and rewrote a shared log while the monitor observed sources through a thread pool. A direct stress reproduction logged **11 of 60** calls with the rewrite pattern and **60 of 60** with append. [E8]

**Classification:** genuine concurrency race in test apparatus.

### F5 — test mutated operator/live HOME state

PR #136 reports that `test_no_subagents.py` invoked the hook with the operator's HOME. Each run wrote fixture misses into the live skills registry. The repair uses a temporary HOME and asserts the live registry does not change. [E9]

**Classification:** hermeticity defect; not necessarily a random red every run, but the same root class as the other CI failures.

## Current warning signals even on green CI

The latest #138 green lane log contains:

- `ResourceWarning: subprocess ... is still running` during `devlane/dispatch`;
- `ResourceWarning: subprocess ... is still running` during `devlane/telemetry`;
- `ResourceWarning: unclosed file <_io.TextIOWrapper ...>` during `devlane/task`. [E3]

These should not be dismissed as cosmetic. With multiple suites running in parallel on a persistent self-hosted machine, leaked processes/descriptors can become timing, port, file-lock, or shared-state interference later.

The same log also warns that the pinned `actions/checkout` v4 commit targets Node 20 and is being forced to run under Node 24 by the runner. It is green now, but the pin should eventually move to a release/commit that natively targets the supported runtime. [E3]

## Self-hosted runner topology: key reliability fact

Recent logs show different runner instances such as `agentscient-wsl-10`, `agentscient-wsl-8`, `agentscient-wsl-5`, and `agentscient-wsl-2`, while reporting the same machine name: `ubuntu-dev`. [E3][E4]

That distinction matters:

- GitHub Actions gives each runner its own runner workspace and checkout cleanup;
- tests that reach into host-level HOME, shared stores, credentials, `/tmp`, process tables, or other host-global resources can still interfere across jobs/runners;
- the repository checkout itself is cleaned with `git clean -ffdx`, but that does not make host-global state hermetic. [E4]

For this repository, **host-state access should be treated as an explicit integration boundary**, not an incidental convenience inside unit tests.

## Efficiency issue: duplicate full validation

Recent merged PRs demonstrate this pattern:

1. full PR CI runs on the synthetic PR merge tree;
2. the PR is merged;
3. the resulting actual `dev` merge commit receives another full CI run via `push`. [E3][E10][E11]

For #138, the PR run completed around 21:06 UTC, the PR merged at 21:06:41, and the `dev` push run started at 21:06:43 and ran for roughly another two minutes. [E3][E10]

This is real duplicate compute, but it is **not automatically waste**: the workflow explicitly says the `dev` push run stamps the landed commit for the downstream release PR. [E1]

Any optimization must therefore preserve this invariant:

> the actual commit that will be proposed from `dev` to `master` has the required CI evidence attached to that SHA.

Do not simply remove the push trigger.

## Recommendations to local agents

### P0 — remove remaining hermeticity hazards

Audit tests for direct dependence on:

- the real `HOME`;
- `.dev` or other live host stores outside a per-test fixture;
- shared `/tmp` naming/content beyond a test-owned directory;
- wall-clock timestamps when the timestamp is not the behavior under test;
- unordered or filename-sorted directory traversal being used as creation order;
- process-table/global process assumptions;
- host credentials/auth files;
- shared append/rewrite files used by concurrent subprocesses.

The goal is not to forbid integration tests. The goal is to make the boundary explicit: a test either owns a temporary isolated state tree, or it is intentionally an integration test against controlled shared state.

### P0 — eliminate the current ResourceWarnings

Trace every still-running subprocess and unclosed file in the latest green lane run. Each fix should include a regression assertion that proves the resource is closed/reaped, not merely suppression of the warning. [E3]

After the suite is clean, consider making relevant resource warnings fatal in CI so new leaks cannot silently accumulate.

### P0 — add a focused flake stress check for repaired classes

Do not blindly rerun the entire CI until green. Instead, create/retain targeted deterministic stress cases for each known class:

- randomized/hostile TMPDIR and HOME names;
- concurrent writers/readers where concurrency exists in production/test harnesses;
- directory contents in deliberately non-semantic order;
- concurrent live-store creation while guarded tests inspect state;
- repeated subprocess creation with explicit reap/close assertions.

A failed run should identify a reproducible invariant violation, not be papered over with retry logic.

### P1 — add stale PR-run cancellation

Add a concurrency policy that cancels obsolete **pull-request** runs when a newer commit is synchronized to the same PR. Preserve `push` and `merge_group` semantics unless separately proven safe to cancel.

Reason: with a ~2-minute lane and a self-hosted runner pool, outdated PR commits otherwise consume runner capacity and increase concurrent pressure on the shared host.

### P1 — add explicit job timeouts

Add explicit timeouts based on measured normal behavior and a generous failure margin. The current baseline is approximately 2 minutes for lane and seconds for app; choose the actual timeout from recent distribution rather than an arbitrary minimal value. [E3]

The purpose is containment of hangs/leaks, not performance tuning.

### P1 — measure whether PR + push duplication can be reduced without breaking release evidence

Before changing triggers, answer:

1. Which check contexts must exist on the actual `dev` merge SHA for the `dev -> master` release PR?
2. Must both the entire lane and app rerun to provide those contexts, or can a cheaper landed-tree verification safely stamp the required evidence?
3. If merge queue becomes active, which SHA/check context is authoritative for `dev` landing and which is required for the release PR?

Do not optimize this by assumption. The current duplication has an explicit release-gating rationale. [E1]

### P1 — update the checkout action pin

Move the pinned checkout action to a commit/release that natively targets the runner's supported Node runtime after verifying behavior. Do not unpin to a floating tag if repository policy requires immutable action SHAs. [E1][E3]

### P2 — benchmark parallel vs serial only as a diagnostic

The existing suite runner already supports `SUITES_SERIAL=1`. [E2]

Measure several clean runs of:

- default parallel mode;
- serial mode;
- parallel mode while normal local dispatch activity is present.

Record wall time and variance. This can distinguish CPU/resource contention from state-isolation races. Do not make serial execution the default merely because it appears quieter.

### P2 — record CI reliability metrics as first-class data

Given Agentscient's existing telemetry emphasis, capture at least:

- workflow run ID and attempt;
- event (`pull_request`, `push`, `merge_group`);
- head SHA/tree SHA if available;
- runner name;
- job start/end/duration;
- failed step/test name;
- whether the same SHA passed on rerun without code change;
- repair PR/LD identifier when a flake is classified.

The useful metric is not raw red percentage. Recent intentional TDD/red-stage commits mean a red run can be correct behavior. The stronger signal is **same code + materially equivalent inputs + different result**, or a proven dependency on ambient state.

## Things not recommended now

### Do not add broad path-based CI skipping

Two minutes for the current coverage is cheap relative to the coupling in hooks, workflow configuration, conductor behavior, and shared contracts. Selective skipping would introduce a new correctness model for relatively little wall-time gain.

### Do not add automatic rerun-until-green behavior

That would convert useful failure evidence into noise and make the system look healthier than it is. Reruns are useful diagnostically when explicitly tracked as evidence of nondeterminism.

### Do not serialize the whole lane as a flake fix

The recent defects are primarily isolation bugs. Serializing tests would hide some of them while increasing feedback time.

### Do not remove `push: dev` without preserving the release gate

The current workflow explicitly documents why it exists. [E1]

## Suggested investigation sequence

1. **Reproduce and remove the three current ResourceWarnings.**
2. **Search the test tree for real HOME/live-store/global-temp access** and classify each occurrence as isolated, guarded integration, or unsafe.
3. **Run targeted hostile-environment/stress tests** for the five confirmed flake classes.
4. **Add PR stale-run cancellation and measured timeouts.**
5. **Collect a small run-history dataset** and separate intentional red runs from nondeterministic rerun-pass cases.
6. **Only then evaluate duplicate PR/push cost**, preserving the downstream release-SHA evidence requirement.
7. **Benchmark parallel vs serial as evidence**, not as an intended architecture change.

## Useful verification commands for local agents

```bash
# Current CI definition
git show origin/dev:.github/workflows/ci.yml

# Current suite launcher
git show origin/dev:ops/bin/suites.sh

# Recent CI history
gh run list --repo uscient/agentscient --workflow ci --limit 50

# Known same-run flake: PR #135, first attempt
gh run view 34644878635 --repo uscient/agentscient --attempt 1 --log

# Latest clean PR baseline: PR #138
gh run view 34647488620 --repo uscient/agentscient --log

# Post-merge dev run for #138
gh run view 34647720027 --repo uscient/agentscient --log

# Merge queue usage at review time
gh api 'repos/uscient/agentscient/actions/runs?event=merge_group&per_page=10'

# Local parallel lane baseline
bash ops/bin/suites.sh

# Local serial diagnostic baseline
SUITES_SERIAL=1 bash ops/bin/suites.sh
```

## Evidence index

**[E1] Current CI workflow on `dev`**  
https://github.com/uscient/agentscient/blob/dev/.github/workflows/ci.yml

**[E2] Current lane suite launcher on `dev`**  
https://github.com/uscient/agentscient/blob/dev/ops/bin/suites.sh

**[E3] PR #138 clean CI run — run `34647488620`**  
https://github.com/uscient/agentscient/actions/runs/34647488620  
PR: https://github.com/uscient/agentscient/pull/138

**[E4] PR #135 flaky run — run `34644878635`, attempt 1 lane job `103413138355`**  
https://github.com/uscient/agentscient/actions/runs/34644878635  
https://github.com/uscient/agentscient/actions/runs/34644878635/job/103413138355  
PR: https://github.com/uscient/agentscient/pull/135

**[E5] PR #138 — repair of LD-21 temporary-path/serialized-whole assertion**  
https://github.com/uscient/agentscient/pull/138

**[E6] Receipt branch failure then repair — runs `34556886776` and `34556972921`**  
https://github.com/uscient/agentscient/actions/runs/34556886776  
https://github.com/uscient/agentscient/actions/runs/34556972921  
Related PR #101: https://github.com/uscient/agentscient/pull/101

**[E7] PR #114 — shared live-store guard repair (LD-16)**  
https://github.com/uscient/agentscient/pull/114

**[E8] PR #103 — concurrent monitor shim logging race (LD-8)**  
https://github.com/uscient/agentscient/pull/103

**[E9] PR #136 — hook test isolation under temporary HOME (LD-22)**  
https://github.com/uscient/agentscient/pull/136

**[E10] Post-merge `dev` push CI after #138 — run `34647720027`**  
https://github.com/uscient/agentscient/actions/runs/34647720027

**[E11] Post-merge `dev` push CI after #137 — run `34646426740`**  
https://github.com/uscient/agentscient/actions/runs/34646426740  
PR: https://github.com/uscient/agentscient/pull/137

**[E12] Merge-group run query observed `total_count: 0` at review time**  
Authenticated API query: `GET /repos/uscient/agentscient/actions/runs?event=merge_group&per_page=10`

## Bottom line for the next agent

Treat the CI as **fast but not yet fully hermetic**. Do not redesign it wholesale. The most valuable work is to eliminate the remaining host-state/resource leaks and make flake evidence measurable. The current parallel architecture is delivering strong coverage in roughly two minutes; preserve that advantage unless measurements show a better tradeoff.
