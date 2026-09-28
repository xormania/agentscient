# Handoff — 2026-09-12, after item 31 and the stage set

Record by Claude Fable 5.1, committed straight to dev under the records
ruling. See the [AAR](../AAR-2026-09-12-item31-stage-set.md). Re-measure
before acting on anything below.

## Where things stand

- dev `97ca65b`. The release draft PR #149, dev into master, is open and
  is the owner's to merge. Zero other open PRs; no open grants; the lock
  is cleared with this record.
- Item 31 is on dev whole: the check-tests job on the wire, the envelope
  validated at the stop, the custody file for tests-fix, the check-envelope
  verb and its registry row, the read-role write guard with the plan and
  adjudicate outputs declared. Two ladder records read `stopped` on dev by
  design: 96e53f at security-re (one fix round per ladder, the PR opened by
  hand) and a4676a at tests-fix (the landing lever refused a trailer-less
  worker commit; the rest by hand).
- The stage set: `ops/conductor/stage-sets.json` holds `contract` and
  `lane`; the driver reads it; `ladder.py stage-sets PATH` validates one.
- Records commit straight to dev (owner, "choice #2"); `AGENTS.md` and
  `ops/README.md` still say draft-first for everything and need the
  one-sentence carve-out by PR.
- Eleven worktrees this session, all clean and pushed: `ag-ld-21`,
  `ag-item31-skeptic-wire`, `ag-ld-23`, `ag-ci-and-tests-review`,
  `ag-ci-and-tests-survey`, `ag-flag-141`, `ag-flag-141-b`,
  `ag-idea-git-capabilities`, `ag-stage-set`, `ag-item31-slice2`,
  `ag-item31-slice3`, all under `../wt/` with their dates.
- The watchdog still runs from `../wt/ag-deliverable-lock-20260911`.

## Corrections to retain

- **Green means every named check passing on the head that will merge.**
  Wait until the head's run has registered before watching (pitfall 22).
- **Write commit messages and PR bodies to files**; a heredoc inside a
  quoted `bash -c` breaks on an apostrophe and lands a truncated message.
- **The hooks resolve relative paths against the main checkout** and read
  shell variables as literals; spell every path in full from the worktree.
- **A tests-fix is a correction** since #133: the driver names one
  `--answers` per skeptic finding and stops `undisposed` until each is
  disposed with a contract citation.
- **The work-order resolver reads the supplied inputs first**; two work
  orders on the shelf no longer make it resolve nothing.
- **Slice 3's plan section D7 is superseded** by item 5 as amended; the
  guard exempts declared outputs.

## Open, owed, not started

- The second-producer regression tests for LD-23 and LD-24, dispatches to
  Grok after the deliverable closed; owed by the ledger's procedure, not
  dispatched under the blanket grant.
- Done after this record was first written, at the owner's word: the three
  ResourceWarnings (#150, 2578d55) and the two CI hardening lines (#151,
  97ca65b), grants 150 and 151 settled.
- The law carve-out for records in `AGENTS.md` and `ops/README.md`.
- The end-to-end fixture work order, with Astra's first phase inside it;
  the census and per-project verdicts as a read job; the lane MCP pilot
  after.
- Slice 1's three contract-pin files each carry their own markdown parser;
  a shared reader is a row for the fixture's scope.
- 567 of 789 findings open; 90 grants settled unverified. Standing debt.

## Next thread

Owner, 2026-09-12: "i have to start working on the prod-lane". The dev
lane is done to the owner's word; the release PR waits on the owner. The
prod lane's rules are in `AGENTS.md` §Standing rulings; nothing in this
session touched the application.

## Retrieval

```sh
git show dev:ops/conductor/AAR-2026-09-12-item31-stage-set.md
git show dev:ops/conductor/handoff/HANDOFF-2026-09-12-item31-stage-set.md
```

Left behind on purpose: the session transcript and the scratchpad (the
edit scripts for grants 143 to 149, the ladder logs, the suites logs).
