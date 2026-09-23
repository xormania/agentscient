# Scope: author `test_courier_native.py` for sessions slice 2

Job: author-tests. Producer: Grok (the contract's author, Claude Fable
5.1, agentscient-87, writes no test). Checked once by Codex
(check-tests), implemented by the S2 builder, reviewed by Grok and Codex.
Withheld: implementation. None exists; read none.

Contract: `ops/conductor/sessions-lever.md` at the ref given, "Slice 2
— persistent native conversation", the shapes at lines 285–374
(`delivery_routes`, `delivery_attempts`, `send_requests`, the attempt
outcomes and the reconciliation rule), the verbs added to
`coordination.py` and `courier.py` at 407–423, the refusals at 425–434
and fixtures 3, 4, 5 and 12 at 449–509. Read `docs/tests.md`,
`ops/testkit/`, `ops/conductor/coordination-lever.md` for the core's
message facts, and `ops/conductor/tests/test_courier.py` as the worked
example over the courier; the slice 1 fakes are yours to extend.

Write `ops/conductor/tests/test_courier_native.py` on the kit: `World`
hermetic, every subprocess through `run` with a timeout, fakes planted
through `Tools` (a planted `submit` callable's calls logged as JSON
lines through the registry), rows by id with
`origin: sessions-lever.md#slice-2 <n>`, `refusal_wire` on every
refusal row. No program embedded in the test module (rule 6).

Rows: `route --take` for stdout and for native, a second take against a
live world-owned holder refusing `route` naming its pid, the take-over
of a reaped holder with a new `since`; `send --key` twice with one body
returning one `M-n` as `repeated`, a third with another body refusing
`idempotency` with no row written; `attempt` then `attempted` through
each outcome, `deliver` recorded once on the first `written` or
`accepted` with the `native:AT-n:` ref and `acked_at` left NULL; the
crash reconciliation: a NULL outcome past the ttl with the message in
the fake's evidence reads `accepted reconciled` and no second
submission, without it reads `uncertain` and one new attempt; the
outstanding cap: a fifth reservation refuses `attempt`; the additive
schema on a store populated by the current schema: every row before is
a row after. A pin on a count the contract does not own is a finding.
Report `reused:` names in the job note.
