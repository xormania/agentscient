# I-026 — the pipeline is not static; it is determined per work order

- recorded: 2026-09-12 00:1xZ, in session, while item 31 slice 2 ran its fix round
- source: owner, verbatim below
- disposition: open

## In the owner's words
> i feel like lots of waste is happening - the entire pipeline shouldn't be static - it should dyanmically determined per work-order

## What was heard

The conductor's reading. The ladder runs the same nine stages for every slice: tests, skeptic, tests-fix, code, security, adversarial, fix-tests, fix-code, security re-audit. Slice 1 of item 31 was three contract documents and document-pin tests; it ran all nine, ten dispatches, and every audit finding it produced was against the plan's design for later slices, none against the documents; five of eight were deferred and the re-audit re-raised the same three. The stages that paid were the tests, the skeptic and the code stage. The waste is a fixed stage set applied to work whose risk class it does not fit.

The law already allows the fix. The workflow genus says workflows are declared graphs executed by a generic engine, never hand-coded step chains, and the audit-ladder pattern says the sequence of reviewers is supplied by the operator as declared data with a per-run override, never inferred by the system. The plan already carries each slice's risk class (contract, driver, launcher argv, other). What is missing is the join: the stage set chosen from the declared risk class, as data the ladder reads, with a floor the owner sets (the second producer on tests and at least one independent review of code are never dropped) and a per-run override on the command line. Calibration rows then measure per stage set, so the choice is checked by the same instrument that measures the bucket.

## Standing facts it must reconcile with

Measured 2026-09-12 against dev `c5ba368`:

- Ladder 20260911T213956Z-ladder-96e53f (slice 1): ten dispatches, two hours of wall time, about fifteen million tokens nine tenths cached; audit findings eight, deferred five, fixed three; re-audit findings three, all repeats.
- `ops/conductor/ladder-lever.md` §Stage table: the table is data in the driver but has no per-slice selection; `docs/workflow.md`: "declared as data in a registry and executed by a generic engine", "supplied by the operator as declared data with a per-run override".
- The plan record 20260911T212110Z-plan-claude-866a60 §3 names a risk class per slice.
