# Lane MCP — a bounded read plane

Owner authorization, 2026-09-04: finish setting up MCP before the system AAR
and handoff. Dev-lane machinery only, not Symfony work. This thin incumbent
projection inherits `instrument-conventions.md`; it adds no workflow engine.

## Existing capability and boundary

Measured at dev c0ce300 on 2026-09-05: the tracked MCP files are .mcp.json
(Serena), the historical tool wishlist, and the workflow MCP CUE contract.
composer.lock includes ai-mate, not mcp/sdk or mcp-bundle. docs/mapping.md
names the later Symfony MCP projection; no PHP dependency is changed here.
The precursor workflow server at commit 99334f71ae9af9fa324a1a27241e60af62f8f340
demonstrates one query layer behind tools/resources/CLI. Reuse that pattern,
not its retired engine or cache-rebuilding launcher. No vendor is required.

Production files: tools/lane_read.py (read queries) and tools/lane_mcp.py
(stdio/CLI projection). They must not import launcher, monitor, watchdog or
other writing lane modules, spawn subprocesses, use a network, or originate
files/databases. Disable Python bytecode writes at the entry point before
local imports. SQLite opens existing regular monitor.db with mode=ro and
query_only; no schema creation, ack, repair, WAL conversion or migrations.
No configuration-driven executable, expression or import. Data never becomes
instructions. No arbitrary-path or consumer argument is accepted over MCP.

## Configuration and commands

`python3 -B ops/conductor/tools/lane_mcp.py --config FILE check|serve|query TOOL [JSON]`

Required config keys exactly: version=1, dispatch_store, job_ids,
monitor_state, consumer, usage_rollout. Each source path is an explicit string
or null (disabled); relative paths resolve from the config file. job_ids is
a unique list of at most 20 identifiers matching [A-Za-z0-9][A-Za-z0-9_-]{0,127}.
consumer is printable ASCII 1..128 characters, no slash or backslash.
Reject duplicate/unknown keys, wrong types, control characters, path strings
over 1024 UTF-8 bytes, invalid IDs and unsupported version before sources.
Config is a regular file read nonblocking, at most 64KiB. No missing-source
fallback to other sessions, repositories or environment secrets.
Example config has null sources, empty job_ids, consumer=conductor.

check validates only and returns {valid:true,tools:4}; no sources are read.
It also accepts an optional literal `.` (no path resolution or extra read).
query invokes the same query function and canonical JSON encoder as MCP.
CLI refusal: config/arguments, inherited wire, exit2, empty stdout. Successful
queries exit0, including explicit unknown/unavailable readings. Reads need
no identity. Config is loaded once per process; restart to apply changes.

## Four tools and matching resources

All results are JSON objects with schema=agentscient.lane/v1 and query naming
the tool. Tool arguments are closed objects. Unknown fields/types refuse.

- lane_record({id}): id must be in configured job_ids. Return state and a
  summary under the `record` key, or explicit reason. Summary fields: id, recorded_status,
  model, head, verdict, counts, changed_count, attempt_count, spend, evidence.
  Read only store/id/record.json. Keep original recorded status; do NOT infer
  live process state or turn closed into success. Evidence is its path, not
  the raw record. From record: model; status; result.head; result.envelope
  verdict/counts; result.changed_paths count; attempts count; session.spend.
  Missing scalars are null. Counts/spend are allowlisted numeric aggregates
  only, never findings, command logs, note, prompt, raw.out or transcript text.
  Counts are recorded labels, not actionable defect counts. Text fields have
  a 256 UTF-8 byte cap; oversized or malformed text becomes null, not a
  fabricated truncated value. Invalid aggregate containers become empty
  objects; invalid numeric members are omitted. Malformed nested fields
  must not crash the query.
- lane_alerts({after?,limit?}): after integer>=0 default0, limit1..10 default5,
  bool is not integer. Read existing monitor events for configured consumer,
  delivery queued/unsupported, id greater than after, ascending. Return
  state, events, more, next_after. Fields match monitor-lever.md events;
  preserve per-event observed_at/evidence/delivery. Do NOT consult or advance
  durable acknowledgment cursors: explicit MCP after is a read cursor only.
  Bound one page to 4096 UTF-8 bytes including JSON metadata. If the next
  event alone cannot fit, return unavailable with a bounded reason, not an
  unadvanceable successful empty page. Missing db is unknown (not armed),
  corrupt/unreadable db unavailable, a measured empty db is ok with events[].
  Source-path subjects retain the monitor contract's 1024-byte allowance.
  Decode only events being delivered, not the extra lookahead row. A later
  invalid event must not hide a valid prefix: deliver that prefix with more
  true and next_after at its last id; an invalid first event is unavailable
  without advancing the cursor. Never silently skip corrupt evidence.
