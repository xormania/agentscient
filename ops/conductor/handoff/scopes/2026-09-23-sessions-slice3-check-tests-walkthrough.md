# Input: check the tests for managed sessions, slice 3

Readings taken 2026-09-23 by the contract session (agentscient-87,
Claude Fable 5.1) against lane/session-20260923-87 at 5e41f41c and
this host. One pass, fixed once, no re-check (owner, 2026-09-23:
"practical issues, not theoretical").

## First-run walkthrough

- assumption: the contract is in the tree. Measured: the section
  "Slice 3 — Dispatcher integration" is `ops/conductor/sessions-lever.md`
  lines 511–739 at 0c54f658, on slice 2's section at b9bc1444.
- assumption: no slice 3 implementation exists. Measured at 5e41f41c:
  `ops/conductor/tools/dispatch_actions.py`, `dispatch_intents.py`,
  `dispatch_mcp.py`, `dispatch_events.py`, `ops/conductor/verifications.json`,
  `ops/conductor/monitor.dispatch.json` and `tests/fakes/dispatch_wrapper.py`
  are absent; `launch.py` and `dispatch.sh` carry no `correlation`.
  Every row stays red on its own assertion, never on import or setup.
- assumption: the real launcher may run in a row. Refusal: the contract's
  Tests section says no live launcher runs in the suite; a row that
  calls `ops/conductor/tools/dispatch.sh` or `launch.py` itself, not the
  planted fake, is a practical finding.
- assumption: the kit binds. Measured (docs/tests.md): `from
  ops.testkit import World, run, refusal_wire`; fakes through `Tools`;
  every subprocess through `run` with a timeout; a program embedded in
  a test module is a finding the wall refuses at CI, so it is practical.
- assumption: the event words are the launcher's job states. Refusal:
  the contract at 0c54f658 said `finished`, `closed`, `tripped`, `DIED`;
  the amendment that follows it uses `monitor.py`'s dispatch metric
  words (`completion`, `no-op`, `invalid`, `death`, `settling`,
  `running`, `unknown`), and a row on the old words is a practical
  finding.
- assumption: the event rows can rely on `send --key`. Measured at
  5e41f41c: `coordination.py` has no `--key`; the rows plant the slice 2
  behaviour through the fake store call or stay red on that assertion,
  and the note says which.
- assumption: grok can claim the assignment through the store. Refusal:
  `launch.py:640 COORD_MCP_HARNESSES = ("codex",)` at 5e41f41c; the note
  says the claim was not possible and the XO settles the store.
- assumption: findings are requirements. Refusal: practical means a row
  cannot fail, does not execute the subject, pins a count the contract
  does not own, embeds a program, or reaches outside the world; style
  and theoretical faults are recorded and declined.
