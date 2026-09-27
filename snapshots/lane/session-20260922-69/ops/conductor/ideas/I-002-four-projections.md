# I-002 — four projections of one service: CLI, TUI, MCP, API

- recorded: 2026-09-03, minutes after I-001
- source: owner, verbatim below
- disposition: ratified — `AGENTS.md` §Standing rulings, second bullet; register row D-SYM-2

## In the owner's words

> this about providing cli, mcp and api resources.

> and probably a TUI (symfony has a lib for that too)

## What was heard

Superseded 2026-09-16 (D-MCP-1): MCP acts as well as reads.

One service per capability; a Console command, a TUI view, an MCP
resource, and an API resource are views of it, generated from the same
contract. The wire holds on all four. MCP stays the read-only context
plane; the CLI and the API act. The TUI is the conductor's seat, live
through Mercure.

## Standing facts it must reconcile with

- `symfony/tui` exists: v8.1.6 on Packagist, experimental, outside the BC promise, no documentation page found — measured 2026-09-03; its API is unmeasured and the first TUI unit begins by measuring it.
- `symfony/mcp-bundle` 0.13.0 builds on the official `mcp/sdk` 0.8.1; `api-platform/mcp` exposes API resources over MCP — measured 2026-09-03.
