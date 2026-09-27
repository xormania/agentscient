# Local agent readiness

Updated: 2026-09-27. Target: Monday, 2026-09-28.

The dev-lane implementation is in `dev`: independent control-plane MCP services,
persistent native harness communication, work orders/jobs, telemetry, artifacts,
managed Git/GitHub delivery, installed Symfony development tools and a separate
Serena v2 REPL provider. The Symfony application remains a starting foundation.
This document defines the setup stages and their completion evidence. It does not
declare an authenticated model run successful because CI passed.

## Stages and completion requirements

| Stage | Requirements | Done means |
| --- | --- | --- |
| Foundation | Use the committed Composer lock: PHP `^8.5.11`, Symfony `8.1.*`, Maker, Mate and MCP Bundle. Keep service attributes, autowiring and autoconfiguration. | Installed Makers generate the native implementation; generated attribute commands register and execute. CI verifies this. |
| Operator setup | Linux/macOS or WSL, Python 3.11+, Git identity and remote access, locked PHP platform, Composer, Docker, selected authenticated harness binaries. Claude background sessions also need tmux. | Team configuration, private state, project binding and pinned Serena image exist. `doctor --online` passes its available checks. |
| Command and context | External CO plus available XO/producer slots; add another slot for concurrent audit. Normal MCP connections only. | CO directs; XO organizes/steers; each collaborator receives its brief and role tools. Unbound members cannot act on arbitrary work. |
| Source work | Job worktree supplied automatically; Serena is separate and restricted to the role's paths. Makers/Mate run through control-plane tools. | Navigation, a persistent REPL value, an allowed edit, installed generation and validation are observed in the bound worktree. Protected paths remain protected. |
| Live coordination | Native conversations stay alive while work proceeds. Reports, evidence and guidance retain their job association. | A live clarification and response are observed with the same native conversation ID; queued messages alone do not establish receipt. |
| Delivery | Save/check/submit through outcome tools; audit the submitted snapshot when needed; inspect before acceptance. | PR/CI/evidence are associated automatically. Changed revisions or dirty work block acceptance. Normal GitHub requirements apply. |
| Turnover | XO accepts or explicitly cancels a named job; CO concludes the finished work order. | Work and evidence remain; collaborators stop and become reusable. A subsequent job starts from the accepted target. |
| Authenticated local acceptance | Run the selected installed harnesses with their real accounts through a bounded, authorized job. | The operator inspects actual native/tool evidence, artifact results, PR and CI. Record the tested revision and harness versions. This stage remains a local check. |

## One-time operator setup

These terminal commands are for the operator. Participating agents use MCP.
From an up-to-date local `dev` checkout, install the locked application dependencies
and build the pinned provider:

```sh
composer install --prefer-dist --no-interaction
docker build --tag agentscient-serena:v2-beta devtools/serena
```

Authenticate the Git remote, GitHub and the native harnesses using their usual local
login. The GitHub service reuses `gh auth token`, an operator-maintained `token_file`
in `team.json`'s `github` section, or `AGENTSCIENT_GITHUB_TOKEN`. Credentials never
appear in agent tool inputs. Git push authentication is separate from API access.

Create the team. Choose the installed harnesses you want; multiple slots can use
the same harness. Names label configured slots, not permanent roles. XO allocates
their actual roles and responsibilities through the control plane.

```sh
python3 devtools/run.py init \
  --state "$HOME/.local/state/agentscient-live" \
  --workspace "$PWD" --repository uscient/agentscient --target dev \
  --serena-image agentscient-serena:v2-beta \
  --co owner --member owner:external \
  --member chief:codex --member worker:claude --member reviewer:grok
```

`init` enables managed workspaces, default installed Symfony tools/checks and the
separate Serena image. It does not start models. It refuses to replace an existing
team. For an existing team, edit its private `team.json`; the equivalent project
configuration is documented in [`devtools/README.md`](../devtools/README.md).
Set each slot's optional `binary`, `model` and `reasoning` there. No model is forced
by the repository. For a PHP binary outside PATH, set `project.development.php` to
its absolute path; `project.development.composer` can select Composer as well.

Check the setup and export the actual CO connection:

```sh
python3 devtools/run.py doctor --state "$HOME/.local/state/agentscient-live" --online
python3 devtools/run.py connection --state "$HOME/.local/state/agentscient-live"
```

Use the returned `mcpServers` object in the user-facing CO client's MCP settings.
It has absolute paths and no `--operator` flag. Keep that connection active while
managed startup, delivery and CI observation are needed. No separate XO connection
needs to be assembled by agents.

