# Brief: one assertion string moved under the test, follow the contract

Since `ops/conductor/tests/test_ladder_lever_inputs.py` was written, the
ladder contract changed on dev (PR 89, `resume --rescope`). The refusal
for a recorded input whose bytes changed now reads, from
`ops/conductor/tools/ladder.py` at this ref:

    record: expected the recorded input sha256 <old>; found <new>; needed restore the recorded bytes, or resume with --rescope to record the change

and `ops/conductor/ladder-lever.md` at this ref says, in the
preconditions table: `record` refuses when "a recorded scope, plan or
input changed without `--rescope`"; needed "choose or repair the record,
or resume with `--rescope`".

One test still asserts the pre-PR-89 wording "restore the recorded bytes
or repair the digest":

    test_resume_refuses_when_input_bytes_changed

Change only that expected string so the assertion follows the current
contract, keeping the class `record` and the recorded-digest assertions
exactly as they are. Nothing else in the file changes. Do not read or
edit the implementation beyond the one refusal line quoted above.

Frozen command:
`python3 -m unittest discover -s ops/conductor/tests -p test_ladder_lever_inputs.py`
Expected after the change at this ref: Ran 13 tests, OK.

## First-run walkthrough

- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home — measured by the launcher's contract.
- assumption: at this ref exactly one test fails, on that string —
  measured 2026-09-10 at 41176c7: FAILED (failures=1).
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
