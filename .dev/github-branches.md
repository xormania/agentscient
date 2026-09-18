# GitHub branches — where this stands, and what a new session picks up

**Read this section first. The report below it was written before the cleanup and
describes the population as it was; the numbers in it are still true of that
moment, not of now.**

## State, measured 2026-09-18T02:39:31Z on this host (128 heads on origin at that moment)

| reading | value |
|---|---:|
| branches on `origin` | **128** (was 394) |
| retired in the cleanup | **266** |
| open pull requests | 7 |
| `refs/dispatch/*` on origin | 443 |
| `refs/backup/*` on origin | 2 |
| commits existing only on this disk | **0** |

Every retired branch is in one verified bundle, and nothing was deleted before that
bundle was cloned and every tip looked up inside the clone.

| what | where |
|---|---|
| the bundle | `/home/scientdb/wt-archive/agentscient-refs-20260918T015216Z.bundle` — 12,243,117 bytes, 1,339 refs, sha256 `9bdcd036ab7c6d5ebe651facc55dba1cf02550b66deceec9ce8fa34cc58407cf` |
| the index, one row per retired branch | `ops/conductor/handoff/branch-archive-20260918T015216Z.tsv` (committed at `6c93578c`, pushed) |
| the lever | `ops/bin/branch-retire.sh` — `--plan`, `--archive`, `--retire` |
| the run log | `/home/scientdb/wt-archive/branch-retire-20260918T015528Z.log` |

Restore everything: `git clone <bundle> <dir>`. Restore one branch:
`git fetch <bundle> <sha>:refs/heads/<name>`, the sha from the index. Proven on
2026-09-18: `lane/agy-accounting-acceptance-20260908` fetched out of the bundle and
came back at `6292122fa07e`, the sha the index records.

## What was kept, and why

| class | branches | meaning |
|---|---:|---|
| `holds-changed-code` | 50 | differs from the trunk on tracked files, adds none the trunk lacks |
| `holds-new-code` | 34 | adds files outside `.dev/` the trunk does not have |
| `checked-out` | 31 | a local worktree has it checked out |
| `open-pr` | 6 | an open pull request heads here |
| `live-session` | 3 | the deliverable lock names it |
| `unrelated-history` | 2 | no merge base with the trunk; no diff means anything |
| `permanent` | 2 | `dev` and `master` |

## What a new session picks up, in order

1. **Read the 34 `holds-new-code` branches** and answer one question each: does the
   trunk want the file, yes or no. Not long-term value — only that. Then retire them
   the same way, `--plan` and `--archive` first. The list is below.
2. **Stop the growth at its three sources**, largest first: the dispatcher mints a
   branch per job record when `refs/dispatch/*` already carries the commits (80 of
   the 266 retired existed for that reason alone); rescue sweeps push local tips into
   `refs/heads/` instead of an archive namespace (the 2026-09-16 sweep minted about
   149 names that way); and nothing retires a branch at session close, so one branch
   per session accumulates for ever.
3. **The law lines, the owner's call, deferred by them on 2026-09-17** ("get it
   cleaned first - then we'll look at law lines"): `AGENTS.md` says "never a deleted
   branch", which the cleanup of 2026-09-18 no longer matches. The replacement to put
   to the owner is "never an unarchived deletion". The matching hook row lives in
   `ops/devlane/hooks/boundaries.json`, which is wall and needs its own isolated
   session under a `wall` grant.
4. **`branches.py` still assumes `main`.** Its census and allowed PR bases name a
   branch this repository does not have; the trunk is `dev` and the release is
   `master`. Named by the Astra Max report of 2026-09-16, not yet fixed.
5. **`ops/bin/branch-retire.sh` has no tests.** Its readings come from the live
   remote. A second producer owes it a table: a planted branch whose tip moved
   between plan and retire, a bundle whose sha256 does not match its index, a branch
   with an open PR, a branch with no merge base.

### The 34 branches still holding files the trunk does not have

| branch | files the trunk lacks |
|---|---|
| `lane/check-tests-json` | 2 files outside .dev/ |
| `lane/conduct-adapter-tests-20260906` | 3 files outside .dev/ |
| `lane/conduct-canonical-tests-20260906` | 2 files outside .dev/ |
| `lane/conduct-discovery-20260906` | 7 files outside .dev/ |
| `lane/conduct-discovery-final-tests-20260906` | 7 files outside .dev/ |
| `lane/conduct-discovery-runtime-fix-20260906` | 7 files outside .dev/ |
| `lane/conduct-policy-code-20260906` | 1 files outside .dev/ |
| `lane/conduct-policy-code-adjudication-20260906` | 2 files outside .dev/ |
| `lane/conduct-policy-source-ruling-20260906` | 2 files outside .dev/ |
| `lane/conduct-policy-tests-20260906` | 1 files outside .dev/ |
| `lane/conduct-start-tests-20260906` | 3 files outside .dev/ |
| `lane/conduct-start-tests-adjudication-20260906` | 3 files outside .dev/ |
| `lane/context-contracts` | 1 files outside .dev/ |
| `lane/effort-per-role` | 1 files outside .dev/ |
| `lane/finding-admission-20260909` | 15 files outside .dev/ |
| `lane/fixture-fix` | 1 files outside .dev/ |
| `lane/fixture-fix-2` | 1 files outside .dev/ |
| `lane/noguess` | 1 files outside .dev/ |
| `lane/onboarding-completion-20260909` | 8 files outside .dev/ |
| `lane/onboarding-contract-20260910` | 1 files outside .dev/ |
| `lane/onboarding-discovery-20260910` | 7 files outside .dev/ |
| `lane/onboarding-discovery-tests-20260910` | 7 files outside .dev/ |
| `lane/onboarding-policy-20260910` | 1 files outside .dev/ |
| `lane/onboarding-policy-tests-20260910` | 1 files outside .dev/ |
| `lane/record-wall` | 1 files outside .dev/ |
| `lane/security-resume-binding-20260904` | 1 files outside .dev/ |
| `lane/workflow` | 630 files outside .dev/ |
| `records/agy-closeout-20260909` | 5 files outside .dev/ |
| `records/codex-closeout-20260905` | 3 files outside .dev/ |
| `records/codex-machinery-20260904` | 1 files outside .dev/ |
| `records/codex-mcp-closeout-20260905` | 5 files outside .dev/ |
| `review/mcp-cap-quality-20260905` | 2 files outside .dev/ |
| `review/mcp-quality-20260905` | 1 files outside .dev/ |
| `review/mcp-security-20260905` | 1 files outside .dev/ |

