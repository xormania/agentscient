# Handoff — 2026-09-11, after the gate slices landed

## Where things stand

- dev at 6ff81a7 carries all five slices of the uncited-correction gate,
  LD-14 to LD-19 with repairs and second-producer tests, the deliverable
  lock, and the watchdog's drift and stall reports. Release #129 (dev
  into master) is a draft for the owner to merge.
- The deliverable lock names `dev` and `records/aar-20260911`. Set the
  next deliverable before any new work:
  `python3 ops/conductor/tools/deliverable.py set BRANCH... --why TEXT`;
  `show` reads it; `clear` lifts it.
- The watchdog runs from `../wt/ag-deliverable-lock-20260911` (pid
  379354 at hand-off) with `--tick 300 --forge-every 3 --heartbeat-every
  3`, logging to the session scratchpad; restart it from the main
  checkout now that #126 is on dev.
- No open grants. Grok's credential was renewed at 05:41Z; it ages out
  about 30 hours later and the launcher now refuses it before the mint.
- Ladders fd103b (slice 4) and 307788 (slice 5) are recorded `stopped
  withheld` at fix-tests; their PRs were opened and merged by hand. The
  records are complete and need no resume.

## Corrections to retain

- The scope-discipline clause binds the conductor: a finding is a
  ledger row, not a work stream, while a deliverable is open. The lock
  enforces it; the watchdog reports it.
- The `dispatch-by-hand` row honours only an unscoped grant; the
  launcher must run from the branch's own worktree; no `--model` or
  `--effort` on the dispatcher; every path spelled out (pitfall 18).
- `derive_command` runs only `test*.py` artifacts; a support module
  under `tests/` is carried, never run (LD-19).
- `resume LADDER_ID --retry STAGE --because TEXT` is the recorded way
  past a driver-caused retry cap.
- The hand-write row does not see a Python heredoc writing a file;
  scope the grant honestly anyway.
- A hand-landed worker file needs `ruff check` before the push
  (pitfall 21).

## Open, in the ledger, not started

- The ladder's leak heuristic (`withheld`) stops on audit envelopes
  that name the implementation record; both slice 4 and slice 5 ladders
  ended there.
- The ladder's `pr` stage cannot adopt a PR already open for its branch
  (LD-20 candidate).
- The findings export in the tree drifts from the shared ledger between
  exports; a merge conflict on `findings.jsonl` is resolved by
  regenerating it.
- The AAR trust table's audit row is read from notes; audit receipts are
  not wired.

## Next thread

Owner, 2026-09-11: "we'll probably tackle e2e next session - i just need
to trust this enough first." The fixture (I-020) and the monitor work
order (I-021) follow, then item 31's ladder. Start each by naming it as
the deliverable.

## Retrieval

```sh
git show records/aar-20260911:ops/conductor/AAR-2026-09-11-gate-slices.md
git show records/aar-20260911:ops/conductor/handoff/HANDOFF-2026-09-11-gate-slices.md
```

Left behind on purpose: the session transcript, the scratchpad
(pollers' outputs, ladder logs, scope files for the hand dispatches,
`pitfalls.md`), and the session's Monitor tasks.
