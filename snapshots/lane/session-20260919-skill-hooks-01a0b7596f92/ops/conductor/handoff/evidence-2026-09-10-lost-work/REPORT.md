# Lost-work audit — 2026-09-10

## Result

The audit found recoverable work stranded between worker output, branch integration and trunk delivery. It did not demonstrate irretrievable source loss. Existing snapshots, transport refs and branches preserve substantial output, including invalid candidates that must not be accepted merely because they exist.

This was a read-only source audit. No existing source, branch, dispatch record, test, runtime configuration or acceptance state was changed. The earlier manual TDD documentation edit remains uncommitted in its own worktree and was held during this audit. Copies of uncommitted files were saved only in this audit directory, with hashes and original paths.

## Measurement and coverage

Measured against dev `20f9bcaf2b3ae2152b9cab766637b5a89b71214b`. See `measurement.json` for UTC timestamps. Start/end local refs and live remote heads were compared and did not move between the captured endpoints.

- 272 local branches and all 97 live GitHub branches; 98 remote-tracking refs consist of those branch names plus origin/HEAD. All remote head objects were readable locally. Different local/remote tips produced 299 inventory rows.
- 263 registered worktrees and 613 canonical dispatch directories; every worktree/snapshot Git-status query succeeded. There were 593 current record.json files. Of 20 directories lacking one, 16 metadata copies were located in reachable Git history and one in an unreachable but readable commit. Three directories have no located close record; their names identify two plans and one review, and they retain partial files. See legacy-record-custody.json.
- All local branches were checked against dev ancestry and non-merge patch equivalence: 95 tips are ancestors of dev; 118 have only retained records or patch-equivalent authored commits; 59 retain unmatched authored history needing disposition. These categories count branches, not independent features, and include intentional historical archives, plans, tests and superseded versions.
- Git object check `git fsck --full --no-reflogs --unreachable` exited 0 with empty stderr. It listed 182 unreachable commits, 58 trees and 49 blobs. 173 commits have equivalent reachable patches. The remaining nine comprise three merge commits, two WIP stash commits, one index commit, one empty untracked-files commit and two dispatch-record commits. The two WIP stashes' changed file blobs are preserved in reachable history; the matrix wiring stash's two files exactly match current dev. These are not nine missing implementations.
- GitHub returned 78 PRs, below the requested 1,000 limit. The only open PR was draft #78, the worker input-filename fix. A branch without a PR is not automatically abandoned.

## Priority custody findings

| Work | Preserved location | What the audit established | Disposition needed |
|---|---|---|---|
| Corrected enforcement tests completed after the interrupted session | `refs/dispatch/20260910T014425Z-tests-grok-46f153`, head `7875a0e9843c71e07d41090d238401f948311d15` | Seven correction commits have no equivalent patches on any scanned branch or dev. The branch contains the dispatch record, not these corrections. The worker reports valid fixture controls and intended RED; this audit did not independently accept that claim. | Inspect this correction before commissioning another rewrite. Obtain independent acceptance of the exact tests and retained RED evidence before implementation. |
| Committed-result recovery and concurrent test-store guard repairs | `lane/collect-recovery-20260910`, source `955e0a9eb24b2096e8609ec163ec992fe01a6eac` | Source and independent tests are on the branch, absent from dev, with retained TDD/full-suite evidence. This audit did not rerun those tests. The live remote branch exists; no PR was found for it. | Finish the existing bounded acceptance/publication process; do not recreate the repair. |
| Git-ref freshness monitor correction | `lane/dev-freshness-20260909`, source `61556038e3bec511bb17d53feb67d3a54699c0c0` | Implementation, corrected tests and retained TDD evidence exist on the branch, absent from dev. A remote branch exists; no PR was found. | Reconcile final reviews and deliver the existing branch. Do not claim periodic activation from source presence. |
| Bounded foreground dispatch resume front door | `refs/dispatch/20260905T011510Z-code-codex-67a6c7`, source `02d0a8656759d19752f88c24732f2eff384a0356` | Worker envelope is ok; the implementation patch is not equivalent to a patch on any scanned branch. `lane/security-resume-binding-20260904` contains the contract and record, not the source implementation. Generic launcher resume already exists on dev; this is the distinct bounded wrapper/front-door change. | Read retained acceptance and security evidence, check relevance against current contracts, then decide integration or explicit supersession. |
| Discovery runtime repair from September 6 | `refs/dispatch/20260906T144012Z-code-codex-db74db`, source `fb7803f12594ea77d7c0ed8e720ec51998b43959` | Four source/registry files were committed and preserved. No equivalent patch was found on a branch. The dispatch is invalid (missing terminal envelope; CLI exit 1). Its lineage branch retains tests and its record. | Recover as an invalid candidate for inspection, not an accepted implementation. Compare with the later partial discovery work before any new implementation. |
| Inert policy evaluator | `lane/conduct-policy-code-adjudication-20260906` and `lane/conduct-policy-source-ruling-20260906`, source `9ab2a370351ec5b43f808ea6b97ebb3f489245e3` | A 1,645-line implementation exists outside dev. Independent adjudications explicitly kept it INVALID, accounting for 24 test failures and unresolved custody/contract issues. | Preserved rejected work, not a previously completed enforcement system. Reuse requires explicit defect disposition and valid TDD; do not activate it. |
| Newer onboarding partials | Snapshot directories ending `6d01cf`, `b9d9bc`, `cedae4` | Discovery has three modified source files; policy has an untracked lane_policy.py; onboarding contract has two modified documents. All three jobs record invalid timeout outcomes. These files are uncommitted. | Preserve and compare with earlier candidates; resolve scope before resuming. Copies and SHA-256 values are in the custody archive. |
| Session-budget enforcement | `lane/session-budget` | Retains plans, ladder records and added matrix tests. The branch's own delta does not include a session-budget matrix implementation; its ladder records implementation_markers=[] and pr=null. | This is tests/planning retained without completed enforcement, not evidence a working guard disappeared. |
| Debrief from the failed session | `ag-finding-admission-20260909/ops/conductor/AAR-2026-09-10-review-process-failures.md` and adjacent growth.json | Both remain untracked. They are readable and copied into the custody archive. | Retain in the session's eventual closeout; do not describe them as published. |
| Other old partial lines | See ALL-BRANCHES.md: check-tests-json, fixture-fix, context-contracts, noguess, record-wall, dispatch-job-scratch, conduct test branches | Unmatched authored history remains. Some are tests only or earlier versions; shared commits cause multiple candidate branch rows. | Use the per-commit/path index to assign a disposition. This audit does not certify their quality or recommend merging all of them. |

