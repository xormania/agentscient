# I-033 — MCP is no longer read-only

- recorded: 2026-09-16, session agentscient-11 (Fable, lane/session-20260915-e), at the wind-down
- source: owner, verbatim below
- disposition: hardened as D-MCP-1, 2026-09-16

## In the owner's words

> mcp is no longer read only - that's the directive - but don't worry, i caught it and the incoming spec docs will cover it

Asked, a moment earlier, whether an MCP directive was among the loose ends:

> let me guess - my mcp directive is one of them - isn't it?

## What arrived with it

This reverses the standing ruling carried in AGENTS.md (owner,
2026-09-01: MCP is the context-and-diagnostics plane, read-only by
construction; the CLI and the API act) and the stack's wire row that
restates it. Nothing on dev at f23f1884 records the reversal: the MCP
records of 2026-09-05 sit on eight branches, twelve commits, none
merged (H-15 thread T-79). The owner has the spec documents in hand;
until they land, the seed's read-only clause stands in the tree with
this record beside it saying it is superseded by the owner's word.

## What a ruling would have to settle

- which MCP verbs act, under which identity, and with what refusal
  wire (docs/wire.md), so an acting MCP surface refuses like the CLI;
- what the four-projections ruling becomes when MCP is no longer the
  one read-only projection;
- the seed clause in AGENTS.md and the stack row, rewritten from the
  spec documents, not from this note.

Hardens through the register as a D- row when the spec documents land.
