# Role capability packages

Agentscient configures standalone sessions from versioned role packages. The
maintained definitions are in [role-packages.cue](../devtools/role-packages.cue);
[role-packages.json](../devtools/role-packages.json) is its concrete, checked-in
export. Normal Python services load the export without requiring CUE, PHP or
Symfony. Package files are trusted repository configuration, never agent inputs.

| Package field | Used by |
| --- | --- |
| `responsibility`, `skills` | Shared and role onboarding plus relevant installed skill references |
| `runtime` | Permitted harnesses, model/reasoning defaults and optional allowlists |
| `hooks` | Private harness profiles using the shared MCP-only gate and lifecycle observations |
| `mcp` | Role tool ceilings, grouped by binding, project and provider prerequisites |
| `workspace` | Editing eligibility, default editable paths and Serena eligibility |

The package is a maximum. The current service binding, job/assignment, reporting
relationship, plan revision, pause state, provider availability and source-path
rules determine whether an operation can run. MCP services check these before
performing effects. Backing command, workspace, development, delivery and advice
services also check the declared capability ceiling; retained workers recheck it
before executing queued work. Hooks and native permission adapters reject calls outside the
current role catalog early; they do not replace those service checks. Serena is
included only for an eligible current workspace binding. Agent creation and Git
operations, including branch names, remain behind MCP.

CO's package supplies the interface tools and instructions; it has no assessment,
execution, coordination or acceptance tools. XO, NCO, planner and specialist
packages preserve the existing command boundaries. Native delegation remains
explicitly disabled. Skills and execution options do not expand command authority.

## Operator runtime configuration

The generated repository file **`devtools/role-packages.json`** is separate from
the existing private **`<state>/roles.json`** and **`<state>/vendors.json`**. Those
operator files keep their current format: ordered profile choices by role,
availability, custom model/reasoning strings, binary paths and Codex providers.
Existing fixed teams and runtime policies continue to work.

Package model/reasoning defaults and allowlists are initially `null`: configured
operator choices and native inherited defaults retain their existing behavior.
An explicit package allowlist requires an explicitly permitted configured value
or a permitted package default. An unknown inherited value cannot satisfy it.
Invalid profiles are rejected before workspace preparation or new seat allocation.
Existing bindings are retained when an assignment attempt is rejected.

Project `paths` settings may narrow a package's editable paths. Settings outside
that ceiling are rejected before promotion, recovery or checkpointing; widening
a role requires a reviewed package change. Job and assignment paths narrow the
result further.

`onboard` includes the package role, version and content revision. Private native
profiles record the package and binding revision. Session startup telemetry records
the selected package alongside its execution settings. Running sessions retain
their startup model/harness settings; changing runtime preferences applies to a
later start and does not change their command authority.

## Maintainer changes

Edit the CUE definition and regenerate with the pinned CI version, CUE v0.17.1:

```bash
cue fmt devtools/role-packages.cue
python3 -m devtools.role_packages --write
python3 -m devtools.role_packages --check
AGENTSCIENT_CUE=cue PYTHONPATH=devtools/tests:. python3 -m unittest devtools.tests.test_role_packages -v
```

Generation vets the entire CUE source before exporting its concrete `packages`
value. The Python loader checks raw field presence, supported shapes, skill
references, hook invariants and source/export correspondence. The MCP registry
rejects unknown tool references at startup. CI repeats CUE validation, export-drift
checks and rejection controls in the existing dev-lane configuration job.
Pull-request CI runs for every base branch, including an unmerged parent in a
stack. The change selector still compares against that parent and selects the
affected suites; the required `lane` check keeps the same completion rules.

Deploy the matching source and generated export together, then restart control
services and managed sessions to load package changes consistently. Packages are
cached per service process; this change does not introduce policy hot reload.
Current job/revision/role authorization is still checked on each MCP call.
