# Work order: the stage set is chosen per work order (stage-set)

Owner, 2026-09-12, in session: "i feel like lots of waste is happening - the
entire pipeline shouldn't be static - it should dyanmically determined per
work-order"; then "agreed - write the scope for the stage-set slice - and
btw; my insights are about exactly this - graphs and contracts". The idea
is recorded as I-026. The scope-discipline clause beside this file governs.

This file is the scope only: what, and the boundaries. The plan is not its
author's to write. The scope is settled with the owner in session before
the plan is dispatched; the seed table in item 10 is the owner's to amend.

## What

The ladder runs the same nine stages for every slice. Slice 1 of item 31,
three contract documents and their document pins, ran ten dispatches in two
hours; its two audits and its re-audit produced eight findings, all against
the plan's design for later slices and none against the documents. The
workflow law already says a workflow is a declared graph run by a generic
engine and that the sequence of reviewers is supplied as declared data with
a per-run override, never inferred by the system. The plan already names
each slice's risk class. After this work order the ladder reads a tracked
table, the owner's, that maps a risk class to a stage set; the plan's
machine line names the class; a floor in the driver keeps the two rules the
lane has measured hardest; a per-run override must say why; and every stage
not run is declared on the record.

## Contract

1. **The table is declared data.** A tracked file
   `ops/conductor/stage-sets.json` maps a class name to an ordered list of
   stage names drawn from the driver's stage table, in the driver's order.
   The driver reads it at start and records its path and digest beside the
   conf. An absent or unreadable file, a class not in it, or a stage name
   not in the driver's table refuses (class `stage-set`, expected–found–
   needed naming the file, the class or the stage). There is no default
   set: absence is declared, never inferred.
2. **The plan names the class.** The machine line becomes
   `slice<TAB>name<TAB>S|M<TAB>class`. A slice line without a class, or with
   a class the table does not hold, refuses `plan` naming the slice. The plan
   job's prompt states the grammar and names the table file so the planner
   chooses from it.
3. **The floor is in the driver, not the table.** A set that omits `tests`
   or `check-tests`, or names `code` without at least one of `security` and
   `adversarial`, is refused at load (class `stage-set`, naming the row and
   the missing stage). The fix round is one unit: a set names `fix-tests`
   and `fix-code` together or neither, and `security-re` only with them.
4. **Conditions still hold inside a set.** A stage in the set runs only when
   its existing condition holds (the skeptic's `changes` for `tests-fix`, an
   audit's `changes` for the fix round). A stage not in the set never runs.
5. **The override says why.** `ladder.sh SCOPE BRANCH PLAN --stage-set CLASS
   --because TEXT` runs that class for this ladder; `--stage-set` without
   `--because` refuses `arguments`. The record carries `stage_set` with the
   class, its stages, the table's digest, the source (`plan` or `override`),
   and for an override the reason, the agent and the time. `resume` keeps
   the recorded set and refuses `record` if the table's bytes changed
   without `--rescope`.
6. **Absence is declared on the record.** Every stage of the driver's table
   that is not in the chosen set is present with `outcome: skipped` and
   condition `not in stage set <class>`.
7. **Calibration names the set.** The calibration row per slice carries the
   class; the plan's estimated minutes and the driver's measured minutes
   cover the set's stages; findings per stage are recorded against the set.
8. **The lever says so.** `ops/conductor/ladder-lever.md` gains the
   selection paragraph under its stage table, the `stage-set` rows in its
   refusal table, the `--stage-set` form in its instrument line, and the
   record fields of items 5 and 6.
9. **Refusals on the wire.** Every new refusal is one stderr line
   `class: expected …; found …; needed …`, exit 2, stdout empty, with one
   hermetic invocation added to the registry (`docs/wire.md` §Conformance).
10. **The seed table, the owner's to amend.** Two classes at landing:
    `contract` → tests, check-tests, tests-fix, code, adversarial;
    `lane` → tests, check-tests, tests-fix, code, security, adversarial,
    fix-tests, fix-code, security-re (today's nine). Item 31 slice 3 and
    every driver or launcher slice run under `lane`.

## Boundaries — not this work order

- What any stage does, who runs it, or how it is dispatched. The
  dispatcher, launcher, landing lever and ledger are untouched; models and
  harnesses stay in the lane conf.
- Selection by the system. The class is declared by the planner and checked
  by the owner in the plan; nothing infers it from file paths, diff size or
  history.
- Records. They do not go through the ladder (I-025).
- The end-to-end fixture (I-020); it will assert this selection as a
  scenario once both exist.
- Item 31 slice 3 and its guard.
- Per-stage cost or token telemetry beyond the minutes already recorded.

## Measured, 2026-09-12, at dev `0dacd84`

- `ops/conductor/tools/ladder.py` `DISPATCH_STAGES`: nine rows, tests to
  security-re; `REVIEW_STAGES` and `WITHHELD_STAGES` name their members;
  `mark_skipped(name, condition)` writes `outcome: skipped` with a
  condition; `parse_plan` reads `slice` lines with three fields and `bucket`
  lines with four.
- The plan job's prompt (`ops/devlane/task/jobs.json`) states the grammar
  `slice<TAB>name<TAB>S|M` and asks for a risk class in prose ("touches the
  dispatcher, the launcher's argv building, a contract: its own slice"); it
  names `.dev/wip/calibration-buckets.md` for the calibration row's shape,
  and that file is absent from the tree.
- Ladder 20260911T213956Z-ladder-96e53f (item 31 slice 1): ten dispatches,
  two hours, audit findings eight (five deferred, three fixed), re-audit
  findings three, all repeats of the first audit's.
- `ops/conductor/tests/test_ladder*.py`: thirteen files; `_LadderFixture`
  stubs the dispatcher, launcher, landing lever and ledger.
- `ops/conductor/registry/ladder.py.json`: a `tool` and `rows` object.

## Tests — proposed coverage, not approval

- `ops/conductor/tests/`: the table load and each refusal (absent file,
  unknown class, unknown stage, each floor violation, a partial fix round);
  the plan grammar with and without a class; the override with and without
  `--because`; the record's `stage_set` and its skipped rows; resume keeping
  the set and refusing a changed table; the calibration row naming the
  set; a `contract` ladder that dispatches no security stage and a `lane`
  ladder that dispatches all nine, on `_LadderFixture`; the wire on each new
  refusal.
- `ops/devlane/task/tests/`: the plan prompt's grammar names the class and
  the table file.

## Calibration

Declared M in two S buckets: the table, its load and floor, and the plan
grammar (`ops/conductor/stage-sets.json`, `ladder.py` parse and load,
`jobs.json`); the selection, override, record and calibration
(`ladder.py` run, `ladder-lever.md`, the registry). The planner buckets;
this row is the declaration it is measured against.
