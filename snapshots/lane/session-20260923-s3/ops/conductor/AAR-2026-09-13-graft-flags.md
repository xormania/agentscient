# AAR — 2026-09-13, the token question; LD-33, LD-34; the ledgers' shape; the dispatcher tests' tree

Session record by Claude Fable 5.1, closed at the owner's word ("AAR and
handoff - good job"). Eight branches cut from dev, all merged: `-b` (#179
`37750dd0`), `-c` (#180 `23a30592`, #182 `e7e0d41e`), `-d` (#184
`39cf7d81`), `-e` (#185 `1c7fd5ee`), `-f` (#186 `d8eec5c7`), `-g` (#188
`c2d7347f`), `-h` (#190 `c7245c6c`), and `-j` for this close. Measured at
close, dev `c7245c6c`: no open PR; grants 188 to 200 settled (185 too,
the previous session's); the lock names `-i` (the new session's) and
`-j`; every worktree of this session merged, pushed and clean, one
test leftover (`untracked.txt` in `-e`, from the red run of the fixture
test) removed at close. The
[handoff](handoff/HANDOFF-2026-09-13-graft-flags.md) carries what stays
open.

## Request and outcome

The owner asked, in order: the tail of the previous session's close, pasted
as the opening message; "is the token optimizing work done?"; "hand grant
ok'd to fix"; "no - you merge when green - then tell me about the matrix
issue"; "hand grant ok'd - Add matrix.py and the hooks test directory to
the wall paths"; "hand grant ok'd close the open thing, in LD-34"; "re: other
session #181 - is that an issue? should we fix it?"; "can you communicate with
other claude session - verify that its not fixing those issues first. If its
not, hand grant - fix issue #1 - PR and merge, then issue #2 - PR and merge";
"hand grant ok'd fix the pitfalls page - in fact anything similar - fix it -
agents need to work in parallel"; "So are the issues sorted out for parallel
work?"; "i'd get minimize parallel work conflicts - hand grant ok'd for
fixing"; "make sure to co-ordinate with other session to de-conflict";
"other session lifecycle done - new session took over handoff - co-ordinate
to de-conflict - give it a minute to onboard properly"; "AAR and handoff -
good job".

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
- **Issue 2, the CI signal** (#185, merged `1c7fd5ee`): the dispatcher wrapper tests
  dispatched against the live checkout, so a branch behind or conflicting
  with dev failed a dozen of them with stale-base (#175, #182). The fixture
  builds a scratch repository with no origin ref. Red 1 of 2 then 2 OK;
  the four wrapper suites 100 OK; suites.sh 2972 tests, exit 0.
- **Anything similar** (`-f`, `725109a5`): measured since 2026-09-11, only
  the pitfalls page shared the appended-table shape (4 commits, one
  conflict); ideas are one file each, the other ledgers SQLite. ledger.py
  names each ledger as data (defects, pitfalls); defects.py is a shim over
  it; pitfalls from row 30 are files. Red 5 then 5 OK; test_defects 6 OK
  through the shim; conventions 18 OK; consolidation 32 OK; corpus 128
  pass. Pitfall 30 is the first row through the lever. #186 merged `d8eec5c7`.
- **Parallel conflicts, the four standing items** (answered at `d8eec5c7`):
  the lock only grows (LD-28); sorted placement lists in the consolidation
  gate; the same ledger id minted twice; corpus rows pinning neighbours.
  On `-g` (`5975dabe`): `deliverable.py remove` (red 1 then OK, lever suite
  6 OK; LD-28 closed) and ledger.py minting past origin/<trunk> after a
  bounded fetch (red '30' != '31' then OK; test_ledger 6 OK). suites.sh
  2979 tests, exit 0; corpus 131 pass. The placement lists are the other
  session's file in flight: agentscient-5e chose to land #187 first and
  leave the move to registry files to this session after it. The
  neighbour-pinning class is practice (pitfall 30); a corpus-shape rule in
  probes.py is a wall change, not done. #188 merged `c2d7347f`; the lock
  lifted of seven landed branches by the new verb.
- **The placement lists** (`-h`, `32710253`, after agentscient-5e's #187
  landed at `48639a71` by its choice): each tool declares migrated, pending
  or no-wire in `ops/conductor/placement/<tool>.py.json`, 23 files written
  from the tuples at `c2d7347f`; the gate reads the directory and closes
  it both ways. Red 2 of 34 then 34 OK; three of the other session's
  corpus rows moved from the tuples to the files, told; suites.sh 2981
  tests, exit 0; corpus 139 pass, exit 0 read from the process.
  #190 merged `c7245c6c`; the lock lifted of `-h` by the remove verb.
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

- **Two commit messages on `-h` overclaimed a corpus reading** (`466b8792`,
  `ae1ad1b9`): the run and the commit sat in one command, so the message
  was written before the output existed; the first run had been refused
  (cat is not an allowlisted read), the second printed 3 fails. Corrected
  at `32710253`; pitfall 31, the run in one command and the commit in the
  next.
- **Two ruff rounds on #184**: suites.sh on the host runs no ruff, so the
  local run at `f6494db0` could not see six findings the lane job found;
  the first fix commit `d814a547` said ruff passed with one finding left,
  read from a piped ruff whose exit I printed and did not act on; corrected
  at `d0bbd3c4`.
- **#182's lane job failed on the very defect it was recording**: #181 had
  landed LD-35 in the same table; resolved by merging dev forward at
  `47c3a540`.
- **A neighbour's corpus row broke on my insert**: suites.sh at `67643ad0`
  had one red, session -a's P-MON-20260913-gate pinning two entries of the
  sorted MIGRATED list as adjacent; ledger.py landed between them. Narrowed
  to membership at `725109a5`, the other session told; my own P-LEDGER row
  had pinned a moving count the same way and was pinned to row 30.
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

- This session, `worth.py waste` at 07:34Z over the window from 05:00Z:
  49.1M tokens, 196,647 out, 247 turns, mean context 198k; hook refusals
  counted by the report: 0 (the report does not see them; this record
  counts 3 graft-first, 5 clipped-sweep, 1 deliverable, 1 hand-write,
  3 claim-unmeasured, 1 stale push, 2 wall-write readings taken on
  purpose). Against the three sessions before the thrift change at 200.6M,
  45.7M and 14.9M with mean context 465k, 309k, 243k: one session, eight
  PRs, under a quarter of the largest, at under half its mean context.
- `worth.py waste` for this session at 05:31Z: 590,764 tokens, 11 turns,
  mean context 53k; at write time unmetered, roughly 30 turns.
- Corpus: 108 pass, 0 fail, 0 unreachable, from the tree at `2c983635`.
- Corpus: 111 pass, 0 fail, 0 unreachable, from the tree at `5a9e123e`;
  112 at the close, run from the tree at `23a30592` plus the closing row.
- Corpus: 119 pass at `f6494db0`; suites.sh on `-e` at `7d7e3714`: 2972
  tests, exit 0; ruff over ops/conductor: all checks passed.
- suites.sh on `-h` at `32710253`: 2981 tests, exit 0; corpus 139 pass.
- suites.sh on `-g` at `5975dabe`: 2979 tests, exit 0; corpus 131 pass.
- suites.sh on `-f` at `67643ad0`: 2977 tests, one red (the corpus row
  above); corpus 128 pass and test_probes 22 OK at `725109a5`; the whole
  suite not re-run on the host after that commit, CI is the reading.
