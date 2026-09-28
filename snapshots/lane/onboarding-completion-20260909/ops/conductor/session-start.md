# Session startup — working contract

Owner request, 2026-09-09: complete reliable onboarding, including tools,
MCP, watchdog, monitor, concurrent sessions and bounded operation. This
implementation composes the existing instruments. Proposed policy engines,
executor replacements and MCP v3/v4 are not prerequisites.

Inherits `instrument-conventions.md`. This is independent dev tooling.
`onboard.py` remains the existing read-only brief, with its existing exits.

## Entry and custody

`ops/bin/session.sh codex [ARGS...]` or `claude [ARGS...]` starts an
interactive conductor with a generated session id. `WF_AGENT` supplies its
full model identity. The launcher runs from this repository's worktree;
it does not switch branches, fetch, merge, install dependencies or dispatch
model work. Dispatched workers (`DISPATCH_JOB`) must not bootstrap conductors.

`python3 ops/conductor/tools/session.py` exposes `start HOST [ARGS...]`,
`status`, `catalogue`, `track JOB`, `hook`, and internal `supervise`.
`AGENTSCIENT_SESSION_DIR` binds child tools to the launcher's state directory.
Directories are private under XDG_STATE_HOME/agentscient/sessions, with a
fresh UUID for each launch. A manifest records repo, branch, SHA, identity,
consumer, jobs, host/supervisor identities and lifecycle observations.
All state updates use a per-session lock and atomic replacement.

Each launch gets its own monitor config, monitor SQLite state, watchdog
log and cursors. No shared alert acknowledgement or global process cleanup.
The supervisor owns its child processes and only terminates those children.
Closing a host stops its coverage; crashes are detected by PID plus Linux
process start time. A 30-minute idle lease renewed by hooks and job tracking
stops unattended coverage; live tracked jobs extend it, within an eight-hour
absolute ceiling. Limits are reported. Expiry is visible as stopped coverage,
never readiness. Supervision performs no model calls.

## Startup and delivery

The launcher creates/validates explicit monitor and MCP v2 configurations,
starts monitor and watchdog under a supervisor, and overrides only this
host invocation's `agentscient_lane` MCP server with `session_mcp.py`.
No global host settings or trust records are rewritten.

Project-native SessionStart, PreToolUse, PostToolUse and SessionEnd hooks
invoke `session.py hook`. Hosts must enable/trust these hooks using their
native controls. Unwrapped sessions receive a concise setup message and
must not be described as covered. Workers receive no conductor context.
SessionStart prints the compact catalogue and measured session status.
Tool hooks renew the lease and deliver monitor alerts and newly observed
watchdog output, bounded to 12 KiB per invocation. Delivery is at a host
hook boundary, not an unsolicited wake-up during idle time or a blocked
tool. Receipt records mean output was emitted to the host, not understood.
Output containing observed branch/job text is explicitly labelled data.
SessionEnd requests only its own supervisor to stop.

Readiness requires living monitor and watchdog processes, a successful
monitor cycle, a native startup-hook receipt and a successful MCP tool
request. `status` reports each separately and returns Finding while any
is absent. A running process alone does not mean onboarding completed.
Failures of the supervisor or either instrument appear on subsequent hooks
and status reads; there is no automatic infinite restart loop.

## Dispatch and MCP couplings

When the session binding is present in the conductor environment, dispatch
attaches the minted job id through `session.py track JOB` before launching
the worker. Attachment failures stop that launch with a diagnostic; existing
dispatches and records are retained. No session binding preserves the old
dispatch behavior. The worker environment removes the conductor binding.
Tracking updates both monitor and MCP configurations under the session lock.

`session_mcp.py serve` is read-only: it reloads the explicit v2 config for
each request, then calls the existing lane MCP request dispatcher. Its
tools/resources remain the seven v2 tools/resources. It creates no state,
acknowledges no alerts, launches no processes, and does not invoke models.
Successful tool calls are observed through the host PostToolUse hook;
MCP itself writes no receipt. The session's hook consumer and MCP consumer
are distinct, so hook acknowledgement cannot hide evidence from MCP.

## Discovery and acceptance

`catalogue` is a read-only JSON inventory measured from the worktree: all
public conductor tools, levers, dispatch jobs, telemetry instruments, hook
files, local skill entry points, feature specifications, MCP tools and
optional application Mate availability. Entries name their source paths;
the startup projection contains counts and commands for targeted reads.
Suggestions, historical plans and optional Mate remain labelled as such;
their availability is not an admission requirement.

Independent tests must exercise the public CLI/host hook boundary with
synthetic hosts, two concurrent sessions and real monitor/MCP fixtures:
isolation, duplicate tracking, current job visibility, alert delivery,
unavailable/dead coverage, bounded expiry and scoped shutdown, worker
exclusion, missing identity/session, catalogue closure and unchanged
read-only onboarding. Host fixtures must not make model calls. A live host
probe records which native hooks actually ran; synthetic passes alone do
not establish native integration. Refusal classes: arguments, identity,
session, host, repo. Errors after startup return Abort with retained state.
