# AAR — 2026-09-13, the token question; LD-33, LD-34; the ledger's shape; the dispatcher tests' tree

Session record by Claude Fable 5.1 on `lane/session-20260913-b` (#179,
`37750dd0`), `-c` (#180 `23a30592`, #182 `e7e0d41e`), `-d` (#184
`39cf7d81`) and `-e`, all cut from dev. Measured at write time: `-e` at
`7d7e3714`, its PR not yet open; grants 188 to 194 settled, 195 open; the
lock names `-n`, `-a`, `-b`, `-c`, `-d`, `-e`. The
[handoff](handoff/HANDOFF-2026-09-13-graft-flags.md) carries the next thread.

## Request and outcome

The owner asked, in order: the tail of the previous session's close, pasted
as the opening message; "is the token optimizing work done?"; "hand grant
ok'd to fix"; "no - you merge when green - then tell me about the matrix
issue"; "hand grant ok'd - Add matrix.py and the hooks test directory to
the wall paths"; "hand grant ok'd close the open thing, in LD-34"; "re: other
session #181 - is that an issue? should we fix it?"; "can you communicate with
other claude session - verify that its not fixing those issues first. If its
not, hand grant - fix issue #1 - PR and merge, then issue #2 - PR and merge".

- Answer given at `cb716534`: thrift 2, 3 and 4 landed in #175 (`4fdc6d0e`);
  class 1, context churn, has no code countermeasure, its remedy is the
  practice the owner applied by opening this session; the test is the next
  window of `worth.py waste`, which at 05:31Z showed the two sessions
  opened after the change at 53k and 70k mean context against 243k to
  520k for the three before it, too few turns to call.
- Found while measuring at `cb716534`: the narrowed graft-first row refused
  `grep -rl` three times in this session (graft-first.log 05:27Z to
  05:29Z), the refusal text saying a file list stays allowed. LD-33.
- One commit, `2c983635`: combined short flags split before the count-flag
  check; red 1 failure then 1 OK with one command; test_matrix 70 OK,
  hooks suite 282 OK, corpus 108 pass. PR #179, merged by this session at
  the owner's word, `37750dd0`.
- The matrix issue, answered at `37750dd0`: the law names the registry and
  engine as the wall, `WALL_PATHS` named boundaries.json and engine.py,
  so the rows and their tests were lane code. Owner: add them. One commit,
  `5a9e123e`: the list gains matrix.py and `ops/devlane/hooks/tests/`;
  red 3 failures then OK; hooks suite 282 OK; corpus 111 pass. LD-34.
  PR #180, five checks pass; merged `23a30592`. LD-34's open half closed
  on four live readings, #182 merged `e7e0d41e`.
- **Issue 1, the ledger's shape** (#184, merged `39cf7d81`): three of five
  merge-forwards since 2026-09-11 conflicted in lane-defects.md. defects.py
  (next, add, show, list) writes one file per row under `lane-defects/`
  from LD-36; the table is frozen at LD-35. Red 6 then 6 OK; conventions
  gate 18 OK; the consolidation gate named the new tool and gained it.
- **Issue 2, the CI signal** (`7d7e3714`): the dispatcher wrapper tests
  dispatched against the live checkout, so a branch behind or conflicting
  with dev failed a dozen of them with stale-base (#175, #182). The fixture
  builds a scratch repository with no origin ref. Red 1 of 2 then 2 OK;
  the four wrapper suites 100 OK; suites.sh 2972 tests, exit 0.
- Session agentscient-5e, asked first, held branch `-a`, grant 193 and #183
  and said neither issue was in its scope; agentscient-8e did not answer.

## What was decided and why

- **Ordinary grant, not wall class**: matrix.py is not in `WALL_PATHS` at
  `cb716534`, and the wall-write row refuses a wall grant that touches a
  non-wall path; the previous thrift commit `cc04f7d9` took the same path
  and named the gap. Closed by #180 at the owner's word.
- **Two grants for the wall extension**: the enforcing hook is the main
  checkout's matrix.py, whose list at `37750dd0` did not name matrix.py,
  so a wall grant (189) refused it as non-wall code and an ordinary grant
  (190) wrote it and its test; 189 wrote boundaries.json.
- **LD-34 closed on a reading, not a code change** (owner: "close the open
  thing, in LD-34"): with #180 on dev at `23a30592`, the enforcing hook
  lists matrix.py and the hooks tests, so the next extension of the list
  writes only wall paths under one wall grant. Four live readings under
  grant 192, in the ledger row; the fourth, a wall grant refused on
  launch.py, is the isolation rule working, not a gap.

## What went wrong

- **Two ruff rounds on #184**: suites.sh on the host runs no ruff, so the
  local run at `f6494db0` could not see six findings the lane job found;
  the first fix commit `d814a547` said ruff passed with one finding left,
  read from a piped ruff whose exit I printed and did not act on; corrected
  at `d0bbd3c4`.
- **#182's lane job failed on the very defect it was recording**: #181 had
  landed LD-35 in the same table; resolved by merging dev forward at
  `47c3a540`.
- **A push refused stale**: dev moved five commits (#183) between my
  commit and the push on `-d`; merged forward at `4dfd968b`, no conflict.
- **One unbounded read of my own**: `probes.py run` prints one JSON line
  carrying every row; I tailed it twice without a filter and paid for the
  full corpus twice. Class 2 of the thrift table, in the session that was
  measuring class 3.
- **Hook refusals on my own command shapes**: 3 graft-first (LD-33, the
  change at `2c983635`), 2 clipped-sweep on a multi-alternation grep with
  a head, 1 deliverable (a worktree cut in the same command as the lock
  add, so the lock add never ran), 1 hand-write (the grant assignment
  after a `cd` is not a leading assignment).
- **Lever usage learned by refusal**: `deliverable.py add` wants `--why`;
  `probes.py run` takes no file; a nearmiss row needs `premise_flaw`. Each
  cost a turn.

## Calibration

- `worth.py waste` for this session at 05:31Z: 590,764 tokens, 11 turns,
  mean context 53k; at write time unmetered, roughly 30 turns.
- Corpus: 108 pass, 0 fail, 0 unreachable, from the tree at `2c983635`.
- Corpus: 111 pass, 0 fail, 0 unreachable, from the tree at `5a9e123e`;
  112 at the close, run from the tree at `23a30592` plus the closing row.
- Corpus: 119 pass at `f6494db0`; suites.sh on `-e` at `7d7e3714`: 2972
  tests, exit 0; ruff over ops/conductor: all checks passed.
