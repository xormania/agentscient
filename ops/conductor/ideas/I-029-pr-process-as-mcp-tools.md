# I-029 — the PR process formalized: custom MCP tools that enforce it, and GitHub issues and discussions for agent coordination

- recorded: 2026-09-13, in session, after PR #175 merged (dev `4fdc6d0e`)
- source: owner, verbatim below; the day's measurements by Claude Fable 5.1
- disposition: open; on the owner's to-do list, the owner's own intention, recorded so it is not lost

## In the owner's words

> its on my to-do list - i want to formailze the PR process better. I will, just record that i intend to - add that i think the whole process should be available as custom MCP tools the enforce the process of getting a PR constructed, reviewed, and merged - also that we can use github issues and discussions (by we - i mean agents co-ordinating)

And the same day, the ruling the process must carry: "a draft PR should never be marked for review unless it can be merged immediately" (CONTRIB §Draft first; LD-32).

## What the day measured, as input to the design

- The PR path today is prose plus hooks: CONTRIB's four headings and ready table, the pr-proof row on the merge verb, the trunk-commit row, the trailer gate. Each step is a session reading a page and typing commands; PR #175 took a ready note, a refused merge, a proof section added after the fact, a corrected corpus row, a second ready note, and five CI rounds for one branch.
- The gate is asymmetric: ready passed without the proof the merge demanded (LD-32).
- Guard rows scan command text, so a heredoc that quotes a verb in prose is refused as if it ran it (pitfall 27, LD-32).
- Coordination between sessions is by record files that collide: two sessions appended to the same two tables and PR #175 went DIRTY, with no CI run until dev was merged forward.

## The shape the owner names

- The whole path as MCP tools, each a lever with a contract and the refusal wire: construct (branch from the trunk, lock, work order), open (draft, body from the template, proof rows), review (the two-harness verdicts pinned to a head), ready (the merge's own gate applied early, refused when any row would refuse the merge), merge (no squash, no delete; settle the grants, lift the lock). The tools act; the current lane MCP stays read-only, so this is a separate, deliberately admitted writable surface (the standing MCP ruling and the conductor start plan both say a writable conductor tool needs its own admission).
- GitHub issues and discussions as the coordination plane between agents: work orders and findings as issues, session-to-session threads as discussions, so two sessions do not learn of each other by a merge conflict in a records table.

## Standing facts it must reconcile with

- MCP is the context-and-diagnostics plane, read-only by construction (AGENTS.md §Standing rulings; `ops/conductor/lane-mcp-lever.md`); an acting surface is a new contract.
- No producer owns two consecutive artifacts; a tool that constructs and merges must still hold the two-reviewer seam.
- The wire: every refusal expected–found–needed; ready and merge refuse with the same reading.

## Next

The owner's to-do; not scheduled here. A scope is settled with the owner before any plan.
