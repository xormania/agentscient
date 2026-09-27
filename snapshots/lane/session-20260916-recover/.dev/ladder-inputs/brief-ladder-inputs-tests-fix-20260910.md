# Brief: correct two regression tests per the third-harness ruling

Ruling: dispatch `20260910T233710Z-review-codex-cd4bef` (Codex, read-only)
on the five red tests in `ops/conductor/tests/test_ladder_lever_inputs.py`
against the quoted contract in
`in/brief-ladder-inputs-tests-20260910.md`. Three findings were UPHELD
against the implementation and are being fixed separately; two were
REJECTED as assumptions the contract does not make. Correct exactly those
two tests. Change nothing else in the file; do not read or edit
`ops/conductor/tools/ladder.py`.

## The two rejected assumptions, verbatim from the ruling

1. `test_dry_run_argv_carries_input_after_the_plan` (finding #1):
   "The test requires dry-run launch argv to expose the plan and start
   inputs in after-plan order. The contract says only, 'Each `--input
   PATH` names a file handed to every stage beside the scope and plan';
   it does not specify dry-run output or argv ordering." The fixture
   passes no plan, so there is no plan path to be after. Assert what the
   contract says: every non-`pr` stage's argv carries `--input <path>`
   for each start input. Do not require a plan, and do not require an
   order relative to the plan.

2. `test_resume_refuses_when_input_bytes_changed` (finding #5): "The
   failing assertion requires a clean fixture worktree before resume,
   which the quoted contract does not require. `close_tripped_record`
   rewrites a tracked dispatch record without committing it, so the test
   fails at line 346 before invoking resume." Drop the clean-porcelain
   requirement, or commit the fixture's own rewrite before resuming;
   keep every assertion about the `record` refusal, the recorded digest
   and the dispatch counts.

## Frozen command

`python3 -m unittest discover -s ops/conductor/tests -p test_ladder_lever_inputs.py`

At this ref the merged fix is present. Expected after correction: the
two corrected tests pass; the three tests the ruling UPHELD
(`test_input_flag_without_a_path_refuses_arguments`,
`test_missing_input_refuses_input`, `test_unreadable_input_refuses_input`)
stay red until the implementation fix lands, and must not be edited.

## First-run walkthrough

- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home — measured by the launcher's contract;
  the ladder fixtures need neither.
- assumption: at this ref the two named tests fail for the reasons the
  ruling quotes — measured 2026-09-10 at dd7784c: FAILED (failures=5),
  the two among them.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
