# Local setup and readiness

The development environment provides independent control-plane MCP services,
persistent native harness communication, work orders/jobs, telemetry, artifacts,
managed Git/GitHub delivery, installed Symfony development tools and a separate
Serena v2 REPL provider. The Symfony application remains a starting foundation.
This guide covers operator setup and the evidence needed before relying on a local
team. For normal agent usage, see the [roles and tools](control-plane-roles-and-tools.md).

## Stages and completion requirements

| Stage | Requirements | Done means |
| --- | --- | --- |
| Foundation | Use the committed Composer lock: PHP `^8.5.11`, Symfony `8.1.*`, Maker, Mate and MCP Bundle. Keep service attributes, autowiring and autoconfiguration. | Installed Makers generate the native implementation; generated attribute commands register and execute. CI verifies this. |
| Operator setup | Linux/macOS or WSL, Python 3.11+, Git identity and remote access, locked PHP platform, Composer, Docker, selected authenticated harness binaries. All managed harness sessions need tmux. | Team configuration, private state, project binding and pinned Serena image exist. `doctor --online` passes its available checks. |
| Command and context | External CO plus available XO/producer slots; add another slot for concurrent audit. Normal MCP connections only. | CO directs; XO organizes/steers; each collaborator receives its brief and role tools. Unbound members cannot act on arbitrary work. |
| Source work | Job worktree supplied automatically; Serena is separate and restricted to the role's paths. Makers/Mate run through control-plane tools. | Navigation, a persistent REPL value, an allowed edit, installed generation and validation are observed in the bound worktree. Protected paths remain protected. |
| Live coordination | Native conversations stay alive while work proceeds. Reports, evidence and guidance retain their job association. | A live clarification and response are observed with the same native conversation ID; queued messages alone do not establish receipt. |
| Delivery | Save/check/submit through outcome tools; audit the submitted snapshot when needed; inspect before acceptance. | PR/CI/evidence are associated automatically. Changed revisions or dirty work block acceptance. Normal GitHub requirements apply. |
| Turnover | XO accepts jobs into their work order and submits the combined result; CO inspects and concludes it. | Job and final PRs are checked separately. Merged worktrees retire after shutdown; history and evidence remain. |
| Authenticated local acceptance | Run the selected installed harnesses with their real accounts through a bounded, authorized job. | The operator inspects actual native/tool evidence, artifact results, PR and CI. Record the tested revision and harness versions. This stage remains a local check. |

## One-time operator setup

These terminal commands are for the operator. Participating agents use MCP. Start
with an up-to-date local `dev` checkout and these prerequisites:

| Prerequisite | Used by |
| --- | --- |
| Linux/macOS or WSL; Python 3.11+ | Control plane and native harness adapters; SQLite is in the standard library. |
| Git with commit identity and authenticated remote access | Managed worktrees, checkpoints and delivery. |
| GitHub API access | PRs, CI and feedback; configure it as described below. |
| PHP matching the committed Composer platform and Composer | Installed Symfony Makers, Mate and checks. |
| Docker | Separate pinned Serena v2 REPL provider. |
| Installed, authenticated Codex, Claude or Grok binaries | The collaborators you choose; All managed harness sessions need tmux. |

Install the locked application dependencies and build the provider:

```sh
composer install --prefer-dist --no-interaction
docker build --tag agentscient-serena:v2-beta devtools/serena
```

Authenticate the Git remote, GitHub and the native harnesses using their usual local
login. The GitHub service reuses `gh auth token`, an operator-maintained `token_file`
in `team.json`'s `github` section, or `AGENTSCIENT_GITHUB_TOKEN`. Credentials never
appear in agent tool inputs. Git push authentication is separate from API access.

Create the team with shared role policy. The service allocates instances as XO
requests roles; multiple jobs can use the same role. Enable your logged-in vendors
and edit ordered harness/model/reasoning preferences in the generated private
`roles.json` and `vendors.json` files. See [runtime policy](shared-runtime-config.md).

```sh
python3 devtools/run.py init \
  --state "$HOME/.local/state/agentscient-live" \
  --workspace "$PWD" --repository uscient/agentscient --target dev \
  --serena-image agentscient-serena:v2-beta \
  --co owner --member owner:external --runtime
```

`init` enables managed workspaces, default installed Symfony tools/checks and the
default sibling `../wt-ag/` worktree directory. Work orders integrate their jobs
before final delivery into `dev`. Configure the [GitHub rules](../.github/CI.md#github-settings)
for both PR destinations before local acceptance. `init` also enables the
separate Serena image. It does not start models. It refuses to replace an existing
team. For an existing team, edit its private `team.json`; see
[team and project configuration](../devtools/OPERATIONS.md#team-and-project-configuration).
Existing fixed-member teams remain supported. Shared runtime teams set optional
`binary`, `model` and `reasoning` in role profiles. No model is forced by the repository.
For a PHP binary outside PATH, set `project.development.php` to
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

## Start work through CO

Each session calls `onboard` to receive its customized responsibilities, current
tools and shared skill catalog. Use `skill_read` for relevant task guidance; see
[role onboarding](role-onboarding.md).

The CO client uses `direct` to state the objective, completion criteria and
boundaries. That binds XO; XO uses `orchestrate` to create named responsibilities
and start live collaborators. Each receives its brief, role-scoped tools and job
workspace automatically. Native managed profiles also attach the separate Serena
provider when configured. Agents do not assemble connections or select branches.

Use the [role/tool reference](control-plane-roles-and-tools.md) for the actual
catalog, source paths, retained operations, review and acceptance behavior.
Externally hosted specialist clients require the separate
[specialist connections](../devtools/OPERATIONS.md#external-specialist-connections).

## Authenticated local acceptance

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
- XO inspects and accepts each passing contribution, then submits the combined
  result with `work_submit`. CO inspects that delivery and concludes after CI
  passes. Turnover preserves history and permits another job; merged worktrees
  retire after shutdown.
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

The [CI guide](../.github/CI.md) lists the Python/MCP/native-protocol fixtures,
real installed Symfony integration, pinned Serena container integration and local
verification commands. These checks use no model account. Authenticated native
delivery and model behavior require the local acceptance run above.
