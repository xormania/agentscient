# Handoff — 2026-09-10, lost-work audit

Owner-requested record by GPT-6 (`gpt-6-astra`). Retained branch:
`records/lost-work-audit-20260910`, created from dev
`20f9bcaf2b3ae2152b9cab766637b5a89b71214b`. This record hands over the audit;
it does not supersede unrelated lineages or accept their unfinished work.
See the [AAR](../AAR-2026-09-10-lost-work-audit.md).

## Start here

**Read `/tmp/ag-lost-work-audit-20260910/REPORT.md` first.** The original audit
directory also contains JSON inventories, refs, reflogs, object-check output,
PR readings, investigation scripts and a local archive of uncommitted files.
If `/tmp` is unavailable, use the [retained report](evidence-2026-09-10-lost-work/REPORT.md)
and [every-branch inventory](evidence-2026-09-10-lost-work/ALL-BRANCHES.md) in this
bundle. No irretrievable source loss was demonstrated; preserved but stranded,
rejected and incompletely delivered work was found.

Owner steering: inspect all branches for lost work before continuing TDD/hook
changes. The owner explicitly requires TDD and was angry that implementation
proceeded against invalid tests. Do not treat that requirement as ambiguous,
substitute more documentation for enforcement, or re-create recovered work
before inspecting its custody. This closeout authorizes no blanket integration.

The audit-time scope was 272 local branches, 97 live remote branches, 263
worktrees and 613 dispatch directories. The [measurement](evidence-2026-09-10-lost-work/measurement.json)
is stamped against dev `20f9bca`; branch classification was 95 ancestors,
118 records/equivalent patches, 59 unmatched authored-history candidates.
The candidates are not 59 independently missing features. PR #78 was the only
open PR in the captured GitHub query. Re-measure before an outward action.

## Corrections the next session must retain

- **Bash does reach the matrix through `context-precheck.sh`.** The earlier
  claim that it was unwired was wrong. The wrapper calls `matrix.py` at line
  20. Cross-harness execution/activation in the failed Codex session was not
  established by this audit. Do not repair the alleged missing Bash matcher
  on the strength of the retracted diagnosis.
- An invalid test batch is not permission to change the contract to satisfy
  it. Valid RED, independent test acceptance and frozen bytes precede code.
  Stop the affected implementation when the acceptance test proves defective.
- The branch receiving a dispatch record does not prove it received that
  worker's implementation or tests. Verify the result commit separately.
- The old `lane/workflow` retention is intentional; its unmerged runtime is
  not authorization to restore the withdrawn migration plan.

## Recoverable holdings and next actions

These are audit-time locations, not current acceptance certificates. Read their
existing records and compare their exact bytes with dev before deciding a
bounded recovery. Do not merge, collect as accepted or activate invalid output
merely because it can be recovered.

| Holding | Exact custody | Next bounded action |
|---|---|---|
| Latest enforcement-test correction | `refs/dispatch/20260910T014425Z-tests-grok-46f153`, head `7875a0e9843c71e07d41090d238401f948311d15` | Inspect seven correction commits absent from the scanned branches. The worker's valid-RED claim still needs independent acceptance; do not commission a duplicate rewrite or start enforcement implementation first. |
| Recovery and concurrent test-store guard repair | `lane/collect-recovery-20260910`; source `955e0a9eb24b2096e8609ec163ec992fe01a6eac` | Reconcile retained tests, RED/GREEN evidence and final review records, then finish existing delivery. No PR found at audit time. |
| Git-ref monitor repair | `lane/dev-freshness-20260909`; source `61556038e3bec511bb17d53feb67d3a54699c0c0` | Reconcile final bounded acceptance and delivery; source presence does not prove periodic activation. No PR found at audit time. |
| Bounded resume front door | `refs/dispatch/20260905T011510Z-code-codex-67a6c7`; source `02d0a8656759d19752f88c24732f2eff384a0356` | Worker result is ok; source is absent from branch patch history. Check current contract relevance and acceptance before integrating. This is distinct from generic launcher resume already on dev. |
| Older discovery repair | `refs/dispatch/20260906T144012Z-code-codex-db74db`; source `fb7803f12594ea77d7c0ed8e720ec51998b43959` | Invalid terminal result; compare its four changed files with the newer discovery partial before new work. |
| Inert policy implementation | `lane/conduct-policy-code-adjudication-20260906` / `lane/conduct-policy-source-ruling-20260906`; source `9ab2a370351ec5b43f808ea6b97ebb3f489245e3` | Independent adjudications explicitly keep it invalid with unresolved test/custody issues. It is not a completed enforcement system awaiting a toggle. |
| Three dirty failed-job snapshots | `/home/scientdb/.local/state/agentscient/dispatch/` IDs `20260910T001358Z-code-codex-6d01cf`, `20260910T001531Z-code-codex-b9d9bc`, `20260910T010956Z-code-codex-cedae4`, each under `snapshot/` | Preserve and compare discovery source, policy source and onboarding contract partials. All recorded timeout outcomes are invalid. |
| Session-budget work | `lane/session-budget` | Plans and tests are retained; no corresponding guard implementation was found in that branch's delta. Resolve its incomplete status rather than claiming enforcement disappeared. |

