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
`profiles`, and a nonempty `roles` mapping. Keys are identities from the configured
[capability catalog](role-capability-packages.md); each has an ordered list of
profile names. The catalog defines the role names and count, and maps each role's
`behavior` to an installed adapter in `devtools/adapters.json`. Its `defaults`
mapping selects the role when a workflow needs a behavior such as planning.
Several role identities may share one behavior; ambiguous automatic selection
requires an explicit default.

Runtime preferences may configure a subset of the catalog. Unknown role identities
are rejected, and requesting an omitted role fails before its allocation; profiles
are never chosen implicitly. Different roles may use different lists or share one.
For example, a profile is:

```json
{"harness":"claude","vendor":"anthropic","model":null,"reasoning":null}
```

Set `model` and `reasoning` to values accepted by your installed harness. Null
leaves the native default in control and telemetry labels it accordingly. Optional
`binary` is an executable path/name, never a shell command. A harness adapter may
support a `provider` key for a configured native model provider; the supplied
Codex adapter does. Vendor identity is explicit, not inferred from the model name.
Generated files contain the configured catalog's roles, using each role's declared
harness order and the installed harness adapters' vendor defaults. Vendors stay
disabled until you enable your logins.

`vendors.json` has `version: 1` and a `vendors` mapping. For example:

```json
{"version":1,"vendors":{"anthropic":{"available":false,"reason":"Usage exhausted"},"openai":{"available":true},"xai":{"available":true}}}
```

Availability controls new launches only. The service tries a role's preferences in
order, skipping disabled vendors and missing executables. It fails if none are
available; it never enables another vendor or replays an interrupted task itself.
An optional `reset_at` string is an operator reminder, not proof that quota reset.
Save edits by replacing complete JSON files atomically. Malformed policy fails
closed. Both files, the role catalog and the adapter manifest contribute to the
recorded configuration revision. Catalog CUE and generated JSON are repository
configuration shared by services; they are not selected independently per team.

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
