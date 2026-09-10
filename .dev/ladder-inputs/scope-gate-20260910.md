# Work order: the uncited-correction gate

Owner, 2026-09-10, in session: "work orders are going over scope - they're
treating feedback as requirements"; "start the gate work order under the
clause". The clause is `scope-discipline.md` beside this file; this work
order is its mechanical form and retires it for what it covers.

This file is the scope only: what, and the boundaries. The plan is not
its author's to write.

## What

A correction is a write job launched to answer reviewer findings. Today
nothing stands between a finding and a correction dispatch: the finding's
truth is adjudicated, its membership in the work order never is. The gate
refuses a correction at mint unless every finding it answers is named,
disposed in the findings ledger, and that disposition cites the numbered
contract item the finding violates. No citation, no correction.

## Contract

1. **Correction, defined mechanically.** A correction dispatch is a
   write-role job (`implement`, `author-tests` in `jobs.json`) whose
   `--follows` names a record whose job is a read review job
   (`check-tests`, `security-audit`, `adversarial-review`, `adjudicate`,
   `sweep`) or whose inputs include a file from such a record's `out/`.
   The shape is read from the dispatch arguments and the followed record,
   never inferred from prose in the scope.
2. **Findings are named, not inferred.** A correction names the finding
   keys it answers through a declared dispatch field. The planner chooses
   the field; it is declared in the dispatch contract and recorded in the
   record. A correction of the shape in item 1 that names no key is refused.
3. **Refusal at mint, on the wire.** Before any harness runs: class token
   from the launcher's refusal table, one stderr line `class: expected …;
   found …; needed …`, stdout empty, exit 2, no record minted. The needed
   half names the exact `findings.py disposition` command that would
   satisfy it. Distinct found-texts for: no key named; key absent from the
   store; key still `open`; disposition evidence carries no contract
   citation; disposition dated after the mint attempt.
4. **Citation shape.** A disposition satisfies the gate when its evidence
   contains `contract item N` where N is a numbered item of a scope file,
   and names that scope file by path. The planner fixes the exact grammar
   as data in one place; the gate and `findings.py` read the same
   definition.
5. **Time order.** The disposition's `disposed_at` precedes the mint. A row
   written after the refusal satisfies the next attempt, not the refused one.
6. **No override.** The gate has no `overrides` row and no hand-grant
   escape. The only way through is a disposition row, which is cheap and
   honest. Owner's clause item 6: "refused at the conductor".
7. **Non-corrections untouched.** A write job that follows a plan, tests,
   or implement record, or follows nothing, is not a correction and is not
   inspected by this gate.
8. **Recorded.** An accepted correction's record carries the finding keys
   and their citations, so the audit trail is mechanical: from any
   correction record, every finding it answered and the item each cites.
9. **The ladder stops rather than corrects.** The driver's `fix-tests` and
   `fix-code` stages are corrections under item 1. Before launching either,
   the driver checks every finding in the audit envelopes it would hand
   over; if any lacks a satisfying disposition, it stops with a declared
   stop reason naming the undisposed keys, and `resume` continues once
   rows exist. The driver never writes dispositions itself.
10. **Conformance.** The gate joins the refusal registry in the change that
    lands it, with one hermetic refusal-provoking invocation.

## Boundaries — not this work order

- The PR readiness gate (a ready note with an undisposed CHANGES verdict).
  Separate work order.
- Reviewer prompts under `ops/conductor/concerns/` demanding the declared
  half of each finding. Separate work order; clause item 5 covers it by
  discipline until then.
- Any change to what a finding is, the findings schema, or the export.
  The gate reads the store; it does not reshape it.
- Retro-disposing the 532 open rows. That is conductor work under the
  clause, not code.

## Measured, 2026-09-10, at 94ab7a0

- `grep -c finding ops/devlane/dispatch/record.py ops/conductor/tools/dispatch.sh`: 0 and 0. No finding or citation field exists on the dispatch surface. `launch.py` has `--follows` (append, line 2494).
- `jobs.json` roles: write = `implement`, `author-tests`; read = `check-tests`, `security-audit`, `adversarial-review`, `adjudicate`, `sweep`, `plan`; `verify` has no role.
- Findings store: `~/.local/state/agentscient/findings.db`, table `findings(key, record, job, stage, harness, model, unit, ref, verdict, n, severity, where, claim, reproduce, disposition DEFAULT 'open', evidence, disposed_at, disposed_by)`. Verb: `findings.py disposition KEY DISPOSITION EVIDENCE`.
- A past correction record (`20260904T230616Z-code-codex-65775d`): job implement, stage code, `follows ['20260904T224943Z-adjudicate-grok-f64a28']`, inputs `in/security-fix-57.md`, `in/RULING.md`. That is the shape item 1 names.
- Ladder stage table (`ops/conductor/ladder-lever.md`): `fix-tests` and `fix-code` take both audit envelopes as inputs; review stages import envelopes through `findings.py import`.
- Refusal wire: `docs/wire.md`. Launcher refusal table: `ops/devlane/dispatch/CONTRACT.md` §refusals.
- Ledger after re-import today: 657 rows, 532 open, none carrying a contract citation.

## Tests — proposed coverage, not approval

- `ops/devlane/dispatch/tests/`: mint refuses each found-text in item 3 against a planted store; accepts with a satisfying row; ignores non-correction write jobs (item 7); records keys and citations (item 8); the hermetic registry invocation (item 10).
- `ops/conductor/tests/`: `findings.py` citation check on evidence, both directions; ladder stops before `fix-tests`/`fix-code` with undisposed keys and resumes once rows exist (item 9).

## Calibration

Declared M as two S buckets: the mint gate with its store query; the
ladder stop. Files expected: `ops/devlane/dispatch/launch.py`,
`ops/devlane/dispatch/CONTRACT.md`, `ops/conductor/tools/findings.py`,
`ops/conductor/tools/ladder.py`, `ops/conductor/ladder-lever.md`, tests.
The planner buckets; this row is the declaration it is measured against.
