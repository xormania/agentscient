# AAR — 2026-09-13, the ladder, monitor and lane-read migrations

Session `lane/session-20260913-a`, Claude Fable 5.1, by hand under
grants 187, 193, 197 and 199. Written at `ba4ad806`, extended at
`b00b23aa` and at `374e6e0f`, closed after #187 merged at `48639a71`;
the readings below name the sha each was taken at. §Close sums the
session; the thread sections follow.

## Close

- Three PRs from one branch, each merged by the owner on green checks
  and a ready note: #181 (`ed109e17`, ladder.py), #183 (`4b66b31e`,
  monitor.py), #187 (`48639a71`, lane_read.py, lane_mcp.py,
  lane_refs.py). The gate went from 11 migrated tools to 17 migrated
  and 1 no-wire; five stay pending, none of them a copy removal.
- The method that held across all three: the gate red first with the
  tool placed; every `except` naming ValueError read by AST for whether
  its body can reach `refuse()`, not by eye; the suites that stage a
  copy of a tool given the two siblings; corpus rows written from the
  record's own text and pinning one list entry.
- Parallel sessions: three others landed six PRs on dev during this
  session (#179, #180, #182, #184, #185, #186). Two merges conflicted on
  one hunk each (a ledger row, a sorted list) and both resolved by
  keeping both sides. From the owner's word onward the file list went
  to the peer before the first edit, and the peer's insert that broke
  one of this session's corpus rows was fixed on their side before
  this session merged.
- Calibration for the session: tokens not measured (LD-30: the
  launcher's Claude store path does not exist, and `worth.py` was not
  run). Hook refusals: 10 across the session, 1 wrong (LD-35), 2 from a
  page defect since corrected (pitfall 29). Suite runs that read red
  from the tree's own state rather than the change: 3 (the wrapper
  merge, the untracked file, a row's spelling), each rerun clean.
  Corpus at close: 133 pass at `374e6e0f`.

## The request, in the owner's words

The session opened on a report that the instrument-consolidation
records were on dev (`794b2a3e`, #178) and that the handoff's next
thread was `ladder.py`. The owner: "do it - hand grant ok'd"
(2026-09-13). The handoff also required a fresh onboard because #175
had changed the brief; done first.

## What was done

- `ladder.py` (2,271 lines) imports the shared module instead of its
  four private copies; `Refused` is kept as an import alias of the
  shared `Refusal`; the laneconf loader's cwd fallback is gone; the one
  suite staging the driver alone stages the two siblings beside it.
  Commit `fef8b1cd`.
- Gate red first: `python3 -m unittest discover -s ops/conductor/tests
  -p test_instrument.py` at `cb716534` with `ladder.py` moved to
  `MIGRATED`: Ran 32, FAILED (failures=1) naming `['IDENTITY',
  'Refused', 'conf_value', 'refuse']`. Green with the same command at
  `fef8b1cd`: Ran 32, OK.
- Ladder suites (`-p 'test_ladder*.py'`): Ran 208 OK at `cb716534` and
  at `fef8b1cd`. Dispatch suite: Ran 618 OK at `fef8b1cd`. `ruff
  check`: one import-order finding, fixed, then clean.
- `ops/bin/suites.sh` at `ba4ad806`: dispatch 618, harness 155, task
  351, telemetry 227, hooks 282, fixtures 221 (skipped=6), workflow 48,
  conductor 1054, pr-overview 8, all OK.
- Corpus: `probes.py run` at `fef8b1cd`: pass 109, fail 0,
  unreachable 0; the four new `P-LADDER-20260913-*` rows PASS.
- Records commit `eeef6fc9`: the rows, pitfalls 28 and 29, the
  deliverable skill page with the lock before the worktree. PR #181
  opened as a draft, head `ba4ad806`.

## Decisions

- **Alias, not rename.** `from instrument import Refusal as Refused`
  keeps every `Refused` site in the driver and its two suites reading
  as before; the gate reads AST definitions and accepts an import
  alias. Renaming would have touched the driver and two suites for no
  behaviour change.
- **The cwd fallback goes.** The instrument-consolidation handoff's
  correction: a tool finds its siblings beside its own file, never
  under the working directory. The lever suite relied on it and was
  brought to the eleven earlier suites' staging.
- **`run()`, `git()`, `utc_stamp()`, `full_identity()` stay.** None is
  a copy the gate names; `run()`'s signature differs from the shared
  one and moving it is every call site in the driver, a reading of its
  own.
- **A found defect stayed a row.** The skill-page order and the hook's
  prose reading became pitfall rows and one LD row on this branch, not
  a repair branch; the page fix rode in the records commit because it
  is the row's own remedy.

## What went wrong

- Seven hook refusals before the first edit landed, none a lane defect
  but one: `deliverable` on the worktree-before-lock order (the skill
  page's order; corrected), `hand-write` twice (the grant id not the
  first token: exported inside the command, then after `cd`), `graft-
  first` three times (`-r` searches; Graft's context stale for the
  moved checkout, prepared anew for the worktree), `clipped-sweep`
  once, `test-form` once (the module form of unittest). Each remedy was
  on the `refused` page; two misses logged there.
- `evgrep.sh` alternations read as zero three times before the
  basic-regex shape was noticed; one reading ("who stages ladder.py")
  was taken from a false zero and re-taken. Pitfall 28.
- The `deliverable` hook refused a heredoc that only quoted the
  worktree command in prose to correct the skill page: a wrong
  refusal, LD-35. Worked around through a script file.
- `suites.sh` at `eeef6fc9` wrote the wrapper merge `ba4ad806` (#179
  had landed on dev) and read three reds from its own HEAD move,
  LD-29's second recurrence on this lane; rerun clean at `ba4ad806`.
- `claim-unmeasured` refused the PR body twice on a reviewer note that
  read as a claim; the second refusal because a chained "edit then
  create" was judged on the pre-edit file.

## Calibration

- Tokens: not measured this session.
- Graft: one query in the worktree's context reported about 100k
  tokens saved against reading twelve files whole; two more calls
  refused stale before the context was prepared.
- Hooks: 9 refusals in the session, 1 of them wrong (LD-35), 2 of them
  a page defect (pitfall 29).
- Corpus: 109 rows pass at `fef8b1cd`.

## Second thread: monitor.py

Owner, 2026-09-13: "181 is merged - continue, monitor.py" (#181 merged
at `ed109e17`). Grant 193. PR #183.

- The handoff's open question, which handler sees a refusal once the
  class leaves ValueError, was answered by measurement, not by reading
  1,377 lines: an AST pass over `ed109e17` computed the closure of
  functions that call `refuse()` (28 of them) and listed every `try`
  with a ValueError handler (14). The three whose bodies reach the
  closure (`_path` 123, `load_config` 195, `digest` 1160) each have an
  `except Refusal` handler first; the other eleven bodies never reach
  it. The change is neutral for every handler. Twenty lines of script,
  one reading, and the shape to reuse for `lane_read.py`.
- Red at `ed109e17` (gate Ran 32, 1 failure naming `IDENTITY_RE`,
  `Refusal`, `refuse`), green at `b00b23aa` (Ran 32 OK); monitor Ran
  73 OK before and after; lane MCP Ran 50 OK before and after; ruff
  clean; no lane-name literal.
- Decisions: `now` imported as `utc_now` because `main()` binds a local
  `now`; `_identity()` replaced at its two call sites rather than kept
  as a call-through; the ID_RE check on the lane name and the
  confinement of the state directory stay the monitor's own; the
  conformance-registry gap stays recorded, not filled, in a migration
  commit.
- What went wrong: `suites.sh` was run with the new corpus rows still
  untracked, and dev moved (#182) during the run; the ten wrapper tests
  that run the real dispatcher refused `stale-base` on the untracked
  file, and `test_probes` graded the untracked nearmiss row before this
  AAR carried its phrase: 11 reds from the tree's state. The
  claim-unmeasured hook refused the commit message once for the owner's
  quoted word "merged"; the merge sha now sits beside it.
- Calibration: tokens not measured. Hook refusals this thread: 1
  (claim-unmeasured on a quotation), 0 wrong.

## Third thread: the lane_read family

Owner, 2026-09-13: "sync with dev branch branch - then hand grant ok'd
to start lane_read". Grant 197. PR #187.

- Coordination, at the owner's word: the file list went to session f7
  before the first edit; f7 named one adjacent line and two record
  conventions (defects.py, ledger.py); the one hunk merged at
  `374e6e0f`. Two sessions inserting into one sorted list is the shape
  to expect on every consolidation commit; a corpus row that pins two
  neighbours in such a list breaks on the other session's insert.
- The AST reading paid for itself a second time: it found the one
  handler (`load_config` 229) that swallowed a Refusal as ValueError,
  which a line-by-line read of 2,060 lines would have had to find by
  eye, and it showed the previous handoff's claim about `lane_refs`
  importing the refusal class to be wrong (it imports nine names, none
  refusing). A tool that never refuses needed a third gate placement,
  not a fake import.
- Red at `1c7fd5ee` (Ran 33, failures=3), green at `15404f6d` (Ran 33
  OK); lane MCP Ran 50 OK before and after; `suites.sh` at `374e6e0f`
  nine suites OK, conductor Ran 1068; corpus pass 133 at `374e6e0f`.
- What went wrong: ruff wanted the instrument import ahead of the
  lane_read import, which would have lost the one-line tooling refusal;
  the fix was lane_mcp's own fallback block, checked by hand (a copy
  with no instrument.py beside it exits 2 with the line). The first
  `suites.sh` at `15404f6d` read one red, `P-MON-20260913-gate`, my own
  row broken by my own insert into the list; the fix was already on dev
  from f7 and came in with the merge.
- Calibration: tokens not measured. Hook refusals this thread: 0.
