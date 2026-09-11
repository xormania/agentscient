# The workflow end-to-end fixture — next work order after the gate

Owner, 2026-09-11, in session, after a day in which seven lane defects
were each found by running the workflow live and repaired by hand:
"i think you may see the over-arching theme - the workflow - all of it,
needs solid behavior end-to-end testing with a fixture"; then "add the
e2e fixture as the next work order after the gate".

Standing: queued. It starts when slice 5 of the uncited-correction gate
(`.dev/ladder-inputs/scope-gate-20260910.md`) has landed, so the gate is
the first thing the fixture proves end to end. The scope is settled in
session with the owner before any plan; this record is the decision and
the material, not the scope.

## What it is

One synthetic repository under an isolated HOME and state root, fake
harness CLIs that return planted envelopes, and the real driver,
launcher, dispatcher, landing lever, ledger and hooks running against
it. A scenario is a full ladder run with planted outcomes, asserted end
to end. Deterministic, offline, and never touching the operator's live
stores, which is proven once at the fixture level rather than by each
suite snapshotting the host.

## What exists to build on, measured 2026-09-11 at 4b8e986

- `ops/devlane/fixtures/`: synthetic envelopes and store builders;
  `apps/` holds four planted-fault application fixtures with a fault
  registry (`FAULT-KINDS.md`).
- `ops/conductor/tests/test_ladder_lever.py`: stubs for the dispatcher,
  launcher, landing lever and ledger (six stub definitions), and the
  `_LadderFixture` the regression suites reuse.
- `ops/devlane/harness/tests/fakes/`: one fake bridge; no fake harness
  CLI for grok, codex or claude yet.
- `ops/design/features/`: the BDD feature shelf, areas dispatch, repo,
  telemetry, workflow.

What is missing is the composition: the stubs replace the real tools
instead of driving them, and no test runs a whole ladder.

## Scenarios the day supplied, each a defect row in
`ops/conductor/handoff/lane-defects.md`

- inputs reach every stage, and a stage refuses when a named input is
  absent (LD-2; the skeptic's `scope-inputs` refusal);
- a corrected scope, plan or input is a recorded event on resume, and
  refuses without `--rescope` (LD-3);
- audits that name the changed files do not trip custody; a leaked
  implementation line does; fix-tests sees envelopes, never records
  (LD-7, both halves);
- refusal texts on the wire match the contract they cite (LD-6);
- the gate refuses an uncited correction and admits a cited one; the
  driver stops `undisposed` before a fix round (the gate work order);
- nothing under test writes to the operator's stores, proven at the
  fixture boundary, retiring the per-suite live-store and ledger
  snapshots (LD-4, and the handwork ledger case on PR 90).

## Calibration

The concerns contract applies to the workflow itself: planted faults
the fixture must catch, clean runs it must pass, rates reported beside
verdicts. A scenario without a planted counterpart is a declared gap.
