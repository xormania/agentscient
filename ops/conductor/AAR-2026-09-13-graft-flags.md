# AAR — 2026-09-13, the token question; LD-33; the wall list (LD-34)

Session record by Claude Fable 5.1 on `lane/session-20260913-b` (#179,
merged at `37750dd0`) and `lane/session-20260913-c` (#180), both cut from
dev. Measured at write time: #180 open as a draft at `5a9e123e`, five
checks pass; grants 188 settled, 189 and 190 open; the lock names `-n`,
`-a`, `-b`, `-c`. The [handoff](handoff/HANDOFF-2026-09-13-graft-flags.md)
carries the next thread.

## Request and outcome

The owner asked, in order: the tail of the previous session's close, pasted
as the opening message; "is the token optimizing work done?"; "hand grant
ok'd to fix"; "no - you merge when green - then tell me about the matrix
issue"; "hand grant ok'd - Add matrix.py and the hooks test directory to
the wall paths".

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
  PR #180, five checks pass.

## What was decided and why

- **Ordinary grant, not wall class**: matrix.py is not in `WALL_PATHS` at
  `cb716534`, and the wall-write row refuses a wall grant that touches a
  non-wall path; the previous thrift commit `cc04f7d9` took the same path
  and named the gap. Closed by #180 at the owner's word.
- **Two grants for the wall extension**: the enforcing hook is the main
  checkout's matrix.py, whose list at `37750dd0` did not name matrix.py,
  so a wall grant (189) refused it as non-wall code and an ordinary grant
  (190) wrote it and its test; 189 wrote boundaries.json. LD-34 leaves
  the self-extension open: the next extension takes the same two grants.

## What went wrong

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
- Corpus: 111 pass, 0 fail, 0 unreachable, from the tree at `5a9e123e`.