## Correction to the earlier hook diagnosis

The claim that Bash was not wired to the matrix was wrong. `.claude/settings.json` invokes `context-precheck.sh` for Bash; that wrapper calls `matrix.py` at line 20. The original wiring commit `2ba1ae4` states the same chain, and both wiring files match the surviving WIP stash exactly. The matrix wiring was not lost from dev. This source check establishes the configured Claude path, not successful execution of every hook in the failed Codex session. Cross-harness activation was not established by this audit.

The advisory test guard and matrix's lack of a valid-RED acceptance check remain separate observations. A hook present in source, a test written for it, a worker result preserved under a transport ref, branch integration, trunk delivery and runtime activation are different states. The locations above demonstrate several gaps between those states; no claim is made that a single mechanism caused every interruption.

## Intentional retention and limits

`lane/workflow` is not a recovery target by default: its PR was closed unmerged at the owner's instruction, as recorded in ops/README.md. Retained records/* branches and review records likewise must not be counted as missing runtime features. The agy branches include older contract variants and patch-equivalent work; agy delivery is already represented by merged PR #77.

No deleted or never-saved file can be ruled out merely by a clean fsck. This audit covers this clone, its live origin heads, registered worktrees, reflogs, reachable/unreachable Git objects and the canonical dispatch store. It does not cover other machines, unregistered clones, every ignored directory, arbitrary /tmp output, expired/pruned Git objects or independently revalidate every candidate's tests. Stable patch IDs detect equivalent patches, not all semantic reimplementations or supersession. Unreachable blob content was not exhaustively interpreted.

## Artifacts and reproduction

- ALL-BRANCHES.md: every branch/head classification and per-commit authored paths for the 59 local candidate branches.
- branches.json / classified-branches.json / unmerged-commits.json: raw and derived branch evidence.
- dispatches.json / classified-dispatches.json: per-directory record, snapshot status, ref and patch-equivalence custody.
- worktrees.json: every registered worktree and its measured status.
- unreachable-commits.json, fsck.txt, fsck.stderr, reflogs.txt: object/reflog evidence.
- uncommitted-custody.tar.gz and uncommitted-custody-manifest.json: copied uncommitted files with original paths and hashes. The archive is a local copy, not off-machine backup or acceptance.
- refs-start.tsv / refs-end.tsv and remote-heads.tsv / remote-heads-end.tsv: point-in-time branch heads.
- pull-requests.json: GitHub PR evidence.
- inventory.py, classify.py and report.py: read-only investigation scripts and derived report generation. These are audit apparatus, not proposed repository tools or production tests.

No recovery merge, cherry-pick, dispatch, hook edit, test edit or deletion was performed during this audit.
