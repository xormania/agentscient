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

[Finding admission](../../devlane/task/FINDING-ADMISSION.md) owns which rows
earn correction, the optional evaluation shape, append-only evaluation/dispute
and disposition history, and the ledger's correction projection. These are
declared implementation obligations, not a claim of live enforcement. Preserve
raw findings and verdicts; neither a disposition nor severity grants admission.
Old rows remain readable and require bound evaluation before fresh correction.

The series this makes readable is the audit ladder's marginal detection
series (`docs/workflow.md`): findings per reviewer per batch, and what
each later stage still found. That is the number the planning process
is judged by (scope-lane-fixes.md item 25).
