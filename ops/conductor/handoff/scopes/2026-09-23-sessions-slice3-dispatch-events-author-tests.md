# Scope: author `test_dispatch_events.py` for sessions slice 3

Job: author-tests. Producer: Grok (the contract's author, Claude Fable
5.1, agentscient-87, writes no test). Checked once by Codex
(check-tests), implemented by the S3 builder, reviewed by Grok and Codex.
Withheld: implementation. None exists; read none.

Contract: `ops/conductor/sessions-lever.md` at the ref given, "Slice 3
— Dispatcher integration" (lines 511–739 at 0c54f658): the
follow-through paragraph at 650–664 (`dispatch_events.py route`, the
event words `completion` and `no-op` → inform, `invalid` and `death` →
finding, the rest acked and never sent; the per-pass config under the
state directory naming the launched record ids, `monitor.py run --once`
then `digest`; `send --key event:<event id>:<recipient>`; the ack after
the batch), fixture 9 and the third clean neighbour at
684–739; and slice 2's `send_requests` and `send --key` at 356–371 for
the key it relies on. Read `docs/tests.md`, `ops/testkit/`,
`ops/conductor/monitor-lever.md` (the digest event shape and `--ack`),
`ops/conductor/coordination-lever.md` (message facts) and
`ops/conductor/tests/test_courier.py` as the worked example of a suite
over a pass that reads and sends.

Write `ops/conductor/tests/test_dispatch_events.py` on the kit: `World`
hermetic, every subprocess through `run` with a timeout, the fake
`fakes/dispatch_digest.py` (new, yours: stands in for `monitor.py`;
`run --once` takes the per-pass config and logs its ids, `digest`
answers events by spec, `--ack` calls logged as JSON lines) planted
through `Tools`, an intent row planted through `dispatch_intents.py`
(never by hand in the store), rows by id with
`origin: sessions-lever.md#slice-3 9`. No program embedded in the test
module (rule 6).

Names the code uses (contract, "The programs it runs"): the fakes are
planted at the paths the keys `DISPATCH_WRAPPER`, `DISPATCH_LAUNCHER`
and `DISPATCH_MONITOR` name in the world's environment (defaults
`ops/conductor/tools/dispatch.sh`, `ops/devlane/dispatch/launch.py`,
`ops/conductor/tools/monitor.py`; each an argv, no shell); a key naming
a non-executable refuses `launcher` (wrapper, launcher) or `store`
(monitor); `DISPATCH_CAPACITY` default 6; the jobs root `$DISPATCH_JOBS`
else `$XDG_STATE_HOME/<lane>/dispatch`; `verifications.json` read from
the repository root; the scope file at
`<state dir>/dispatch-intents/DI-n/scope.txt`.

Rows: a `completion` event for a launched intent → one `inform` to the
assignment's holder carrying the record id and the exit, one ack, and
the config the fake received naming that record id; `death` → a
`finding` to the Dispatcher and to the holder; `running` → acked, no
message; the same digest
served twice → no second message (the message count by `send --key`);
a send that fails because the world holds the store's write lock → no
ack logged and the messages absent; an event for a record with no
intent → acked, no message; `--once` returns after one pass. A pin on
a count the contract does not own is a finding. Report `reused:` names
in the job note.