The [inventory](evidence-2026-09-10-lost-work/ALL-BRANCHES.md) indexes all remaining
branches and candidate commits, including check-tests-json, fixture-fix,
context-contracts, noguess, record-wall, dispatch-job-scratch and conduct tests.
It preserves old variants and intentional record branches without recommending
their wholesale restoration.

## Paused edit and uncommitted records

Manual TDD edit: **uncommitted, not on dev, no live guard installed**.
Branch `docs/tdd-valid-red-20260910`, worktree
`/home/scientdb/projects/uscient/wt/ag-tdd-valid-red-20260910`, files `AGENTS.md`
and `ops/process/tdd.md`. Its diff check passed. Hold it during recovery triage;
do not describe it as landed or mechanically enforced.

The recovered session `01a08871-8cbc-7393-a820-aca20e10a6a9` wrote
`/home/scientdb/projects/uscient/wt/ag-finding-admission-20260909/ops/conductor/AAR-2026-09-10-review-process-failures.md`
and adjacent `handoff/evidence-2026-09-10-review-process/growth.json`; both were
untracked at audit time. Its local transcript is
`/home/scientdb/.codex/sessions/2026/09/09/rollout-2026-09-09T19-12-18-01a08871-8cbc-7393-a820-aca20e10a6a9.jsonl`.
The exact exception was not found in the inspected records.

Local preservation archive:
`/tmp/ag-lost-work-audit-20260910/uncommitted-custody.tar.gz`.
All 25 copied files matched the [manifest](evidence-2026-09-10-lost-work/uncommitted-custody-manifest.json).
It includes the main checkout's two untracked WIP files, old check-tests-json
scratch files, the prior debrief/evidence, the paused manual edit and the three
worker partials. The archive itself is not committed or published here.

## Stable retrieval and closeout limits

Once this bundle is committed, retrieve it without depending on its worktree:

```sh
git show records/lost-work-audit-20260910:ops/conductor/handoff/HANDOFF-2026-09-10-lost-work-audit.md
git show records/lost-work-audit-20260910:ops/conductor/AAR-2026-09-10-lost-work-audit.md
git show records/lost-work-audit-20260910:ops/conductor/handoff/evidence-2026-09-10-lost-work/REPORT.md
```

Record the resolved full commit for immutable retrieval. Remote custody is only
established by a matching live origin ref after publication, not by these
instructions. No automatic onboard selection or trusted discovery bindings are
created by this report. The retained branch is not a dev/master merge request.

The [probe corpus](probes/probes-2026-09-10-lost-work-audit.jsonl) covers key
holdings through allowlisted Git reads. Author checks are not independent
grading and do not approve the recovered source or tests. No full suites or
vendor runtime probes were run in this closeout.

Explicitly left behind: full raw audit JSON/ref/reflog/object outputs and scripts
under `/tmp`, the local custody archive, original transcripts, live dispatch
stores, and all source/test worktrees. The retained audit report, branch index,
measurements, original audit checksum index and archive manifest are copied
here. The checksum index includes local-only artifacts; it does not claim all
listed bytes are published. Other machines, unregistered clones, all ignored
paths, expired objects, semantic equivalence of every candidate and current
runtime activation remain outside the audit. No irretrievable-loss guarantee,
independent TDD acceptance or monetary-spend total is claimed.
