# Five regression tests red against the merged fix — for a third-harness ruling

Tests: ops/conductor/tests/test_ladder_lever_inputs.py (Grok, dispatch 20260910T231830Z-tests-grok-6cd04a). Fix: ops/conductor/tools/ladder.py and ops/conductor/ladder-lever.md as merged in PR 87 (a9ab39e). Contract the tests were written from: .dev/ladder-inputs/brief-ladder-inputs-tests-20260910.md, section 'Contract, verbatim'. Measured at dd7784c, 2026-09-10:

```
FAIL: test_dry_run_argv_carries_input_after_the_plan (test_ladder_lever_inputs.InputDispatchArgv.test_dry_run_argv_carries_input_after_the_plan)
AssertionError: plan path missing from argv: ['/tmp/ladder-lever-ys9y2kh7/wt-ladder-aa32/ag-ladder-aa32/ops/devlane/dispatch/launch.py', 'author-tests', '--harness', 'grok', '--model', 'ladder-model-grok-aa32', '--effort', 'ladder-effort-grok-aa32', '--stage', 'tests']
FAIL: test_input_flag_without_a_path_refuses_arguments (test_ladder_lever_inputs.InputRefusals.test_input_flag_without_a_path_refuses_arguments)
AssertionError: 'SCOPE BRANCH [PLAN] [--input PATH]... or resume LADDER_ID' not found in 'arguments: expected --input followed by a path; found --input with no path; needed name the input file'
FAIL: test_missing_input_refuses_input (test_ladder_lever_inputs.InputRefusals.test_missing_input_refuses_input)
AssertionError: 'supply a readable input file' not found in 'input: expected a readable input file; found /tmp/ladder-lever-a937rn54/wt-ladder-aa32/ag-ladder-aa32/no-such-input-aa32.md; needed supply a input' : input: expected a readable input file; found /tmp/ladder-lever-a937rn54/wt-ladder-aa32/ag-ladder-aa32/no-such-input-aa32.md; needed supply a input
FAIL: test_unreadable_input_refuses_input (test_ladder_lever_inputs.InputRefusals.test_unreadable_input_refuses_input)
AssertionError: 'supply a readable input file' not found in "input: expected a readable input file; found [Errno 13] Permission denied: '/tmp/ladder-lever-jl7qfxt3/wt-ladder-aa32/ag-ladder-aa32/wo-alpha-aa32.md'; needed correct its permissions" : input: expected a readable input file; found [Errno 13] Permission denied: '/tmp/ladder-lever-jl7qfxt3/wt-ladder-aa32/ag-ladder-aa32/wo-alpha-aa32.md'; n
FAIL: test_resume_refuses_when_input_bytes_changed (test_ladder_lever_inputs.InputResume.test_resume_refuses_when_input_bytes_changed)
AssertionError: ' M .dev/records/dispatches/20260904T120000Z-tests-grok-aa0132.json\n' != ''
FAILED (failures=5)
```

For each failing test rule UPHELD (the fix violates the quoted contract; name the sentence), REJECTED (the test asserts something the contract does not say; name what), or PARTIAL. Reproduce by running the named test. Do not edit anything.
