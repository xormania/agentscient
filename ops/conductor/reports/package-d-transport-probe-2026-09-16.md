# Package D — what the durable chain already does, and what it does not

Measured 2026-09-16 against `8ffee840`, driving the acting MCP server and
the coordination core over a real store in a scratch `XDG_STATE_HOME`.
Nothing outside the scratch root was written. This is a reading, not a
plan: the plan is the Fable session's on #245, and this exists so it is
written against measured behaviour rather than assumption.

## The chain that exists

Two participants bound through the core's own `bind`, one lead and one
worker sharing an agent string, then the worker's question carried
through the acting server:

| step | surface | reading |
|---|---|---|
| `coord_send` | the acting MCP server | exit 0 in 46 ms, message `M-1` queued |
| `coord_inbox` | the acting MCP server | exit 0 in 35 ms, the lead's inbox carries it |
| `deliver` | the core's CLI | exit 0, `delivered M-1 ref msg_id-from-a-native-send` |
| `coord_ack` | the acting MCP server | exit 0 in 35 ms |

The four facts the core keeps apart, read back after the run:

```
M-1 request from PT-2 to PT-1: the worker's in-progress question
queued       2026-09-16T10:59:32.275447Z
delivered    2026-09-16T10:59:32.353738Z ref msg_id-from-a-native-send
acknowledged 2026-09-16T10:59:32.394288Z by PT-1
```

Queued to delivered, 78 ms; delivered to acknowledged, 41 ms. Those are
the separately measured readings AC-08 asks for, and they are real: each
is a stamp the core wrote, not an interval this probe timed around its own
calls.

## What is missing, named exactly

**Nothing carries a queued message to a session.** `deliver` takes a
`--ref` its caller supplies, so the transport receipt above is a string
this probe invented. The durable half of AC-08 is built and the delivery
half is not: a message sits in the store until something reads it and
sends it.

That is the whole of package D's first slice, and it is one component:
something that watches for queued messages whose recipient is a session
it can reach, sends over the native cross-session transport, and records
`deliver` with the transport's own id. Until it exists, "queue insertion
alone fails this criterion" describes exactly where this lane stands.

## What the transport gives, measured from this session

- A send returns an id: the cross-session tool answers with a `msg_id`,
  which is the value `deliver --ref` should carry rather than an invented
  string.
- **A send is not a receipt.** The tool's own answer says the message is
  queued at the receiver and that a delivery notice follows only if that
  session holds or refuses it. A session in a different permission mode
  holds peer messages for its user, and may let them expire. So `queued`,
  `delivered` and `acknowledged` are three facts here for the same reason
  the core keeps them apart, and a route that collapsed them would be
  claiming receipt from a send.
- The transport's own environment reaches a project-registered MCP server:
  `CLAUDE_CODE_MESSAGING_SOCKET` and `CLAUDE_CODE_MESSAGING_TOKEN` were
  measured in one on 2026-09-16, beside `CLAUDE_CODE_SESSION_ID`.

## The open question this leaves for the plan

A dispatched Codex or Grok worker has no native messaging of its own, so
the cross-harness half of AC-08 cannot be a worker sending: it has to be
the worker writing to the store through the acting server, exactly as
above, and the deliverer carrying it. That makes the deliverer the single
point where a cross-harness event becomes a session's notification, and
the place every latency reading in the acceptance criterion is taken.
