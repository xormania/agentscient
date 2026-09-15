# AAR — 2026-09-14, the test kit plan landed: slices 3 to 21 by hand

Record by Claude Fable 5.1 on `lane/session-20260914-b`, the second
half of the session whose first half is
`AAR-2026-09-14-testkit-reading.md` (T-1, slices 1 and 2, #207). Grants
229 (wall) and 230 (other), both at the owner's word; the second
producer is absent on every commit and every commit says so.

## The request, in the owner's words

- "what are you waiting for? why won't you get it done? hand grant
  ok'd. You do the pr's, merge the, i don't want to talk to you until
  its all done"
- earlier the same evening, on the wall rule the plan follows: "hand
  grant ok's - do all right now"; and, asked whether the tests were
  rewritten after #207: this record is the answer.

The wall rule (owner, 2026-09-12: the wall is changed only in a session
whose deliverable is the wall) was raised once and the owner reaffirmed
the order; this session then held both grant classes and led every
write with the one its path takes, `matrix.wall_write` refusing the
other. That is the isolation the hooks give; the session-level
isolation the ruling asks for was set aside by the owner for this run,
said here.

## What was done

- #207 MERGED `4c47b5b6`: docs: the test contract, slice 1 and 2 of the test kit plan, the reading of T-1
- #210 MERGED `ebd8f82e`: hooks: the test kit and the job catalogue are wall paths, the tenth suite (slices 3 and 4)
- #211 MERGED `3b9d2a11`: testkit: the kit, slices 5 to 7: World, run, Tools and the case pattern
- #212 MERGED `79020093`: tests: the ladder family onto the kit, four tables, seven files retired on the record (slices 8 to 14)
- #213 MERGED `8e7679f9`: tests: the ladder refusal and stop tables calibrated, the rest of the retirement (slices 11, 13, 15)
- #214 MERGED `5e849908`: hooks, workflow: the kit-import row and the census ratchet, the enforced path (slices 16 and 17)
- #215 MERGED `3924b8ee`: task, dispatch, hooks, records: the prompts name the kit, the hooks family rides on it, the leverage measured (slices 18 to 21)

- **Slices 3 and 4** (#210): `ops/testkit/` and `jobs.json` are wall
  paths; the tenth suite in `suites.sh`; the kit's ruff rows.
- **Slices 5 to 7** (#211): the kit at `ops/testkit/`: `World`, `run`,
  `Tools`, `fake_program`, `cases` with `calibrate` and `sidebyside`;
  its own suite of 30, four planted faults each turning its named test
  red before landing.
- **Slices 8, 9, 10, 12, 14** (#212): the ladder family onto the kit:
  five programs to files, the fixture on `World`/`run`/`Tools`, the
  guard as adapter over `compare`, four pure tables (39 rows), six
  faults as data, seven regression files retired on the side-by-side
  record (every fault caught by old caught by new).
- **Slices 11, 13, 15** (#213): the refusal table (22 rows) and the
  stop tables (13 rows), calibrated (13 faults, none quiet); the
  archive copy became a repository; the stub's inherited stdin no
  longer hangs; `RefusalsBeforeLaunch`, `DerivedCommand` and the LD-23
  file retired on the record.
- **Slices 16 and 17** (#214): the `kit-import` row and its predicate
  (a new test module imports the kit or declares its exemption; no
  grant lifts it); T-20's duplicate `TRUNK_WRITES` line gone; the
  census ratchet and its CI step, baseline written by the verb.
- **Slices 18 to 21** (#215): the tests job's and the skeptic's
  prompts name the kit and `calibrate`; the what-exists brief names the
  kit's invariants; the role card's item 7; the hooks tests' support
  and gh stub on the kit (two families share the primitives); the
  leverage measured and recorded, I-029 the home for any package
  proposal, none made.

## Readings at close

- Branch `3924b8ee`, `origin/dev` `3924b8ee`; unpushed 0 (`git log origin/dev..HEAD`); uncommitted 0 before this record was written, this record and its rows after.
- Full suite at `1260a912`: == ruff All checks passed! == devlane/dispatch Ran 621 tests in 80.610s OK == devlane/harness Ran 155 tests in 6.389s OK == devlane/task Ran 356 tests in 11.977s OK == devlane/telemetry Ran 227 tests in 51.971s OK == devlane/hooks Ran 304 tests in 64.313s OK == devlane/fixtures Ran 221 tests in 37.194s OK (skipped=6) == devlane/workflow Ran 60 tests in 1.316s OK == testkit Ran 30 tests in 8.152s OK == conductor Ran 1166 tests in 159.737s OK == pr-overview Ran 8 tests in 0.875s OK suites exit=0
- Corpus: 3924b8ee {'pass': 247, 'fail': 0, 'unreachable': 0}
- The ratchet: ratchet holds: home_by_hand=57, embedded_programs=30, run_without_timeout=179
- Findings: 20260913T023636Z-review-codex-bdbe55|fixed|1; 20260913T023636Z-review-codex-bdbe55|ruled|6; 20260913T034513Z-plan-claude-892490|deferred|3; 20260913T034513Z-plan-claude-892490|fixed|1; 20260913T034513Z-plan-claude-892490|ruled|2
- Grants: 229 wall the test kit plan slices 3 to 21, wall paths: matrix.py, boundaries.json, engine.py, ops/devlane/hooks/tests/, ops/bin/suites.sh, .github/workflows/ci.yml, ops/testkit/ and ops/devlane/task/jobs.json once slice 3 names them age=6636s ttl=28800s within ttl; 230 other the test kit plan slices 3 to 21, every non-wall path: ruff.toml, the ladder family tests, launch.py, the checks, records and corpus rows, PRs and merges on proof age=6636s ttl=28800s within ttl
- Lock: `lane/session-20260914-b` alone (`deliverable.py show`); removed once this record is on dev.
- Threads held on the branch: none held

## Decisions

- **One producer, said in every commit.** The owner's hand-grant
  doctrine covers dev-lane changes by hand; the kit's tests and code
  share an author here against docs/tests.md rule 8, and the
  planted-fault readings (the kit's four, the ladder's nineteen) stand
  in for the second eye. A second producer's review of the kit is
  open work, not a claim.
- **`_reap` vs kill-then-communicate, `_completed()`, `hermetic_env`
  functions, `TESTKIT_DIR`, TMPDIR only when it exists**: each measured
  first, in its commit body.
- **The archive copy is a repository.** The fixture-driven tables read
  HEAD; a plain extraction has none. Measured red, then fixed in the
  kit.
- **Count rows move with the count.** Three registry count rows and one
  fixture-text row were re-anchored in the commits that moved them;
  each says so.
- **What stays, named:** ResumeDigests and the four duplicate suites
  (slice 15); 57 modules setting HOME by hand under the ratchet; no
  package (I-029).

## What went wrong

- Commit 1583bbeb carried only a deletion: its `git add` sat in a
  chain a hook refused; 20338ee7 carried the files and says so.
- Twelve claim-unmeasured refusals on commit and PR bodies, each a
  reading added or a word dropped; three refusals of scratch edit
  scripts (paths built at run time) and four clipped-sweep refusals on
  multi-pattern greps.
- The sixty-concurrent-calls test stalled three times (61 s, 307 s,
  307 s) before the cause was found: the planted program read an
  inherited stdin nobody closed. Fixed in the kit with `select`.
- The three verb records read clean red once (no HEAD in the archive)
  and were regenerated after the kit fix.
- The main checkout's hooks ran from a checkout 44 commits behind
  until `trunk-forward.py` was run by hand against it (T-11's option 1,
  from session -a's #206), and after each merge since.

## Calibration

- Tokens: not measured this session.
- Hook refusals this half: claim-unmeasured 12, hand-write 3,
  clipped-sweep 4, trunk-commit 1 (the ff of the main checkout, replaced
  by trunk-forward.py); 0 wrong.
- Corpus rows written this half: 30, all PASS at close.

## Handoff

H-6 in the store: the kept duplicates' retirement, the other families
onto the kit under the ratchet, the record-digest fault, the first live
readings of the enforced path. H-5's T-23, T-24, T-25 stay open as
written. Grants 229 and 230 settled with the last merge sha; the lock
entry removed once #215 and this record are on dev.
