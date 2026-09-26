# MCP, telemetry, and live harnesses

This directory has three responsibilities: a stdio MCP server, local measured
telemetry, and communication between persistent Codex, Claude Code, and Grok
sessions. Python 3.11+ and SQLite from its standard library are sufficient for
the MCP server. Native launchers require Linux/macOS and the selected locally
installed, authenticated harness. Background Claude sessions also require tmux.

There is no dispatcher, task engine, assignment registry, grant system, audit
ladder, source editor, shell capability, or project command runner.

## Set up a team

An operator runs this once from the repository checkout. State must be outside
the source worktree. The `external` member represents the MCP client from which
you manage the team; it does not spawn another model.

```sh
python3 devtools/run.py init \
  --state "$HOME/.local/state/agentscient-live" \
  --workspace "$PWD" \
  --member owner:external --member codex:codex --member claude:claude --member grok:grok
```

Select only the harnesses you use. Edit that state directory's `team.json` to set
each member's `binary`, optional `model` and `reasoning`, and workspace. Different
members can use separate worktrees. Existing member identities cannot silently
move to a different harness or workspace; use a new member name for that change.
No model is selected by this repository.

Add this server to the managing client's MCP configuration, replacing the paths
with absolute paths on your machine (the command must be your Python executable):

```json
{
  "mcpServers": {
    "agentscient_dev": {
      "command": "/absolute/path/to/python3",
      "args": ["/absolute/path/to/agentscient/devtools/run.py", "mcp",
               "--state", "/absolute/path/to/state", "--member", "owner"]
    }
  }
}
```

`tools/list` exposes only `capability_search`, `capability_describe`, and
`capability_invoke`. Search returns five capabilities per page; describe supplies
the input schema. Invoke takes `{"capability":"name","arguments":{...}}`.

| Capability | Purpose |
| --- | --- |
| `peers` | Configured members, observed state, and actual native conversation IDs |
| `session_start`, `session_stop` | Start a configured member or request that it stops |
| `message_send` | Send a durable message with an idempotency key |
| `message_inbox`, `message_wait` | Read or briefly wait for incoming messages |
| `message_ack`, `message_retry` | Acknowledge reception or explicitly retry uncertain delivery |
| `telemetry_events`, `telemetry_usage` | Read paginated measured events and available native usage |

For example, invoke `session_start` with `{"member":"codex"}`, then `message_send`
with `{"to":"codex","body":"Your message","key":"unique-key-for-this-message"}`.
Starting a session reports observed startup state, not proof that the model has
received or processed anything. A recipient's explicit acknowledgement is separate.

## Native conversations

Codex keeps one app-server thread and receives peer messages through
`turn/start.toolOutput`. Its dynamic tools proxy the actual stdio MCP server.
Startup checks that the installed binary advertises the required tool-output API.
Grok keeps one ACP session, using `session/prompt` when idle and `_x.ai/interject`
while busy. Claude keeps its native interactive session and receives MCP channel
notifications. Delivery waits for the native channel registration log entry;
initial MCP handshake alone does not establish a ready channel.

Claude may need its native development-channel approval. Attach to the tmux
terminal returned by `session_start`. The approval remains in the native UI;
there is no replacement repository permission process.

Private profiles expose this team's MCP surface and deny native shell/filesystem
tools. Codex and Grok reuse only selected local login/configuration information;
Claude retains its native account login. These settings do not form an OS sandbox.
Global harness settings are not rewritten. Vendor protocol changes can require an
adapter update; startup failures and delivery errors remain visible in telemetry.

Operator equivalents are available for bootstrap and troubleshooting:

```sh
python3 devtools/run.py start --state /absolute/path/to/state --member codex
python3 devtools/run.py agent --state /absolute/path/to/state --member claude
python3 devtools/run.py status --state /absolute/path/to/state
python3 devtools/run.py stop --state /absolute/path/to/state --member codex
```

`agent` runs in the current terminal. MCP participants use the named capabilities,
not these CLI commands. A stopped session's records survive; restarting creates
a new native conversation. This does not claim transcript/context recovery.

## Telemetry and delivery

The state directory contains `live.sqlite3`, private native profiles, process
logs, and redacted JSONL transport traces under `telemetry/`. Events record MCP
operation timing/results, native identity/activity, message submission and
acknowledgement, and usage observations when the native protocol supplies them.
Missing usage is unknown, not zero; no estimated cost is fabricated.

Queued, submitted, and acknowledged are distinct. A crash during delivery becomes
`uncertain` on restart, not an automatic duplicate. Only the sender can explicitly
retry that message; the ID stays the same. Traces and message history stay local.

## Verification and source

```sh
python3 -m unittest discover -s devtools/tests -v
ruff check devtools
```

Tests launch real stdio MCP servers and native protocol fixtures to exercise
concurrent delivery during unfinished work, persistent identities, acknowledgements,
restart behavior, channel registration, telemetry, and the native-tool boundary.
Fixtures are not new evidence of authenticated vendor-model acceptance. The native
transports are adapted from the previously accepted
[`multi-harness-proof`](https://github.com/xormania/multi-harness-proof/tree/a944f31b7527807d000da985c546e8b5bc9ff476).
Its MIT notice is retained in `PROVENANCE-LICENSE`. No old development-system
runtime or records are imported.