`doctor` returns exit code 2 for a failed prerequisite. Its probes inspect the
configured checkout, remote identity, Git identity, private state, locked real PHP
platform, Docker image source label, selected binaries and installed Codex protocol
schema. `--online` additionally reads the remote target and GitHub access. It does
not push, merge, install dependencies, start models, or validate model credentials.
Claude channel registration and Grok ACP authentication are checked on native
startup. A `preflight_passed` result still requires the authenticated acceptance
stage. Image labels identify the configured build; runtime boundary checks are the
separate integration test, not an inference from a label.

## Current role surface

Every bound role gets `work_context`, `work_report` and `guidance_request`.
Configured specialists also get `work_inspect`, `framework_inspect` and `work_check`.
Editing roles get `work_save`, `work_refresh`, `work_recover`, `work_submit` and
`review_respond`. Repository, branch, target, workspace and PR association stay
behind those tools.

| Role | Additional control-plane tools | Serena source access |
| --- | --- | --- |
| CO | `direct`, `monitor`, `conclude` | None |
| XO | `orchestrate`, `monitor`, `steer` | None |
| Coder | Editing tools; `framework_generate` | Product paths |
| Audit | `review_record` | Read-only submitted snapshot |
| Docs | Editing tools | Documentation and README |
| Research | Inspection, reports and evidence | Read-only source |
| Test Writer | Editing tools; `framework_generate` restricted to `make:test` | Tests and PHPUnit configuration |
| Architect | Editing tools | Documentation; other source read-only |

Serena exposes its own `serena_repl`; the service supplies its session and workspace.
Start with `s.info()` for progressive API documentation. Python variables persist
while that provider session remains valid. Background execution is frozen between
calls to coordinate with Git, checks and Makers. The container receives neither
host credentials nor the control database, Docker socket or runtime network.
Installed Symfony commands run as the local service user; their fixed command
interface is not an OS sandbox for application code or Composer plugins.

Research currently covers repository material, supplied sources and retained
evidence. There is no general external web-search provider in the managed profiles.
CO can supply external research as relevant context; provider expansion is separate
from the working source-development path.

## Bounded authenticated acceptance

Use a small owner-approved foundation improvement, or an operator-owned test
repository containing this Symfony foundation. Set the actual objective, completion
criteria and protected paths through CO's `direct`. Do not turn temporary acceptance
probes into product requirements. The local agents should not build or repair their
own dev-lane during this run.

Require the following evidence without prescribing how agents solve the job:

- XO starts a persistent collaborator; it receives the right tools and brief.
- The collaborator uses installed Maker metadata/generation, Mate diagnostics,
  Serena REPL and configured checks for the bounded change.
- A clarification arrives while work is underway, is answered, and the native
  conversation identity remains stable. Pause/resume also preserves that identity.
- The result is checkpointed and submitted with retained evidence. Audit, when
  assigned, reviews that revision; findings and responses arrive through MCP.
- XO inspects and accepts the current passing revision through ordinary GitHub
  rules. CO sees the result. Turnover preserves history and permits another job.
- Native shell/edit attempts are denied; observed usage is reported honestly.
  A stopped/restarted session is a new conversation, not claimed transcript recovery.

After the run, the operator can export a compact evidence index for its work-order
number (the number is an operator argument, not agent bookkeeping):

```sh
python3 devtools/run.py evidence \
  --state "$HOME/.local/state/agentscient-live" --work-order 1
```

It reads existing state without upgrading or changing it. It lists native identities,
completed tool-call counts, message/acknowledgement states, operation states,
artifacts and job/PR/acceptance records. It does not certify success: a completed call
can return a failed check or an asynchronous receipt. Inspect the retained results
and native traces alongside this index. Keep the acceptance assessment with the
work-order result.

## Verification already available

CI runs the Python/MCP/native-protocol/Git/GitHub fixtures and the actual installed
Symfony integration, including Maker attributes/autoconfiguration and Mate.
It also builds the pinned upstream Serena beta and executes persistent Python,
PHPactor navigation, edits, protected-file denial, pause/resume and a checkpoint
inside the real container. These integration scripts are available locally:

```sh
python3 devtools/integration/symfony.py
python3 devtools/integration/serena.py
```

They use disposable worktrees and no model account. Neither substitutes for the
authenticated live-harness acceptance above. The old development system remains
removed; this setup adds no dispatch workflow, grant system or mandatory review
ladder. The trusted operator catalog is for setup/repair and is never attached to
normal managed roles.
