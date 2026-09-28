# Shared role runtimes

Initialize an operator-owned policy in the private state directory:

```sh
python3 devtools/run.py init --state /private/team --workspace /repo/agentscient \
  --co owner --member owner:external --runtime
```

Add the existing project/repository options when this team will manage product
workspaces. Existing fixed-member teams continue to work. To migrate one, create
`roles.json` and `vendors.json` using the schema below, then set `"runtime": true`
in `team.json`. Existing running conversations are not reconfigured.

`roles.json` has `version: 1`, `max_sessions` (1–100 concurrent bound collaborators),
`profiles`, and `roles`. Every role must have an ordered list of profile names:
`co`, `xo`, `coder`, `audit`, `docs`, `research`, `test_writer`, `architect`.
Different roles may use different lists, or share one. For example, a profile is:

```json
{"harness":"claude","vendor":"anthropic","model":null,"reasoning":null}
```

Set `model` and `reasoning` to values accepted by your installed harness. Null
leaves the native default in control and telemetry labels it accordingly. Optional
`binary` is an executable path/name, never a shell command; Codex also accepts a
`provider` key for a configured native model provider. Vendor identity is explicit,
not inferred from the model name. The generated files contain all eight roles and
Claude/Codex/Grok defaults, with vendors disabled until you enable your logins.

`vendors.json` has `version: 1` and a `vendors` mapping. For example:

```json
{"version":1,"vendors":{"anthropic":{"available":false,"reason":"Usage exhausted"},"openai":{"available":true},"xai":{"available":true}}}
```

Availability controls new launches only. The service tries a role's preferences in
order, skipping disabled vendors and missing executables. It fails if none are
available; it never enables another vendor or replays an interrupted task itself.
An optional `reset_at` string is an operator reminder, not proof that quota reset.
Save edits by replacing complete JSON files atomically. Malformed policy fails
closed. Both files contribute to the recorded configuration revision.

CO asks for an objective; XO asks for named work and roles. The service allocates
instances dynamically, supports several instances of one role, and snapshots the
resolved runtime for each launch. Native settings and fallback reasons go to
telemetry. CO/XO tools expose role capacity and work state without model selectors.
Operator `runtime_status` exposes policy, availability and resolution diagnostics
through MCP. Model settings do not grant tools or authority.

If a vendor runs out mid-session, mark it unavailable, stop the affected session,
and resume the bound work after it stops. The next launch resolves current policy.
The work, evidence and message history survive; a new native conversation is a
new session, not a cross-vendor transcript migration.
