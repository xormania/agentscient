# Local agent development support

`devtools/` is the dev-lane: independent Python services behind MCP for live agent
coordination and product development. The Symfony application in `src/`, `config/`
and `packages/` is the prod-lane.

## Choose a guide

| Need | Guide |
| --- | --- |
| First installation and local acceptance | [Local setup and readiness](../docs/local-agent-readiness.md) |
| Role packages, execution options and enforced ceilings | [Role capability packages](../docs/role-capability-packages.md) |
| Normal CO, XO and specialist work | [Roles and tools](../docs/control-plane-roles-and-tools.md) |
| Team configuration, credentials, native sessions, storage or repair | [Operator reference](OPERATIONS.md) |
| Development checks and integration tests | [CI guide](../.github/CI.md) |

## Services and providers

| Component | Responsibility |
| --- | --- |
| **Control-plane MCP** (`agentscient_dev`) | Role/work binding, brief delivery, live reporting and guidance, work orders/jobs, artifacts, telemetry, workspace/Git/GitHub outcomes, installed Maker/Mate calls and configured checks. |
| **Serena MCP** (`serena`) | Source navigation and edits through the v2 REPL, bound automatically to the current specialist's workspace and paths. |
| **Native harness adapters** | Keep configured conversations alive and carry live messages through their native protocols; the shipped adapters support Codex, Claude and Grok. |
| **SQLite and managed storage** | Retain work, state, messages, observations and artifact associations; store artifact payloads separately. |
| **Jev assessment** | Independently enabled role/job relevance filtering, proof-backed completion and on-demand advice, using configured provider credentials and existing artifacts/telemetry. |

CO is xor's interface: it relays xor's instructions and prepared context to XO,
and system messages back to xor. XO owns planning, execution, coordination and
acceptance. It commissions a planner, coordinates a one-job plan directly, or
appoints one NCO per job for a multi-job plan. Work-order numbers bind the overall
effort; jobs hold bounded responsibilities and their delivery evidence. Agents use
outcome tools while the services manage repository and provider details.

The normal tool catalog is role-scoped and directly callable. It does not expose
the backing GitHub catalog or a shell. The separate operator connection is for
setup and repair; it is not attached to managed agents. Live conversation is the
coordination mechanism. XO allocates responsibilities and routes guidance through
each collaborator's work binding.

Each collaborator is a standalone managed native session. Agentscient creates and
coordinates those sessions; harness-native subagents are not used. Model, harness
and reasoning choices do not widen the service-enforced role or work authority.

## Runtime

The core uses Python 3.11+ and SQLite from the standard library. Managed sessions
require Linux or WSL2 with readable process identities, pidfd access and abstract
Unix sockets. Native collaborators need installed, authenticated harnesses and
tmux. Source editing uses the pinned Docker-based Serena
provider. Symfony generation, diagnostics and validation need PHP and Composer
matching the application's committed lockfile.

[Setup](../docs/local-agent-readiness.md) connects these pieces. The
[operator reference](OPERATIONS.md#native-conversations) describes native transport,
startup checks and recovery. The [tool reference](../docs/control-plane-roles-and-tools.md#serena-v2-repl)
explains REPL lifetime and workspace isolation.

## Code map

| Files | Responsibility |
| --- | --- |
| `api.py`, `mcp.py`, `control.py`, `commands.py` | MCP surface, role/context enforcement and CO/XO outcomes |
| `role_packages.py`, `role-packages.cue`, `role-packages.json` | Validated role identities, behavior mappings and runtime projections |
| `adapters.py`, `adapters.json`, `role_behaviors.py`, `harnesses.py` | Installed evaluation, role and harness implementations selected by configuration |
| `launch.py`, `native.py`, `profiles.py`, `compat.py` | Persistent native sessions, private profiles and protocol checks |
| `work.py`, `store.py`, `artifacts.py`, `telemetry.py` | Work records, SQLite state, artifacts and measured observations |
| `workspaces.py`, `orders.py`, `retirement.py`, `github.py`, `delivery.py`, `feedback.py` | Job/work-order integration, worktree retirement, PR/CI, review, acceptance and diagnostics |
| `development.py`, `operations.py`, `serena_provider.py` | Installed framework tools, retained long operations and the separate REPL gateway |
| `configuration.py`, `configuration.cue`, `configuration.json` | Validated defaults and private project → role → job policy resolution |
| `advice.py`, `jev.py`, `credentials.py` | Work-scoped assessment, configured TypeSafe transport and private credential sources |
| `diagnostics.py`, `completion.py` | Configured permitted skill guidance, scoped context projection and proof boundaries |
| `readiness.py`, `run.py` | Operator setup, preflight, evidence index and entry points |
| `tests/`, `integration/` | Protocol/service tests and real Symfony/Serena integrations |

Source and license details are in the
[operator reference](OPERATIONS.md#source-attribution).

Runtime setup is self-contained in this branch. Configure the private overlay and
key source using the [operator reference](OPERATIONS.md#configuration-and-local-jev-credentials);
historical branches are not runtime dependencies.
