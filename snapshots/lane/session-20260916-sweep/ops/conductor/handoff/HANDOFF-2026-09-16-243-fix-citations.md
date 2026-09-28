# #243's fix commits and the findings they close

Written 2026-09-16 by the session holding `lane/session-20260916-c`,
Claude Opus 5 (1M context), by hand under grant 258.

## Why this record exists

CONTRIB's ready row for a closed security audit says that after the
audit's sha every commit is either in the records set or "a fix commit in
the Fix commit shape whose `Finding:` line names a key of that same
record", and that the first commit which is neither voids the audit. The
four fix commits below name every key they close, with the readings they
were measured against, in the commit body rather than in a `Finding:`
trailer. Asked to rule on the letter against the intent, the Lead ruled
on 2026-09-16, relayed through agentscient-0d (the XO): a fix commit
naming the audit's keys and readings in its body satisfies the row. The
owner's sentence behind it, the same day: a fix commit citing the audit's
own rows does not void the audit.

This record is the mapping in one place, so the row can be checked
without reading six commit messages. It is in the records set
(`ops/conductor/handoff/`) and voids nothing by landing.

The audit is `20260916T100839Z-review-codex-1833de`, at `b1d868b0`.

## The mapping

| commit | closes | measured |
|:--|:--|:--|
| `0b88440b` | `20260916T100744Z-review-grok-bcfee6#1`, `20260916T100839Z-review-codex-1833de#2` | RED Ran 94 tests FAILED (failures=6), GREEN Ran 94 tests OK |
| `f136f760` | `20260916T100744Z-review-grok-bcfee6#2`, `20260916T100821Z-review-codex-834580#2`, `20260916T100839Z-review-codex-1833de#3` | RED Ran 99 tests FAILED (failures=3, errors=2), GREEN Ran 99 tests OK |
| `19ba53f2` | `20260916T100744Z-review-grok-bcfee6#3`, `20260916T100821Z-review-codex-834580#1`, `20260916T100839Z-review-codex-1833de#4` | RED Ran 101 tests FAILED (failures=1), GREEN Ran 101 tests OK |
| `73e47041` | `20260916T100744Z-review-grok-bcfee6#4`, `20260916T100821Z-review-codex-834580#4`, `20260916T100839Z-review-codex-1833de#5`, `20260916T101838Z-review-codex-beb7b6#3`, `20260916T101802Z-review-grok-7bbe10#2` | RED Ran 119 tests FAILED (failures=14), GREEN Ran 119 tests OK |

Every reading is `python3 -m unittest discover -s ops/conductor/tests -p
test_coordination.py` from the worktree root, the same command for the
red and the green of each pair, with `ruff check` on the changed files
reading `All checks passed!` at each.

One citation to correct, since the tree cannot be rewritten: `73e47041`
spells the Grok reader finding `20260916T101838Z-review-grok-7bbe10#2`,
taking the timestamp from the Codex record beside it. The record is
`20260916T101802Z-review-grok-7bbe10`. The ledger disposition names the
right key.

## The commits that are not fix commits

Three commits on this branch after the audit's sha close no finding, and
naming them is the point of this record.

- `b902246d`, the `revoke` verb. New surface the audit never saw, found
  in the live run — the trial store stands at two leads because `grant`
  appends and nothing subtracted — and ruled into #243 by the Lead on
  2026-09-16 as its own commit with no second PR. **It is outside the
  audit's coverage and nothing here claims otherwise.** Anyone reading
  "#243 audited" as covering `revoke` is reading further than the record
  goes.
- `75239f42`, the literals fix: the read-only reader asked SQLite's
  catalogue by its original name, which contains the release branch's
  word, and the lane's literals verb refused the tree. It reads
  `sqlite_schema` now, the same catalogue under the name SQLite 3.33 gave
  it. A CI repair, not a finding.
- `9480b82e` and `eb95208d`, merges of `dev` forward.

## The rows, not fixed

Four findings of the same three records were disposed as rows rather
than fixes, by the Lead's rulings of 2026-09-16, and are in the ledger
with their reasons:

- `20260916T100821Z-review-codex-834580#3` — `grant` overwrites the
  single `granted_by` pointer. Real, but the lane has one lead and will
  not reach the cycle during the proof.
- `20260916T100839Z-review-codex-1833de#1` — the session id as
  authority. Accepted risk, no fix and not even the redaction (owner,
  2026-09-16). What the id is and is not is now written into
  `coordination-lever.md` at the sentence it qualifies.
- `20260916T100744Z-review-grok-bcfee6#5` and
  `20260916T100821Z-review-codex-834580#5` — p3, deferred, not before
  ready.
