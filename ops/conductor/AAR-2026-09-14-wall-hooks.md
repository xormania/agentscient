# AAR — 2026-09-14, the wall hooks: T-5, T-11 and T-13

Session `lane/session-20260914-a`, Claude Fable 5.1, by hand under wall
grant 223 (the hook tests, engine, registry, matrix docstring, ci.yml)
and grant 224 (the SessionStart script, settings.json, the records).
Written at `95c83ef8`, the code head; every reading names its sha. The
handoff is rows in the state engine's store, not a file.

## The request, in the owner's words

After the board at onboard, the owner: "blanket hand grant ok'd - get
T5,11, and 13 don" (2026-09-14). The three threads were taken from the
store on this branch (`handoff.py take T-5`, `T-11`, `T-13`, each
`taken ... on lane/session-20260914-a`).

## What was done

| commit | grant | what |
|---|---|---|
| `5b015438` | 223 | the red: two engine tests and `test_trunk_forward.py` |
| `c197667d` | 223 | `engine.py`: a merge of `<remote>/<trunk>` that git reports as a fast-forward is not a trunk commit; the `file_state_store` predicate; the `file-state` row in the registry; the matrix docstring line |
| `3e030317` | 224 | `trunk-forward.py`, a SessionStart hook bound before the engine in `.claude/settings.json` |
| `95c83ef8` | 223 | `ci.yml`: actions/checkout 4.4.0 to 7.0.1, the two lines of #200 (`20729e00`), dependabot credited |
| `264745c0` | 224 | `trunk-forward.py`'s docstring reworded: the literals verb forbids the lane literal for the trunk |
| the records commit | 224 | this page; the `refused` and `state` skill pages; the README hooks line; LD-38's repair; seven corpus rows `P-WALLHOOKS-20260914-*` |

## Readings

- Red at `6e3de429` (the base): `python3 -m unittest discover -s
  ops/devlane/hooks/tests -p 'test_engine.py'`: Ran 18 tests, FAILED
  (failures=2), the trunk row refusing `git merge --ff-only origin/dev`
  and hook-error on the unknown predicate; `-p 'test_trunk_forward.py'`:
  Ran 10 tests, FAILED (failures=10), the script absent.
- Green with the same commands at `3e030317`: Ran 18 tests, OK; Ran 10
  tests, OK. `test_boundaries.py`: Ran 6 tests, OK. The whole hooks
  suite: Ran 303 tests, OK. `engine.py lint`: 6 engine rows, 11
  predicates, no unknown predicate or event. `ruff check` on the five
  Python files: clean.
- The wire by hand at `c197667d`, the branch's engine against the main
  checkout at `cccc810b`: a redirect to
  `~/.local/state/agentscient/claims.json` answered deny with
  `[engine:file-state]`; `git -C <main> merge --ff-only origin/dev`
  answered nothing (let through); `git -C <main> merge --no-ff
  origin/dev` answered deny with `[engine:trunk-commit]`.
- `trunk-forward.py` by hand at `3e030317` against this worktree:
  `trunk-forward: ... is on lane/session-20260914-a, not dev; not
  moved`, exit 0. Its first live run at a session start waits on the
  merge; not measured here.
- `ops/bin/suites.sh` at `95c83ef8`: dispatch 618, harness 155, task 351, telemetry 227, hooks 303,
  fixtures 221, workflow 51, pr-overview 8, all OK; conductor Ran 1180,
  FAILED (failures=2): `laneconf.py literals` on `trunk-forward.py`'s
  docstring naming the remote trunk by its lane literal, reworded in
  `264745c0`; and the tracked corpus's three count rows, re-pinned in
  the records commit. Exit 1. The re-run on the head is in the PR's
  ready note.
- Corpus: `probes.py run` at `95c83ef8`, before this session's rows:
  pass 194, fail 3, unreachable 0. The three fails are count rows this
  change moved on purpose, `P-BND-20260912-registry` (20 to 21 rows),
  `P-TRUNK-20260912-prose` (5 to 6 engine rows) and
  `P-ENG-20260912-vocab` (10 to 11 predicates), re-pinned in the
  records commit. The seven rows of this session and the re-run are
  read in the PR's ready note.

