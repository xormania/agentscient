# Builder briefs, 2026-09-16: classes 8, 1, 4, 5 of the day's twelve issues, and the strict-kit sweep

Planner: agentscient-0d (Claude Fable 5.1), lane/session-20260916-h, at the Lead's assignment (agentscient-11, 09:15Z) under the owner's words: "give it the important shit to fix that stops wasting agents' work". Input: the planner's record 20260916T085626Z-review-claude-30f3eb (its plan in the envelope's note field, Part 1 classes by mechanism, Part 2 slices) and the issues report in that record's `in/`.

| slice | class | builder | brief |
|---|---|---|---|
| S1 classifier-edge | 8 | agentscient-0d, by hand, this branch | commit on this branch: harness-capabilities.md, probes-2026-09-16-classifier-edge.jsonl, the refused skill, CONTRIB.md |
| S2 ledger-id-reservation | 1a | an Opus session | S2-ledger-id-reservation.md |
| S3 measure-as-argv | 4 | an Opus session (first to free) | S3-measure-as-argv.md |
| S4 lock-on-the-engine | 1b | an Opus session, after S3 | S4-lock-on-the-engine.md |
| S5 wrapper-hermetic-store | 5 | agentscient-c8 | S5-wrapper-hermetic-store.md |
| S6 ambient-sweep | strict kit | an Opus session (driver), agentscient-c8 and an Opus session (families) | S6-ambient-sweep.md |
| S7 rg-not-grep | 8, the tool side | agentscient-c8 after S5, by hand; the wall half is W4 | S7-rg-not-grep.md |

Wall items W1 (file-state admits a job's declared outputs), W2 (MCP matchers, anchored: the current one is an unanchored regex, see harness-capabilities.md), W3 (security audit before ready), W4 (graft-first and clipped-sweep judge rg exactly as grep, with the hook tests for the S7 lever) are the Lead's wall queue; their faults and neighbours are in the plan message of 09:33Z and in S1's commit.

Each brief carries a `## Scope` section under 1024 bytes (SCOPE_CAP) for `--scope-file`; the whole brief goes as `--input`.

Dispatching (owner, 2026-09-16, relayed by agentscient-11 at 10:27Z: from now no session runs dispatch.sh itself; every dispatch goes through agentscient-2d, the Dispatcher). A session sends the Dispatcher the job and stage, the harness, its worktree path, the head sha and the absolute path of a scope file it wrote under 1024 bytes; the Dispatcher replies with the record id and pid; the record lands in the session's worktree and the session imports and reports the findings. The shape the Dispatcher runs, measured 2026-09-16 on lane/session-20260916-h before the rule (records 20260916T094142Z-review-codex-995043 and 20260916T094152Z-review-grok-e72972): `security-audit`, `adversarial-review`, `author-tests` and `implement` are all judged dispatch-by-hand; `ALLOWED_BY_HAND` in ops/devlane/hooks/claude/matrix.py names only plan, adjudicate, sweep and verify. The row lifts only for an open unscoped grant whose id is the first token of the whole Bash text, so one dispatch per call: `HAND_GRANT=<id> WF_AGENT='Name <addr>' env -C <worktree> <worktree>/ops/bin/dispatch.sh --job <job> --harness <harness> --scope-file <absolute path> --branch <branch> --agent 'Name <addr>' --detach`. A `wc -c` or any other statement before the id hides it (the shape of pitfall 27) and the row refuses; the refused skill's row names only the two write jobs. The dispatcher stamps `--ref <head sha>`, so the review reads the pushed head and a later push voids it.
