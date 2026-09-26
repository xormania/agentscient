# Progressive MCP entry for live development

`tools/dev_mcp.py` projects existing coordination and evidence services through
three MCP tools: `capability_search`, `capability_describe`, and
`capability_invoke`. It owns no domain state and needs no Symfony kernel or
application dependencies. The initial tools/list payload is 1,154 UTF-8 bytes
with compact JSON; the transport bounds whole responses at 16,384 bytes.

Live communication between persistent harnesses is the default. The standalone
dispatch adapter remains available only for an explicit owner request. The
new entry neither advertises nor invokes its launch, wait, status or collect
operations. Reading historical evidence does not launch work.

## Start and use

The existing session launcher must supply its normal trusted participant
context. An MCP request cannot bind itself, choose a role or supply an identity.
The entry uses the same private capability verification as coordination_mcp.

```sh
python3 -B ops/conductor/tools/dev_mcp.py check
python3 -B ops/conductor/tools/dev_mcp.py serve
```

`--binding FILE` optionally narrows capabilities and names the expected
participant using the existing coordination binding shape. A binding file does
not replace the session's private capability. `--evidence-config FILE` accepts
the existing lane_mcp configuration; without it, evidence capabilities describe
their missing configuration and messaging stays usable. Options precede the verb.

Search returns at most ten capability cards, with `next_offset` for further
pages. Describe returns one complete input schema. Call that schema through
`capability_invoke` with `capability` and `arguments`; returning a schema as data
does not install a native host tool. Describing availability reports configured
access, not authentication, successful invocation, or native readiness.

For a peer exchange, discover `coord_participants`, then describe and invoke
`coord_send`. Use a stable `key` when retrying the same message. Recipients use
`coord_inbox`, `coord_ack`, and `coord_resolve`; the core still requires a valid
evidence reference for resolution. `coord_routes` and `coord_attempts` inspect
existing courier state and native submissions. A send queues a durable message;
it does not claim the recipient received, acknowledged or resolved it. The
existing sessions/courier services must be running for native delivery.

Caller-provided authority, unknown arguments and unknown capabilities refuse
before invocation. Oversized message responses preserve the committed message
identifier so callers can retry with the same key or inspect its durable record.
Oversized request IDs refuse before a write. Resources cannot invoke mutations.

## Validation and remaining work

`test_dev_mcp.py` drives real stdio against the existing coordination store in
isolated test worlds, including peer exchange, binding denial, retry identity,
dispatch exclusion, pagination and response bounds. It belongs to the CI profile.

This adapter does not restrict native harness tools or prove live delivery.
Profile wiring, Serena v2 REPL, project actions, Mate, custom Makers and the
three-harness local acceptance remain stages of
[the readiness handoff](../../docs/dev-lane-mcp-readiness.md). The legacy
coordination and evidence server entry points remain compatible.