## Related records

- `ops/conductor/handoff/worktree-archive-2026-09-17.md` and its manifest — the local
  worktree fleet, archived the same way the day before: 670,299 inodes under a shared
  `wt/` down to 58,384 under this lane's own `ag-wt/`.
- `ops/conductor/handoff/lane-defects/LD-106.md` — the `lane.conf` parity row that is
  red on this host alone.
- The owner's supplied branch-growth recommendation by Astra Max, 2026-09-16, read at
  `/mnt/c/Users/xorma/Downloads/CurrentDownloads/grok/agentscient-branch-growth-and-retirement-recommendation-2026-09-16 (2).md`.

---

# The branches on GitHub with unique commits and no pull request

Measured 2026-09-18T01:34:51Z against `origin/dev` at `ee62c3d183e4`, on the host, with the
remote refs freshly fetched. Every number below is a reading from a command named
in [How this was measured](#how-this-was-measured); nothing is inferred from a name.

## What is on GitHub

| reading | count |
|---|---:|
| branches on origin | 393 |
| contained in `origin/dev` — landed, dead names | 195 |
| carrying commits `dev` does not have | 198 |
| of those, with any pull request (open, merged or closed) | 15 |
| **of those, with no pull request ever — this report** | **183** |

## The 183, by what they actually hold

| kind | branches | what it means |
|---|---:|---|
| `unlanded` | 91 | holds files dev does not have, or differs from dev on files it touched |
| `dispatch-record` | 76 | every commit is a `dispatch: record` commit — job bookkeeping |
| `patch-equivalent` | 11 | every commit has an equivalent patch already in dev (`git cherry`) |
| `content-in-dev` | 2 | dev's current content matches the branch on every file it touched |
| `no-file-change` | 3 | the commits change no file relative to dev's merge base |

Read that table as a disposition: **92 of the 183 need no reading at all** — 76 are
dispatch-record bookkeeping whose content the dispatch store already holds, 11 are
patch-equivalent to dev, 2 match dev's content exactly, 3 change no file. The other
91 hold something.

### What the 91 hold

| files present on the branch and absent from dev | count |
|---|---:|
| `.dev/` session records | 287 |
| `ops/**/*.py` | 83 |
| `ops/**` other (contracts, notes) | 50 |

Most of it is records. Code is concentrated: **21 of the 91 branches** hold any
`ops/*.py` file dev lacks, and those come to **34 distinct paths**, not 83 —
the same files ride several branches of one family.

The 34 paths, and how many branches carry each:

| branches | path |
|---:|---|
| 6 | `ops/conductor/tests/test_lane_policy.py` |
| 5 | `ops/conductor/tests/discovery_v3_support.py` |
| 5 | `ops/conductor/tests/test_discovery_v3_adapter.py` |
| 5 | `ops/conductor/tests/test_discovery_v3_catalogues.py` |
| 5 | `ops/conductor/tests/test_discovery_v3_config.py` |
| 5 | `ops/conductor/tests/test_discovery_v3_handoffs.py` |
| 5 | `ops/conductor/tests/test_discovery_v3_snapshots.py` |
| 5 | `ops/conductor/tests/test_discovery_v3_startup.py` |
| 2 | `ops/conductor/tools/lane_policy.py` |
| 2 | `ops/conductor/tests/conduct_test_support.py` |
| 2 | `ops/conductor/tests/test_conduct_enforcement.py` |
| 2 | `ops/conductor/tests/test_conduct_start.py` |
| 2 | `ops/conductor/tests/test_admission_enforcement_custody.py` |
| 2 | `ops/conductor/tests/test_admission_enforcement_followup.py` |
| 2 | `ops/conductor/tests/test_admission_enforcement_terminal.py` |
| 2 | `ops/conductor/tests/test_finding_admission_ledger.py` |
| 2 | `ops/conductor/tests/test_finding_admission_routing.py` |
| 2 | `ops/devlane/dispatch/tests/admission_enforcement_support.py` |
| 2 | `ops/devlane/dispatch/tests/test_admission_enforcement_declaration.py` |
| 2 | `ops/devlane/dispatch/tests/test_admission_enforcement_fixtures.py` |
| 2 | `ops/devlane/dispatch/tests/test_admission_enforcement_review_slots.py` |
| 2 | `ops/devlane/dispatch/tests/test_admission_enforcement_verify.py` |
| 2 | `ops/devlane/task/tests/test_admission_enforcement_validate.py` |
| 2 | `ops/devlane/task/tests/test_finding_admission_envelope.py` |
| 1 | `ops/conductor/tests/test_ladder_audit_fix.py` |
| 1 | `ops/devlane/task/tests/test_check_tests_json.py` |
| 1 | `ops/devlane/harness/tests/test_closure_gate.py` |
| 1 | `ops/conductor/tests/test_laneconf_defaults.py` |
| 1 | `ops/devlane/dispatch/tests/test_launch_record_wall_at_mint.py` |
| 1 | `ops/devlane/harness/tests/adapter_test_support.py` |
| 1 | `ops/devlane/harness/tests/test_adapter_argv.py` |
| 1 | `ops/devlane/harness/tests/test_output_capability.py` |
| 1 | `ops/devlane/dispatch/tests/test_execution_adoption.py` |
| 1 | `ops/devlane/task/tests/test_execution_frontend.py` |

## The families, and why each is not on dev

Grouped mechanically by namespace and name stem; the *why* column states only what a
reading supports. A branch with no pull request never entered the gate, so in every
case the literal answer to "why is it not on dev" is the same: **nobody proposed it**.
What differs is whether anything would be lost by leaving it there.

### `lane/conduct-*` — 18 branches, 2026-09-06

38 `ops/*.py` files dev lacks, 75 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/conduct-discovery-20260906` | 2026-09-06 | 11 | 7 | 0 | 4 | — | 0 |
| `lane/conduct-discovery-final-tests-20260906` | 2026-09-06 | 26 | 7 | 0 | 4 | — | 3 |
| `lane/conduct-discovery-runtime-fix-20260906` | 2026-09-06 | 28 | 7 | 0 | 5 | — | 0 |
| `lane/conduct-adapter-tests-20260906` | 2026-09-06 | 18 | 3 | 0 | 7 | — | 0 |
| `lane/conduct-start-tests-20260906` | 2026-09-06 | 16 | 3 | 0 | 5 | — | 0 |
| `lane/conduct-start-tests-adjudication-20260906` | 2026-09-06 | 16 | 3 | 0 | 5 | — | 0 |
| `lane/conduct-canonical-tests-20260906` | 2026-09-06 | 11 | 2 | 0 | 3 | — | 0 |
| `lane/conduct-policy-code-adjudication-20260906` | 2026-09-06 | 8 | 2 | 0 | 4 | 20260906T132741Z-code-codex-b5b12f | 0 |
| `lane/conduct-policy-source-ruling-20260906` | 2026-09-06 | 8 | 2 | 0 | 4 | 20260906T132741Z-code-codex-b5b12f | 0 |
| `lane/conduct-policy-code-20260906` | 2026-09-06 | 7 | 1 | 0 | 5 | — | 0 |
| `lane/conduct-policy-tests-20260906` | 2026-09-06 | 6 | 1 | 0 | 4 | — | 5 |
| `lane/conduct-adapter-adjudication-20260906` | 2026-09-06 | 5 | 0 | 0 | 3 | — | 0 |
| `lane/conduct-coupling-reconciliation-20260906` | 2026-09-06 | 14 | 0 | 0 | 5 | — | 0 |
| `lane/conduct-first-start-adjudication-20260906` | 2026-09-06 | 10 | 0 | 0 | 4 | — | 0 |
| `lane/conduct-message-tests-20260906` | 2026-09-06 | 4 | 0 | 0 | 2 | — | 0 |
| `lane/conduct-relay-contract-20260906` | 2026-09-06 | 5 | 0 | 0 | 3 | — | 0 |
| `lane/conduct-start-adjudication-20260906` | 2026-09-06 | 9 | 0 | 0 | 4 | — | 0 |
| `lane/conduct-start-coupling-20260906` | 2026-09-06 | 10 | 0 | 0 | 4 | — | 1 |

Files dev lacks, most shared first: `ops/conductor/tests/test_lane_policy.py`, `ops/conductor/tests/discovery_v3_support.py`, `ops/conductor/tests/test_discovery_v3_adapter.py`, `ops/conductor/tests/test_discovery_v3_catalogues.py`, `ops/conductor/tests/test_discovery_v3_config.py`, `ops/conductor/tests/test_discovery_v3_handoffs.py`.

### `lane/onboarding-*` — 6 branches, 2026-09-09

16 `ops/*.py` files dev lacks, 25 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/onboarding-discovery-20260910` | 2026-09-09 | 29 | 7 | 0 | 5 | 20260910T001358Z-code-codex-6d01cf | 0 |
| `lane/onboarding-discovery-tests-20260910` | 2026-09-09 | 27 | 7 | 0 | 4 | 20260910T001358Z-code-codex-6d01cf | 1 |
| `lane/onboarding-policy-20260910` | 2026-09-09 | 9 | 1 | 0 | 5 | 20260910T001531Z-code-codex-b9d9bc | 0 |
| `lane/onboarding-policy-tests-20260910` | 2026-09-09 | 7 | 1 | 0 | 4 | 20260910T001531Z-code-codex-b9d9bc | 1 |
| `lane/onboarding-completion-20260909` | 2026-09-09 | 7 | 0 | 8 | 4 | 20260910T015009Z-tests-grok-9f80d3 | 0 |
| `lane/onboarding-contract-20260910` | 2026-09-09 | 5 | 0 | 1 | 3 | 20260910T001134Z-code-codex-712230, 20260910T010615Z-code-codex-9e6040… | 0 |

Files dev lacks, most shared first: `ops/conductor/tests/discovery_v3_support.py`, `ops/conductor/tests/test_discovery_v3_adapter.py`, `ops/conductor/tests/test_discovery_v3_catalogues.py`, `ops/conductor/tests/test_discovery_v3_config.py`, `ops/conductor/tests/test_discovery_v3_handoffs.py`, `ops/conductor/tests/test_discovery_v3_snapshots.py`.

### `lane/agy-*` — 36 branches, 2026-09-08

0 `ops/*.py` files dev lacks, 43 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/agy-config-final-correction-20260908` | 2026-09-08 | 3 | 0 | 0 | 1 | — | 0 |
| `lane/agy-config-test-adjudication-20260908` | 2026-09-08 | 3 | 0 | 0 | 1 | — | 0 |
| `lane/agy-config-test-correction-20260908` | 2026-09-08 | 5 | 0 | 0 | 1 | — | 0 |
| `lane/agy-config-test-review-20260908` | 2026-09-08 | 3 | 0 | 0 | 1 | — | 0 |
| `lane/agy-configuration-tests-20260908` | 2026-09-08 | 4 | 0 | 0 | 1 | 20260908T061804Z-code-codex-cc64ee | 0 |
| `lane/agy-contract-adjudication-20260908` | 2026-09-08 | 2 | 0 | 0 | 0 | 20260908T061804Z-code-codex-cc64ee | 0 |
| `lane/agy-contract-review-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | 20260908T061804Z-code-codex-cc64ee | 0 |
| `lane/agy-dispatch-test-review-20260908` | 2026-09-08 | 7 | 0 | 0 | 1 | — | 0 |
| `lane/agy-dispatch-tests-20260908` | 2026-09-08 | 3 | 0 | 0 | 1 | — | 0 |
| `lane/agy-envelope-final-correction-20260908` | 2026-09-08 | 3 | 0 | 0 | 1 | — | 0 |
| `lane/agy-envelope-test-adjudication-20260908` | 2026-09-08 | 4 | 0 | 0 | 2 | 20260908T061804Z-code-codex-cc64ee | 0 |
| `lane/agy-envelope-test-correction-20260908` | 2026-09-08 | 6 | 0 | 0 | 2 | 20260908T061804Z-code-codex-cc64ee | 0 |
| `lane/agy-envelope-test-review-20260908` | 2026-09-08 | 4 | 0 | 0 | 2 | 20260908T061804Z-code-codex-cc64ee | 0 |
| `lane/agy-envelope-tests-20260908` | 2026-09-08 | 3 | 0 | 0 | 1 | 20260908T061804Z-code-codex-cc64ee | 3 |
| `lane/agy-isolation-last-fix-20260908` | 2026-09-08 | 4 | 0 | 0 | 2 | — | 0 |
| `lane/agy-isolation-legacy-flags-20260908` | 2026-09-08 | 5 | 0 | 0 | 2 | — | 0 |
| `lane/agy-isolation-legacy-tests-20260908` | 2026-09-08 | 3 | 0 | 0 | 1 | — | 1 |
| `lane/agy-isolation-test-adjudication-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | — | 0 |
| `lane/agy-isolation-test-correction-20260908` | 2026-09-08 | 3 | 0 | 0 | 1 | — | 0 |
| `lane/agy-isolation-test-review-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | — | 0 |
| `lane/agy-isolation-tests-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | — | 0 |
| `lane/agy-lifecycle-cwd-ruling-20260908` | 2026-09-08 | 3 | 0 | 0 | 1 | 20260908T083444Z-tests-grok-0fd56a | 0 |
| `lane/agy-lifecycle-fix-20260908` | 2026-09-08 | 5 | 0 | 0 | 2 | — | 0 |
| `lane/agy-lifecycle-fix-review-20260908` | 2026-09-08 | 3 | 0 | 0 | 1 | 20260908T083444Z-tests-grok-0fd56a | 0 |
| `lane/agy-lifecycle-ruling-20260908` | 2026-09-08 | 7 | 0 | 0 | 1 | — | 0 |
| `lane/agy-live-accounting-final-fix-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | — | 0 |
| `lane/agy-live-accounting-regression-20260908` | 2026-09-08 | 3 | 0 | 0 | 1 | — | 0 |
| `lane/agy-live-usage-fix-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | — | 0 |
| `lane/agy-live-usage-tests-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | — | 0 |
| `lane/agy-native-reader-fix-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | — | 0 |
| `lane/agy-native-regression-tests-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | — | 0 |
| `lane/agy-portable-fixture-fix-20260908` | 2026-09-08 | 6 | 0 | 0 | 2 | — | 0 |
| `lane/agy-probe-selection-fix-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | — | 0 |
| `lane/agy-regression-final-fix-20260908` | 2026-09-08 | 4 | 0 | 0 | 2 | — | 0 |
| `lane/agy-runtime-ruling-fix-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | — | 0 |
| `lane/agy-terminal-test-fix-20260908` | 2026-09-08 | 2 | 0 | 0 | 1 | — | 0 |

### `lane/check-*` — 1 branches, 2026-09-04

2 `ops/*.py` files dev lacks, 38 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/check-tests-json` | 2026-09-04 | 92 | 2 | 0 | 38 | — | 0 |

Files dev lacks, most shared first: `ops/conductor/tests/test_ladder_audit_fix.py`, `ops/devlane/task/tests/test_check_tests_json.py`.

### `lane/audit-*` — 1 branches, 2026-09-10

12 `ops/*.py` files dev lacks, 20 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/audit-enforcement-20260910` | 2026-09-10 | 49 | 12 | 3 | 20 | 20260909T232304Z-code-codex-eae1ea | 0 |

Files dev lacks, most shared first: `ops/conductor/AAR-2026-09-09-review-churn.md`, `ops/conductor/tests/fixtures/finding_admission/agy-sample-classifications.json`, `ops/conductor/tests/test_admission_enforcement_custody.py`, `ops/conductor/tests/test_admission_enforcement_followup.py`, `ops/conductor/tests/test_admission_enforcement_terminal.py`, `ops/conductor/tests/test_finding_admission_ledger.py`.

### `lane/finding-*` — 1 branches, 2026-09-09

12 `ops/*.py` files dev lacks, 16 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/finding-admission-20260909` | 2026-09-09 | 39 | 12 | 3 | 16 | 20260909T232304Z-code-codex-eae1ea | 1 |

Files dev lacks, most shared first: `ops/conductor/AAR-2026-09-09-review-churn.md`, `ops/conductor/tests/fixtures/finding_admission/agy-sample-classifications.json`, `ops/conductor/tests/test_admission_enforcement_custody.py`, `ops/conductor/tests/test_admission_enforcement_followup.py`, `ops/conductor/tests/test_admission_enforcement_terminal.py`, `ops/conductor/tests/test_finding_admission_ledger.py`.

### `lane/session-*` — 6 branches, 2026-09-04 → 2026-09-16

0 `ops/*.py` files dev lacks, 14 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/session-20260916-a` | 2026-09-16 | 1 | 0 | 3 | 1 | — | 0 |
| `lane/session-20260916-i` | 2026-09-16 | 4 | 0 | 0 | 2 | — | 0 |
| `lane/session-20260916-s2` | 2026-09-16 | 2 | 0 | 1 | 0 | — | 0 |
| `lane/session-20260916-s3` | 2026-09-16 | 2 | 0 | 1 | 0 | — | 0 |
| `lane/session-20260916-sweep` | 2026-09-16 | 8 | 0 | 3 | 2 | — | 0 |
| `lane/session-budget` | 2026-09-04 | 22 | 0 | 0 | 9 | — | 0 |

Files dev lacks, most shared first: `ops/conductor/handoff/lane-defects/LD-71.md`, `ops/conductor/handoff/lane-defects/LD-72.md`, `ops/conductor/handoff/lane-defects/LD-73.md`, `ops/conductor/handoff/scopes/scope-s2.txt`, `ops/conductor/handoff/scopes/scope-s3.txt`, `ops/conductor/handoff/lane-defects/LD-82.md`.

### `lane/fixture-*` — 3 branches, 2026-09-04

0 `ops/*.py` files dev lacks, 16 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/fixture-audit` | 2026-09-04 | 3 | 0 | 0 | 2 | — | 0 |
| `lane/fixture-fix` | 2026-09-04 | 15 | 0 | 1 | 4 | — | 1 |
| `lane/fixture-fix-2` | 2026-09-04 | 34 | 0 | 1 | 10 | — | 0 |

Files dev lacks, most shared first: `ops/devlane/fixtures/copy-list`.

### `lane/context-*` — 1 branches, 2026-09-04

1 `ops/*.py` files dev lacks, 9 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/context-contracts` | 2026-09-04 | 19 | 1 | 0 | 9 | — | 0 |

Files dev lacks, most shared first: `ops/devlane/harness/tests/test_closure_gate.py`.

### `records/codex-*` — 3 branches, 2026-09-04 → 2026-09-05

0 `ops/*.py` files dev lacks, 0 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `records/codex-closeout-20260905` | 2026-09-05 | 1 | 0 | 3 | 0 | — | 0 |
| `records/codex-machinery-20260904` | 2026-09-04 | 5 | 0 | 1 | 0 | — | 0 |
| `records/codex-mcp-closeout-20260905` | 2026-09-05 | 1 | 0 | 5 | 0 | — | 0 |

Files dev lacks, most shared first: `ops/conductor/handoff/HANDOFF-2026-09-04-codex-machinery.md`, `ops/conductor/AAR-2026-09-05-codex-closeout.md`, `ops/conductor/handoff/HANDOFF-2026-09-05-codex-closeout.md`, `ops/conductor/handoff/evidence-2026-09-05-codex-closeout.json`, `ops/conductor/AAR-2026-09-05T22-codex-mcp-closeout.md`, `ops/conductor/handoff/HANDOFF-2026-09-05-codex-mcp-closeout.md`.

### `records/agy-*` — 1 branches, 2026-09-09

0 `ops/*.py` files dev lacks, 2 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `records/agy-closeout-20260909` | 2026-09-09 | 4 | 0 | 5 | 2 | — | 0 |

Files dev lacks, most shared first: `ops/conductor/AAR-2026-09-09-agy.md`, `ops/conductor/handoff/HANDOFF-2026-09-09-agy.md`, `ops/conductor/handoff/evidence-2026-09-09-agy/measurements.json`, `ops/conductor/handoff/evidence-2026-09-09-agy/publication.json`, `ops/conductor/handoff/probes/probes-2026-09-09-agy.jsonl`.

### `repair/audit-*` — 1 branches, 2026-09-10

0 `ops/*.py` files dev lacks, 0 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `repair/audit-enforcement-manual-20260910` | 2026-09-10 | 3 | 0 | 7 | 0 | — | 0 |

Files dev lacks, most shared first: `ops/conductor/handoff/evidence-2026-09-10-manual-enforcement/README.md`, `ops/conductor/handoff/evidence-2026-09-10-manual-enforcement/SHA256SUMS`, `ops/conductor/handoff/evidence-2026-09-10-manual-enforcement/native-probe.py.txt`, `ops/conductor/handoff/evidence-2026-09-10-manual-enforcement/native-roles.json`, `ops/conductor/handoff/evidence-2026-09-10-manual-enforcement/producer-correction.json`, `ops/conductor/handoff/evidence-2026-09-10-manual-enforcement/shared-drafts.json`.

### `review/mcp-*` — 3 branches, 2026-09-05

0 `ops/*.py` files dev lacks, 3 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `review/mcp-cap-quality-20260905` | 2026-09-05 | 2 | 0 | 2 | 1 | — | 0 |
| `review/mcp-quality-20260905` | 2026-09-05 | 2 | 0 | 1 | 1 | — | 0 |
| `review/mcp-security-20260905` | 2026-09-05 | 2 | 0 | 1 | 1 | — | 0 |

Files dev lacks, most shared first: `ops/conductor/reports/mcp-cap-closeout-ac29ca8-2026-09-05.md`, `ops/conductor/reports/mcp-cap-evaluation-ac29ca8-2026-09-05.json`, `ops/conductor/reports/mcp-final-rulings-e7558de-2026-09-05.md`, `ops/conductor/reports/mcp-security-e7558de-2026-09-05.json`.

### `lane/noguess-*` — 1 branches, 2026-09-04

1 `ops/*.py` files dev lacks, 5 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/noguess` | 2026-09-04 | 13 | 1 | 0 | 5 | — | 0 |

Files dev lacks, most shared first: `ops/conductor/tests/test_laneconf_defaults.py`.

### `lane/dispatch-*` — 1 branches, 2026-09-04

0 `ops/*.py` files dev lacks, 5 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/dispatch-job-scratch` | 2026-09-04 | 13 | 0 | 0 | 5 | — | 0 |

### `lane/record-*` — 1 branches, 2026-09-04

1 `ops/*.py` files dev lacks, 3 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/record-wall` | 2026-09-04 | 13 | 1 | 0 | 3 | — | 0 |

Files dev lacks, most shared first: `ops/devlane/dispatch/tests/test_launch_record_wall_at_mint.py`.

### `review/pr73-*` — 2 branches, 2026-09-06

0 `ops/*.py` files dev lacks, 4 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `review/pr73-integration-20260906` | 2026-09-06 | 3 | 0 | 0 | 3 | — | 0 |
| `review/pr73-merge-20260906` | 2026-09-06 | 2 | 0 | 0 | 1 | — | 0 |

### `records/wip-*` — 1 branches, 2026-09-04

0 `ops/*.py` files dev lacks, 3 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `records/wip-recovery-20260904-local-20260916` | 2026-09-04 | 2 | 0 | 0 | 3 | — | 0 |

### `deprecated/wip-*` — 1 branches, 2026-09-10

0 `ops/*.py` files dev lacks, 2 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `deprecated/wip-20260904` | 2026-09-10 | 1 | 0 | 0 | 2 | — | 0 |

### `lane/ladder-*` — 1 branches, 2026-09-04

0 `ops/*.py` files dev lacks, 2 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/ladder-audit` | 2026-09-04 | 3 | 0 | 0 | 2 | — | 0 |

### `lane/watchdog-*` — 1 branches, 2026-09-04

0 `ops/*.py` files dev lacks, 1 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `lane/watchdog-tests` | 2026-09-04 | 4 | 0 | 0 | 1 | — | 0 |

### `repo/watchdog-*` — 1 branches, 2026-09-04

0 `ops/*.py` files dev lacks, 1 record files.

| branch | last commit | commits | code | doc | records | dispatch records | successors |
|---|---|---:|---:|---:|---:|---|---:|
| `repo/watchdog-review-20260904` | 2026-09-04 | 2 | 0 | 0 | 1 | 20260904T225206Z-code-codex-880f8f | 0 |

## Against the 2026-09-16 branch-growth report

The owner supplied `agentscient-branch-growth-and-retirement-recommendation-2026-09-16 (2).md`
(Astra Max, 27,999 bytes, read 2026-09-17; the file sits in a `grok/` download
directory, which does not name its author — owner, 2026-09-17: "its not grok report -
just in a grok dir - its Astra Max"). Its census and this one agree, a day apart:

| reading | that report, 2026-09-16 14:46Z | here, 2026-09-18Z |
|---|---:|---:|
| remote branches | 387 | 393 |
| tips contained in dev | 193 | 195 |
| tips outside dev | 192 | 198 |
| open pull requests | 0 | 7 |

Six branches and seven pull requests appeared in the interval; nothing contradicts.
Its repository readings hold too, re-measured here through the GitHub API: default
branch `master`, `delete_branch_on_merge` false, merge commits allowed, squash and
rebase disabled, `dev` and `master` both protected. Repository size 12,899 KB.

That report states its own limit in §8: "Semantic patch equivalence and usefulness
were not assessed across all 192 nonpermanent tips outside dev." **This report is
that assessment**, for the 183 of those tips that never had a pull request. Its
finding — that half the inventory is already inside dev — is about ancestry; the
finding here is narrower and harder: of the tips that are *not* in dev, only 21
branches hold any code dev lacks, and those come to 34 files.

Where the two part company: that report recommends replacing "never a deleted
branch" with lifecycle retirement and bundle archival. That is a change to the law,
and the law is the owner's. Nothing here deletes, recommends deleting, or depends
on deleting.

## What this does not measure

- Whether any of the 34 `ops/*.py` files dev lacks *should* land. That is a reading
  of the code against current contracts, not an ancestry check.
- Whether work on a branch was redone in dev under a different path or a different
  name. A renamed file reads here as "absent from dev", and this method cannot tell
  a rename from an abandonment.
- Why any particular branch stopped. No session record was consulted for the
  per-branch rows; the pull-request absence is measured, the intent behind it is not.
- The 15 branches outside dev that *do* carry a pull request, and the 195 already
  inside dev. Both are out of scope here.
- Anything about the local worktrees or the archive; those are in
  `ops/conductor/handoff/worktree-archive-2026-09-17.md`.

## What to do with this

1. **The 76 dispatch-record branches need no reading.** Their commits are records of
   jobs, and the dispatch store holds the same records. Nothing is lost by leaving
   them, and nothing is gained by reading them.
2. **The 16 patch-equivalent, content-matching and no-change branches are settled
   by the measurement itself.** Dev already has their content.
3. **The 21 code-carrying branches are the only ones worth a human reading**, and
   two families cover most of it: the `discovery_v3` test family (5 branches sharing
   7 files) and the admission-enforcement family (`lane/finding-admission-20260909`
   and `lane/audit-enforcement-20260910`, 12 code files each, overlapping).
   `lane/check-tests-json` is large in commits (92) but holds only 2 code files dev
   lacks; its bulk is records.
4. **The remaining 70 add no file dev lacks, which is not the same as holding
   only records.** Measured 2026-09-18 while building the retirement lever: of the
   91, exactly **3** differ from dev only under `.dev/`. The other 70 differ from
   dev on tracked files outside `.dev/` — older or divergent versions of files dev
   already has. Nothing is lost by archiving them, but "records only" was the wrong
   word for them and this line is the correction.

## How this was measured

Every row came from one of these, run on the host at the time stamped above with
`origin` freshly fetched:

- the population: `git for-each-ref refs/remotes/origin`, each tip tested with
  `git rev-list --count origin/dev..<branch>`; pull requests from
  `gh pr list --state all --limit 1000 --json number,headRefName,state`, joined on
  head branch name.
- commits per branch: `git log --format='%h\t%cs\t%an\t%s' <branch> --not origin/dev`.
- patch equivalence: `git cherry origin/dev <branch>`; `-` means dev already has an
  equivalent patch, `+` means it does not.
- files the branch touches: `git diff --name-only origin/dev...<branch>`; files where
  it still differs from dev: `git diff --name-only origin/dev <branch> -- <those files>`.
- files dev does not have at all: that differing set minus
  `git ls-tree -r --name-only origin/dev`.
- dispatch-record association: every `refs/dispatch/*` tip tested for membership in
  the branch's commit set.
- successors: `git branch -r --contains <branch>`, minus the branch itself.

The scripts are `collect.py`, `classify2.py`, `enrich.py`, `absent.py`,
`opsabsent.py` and `render.py`, written to this session's scratchpad under
hand grant 302. They are not committed: `/tmp` is cleared at boot, so the data they
produced is this file, and re-running the commands above reproduces it.

## Every one of the 183

`kind` as defined above; `code/doc/rec` count files present on the branch and absent
from dev; `succ` counts other remote branches that contain this tip.

| branch | last | commits | kind | code | doc | rec | succ | authors |
|---|---|---:|---|---:|---:|---:|---:|---|
| `lane/audit-enforcement-20260910` | 2026-09-10 | 49 | unlanded | 12 | 3 | 20 | 0 | Grok 4.6 |
| `lane/finding-admission-20260909` | 2026-09-09 | 39 | unlanded | 12 | 3 | 16 | 1 | xormania |
| `lane/conduct-discovery-20260906` | 2026-09-06 | 11 | unlanded | 7 | 0 | 4 | 0 | xormania |
| `lane/conduct-discovery-final-tests-20260906` | 2026-09-06 | 26 | unlanded | 7 | 0 | 4 | 3 | xormania |
| `lane/conduct-discovery-runtime-fix-20260906` | 2026-09-06 | 28 | unlanded | 7 | 0 | 5 | 0 | xormania |
| `lane/onboarding-discovery-20260910` | 2026-09-09 | 29 | unlanded | 7 | 0 | 5 | 0 | GPT-6 Astra |
| `lane/onboarding-discovery-tests-20260910` | 2026-09-09 | 27 | unlanded | 7 | 0 | 4 | 1 | GPT-6 Astra |
| `lane/conduct-adapter-tests-20260906` | 2026-09-06 | 18 | unlanded | 3 | 0 | 7 | 0 | xormania |
| `lane/conduct-start-tests-20260906` | 2026-09-06 | 16 | unlanded | 3 | 0 | 5 | 0 | xormania |
| `lane/conduct-start-tests-adjudication-20260906` | 2026-09-06 | 16 | unlanded | 3 | 0 | 5 | 0 | xormania |
| `lane/check-tests-json` | 2026-09-04 | 92 | unlanded | 2 | 0 | 38 | 0 | Grok 4.6 |
| `lane/conduct-canonical-tests-20260906` | 2026-09-06 | 11 | unlanded | 2 | 0 | 3 | 0 | xormania |
| `lane/conduct-policy-code-adjudication-20260906` | 2026-09-06 | 8 | unlanded | 2 | 0 | 4 | 0 | xormania |
| `lane/conduct-policy-source-ruling-20260906` | 2026-09-06 | 8 | unlanded | 2 | 0 | 4 | 0 | xormania |
| `lane/conduct-policy-code-20260906` | 2026-09-06 | 7 | unlanded | 1 | 0 | 5 | 0 | xormania |
| `lane/conduct-policy-tests-20260906` | 2026-09-06 | 6 | unlanded | 1 | 0 | 4 | 5 | xormania |
| `lane/context-contracts` | 2026-09-04 | 19 | unlanded | 1 | 0 | 9 | 0 | xormania |
| `lane/noguess` | 2026-09-04 | 13 | unlanded | 1 | 0 | 5 | 0 | xormania |
| `lane/onboarding-policy-20260910` | 2026-09-09 | 9 | unlanded | 1 | 0 | 5 | 0 | GPT-6 Astra |
| `lane/onboarding-policy-tests-20260910` | 2026-09-09 | 7 | unlanded | 1 | 0 | 4 | 1 | GPT-6 Astra |
| `lane/record-wall` | 2026-09-04 | 13 | unlanded | 1 | 0 | 3 | 0 | xormania |
| `deprecated/wip-20260904` | 2026-09-10 | 1 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/agy-config-final-correction-20260908` | 2026-09-08 | 3 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-config-test-adjudication-20260908` | 2026-09-08 | 3 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-config-test-correction-20260908` | 2026-09-08 | 5 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-config-test-review-20260908` | 2026-09-08 | 3 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-configuration-tests-20260908` | 2026-09-08 | 4 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-contract-adjudication-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-contract-review-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-dispatch-test-review-20260908` | 2026-09-08 | 7 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-dispatch-tests-20260908` | 2026-09-08 | 3 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-envelope-final-correction-20260908` | 2026-09-08 | 3 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-envelope-test-adjudication-20260908` | 2026-09-08 | 4 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/agy-envelope-test-correction-20260908` | 2026-09-08 | 6 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/agy-envelope-test-review-20260908` | 2026-09-08 | 4 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/agy-envelope-tests-20260908` | 2026-09-08 | 3 | unlanded | 0 | 0 | 1 | 3 | xormania |
| `lane/agy-isolation-last-fix-20260908` | 2026-09-08 | 4 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/agy-isolation-legacy-flags-20260908` | 2026-09-08 | 5 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/agy-isolation-legacy-tests-20260908` | 2026-09-08 | 3 | unlanded | 0 | 0 | 1 | 1 | xormania |
| `lane/agy-isolation-test-adjudication-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-isolation-test-correction-20260908` | 2026-09-08 | 3 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-isolation-test-review-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-isolation-tests-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-lifecycle-cwd-ruling-20260908` | 2026-09-08 | 3 | unlanded | 0 | 0 | 1 | 0 | Grok 4.6 |
| `lane/agy-lifecycle-fix-20260908` | 2026-09-08 | 5 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/agy-lifecycle-fix-review-20260908` | 2026-09-08 | 3 | unlanded | 0 | 0 | 1 | 0 | Grok 4.6 |
| `lane/agy-lifecycle-ruling-20260908` | 2026-09-08 | 7 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-live-accounting-final-fix-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-live-accounting-regression-20260908` | 2026-09-08 | 3 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-live-usage-fix-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-live-usage-tests-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-native-reader-fix-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-native-regression-tests-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-portable-fixture-fix-20260908` | 2026-09-08 | 6 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/agy-probe-selection-fix-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-regression-final-fix-20260908` | 2026-09-08 | 4 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/agy-runtime-ruling-fix-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/agy-terminal-test-fix-20260908` | 2026-09-08 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `lane/conduct-adapter-adjudication-20260906` | 2026-09-06 | 5 | unlanded | 0 | 0 | 3 | 0 | xormania |
| `lane/conduct-coupling-reconciliation-20260906` | 2026-09-06 | 14 | unlanded | 0 | 0 | 5 | 0 | xormania |
| `lane/conduct-first-start-adjudication-20260906` | 2026-09-06 | 10 | unlanded | 0 | 0 | 4 | 0 | xormania |
| `lane/conduct-message-tests-20260906` | 2026-09-06 | 4 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/conduct-relay-contract-20260906` | 2026-09-06 | 5 | unlanded | 0 | 0 | 3 | 0 | xormania |
| `lane/conduct-start-adjudication-20260906` | 2026-09-06 | 9 | unlanded | 0 | 0 | 4 | 0 | xormania |
| `lane/conduct-start-coupling-20260906` | 2026-09-06 | 10 | unlanded | 0 | 0 | 4 | 1 | xormania |
| `lane/dispatch-job-scratch` | 2026-09-04 | 13 | unlanded | 0 | 0 | 5 | 0 | xormania |
| `lane/fixture-audit` | 2026-09-04 | 3 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/fixture-fix` | 2026-09-04 | 15 | unlanded | 0 | 1 | 4 | 1 | xormania |
| `lane/fixture-fix-2` | 2026-09-04 | 34 | unlanded | 0 | 1 | 10 | 0 | xormania |
| `lane/ladder-audit` | 2026-09-04 | 3 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/onboarding-completion-20260909` | 2026-09-09 | 7 | unlanded | 0 | 8 | 4 | 0 | xormania |
| `lane/onboarding-contract-20260910` | 2026-09-09 | 5 | unlanded | 0 | 1 | 3 | 0 | xormania |
| `lane/session-20260916-a` | 2026-09-16 | 1 | unlanded | 0 | 3 | 1 | 0 | xormania |
| `lane/session-20260916-i` | 2026-09-16 | 4 | unlanded | 0 | 0 | 2 | 0 | xormania |
| `lane/session-20260916-s2` | 2026-09-16 | 2 | unlanded | 0 | 1 | 0 | 0 | xormania |
| `lane/session-20260916-s3` | 2026-09-16 | 2 | unlanded | 0 | 1 | 0 | 0 | xormania |
| `lane/session-20260916-sweep` | 2026-09-16 | 8 | unlanded | 0 | 3 | 2 | 0 | xormania |
| `lane/session-budget` | 2026-09-04 | 22 | unlanded | 0 | 0 | 9 | 0 | xormania |
| `lane/watchdog-tests` | 2026-09-04 | 4 | unlanded | 0 | 0 | 1 | 0 | Grok 4.6 |
| `records/agy-closeout-20260909` | 2026-09-09 | 4 | unlanded | 0 | 5 | 2 | 0 | xormania |
| `records/codex-closeout-20260905` | 2026-09-05 | 1 | unlanded | 0 | 3 | 0 | 0 | GPT-6 Astra |
| `records/codex-machinery-20260904` | 2026-09-04 | 5 | unlanded | 0 | 1 | 0 | 0 | GPT-6 Astra |
| `records/codex-mcp-closeout-20260905` | 2026-09-05 | 1 | unlanded | 0 | 5 | 0 | 0 | xormania |
| `records/wip-recovery-20260904-local-20260916` | 2026-09-04 | 2 | unlanded | 0 | 0 | 3 | 0 | xormania |
| `repair/audit-enforcement-manual-20260910` | 2026-09-10 | 3 | unlanded | 0 | 7 | 0 | 0 | xormania |
| `repo/watchdog-review-20260904` | 2026-09-04 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `review/mcp-cap-quality-20260905` | 2026-09-05 | 2 | unlanded | 0 | 2 | 1 | 0 | xormania |
| `review/mcp-quality-20260905` | 2026-09-05 | 2 | unlanded | 0 | 1 | 1 | 0 | xormania |
| `review/mcp-security-20260905` | 2026-09-05 | 2 | unlanded | 0 | 1 | 1 | 0 | xormania |
| `review/pr73-integration-20260906` | 2026-09-06 | 3 | unlanded | 0 | 0 | 3 | 0 | GPT-6 |
| `review/pr73-merge-20260906` | 2026-09-06 | 2 | unlanded | 0 | 0 | 1 | 0 | xormania |
| `deprecated-work` | 2026-09-10 | 1 | no-file-change | 0 | 0 | 0 | 1 | xormania |
| `deprecated/session-watch-20260904` | 2026-09-10 | 2 | no-file-change | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-accounting-acceptance-20260908` | 2026-09-08 | 4 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-canonical-smoke-20260908` | 2026-09-08 | 3 | patch-equivalent | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-claude-code-ruling-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-combined-review-20260908` | 2026-09-08 | 3 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-config-remaining-adjudication-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-config-test-acceptance-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-corrected-contract-adjudication-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-corrected-contract-review-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-correction-review-20260908` | 2026-09-08 | 2 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-discovery-live-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-discovery-probe-recipe-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-envelope-remaining-adjudication-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-envelope-test-acceptance-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-final-candidate-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-final-test-ruling-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-grok-code-ruling-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-host-observation-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-isolation-implementation-20260908` | 2026-09-08 | 2 | patch-equivalent | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-live-observation-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-native-seams-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-parser-status-acceptance-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-permissions-observation-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-regression-final-ruling-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-runtime-candidate-20260908` | 2026-09-08 | 7 | patch-equivalent | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-security-ruling-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-source-last-ruling-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-stdin-observation-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-terminal-test-accept-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-terminal-test-ruling-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-test-final-acceptance-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-wire-evidence-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/agy-worker-security-20260908` | 2026-09-08 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/conduct-canonical-contract-review-20260906` | 2026-09-06 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/conduct-canonical-contracts-20260906` | 2026-09-06 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/conduct-discovery-adjudication-20260906` | 2026-09-06 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/conduct-interfaces-20260906` | 2026-09-06 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/conduct-onboard-tests-20260906` | 2026-09-06 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/conduct-wait-diagnostic-20260906` | 2026-09-06 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/dispatch-agent-local-20260916` | 2026-09-04 | 2 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/final-quality-20260905` | 2026-09-05 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/final-security-20260905` | 2026-09-05 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/fixture-apps-grok-authored` | 2026-09-04 | 5 | patch-equivalent | 0 | 0 | 0 | 0 | Grok 4.6 |
| `lane/fixture-apps-grok-authored-2` | 2026-09-04 | 6 | patch-equivalent | 0 | 0 | 0 | 0 | xormania |
| `lane/hook-false-positives-local-20260916` | 2026-09-04 | 2 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/killers` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/lane-conf-grok-authored` | 2026-09-04 | 5 | patch-equivalent | 0 | 0 | 0 | 0 | Grok 4.6 |
| `lane/lane-conf-grok-authored-2` | 2026-09-04 | 11 | patch-equivalent | 0 | 0 | 0 | 0 | xormania |
| `lane/ld23-ld24-review-20260912` | 2026-09-11 | 2 | content-in-dev | 0 | 0 | 0 | 0 | xormania |
| `lane/live-proof-20260912` | 2026-09-12 | 2 | content-in-dev | 0 | 0 | 0 | 0 | xormania |
| `lane/matrix-measure` | 2026-09-04 | 1 | patch-equivalent | 0 | 0 | 0 | 0 | xormania |
| `lane/merge-check-53d23ff9` | 2026-09-15 | 1 | patch-equivalent | 0 | 0 | 0 | 0 | xormania |
| `lane/merge-check-6bc6f898` | 2026-09-15 | 1 | no-file-change | 0 | 0 | 0 | 0 | xormania |
| `lane/merge-check-c2ee49f5` | 2026-09-15 | 1 | patch-equivalent | 0 | 0 | 0 | 0 | xormania |
| `lane/merge-check-fcc9a150` | 2026-09-15 | 1 | patch-equivalent | 0 | 0 | 0 | 0 | xormania |
| `lane/onboard-running-local-20260916` | 2026-09-04 | 2 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/onboarding-brief-inputs-20260910` | 2026-09-09 | 2 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/toolchains` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `lane/worth-session-row-local-20260916` | 2026-09-04 | 2 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/codex-live-output-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/daybreak-pr57-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/daybreak-pr58-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/daybreak-pr60-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/draft62-codex-security-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/draft62-grok-security-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/draft63-grok-security-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/draft64-codex-security-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/draft64-grok-security-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/draft65-codex-security-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/draft65-grok-security-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/grok-pr58-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `repo/lineage-review-20260904` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/lane-mcp-quality-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/lane-mcp-security-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/mcp-cap-security-20260905` | 2026-09-05 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/mcp-ruling-20260905` | 2026-09-05 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/pr63-final-daybreak-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/pr63-final-grok-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/pr65-final-daybreak-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/pr65-final-grok-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/pr66-quality-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/pr66-security-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/pr74-integration-20260906` | 2026-09-06 | 2 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/readme-20260905` | 2026-09-05 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/readme-claude-20260905` | 2026-09-05 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/readme-followup-20260905` | 2026-09-05 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `review/readme-ruling-20260905` | 2026-09-05 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `reviews/final62-codex-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `reviews/final62-grok-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `reviews/final64-codex-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |
| `reviews/final64-grok-20260905` | 2026-09-04 | 1 | dispatch-record | 0 | 0 | 0 | 0 | xormania |

