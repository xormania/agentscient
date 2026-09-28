# I-022 — an external review of CI and the test corpus, and a testkit proposed

- recorded: 2026-09-11, in session, after the LD-23 and LD-24 repairs landed (PR #139)
- source: owner, verbatim below; the two documents beside this record were supplied by the owner under `.xor/in/ci-and-tests/` and are copied verbatim, their author not verified
- disposition: open

## In the owner's words
> i'd like you to look at `.xor/in/ci-and-tests/`

> since you agree - you should relocate the files to a tracked location - then let's talk about how to make it happen.

## The documents

- `I-022-ci-review-handoff-2026-09-11.md`: the CI review, reliability, efficiency and flakes, measured at dev `032092c`.
- `I-022-test-framework-research-2026-09-11.md`: the test framework research and the `ops/testkit` proposal, measured at the same sha.

Both were copied byte for byte (`sha256sum`: `9b97c67a4f12b608…` and `e2e5346e940fc886…`, the same under both paths). Their evidence links are GitHub run and PR pages; every claim checked below was checked against this tree and the run history, not against the links.

## What was heard

The conductor's reading, said in session and recorded here.

The CI review is accurate and conservative. Its five flake classes are this lane's own ledger rows: LD-21, the receipt ordering repair, LD-16 (PR #114), LD-8 (PR #103) and LD-22 (PR #136). Its refusals to recommend rerun-until-green, path skipping and serialized suites agree with the lane's law on absence and measurement. Two of its recommendations are a few lines in the workflow and carry no risk: cancel superseded pull-request runs, and set measured job timeouts. The duplicate push run on dev stays, because the workflow says why it exists.

The research document's diagnosis matches what was measured: isolation discipline exists but is re-implemented per suite, which is the LD-4, LD-9, LD-16, LD-22 pattern stated as a count. Its proposal is the end-to-end fixture of I-020 under another name: `TestWorld` is the fixture's isolated root, the fake tool registry is the fake harness CLI, invariant case tables are scenarios as data as `docs/probes.md` requires, and its calibration is `docs/concerns.md`'s planted faults. It keeps unittest and adds no vendor. The reading is to fold its Phase 1 into I-020's scope rather than run two efforts, and not to start with the lane_mcp pilot: the ladder suite stubs the dispatcher and launcher, so 929 green conductor tests could not see LD-23 or LD-24 on 2026-09-11, because the stub replaced the component that held the defect. The fixture that runs the real driver against a fake CLI is the first scenario to build. The portfolio metrics and mutation testing wait until two families share the primitives, as the document itself says.

What it must reconcile with: the second-producer rule (a case row added to a shared table still needs a producer other than the fixer), the pipeline (scope settled with the owner, plan by Fable, tests by Grok, code by Codex, review by both), and the deliverable lock (this is queued work, not a finding to branch on).

## Standing facts it must reconcile with

Measured 2026-09-11 against dev `9dfa27e` (the ideas' claims are stamped `032092c`; none of these files changed between):

- `grep -c concurrency .github/workflows/ci.yml` → 0; `grep -c timeout-minutes` → 0; `grep -c merge_group` → 2.
- `gh api 'repos/uscient/agentscient/actions/runs?event=merge_group&per_page=1' --jq .total_count` → 0.
- `ops/bin/suites.sh` on this host at `032092c` plus the LD-21 change: nine suites OK, 2727 tests; `grep -c ResourceWarning` on its log → 3 warnings (two `subprocess … is still running`, one `unclosed file`), plus 3 tracemalloc hints.
- lane_mcp: `ops/conductor/tests/test_lane_mcp*.py` 152308 bytes over `ops/conductor/tools/lane_mcp.py` 16462 bytes → 9.25, three test files, as the document says.
- Across 186 test files under `ops/**/tests/` and `.claude/skills/*/tests/`: 52 set `HOME` by hand, 14 through an isolation helper, 82 build a `TemporaryDirectory`, 7 use `live_store_guard`, 6 fake programs are embedded as string constants in 2 files (`test_ladder_lever.py`, one other).
- LD-23 and LD-24 (PR #139): the conductor suite was 929 OK at `032092c` with the dispatcher, launcher, landing lever and ledger stubbed; the live ladder 96e53f stopped at tests-fix on both.

## Next

Settled with the owner in session, not here: whether the CI hardening lines go in as their own small change; whether I-020's scope absorbs the testkit's Phase 1 when item 31 lands.