## Decisions

- **The exception is one ref.** Only a merge whose single operand is
  `<remote>/<trunk>` passes; a local branch that would fast-forward
  still refuses, because the row's point is that the trunk moves only
  by what landed on the remote (LD-38's own words).
- **`--ff-only` on a diverged trunk is let through.** Git refuses it
  itself and no commit can result; the row refuses what would create a
  commit, not what git will refuse anyway.
- **`file-state` escapes nothing.** The remedy is the engine, the
  agent's own; the placement pin `FILE_BACKED` with the owner's word is
  the only other way, and the row's needed half says so. `.log` is not
  a store suffix: the matrix itself writes `graft-first.log` under the
  state directory.
- **The SessionStart script is Python beside `engine.py`**, one line
  always, exit 0 always: a session start is never blocked, and a fetch
  that fails is said as could-not-look.
- **T-13 by hand, not a cherry-pick.** `cherry-pick --no-commit` reads
  as a write to `.`, which a wall grant may not cover, and an amend is
  denied; the two lines were applied by a script that spells the path,
  with dependabot in `Source:` and `Co-Authored-By:`. #200 stays open
  for the owner; whether Dependabot closes it once dev carries the
  version is not measured.

## What went wrong

- The first onboard brief measured the main checkout at `cccc810b`,
  14 commits behind `origin/dev` at `6e3de429`: T-11's cost, paid once
  more. The brief was re-taken from a detached worktree
  `../wt/ag-onboard-20260914` at `6e3de429`, which served the
  `== handoffs` section the stale tree could not.
- `claim-unmeasured` refused two commit messages: a body paragraph with
  "passes" and no reading, then a subject line with "passes". The hook
  denies the whole Bash call, so a chained `git add && git commit`
  staged nothing; both retries were scanned with
  `matrix.unmeasured_claim` first (pitfall 36).
- Five `clipped-sweep` refusals on alternation greps piped to `head`,
  one `stale-check-rollup` on `statusCheckRollup`; none wrong, one
  pattern per call after.
- `coverage-zones.md` names `test_ci_shape` for the CI shape zone;
  `find ops -name 'test_ci_shape*'` at `95c83ef8` found nothing. Not
  measured whether it lives elsewhere; #200's own checks ran to pass on
  the same two lines (run 34783304650).

## Calibration

- Tokens: not measured this session.
- Hook refusals: 8 (`clipped-sweep` 5, `claim-unmeasured` 2,
  `stale-check-rollup` 1), 0 wrong.
- Corpus at `95c83ef8`, before this session's rows: pass 194, fail 3
  (the three count rows above), unreachable 0.

## Second thread: T-8, T-9, T-14 and the T-4 reading

Owner, 2026-09-14, after #206 merged at `0afd70bb`: "merge when green -
keep moving". Grant 226 (other). The branch was fast-forwarded to
`0afd70bb` first; T-8, T-9, T-14 and T-4 taken from the store.

- **T-8, retire `== thread`**: `onboard.py` loses the section and its
  calibration reader; the brief ends at `== handoffs` and reads no
  `AAR-*.md`. Twelve assertions and two test classes in
  `test_onboard_lever.py` turned from pinning the clause to pinning its
  absence; `onboard-lever.md` carries the retirement paragraph in the
  section's place, the onboard skill's step 5 says the board is the
  hand-over, `handoff-lever.md` says the section is last.
- **T-9, one transaction per package**: `machine.move_many` moves a
  list, or the ids a callable chooses under the write lock, in one
  `BEGIN IMMEDIATE` at one stamp; `move`'s checks moved into
  `_move_locked` so both share them. `handoff.py take H-n` chooses the
  open threads and refuses another holder inside that transaction. The
  red read three stamps for three threads at `0afd70bb`; the green reads
  one.
- **T-14**: the close skill's step 2 waits with `watch.py pr <number>`,
  then `gh pr checks` as the reading.
- **T-4, the skill-use hook's first live rows**: `skill_events` rows
  with detail `(no arguments)` are the hook's (the hand command never
  writes that detail): the first is row 291 at 2026-09-14T01:17:24Z
  (`claim`), then 292 (`explain`), 298 (`close`); this session's own are
  304, 305, 306 at 23:11:45Z (`dev-lane`, `deliverable`, `handwrite`,
  the three Skill calls of its start). Twelve such rows at the reading.
  Every row carries the session as `unrecorded` and the agent as the
  lane's default identity, not `skill-use hook <...>`; a hand `log-use`
  beside a Skill call still double-counts (`onboard` rows 302 and 314).

