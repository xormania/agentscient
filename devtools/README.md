# Local agent development support

`devtools/` is the dev-lane: independent Python services behind MCP for live agent
coordination and product development. The Symfony application in `src/`, `config/`
and `packages/` is the prod-lane.

## Choose a guide

| Need | Guide |
| --- | --- |
| First installation and local acceptance | [Local setup and readiness](../docs/local-agent-readiness.md) |
| Normal CO, XO and specialist work | [Roles and tools](../docs/control-plane-roles-and-tools.md) |
| Team configuration, credentials, native sessions, storage or repair | [Operator reference](OPERATIONS.md) |
| Development checks and integration tests | [CI guide](../.github/CI.md) |

## Services and providers

| Component | Responsibility |
| --- | --- |
| **Control-plane MCP** (`agentscient_dev`) | Role/work binding, brief delivery, live reporting and guidance, work orders/jobs, artifacts, telemetry, workspace/Git/GitHub outcomes, installed Maker/Mate calls and configured checks. |
| **Serena MCP** (`serena`) | Source navigation and edits through the v2 REPL, bound automatically to the current specialist's workspace and paths. |
| **Native harness adapters** | Keep Codex, Claude and Grok conversations alive and carry live messages through their native protocols. |
| **SQLite and managed storage** | Retain work, state, messages, observations and artifact associations; store artifact payloads separately. |
| **Optional Jev advice** | XO/NCO assignment advice and scoped execution-role source/diagnostic assessment through two on-demand MCP tools, using the existing artifacts and telemetry. |

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

The core uses Python 3.11+ and SQLite from the standard library on Linux/macOS or
WSL. Native collaborators need installed, authenticated harnesses and tmux for
managed sessions. Source editing uses the pinned Docker-based Serena
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
| `launch.py`, `native.py`, `profiles.py`, `compat.py` | Persistent native sessions, private profiles and protocol checks |
| `work.py`, `store.py`, `artifacts.py`, `telemetry.py` | Work records, SQLite state, artifacts and measured observations |
| `workspaces.py`, `orders.py`, `retirement.py`, `github.py`, `delivery.py`, `feedback.py` | Job/work-order integration, worktree retirement, PR/CI, review, acceptance and diagnostics |
| `development.py`, `operations.py`, `serena_provider.py` | Installed framework tools, retained long operations and the separate REPL gateway |
| `advice.py`, `jev.py` | Optional work-scoped assessment and the bounded TypeSafe HTTP client |
| `readiness.py`, `run.py` | Operator setup, preflight, evidence index and entry points |
| `tests/`, `integration/` | Protocol/service tests and real Symfony/Serena integrations |

Source and license details are in the
[operator reference](OPERATIONS.md#source-attribution).

An older development system is preserved on the
[`shit` branch](https://github.com/uscient/agentscient/tree/shit).
