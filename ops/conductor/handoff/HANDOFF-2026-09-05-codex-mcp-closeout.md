# Handoff — Codex MCP closeout, 2026-09-05

Measured 2026-09-05T22:39:00.218086+00:00 at dev `c06ed9442ba51c9e96aa8de9f9bde93d0843a6cc`.
This supersedes this session's earlier statements that PR72 was unmerged.
[Full AAR](../AAR-2026-09-05T22-codex-mcp-closeout.md) ·
[commands and measurements](evidence-2026-09-05-codex-mcp/measurements.json).

These closing records live on retained branch
`records/codex-mcp-closeout-20260905`, in
`../wt/ag-closeout-mcp-20260905`. They are not merged into dev; no report-only
PR is being opened. The next session should read this record explicitly.

## Read this first

1. PR70 (README), PR71 (release) and PR72 (MCP reads and cap correction) are
   all MERGED. PR72 merged at `c06ed94` on 22:24:46Z, after the session left it
   green and unmerged. No open PRs were returned at close. All PR71/72 review
   threads were resolved. Recheck GitHub before acting; this is a timestamped
   observation, not a promise about the next session.
2. Dev is `c06ed9442ba51c9e96aa8de9f9bde93d0843a6cc`; master is
   `0b1f1b68dc95e60cfeb458fe8ae956506f59af9c`. Post-merge dev CI
   [33995834974](https://github.com/uscient/agentscient/actions/runs/33995834974)
   and CodeQL [33995834945](https://github.com/uscient/agentscient/actions/runs/33995834945)
   succeeded. There is no new dev-to-master release PR. Owner alone merges
   master; the prior release instruction was fulfilled by PR71.
3. The main checkout remains `c715b24aaea4bf040b2bf63021b59125474e1485`, with
   only the owner's untracked `.dev/wip/` in short status. Do not update,
   switch, clean or overwrite it. Upstream contains paths under that directory;
   use a new owned worktree from freshly fetched origin/dev for new work.
4. No correction worker needs resuming: all five correction dispatches have
   accepted terminal envelopes. Old AAR queues and PIDs are historical. A
   close-time scan found no processes at the documented watchdog/monitor
   script entrypoints. Alternate entrypoints and unrelated actors were not
   inventoried; do not blindly restart machinery or reset its state.
5. The saved MCP host connection is still v1 and its connected brief call
   failed. The code is merged; host activation is not complete or claimed.
   The operational follow-up below is the most useful thing to inspect before
   relying on the new tools. The owner has not selected the next feature task.

## MCP state and operational follow-up

Implemented in `ops/conductor/tools/lane_read.py` and `lane_mcp.py`:

- v1 keeps `lane_brief`, `lane_record`, `lane_alerts`, `lane_usage`.
- v2 adds `lane_findings` pages, caller-held `lane_changes` checkpoints and
  `lane_jobs` cards, with resources/templates. `_meta` objects are accepted.
- Named cards work when a readable registry has more than 64 entries; only
  unnamed listing has the 64-entry cap. Fix `67e0bc0`, regression in
  `TestLaneMcpContextJobs.test_lane_jobs_named_card_at_sixty_five_entries`.
- MCP is read-only, local and bounded. It does not dispatch jobs, acknowledge
  monitor state, fetch GitHub, wake idle models, or prove live PR readiness.
  No Symfony API/TUI twin or new dependency was added.

Authoritative design: [v2 contract](../lane-mcp-v2.md),
[v2 config example](../lane-mcp-v2.example.json),
[baseline contract](../lane-mcp-lever.md). Configuration selects sources and
job IDs explicitly; a missing source is not silently discovered elsewhere.
The server reads configuration at process startup.

At close, `codex mcp get agentscient_lane --json` showed the existing enabled
stdio entry, a version-1 configuration and seven selected `job_ids`. The
configured entrypoint's worktree was at
`eb4eb53def151d419a0b37b35fcf629204d90f91`. This session advertised only the
four v1 tools. A connected `lane_brief` call returned `MCP -32602 Invalid
params`; running the saved entry command as `query lane_brief {}` instead of
`serve` exited 0 and returned state `ok`. The host error's cause was not proved.
The old entrypoint predates the merged request-metadata support, so compare
its request handling with current dev before assuming a data-source failure.

A useful next-session diagnostic sequence, subject to the owner's next task:

1. Inspect the saved entry and resolve its runtime/configuration paths through
   `codex mcp get agentscient_lane --json`. Keep private paths and environment
   values out of authored reports.
2. Inspect the actual connected request/response and reproduce the refusal.
   Compare the old runtime with current dev's metadata handling. Code passing
   fixture tests does not prove the host has started that code.
3. If updating the connection, choose a retained runtime checkout and explicit
   source configuration. v2 additionally needs `job_registry`; use the example
   and `lane_mcp.py --config FILE check`. Do not point at a disposable snapshot.
4. Restart the relevant client/server, then verify tool discovery and real
   CLI/tool/resource parity. Expect seven tools only with a v2 configuration.
   Record actual host results before claiming activation or context savings.

No host entry, configuration, daemon or monitor state was changed during this
session. The exact host configuration remains private local state, not an
artifact to copy into the repository.

## Evidence to use without rereading every log

| Evidence | Location / immutable ref |
| --- | --- |
| Research, source boundary and fourteen candidates | `ops/conductor/MCP-RESEARCH-2026-09-05.md` and `reports/mcp-research-2026-09-05.json` on dev |
| Contract admission, failed attempts, independent tests and implementation | `ops/conductor/reports/mcp-pipeline-2026-09-05.md` on dev |
| Reproducible fixed-task script | `ops/conductor/reports/mcp-context-evaluation-2026-09-05.md` on dev; dated original JSON retains its original measurement head |
| Current evaluation, quality record and closeout | `review/mcp-cap-quality-20260905` at `216420e13ebdc6db321b294010e8c1a90e6d6262` |
| Final security record | `review/mcp-cap-security-20260905` at `db0342bddc507c3676e6a2d62329ed1d3776f4e3` |
| Earlier whole-feature findings and dispositions | `review/mcp-quality-20260905` at `3fe02bdac7fbc30e20c464c00b53e95fe31df65e` |
| Earlier security artifact | `review/mcp-security-20260905` at `076f1ac5d8ec10f879d384c0536f1e39b23cbf9e` |
| Independent Opus ruling | `review/mcp-ruling-20260905` at `7696494cd01aa3df8c653ffd2954119b5076059e` |
| Starting handoff, historical scope beyond this session | `records/codex-closeout-20260905` at `ce2bbf97aba915fcf0b3583f5ef04dfadcbdd52e` |

Exact final correction target was `ac29ca8f79beb0b285884d7bf7f6635f34275c67`.
Both fresh reviews were accepted APPROVE with no findings. Quality ran all
50 MCP tests and scratch probes; security ran in-memory boundary probes but
could not run fixture tests in its read-only sandbox. Local and PR CI ran
1,911 tests across nine suites, six skips, including 622 conductor tests.
PR merge `b50396c` and candidate tree both resolved to
`76080efaa63118f17ffa004c1a52dc85f45c6166`. The final fix retained all prior
parsing guards. Root did not rewrite Copilot's existing `56b26b5` commit.

Correction record IDs, all closed:

- tests: `20260905T215513Z-tests-grok-f2787b` (Grok 4.6)
- skeptic: `20260905T220422Z-check-tests-codex-b852fb` (Daybreak)
- implementation: `20260905T220642Z-code-codex-3fe449` (GPT-5.6 Sol)
- quality: `20260905T221346Z-review-grok-7662b2` (Grok 4.6)
- security: `20260905T221355Z-review-codex-d51502` (Daybreak)

Canonical local records remain at
`~/.local/state/agentscient/dispatch/ID/record.json`. Tracked captures are
verbatim, including model provenance. Read verdict, status, attempt result
and actual model independently; a generic self-printed model stamp is not
the actual model. An exited process without an accepted envelope is not green.

## Deferred concerns and promising next work

Existing nonblocking findings remain disclosed: findings accept UTF-16/32
despite the new contract's UTF-8 wording; the registry reader lacks the
record reader's 1024-depth precheck; encoding-policy fixtures are absent;
the test header retains pre-implementation wording. BOM handling differs
between readers. A catalogue exceeding the complete 16 KiB query bound is
a specified refusal. These are not a fresh security incident or permission
to start another hardening loop. Functionality first; rule on new findings
against the contract instead of turning every P2 label into a blocker.

The research's best follow-up opportunities are a bounded handoff/review
packet, a selected artifact index, dispatch prechecks and a CI evidence
packet supplied by a separate observer. A small cap correction still used
6,541,390 reported total tokens across five workers; see the AAR's accounting
limits. Preserve independent review while reducing repeated whole-tree
onboarding and wide diffs. No new contract or implementation for these
proposals was started. A roadmap entry is not an authorized work order.

## Working constraints and traps

Read the current AGENTS.md, docs and ops/README.md before new lane work.
Dispatch through `ops/bin/dispatch.sh` or `go.sh`; no in-session subagents.
Tests and implementation are different producers. Rule on CHANGES before
applying a correction. Work in an owned worktree, draft-first into dev,
stationary and green before ready, merge commits only, never delete branches.
Owner alone merges master. Every authored commit needs parsed Source and
actual-model Co-Authored-By trailers. A review request does not authorize
pushing a fix to dev; this mattered to the owner in the Copilot incident.

The wrapper has no `--base` flag; give the bounded correction diff and the
exact comparison refs in inputs/scope. `--scope-file` is capped at 1,024
bytes. `--stage code` is valid; `--stage implement` is not. Run the wrapper
and `launch.py wait ID` in the target lineage's owning worktree: waiting from
another worktree can say record not found even when canonical state exists.
`land.py ID --co-author 'Actual Model <vendor-noreply>'` handles worker code.
The launcher can commit a Codex write when its sandbox denies git metadata;
read jobs do not gain arbitrary report-write permission from a prompt.

Do not print `ops/bin/term-wall.conf`. Authored records use relative paths and
exclude private account identifiers. Preserve canonical captures byte-for-byte.
The root worktrees from this session and all review branches remain retained;
the main checkout is not available for reuse as a clean task workspace.

## Custody checks and explicit left-behind declarations

[Probe rows](probes/probes-2026-09-05-codex-mcp-closeout.jsonl) cover the
critical session holdings. The production `ops/conductor/tools/probes.py`
runner was looked for and is absent. Closeout uses a small read-only manual
execution of those rows, not a claim that the production runner exists or
that its identity-stripping boundary has been implemented. The manual run
passed all eight rows with zero failures or unreachable rows;
[results](evidence-2026-09-05-codex-mcp/probe-results.json) bind the artifact hashes.

Full private transcripts and the root session's token usage were not exported
or measured. Temporary scratch configurations/scripts and local suite logs
remain local; reproducible commands and durable review/CI evidence are linked
above. Private host configuration and daemon state were deliberately not
copied. Older unrelated branches, queues, ruleset settings and alternative
monitor processes were not re-audited; their earlier records are historical
leads, not verified live holdings. The original starting handoff remains
retained for that history and must be remeasured before acting on it.
