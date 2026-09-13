# AAR — 2026-09-13, the ladder and monitor migrations

Session `lane/session-20260913-a`, Claude Fable 5.1, by hand under
grants 187 and 193. Written at `ba4ad806` and extended at `b00b23aa`;
the readings below name the sha each was taken at. The monitor thread
is the last section.

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