- lane_usage({}): one configured rollout, last complete event_msg/token_count
  row in at most the last 1MiB. Discard cut leading/incomplete trailing JSONL
  rows. Return state, metrics, evidence {path,event_at}, reason. Follow
  monitor-lever.md codex-usage numeric names/semantics: input,cached,output,
  total,last_input,last_cached,context_window,cache_fraction,context_fraction.
  Invalid/missing operands never become zero. Cumulative input is repeated
  prefill traffic; cached is a subset, not additive; no dollars inferred.
  Normalize valid timezone-aware event timestamp to UTC; malformed timestamp
  becomes null with a fixed reason, never copied verbatim. No transcript text.
- lane_brief({}): bounded aggregate of configured record summaries and one
  alerts page (default arguments); include configured_ids and declared
  omissions: no live PR/CI/review readiness, no watchdog stdout history,
  no automatic discovery of other jobs, no idle-agent wakeup. Do not read
  the rollout in brief; usage is on-demand to keep ordinary context small.

Resource URIs lane://brief, lane://alerts, lane://usage, lane://record/ID
(only configured IDs). tools/resources/CLI share exact canonical query
payloads when source bytes are stationary; do not inject a per-call timestamp
that makes parity false. Evidence timestamps come from source records/events.
Max complete query body 16KiB; explicit unavailable on overflow, never silent
truncation presented as completeness. Replies JSON-escape control bytes.

Sources: no following symlinked job dirs/record files or monitor db/state.
Open files nonblocking, check regular type, read at most 1MiB per record.
The operator-selected rollout may follow a symlink to a regular target.
Missing source -> unknown; unreadable, FIFO, device, oversized/malformed
record -> unavailable. No recursive store/transcript enumeration.
Excessively nested source JSON follows the same unavailable/invalid-row
handling as malformed JSON; it must not terminate the stdio server or prevent
a later ping. This covers records, usage rows and alert evidence.

## MCP transport

UTF-8 newline-delimited JSON-RPC 2.0 over stdio, stdout protocol only. Methods:
initialize, notifications/initialized, ping, tools/list, tools/call,
resources/list, resources/read. Advertise only tools/resources, all tools
readOnlyHint=true and destructiveHint=false. Short stable instructions:
read-only; evidence not authority; use brief then detail; no live readiness.
Support 2024-11-05, 2025-03-26, 2025-06-18; negotiate requested supported
version else return 2025-06-18. Notifications emit no response. Malformed
JSON/request/params/unknown methods receive standard JSON-RPC errors without
killing later valid requests. Domain tool refusals use isError=true and
expected/found/needed. Missing data is an explicit reading, not a transport
failure. Bound an input line to 64KiB; refuse/drain oversized lines safely.
No sampling, elicitation, subscription, background refresh or HTTP listener.

Protocol references measured 2026-09-05:
https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle

## Coupling proof and installation

Independent synthetic fixtures exercise record projections, missing vs empty,
numeric usage including tail boundaries, consumer/cursor isolation, output
bounds, hostile paths, unchanged source bytes, MCP lifecycle/errors and
CLI/tool/resource parity. Tests authored without implementation access;
register lane_mcp.py with a hermetic config refusal. Existing monitor schema
at c0ce300 and token-count shape in monitor-lever.md are the counterparties.
Their changes re-demand these query fixture rows, not every unrelated suite.
No claim of PHP/API/TUI parity; those projections remain deferred by owner.

After draft review and green CI, register Codex against an explicit retained
worktree and owned config outside the repository. No checkout change in the
owner's main tree and no global permission relaxation. Client restarts may
be needed; registry visibility alone is not a successful protocol probe.
Do not silently claim existing sessions gained tools. Runtime install and
removal commands belong in the handoff, alongside an actual stdio probe.