Readings: red at `0afd70bb`, commit `43ac5963`: `test_onboard_lever.py`
Ran 34, FAILED (failures=8); `test_machine.py` Ran 31, FAILED
(errors=1); `test_handoff.py` Ran 34, FAILED (failures=1). Green at
`3d65ee8e` with the same commands: Ran 34 OK, Ran 31 OK, Ran 34 OK;
`ruff check` on the three tools clean; the live brief from the branch's
tree ends `== handoffs` then `brief complete`, exit 0.
`ops/bin/suites.sh` at `3d65ee8e`: dispatch 618, harness 155, task 351, telemetry 227, hooks 303, fixtures 221, workflow 51, conductor 1182, pr-overview 8, every one OK, exit 0. Corpus at
`3d65ee8e`: pass 205, fail 0, unreachable 0; the six `P-NEXT-20260914-*` rows are read
in the ready note.

Decisions: the AAR plants stay in the onboard fixture, so the tests
prove the retired section prints nothing from them rather than that
nothing was planted. `move_many` takes a callable so the choice and the
moves share one lock; a list form stays for callers that already hold
the ids. The `taken` refusal of a package take now fires inside the
transaction, as the contract's failure column already said.

What went wrong: the onboard skill's step numbering on the branch
differed from the main checkout's copy read at session start (the
checkout is 14 commits behind), so one page edit was placed by a second
script after the first asserted zero matches. Hook refusals in this
thread: `clipped-sweep` 3, 0 wrong.

## Third thread: T-19 and T-2 (LD-36)

After #208 merged at `f8acfa2f`, the owner's standing word ("keep
moving"); grant 228 (other). T-19 and T-2 taken from the store.

- **T-19, the zone row**: `find . -name '*ci_shape*'` at `f8acfa2f`
  finds nothing, and no `test_ci_contexts*` either; the workflow tests
  directory holds `test_ci_two_jobs.py` (20 tests) and `checks/` holds
  `ci_contexts.py`, referenced by neither `ci.yml` nor `suites.sh`. The
  CI shape row now names the pins that exist and the floor that runs;
  the gitea-ci row says its suite is absent on `dev`, a named gap.
