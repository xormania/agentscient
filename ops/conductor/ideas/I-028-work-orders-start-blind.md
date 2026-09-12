# I-028 — every work order starts blind; connect the read plane that already exists

- recorded: 2026-09-12, in session, while measuring token waste
- source: owner, verbatim below; measurements by Claude Fable 5.1 against dev `7ca8886`
- disposition: open; the owner asked for "close enough to functioning" between hooks and MCP; proposed as the next hand change after the effort and turn-cap change (grant 155)

## In the owner's words
> do you see the issue? every work-order works in isolation from the rest of the code - its doesn't use any previous work, it works blind.

> I need something here. between hooks and mcp - can't we get this close enough to functioning?

## What was measured

- Two days of dispatches (2026-09-10 to 2026-09-12): Grok 64 dispatches, 149M tokens; Codex 62, 112M; Claude 17, 31M; nine tenths of every figure is cache reads of the worker's own growing conversation.
- One Grok test author (record `20260912T001007Z-tests-grok-a76b8a`): 23 minutes, 393 messages, 109 tool calls, 26 patch edits (twelve on one file), 7.7M tokens, four test files produced. It read forty files to write four, starting from nothing.
- The per-job effort lever (`EFFORT_<HARNESS>_<JOB>`, PR #20, 2026-09-04) sat unused for eight days: the tracked conf set only per-harness rows. No work order since knew it was there.
- Lane MCP v2 (admitted 2026-09-05, seven read tools: brief, alerts, usage, record, findings, changes, jobs) has tests and zero references in `ops/devlane/dispatch/launch.py`: no worker has ever been connected to it.
- The onboard lever (`ops/conductor/tools/onboard.py`) runs for the conductor after compaction and never for a worker.
- Graft is prepared for code workers and withheld from test authors by design (`brief.graft.state = withheld`).
- Hooks reach Claude workers only, through the snapshot's project settings; Codex and Grok have no hook surface of the lane's.

## The proposal, cheapest first

1. Prepend a worker cut of the onboard brief to every worker prompt: the levers that exist, the lane.conf keys, the jobs, the ideas index, the last handoff's "corrections to retain". A launcher change; the lever exists.
2. Attach the lane MCP to each worker at launch: Claude by `--mcp-config`, Codex by a `-c mcp_servers` override, Grok by its config file; one config file per dispatch, the server is already built.
3. One clause in every job prompt: before building, look up what exists (the brief, `lane_jobs`, `lane_changes`, the code map) and say in the envelope what was found and reused. Without the clause a worker with the tools still starts blind.

What this does not do: it does not make reuse a verified edge. That is the declared graph the owner's prod-lane insights are about ("graphs and contracts"), and it waits for the prod lane by the owner's word.
