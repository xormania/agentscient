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

## The live run, 2026-09-16, with the courier carrying it

Two participants, two session ids, one host, a scratch store. The lead
armed `courier.py watch --tick 2` as a session arms a Monitor, and the
worker asked its question through the acting MCP server *after* the
courier was already watching, so these are a real wait and not a replay.

```
the worker asked through the acting server: M-1
the line reached the lead's session after 1041 ms, tick 2s:
  2026-09-16T11:09:48.884560Z M-1 request from PT-2: may I change the contract's section 6?

queued       2026-09-16T11:09:47.886495Z
delivered    2026-09-16T11:09:48.884628Z ref courier:2026-09-16T11:09:48.884560Z:M-1
acknowledged 2026-09-16T11:09:49.955375Z by PT-1
```

Queued to delivered, 998 ms against a 2 s tick. Delivered to
acknowledged, 1071 ms. The printed line's stamp and the stored receipt's
are 68 microseconds apart and the ref carries the line's own stamp, which
is what "the line a session reads and the stamp the store keeps are one
event" means when it is measured rather than asserted.

`acknowledged` was absent until the lead's own `ack` ran. Nothing the
courier does writes it, which is the point: delivery is the transport's
fact and acknowledgment is the recipient's.

## What the live run found in the courier

The first run of this measurement showed `queued` and **no** `delivered`
stamp, although the line had printed. The cause was the run's own
impatience — it terminated the courier in the window between the print
and the receipt — and it is worth recording because it demonstrates the
property rather than a defect:

**The courier is at-least-once, not exactly-once.** It prints, then
records. A courier stopped between the two leaves a line a session has
seen and a store that does not know it, and the next pass carries that
message again, because the filter is `delivered_at is None`. A repeated
line, never a silent loss. The other order — record, then print — would
stamp a delivery no session ever saw, and nothing would ever carry it
again. That is the failure worth preventing, so the order is deliberate
and the tool's own comment now says so.

## The calibration, and one declared gap

Each fault planted in the tool, the suite run against it:

| planted fault | caught by |
|---|---|
| prints but never records the delivery | 3 cases |
| carries the whole inbox, delivered or not | 1 case |
| acknowledges while delivering | 1 case |
| carries every participant's messages, not its own | 4 cases |

And the gap the calibration found, declared rather than discovered later:
`undelivered()` has two paths, the core's own `undelivered` verb and
`inbox` filtered on `delivered_at`. The core at b1d868b0 has no such
verb, so the first path is unreachable today and a fault planted in it
was caught by nothing. The cases exercise the path that runs. When
package B lands the verb, the calibration is re-run against the other
path before it is trusted.
