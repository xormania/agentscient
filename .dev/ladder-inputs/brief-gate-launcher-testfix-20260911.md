# Brief: one wrong assertion in the frozen test set (slice 4, launcher gate)

Ladder 20260911T040533Z-ladder-fd103b stopped at its code stage: record
20260911T045555Z-code-codex-532808 (implement, gpt-5.6-sol) reported its
envelope `invalid` with one p1 against the tests, not the code. Its
implementation is landed on this branch (7478d31). The frozen test set is
the acceptance criterion; a review of tests may reject an assertion as
wrong but may not add cases (scope-discipline clause, item 4).

## The finding (record 532808, p1)

`test_launch_correction_gate.CorrectionShape.test_out_input_under_a_review_job_is_a_correction`
plants `jobs_root/<rec_id>/out/note.md` for each of the five review jobs,
dispatches a write job with `--input` naming that file, and then calls
`assert_no_mint()`, whose second assertion is `job_dirs() == []`. The
directory the fixture itself planted makes that assertion unsatisfiable;
the gate refuses correctly (wire line `correction`, exit 2, no record,
no child started) and the five subtests still fail. Measured on 7478d31:
`FAILED (failures=5)`, all five on that one assertion.

The test verifies contract item 1 of `.dev/ladder-inputs/scope-gate-20260910.md`
(inputs from a review record's `out/` make a correction) and its no-mint
check is item 3 (no record minted). Both hold in the implementation.

## The change

Edit `ops/devlane/dispatch/tests/test_launch_correction_gate.py` (and its
support module only if the helper lives there) so the no-mint check
ignores directories the fixture planted before the dispatch, the way
`minted_record_files` already ignores `planted_ids`: for example, record
the job directories present before the dispatch and assert the set is
unchanged, or track planted job ids alongside planted record ids. Keep
every other assertion; add no cases; do not touch `launch.py`,
`record.py` or `correction.py`.

Prove red first (the current assertion fails on this tree: run the frozen
command before editing and quote the failure count), then green, commit,
list the file in `artifacts`. Frozen command:
`python3 -m unittest discover -s ops/devlane/dispatch/tests -p test_record_answers.py && python3 -m unittest discover -s ops/devlane/dispatch/tests -p test_launch_correction_gate.py`

## First-run walkthrough
- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home — measured by the dispatch suites.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
