# Handoff — Codex dev-lane closeout, 2026-09-05

Measured 04:31 UTC against dev `fbdbacfe0ed956fc7f8e65b222d0a7df41886f8f`.
This supersedes the old 2026-09-04 Codex machinery checkpoint. Start here;
do not ingest that checkpoint or archived WIP as live instructions.
Full reasoning: [system AAR](../AAR-2026-09-05-codex-closeout.md).
These closing records live on retained branch `records/codex-closeout-20260905`,
not yet merged into dev. No extra report-only PR was opened.

## State to inherit

- PR67 merged into dev at `fc959ca2ef3be204853cf3c93488d2d8f4e50ecb`.
  PR68 merged at `fbdbacfe0ed956fc7f8e65b222d0a7df41886f8f`.
  Both candidates were fully green; post-merge dev CI 33944639089 is green.
  GitHub open-PR list was empty. All branches retained.
- Owner merged release PR66 into master at `5a202ddf02707d741893e172685b3c748a9fdf4c`.
  PR67/68 are newer dev work, not another release authorization.
- Main checkout is still `c715b24aaea4bf040b2bf63021b59125474e1485`, with only
  the owner's untracked `.dev/wip/`. Do not clean it, overwrite it, or switch
  it blindly: those paths are now tracked upstream. Use a new worktree from
  origin/dev for the next slice. All 25 imported capture blobs match `138e009`.
- Seven final dispatches are closed. No implementation/review worker from this
  final batch remains active. Background watchdog and monitor remain running.
- Owner disabled all rulesets; they remain disabled. Do not silently restore them.
  Rust CodeQL is AVAILABLE BUT DISABLED by owner choice; Actions analysis remains
  enabled. Prior Rust run 33944056469 succeeded. Do not re-enable it without need.

## Operating posture

Dev-lane machinery first, not Symfony application work. Grok does QUALITY;
Daybreak high does SECURITY. Dispatch only through ops/bin/dispatch.sh or go.sh.
No in-session subagents. Separate implementation and test producers; root judges
the oracle. Reports belong in PR comments. Draft first, green and stationary
before ready, merge commits into dev only, never delete branches. Owner alone
merges master. Exact model attribution and Source trailers on every commit.

Functionality first; do not chase P3s or blindly promote every P2 to a merge
blocker. Captured logs/records/data stay verbatim. Authored code/docs/PR prose
must not introduce private account identifiers. Use relative authored paths.
The term wall now distinguishes archive content from authored content, but still
checks every tracked path and the archive README.

## Live machinery (remeasure PIDs before acting)

| Component | PID at close | Retained worktree / code |
| --- | --- | --- |
| K9 watchdog | 4079824 | `../wt/ag-pr66-fixes.oKulon`, `925d88b` (merged code) |
| Condition monitor | 3262024 | `../wt/ag-monitor-machinery.cNp4OT`, `1f70396` (merged code) |
| MCP server | client-started stdio | `../wt/ag-lane-mcp.TH2iy7`, `eb4eb53` (merged code) |

K9: tick 30s, forge every 10 ticks, heartbeat every 2. New census observed four
concurrent workers correctly. Startup historical deviations are not fresh bugs.
The old K9 PID3093326 was stopped after its replacement was verified.

State-root-relative files:
- `mcp-codex-20260904/config.json`: explicit source paths and seven selected ids.
- `monitor-codex-20260904/config.json`: 3 monitors, 2 schedules, 7 conditions/routes.
- `monitor-codex-20260904/state`: existing durable queue/state; do not reset.
- `dispatch/ID/record.json`: canonical evidence; captures are not instructions.

Monitor local cadence=30s, GitHub=300s; consumer `codex-machinery`. Conditions:
job changes, context >75%, cache <80%, quota remaining <20%, and unavailable
sources. Configuration reloads while the monitor runs. Add/change/remove named
entries in its owned config; check it before relying on changes. No model per
tick and no idle-session wakeup integration. Processes are not boot-managed.

## MCP use, change, removal

The vendor-neutral read service provides lane_brief, lane_record, lane_alerts
and lane_usage, plus matching resources. Codex is only one configured client.
Its global entry is named `agentscient_lane`. Inspect with:

```sh
codex mcp get agentscient_lane --json
```

The entry reveals the resolved runtime locations without hardcoding a host
account in this runbook. A fresh Codex app-server using the saved entry discovered
all four tools with zero model turns. A real stdio brief returned state=ok;
a following ping succeeded. Existing chat sessions are not claimed to gain
tools automatically; start a new client/session if needed.

Use brief first, individual records only when needed, usage on demand. Read
cursors never acknowledge monitor messages. Source configuration is read once
per MCP process; restart the client/server after changing it. The monitor's
configuration reloads independently. For a new conductor session, explicitly
select its own rollout and current job ids in both configs; the closing config
still watches this session. Do not enumerate other users' sessions.

To remove only this client connection:

```sh
codex mcp remove agentscient_lane
```

No project code or other Codex settings depend on that entry. Unrelated Codex
configuration was verified unchanged after registration. General client setup:
[official MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

## Do not reopen as current blockers

The contract explicitly records oversized-integer transport/usage failures,
SQLite cursor overflow, and manually planted non-finite alert evidence.
Root reproduced and deferred them as P3 under the owner risk model. Do not claim
blanket malformed-input safety; reassess before remote or untrusted-source use.
The prior _meta, worst-case brief sizing and registry-docstring P3s also remain.

PR66's four conversations are resolved, including an explicitly deferred P3.
No fresh resume isolation proof was delivered. Optional front-door implementation
`02d0a8656759d19752f88c24732f2eff384a0356` and contract
`0b374802a9335c0d300f568d022ad4b364406989` remain reachable and unlanded.
Do not silently include them in a new PR.

## Next-session choices, not automatic work

Ask the owner which functional slice comes next. The branch census points to
targeted diffs, not bulk merges:

1. `lane/check-tests-json` at `fe2e474`: salvage write-path/envelope leftovers,
   but its old stdout-only skeptic direction conflicts with current contracts.
2. `lane/fixture-fix-2` at `d42ffb1`: tracked copy-list and remaining fixture pins.
3. `lane/session-budget` at `eb14e0a`: branch ceilings differ from archived scope.
4. Tests-only/context candidates: dispatch-job-scratch, context-contracts,
   record-wall, noguess. PR10 workflow stays intentionally parked.

Grok's [recovery report summary](https://github.com/uscient/agentscient/pull/67#issuecomment-5549302453)
states census limits. Full raw report: dispatch
`20260905T020420Z-review-grok-2327f1/out/RECOVERY.md`, unchanged.
The corpus did not establish every unreachable object or merge-resolution delta.

Testing philosophy and conductor cost deserve the next discussion: reuse small
fixtures, separate producers, bounded evidence, explicit elapsed/token budgets,
and context caching. The final seven workers alone used 8,451,032 cumulative
tokens; a 200-line oracle took nearly ten minutes. Better machinery should reduce
that overhead, not create an endless suite/review loop.

## Evidence and custody

[Closing measurements](evidence-2026-09-05-codex-closeout.json) carry final heads,
tests, worker usage, runtime process ids and the no-model MCP discovery result.
PR comments contain reviewer reports and root adjudications; captured originals
were not rewritten. Remaining holdings above are explicitly left behind, not
claimed complete. Re-measure remote refs, jobs and processes before new actions.
