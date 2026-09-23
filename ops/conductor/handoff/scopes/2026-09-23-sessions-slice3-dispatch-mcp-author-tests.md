# Scope: author `test_dispatch_mcp.py` for sessions slice 3

Job: author-tests. Producer: Grok (the contract's author, Claude Fable
5.1, agentscient-87, writes no test). Checked once by Codex
(check-tests), implemented by the S3 builder, reviewed by Grok and Codex.
Withheld: implementation. None exists; read none.

Contract: `ops/conductor/sessions-lever.md` at the ref given, "Slice 3
— Dispatcher integration" (lines 511–739 at 0c54f658): the MCP
paragraph at 642–649 (`dispatch_mcp.py`, the four tools
`coord_launch`, `coord_status`, `coord_wait`, `coord_collect`, the
standalone entry), the refusals at 658–674 and fixture 11 at 684–739.
Read `docs/tests.md`, `ops/testkit/`,
`ops/conductor/coordination-mcp-lever.md` (the tool shape, the error
result, the binding) and `ops/conductor/tests/test_coordination_mcp.py`
as the worked example of a suite speaking MCP over stdio to a standalone
server.

Write `ops/conductor/tests/test_dispatch_mcp.py` on the kit: `World`
hermetic, the server spawned through `run` with a timeout (or the kit's
owned child when a live stdio exchange is needed), the same
`fakes/dispatch_wrapper.py` and `fakes/dispatch_launch.py` planted
through `Tools` (owned by `test_dispatch_actions.py`'s scope; extend,
never fork), rows by id with `origin: sessions-lever.md#slice-3 11`,
`refusal_wire` on the CLI-side rows and the error result's class token
on the MCP-side rows. No program embedded in the test module (rule 6).

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

Rows: `tools/list` names the four with `coord_launch` and
`coord_collect` marked as mutations; `coord_launch` by a bound
dispatcher holding the machine writes the same intent row the CLI
writes and returns `DI-n` with the record id; the same key twice returns
the same `DI-n`; a worker's `coord_launch` returns the error result with
`role`; a non-holder's with `holder`; `coord_status` needs no identity;
`coord_wait` on a not-clean fake reading returns the reading, not an
error; `coord_collect` with an unknown name returns `verify` and the
fake `launch.py` log stays empty. The server runs without the
`CATALOGUE` registration line. A pin on a count the contract does not
own is a finding. Report `reused:` names in the job note.
