# Scope: author `test_dispatch_actions.py` for sessions slice 3

Job: author-tests. Producer: Grok (the contract's author, Claude Fable
5.1, agentscient-87, writes no test). Checked once by Codex
(check-tests), implemented by the S3 builder, reviewed by Grok and Codex.
Withheld: implementation. None exists; read none.

Contract: `ops/conductor/sessions-lever.md` at the ref given, "Slice 3
— Dispatcher integration" (lines 511–739 at 0c54f658): the shapes at
546–620 (`dispatch_intents`, the `dispatch-intent` machine, the launch
order, reconciliation, capacity, holder, `verifications.json`), the
CLI verbs at 622–640, the refusals at 658–674, fixtures 1–8 and 10 at
684–739. Read `docs/tests.md`, `ops/testkit/`,
`ops/conductor/machine-lever.md`, `ops/conductor/coordination-lever.md`
(participants, assignments, the `dispatcher` role) and
`ops/conductor/tests/test_sessions.py` as the worked example of a suite
over a machine on the engine with a bound participant.

Write `ops/conductor/tests/test_dispatch_actions.py` on the kit:
`World` hermetic with the source lane's name, every subprocess through
`run` with a timeout, the fakes `fakes/dispatch_wrapper.py` (stands in
for `dispatch.sh`: logs its argv as one JSON line; by spec prints
`record:` and `launcher-pid:` and writes `<jobs root>/<id>/state.json`
with the `--correlation` value, or refuses with a given line, or exits
without `record:`, or writes then dies) and `fakes/dispatch_launch.py`
(stands in for `launch.py`: `status`, `wait`, `collect` readings by
spec, argv logged), both new and yours, planted through `Tools`; rows by
id with `origin: sessions-lever.md#slice-3 <n>` naming the fixture
number; `refusal_wire` on every refusal row. No program embedded in the
test module (rule 6). The dispatcher participant is bound in the world
and holds the `dispatcher` machine through `dispatcher.py set`; a
worker participant is bound for the `role` row.

Rows: fixtures 1 to 8 and 10, every refusal class in the table once,
and the clean neighbours (an `--input` past `SCOPE_CAP`; `status` by a
worker). The relaunch rows assert the wrapper's log line count. A pin
on a count the contract does not own is a finding. Report `reused:`
names from `docs/tests.md` in the job note.
