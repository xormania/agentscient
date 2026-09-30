# Runtime telemetry

The private state directory retains `live.sqlite3` events and
`telemetry/<member>.jsonl` communications. Captures are append-only across restarts;
each frame includes the component, connection, process, member, generation, native
conversation, role and work binding when known. Multiple writers serialize appends.
MCP tool frames retain the effective per-request `work_order` and `job` separately
from the member's persistent selection, including explicit operator overrides.
Rejected requests with no resolved scope are marked `unresolved`. Directional
`wire_sequence` values preserve transport order across concurrent request handling;
outbound recording and transmission share one lock.
Files are owner-readable. They contain task content; keep the state directory private.
Credential keys, known secret environment values and bearer credentials are redacted
in events and traces, including JSON nested in MCP text results. This is a credential
filter, not a promise to identify every secret someone types into prose.

Codex and Grok record incoming and outgoing native protocol frames, MCP traffic,
tool arguments/results, messages, streamed responses and exposed usage updates.
Claude records MCP channel traffic and hooks, and tails the native session's JSONL
transcript while it runs. SessionStart supplies its transcript path; only a matching
session file under the native Claude projects directory is accepted. A missing or
rejected transcript does not count as captured conversation content. Partial JSONL
writes wait for the complete line. An external CO connected through MCP has MCP
traffic captured; its private native conversation is not visible to this server.
The common `co` launcher additionally captures live native terminal output with
the same filtering, plus hooks and available Claude transcript entries. It does
not capture raw keystrokes. The separate Serena MCP gateway also records incoming
requests and outgoing results. See [session handover](session-handover.md).

`runtime_requested` records explicit and inherited harness/model/reasoning/provider
choices. `runtime_observed` records only fields actually reported by the native
protocol, hooks or transcript. These observations do not certify a vendor's internal
routing. Missing fields stay unknown. MCP client names and versions are retained
separately and are not used to guess a model. Session, usage, failure and delivery
events link to the same generation. Queued, delivering, submitted and acknowledged
messages remain distinct; delivery events retain their attempt ID and safe content.

Optional Jev calls emit `jev_evaluation` events in the same work scope. These
record the purpose, input fingerprint, model, elapsed time, cache reuse and
retained evidence. Provider usage appears on fresh successful evaluations;
cache hits have `usage: null` and should not be counted as fresh consumption.
The referenced artifact includes the exact sanitized TypeSafe request, response,
binding and operator policy. `jev_feedback` connects an evaluation to a decision
update, and an outcome update to that decision. Feedback labels and report text
record the officer's assessment separately from Jev's probabilities. Recording a
decision does not allocate, revise or accept work; normal command tools do that.
The response retains the original evaluation's usage. Advice is recorded
separately from subsequent agent decisions and measured outcomes; a recommendation
does not establish that the agent followed it or that it improved the result.

Known failures also carry service-owned `failure.category`, `reason`, and trusted
`details` through MCP, retained operations, and events. Provider outcomes distinguish
unavailability, invalid responses, invalid requests, and unclassified failures.
They must not be counted as substantive judgments that work failed its objective.

`skill_guidance_delivered` retains the triggering call, failure, concrete suggested
actions, originating operation, context identity and configuration revision.
`recovery_action_observed` correlates a later exact call under that same context and
policy using `guidance_event`, `originating_operation`, and `subsequent_operation`.
`matches` distinguishes suggested actions from original-call retries. An original
retry with an observed successful outcome sets `condition_resolved: true`; a
failed retry sets false, and pending or unknown outcomes remain null. A suggested
check instead records its named measurement, evidence, observed and expected
revision, and workspace cleanliness. A worker's `completed` state does not
override a nested failed check. The correlation captures sequence and outcomes;
it does not establish that guidance caused a recovery. Old context/configuration
suggestions are not correlated with replacement work, and telemetry faults cannot
replace the tool outcome.

Inspect operator `telemetry_events` / `telemetry_usage`, the JSONL traces, or run:

```sh
python3 devtools/run.py evidence --state /private/team --work-order 1
```

The evidence summary includes runtime records and trace paths alongside work,
delivery and validation observations. Protocol fixture tests exercise capture and
redaction, not authenticated model acceptance. Local acceptance still requires the
installed, logged-in harnesses and retained evidence from that run.
