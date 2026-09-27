# Brief: regression tests for LD-17 from another harness

LD-17 (row in `ops/conductor/handoff/lane-defects.md`; the sentence in
`ops/conductor/ladder-lever.md`: "A stage is waited for its job's cap from
`ops/devlane/task/jobs.json` (the record copy's own cap when it already
carries one) plus `LADDER_WAIT_GRACE`; `WALL_DEFAULT` applies only when
neither names a cap") landed by hand in PR 117 with the repairer's own test
`ops/conductor/tests/test_ladder_wall.py`. The lane rule asks a second
producer for the regression test. Write
`ops/conductor/tests/test_ladder_wall_from_job_cap.py` from the lever
sentence only; do not read or copy the repairer's test, and do not edit
the driver.

The subject is `Driver.stage_wall(stage, launched)` in
`ops/conductor/tools/ladder.py`, callable on a stub carrying `worktree`
(a `Path` to a temporary tree holding `ops/devlane/task/jobs.json`); load
the module with `importlib` and register it in `sys.modules` before
executing, as its dataclasses need. The stage-to-job table is
`DISPATCH_STAGES` in the same module. Cover:
- a record copy carrying `caps.timeout` wins, whatever jobs.json says;
- a record copy without a cap (the launcher fills it only at close)
  yields the stage's job cap read from the tree's jobs.json, for a
  dispatch stage of each role (a tests stage and a review stage);
- a stage absent from the table yields None (WALL_DEFAULT applies);
- a missing or unparseable jobs.json yields None, never an exception;
- a job row without `caps.timeout` yields None.
Prove each case red against a planted copy of the driver whose
`stage_wall` returns only the record copy's cap, then green against the
real one; say in `note` how. Frozen command:
`python3 -m unittest discover -s ops/conductor/tests -p test_ladder_wall_from_job_cap.py`

## First-run walkthrough
- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home — measured by the conductor suites.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
