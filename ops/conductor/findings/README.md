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
and disposition history, and the ledger's correction projection. The owners
implement these interfaces; independent acceptance remains pending. Preserve
raw findings and verdicts; neither a disposition nor severity grants admission.
Old rows remain readable and require bound evaluation before fresh correction.

The [mandatory prevention amendment](../../devlane/task/FINDING-ADMISSION.md#mandatory-prevention-amendment)
extends this same ledger with immutable work-order declarations and append-only
review reservations, execution-receipt references and followup closure events.
Canonical launch uses its eligibility decision for manual and ladder dispatch
before model spawn. A completed review cannot be restarted as an initial review
under another unit/id; followups require admitted unresolved findings, bound
corrections and an existing permitted slot. Imported worker assertions cannot
certify launcher execution. Legacy reads remain unchanged; enforcement and
independent acceptance of these additions are pending.

The series this makes readable is the audit ladder's marginal detection
series (`docs/workflow.md`): findings per reviewer per batch, and what
each later stage still found. That is the number the planning process
is judged by (scope-lane-fixes.md item 25).

## Finding admission implementation

`findings.py dispute KEY EVIDENCE` appends an identity-bearing dispute.
`findings.py corrections --ref FULL_SHA --scope-sha256 SHA256 RECORD [RECORD ...]`
reads the complete imported review batch without identity or writes. It emits
only bound admitted evaluations and held keys, or refuses the whole read.
The shared [admission contract](../../devlane/task/FINDING-ADMISSION.md) owns
classifications, evidence, legacy behavior and independent adjudication.

Import retains original source bytes, input/report bytes, evaluations and
dispositions separately from the existing derived columns. Export adds ordered
`evaluations`, `disputes` and `disposition_history`. Existing overwritten
disposition history is unavailable; migration preserves only the stored row,
including any null timestamp or identity. Active dispatches are not immutable
sources and are imported once they have produced an envelope.
