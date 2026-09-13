# AAR — 2026-09-13, the wall migration: laneconf.py and probes.py

Session `lane/session-20260913-i`, Claude Fable 5.1, by hand under
wall grant 201 (the two files) and grant 202 (the placement files and
the records). Written at `2e7dec62`; the readings below name the
sha each was taken at. The handoff is
`handoff/HANDOFF-2026-09-13-wall-migration.md`.

## The request, in the owner's words

The session onboarded from `HANDOFF-2026-09-13-ladder-migration.md`
(owner: "onboard from HANDOFF-2026-09-13-ladder-migration.md";
`onboard.py` at dev `c2d7347f`: brief complete, exit 0, no absences).
That handoff's next thread named two wall files for a wall session and
three older tools for the owner's ruling. The owner: "hand grant to
continue two wall files - and i want a plain english simple summary of
the 3 older tools" (2026-09-13). The summary went to the owner in the
session; its substance is in the handoff's next thread.

## What was done

- `laneconf.py` imports `Refusal` and `emit` from the shared module.
  `ConfigError` stays under its name as a subclass of `Refusal`, because
  seven consumers catch it by that name (`fixture.sh`, `graft.py`,
  `launch.py`, `worth.py`, `probe.py`, `pr_overview.py`, and
  `instrument.py`'s own `conf()`), and two of them, `launch.py` line 103
  and `worth.py` line 840, call `line(kind)` to project the refusal under
  their own token; that override is kept and builds its line through
  `Refusal`, so the format string lives in `instrument.py` alone.
  `main()` emits through the shared `emit()`. Commit `dee2b4c9`.
- `probes.py` drops its own `refuse()` (write to stderr, `sys.exit(2)`)
  for the shared raising one and catches `Refusal` at `main()`. Its four
  `except ValueError` handlers (`json.loads` at two sites, `shlex.split`,
  `float()` on `PROBES_TIMEOUT`) wrap calls that never refuse, so no
  handler sees a refusal it did not see before. Same commit.
- Both carry the tooling fallback every migrated tool has.
- The placement files for both moved from `pending` to `migrated`,
  commit `15bea6a3`, under grant 202: the placement directory is not a
  wall path and a wall grant may not write a non-wall code path.
- Corpus rows `P-WALL-20260913-*` (six) in
  `probes-2026-09-13-wall-migration.jsonl`, each pinning one line or one
  file; the records commit.

## Readings

- Gate red first, the placement files flipped ahead of the code:
  `python3 -m unittest discover -s ops/conductor/tests -p
  test_instrument.py` at `c7245c6c`: Ran 34, FAILED (failures=2),
  `laneconf.py does not import instrument` and `['refuse'] != []` for
  `probes.py`. Green with the same command at `dee2b4c9`: Ran 34 OK.
- Before and after, same commands: `test_laneconf.py` Ran 83 OK;
  `test_probes.py` Ran 22 OK; `test_instrument_conventions.py` Ran 18
  OK; dispatch `test_launch*.py` Ran 444 OK; telemetry `test_worth*.py`
  Ran 68 OK; hooks `test_matrix.py` Ran 70 OK; harness Ran 155 OK.
  `ruff check` on the two files: clean.
- The wire by hand at `dee2b4c9`: `probes.py dance` exits 2 with one
  `arguments:` line; `laneconf.py get LANE_NAME` with `LANE_CONF` naming
  an absent file exits 2 with `conf-file:`; `get NO_SUCH_KEY` exits 2
  with `key:`; `get LANE_NAME` prints the lane and exits 0.
  `ConfigError('key', 'a  b', 'c', 'd').line('conf-key')` reads
  `conf-key: expected a b; found c; needed d`.
- `ops/bin/suites.sh` at `15bea6a3`: dispatch 618, harness 155, task 351, telemetry 227, hooks 282, workflow 48, conductor 1071, pr-overview 8, all OK; fixtures Ran 221, FAILED (failures=4, skipped=6), the four app tests whose scratch copy list carried `laneconf.py` without `instrument.py` (§What went wrong); fixed in `a9b79257`, fixtures app suites Ran 132 OK (skipped=6) on that tree. The full set re-run on the records commit is in the PR's ready note.
- Corpus: `probes.py run` at `2e7dec62`: pass 145, fail 0, unreachable 0; the six `P-WALL-20260913-*` rows of this session PASS.

## Decisions

- **The class name stays; the format string goes.** Renaming
  `ConfigError` would have touched six non-wall files, which a wall
  session may not write, for no behaviour change. A subclass keeps
  every `except laneconf.ConfigError` and both `line(kind)` calls
  reading as before.
- **Stated wire difference.** `Refusal` collapses runs of whitespace in
  every field; `ConfigError` did not. No test pinned a multi-space
  refusal, and no consumer builds one.
- **`_repo_root()` and `probes.py`'s git call stay their own.** Neither
  is a copy the gate names; the shared `git()` would change the wire on
  a missing git in an untested corner. Not this session's deliverable.
- **Two commits, two grants.** The placement directory is not a wall
  path; the flip went under grant 202 after the code, so the gate was
  never red between commits.
- **Two wall items from session -h stay open, unassigned.** The
  corpus-shape rule against an `expect` spanning lines, and the hook's
  deliverable remedy still saying `clear` in `matrix.py`: both wall
  writes, neither the owner's word this session.

## What went wrong

- The handoff was named without its directory; it lives under
  `ops/conductor/handoff/`. Found by `find`, a one-line cost.
- Hook refusals: `graft-first` twice (a `-rn` alternation across `ops/`;
  the remedy is a per-file `grep -c` then `grep -n`), `clipped-sweep`
  four times (an alternation into `head`; count first), `hand-write`
  twice on `cd <wt> && HAND_GRANT=202 git checkout` (pitfall 27: the
  grant id is the first token of the whole command; `git -C <wt>` with
  the id leading passed). None wrong; nothing new for the pitfalls
  ledger.
- `suites.sh` at `15bea6a3` read four reds in `devlane/fixtures`: the
  four app fixture tests plant a copy list for a scratch repository that
  carried `laneconf.py` alone, and a `laneconf.py` with no
  `instrument.py` beside it now refuses `tooling`, so the scratch
  `dispatch.sh --dry-run` exited 3. The lists name `instrument.py` ahead
  of `laneconf.py` since `a9b79257` (grant 202: the tests are not a wall
  path, and the fix is the wall change's own remedy). The staging rule
  was written for suites that copy a tool; the fixture lists are a
  fourth kind of copier and were not read before the change.
- The gate was first flipped in its tuple form at `a93379ca`; #190
  landed the placement files mid-session (`c7245c6c`), so the edit was
  discarded, the branch fast-forwarded, and the red re-taken in the
  placement form. The peer had named the change before it landed.

## Calibration

- Tokens: not measured this session.
- Hook refusals: 8 (`graft-first` 2, `clipped-sweep` 4, `hand-write` 2), 0 wrong.
- Corpus at the records commit: pass 145, fail 0, unreachable 0; the six `P-WALL-20260913-*` rows of this session PASS.

## Second thread: the skills registry and four items against the friction

Owner, 2026-09-13, after #192 merged at `eaf73b98`: "let's look at the
skill registry - are the being used? are there any possible new skills
to smooth the friction?", then "hand grant ok'd for new skills #1-4 -
do them in one PR". Grants 208 (pages, hook, settings, records) and
209 (the hook's test, a wall path). Same branch, fast-forwarded to
`eaf73b98` first; a second branch named in the lock while #192 was
open was removed once it merged.

- The reading that decided the four: `skills.py report` and the
  `skill_events` table at 08:1xZ: 170 misses, 156 of them guard
  refusals against `refused`, 21, 55 and 94 per day over three days;
  graft-first 45, hand-write 28, clipped-sweep 18, claim-unmeasured 18,
  trunk-commit 9; 31 of the 45 graft-first rows were `grep` over a
  directory; every row carried one agent and the session id unknown.
  Uses were hand-logged only: 12 close, 7 deliverable, 6 dev-lane, 6
  onboard, zero for thirteen skills, and no hook on the Skill tool
  (`.claude/settings.json` matchers: Bash, Write/Edit, Agent, compact).
- `search`, `handwrite`, `claim`: one page per refusal class, the shape
  that keeps the guard quiet, each opening with the count that demanded
  it and closing with the worked shapes from the refusal log. Commit
  `85dfe597`.
- `skill-use.py`: PreToolUse on the Skill tool, the shape of `miss.py`;
  logs `invoked` with the arguments as the detail; always allows;
  signs as itself with the lane's name when no `WF_AGENT` is inherited.
  Bound by one settings row with matcher `Skill`. The skills page
  sentence that said "until wired, log by hand" now says what the hook
  does. Same commit.
- Red first: `python3 -m unittest discover -s ops/devlane/hooks/tests
  -p test_skill_use.py` at `eaf73b98` with the test staged: Ran 8,
  seven on the absent hook, one on the missing settings row (commit
  `21d50dc8`, grant 209). Green, same command, at `85dfe597`: Ran 8
  OK. Whole hooks suite Ran 290 OK. `ruff check` on the hook and the
  test: clean. `skills.py sync`: 26 on disk, 27 rows.
- Corpus: `probes.py run` at `85dfe597`: pass 152, fail 0, unreachable 0; the six `P-SKILLS-20260913-*` rows PASS.
- `ops/bin/suites.sh` at `85dfe597`: dispatch 618, harness 155, task 351, telemetry 227, hooks 290, fixtures 221 (skipped=6), workflow 48, conductor 1071, pr-overview 8, all OK, exit 0.
- Not measured: the hook consumed by a live session. This session runs
  from the main checkout on dev, where the settings row does not exist
  until the merge; the first live `invoked` row written by the hook,
  not by hand, is the reading the next session takes and names.

### Decisions

- **Pages before levers.** Each of the three pages is the accepted
  spelling the `refused` page already names, moved ahead of the
  refusal; a lever that rewrites commands was not asked for and would
  hide the shape from the session. If the miss counts do not fall in
  the next window, the lever is the next step, measured.
- **One event, two writers.** The hook writes the same `invoked` event
  the hand command writes, so `report` needs no new column; a hand log
  after a hook log double-counts, and the skills page now says when
  to log by hand.
- **Two commits, two grants, test first.** The test is a wall path; the
  hook, the row and the pages are not. The red commit precedes the
  green one in history.