- **T-2, LD-36**: `launch.py`'s guard read `args.stage`, which the
  wrapper never passes for a review job, so a review of the trunk tip
  launched with the prompt "Review the change at <ref> against <ref>"
  and an empty patch (the red's own reading at `f8acfa2f`). The guard
  now reads the derived stage, and a ref that sits on the trunk takes
  its base against `RELEASE_BRANCH`, so the release review diffs
  release...trunk. `_review_base` is the one merge-base reader for both
  anchors. No `--base` flag was added: the anchor rule needs no wrapper
  change, which was LD-36's second remedy.

Readings: red at `f8acfa2f`, commit `98532080`: `test_launch_u10b.py`
Ran 10, FAILED (failures=2), the third case a silent neighbour that
reads green at the base. Green at `b2e267d5` with the same command: Ran
10 OK; the whole dispatch suite: Ran 621 tests, OK; `ruff check` on
`launch.py` clean. `ops/bin/suites.sh` at `b2e267d5`: dispatch 621, harness 155, task 351, telemetry 227, hooks 303, fixtures 221, workflow 51, conductor 1182, pr-overview 8, every one OK, exit 0.
The six `P-TRUNKREV-20260914-*` rows are read in the ready note.

Decisions: the release anchor applies only when the trunk anchor is the
ref itself; a lineage that left the trunk keeps its trunk base (the
third red case pins it). With no release branch the base stays the ref
and the guard refuses, as before but now for a wrapper-dispatched job
too. Hook refusals in this thread: 0.

## Fourth thread: GitHub resolved, and the close

Owner, 2026-09-14/15: "by hand fastforward - i'm not doing it after this
time - i want github resolved"; then "aar and handoff". No grant beyond
233 for this page; nothing else was written.

- **The last by-hand fast-forward.** The main checkout read `3b9d2a11`
  on dev, 0 behind `origin/dev`, clean, carrying `trunk-forward.py` and
  its settings row. The hook run by hand against it: `trunk-forward: dev
  already at 3b9d2a11, the tip of origin/dev`, exit 0. `git -C <main>
  merge --ff-only origin/dev` through the live trunk row: `Already up to
  date`, exit 0. The chicken-and-egg is over: the hooks run from the
  checkout, the checkout carried the old hooks, and the old hooks refused
  the one merge that moves it; from `0afd70bb` on, every session start
  moves it and any session may run the merge itself. Later in the close
  the checkout read `f08d56c7`, 0 behind.
- **#200** read CLOSED after #206 carried the same two lines; T-18 done.
- **The CodeQL ghost, run 34748624693.** Every client lever was tried and
  refused: `gh run cancel` answers "completed", the force-cancel API 409
  "not been queued yet", DELETE 403, the jobs list empty, status queued
  since 2026-09-13T08:52:36Z. The owner toggled code scanning default
  setup off and on by hand (`PATCH .../code-scanning/default-setup`,
  `{}` then run 34913719378, which completed success); the ghost still
  reads queued and DELETE still 403. Harmless: #206, #208 and #209 merged
  past it, the required checks being lane and app. Thread T-26 to the
  owner supersedes T-12; the remedy left is GitHub support.
- **The handoff process, verified at the owner's word.** The law says
  no records PR trails the work in three places (`handoff-lever.md`
  §Where it sits, the close skill 6b, `ops/README.md`). Practice since
  #203, each PR's files read by `gh pr view --json files`: #204 and
  #205 records-only from before the rule took hold; #206, #208, #209
  (this session) and #207, #210 to #215, #217 (session -b) work with
  records; #216 (session -b, two files) the one records-only PR since.
  Named to session -b by message; acknowledged.

## Calibration

- Tokens (`worth.py waste --since 2026-09-14T22:50Z`): this session 49.2M cached, 206,838 out, mean context about 310k over 158 turns; session -b 162.6M cached, 572,429 out, 429 turns; the Grok review record 20260915T023743Z-review-grok-7da077 3.44M total; the Codex adjudication 20260915T025600Z-adjudicate-codex-68d3d9 1.76M total; 0 refusals counted by the meter (the hook refusals are in the skills store, not the meter).
- Hook refusals logged on this host since the session started, both
  sessions together because every row's session reads `unrecorded`
  (T-4): 52; clipped-sweep 24, claim-unmeasured 16, hand-write 4,
  graft-first 3, trunk-commit 2, stale-check-rollup 1, pr-proof 1,
  file-state 1. This session's own, from its transcript: clipped-sweep
  8, claim-unmeasured 4, stale-check-rollup 1, hand-write 1; 0 wrong.
- Corpus at the last head of this session's work, `be8731da`: pass 222,
  fail 0, unreachable 0; on `dev` after #209 the same rows are green in
  #209's ready note.
- PRs: three, #206 `0afd70bb`, #208 `f8acfa2f`, #209 `1bce40b6`, each
  merged on the proof gate at the owner's standing word. Threads closed:
  T-5, T-11, T-13, T-8, T-9, T-14, T-4, T-15, T-19, T-2, T-18; T-10 and
  T-12 superseded. Grants 223, 224, 226, 228 settled on bare shas; 233
  settles on this commit.
- Parallel session -b (test kit plan) ran throughout; file lists were
  exchanged three times, no hunk collided, and dev was merged forward
  once (`be8731da`) under #209.
