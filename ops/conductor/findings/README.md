# The findings ledger

Every finding a reviewer makes, with what became of it. Data, not
ceremony (owner, 2026-09-04: "make sure we record these security
issues - data, data, data - its not ceremony - its future value").

The source is the run records: each check-tests, security-audit or
adversarial-review record under `.dev/records/dispatches/` carries the
reviewer's envelope with its findings verbatim. `ops/conductor/tools/findings.py`
imports them into a SQLite store under `~/.local/state/agentscient/findings.db`,
holds each finding's disposition with the identity that set it, and
exports the whole store here as `findings.jsonl`, one row per finding,
regenerated and never edited by hand. Dispositions: open, fixed,
addressed, deferred, ruled, fix-round, opinion; the evidence names the
commit, the record, the ruling or the scope item.

A finding may carry the reviewer's `practical` label, `yes` with the
`failing` invocation or `no` (ops/devlane/task/CONTRACT.md §The
practical label). The store holds both columns and the export writes
them only on a row whose finding carried them, so rows exported before
the label keep their shape. A labelled finding ruled rather than fixed
is ruled with evidence beginning `declined: not practical — `; the
`finding-disposition` row reads that judgement in the PR's `## Proof`
at `gh pr ready`. A finding without the label is ruled on any ground,
as the rulings before it were.

The read verb `cited` KEY reports whether that finding is disposed with a
holding contract citation. The citation grammar lives in `findings.py`; the
gate and `findings.py` read the same definition.

The series this makes readable is the audit ladder's marginal detection
series (`docs/workflow.md`): findings per reviewer per batch, and what
each later stage still found. That is the number the planning process
is judged by (scope-lane-fixes.md item 25).


## Observation and explicit exports

`summary`, `cited KEY`, `export` and `export --calibration` are read-only.
They neither initialize an absent database nor migrate a legacy schema.
`import`, `disposition` and `calibrate` retain explicit writer initialization;
`import` adds the label columns while retaining old dispositions and row shape.
Missing, corrupt, locked, unreadable or incompatible stores refuse visibly.

Plain exports only print JSONL. Use `export --write [PATH]` or
`export --calibration --write [PATH]` to write a file deliberately, with an
identity. The default destinations remain `findings.jsonl` and
`calibration.jsonl` in this directory. File export does not initialize or
migrate its source store. Ordinary calibration reads no longer rewrite the
tracked export; scripts that relied on that side effect must add `--write`.
