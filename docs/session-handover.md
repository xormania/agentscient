# Native CO and role replacement

Initialize the [shared runtime](shared-runtime-config.md), configure the chosen
harnesses' [native login storage](../devtools/OPERATIONS.md#native-login-storage),
and enable their vendors. From Linux or WSL2, start the CO:

```sh
python3 devtools/run.py co --state "$HOME/.local/state/agentscient-live"
```

For an existing work binding, this uses its configured CO role identity. Without
a work binding, it uses the catalog's default role for CO behavior. A binding
with another behavior is rejected. The launcher uses the first available profile
in the selected role's preference list. An operator can
choose a configured CO profile and override model or reasoning for this launch:

```sh
python3 devtools/run.py co --state "$HOME/.local/state/agentscient-live" \
  --profile claude --model YOUR_MODEL --reasoning YOUR_EFFORT
```

Profile names come from `roles.json`; the defaults are `codex`, `claude` and `grok`.
An explicit profile must belong to CO's preference list and have an available
vendor and executable. A disabled explicit choice fails instead of silently
launching a different vendor. Model and effort values must be supported by the
installed harness and selected model, and must satisfy that role package's
model/reasoning allowlists. Overrides are checked before a new session is registered;
they do not edit the configured profile. Omit them to use the configured values,
package defaults or permitted native defaults. Ordinary agent MCP tools do not
accept these runtime choices.

The launcher opens the native interactive terminal with a private profile and
the common MCP server. Project files are accessed through role tools. The CO calls
`onboard`, which includes its shared and role instructions. Use `skill_read` only
for relevant skills not already marked `loaded`. CO then relays xor's instructions
to XO; XO creates managed tmux sessions for the specialist roles. Claude may show
its native development-channel consent.
Normal native authentication and consent remain in force.
Supported Codex/Grok file-based login data is retained privately for the same
member and harness across launches. A changed operator login takes precedence;
the runtime does not write back to the operator's global credential file. Codex
keyring accounts need the dedicated file-login setup described in the operator
reference before a private profile can reuse them.

## Swap CO

1. Have CO retain important user decisions, pending questions and next actions
   with `work_report`. Reports, jobs, messages and evidence are already durable.
2. Exit the current native CO normally. If it is stuck, use the operator's
   `stop --state ... --member owner` command and wait for shutdown.
3. Run `co` again, optionally choosing another profile. The replacement loads
   `onboard` and `work_context` for the same logical CO and current work.

CO may switch among its configured harness adapters. The existing XO and specialists keep
their conversations. Native transcript, private reasoning and REPL variables do
not migrate. Unreported private decisions cannot be reconstructed by the service.
Codex/Grok interactive CO clients read new team reports through `work_context`
or `monitor`; their TUI is not the managed app-server/ACP message bridge. Claude
can also receive the registered MCP channel. Keep a normal team MCP connection
active for launch intents and background observation.

## Replace other roles

| Controller | Action | Preserved |
| --- | --- | --- |
| Operator | Replace XO through trusted repair tools | XO work, specialist team, reporting chain, evidence |
| XO | `steer(action="replace", work=..., role=..., direction=...)` | Named specialist's role, job, workspace, history and evidence |
| XO | `steer(action="pause" / "resume")` | A still-running native conversation |

Replacement requests stop the old process, then launch the same member with the
current role/vendor policy. They do not retry an uncertain message or replay a
native conversation. Recovery uses the latest brief and durable reports. Inspect
`monitor` for observed startup or a failure; fix operator configuration and use
resume/replacement again if no runtime is available. Externally attached XO or
specialists require their operator to reconnect them.

Each launch has a new generation. Native MCP and hook commands carry that
generation in a separate private profile directory. Old connections and old
profile reconnects cannot act in a replacement session. A new generation waits
for an in-flight MCP/provider call to finish; launching while a call is active
returns a retryable error. The old native process must exit before replacement.
The separate Serena gateway enforces the same session boundary.
Live delivery claims recheck the generation and stop state in the same transaction
as dequeuing, so a retiring process cannot consume its replacement's recovery direction.
After native shutdown, a fresh external connection from the exported `connection`
configuration can resume the same external CO seat without a generation argument.
It keeps the durable work and captures the last generation as a boundary: the next
native launch invalidates it. Connections opened before shutdown and connections
that explicitly carry the stopped native generation remain blocked.

## Evidence and limits

The CO launcher records terminal output, MCP calls/results, hooks, runtime choices
and available Claude transcript entries alongside existing per-member telemetry.
It does not record raw keystrokes; native login/password input remains governed by
the harness. Output uses credential filtering and incomplete-line buffering. The
capture contains native terminal control sequences and task content. Not every
terminal redraw is a structured message, and a visible selected model is not
proof of the vendor's internal routing. Preserve private state accordingly.

CI runs real PTYs, tmux, MCP, generation fencing, cross-harness CO fixtures and
vendor fallback on XO replacement. It retains the resulting traces and database.
These are protocol/CLI fixtures: installed authenticated vendor acceptance remains
the [local check](local-agent-readiness.md#authenticated-local-acceptance).

Native CLI settings were checked against the official
[Codex reference](https://developers.openai.com/codex/cli/reference),
[Codex configuration](https://developers.openai.com/codex/config-reference),
[Claude reference](https://code.claude.com/docs/en/cli-reference),
[Grok reference](https://docs.x.ai/build/cli/reference) and
[Grok settings](https://docs.x.ai/build/settings/reference).
