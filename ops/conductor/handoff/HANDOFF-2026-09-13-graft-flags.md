# Handoff — 2026-09-13, LD-33, LD-34, the ledgers' shape, the dispatcher tests' tree

Record by Claude Fable 5.1 on `lane/session-20260913-b` (#179), `-c`
(#180, #182), `-d` (#184), `-e` (#185), `-f` (#186) and `-g`. The board, PRs and grants are re-measured by
`onboard.py`, not taken from here.

## Where things stand

- PR #179 (`2c983635`), draft: graft-first splits combined short flags so
  `-rl` and `-rnc` read as a file list or a count, as the refusal text
  promised. LD-33 in the defect ledger; three corpus rows in
  `probes-2026-09-13-graft-flags.jsonl`. Merged at `37750dd0` at the
  owner's word ("you merge when green").
- PR #180 (`5a9e123e`): matrix.py and `ops/devlane/hooks/tests/` are wall
  paths; the registry row and docstring name them; LD-34 and three corpus
  rows. Five checks pass at `5a9e123e`. After it lands, a hook row or a
  hooks test changes only in a session under a wall grant that writes
  wall paths and records. Extending the list is one wall grant now that
  the list names matrix.py (LD-34, closed at `23a30592` on a live
  reading under grant 192).
- Defect rows from LD-36 are files under `ops/conductor/handoff/lane-defects/`,
  written by `python3 ops/conductor/tools/defects.py add --where W --defect D
  --repair R --tests T` (#184, `39cf7d81`); the page's table is frozen at
  LD-35. From `-f` (`725109a5`) the shape is `ledger.py`, one lever over
  every appended register: `ledger.py add pitfalls --what-bit T --do-instead T`
  for pitfalls from row 30 (the table stops at 29), `ledger.py ledgers` for
  the list; defects.py is a shim over it. A fetch before minting the id
  would narrow the same-id window and is not done. A corpus row that
  pins neighbours in a sorted list breaks on any session's insert
  (pitfall 30): pin membership.
- The dispatcher wrapper tests dispatch against a scratch repository
  (#185, `1c7fd5ee`); a branch's lineage no longer reads as their
  failure. suites.sh runs no ruff on the host; the lane job does, so a
  local green can still be a CI red on lint.
- Token thrift: items 2, 3, 4 landed at `4fdc6d0e` (#175). Item 1, context
  churn, is practice, not code. Whether the change worked is the next full
  window of `python3 ops/devlane/telemetry/worth.py waste --repo
  /home/scientdb/projects/uscient/agentscient --since 2026-09-13T05:00:00Z`;
  the early reading (05:31Z) is in the AAR.
- Parallel work, after `-g` (`5975dabe`): a session lifts its own branch
  with `deliverable.py remove <branch>` at close, never `clear` while
  another session runs; ledger ids count the trunk's rows after a fetch.
  Still open: the consolidation gate's placement lists (MIGRATED, PENDING,
  NO_WIRE in test_instrument.py) move to a `placement` key in each
  registry file, in this session's own PR after agentscient-5e's #187
  lands (its choice, (b)); the conventions page line 87 names the three
  placements and needs the registry wording; NO_WIRE keeps its meaning. A
  corpus-shape rule against expects that span lines is a probes.py (wall)
  change, not done; pitfall 30 is the practice. The hook's deliverable
  remedy still says `clear` (matrix.py, wall): one line for a wall session.
- Grants 185 and 188 to 196 settled; 198 settles against the PR from `-g`.
  Worktrees `../wt/ag-session-20260913-{b,c,d,e,f,g}`. The lock names `-n` (landed), `-a` (the instrument
  session, grant 187, running beside this one), `-b` (landed) and `-c`.
  Worktrees `../wt/ag-session-20260913-b` and `-c`.
- The test kit plan's reading with the owner (HANDOFF-2026-09-13-token-thrift
  §Where things stand) is untouched by this session and stays the thread
  for the session the owner opens for it.

## Retrieval

```sh
git show dev:ops/conductor/handoff/HANDOFF-2026-09-13-graft-flags.md
gh pr list --state all --head lane/session-20260913-g --json number,state,mergeCommit
python3 ops/conductor/tools/ledger.py ledgers
python3 ops/conductor/tools/hand.py open
```

Left behind on purpose: the session transcript and the scratchpad.
