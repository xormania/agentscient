# Brief: regression tests for the ladder's start-time inputs (PR 87)

Direct repair PR 87 (`repair/ladder-carries-inputs-20260910`, commit
05e5bc3) taught `ops/conductor/tools/ladder.py` a repeatable
`--input PATH` start argument. These tests are written on a branch cut
from dev BEFORE that fix, from the contract words below, so every test
is red here for the right reason: the driver refuses the form. They are
then run against the fix. The fixer did not write them; do not read
PR 87's implementation.

## Contract, verbatim from the repaired `ops/conductor/ladder-lever.md`

> `ops/bin/ladder.sh SCOPE BRANCH [PLAN] [--input PATH]...` starts a
> ladder in the worktree that owns `BRANCH`. Each `--input PATH` names a
> file handed to every stage beside the scope and plan, so the work
> order a scope sentence cites reaches every worker as a supplied input;
> each is recorded with its digest and re-verified on resume.

> Record: scope, optional plan, start inputs, and conf paths with
> SHA-256 digests. The record key is `inputs`, a list of
> `{"path", "sha256"}` in the order given.

> Refusal `input`: a `--input` path is absent or unreadable; needed
> "supply a readable input file". Refusal `arguments` names the form
> `SCOPE BRANCH [PLAN] [--input PATH]... or resume LADDER_ID`.

> Resume: a recorded input whose bytes changed refuses class `record`,
> "restore the recorded bytes or repair the digest", before any dispatch.

## Tests to write

One file: `ops/conductor/tests/test_ladder_lever_inputs.py`, built on the
fixtures already in `ops/conductor/tests/test_ladder_lever.py`
(`_LadderFixture` and its stubbed dispatcher, launcher, landing and
findings tools). Cover, each as its own test:

- `--input PATH` after the positionals is accepted; `--input=PATH` too;
  two inputs keep their order.
- a missing or unreadable input refuses class `input`, one stderr line
  on the wire, exit 2, empty stdout, no ladder record written.
- `--input` with no following path refuses `arguments`.
- the ladder record carries `inputs` with path and sha256 per input, in
  order; with no `--input` it is an empty list, present.
- every dispatch stage's argv carries `--input <path>` for each start
  input, after the plan; the `--dry-run` output shows the same.
- on resume, an input whose bytes changed refuses `record` naming the
  recorded sha256; unchanged bytes resume normally.
- the `arguments` refusal text names the new form.

Frozen command:
`python3 -m unittest discover -s ops/conductor/tests -p test_ladder_lever_inputs.py`

## First-run walkthrough

- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home — measured by the launcher's contract;
  the stubs in `test_ladder_lever.py` need neither.
- assumption: at this ref the driver refuses `--input` with `arguments`
  — measured 2026-09-10 on dev 94ab7a0: `arguments: expected SCOPE BRANCH
  [PLAN]; found … --input …; needed choose the documented start form`.
  That is the red every test must show, not an import or collection
  error.
- assumption: the fixture runs the driver as a subprocess or in-process
  through `main(argv)` — measured: `test_ladder_lever.py` does both;
  follow its pattern.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
